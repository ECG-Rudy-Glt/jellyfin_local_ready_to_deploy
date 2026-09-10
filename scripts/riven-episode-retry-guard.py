#!/usr/bin/env python3
"""Retente les épisodes Riven bloqués en "Requested" après un scrape échoué.

Le scheduler natif de retry de Riven ne retente que les items de type
movie/show, jamais les épisodes individuellement — un épisode dont la première
tentative de scrape échoue peut donc rester bloqué indéfiniment, sans aucun
mécanisme de retry automatique côté Riven. Ce garde-fou comble ce trou : retente
via `/api/v1/items/retry` tout épisode encore en "Requested" plus de
STUCK_THRESHOLD_MINUTES après sa dernière tentative de scrape (`scraped_at`).

Config : /etc/media-guards.env (RIVEN_URL, RIVEN_API_KEY). Déployé par Ansible —
systemd timer riven-episode-retry-guard.timer, toutes les heures.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

RIVEN_URL = os.environ["RIVEN_URL"]
RIVEN_API_KEY = os.environ["RIVEN_API_KEY"]
STUCK_THRESHOLD_MINUTES = 60


def riven_request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{RIVEN_URL}{path}", data=data, method=method)
    req.add_header("x-api-key", RIVEN_API_KEY)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def stuck_episode_ids():
    result = riven_request("GET", "/api/v1/items?states=Requested&type=episode&limit=500")
    now = datetime.datetime.now(datetime.timezone.utc)
    stuck = []
    for item in result.get("items", []):
        scraped_at = item.get("scraped_at")
        if not scraped_at:
            continue
        scraped_dt = datetime.datetime.fromisoformat(scraped_at).replace(tzinfo=datetime.timezone.utc)
        age_minutes = (now - scraped_dt).total_seconds() / 60
        if age_minutes >= STUCK_THRESHOLD_MINUTES:
            stuck.append(str(item["id"]))
    return stuck


def main():
    ids = stuck_episode_ids()
    if not ids:
        print("Aucun épisode bloqué en Requested après un scrape échoué.")
        return

    result = riven_request("POST", "/api/v1/items/retry", body={"ids": ids})
    print(f"Retried {len(ids)} épisodes bloqués : {result.get('message', '')}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"Erreur de connexion à Riven : {e}", file=sys.stderr)
        sys.exit(1)
