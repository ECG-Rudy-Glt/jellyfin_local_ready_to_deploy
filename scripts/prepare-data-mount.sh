#!/usr/bin/env bash
# Rend DATA_DIR « shared » : bind mount sur lui-même + propagation rshared.
# Sans ça, le montage FUSE créé par Decypharr reste invisible pour les autres
# conteneurs (voir ARCHITECTURE.md « Le piège du montage »). Idempotent ; à relancer
# après chaque redémarrage de l'hôte si tu n'utilises pas l'unité systemd du README.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
[ -f .env ] && source .env
set +a

: "${DATA_DIR:?DATA_DIR non défini dans .env}"
case "$DATA_DIR" in
  /*) ;;
  *) echo "DATA_DIR doit être un chemin absolu (actuel : $DATA_DIR)" >&2; exit 1 ;;
esac

if [ "$(id -u)" -ne 0 ]; then
  exec sudo --preserve-env=DATA_DIR,CACHE_DIR,PUID,PGID "$0" "$@"
fi

mkdir -p "$DATA_DIR"/{remote,symlinks,media/movies,media/tv}
mkdir -p "${CACHE_DIR:-./data/cache}"/{decypharr,jellyfin}
chown -R "${PUID:-1000}:${PGID:-1000}" "$DATA_DIR" "${CACHE_DIR:-./data/cache}" 2>/dev/null || true

if ! mountpoint -q "$DATA_DIR"; then
  mount --bind "$DATA_DIR" "$DATA_DIR"
  echo "Bind mount créé sur $DATA_DIR"
fi
mount --make-rshared "$DATA_DIR"

if findmnt -no PROPAGATION "$DATA_DIR" | grep -q shared; then
  echo "OK : $DATA_DIR est en propagation shared."
else
  echo "ÉCHEC : propagation shared non vérifiée sur $DATA_DIR" >&2
  exit 1
fi
