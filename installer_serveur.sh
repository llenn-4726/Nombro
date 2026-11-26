#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$APP_DIR/.venv/bin/python"
PORT="${FLASK_PORT:-5000}"
UNIT_DIR="$HOME/.config/systemd/user"
BACKUP_DIR="$APP_DIR/instance/backups"

cd "$APP_DIR"
for file in app.py nombro_backup.py requirements.txt; do
  if [[ ! -f "$APP_DIR/$file" ]]; then
    echo "Fichier manquant : $APP_DIR/$file" >&2
    exit 1
  fi
done

if [[ ! -x "$PYTHON" ]]; then
  echo "Création de l’environnement Python…"
  if ! python3 -m venv "$APP_DIR/.venv"; then
    echo "Python venv manque. Sur Ubuntu, installe-le avec : sudo apt install python3-venv" >&2
    exit 1
  fi
fi

echo "Installation des dépendances…"
"$PYTHON" -m pip install -r "$APP_DIR/requirements.txt"

DB="$APP_DIR/instance/plusvalue.sqlite3"
if [[ ! -f "$DB" ]]; then
  if [[ -f "$APP_DIR/nombro-backup.zip" ]]; then
    echo "Restauration initiale du catalogue…"
    "$PYTHON" "$APP_DIR/nombro_backup.py" restore "$APP_DIR/nombro-backup.zip"
  else
    echo "Base Nombro absente et nombro-backup.zip introuvable. Installation arrêtée pour éviter un catalogue vide." >&2
    exit 1
  fi
else
  echo "Base existante conservée : $DB"
fi

# Refuse to collide with a manually started Nombro process.
if "$PYTHON" -c 'import socket,sys; s=socket.socket(); s.settimeout(.3); r=s.connect_ex(("127.0.0.1",int(sys.argv[1]))); s.close(); raise SystemExit(0 if r == 0 else 1)' "$PORT"; then
  echo "Le port $PORT est déjà utilisé. Arrête l’ancien serveur (Ctrl+C), puis relance cet installateur." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR" "$UNIT_DIR"
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

# Make and verify an initial backup before enabling the schedule.
"$PYTHON" "$APP_DIR/nombro_backup.py" backup
systemctl --user daemon-reload
systemctl --user enable --now nombro-backup.timer
systemctl --user enable --now nombro-server.service

# Keep the user systemd manager alive across logout and start it at boot.
LINGER_STATE="$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || true)"
if [[ "$LINGER_STATE" != "yes" ]]; then
  echo "Activation du démarrage automatique dès l’allumage du PC (mot de passe administrateur demandé)…"
  if command -v sudo >/dev/null 2>&1; then
    sudo loginctl enable-linger "$USER"
  else
    echo "Impossible d’activer le démarrage avant connexion sans sudo. Lance : sudo loginctl enable-linger $USER" >&2
    exit 1
  fi
fi

echo
echo "Installation terminée. Nombro démarre automatiquement avec le PC, même avant l’ouverture de session."
echo "Sauvegarde quotidienne activée à 13 h (heure locale)."
echo "Sauvegardes : $BACKUP_DIR"
echo "Sur ce PC : http://localhost:$PORT"
LAN_IPS="$(hostname -I 2>/dev/null | xargs || true)"
if [[ -n "$LAN_IPS" ]]; then
  for IP in $LAN_IPS; do echo "Depuis un autre PC du même réseau : http://$IP:$PORT"; done
fi
echo "Vérifier le minuteur : systemctl --user list-timers nombro-backup.timer"
