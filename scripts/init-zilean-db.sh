#!/usr/bin/env bash
# Crée la base "zilean" dans riven-db si elle n'existe pas encore. L'image
# ipromknight/zilean testée ici la crée elle-même au premier démarrage (elle se
# connecte en tant que postgres/superuser) — ce script est un filet de sécurité
# pour une image plus ancienne/future qui ne le ferait pas. Idempotent, sans
# effet si la base existe déjà.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Attente de riven-db..."
until docker compose exec -T riven-db pg_isready -U postgres >/dev/null 2>&1; do
  sleep 2
done

exists="$(docker compose exec -T riven-db psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='zilean'")"
if [ "$exists" = "1" ]; then
  echo "Base zilean déjà présente."
else
  docker compose exec -T riven-db psql -U postgres -c "CREATE DATABASE zilean;"
  docker compose restart zilean
  echo "Base zilean créée, conteneur zilean redémarré."
fi
