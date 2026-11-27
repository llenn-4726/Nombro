#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$APP_DIR/.venv/bin/python"
PORT="${FLASK_PORT:-5000}"
UNIT_DIR="$HOME/.config/systemd/user"

cd "$APP_DIR"
for file in app.py nombro_backup.py requirements.txt import_catalogue.py catalogue.json; do
  [[ -f "$APP_DIR/$file" ]] || { echo "Fichier manquant : $file" >&2; exit 1; }
done

# Stop the previous Nombro service before migrating its local database.
if command -v systemctl >/dev/null 2>&1; then
  systemctl --user stop nombro-server.service 2>/dev/null || true
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Création de l'environnement Python…"
  if ! python3 -m venv "$APP_DIR/.venv"; then
    echo "Python venv manque. Installe-le avec : sudo apt install python3-venv" >&2
    exit 1
  fi
fi

echo "Installation des dépendances…"
"$PYTHON" -m pip install -r "$APP_DIR/requirements.txt"

DB="$APP_DIR/instance/plusvalue.sqlite3"
if [[ ! -f "$DB" ]]; then
  echo "Initialisation d'une base neuve…"
  (cd "$APP_DIR" && "$PYTHON" -c 'import app')
else
  echo "Base de cette installation conservée : $DB"
fi

mkdir -p "$APP_DIR/instance/backups" "$UNIT_DIR"
cat > "$UNIT_DIR/nombro-server.service" <<UNIT
[Unit]
Description=Nombro server on the local network
After=network.target
[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=FLASK_HOST=0.0.0.0
Environment=FLASK_PORT=$PORT
ExecStart="$PYTHON" "$APP_DIR/app.py"
Restart=on-failure
RestartSec=3
[Install]
WantedBy=default.target
UNIT
cat > "$UNIT_DIR/nombro-backup.service" <<UNIT
[Unit]
Description=Create and verify a Nombro backup
[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart="$PYTHON" "$APP_DIR/nombro_backup.py" backup
UNIT
cat > "$UNIT_DIR/nombro-backup.timer" <<'UNIT'
[Unit]
Description=Daily Nombro backup at 13:00
[Timer]
OnCalendar=*-*-* 13:00:00
Persistent=true
Unit=nombro-backup.service
[Install]
WantedBy=timers.target
UNIT

"$PYTHON" "$APP_DIR/nombro_backup.py" backup
systemctl --user daemon-reload
systemctl --user enable --now nombro-backup.timer
systemctl --user enable --now nombro-server.service
LINGER_STATE="$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || true)"
if [[ "$LINGER_STATE" != yes ]] && command -v sudo >/dev/null 2>&1; then
  sudo loginctl enable-linger "$USER"
fi
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Nombro installé et démarré."
echo "Sur ce PC : http://localhost:$PORT"
[[ -z "$IP" ]] || echo "Depuis un autre PC du réseau : http://$IP:$PORT"
echo "Sauvegarde automatique chaque jour à 13 h."
echo "Après création du compte web, importer le catalogue avec :"
echo "  $PYTHON $APP_DIR/import_catalogue.py --list-users"
echo "  $PYTHON $APP_DIR/import_catalogue.py --email 'adresse-du-compte'"
