#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/llenn/Documents/Codex/2026-11-18/fai"
APP_URL="http://localhost:5000"
cd "$APP_DIR"

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import flask, waitress' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt
fi

open_firefox() {
    nohup firefox --new-window "$APP_URL" >/dev/null 2>&1 </dev/null &
}

if .venv/bin/python -c 'import socket; s=socket.socket(); s.settimeout(.3); result=s.connect_ex(("127.0.0.1", 5000)); s.close(); raise SystemExit(result != 0)' 2>/dev/null; then
    echo "Nombro tourne déjà. Firefox va s'ouvrir sur l'application."
    open_firefox
    exit 0
fi

(
    for _ in {1..80}; do
        if .venv/bin/python -c 'import socket; s=socket.socket(); s.settimeout(.2); result=s.connect_ex(("127.0.0.1", 5000)); s.close(); raise SystemExit(result != 0)' 2>/dev/null; then
            open_firefox
            exit 0
        fi
        sleep 0.25
    done
) >/dev/null 2>&1 </dev/null &

echo "Nombro démarre. Firefox va s'ouvrir automatiquement."
echo "Garde cette fenêtre ouverte pendant l'utilisation ; Ctrl+C arrête Nombro."
exec .venv/bin/python app.py
