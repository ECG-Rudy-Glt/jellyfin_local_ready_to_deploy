#!/usr/bin/env bash
# Prépare MEDIA_DIR pour RivenVFS : bind mount sur lui-même + propagation rshared.
# Nécessaire pour que le montage FUSE créé par le conteneur riven devienne visible
# côté hôte, et donc dans le conteneur jellyfin (bind mount séparé du même
# chemin) — voir ARCHITECTURE.md "Le piège du montage média". Idempotent, à relancer
# sans risque (y compris après un reboot, si tu ne veux pas de service systemd dédié).
set -euo pipefail

cd "$(dirname "$0")/.."
set -a
# shellcheck disable=SC1091
[ -f .env ] && source .env
set +a

MEDIA_DIR_ABS="$(mkdir -p "${MEDIA_DIR:-./data/media}" && cd "${MEDIA_DIR:-./data/media}" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Ce script a besoin de sudo pour monter/propager ${MEDIA_DIR_ABS}." >&2
  exec sudo "$0" "$@"
fi

if ! mountpoint -q "$MEDIA_DIR_ABS"; then
  mount --bind "$MEDIA_DIR_ABS" "$MEDIA_DIR_ABS"
  echo "Bind mount créé sur $MEDIA_DIR_ABS"
fi

mount --make-rshared "$MEDIA_DIR_ABS"

if findmnt -T "$MEDIA_DIR_ABS" -o PROPAGATION | grep -q shared; then
  echo "OK — $MEDIA_DIR_ABS est en propagation shared."
else
  echo "ÉCHEC — la propagation shared n'a pas pu être vérifiée sur $MEDIA_DIR_ABS" >&2
  exit 1
fi
