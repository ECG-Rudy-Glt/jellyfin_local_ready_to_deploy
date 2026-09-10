#!/usr/bin/env python3
"""Disk guard Jellyfin — vide le cache de transcodage si le disque approche du plein.

Le cache de transcodage HLS peut accumuler des fichiers orphelins (lectures
interrompues sans nettoyage) et remplir un disque en quelques heures — plus
vite que la tâche native Jellyfin "Nettoyer le dossier des transcodages" (ne
supprime que les fichiers de plus d'un jour, une fois par jour). Ce script est
un filet de sécurité indépendant : vérifie l'usage disque périodiquement, vide
le cache de transcodage dès que le seuil est dépassé (fichiers 100% jetables,
régénérés à la demande par Jellyfin).

Config : /etc/media-guards.env (JELLYFIN_CACHE_DIR — même valeur que
JELLYFIN_CACHE_DIR dans le .env principal). Déployé par Ansible — systemd timer
jellyfin-disk-guard.timer, toutes les 15 min.
"""
import os
import shutil
import subprocess
from pathlib import Path

THRESHOLD_PERCENT = 80
CACHE_DIR = Path(os.environ["JELLYFIN_CACHE_DIR"])
TRANSCODE_DIR = CACHE_DIR / "transcodes"


def disk_usage_percent(path):
    total, used, free = shutil.disk_usage(path)
    return used / total * 100


def clear_transcodes():
    if not TRANSCODE_DIR.exists():
        return 0
    removed = 0
    for entry in TRANSCODE_DIR.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def main():
    pct = disk_usage_percent(CACHE_DIR)
    if pct < THRESHOLD_PERCENT:
        print(f"Disque à {pct:.1f}% — sous le seuil ({THRESHOLD_PERCENT}%), rien à faire.")
        return

    print(f"Disque à {pct:.1f}% — seuil ({THRESHOLD_PERCENT}%) dépassé, purge du cache de transcodage.")
    removed = clear_transcodes()
    new_pct = disk_usage_percent(CACHE_DIR)
    print(f"{removed} entrée(s) supprimée(s) — disque maintenant à {new_pct:.1f}%.")

    if new_pct >= THRESHOLD_PERCENT:
        print("ATTENTION : toujours au-dessus du seuil après purge — le cache de transcodage "
              "n'est pas la cause principale cette fois, investiguer manuellement.")
        subprocess.run(["du", "-x", "--max-depth=2", "-h", str(CACHE_DIR.parent)], check=False)


if __name__ == "__main__":
    main()
