#!/usr/bin/env python3
"""Riven VFS cache cleanup — vide le cache disque de RivenVFS périodiquement.

Le cache VFS est généralement petit comparé à un film 4K (souvent 20-50 Go) —
un seul film en 4K peut donc déjà faire tourner l'éviction en continu pendant
toute la lecture, ce qui peut dans de rares cas mener à un cache corrompu
(micro-coupures en lecture, "partial file" côté FFmpeg sans erreur réseau
correspondante côté débrideur). Vider périodiquement borne ce risque à moindre
coût — le cache est par nature une donnée régénérable, pas une source de vérité.

Ce script vide le répertoire de cache RivenVFS côté hôte — SAUF si une lecture
Jellyfin est en cours (vérifié via `/Sessions`), pour ne jamais interrompre un
visionnage en train de se dérouler.

Config : /etc/media-guards.env (JELLYFIN_URL, JELLYFIN_API_KEY, RIVEN_CACHE_DIR
— même valeur que RIVEN_CACHE_DIR dans le .env principal, voir docker-compose.yml).
Déployé par Ansible — systemd timer riven-cache-cleanup.timer, 3x/jour.
"""
import json
import os
import shutil
import urllib.request
from pathlib import Path

JELLYFIN_URL = os.environ["JELLYFIN_URL"]
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]
CACHE_DIR = Path(os.environ["RIVEN_CACHE_DIR"])


def someone_is_watching():
    req = urllib.request.Request(f"{JELLYFIN_URL}/Sessions", headers={"X-Emby-Token": JELLYFIN_API_KEY})
    with urllib.request.urlopen(req, timeout=30) as r:
        sessions = json.loads(r.read())
    return any(s.get("NowPlayingItem") for s in sessions)


def cache_size_bytes(path):
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def main():
    if someone_is_watching():
        print("Lecture en cours détectée — nettoyage sauté cette fois.")
        return

    before = cache_size_bytes(CACHE_DIR)
    for entry in CACHE_DIR.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
        else:
            entry.unlink(missing_ok=True)

    print(f"Cache RivenVFS vidé ({before / (1024**3):.1f} Go libérés).")


if __name__ == "__main__":
    main()
