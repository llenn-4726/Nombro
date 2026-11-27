#!/usr/bin/env python3
"""Import the prepared Nombro catalog into one account on this server."""
import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "instance" / "plusvalue.sqlite3"
IMAGE_DIR = ROOT / "instance" / "product-images"
BACKUP_DIR = ROOT / "instance" / "backups"
DATA_PATH = ROOT / "catalogue.json"


def main():
    parser = argparse.ArgumentParser(description="Importe les 18 fiches du catalogue Nombro.")
    parser.add_argument("--list-users", action="store_true", help="afficher les comptes présents et le nombre de fiches")
    parser.add_argument("--email", help="adresse du compte Nombro à alimenter")
    args = parser.parse_args()
    if not DB_PATH.is_file():
        raise SystemExit(f"Base Nombro introuvable : {DB_PATH}\nPlace ce dossier dans le dossier Nombro du serveur.")
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    users = db.execute("SELECT id, email FROM users ORDER BY email").fetchall()
    if args.list_users:
        for user in users:
            count = db.execute("SELECT COUNT(*) FROM products WHERE user_id = ?", (user["id"],)).fetchone()[0]
            print(f'{user["email"]} : {count} produit(s)')
        db.close()
        return
    if not args.email:
        db.close()
        raise SystemExit("Indique d’abord le compte cible : --list-users, puis --email adresse@exemple.fr")
    match = next((u for u in users if u["email"].casefold() == args.email.strip().casefold()), None)
    if match is None:
        db.close()
        raise SystemExit("Ce compte n’existe pas dans la base active du serveur. Aucun changement effectué.")
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    products = payload["products"]
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"avant-import-catalogue-{stamp}.sqlite3"
    backup = sqlite3.connect(backup_path)
    db.backup(backup)
    backup.close()
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    try:
        db.execute("BEGIN IMMEDIATE")
        for item in products:
            name = item["name"].strip()
            ref = item.get("supplier_ref", "").strip()
            existing = db.execute(
                "SELECT id FROM products WHERE user_id = ? AND (lower(name) = lower(?) OR (? <> '' AND lower(supplier_ref) = lower(?))) LIMIT 1",
                (match["id"], name, ref, ref),
            ).fetchone()
            if existing:
                skipped += 1
                continue
            photo_name = ""
            relative_photo = item.get("photo", "")
            if relative_photo:
                source = (ROOT / relative_photo).resolve()
                if ROOT not in source.parents or not source.is_file():
                    raise RuntimeError(f"Photo absente ou chemin invalide : {relative_photo}")
                photo_name = source.name
                shutil.copy2(source, IMAGE_DIR / photo_name)
            vat = float(payload.get("vat_rate", 20))
            factor = 1 + vat / 100
            purchase_ht = float(item["purchase_ht"])
            sale_ht = float(item["sale_ht"])
            service_ht = float(item.get("service_ht", 0))
            competitors = []
            for comp in item.get("competitors", []):
                notes = comp.get("source", "")
                if "photo fournie" in notes:
                    notes = "Prix HT recopié du tableau fourni; non revalidé en ligne."
                else:
                    notes = "Prix HT affiché sur la fiche consultée le 26/11/2026; tarif susceptible d’évoluer. " + notes
                competitors.append({
                    "brand": comp["brand"],
                    "price": round(float(comp["ht"]) * factor, 2),
                    "url": comp.get("url", ""),
                    "notes": notes[:300],
                })
            cursor = db.execute("""INSERT INTO products
                (user_id, name, product_code, manufacturer, supplier_ref, barcode, supplier,
                 purchase_price, sale_price, purchase_ttc, sale_ttc, vat_rate, extra_cost_ttc,
                 quantity, notes, photo_path, service_description, service_cost_ttc,
                 competitors_json, created_at)
                VALUES (?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?, ?, ?)""",
                (match["id"], name, item.get("product_code", ""), item.get("manufacturer", ""), ref,
                 round(purchase_ht, 2), round(sale_ht + service_ht, 2), round(purchase_ht * factor, 2),
                 round((sale_ht + service_ht) * factor, 2), vat, item.get("notes", ""), photo_name,
                 f"Prestation (HT, source photo) : {service_ht:.2f} €" if service_ht else "",
                 round(service_ht * factor, 2), json.dumps(competitors, ensure_ascii=False), datetime.now().astimezone().isoformat()))
            product_id = cursor.lastrowid
            for competitor in competitors:
                db.execute("INSERT OR IGNORE INTO competitor_brands (user_id, name, created_at) VALUES (?, ?, ?)",
                           (match["id"], competitor["brand"], datetime.now().astimezone().isoformat()))
            added += 1
        db.commit()
    except Exception:
        db.rollback()
        db.close()
        raise
    db.close()
    print(f"Import terminé pour {match['email']} : {added} ajouté(s), {skipped} déjà présent(s).")
    print(f"Sauvegarde préalable : {backup_path}")
    print(f"Photos installées dans : {IMAGE_DIR}")

if __name__ == "__main__":
    main()
