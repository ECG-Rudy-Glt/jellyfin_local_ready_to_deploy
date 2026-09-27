#!/usr/bin/env bash
# Crée config/decypharr/config.json depuis l'exemple (une seule fois), en reportant
# PUID/PGID de .env. N'écrase jamais une config existante : Decypharr la modifie
# lui-même quand tu changes un réglage dans son interface.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
[ -f .env ] && source .env
set +a

dest=config/decypharr/config.json
if [ -f "$dest" ]; then
  echo "$dest existe déjà, laissé tel quel."
  exit 0
fi

python3 - "$dest" <<'PY'
import json, os, sys
cfg = json.load(open("config/decypharr/config.json.example"))
cfg["mount"]["dfs"]["uid"] = int(os.environ.get("PUID", 1000))
cfg["mount"]["dfs"]["gid"] = int(os.environ.get("PGID", 1000))
with open(sys.argv[1], "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
chmod 600 "$dest"
echo "$dest créé (la clé API reste dans .env)."
