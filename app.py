import os
import csv
import io
import math
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "dev-key-a-remplacer-en-production"),
    DATABASE=str(INSTANCE_DIR / "plusvalue.sqlite3"),
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            sale_price REAL NOT NULL,
            purchase_ttc REAL,
            sale_ttc REAL,
            vat_rate REAL NOT NULL DEFAULT 20,
            extra_cost_ttc REAL NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
    """)
    # Keep existing local accounts working when the profile fields are added.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "name" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "phone" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
    product_columns = {row["name"] for row in db.execute("PRAGMA table_info(products)")}
    for column, definition in (
        ("purchase_ttc", "REAL"),
        ("sale_ttc", "REAL"),
        ("vat_rate", "REAL NOT NULL DEFAULT 20"),
        ("extra_cost_ttc", "REAL NOT NULL DEFAULT 0"),
    ):
        if column not in product_columns:
            db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
    # Old prices were entered without VAT fields; retain their value as HT.
    db.execute("UPDATE products SET purchase_ttc = purchase_price * 1.2 WHERE purchase_ttc IS NULL")
    db.execute("UPDATE products SET sale_ttc = sale_price * 1.2 WHERE sale_ttc IS NULL")
    db.commit()


with app.app_context():
    init_db()


@app.before_request
def prepare_request():
    g.user = None
    if session.get("user_id"):
        g.user = get_db().execute("SELECT id, email, name, phone FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        if g.user is None:
            session.clear()
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)


@app.context_processor
def inject_globals():
    return {"csrf_token": session.get("csrf_token"), "current_user": g.get("user")}


@app.before_request
def protect_forms():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        submitted = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not submitted or not secrets.compare_digest(submitted, expected):
            abort(400, "Jeton de sécurité invalide. Rechargez la page puis réessayez.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_price(value):
    try:
        result = float(value.replace(",", ".").strip())
        if not math.isfinite(result) or result < 0 or result > 1_000_000_000:
            raise ValueError
        return round(result, 2)
    except (ValueError, AttributeError):
        return None


def parse_rate(value):
    try:
        result = float(value.replace(",", ".").strip())
        if not math.isfinite(result) or result < 0 or result > 100:
            raise ValueError
        return round(result, 2)
    except (ValueError, AttributeError):
        return None


@app.route("/")
def index():
    return redirect(url_for("dashboard" if g.user else "login"))


@app.route("/inscription", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or len(name) > 100:
            flash("Saisissez votre nom (100 caractères maximum).", "error")
        elif not email or "@" not in email or len(email) > 254:
            flash("Saisissez une adresse e-mail valide.", "error")
        elif len(phone) > 30 or (phone and not all(char.isdigit() or char in "+ ().-" for char in phone)):
            flash("Saisissez un numéro de téléphone valide.", "error")
        elif len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "error")
        else:
            try:
                db = get_db()
                cursor = db.execute("INSERT INTO users (email, name, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                                    (email, name, phone, generate_password_hash(password), datetime.utcnow().isoformat()))
                db.commit()
                session.clear()
                session["user_id"] = cursor.lastrowid
                session["csrf_token"] = secrets.token_urlsafe(32)
                flash("Votre compte est prêt. Vous pouvez créer votre première fiche produit.", "success")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("Un compte existe déjà avec cette adresse e-mail.", "error")
    return render_template("register.html")


@app.route("/profil", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        if not name or len(name) > 100:
            flash("Saisissez votre nom (100 caractères maximum).", "error")
        elif len(phone) > 30 or (phone and not all(char.isdigit() or char in "+ ().-" for char in phone)):
            flash("Saisissez un numéro de téléphone valide.", "error")
        else:
            db = get_db()
            db.execute("UPDATE users SET name = ?, phone = ? WHERE id = ?", (name, phone, g.user["id"]))
            db.commit()
            flash("Votre profil a été mis à jour.", "success")
            return redirect(url_for("dashboard"))
    return render_template("profile.html")


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("dashboard"))
        flash("E-mail ou mot de passe incorrect.", "error")
    return render_template("login.html")


@app.post("/deconnexion")
@login_required
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("login"))


def dashboard_data():
    products = get_db().execute("SELECT * FROM products WHERE user_id = ? ORDER BY id DESC", (g.user["id"],)).fetchall()
    total_profit = sum(((p["sale_ttc"] - p["purchase_ttc"] - p["extra_cost_ttc"]) / (1 + p["vat_rate"] / 100)) * p["quantity"] for p in products)
    profitable_count = sum(1 for p in products if p["sale_ttc"] > p["purchase_ttc"] + p["extra_cost_ttc"])
    average_margin = 0
    if products:
        margins = []
        for p in products:
            costs = p["purchase_ttc"] + p["extra_cost_ttc"]
            margins.append((p["sale_ttc"] - costs) / costs * 100 if costs else 0)
        average_margin = sum(margins) / len(margins)
    return {"products": products, "total_profit": total_profit,
            "profitable_count": profitable_count, "average_margin": average_margin}


@app.route("/tableau-de-bord")
@login_required
def dashboard():
    return render_template("dashboard.html", **dashboard_data())


@app.route("/grille")
@login_required
def spreadsheet():
    return render_template("grid.html", **dashboard_data())


@app.route("/api/produit/<int:product_id>/cellules", methods=["PATCH"])
@login_required
def update_product_cells(product_id):
    product = get_db().execute("SELECT id FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"])).fetchone()
    if product is None:
        return jsonify(error="Produit introuvable."), 404
    values = request.get_json(silent=True) or {}
    purchase_ht = parse_price(str(values.get("purchase_ht", "")))
    sale_ht = parse_price(str(values.get("sale_ht", "")))
    extra_ht = parse_price(str(values.get("extra_cost_ht", "0")))
    vat_rate = parse_rate(str(values.get("vat_rate", "")))
    try:
        quantity_value = float(values.get("quantity", 0))
        quantity = int(quantity_value)
        if not math.isfinite(quantity_value) or quantity_value != quantity or quantity < 1 or quantity > 1_000_000:
            raise ValueError
    except (TypeError, ValueError):
        quantity = None
    if None in (purchase_ht, sale_ht, extra_ht, vat_rate, quantity):
        return jsonify(error="Valeurs invalides : montants positifs, TVA entre 0 et 100 %, quantité de 1 à 1 000 000."), 400
    factor = 1 + vat_rate / 100
    db = get_db()
    db.execute("""UPDATE products SET purchase_price = ?, sale_price = ?, purchase_ttc = ?,
        sale_ttc = ?, vat_rate = ?, extra_cost_ttc = ?, quantity = ?
        WHERE id = ? AND user_id = ?""",
        (purchase_ht, sale_ht, round(purchase_ht * factor, 2), round(sale_ht * factor, 2),
         vat_rate, round(extra_ht * factor, 2), quantity, product_id, g.user["id"]))
    db.commit()
    return jsonify(saved=True)


@app.route("/produits/export.csv")
@login_required
def export_products():
    products = get_db().execute("SELECT * FROM products WHERE user_id = ? ORDER BY name COLLATE NOCASE", (g.user["id"],)).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Produit", "Achat TTC", "Achat HT", "Vente TTC", "Vente HT", "TVA %", "Frais TTC", "Bénéfice HT / unité", "Bénéfice HT total", "Marge %", "Quantité", "Notes"])
    for product in products:
        factor = 1 + product["vat_rate"] / 100
        purchase_ht = product["purchase_ttc"] / factor
        sale_ht = product["sale_ttc"] / factor
        costs_ht = (product["purchase_ttc"] + product["extra_cost_ttc"]) / factor
        profit_unit = sale_ht - costs_ht
        margin = profit_unit / costs_ht * 100 if costs_ht else 0
        writer.writerow([product["name"], product["purchase_ttc"], round(purchase_ht, 2), product["sale_ttc"], round(sale_ht, 2), product["vat_rate"], product["extra_cost_ttc"], round(profit_unit, 2), round(profit_unit * product["quantity"], 2), round(margin, 1), product["quantity"], product["notes"]])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=mimosa-produits.csv"})


@app.route("/produit/nouveau", methods=["GET", "POST"])
@login_required
def new_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        purchase = parse_price(request.form.get("purchase_ttc"))
        sale = parse_price(request.form.get("sale_ttc"))
        vat_rate = parse_rate(request.form.get("vat_rate", "20"))
        extra_costs = parse_price(request.form.get("extra_cost_ttc", "0"))
        try:
            quantity = int(request.form.get("quantity", "1"))
            if quantity < 1 or quantity > 1_000_000:
                raise ValueError
        except ValueError:
            quantity = None
        notes = request.form.get("notes", "").strip()[:2000]
        if not name or len(name) > 120:
            flash("Le nom du produit est obligatoire (120 caractères maximum).", "error")
        elif purchase is None or sale is None or extra_costs is None:
            flash("Les montants TTC doivent être des nombres positifs (ex. 12,50).", "error")
        elif vat_rate is None:
            flash("Le taux de TVA doit être compris entre 0 et 100 %.", "error")
        elif quantity is None:
            flash("La quantité doit être un entier supérieur à zéro.", "error")
        else:
            db = get_db()
            purchase_ht = round(purchase / (1 + vat_rate / 100), 2)
            sale_ht = round(sale / (1 + vat_rate / 100), 2)
            extra_costs_ht = round(extra_costs / (1 + vat_rate / 100), 2)
            db.execute("""INSERT INTO products
                (user_id, name, purchase_price, sale_price, purchase_ttc, sale_ttc, vat_rate, extra_cost_ttc, quantity, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g.user["id"], name, purchase_ht, sale_ht, purchase, sale, vat_rate, extra_costs, quantity, notes, datetime.utcnow().isoformat()))
            db.commit()
            flash("La ligne a été ajoutée à la grille.", "success")
            return redirect(url_for("spreadsheet"))
    return render_template("new_product.html")


@app.route("/produit/<int:product_id>/modifier", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"])).fetchone()
    if product is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        purchase = parse_price(request.form.get("purchase_ttc"))
        sale = parse_price(request.form.get("sale_ttc"))
        vat_rate = parse_rate(request.form.get("vat_rate", "20"))
        extra_costs = parse_price(request.form.get("extra_cost_ttc", "0"))
        try:
            quantity = int(request.form.get("quantity", "1"))
            if quantity < 1 or quantity > 1_000_000:
                raise ValueError
        except ValueError:
            quantity = None
        notes = request.form.get("notes", "").strip()[:2000]
        if not name or len(name) > 120:
            flash("Le nom du produit est obligatoire (120 caractères maximum).", "error")
        elif purchase is None or sale is None or extra_costs is None:
            flash("Les montants TTC doivent être des nombres positifs (ex. 12,50).", "error")
        elif vat_rate is None:
            flash("Le taux de TVA doit être compris entre 0 et 100 %.", "error")
        elif quantity is None:
            flash("La quantité doit être un entier supérieur à zéro.", "error")
        else:
            factor = 1 + vat_rate / 100
            db.execute("""UPDATE products SET name = ?, purchase_price = ?, sale_price = ?,
                purchase_ttc = ?, sale_ttc = ?, vat_rate = ?, extra_cost_ttc = ?, quantity = ?, notes = ?
                WHERE id = ? AND user_id = ?""",
                (name, round(purchase / factor, 2), round(sale / factor, 2), purchase, sale, vat_rate, extra_costs, quantity, notes, product_id, g.user["id"]))
            db.commit()
            flash("La ligne a été mise à jour.", "success")
            return redirect(url_for("spreadsheet"))
    return render_template("new_product.html", product=product)


@app.post("/produit/<int:product_id>/supprimer")
@login_required
def delete_product(product_id):
    db = get_db()
    cursor = db.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"]))
    db.commit()
    if cursor.rowcount:
        flash("La ligne a été supprimée.", "success")
    else:
        abort(404)
    return redirect(url_for("spreadsheet"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
