#!/usr/bin/env python3
"""Create and restore verified Nombro backups (SQLite, photos, and session key)."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

APP_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = APP_DIR / "instance"
DATABASE = INSTANCE_DIR / "plusvalue.sqlite3"
PHOTOS = INSTANCE_DIR / "product-images"
SECRET = INSTANCE_DIR / "secret_key"
ARCHIVE_PREFIX = "nombro-backup-"
RETENTION_DAYS = 30


def load_backup_dir():
    configured = os.environ.get("NOMBRO_BACKUP_DIR")
    config_files = (APP_DIR / "backup.env", INSTANCE_DIR / "backup.env")
    if not configured:
        for config_file in config_files:
            if not config_file.exists():
                continue
            for line in config_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("NOMBRO_BACKUP_DIR="):
                    configured = line.split("=", 1)[1].strip().strip("\"'")
                    break
            if configured:
                break
    if not configured:
        return INSTANCE_DIR / "backups"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else APP_DIR / path


def backup_location_configured():
    if os.environ.get("NOMBRO_BACKUP_DIR"):
        return True
    return (APP_DIR / "backup.env").is_file() or (INSTANCE_DIR / "backup.env").is_file()


def require_backup_mount():
    configured = os.environ.get("NOMBRO_BACKUP_REQUIRE_MOUNT")
    if configured is None:
        config_file = APP_DIR / "backup.env"
        if config_file.exists():
            for line in config_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("NOMBRO_BACKUP_REQUIRE_MOUNT="):
                    configured = line.split("=", 1)[1].strip().strip("\"'")
                    break
    return (configured or "0").strip().lower() in {"1", "true", "yes"}


def ensure_backup_mount(directory):
    if not require_backup_mount():
        return
    current = Path(directory).expanduser().resolve()
    while current != current.parent:
        if os.path.ismount(current):
            return
        current = current.parent
    raise RuntimeError(f"Le partage/disque de sauvegarde n’est pas monté : {directory}")


def check_sqlite(path):
    if not path.is_file():
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                return False
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return {"users", "products"}.issubset(tables)
    except sqlite3.DatabaseError:
        return False


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_files(archive):
    with zipfile.ZipFile(archive, "r") as zipped:
        names = set(zipped.namelist())
        if "manifest.json" not in names or "database.sqlite3" not in names:
            raise ValueError("Archive incomplet")
        manifest = json.loads(zipped.read("manifest.json"))
        if manifest.get("format") != 1:
            raise ValueError("Format de sauvegarde non pris en charge")
        with tempfile.TemporaryDirectory(prefix="nombro-verify-") as temp:
            db_path = Path(temp) / "database.sqlite3"
            db_path.write_bytes(zipped.read("database.sqlite3"))
            if not check_sqlite(db_path):
                raise ValueError("Base SQLite invalide dans l’archive")
            for filename, expected in manifest.get("sha256", {}).items():
                if filename not in names or hashlib.sha256(zipped.read(filename)).hexdigest() != expected:
                    raise ValueError(f"Fichier endommagé dans l’archive : {filename}")
        return manifest


def list_backups(directory=None):
    directory = directory or load_backup_dir()
    if directory.exists():
        candidates = sorted(directory.rglob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
        for archive in candidates:
            try:
                backup_files(archive)
                return [archive]
            except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError):
                continue
    return []


def create_backup(output_dir=None):
    if not check_sqlite(DATABASE):
        raise RuntimeError(f"La base Nombro est absente ou invalide : {DATABASE}")
    output_dir = output_dir or load_backup_dir()
    ensure_backup_mount(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    year_dir = output_dir / f"{ARCHIVE_PREFIX}{now:%Y}"
    month_dir = year_dir / f"{now:%m}"
    month_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%d-%H%M%S")
    final_path = month_dir / f"{stamp}.zip"
    with tempfile.TemporaryDirectory(prefix="nombro-backup-") as temp:
        temp_dir = Path(temp)
        db_copy = temp_dir / "database.sqlite3"
        with sqlite3.connect(DATABASE, timeout=30) as source, sqlite3.connect(db_copy) as target:
            source.backup(target)
        if not check_sqlite(db_copy):
            raise RuntimeError("La vérification de la copie SQLite a échoué")
        files = [db_copy]
        if SECRET.is_file():
            shutil.copy2(SECRET, temp_dir / "secret_key")
            files.append(temp_dir / "secret_key")
        if PHOTOS.is_dir():
            photo_root = temp_dir / "product-images"
            shutil.copytree(PHOTOS, photo_root)
            files.extend(path for path in photo_root.rglob("*") if path.is_file())
        hashes = {}
        for path in files:
            relative = "database.sqlite3" if path == db_copy else path.relative_to(temp_dir).as_posix()
            hashes[relative] = sha256_file(path)
        manifest = {
            "format": 1,
            "application": "Nombro",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sha256": hashes,
        }
        temporary_archive = output_dir / f".{final_path.name}.{os.getpid()}.tmp"
        try:
            with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                zipped.write(db_copy, "database.sqlite3")
                if (temp_dir / "secret_key").exists():
                    zipped.write(temp_dir / "secret_key", "secret_key")
                if (temp_dir / "product-images").exists():
                    for path in (temp_dir / "product-images").rglob("*"):
                        if path.is_file():
                            zipped.write(path, path.relative_to(temp_dir).as_posix())
                zipped.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            backup_files(temporary_archive)
            os.chmod(temporary_archive, 0o600)
            os.replace(temporary_archive, final_path)
        finally:
            temporary_archive.unlink(missing_ok=True)
    prune_backups(output_dir)
    return final_path


def prune_backups(directory=None):
    directory = directory or load_backup_dir()
    cutoff = datetime.now().astimezone() - timedelta(days=RETENTION_DAYS)
    for archive in directory.rglob("*.zip"):
        try:
            if datetime.fromtimestamp(archive.stat().st_mtime).astimezone() < cutoff:
                archive.unlink()
        except OSError:
            continue


def restore_backup(archive, instance_dir=None):
    archive = Path(archive)
    instance_dir = instance_dir or INSTANCE_DIR
    manifest = backup_files(archive)
    instance_dir.mkdir(parents=True, exist_ok=True)
    recovery_dir = instance_dir / "recovery"
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    db_target = instance_dir / "plusvalue.sqlite3"
    if db_target.exists():
        recovery_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_target, recovery_dir / f"database-before-restore-{stamp}.sqlite3")
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{db_target}{suffix}")
        if sidecar.exists():
            recovery_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(sidecar, recovery_dir / f"{sidecar.name}-before-restore-{stamp}")
    with tempfile.TemporaryDirectory(prefix="nombro-restore-") as temp:
        temp_dir = Path(temp)
        with zipfile.ZipFile(archive, "r") as zipped:
            for name in zipped.namelist():
                posix = PurePosixPath(name)
                if posix.is_absolute() or ".." in posix.parts:
                    raise ValueError("Chemin interdit dans l’archive")
                if name == "manifest.json":
                    continue
                destination = temp_dir.joinpath(*posix.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(zipped.read(name))
        restored_db = temp_dir / "database.sqlite3"
        if not check_sqlite(restored_db):
            raise ValueError("La base de l’archive est invalide")
        # The extraction directory may live on a different filesystem (for
        # example /tmp vs. a home directory on another partition). Stage the
        # restored database beside its destination so os.replace stays on one
        # filesystem and remains atomic.
        staged_db = instance_dir / f".{db_target.name}.restore-{stamp}.tmp"
        try:
            shutil.copy2(restored_db, staged_db)
            os.replace(staged_db, db_target)
        finally:
            staged_db.unlink(missing_ok=True)
        restored_secret = temp_dir / "secret_key"
        if restored_secret.exists():
            shutil.copy2(restored_secret, instance_dir / "secret_key")
            os.chmod(instance_dir / "secret_key", 0o600)
        restored_photos = temp_dir / "product-images"
        if restored_photos.exists():
            photo_target = instance_dir / "product-images"
            if photo_target.exists():
                recovery_dir.mkdir(parents=True, exist_ok=True)
                previous_photos = recovery_dir / f"product-images-before-restore-{stamp}"
                shutil.move(photo_target, previous_photos)
            shutil.move(restored_photos, photo_target)
    return manifest


def recover_if_needed(instance_dir=None, backup_dir=None):
    instance_dir = instance_dir or INSTANCE_DIR
    database = instance_dir / "plusvalue.sqlite3"
    backups = list_backups(backup_dir)
    if not backups:
        if (database.exists() or backup_location_configured()) and not check_sqlite(database):
            raise RuntimeError("Base Nombro absente/corrompue et aucune sauvegarde vérifiée accessible. Démarrage interrompu pour éviter de recréer un catalogue vide.")
        return None
    if check_sqlite(database):
        # Repair missing photo files without replacing a healthy current database.
        with sqlite3.connect(database) as db:
            referenced = {row[0] for row in db.execute("SELECT photo_path FROM products WHERE photo_path != ''")}
        photo_dir = instance_dir / "product-images"
        missing = {Path(name).name for name in referenced if not (photo_dir / Path(name).name).is_file()}
        if missing:
            with zipfile.ZipFile(backups[0], "r") as zipped:
                available = set(zipped.namelist())
                photo_dir.mkdir(parents=True, exist_ok=True)
                for filename in missing:
                    archive_name = f"product-images/{filename}"
                    if archive_name in available:
                        (photo_dir / filename).write_bytes(zipped.read(archive_name))
            return "restored"
        return None
    if database.exists():
        recovery_dir = instance_dir / "recovery"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        damaged = recovery_dir / f"database-damaged-{datetime.now().astimezone():%Y%m%d-%H%M%S}.sqlite3"
        shutil.move(database, damaged)
    restore_backup(backups[0], instance_dir)
    return "restored"


def main():
    parser = argparse.ArgumentParser(description="Sauvegardes vérifiées de Nombro")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup", help="Crée et vérifie une archive complète")
    restore = commands.add_parser("restore", help="Restaure une archive choisie")
    restore.add_argument("archive", type=Path)
    commands.add_parser("recover", help="Restaure automatiquement si la base est absente ou corrompue")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            print(f"Sauvegarde vérifiée : {create_backup()}")
        elif args.command == "restore":
            manifest = restore_backup(args.archive)
            print(f"Restauration terminée (copie du {manifest.get('created_at', 'date inconnue')}).")
        else:
            result = recover_if_needed()
            print("Restauration automatique terminée." if result else "Aucune réparation nécessaire.")
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(f"Erreur sauvegarde/restauration : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
