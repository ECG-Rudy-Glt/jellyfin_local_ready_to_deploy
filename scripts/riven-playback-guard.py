#!/usr/bin/env python3
"""Met en pause le scraping/téléchargement Riven pendant une lecture Jellyfin active.

Le trafic "lecture en cours" (RivenVFS → débrideur) et le trafic "arrière-plan"
(scraping/téléchargement de nouveaux items) passent par les mêmes connexions
débrideur depuis le même conteneur, sans signal réseau permettant de les isoler
par une règle de pare-feu — la seule protection possible est côté application.
Sans ce garde-fou, un scraping en masse (plusieurs items lancés manuellement, ou
juste un backlog important) peut saturer le pool de connexions et provoquer des
ReadTimeout / micro-coupures sur un flux en cours de lecture ailleurs.

Ce script vérifie les sessions Jellyfin actives à chaque passage :
- Si une lecture est en cours : met en pause (`/api/v1/items/pause`) les items
  Riven en état "Indexed" (scraping pas encore fait — le plus gros consommateur
  de CPU), "Scraped" (streams trouvés, pas encore téléchargés) et
  "PartiallyCompleted", pour qu'aucun nouveau travail ne démarre pendant la
  lecture. Les items déjà en cours de traitement ne sont pas interrompus de
  force (fenêtre de recouvrement bornée à la taille du pool de threads Riven,
  se résout d'elle-même).
- Si plus aucune lecture n'est active : remet en route (`/api/v1/items/unpause`)
  les items mis en pause par ce script (liste persistée localement, pour ne
  jamais toucher des items mis en pause manuellement par ailleurs).

Config : /etc/media-guards.env (JELLYFIN_URL, JELLYFIN_API_KEY, RIVEN_URL,
RIVEN_API_KEY). Déployé par Ansible — systemd timer riven-playback-guard.timer,
toutes les 2 minutes.
"""
import json
import os
import urllib.request
from pathlib import Path

JELLYFIN_URL = os.environ["JELLYFIN_URL"]
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]
RIVEN_URL = os.environ["RIVEN_URL"]
RIVEN_API_KEY = os.environ["RIVEN_API_KEY"]

PAUSED_STATE_FILE = "/var/lib/media-guards/riven-playback-guard/paused_by_guard.json"

PAUSABLE_STATES = ["Indexed", "Scraped", "PartiallyCompleted"]


def jellyfin_has_active_playback():
    req = urllib.request.Request(f"{JELLYFIN_URL}/Sessions", headers={"X-Emby-Token": JELLYFIN_API_KEY})
    with urllib.request.urlopen(req, timeout=15) as r:
        sessions = json.loads(r.read())
    return any(s.get("NowPlayingItem") for s in sessions)


def riven_request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{RIVEN_URL}{path}", method=method, data=data,
        headers={"x-api-key": RIVEN_API_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def pausable_item_ids():
    ids = []
    for state in PAUSABLE_STATES:
        result = riven_request("GET", f"/api/v1/items?states={state}&limit=500")
        ids.extend(i["id"] for i in result.get("items", []))
    return ids


def paused_item_ids():
    result = riven_request("GET", "/api/v1/items?states=Paused&limit=500")
    return {i["id"] for i in result.get("items", [])}


def read_guard_paused_ids():
    p = Path(PAUSED_STATE_FILE)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def write_guard_paused_ids(ids):
    p = Path(PAUSED_STATE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ids))


def main():
    if jellyfin_has_active_playback():
        ids = pausable_item_ids()
        if not ids:
            print("Lecture active mais aucun item en attente de traitement — rien à faire.")
            return
        riven_request("POST", "/api/v1/items/pause", {"ids": [str(i) for i in ids]})
        # Vérifie lesquels sont VRAIMENT passés en pause avant de les suivre : l'appel
        # /pause répond "succès" pour tous, mais un item peut perdre la course contre
        # le scraper Riven lui-même (plusieurs items traités en parallèle) et rester
        # dans son état d'origine malgré tout, sans erreur remontée. Ne suivre que les
        # confirmés évite de créer de faux positifs ; les perdants réapparaîtront
        # simplement dans la requête du prochain cycle (auto-cicatrisant).
        actually_paused = paused_item_ids()
        confirmed = [i for i in ids if i in actually_paused]
        lost_race = len(ids) - len(confirmed)
        # Accumule avec les IDs déjà mis en pause lors de cycles précédents de la même
        # session de lecture (un item mis en pause change d'état, donc disparaît de la
        # requête du prochain cycle). Écraser la liste au lieu de l'étendre laisserait
        # des items orphelins (jamais remis en route) sur une lecture longue.
        previously_paused = read_guard_paused_ids()
        all_paused = sorted(set(previously_paused) | set(confirmed))
        write_guard_paused_ids(all_paused)
        msg = f"Lecture active — {len(confirmed)} item(s) confirmés en pause ({len(all_paused)} au total suivis)."
        if lost_race:
            msg += f" {lost_race} item(s) pas encore pausés (course perdue contre le scraper, retenté au prochain cycle)."
        print(msg)
        return

    paused_ids = read_guard_paused_ids()
    if not paused_ids:
        print("Aucune lecture active, rien en pause par ce garde-fou — rien à faire.")
        return

    riven_request("POST", "/api/v1/items/unpause", {"ids": [str(i) for i in paused_ids]})
    write_guard_paused_ids([])
    print(f"Plus de lecture active — {len(paused_ids)} item(s) remis en route.")


if __name__ == "__main__":
    main()
