#!/usr/bin/env python3
"""Vérifie que RivenVFS est sain avant de lancer le scan de bibliothèque Jellyfin.

Si RivenVFS (le montage FUSE fourni par le conteneur Riven) devient
temporairement vide/injoignable — coupure réseau, panne débrideur — pendant
qu'un scan de bibliothèque se déclenche, Jellyfin peut interpréter les dossiers
vides comme des suppressions réelles et effacer des items de sa base alors
qu'aucun fichier n'a réellement disparu côté Riven.

Ce script remplace le déclencheur interne "Analyser la médiathèque" de Jellyfin
(désactivé via l'API par le playbook Ansible) : il compare le nombre de
films/séries visibles sur disque (via le point de montage RivenVFS) au nombre
que Riven connaît en base (`/api/v1/stats`) avant d'autoriser le scan — si
l'écart est trop important, le scan est sauté (log seulement, nouvelle
tentative au prochain passage) plutôt que de risquer une suppression en masse.
Sinon, déclenche un scan normal via l'API Jellyfin (`/Library/Refresh`).

Config : /etc/media-guards.env (JELLYFIN_URL, JELLYFIN_API_KEY, RIVEN_URL,
RIVEN_API_KEY, MEDIA_DIR). Déployé par Ansible — systemd timer
jellyfin-scan-guard.timer, toutes les heures.
"""
import json
import os
import subprocess
import urllib.request

JELLYFIN_URL = os.environ["JELLYFIN_URL"]
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]
RIVEN_URL = os.environ["RIVEN_URL"]
RIVEN_API_KEY = os.environ["RIVEN_API_KEY"]
MEDIA_DIR = os.environ["MEDIA_DIR"]

VFS_MOVIES_PATH = f"{MEDIA_DIR}/vfs/movies"
VFS_SHOWS_PATH = f"{MEDIA_DIR}/vfs/shows"

# Si le montage média voit moins de ce ratio du nombre de films/séries connus de
# Riven, il est considéré cassé (coupure réseau/débrideur, pas une vraie
# suppression). Volontairement bas (50%, pas 80-90%) : quelques items en cours
# de re-scrape font chuter le ratio normalement de quelques % sans que ce soit
# une vraie panne — une vraie panne réseau/débrideur fait chuter le ratio vers
# 0%, largement sous ce seuil.
HEALTH_THRESHOLD = 0.5


def riven_stats():
    req = urllib.request.Request(f"{RIVEN_URL}/api/v1/stats", headers={"x-api-key": RIVEN_API_KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def folder_count(path):
    result = subprocess.run(
        ["find", path, "-mindepth", "1", "-maxdepth", "1"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return len([line for line in result.stdout.splitlines() if line.strip()])


def trigger_jellyfin_scan():
    req = urllib.request.Request(f"{JELLYFIN_URL}/Library/Refresh", method="POST", headers={"X-Emby-Token": JELLYFIN_API_KEY})
    urllib.request.urlopen(req, timeout=15)


def main():
    stats = riven_stats()
    expected_movies = stats.get("total_movies", 0)
    expected_shows = stats.get("total_shows", 0)

    actual_movies = folder_count(VFS_MOVIES_PATH)
    actual_shows = folder_count(VFS_SHOWS_PATH)

    movies_ok = expected_movies == 0 or actual_movies >= expected_movies * HEALTH_THRESHOLD
    shows_ok = expected_shows == 0 or actual_shows >= expected_shows * HEALTH_THRESHOLD

    if not (movies_ok and shows_ok):
        print(
            f"RivenVFS semble cassé/indisponible — {actual_movies}/{expected_movies} films, "
            f"{actual_shows}/{expected_shows} séries visibles sur disque (seuil "
            f"{HEALTH_THRESHOLD:.0%}). Scan Jellyfin sauté pour ne pas supprimer des items "
            f"par erreur — nouvelle tentative au prochain passage."
        )
        return

    print(f"RivenVFS sain ({actual_movies}/{expected_movies} films, {actual_shows}/{expected_shows} séries) — déclenchement du scan Jellyfin.")
    trigger_jellyfin_scan()
    print("Scan déclenché.")


if __name__ == "__main__":
    main()
