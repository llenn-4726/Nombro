#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$APP_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

CONFIG="$APP_DIR/backup.env"
mkdir -p "$APP_DIR/instance" "$HOME/.config/systemd/user"
if [[ ! -f "$CONFIG" ]]; then
  read -r -p "Dossier de sauvegarde (partage réseau conseillé, vide = instance/backups) : " BACKUP_DIR
  REQUIRE_MOUNT=0
  if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="$APP_DIR/instance/backups"
  else
    read -r -p "Ce dossier dépend-il d'un disque/partage monté ? [o/N] : " MOUNT_ANSWER
    if [[ "$MOUNT_ANSWER" =~ ^[oOyY]$ ]]; then REQUIRE_MOUNT=1; fi
  fi
  mkdir -p "$BACKUP_DIR"
  printf 'NOMBRO_BACKUP_DIR="%s"\nNOMBRO_BACKUP_REQUIRE_MOUNT=%s\n' "$BACKUP_DIR" "$REQUIRE_MOUNT" > "$CONFIG"
  chmod 644 "$CONFIG"
fi

cat > "$HOME/.config/systemd/user/nombro-backup.service" <<UNIT
[Unit]
Description=Create and verify a Nombro backup

[Service]
Type=oneshot
WorkingDirectory="$APP_DIR"
EnvironmentFile=-"$CONFIG"
ExecStart="$PYTHON" "$APP_DIR/nombro_backup.py" backup
UNIT

cat > "$HOME/.config/systemd/user/nombro-backup.timer" <<'UNIT'
[Unit]
Description=Daily Nombro backup at 13:00

[Timer]
OnCalendar=*-*-* 13:00:00
Persistent=true
Unit=nombro-backup.service

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now nombro-backup.timer
echo "Sauvegarde Nombro programmée chaque jour à 13 h (heure locale)."
echo "Configuration : $CONFIG"
echo "Vérification : systemctl --user list-timers nombro-backup.timer"
