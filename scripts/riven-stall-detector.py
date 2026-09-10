#!/usr/bin/env python3
"""Détecteur de plantage silencieux Riven — redémarre automatiquement si besoin.

Riven peut se figer en interne (thread bloqué) sans que le conteneur Docker ne
plante — le healthcheck HTTP répond (endpoint léger) mais plus aucun scraper ne
tourne. Symptôme : CPU/réseau au repos, zéro item qui progresse, alors que des
items attendent d'être traités. Root cause générique non identifiable à l'avance
(pas un problème de charge/ressources) ; seul fix connu : redémarrer le conteneur.

Détection : au moins un item "leaf" (film/épisode) bloqué depuis plus de 30 min
(même requête que riven-ongoing-watchdog.py) ET aucune activité SCRAPER/DEBRID
dans les logs Riven depuis STALL_THRESHOLD_MINUTES. Les deux conditions ensemble
évitent les faux positifs (rien à faire = normal, pas un plantage).

Garde-fous avant de redémarrer :
- Container up depuis moins de MIN_UPTIME_MINUTES : on saute (laisse le temps à
  un restart récent de repartir, évite une boucle de redémarrage).
- Session Jellyfin active (lecture en cours) : on saute — RivenVFS est monté en
  FUSE par ce même conteneur, un restart couperait tout flux en cours.

Config : /etc/media-guards.env (JELLYFIN_URL, JELLYFIN_API_KEY). Déployé par
Ansible — systemd timer riven-stall-detector.timer, toutes les 15 min.
"""
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone

JELLYFIN_URL = os.environ["JELLYFIN_URL"]
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]

STALL_THRESHOLD_MINUTES = 15
MIN_UPTIME_MINUTES = 20

STUCK_QUERY = """
SELECT count(*)
FROM "MediaItem"
WHERE type IN ('movie', 'episode')
  AND last_state IN ('Unknown', 'Indexed', 'Scraped')
  AND COALESCE(scraped_at, indexed_at, requested_at) < NOW() - INTERVAL '30 minutes';
"""


def stuck_count():
    result = subprocess.run(
        ["docker", "exec", "riven-db", "psql", "-U", "postgres", "-d", "riven", "-t", "-A", "-c", STUCK_QUERY],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return int(result.stdout.strip())


def recent_scraper_activity():
    result = subprocess.run(
        ["docker", "logs", "riven", "--since", f"{STALL_THRESHOLD_MINUTES}m"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    combined = result.stdout + result.stderr
    return "SCRAPER" in combined or "DEBRID" in combined


def container_uptime_minutes():
    result = subprocess.run(
        ["docker", "inspect", "riven", "--format", "{{.State.StartedAt}}"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    started = datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - started).total_seconds() / 60


def jellyfin_has_active_playback():
    req = urllib.request.Request(f"{JELLYFIN_URL}/Sessions", headers={"X-Emby-Token": JELLYFIN_API_KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        sessions = json.loads(r.read())
    return any(s.get("NowPlayingItem") for s in sessions)


def main():
    stuck = stuck_count()
    if stuck == 0:
        print("Aucun item bloqué depuis plus de 30 min — rien à vérifier.")
        return

    if recent_scraper_activity():
        print(f"{stuck} item(s) bloqué(s) mais activité scraper détectée dans les {STALL_THRESHOLD_MINUTES} dernières minutes — pipeline vivant.")
        return

    uptime = container_uptime_minutes()
    if uptime < MIN_UPTIME_MINUTES:
        print(f"Figement suspecté ({stuck} items bloqués, aucune activité scraper) mais conteneur up depuis {uptime:.0f} min seulement — on laisse le temps, pas de restart.")
        return

    if jellyfin_has_active_playback():
        print(f"Figement suspecté ({stuck} items bloqués, aucune activité scraper) mais session Jellyfin active — restart sauté par précaution (RivenVFS/FUSE).")
        return

    print(f"Figement confirmé : {stuck} item(s) bloqué(s), aucune activité scraper depuis {STALL_THRESHOLD_MINUTES} min, conteneur up depuis {uptime:.0f} min, aucune lecture active. Redémarrage de riven.")
    subprocess.run(["docker", "restart", "riven"], check=True, timeout=60)
    print("Redémarré.")


if __name__ == "__main__":
    main()
