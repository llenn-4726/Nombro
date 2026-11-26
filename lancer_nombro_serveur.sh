#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PORT="${FLASK_PORT:-5000}"
cd "$APP_DIR"

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import flask, waitress' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt
fi

printf '\nNombro serveur démarre sur le réseau local.\n'
printf 'Sur ce PC : http://localhost:%s\n' "$PORT"
LAN_IPS="$(hostname -I 2>/dev/null | xargs || true)"
if [[ -n "$LAN_IPS" ]]; then
    for IP in $LAN_IPS; do
        printf 'Depuis un autre PC du même réseau : http://%s:%s\n' "$IP" "$PORT"
    done
else
    printf 'Depuis un autre PC, utilise l’adresse IP locale de ce PC : http://IP:%s\n' "$PORT"
fi
printf 'Garde cette fenêtre ouverte. Ctrl+C arrête le serveur.\n\n'
export FLASK_HOST="0.0.0.0"
export FLASK_PORT="$PORT"
exec .venv/bin/python app.py
