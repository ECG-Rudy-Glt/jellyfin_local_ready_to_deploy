#!/usr/bin/env python3
"""Riven stuck-item watchdog — relance ce qui reste bloqué (Unknown/Indexed/Scraped).

Plusieurs causes distinctes se traduisent par le même symptôme (un item qui ne
progresse plus jamais tout seul) : un épisode diffusé d'une série "en cours"
jamais renvoyé dans le pipeline de scrape, un item fraîchement demandé dont le
traitement échoue silencieusement après le fetch, ou une saison traitée en pack
qui reste bloquée sans jamais télécharger. Ce script comble ces trous avec une
règle générale : tout item "leaf" (film ou épisode — pas show/season, dont le
retry direct ne cascade pas fiablement en pratique) resté en "Unknown",
"Indexed" ou "Scraped" plus de 30 min est relancé via `/items/retry`.

Backoff : sans frein, les items sans source valide nulle part seraient relancés
en boucle toutes les 30 min pour toujours, saturant scrapers/débrideur et
ralentissant les items neufs légitimes. Compteur de tentatives local
(STATE_FILE) : un item est relancé normalement pour ses 3 premières tentatives,
puis passe à une relance quotidienne seulement au-delà. Priorité par nombre de
tentatives (pas par ancienneté) : sinon un backlog zombie ancien monopolise
indéfiniment le plafond par cycle au détriment des items neufs.

⚠️ Riven écrit ses timestamps sans fuseau horaire explicite dans sa base — si tu
observes un décalage constant entre le seuil "30 minutes" annoncé et la réalité,
compare le fuseau du conteneur `riven-db` (`docker exec riven-db date`) à celui
de l'hôte qui exécute ce script, et ajuste STUCK_QUERY en conséquence
(`NOW() AT TIME ZONE '<fuseau conteneur>'` au lieu de `NOW()`).

Config : /etc/media-guards.env (RIVEN_API_KEY — même valeur que
RIVEN_BACKEND_API_KEY dans le .env principal). Déployé par Ansible — systemd
timer riven-ongoing-watchdog.timer, toutes les 30 min.
"""
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone

RIVEN_API_KEY = os.environ["RIVEN_API_KEY"]
RIVEN_API = "http://localhost:8080/api/v1"
STATE_FILE = "/var/lib/media-guards/riven-ongoing-watchdog/state.json"

MAX_FAST_ATTEMPTS = 3
SLOW_RETRY_INTERVAL = timedelta(hours=24)
BATCH_LIMIT = 40

QUERY = """
SELECT id
FROM "MediaItem"
WHERE type IN ('movie', 'episode')
  AND last_state IN ('Unknown', 'Indexed', 'Scraped')
  AND COALESCE(scraped_at, indexed_at, requested_at) < NOW() - INTERVAL '30 minutes'
ORDER BY COALESCE(scraped_at, indexed_at, requested_at) ASC;
"""


def stuck_item_ids():
    result = subprocess.run(
        ["docker", "exec", "riven-db", "psql", "-U", "postgres", "-d", "riven", "-t", "-A", "-c", QUERY],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def eligible_now(entry, now):
    if entry["attempts"] < MAX_FAST_ATTEMPTS:
        return True
    last_retry = datetime.fromisoformat(entry["last_retry"])
    return now - last_retry >= SLOW_RETRY_INTERVAL


def retry(ids):
    req = urllib.request.Request(
        f"{RIVEN_API}/items/retry",
        data=json.dumps({"ids": ids}).encode(),
        method="POST",
        headers={"x-api-key": RIVEN_API_KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    stuck_ids = stuck_item_ids()
    if not stuck_ids:
        print("Aucun film/épisode bloqué (Unknown/Indexed/Scraped) depuis plus de 30 min.")
        save_state({})
        return

    now = datetime.now(timezone.utc)
    state = load_state()
    state = {i: state[i] for i in stuck_ids if i in state}

    eligible = [i for i in stuck_ids if i not in state or eligible_now(state[i], now)]
    in_backoff = len(stuck_ids) - len(eligible)
    eligible.sort(key=lambda i: state.get(i, {"attempts": 0})["attempts"])
    ids = eligible[:BATCH_LIMIT]
    capped = len(eligible) - len(ids)

    if not ids:
        print(f"{len(stuck_ids)} item(s) toujours bloqué(s), tous en backoff (>={MAX_FAST_ATTEMPTS} tentatives, prochain essai dans <24h).")
        save_state(state)
        return

    result = retry(ids)
    for i in ids:
        attempts = state.get(i, {"attempts": 0})["attempts"] + 1
        state[i] = {"attempts": attempts, "last_retry": now.isoformat()}
    save_state(state)

    print(f"Relancé {len(ids)} item(s) ({in_backoff} en backoff, {capped} au-delà du plafond de {BATCH_LIMIT}) : {ids} — {result}")


if __name__ == "__main__":
    main()
