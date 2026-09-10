#!/usr/bin/env bash
# Installe les garde-fous (scripts/*.py) comme timers systemd sur cet hôte.
# Alternative sans Ansible à `ansible-playbook deploy-media-stack.yml --tags guards`
# — même résultat. À lancer une fois l'onboarding terminé (README §3), une fois
# JELLYFIN_API_KEY et RIVEN_BACKEND_API_KEY renseignés dans .env.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$(id -u)" -ne 0 ]; then
  exec sudo "$0" "$@"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${JELLYFIN_API_KEY:?JELLYFIN_API_KEY manquant dans .env — termine l'onboarding Jellyfin d'abord (README §3)}"
: "${RIVEN_BACKEND_API_KEY:?RIVEN_BACKEND_API_KEY manquant dans .env}"

PROJECT_DIR="$(pwd)"
MEDIA_DIR_ABS="$PROJECT_DIR/${MEDIA_DIR#./}"
JELLYFIN_CACHE_DIR_ABS="$PROJECT_DIR/${JELLYFIN_CACHE_DIR#./}"
RIVEN_CACHE_DIR_ABS="$PROJECT_DIR/${RIVEN_CACHE_DIR#./}"

install -m 0600 /dev/null /etc/media-guards.env
cat > /etc/media-guards.env <<EOF
JELLYFIN_URL=http://localhost:${JELLYFIN_PORT:-8096}
JELLYFIN_API_KEY=${JELLYFIN_API_KEY}
RIVEN_URL=http://localhost:${RIVEN_PORT:-8080}
RIVEN_API_KEY=${RIVEN_BACKEND_API_KEY}
MEDIA_DIR=${MEDIA_DIR_ABS}
JELLYFIN_CACHE_DIR=${JELLYFIN_CACHE_DIR_ABS}
RIVEN_CACHE_DIR=${RIVEN_CACHE_DIR_ABS}
EOF

declare -A INTERVALS=(
  [riven-playback-guard]="2min:2min"
  [riven-stall-detector]="15min:15min"
  [riven-cache-cleanup]="20min:8h"
  [riven-episode-retry-guard]="10min:1h"
  [riven-ongoing-watchdog]="10min:30min"
  [jellyfin-disk-guard]="5min:15min"
  [jellyfin-scan-guard]="10min:1h"
)

for name in "${!INTERVALS[@]}"; do
  boot="${INTERVALS[$name]%%:*}"
  interval="${INTERVALS[$name]##*:}"

  install -m 0755 "scripts/${name}.py" "/usr/local/bin/${name}.py"

  cat > "/etc/systemd/system/${name}.service" <<EOF
[Unit]
Description=Media stack guard: ${name}
After=docker.service

[Service]
Type=oneshot
EnvironmentFile=/etc/media-guards.env
ExecStart=/usr/bin/python3 /usr/local/bin/${name}.py
EOF

  cat > "/etc/systemd/system/${name}.timer" <<EOF
[Unit]
Description=Timer for ${name}

[Timer]
OnBootSec=${boot}
OnUnitActiveSec=${interval}

[Install]
WantedBy=timers.target
EOF

  systemctl enable --now "${name}.timer"
  echo "Installé : ${name}.timer (toutes les ${interval})"
done

systemctl daemon-reload
echo "Garde-fous installés. Vérifier : systemctl list-timers | grep -E 'riven-|jellyfin-'"
