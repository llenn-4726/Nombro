import errno
import hashlib
import hmac
import os
import csv
import io
import json
import math
import secrets
import sqlite3
import time
import zipfile
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from flask import Flask, Response, abort, flash as flask_flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from nombro_backup import recover_if_needed


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
PRODUCT_IMAGE_DIR = INSTANCE_DIR / "product-images"
def load_secret_key():
    configured_key = os.environ.get("FLASK_SECRET_KEY")
    if configured_key:
        return configured_key
    key_path = INSTANCE_DIR / "secret_key"
    try:
        return key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        secret = secrets.token_hex(32)
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return key_path.read_text(encoding="utf-8").strip()
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret)
        return secret

app = Flask(__name__, instance_path=str(INSTANCE_DIR))
app.config.update(
    SECRET_KEY=load_secret_key(),
    DATABASE=str(INSTANCE_DIR / "plusvalue.sqlite3"),
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_REFRESH_EACH_REQUEST=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    HOST=os.environ.get("FLASK_HOST", "127.0.0.1"),
    PORT=int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5000"))),
    SESSION_COOKIE_SECURE=False,
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)


class RequestAwareSessionInterface(SecureCookieSessionInterface):
    def get_cookie_secure(self, application):
        return request.is_secure or super().get_cookie_secure(application)


app.session_interface = RequestAwareSessionInterface()
CURRENCIES = {"EUR": "€", "USD": "$", "GBP": "£", "RUB": "₽", "JPY": "¥", "CHF": "CHF", "CAD": "CA$"}
THEMES = {"light": "Clair", "green-dark": "Green Dark", "black-dark": "Dark noir et blanc", "colorful": "Coloré", "cyberpunk": "Cyberpunk"}
LANGUAGES = {"fr": "Français", "en": "English"}
TRANSLATIONS = {
    "Accueil": "Home", "Récapitulatif": "Dashboard", "Grille tableur": "Price grid",
    "Paramètres": "Settings", "Déconnexion": "Log out", "Connexion": "Log in",
    "Un regard clair sur la rentabilité de vos produits": "A clear view of your product profitability",
    "VOTRE ESPACE NOMBRO": "YOUR NOMBRO WORKSPACE", "Profil, apparence, sécurité et sauvegarde de tes données.": "Profile, appearance, security and data backup.",
    "VOTRE PROFIL": "YOUR PROFILE", "Informations personnelles": "Personal information",
    "L’adresse e-mail ne peut pas être modifiée ici.": "Your email address cannot be changed here.",
    "Nom complet": "Full name", "Numéro de téléphone": "Phone number", "Facultatif": "Optional",
    "Devise des prix": "Price currency", "Unité d’affichage, sans conversion.": "Display unit only; amounts are not converted.",
    "Apparence": "Appearance", "Clair": "Light", "Sombre": "Green Dark", "Green Dark": "Green Dark",
    "Dark noir et blanc": "Pure dark", "Coloré": "Colorful",
    "Cyberpunk": "Cyberpunk",
    "Application immédiate.": "Applied immediately.", "Adresse e-mail": "Email address",
    "Enregistrer mon profil": "Save my profile", "SÉCURITÉ": "SECURITY",
    "Choisis un nouveau mot de passe d’au moins 8 caractères.": "Choose a new password with at least 8 characters.",
    "Mot de passe actuel": "Current password", "Nouveau mot de passe": "New password",
    "Confirmer le nouveau mot de passe": "Confirm new password", "Changer le mot de passe": "Update password",
    "Trop de tentatives de connexion. Réessaie dans 15 minutes.": "Too many login attempts. Try again in 15 minutes.",
    "Marge minimum souhaitée (%)": "Minimum target margin (%)",
    "Utilisée par le filtre « Sous le seuil » de la grille.": "Used by the grid’s “Below target” filter.",
    "Sous le seuil": "Below target", "Marge min. %": "Min. margin %", "Marge max. %": "Max. margin %",
    "Restaurer une sauvegarde": "Restore a backup", "Fichier de sauvegarde JSON": "JSON backup file",
    "Mode de restauration": "Restore mode", "Fusionner avec le catalogue": "Merge with catalog", "Remplacer le catalogue actuel": "Replace current catalog",
    "Je confirme le remplacement de tous mes produits actuels.": "I confirm replacing all my current products.",
    "Confirme le remplacement du catalogue avant de continuer.": "Confirm replacing the catalog before continuing.",
    "Sélectionne un fichier de sauvegarde JSON Nombro.": "Choose a Nombro JSON backup file.", "La sauvegarde dépasse la limite de 2 Mo.": "The backup exceeds the 2 MB limit.",
    "Ce fichier n’est pas une sauvegarde Nombro prise en charge.": "This is not a supported Nombro backup.", "La sauvegarde ne contient aucun produit.": "The backup contains no products.",
    "La restauration a échoué. Le catalogue n’a pas été modifié.": "Restore failed. The catalog was not changed.",
    "Restaurer la sauvegarde": "Restore backup", "La sauvegarde a été restaurée.": "Backup restored.",
    "Parcourir": "Browse", "Aucun fichier sélectionné.": "No file selected.",
    " lignes ajoutées, ": " rows added, ", " doublon(s) ignoré(s).": " duplicate(s) skipped.",
    "Historique des prix": "Price history", "Journal des modifications": "Change log", "Historique": "History", "Ancien achat TTC": "Previous purchase incl. tax",
    "Nouvel achat TTC": "New purchase incl. tax", "Ancienne vente TTC": "Previous sale incl. tax", "Nouvelle vente TTC": "New sale incl. tax",
    "Aucune modification de prix enregistrée.": "No price changes recorded.", "Retour à la grille": "Back to grid",
    "Aucune modification enregistrée.": "No changes recorded.", "Les prochains changements apparaîtront ici.": "Future changes will appear here.",
    "Modifié par": "Changed by", "Champ": "Field", "Avant": "Before", "Après": "After",
    "Nom du produit": "Product name", "Code produit": "Product code", "Fabricant": "Manufacturer",
    "Réf. fournisseur": "Supplier reference", "Code-barres": "Barcode",
    "Fournisseur": "Supplier", "Prix d’achat TTC": "Purchase price incl. tax", "Prix de vente TTC": "Sale price incl. tax",
    "Frais annexes TTC": "Extra costs incl. tax", "Prestation incluse TTC": "Included service incl. tax",
    "Quantité": "Quantity", "Notes": "Notes", "Photo": "Photo", "Concurrence": "Competitors",
    "Présente": "Present", "Absente": "Absent",
    "Ajouter plusieurs concurrents en une fois": "Add several competitors at once",
    "Enseigne ; prix TTC ; lien facultatif ; note facultative": "Retailer; price incl. tax; optional link; optional note",
    "Ajouter les lignes": "Add entries", "concurrent(s) ajouté(s).": "competitor(s) added.",
    "La limite de 20 concurrents par produit est atteinte.": "The 20-competitor limit per product has been reached.",
    "Certaines lignes ont été ignorées (format invalide ou limite atteinte).": "Some rows were skipped (invalid format or limit reached).",
    "SUIVI DES MODIFICATIONS": "CHANGE HISTORY", "TVA": "VAT",
    "Les changements effectués à partir de maintenant apparaîtront ici.": "Changes made from now on will appear here.",
    "Ajoute plusieurs enseignes au même produit, jusqu’à 20 au total.": "Add multiple retailers to the same product, up to 20 in total.",
    "Exporter en PDF": "Export PDF", "Date": "Date", "Achat TTC": "Purchase incl. tax", "Vente TTC": "Sale incl. tax",
    "VOS DONNÉES": "YOUR DATA", "Sauvegarde": "Backup",
    "Télécharge tes produits, prix, quantités et notes. Garde le fichier dans un endroit sûr.": "Download your products, prices, quantities and notes. Keep the file somewhere safe.",
    "Télécharger la sauvegarde": "Download backup", "Bonjour, ": "Hello, ",
    "Voici le résumé de tes produits et de leur rentabilité.": "Here is an overview of your products and profitability.",
    "Ouvrir la grille": "Open price grid", "PRODUITS": "PRODUCTS", "dans ton catalogue": "in your catalog",
    "MARGE TOTALE POTENTIELLE": "POTENTIAL TOTAL MARGIN", "selon les quantités enregistrées": "based on saved quantities",
    "PRODUITS RENTABLES": "PROFITABLE PRODUCTS", "marge moyenne ": "average margin ",
    "VUE D’ENSEMBLE": "OVERVIEW", "Ton catalogue": "Your catalog", "Exporter CSV": "Export CSV",
    "Rentable": "Profitable", "À perte": "At a loss", "À l’équilibre": "Break-even",
    "ACHAT TTC": "PURCHASE INCL. TAX", "VENTE TTC": "SALE INCL. TAX", "QTÉ": "QTY",
    "Marge valeur totale": "Total margin value", "Voir dans la grille": "View in grid", "Fiche produit": "Product details",
    "Ton catalogue est prêt à commencer": "Your catalog is ready to get started",
    "Ajoute une première ligne, puis suis les prix et les marges dans la grille.": "Add your first product, then track prices and margins in the grid.",
    "Aller à la grille": "Go to the grid", "PILOTEZ VOTRE RENTABILITÉ": "MANAGE YOUR PROFITABILITY",
    "Chaque produit": "Every product", "raconte une ": "has a ", "marge.": "margin.",
    "Retrouvez vos coûts, vos prix de vente et votre bénéfice en un seul endroit.": "Keep costs, sale prices and profit in one place.",
    "Une vision simple.": "A clear overview.", "Des décisions plus justes.": "Better informed decisions.",
    "BON RETOUR": "WELCOME BACK", "Se connecter": "Log in", "Créer un compte": "Create an account",
    "Pas encore de compte ?": "Don't have an account yet?", "Votre session restera active jusqu’à 30 jours sur cet appareil.": "Your session will stay active for up to 30 days on this device.",
    "Ma grille de prix": "My price grid",
    "Modifie une cellule HT ou la TVA : TTC, marge et coefficient se recalculent automatiquement.": "Edit an ex-tax price or VAT: tax-inclusive prices, margin and coefficient recalculate automatically.",
    "Ajouter une ligne": "Add product", "LIGNES PRODUIT": "PRODUCT ROWS",
    "MARGE TOTALE ESTIMÉE": "ESTIMATED TOTAL MARGIN", "calculé sur les quantités indiquées": "based on listed quantities",
    "LIGNES RENTABLES": "PROFITABLE ROWS", "marge moyenne": "average margin", "GRILLE MODIFIABLE": "EDITABLE GRID",
    "Prix & rentabilité": "Prices & profitability", "Import CSV": "Import CSV", "Import CSV / Excel": "Import CSV / Excel", "Export CSV": "Export CSV", "Exporter Excel": "Export Excel",
    "Rechercher une ligne…": "Search products…", "Trier": "Sort", "Ordre récent": "Newest first",
    "Nom A → Z": "Name A → Z", "Marge totale ↓": "Total margin ↓", "Taux de marge (%) ↓": "Margin rate (%) ↓",
    "État": "Status", "Tous": "All", "Rentables": "Profitable",
    "Fournisseur": "Supplier", "Devise": "Currency", "Modifications enregistrées automatiquement": "Changes saved automatically",
    "Aucune ligne ne correspond au filtre.": "No rows match these filters.",
    "Ta grille est vide pour le moment": "Your grid is empty for now", "Ajouter la première ligne": "Add the first product",
    "Annuler": "Cancel", "Nom du produit": "Product name", "Code produit": "Product code", "Code-barres": "Barcode",
    "Prix d’achat TTC": "Purchase price incl. tax", "Prix de vente TTC": "Sale price incl. tax", "TVA applicable": "VAT rate",
    "Frais annexes TTC": "Additional costs incl. tax", "Quantité": "Quantity", "Notes": "Notes",
    "APERÇU EN DIRECT": "LIVE PREVIEW", "Vente HT": "Sale excl. tax", "Prix achat HT": "Purchase excl. tax",
    "Marge valeur estimée": "Estimated margin value", "Marge en %": "Margin %", "Coefficient": "Coefficient",
    "NOUVELLE LIGNE": "NEW PRODUCT", "Informations du produit": "Product information", "Informations du nouveau produit": "New product information", "Enregistrer les changements": "Save changes",
    "FICHE PRODUIT": "PRODUCT DETAILS", "Retour à la grille": "Back to the grid", "Marge totale": "Total margin",
    "Aucune note enregistrée.": "No notes saved.", "Ouvrir le site": "Open website",
    "Ajouter à la grille": "Add to grid", "Importer des produits": "Import products", "IMPORT DE PRODUITS": "PRODUCT IMPORT",
    "Choisir un autre fichier": "Choose another file", "Choisir le fichier": "Choose file", "Choisir un fichier": "Choose a file", "Analyser le fichier": "Review file",
    "Fichier CSV": "CSV file", "Fichier CSV ou Excel": "CSV or Excel file", "Produit": "Product", "Achat TTC": "Purchase incl. tax", "Vente TTC": "Sale incl. tax",
    "Importer un fichier": "Import a file", "Importe un CSV Nombro ou un fichier Excel .xlsx. Les lignes sont vérifiées avant ajout au catalogue.": "Import a Nombro CSV or an .xlsx Excel file. Rows are checked before being added to your catalog.",
    "CSV : export Nombro. Excel : colonnes Produit et prix d’achat/vente TTC ou HT. TVA et quantité facultatives. Taille maximale : 5 Mo.": "CSV: Nombro export. Excel: Product and purchase/sale prices (incl. or excl. tax). VAT and quantity are optional. 5 MB maximum.",
    "Photo du produit": "Product photo", "Facultatif · JPG, PNG ou WebP, 5 Mo maximum": "Optional · JPG, PNG or WebP, 5 MB maximum",
    "Photo actuelle du produit": "Current product photo", "Supprimer la photo actuelle": "Remove current photo", "Photo de": "Photo of",
    "Aperçu de la photo sélectionnée": "Preview of the selected photo",
    "Choisir ou déposer une photo": "Choose or drop a photo", "Aucun fichier sélectionné": "No file selected",
    "Photo actuelle": "Current photo", "Nouvelle photo": "New photo",
    "CSV ou Excel.": "CSV or Excel.", "Choisis une suggestion ou saisis un nouveau fournisseur.": "Choose a suggestion or type a new supplier.",
    "Afficher les fournisseurs": "Show suppliers", "Aucun fournisseur enregistré": "No suppliers saved yet",
    "Ajouter le fournisseur": "Add supplier",
    "ANALYSE DU MARCHÉ": "MARKET ANALYSIS", "Concurrence": "Competitors", "Enseigne": "Retailer",
    "Prix concurrent TTC": "Competitor price incl. tax", "Lien du concurrent": "Competitor link", "Note": "Note",
    "Ajouter cette enseigne": "Add this retailer", "Aucune enseigne enregistrée": "No retailers saved yet",
    "Supprimer cette enseigne des suggestions": "Remove this retailer from suggestions",
    "Enseigne supprimée des suggestions.": "Retailer removed from suggestions.",
    "Impossible de supprimer l’enseigne. Réessaie.": "Could not remove this retailer. Try again.",
    "Nom d’enseigne invalide.": "Invalid retailer name.",
    "Écart avec ton prix": "Difference from your price", "Retirer cette enseigne": "Remove this retailer",
    "Aucun concurrent ajouté pour le moment.": "No competitors added yet.", "Compare les prix des enseignes et garde leurs liens et remarques.": "Compare retailer prices and keep their links and notes.",
    "Ajouter une enseigne": "Add a retailer", "Prestation de service": "Service offering",
    "PRESTATION DE SERVICE": "SERVICE OFFERING", "CONCURRENCE": "COMPETITION",
    "Aucune prestation": "No service listed", "Aucun concurrent": "No competitors listed",
    "Prestation incluse dans le produit": "Service included with the product",
    "Ex. Installation de Windows incluse": "E.g. Windows installation included",
    "Les prix d’achat et de vente comprennent le produit et cette prestation.": "Purchase and sale prices include both the product and this service.",
    "PRESTATION INCLUSE": "INCLUDED SERVICE", "Inclus dans le produit": "Included with the product",
    "Prestation incluse TTC": "Included service incl. tax", "Prestation incluse": "Included service",
    "Ce montant est déjà compris dans le prix d’achat TTC.": "This amount is already included in the purchase price incl. tax.",
    "Le montant de la prestation doit être positif ou nul.": "The service amount must be a non-negative number.",
    "Ex. Installation, livraison, garantie étendue…": "E.g. installation, delivery, extended warranty…",
    "Prix concurrents": "Competitor prices", "Ouvrir le site de": "Open the website of", "autres enseignes": "other retailers",
    "Langue": "Language", "Français": "French", "Langue de l’interface.": "Interface language.",
    "Colonnes TTC, marge et coefficient = formules. Marge valeur = vente HT − achat HT. Marge % = marge valeur ÷ vente HT × 100. Coeff = vente TTC ÷ achat HT. Les frais restent affichés séparément. Les changements sont enregistrés quand tu quittes une cellule. Le choix de devise change l’unité affichée, sans conversion des montants.": "Tax-inclusive, margin and coefficient columns are formulas. Margin value = sale excl. tax − purchase excl. tax. Margin % = margin value ÷ sale excl. tax × 100. Coeff. = sale incl. tax ÷ purchase excl. tax. Fees are shown separately. Changes save when you leave a cell. Currency changes the displayed unit only; amounts are not converted.",
    "dans ta grille": "in your grid", "HT": "EX. TAX",
    "NOMBRO · GRILLE DE CALCUL": "NOMBRO · PRICE CALCULATOR", "Grille de ": "Price ",
    "HT, TTC, TVA, frais, quantité et identifiants sont modifiables. Les marges se recalculent automatiquement.": "Ex-tax and tax-inclusive prices, VAT, fees, quantity and identifiers are editable. Margins recalculate automatically.",
    "PRODUIT": "PRODUCT", "CODE-BARRES": "BARCODE", "FOURNISSEUR": "SUPPLIER",
    "TVA": "VAT",
    "FRAIS TTC": "FEES INCL. TAX", "MARGE VALEUR / UNITÉ": "MARGIN VALUE / UNIT", "MARGE VALEUR TOTALE": "TOTAL MARGIN VALUE", "MARGE %": "MARGIN %", "COEFF": "COEFF.",
    "Estimation totale selon la quantité saisie. Les frais restent séparés et ne sont pas inclus dans la formule de marge.": "Total estimate for the entered quantity. Fees are separate and excluded from the margin formula.",
    "Saisissez vos montants TTC, puis indiquez le taux de TVA applicable.": "Enter tax-inclusive prices, then choose the VAT rate.",
    "ACHAT": "PURCHASE", "VENTE": "SALE", "Mes produits": "My products", "Modifier": "Edit", "Nouvelle ligne": "New product",
    "Scanner ou saisir le code-barres": "Scan or enter a barcode",
    "VOTRE ESPACE, VOS CHIFFRES": "YOUR WORKSPACE, YOUR NUMBERS", "La marge,": "Margins,", "en toute ": "made ", "clarté.": "clear.",
    "Créez votre espace pour suivre la rentabilité de vos produits simplement.": "Create your workspace to easily track product profitability.",
    "Vos fiches vous appartiennent.": "Your product data belongs to you.", "Un espace privé par compte.": "A private workspace for every account.",
    "DÉMARRER": "GET STARTED", "Quelques secondes pour commencer.": "Get started in seconds.",
    "8 caractères minimum": "At least 8 characters", "Déjà inscrit ?": "Already registered?",
    "Connectez-vous pour retrouver vos fiches produit.": "Log in to access your products.",
    "Importer un ": "Import a ", "ligne": "row", "valide": "valid", "prête": "ready", "à importer.": "to import.",
    "Mot de passe": "Password", "Créer mon compte": "Create my account", "GRILLE DE PRIX": "PRICE GRID",
    "prix.": "grid.", "Complétez la grille des prix TTC. Nombro calcule les montants HT et votre marge.": "Enter tax-inclusive prices. Nombro calculates the ex-tax amounts and your margin.",
    "saisir ou scanner": "type or scan",
    "Équilibre": "Break-even", "ÉTAT": "STATUS",
    "Supprimer cette ligne ?": "Delete this row?", "Modifier le nom / les notes": "Edit name / notes",
    "Modifier le produit": "Edit product", "Nouvelle ligne de prix": "New price entry",
    "Choisissez un mot de passe": "Choose a password",
    "Modifier la ligne": "Edit product", "Votre mot de passe": "Your password",
    "Ex. Camille Martin": "e.g. Camille Martin",
    "Nom du fournisseur": "Supplier name", "Ex. REF-0042": "e.g. REF-0042",
    "La ligne a été ajoutée à la grille.": "Product added to the grid.", "La ligne a été mise à jour.": "Product updated.",
    "La ligne a été supprimée.": "Product deleted.", "Votre profil a été mis à jour.": "Your profile has been updated.",
    "Le nom du produit est obligatoire (120 caractères maximum).": "Product name is required (120 characters maximum).",
    "Les montants TTC doivent être des nombres positifs (ex. 12,50).": "Tax-inclusive amounts must be positive numbers (e.g. 12.50).",
    "Le taux de TVA doit être compris entre 0 et 100 %.": "VAT must be between 0 and 100%.",
    "La quantité doit être un entier supérieur à zéro.": "Quantity must be a whole number greater than zero.",
    "Vérifie la longueur du code produit, du code-barres ou du fournisseur.": "Check the product code, barcode or supplier length.",
    "Saisissez une adresse e-mail valide.": "Enter a valid email address.",
    "Saisissez votre nom (100 caractères maximum).": "Enter your name (100 characters maximum).",
    "Saisissez un numéro de téléphone valide.": "Enter a valid phone number.",
    "Le mot de passe doit contenir au moins 8 caractères.": "Password must contain at least 8 characters.",
    "E-mail ou mot de passe incorrect.": "Incorrect email or password.", "Vous êtes déconnecté.": "You have been logged out.",
    "Choisissez une devise proposée dans la liste.": "Choose a currency from the list.",
    "Choisissez un thème proposé dans la liste.": "Choose a theme from the list.",
    "Choisissez une langue proposée dans la liste.": "Choose a language from the list.",
    "Le mot de passe actuel est incorrect.": "The current password is incorrect.",
    "Le nouveau mot de passe doit contenir entre 8 et 256 caractères.": "The new password must contain between 8 and 256 characters.",
    "La confirmation du nouveau mot de passe ne correspond pas.": "The new passwords do not match.",
    "Votre mot de passe a été changé.": "Your password has been changed.",
    "Votre compte est prêt. Vous pouvez créer votre première fiche produit.": "Your account is ready. You can add your first product.",
    "Un compte existe déjà avec cette adresse e-mail.": "An account with this email already exists.",
    "Aucune ligne valide à importer.": "No valid rows to import.",
    "Les colonnes ne correspondent pas à un export CSV Nombro.": "The columns do not match a Nombro CSV export.",
    "Le fichier dépasse la limite de 2 Mo.": "The file exceeds the 2 MB limit.",
    "Choisissez un fichier CSV exporté depuis Nombro.": "Choose a CSV file exported from Nombro.",
    "Impossible de lire le fichier CSV.": "Could not read the CSV file.",
    "L’aperçu d’import a expiré. Sélectionnez à nouveau votre fichier.": "The import preview expired. Select your file again.",
    "Valeurs invalides : montants positifs, TVA entre 0 et 100 %, quantité de 1 à 1 000 000.": "Invalid values: positive amounts, VAT from 0 to 100%, quantity from 1 to 1,000,000.",
    "Code produit, code-barres ou fournisseur trop long.": "Product code, barcode or supplier is too long.",
    "Devise non prise en charge.": "Currency is not supported.", "Thème non pris en charge.": "Theme is not supported.",
    "Langue non prise en charge.": "Language is not supported.",
    "nom, prix, TVA ou quantité invalide.": "invalid name, price, VAT or quantity.",
    "code-barres déjà présent, ligne ignorée.": "barcode already exists; row skipped.",
}


def translate(text):
    if getattr(g, "language", "fr") == "en":
        return TRANSLATIONS.get(text, text)
    return text


def flash(message, category="message"):
    localized = translate(message)
    if getattr(g, "language", "fr") == "en" and message.startswith("Ce code-barres est déjà utilisé par « "):
        product_name = message.removeprefix("Ce code-barres est déjà utilisé par « ").removesuffix(" ».")
        localized = f"This barcode is already used by “{product_name}”."
    elif getattr(g, "language", "fr") == "en" and message.startswith("Ligne ") and " : " in message:
        line_number, detail = message.split(" : ", 1)
        localized = f"{line_number.replace('Ligne', 'Row')}: {translate(detail)}"
    elif getattr(g, "language", "fr") == "en" and message.endswith("produit(s) importé(s). Les doublons de code-barres ont été ignorés."):
        imported_count = message.split(" ", 1)[0]
        localized = f"{imported_count} product(s) imported. Duplicate barcodes were skipped."
    flask_flash(localized, category)


def localized_number(value, digits=2):
    formatted = f"{float(value):.{int(digits)}f}"
    return formatted if getattr(g, "language", "fr") == "en" else formatted.replace(".", ",")


app.jinja_env.filters["localized_number"] = localized_number


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def json_object():
    """Return request JSON only when its top-level value is an object."""
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


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
            currency TEXT NOT NULL DEFAULT 'EUR',
            theme TEXT NOT NULL DEFAULT 'light',
            language TEXT NOT NULL DEFAULT 'fr',
            min_margin_percent REAL NOT NULL DEFAULT 0,
            session_version INTEGER NOT NULL DEFAULT 0,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            key_hash TEXT NOT NULL,
            attempted_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_key_time ON login_attempts(key_hash, attempted_at);
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            product_code TEXT NOT NULL DEFAULT '',
            manufacturer TEXT NOT NULL DEFAULT '',
            supplier_ref TEXT NOT NULL DEFAULT '',
            barcode TEXT NOT NULL DEFAULT '',
            supplier TEXT NOT NULL DEFAULT '',
            purchase_price REAL NOT NULL,
            sale_price REAL NOT NULL,
            purchase_ttc REAL,
            sale_ttc REAL,
            vat_rate REAL NOT NULL DEFAULT 20,
            extra_cost_ttc REAL NOT NULL DEFAULT 0,
            quantity INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            photo_path TEXT NOT NULL DEFAULT '',
            service_description TEXT NOT NULL DEFAULT '',
            service_cost_ttc REAL NOT NULL DEFAULT 0,
            competitors_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS competitor_brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL COLLATE NOCASE,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, name)
        );
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            changed_at TEXT NOT NULL,
            old_purchase_ttc REAL NOT NULL,
            old_sale_ttc REAL NOT NULL,
            old_vat_rate REAL NOT NULL,
            new_purchase_ttc REAL NOT NULL,
            new_sale_ttc REAL NOT NULL,
            new_vat_rate REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_price_history_product ON price_history(user_id, product_id, changed_at DESC);
        CREATE TABLE IF NOT EXISTS product_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            changed_at TEXT NOT NULL,
            actor_name TEXT NOT NULL DEFAULT '',
            changes_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_product_change_log_product ON product_change_log(user_id, product_id, changed_at DESC);
    """)
    # Keep existing local accounts working when the profile fields are added.
    columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "name" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    if "phone" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''")
    if "currency" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN currency TEXT NOT NULL DEFAULT 'EUR'")
    if "theme" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'light'")
    db.execute("UPDATE users SET theme = 'green-dark' WHERE theme = 'dark'")
    if "language" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'fr'")
    if "min_margin_percent" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN min_margin_percent REAL NOT NULL DEFAULT 0")
    if "session_version" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")
    product_columns = {row["name"] for row in db.execute("PRAGMA table_info(products)")}
    for column, definition in (
        ("purchase_ttc", "REAL"),
        ("sale_ttc", "REAL"),
        ("vat_rate", "REAL NOT NULL DEFAULT 20"),
        ("extra_cost_ttc", "REAL NOT NULL DEFAULT 0"),
        ("product_code", "TEXT NOT NULL DEFAULT ''"),
        ("manufacturer", "TEXT NOT NULL DEFAULT ''"),
        ("supplier_ref", "TEXT NOT NULL DEFAULT ''"),
        ("barcode", "TEXT NOT NULL DEFAULT ''"),
        ("supplier", "TEXT NOT NULL DEFAULT ''"),
        ("photo_path", "TEXT NOT NULL DEFAULT ''"),
        ("service_description", "TEXT NOT NULL DEFAULT ''"),
        ("service_cost_ttc", "REAL NOT NULL DEFAULT 0"),
        ("competitors_json", "TEXT NOT NULL DEFAULT '[]'"),
    ):
        if column not in product_columns:
            db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
    # Old prices were entered without VAT fields; retain their value as HT.
    db.execute("UPDATE products SET purchase_ttc = purchase_price * 1.2 WHERE purchase_ttc IS NULL")
    db.execute("UPDATE products SET sale_ttc = sale_price * 1.2 WHERE sale_ttc IS NULL")
    # Move old numeric service entries (e.g. "90") into the currency field.
    for row in db.execute(
        "SELECT id, service_description FROM products WHERE service_cost_ttc = 0 AND service_description != ''"
    ).fetchall():
        try:
            amount = float(row["service_description"].replace(",", ".").strip())
        except (ValueError, AttributeError):
            continue
        if math.isfinite(amount) and 0 <= amount <= 1_000_000_000:
            db.execute(
                "UPDATE products SET service_cost_ttc = ?, service_description = '' WHERE id = ?",
                (round(amount, 2), row["id"]),
            )
    db.commit()


with app.app_context():
    recovery = recover_if_needed(INSTANCE_DIR)
    if recovery:
        print("Nombro : les données ont été restaurées depuis la dernière sauvegarde valide.")
    init_db()


@app.before_request
def prepare_request():
    g.user = None
    g.language = "fr"
    if session.get("user_id"):
        g.user = get_db().execute(
            "SELECT id, email, name, phone, currency, theme, language, min_margin_percent, session_version "
            "FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()
        if g.user is None or session.get("session_version") != g.user["session_version"]:
            session.clear()
            g.user = None
        else:
            g.language = g.user["language"] if g.user["language"] in LANGUAGES else "fr"
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)


@app.context_processor
def inject_globals():
    user = g.get("user")
    code = user["currency"] if user else "EUR"
    return {"csrf_token": session.get("csrf_token"), "current_user": user,
            "currency_symbol": CURRENCIES.get(code, "€"), "currency_code": code,
            "theme_name": user["theme"] if user else "light",
            "current_language": g.get("language", "fr"), "language_names": LANGUAGES,
            "tr": translate}


@app.before_request
def protect_forms():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        submitted = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf_token", "")
        if not submitted or not secrets.compare_digest(submitted, expected):
            abort(400, "Jeton de sécurité invalide. Rechargez la page puis réessayez.")


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.endpoint in {"login", "register", "profile"}:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_urlsafe(32))


def login_attempt_key(email):
    raw = f"{email.lower()}|{request.remote_addr or 'unknown'}".encode("utf-8")
    return hmac.new(app.config["SECRET_KEY"].encode("utf-8"), raw, hashlib.sha256).hexdigest()


def login_is_limited(key_hash):
    now = int(time.time())
    db = get_db()
    db.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (now - LOGIN_WINDOW_SECONDS,))
    count = db.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE key_hash = ? AND attempted_at > ?",
        (key_hash, now - LOGIN_WINDOW_SECONDS),
    ).fetchone()[0]
    return count >= LOGIN_MAX_ATTEMPTS


def record_login_failure(key_hash):
    get_db().execute("INSERT INTO login_attempts (key_hash, attempted_at) VALUES (?, ?)", (key_hash, int(time.time())))
    get_db().commit()


def clear_login_failures(key_hash):
    get_db().execute("DELETE FROM login_attempts WHERE key_hash = ?", (key_hash,))
    get_db().commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def parse_price(value):
    try:
        normalized = "".join(str(value).split()).replace(",", ".")
        result = float(normalized)
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


def parse_product_form(form):
    """Validate shared product fields once for both create and edit forms."""
    data = {
        "name": form.get("name", "").strip(),
        "product_code": form.get("product_code", "").strip(),
        "manufacturer": form.get("manufacturer", "").strip(),
        "supplier_ref": form.get("supplier_ref", "").strip(),
        "barcode": form.get("barcode", "").strip(),
        "supplier": form.get("supplier", "").strip(),
        "purchase": parse_price(form.get("purchase_ttc")),
        "sale": parse_price(form.get("sale_ttc")),
        "vat_rate": parse_rate(form.get("vat_rate", "20")),
        "extra_costs": parse_price(form.get("extra_cost_ttc", "0")),
        "service_cost_ttc": parse_price(form.get("service_cost_ttc", "0") or "0"),
        "notes": form.get("notes", "").strip()[:2000],
    }
    try:
        data["quantity"] = int(form.get("quantity", "1"))
        if not 1 <= data["quantity"] <= 1_000_000:
            raise ValueError
    except (TypeError, ValueError):
        data["quantity"] = None

    if not data["name"] or len(data["name"]) > 120:
        error = "Le nom du produit est obligatoire (120 caractères maximum)."
    elif None in (data["purchase"], data["sale"], data["extra_costs"], data["service_cost_ttc"]):
        error = "Les montants TTC doivent être des nombres positifs (ex. 12,50)."
    elif data["vat_rate"] is None:
        error = "Le taux de TVA doit être compris entre 0 et 100 %."
    elif data["quantity"] is None:
        error = "La quantité doit être un entier supérieur à zéro."
    elif (len(data["product_code"]) > 80 or len(data["manufacturer"]) > 160
          or len(data["supplier_ref"]) > 128 or len(data["barcode"]) > 128
          or len(data["supplier"]) > 160):
        error = "Vérifie la longueur du code produit, du fabricant, de la référence fournisseur, du code-barres ou du fournisseur."
    else:
        error = None
    return data, error


def store_product_photo(upload):
    if not upload or not upload.filename:
        return None, None
    content = upload.stream.read(5_000_001)
    if len(content) > 5_000_000:
        return None, "La photo doit faire moins de 5 Mo."
    try:
        from PIL import Image, ImageOps

        with Image.open(io.BytesIO(content)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                return None, "Choisissez une photo JPG, PNG ou WebP."
            if source.width * source.height > 25_000_000:
                return None, "La résolution de la photo est trop élevée."
            source.verify()
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1600, 1600))
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            filename = f"{secrets.token_hex(20)}.webp"
            PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            image.save(PRODUCT_IMAGE_DIR / filename, "WEBP", quality=85, method=6)
            return filename, None
    except Exception:
        return None, "Impossible de lire cette photo. Choisissez une image JPG, PNG ou WebP valide."


def remove_product_photo(filename):
    if filename:
        (PRODUCT_IMAGE_DIR / Path(filename).name).unlink(missing_ok=True)


def supplier_options(user_id):
    return [row["supplier"] for row in get_db().execute(
        "SELECT DISTINCT supplier FROM products WHERE user_id = ? AND supplier != '' ORDER BY supplier COLLATE NOCASE",
        (user_id,),
    ).fetchall()]


def competitor_brand_options(user_id):
    return [row["name"] for row in get_db().execute(
        "SELECT name FROM competitor_brands WHERE user_id = ? ORDER BY name COLLATE NOCASE",
        (user_id,),
    ).fetchall()]


@app.delete("/api/enseignes/concurrence")
@login_required
def delete_competitor_brand():
    values = json_object()
    brand = str(values.get("brand", "")).strip()
    if not brand or len(brand) > 160:
        return jsonify(error=translate("Nom d’enseigne invalide.")), 400
    db = get_db()
    db.execute(
        "DELETE FROM competitor_brands WHERE user_id = ? AND name = ? COLLATE NOCASE",
        (g.user["id"], brand),
    )
    db.commit()
    return jsonify(deleted=True)


def stored_competitors(raw):
    try:
        items = json.loads(raw or "[]")
        return items if isinstance(items, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def parse_competitors(raw):
    try:
        items = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return [], "Les données de concurrence sont invalides."
    if not isinstance(items, list) or len(items) > 20:
        return [], "Ajoute au maximum 20 enseignes concurrentes par produit."
    parsed = []
    error = None
    for item in items:
        if not isinstance(item, dict):
            error = "Une ligne de concurrence est invalide."
            continue
        brand = str(item.get("brand", "")).strip()
        price_text = str(item.get("price", "")).strip()
        url = str(item.get("url", "")).strip()
        notes = str(item.get("notes", "")).strip()
        if not any((brand, price_text, url, notes)):
            continue
        price = parse_price(price_text)
        if not brand or len(brand) > 160 or price is None or len(url) > 500 or len(notes) > 300:
            error = "Chaque concurrent doit avoir une enseigne et un prix valide. Vérifie aussi la longueur du lien et de la note."
            continue
        if url:
            if "://" not in url:
                url = "https://" + url
            try:
                parts = urlsplit(url)
                valid_url = (
                    parts.scheme in {"http", "https"}
                    and bool(parts.hostname)
                    and not parts.username
                    and not parts.password
                    and not any(character.isspace() for character in url)
                )
            except ValueError:
                valid_url = False
            if not valid_url:
                error = "Le lien d’un concurrent doit être une adresse web valide."
                continue
            url = urlunsplit(parts)
        parsed.append({"brand": brand, "price": price, "url": url, "notes": notes})
    return parsed, error


def save_competitor_brands(db, user_id, competitors):
    for competitor in competitors:
        db.execute(
            "INSERT OR IGNORE INTO competitor_brands (user_id, name, created_at) VALUES (?, ?, ?)",
            (user_id, competitor["brand"], datetime.utcnow().isoformat()),
        )


def barcode_conflict(barcode, user_id, exclude_id=None):
    if not barcode:
        return None
    query = "SELECT id, name FROM products WHERE user_id = ? AND barcode = ?"
    params = [user_id, barcode]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    return get_db().execute(query + " LIMIT 1", params).fetchone()


def record_price_change(db, user_id, product_id, old_purchase, old_sale, old_vat, new_purchase, new_sale, new_vat):
    if (old_purchase, old_sale, old_vat) == (new_purchase, new_sale, new_vat):
        return
    db.execute(
        "INSERT INTO price_history (user_id, product_id, changed_at, old_purchase_ttc, old_sale_ttc, old_vat_rate, "
        "new_purchase_ttc, new_sale_ttc, new_vat_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, product_id, datetime.utcnow().isoformat(), old_purchase, old_sale, old_vat,
         new_purchase, new_sale, new_vat),
    )


AUDIT_FIELDS = (
    "Nom du produit", "Code produit", "Fabricant", "Réf. fournisseur", "Code-barres", "Fournisseur", "Prix d’achat TTC",
    "Prix de vente TTC", "TVA", "Frais annexes TTC", "Prestation incluse TTC", "Quantité",
    "Notes", "Photo", "Concurrence",
)


def product_audit_snapshot(product, currency_symbol):
    product = dict(product)
    competitors = stored_competitors(product.get("competitors_json", "[]"))
    competitor_text = "; ".join(
        f"{item.get('brand', '')} — {float(item.get('price') or 0):.2f} {currency_symbol}"
        for item in competitors
    )
    return {
        "Nom du produit": product.get("name", ""),
        "Code produit": product.get("product_code", ""),
        "Fabricant": product.get("manufacturer", ""),
        "Réf. fournisseur": product.get("supplier_ref", ""),
        "Code-barres": product.get("barcode", ""),
        "Fournisseur": product.get("supplier", ""),
        "Prix d’achat TTC": product.get("purchase_ttc", 0),
        "Prix de vente TTC": product.get("sale_ttc", 0),
        "TVA": product.get("vat_rate", 0),
        "Frais annexes TTC": product.get("extra_cost_ttc", 0),
        "Prestation incluse TTC": product.get("service_cost_ttc", 0),
        "Quantité": product.get("quantity", 1),
        "Notes": product.get("notes", ""),
        "Photo": bool(product.get("photo_path", "")),
        "Concurrence": competitor_text,
    }


def record_product_changes(db, user_id, product_id, actor_name, old_values, new_values):
    changes = {}
    for field in AUDIT_FIELDS:
        old_value = old_values.get(field, "")
        new_value = new_values.get(field, "")
        if old_value == new_value:
            continue
        if field in {"Prix d’achat TTC", "Prix de vente TTC", "Frais annexes TTC", "Prestation incluse TTC"}:
            old_value = f"{float(old_value):.2f} {CURRENCIES.get(g.user['currency'], '€')}" if old_value != "" else "—"
            new_value = f"{float(new_value):.2f} {CURRENCIES.get(g.user['currency'], '€')}" if new_value != "" else "—"
        elif field == "TVA":
            old_value = f"{float(old_value):g} %" if old_value != "" else "—"
            new_value = f"{float(new_value):g} %" if new_value != "" else "—"
        elif field == "Photo":
            old_value = "Présente" if old_value else "Absente"
            new_value = "Présente" if new_value else "Absente"
        else:
            old_value = str(old_value).strip() or "—"
            new_value = str(new_value).strip() or "—"
        changes[field] = {"old": old_value, "new": new_value}
    if changes:
        db.execute(
            "INSERT INTO product_change_log (user_id, product_id, changed_at, actor_name, changes_json) VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, datetime.utcnow().isoformat(), actor_name, json.dumps(changes, ensure_ascii=False)),
        )


def record_product_created(db, user_id, product_id, product):
    product = dict(product)
    if "competitors_json" not in product and "competitors" in product:
        product["competitors_json"] = json.dumps(product["competitors"], ensure_ascii=False)
    record_product_changes(
        db, user_id, product_id, g.user["name"] or g.user["email"], {},
        product_audit_snapshot(product, CURRENCIES.get(g.user["currency"], "€")),
    )


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
        elif len(password) < 8 or len(password) > 256:
            flash("Le nouveau mot de passe doit contenir entre 8 et 256 caractères.", "error")
        else:
            try:
                db = get_db()
                cursor = db.execute("INSERT INTO users (email, name, phone, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                                    (email, name, phone, generate_password_hash(password), datetime.utcnow().isoformat()))
                db.commit()
                session.clear()
                session.permanent = True
                session["user_id"] = cursor.lastrowid
                session["session_version"] = 0
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
        currency = request.form.get("currency", "EUR").strip().upper()
        theme = request.form.get("theme", "light").strip().lower()
        language = request.form.get("language", "fr").strip().lower()
        min_margin = parse_rate(request.form.get("min_margin_percent", "0"))
        if not name or len(name) > 100:
            flash("Saisissez votre nom (100 caractères maximum).", "error")
        elif len(phone) > 30 or (phone and not all(char.isdigit() or char in "+ ().-" for char in phone)):
            flash("Saisissez un numéro de téléphone valide.", "error")
        elif currency not in CURRENCIES:
            flash("Choisissez une devise proposée dans la liste.", "error")
        elif theme not in THEMES:
            flash("Choisissez un thème proposé dans la liste.", "error")
        elif language not in LANGUAGES:
            flash("Choisissez une langue proposée dans la liste.", "error")
        elif min_margin is None:
            flash("La marge minimum doit être comprise entre 0 et 100 %.", "error")
        else:
            db = get_db()
            phone_changed = phone != g.user["phone"]
            if phone_changed:
                db.execute(
                    "UPDATE users SET name = ?, phone = ?, min_margin_percent = ?, session_version = session_version + 1, "
                    "currency = ?, theme = ?, language = ? WHERE id = ?",
                    (name, phone, min_margin, currency, theme, language, g.user["id"]),
                )
                session["session_version"] = g.user["session_version"] + 1
            else:
                db.execute(
                    "UPDATE users SET name = ?, phone = ?, min_margin_percent = ?, currency = ?, theme = ?, language = ? WHERE id = ?",
                    (name, phone, min_margin, currency, theme, language, g.user["id"]),
                )
            db.commit()
            flash("Votre profil a été mis à jour.", "success")
            return redirect(url_for("dashboard"))
    return render_template("profile.html")


@app.post("/profil/mot-de-passe")
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")
    password_row = get_db().execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not password_row or not check_password_hash(password_row["password_hash"], current_password):
        flash("Le mot de passe actuel est incorrect.", "error")
    elif len(new_password) < 8 or len(new_password) > 256:
        flash("Le nouveau mot de passe doit contenir entre 8 et 256 caractères.", "error")
    elif new_password != confirmation:
        flash("La confirmation du nouveau mot de passe ne correspond pas.", "error")
    else:
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new_password), g.user["id"]))
        db.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (g.user["id"],))
        db.commit()
        session["session_version"] = g.user["session_version"] + 1
        flash("Votre mot de passe a été changé.", "success")
    return redirect(url_for("profile"))


def establish_login(user_id):
    version = get_db().execute("SELECT session_version FROM users WHERE id = ?", (user_id,)).fetchone()
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["session_version"] = version["session_version"]
    session["csrf_token"] = secrets.token_urlsafe(32)


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        key_hash = login_attempt_key(email)
        if login_is_limited(key_hash):
            flash("Trop de tentatives de connexion. Réessaie dans 15 minutes.", "error")
        else:
            user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            password_hash = user["password_hash"] if user else DUMMY_PASSWORD_HASH
            password_valid = check_password_hash(password_hash, password)
            if user and password_valid:
                clear_login_failures(key_hash)
                establish_login(user["id"])
                return redirect(url_for("dashboard"))
            record_login_failure(key_hash)
            flash("E-mail ou mot de passe incorrect.", "error")
    return render_template("login.html")


@app.patch("/api/preferences/theme")
@login_required
def update_theme():
    values = json_object()
    theme = str(values.get("theme", "")).lower()
    if theme not in THEMES:
        return jsonify(error=translate("Thème non pris en charge.")), 400
    db = get_db()
    db.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, g.user["id"]))
    db.commit()
    return jsonify(saved=True, theme=theme)


@app.patch("/api/preferences/langue")
@login_required
def update_language():
    values = json_object()
    language = str(values.get("language", "")).lower()
    if language not in LANGUAGES:
        return jsonify(error=translate("Langue non prise en charge.")), 400
    db = get_db()
    db.execute("UPDATE users SET language = ? WHERE id = ?", (language, g.user["id"]))
    db.commit()
    return jsonify(saved=True, language=language)


@app.post("/deconnexion")
@login_required
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "success")
    return redirect(url_for("login"))


def dashboard_data():
    products = [dict(row) for row in get_db().execute(
        "SELECT * FROM products WHERE user_id = ? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()]
    for product in products:
        product["competitors"] = stored_competitors(product.get("competitors_json"))
    total_margin = sum((p["sale_ttc"] - p["purchase_ttc"]) / (1 + p["vat_rate"] / 100) * p["quantity"] for p in products)
    profitable_count = sum(1 for p in products if p["sale_ttc"] > p["purchase_ttc"])
    average_margin = 0
    if products:
        margins = []
        for p in products:
            margins.append((p["sale_ttc"] - p["purchase_ttc"]) / p["sale_ttc"] * 100 if p["sale_ttc"] else 0)
        average_margin = sum(margins) / len(margins)
    below_target_count = sum(
        1 for p in products
        if (
            (p["sale_ttc"] - p["purchase_ttc"]) / p["sale_ttc"] * 100 < g.user["min_margin_percent"]
            if p["sale_ttc"] else g.user["min_margin_percent"] > 0
        )
    )
    return {"products": products, "total_margin": total_margin,
            "profitable_count": profitable_count, "average_margin": average_margin,
            "below_target_count": below_target_count, "min_margin_percent": g.user["min_margin_percent"]}


@app.route("/tableau-de-bord")
@login_required
def dashboard():
    return render_template("dashboard.html", **dashboard_data())


@app.route("/grille")
@login_required
def spreadsheet():
    suppliers = supplier_options(g.user["id"])
    return render_template("grid.html", suppliers=suppliers, **dashboard_data())


@app.get("/api/produits/recherche")
@login_required
def search_saved_products():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify(products=[])
    pattern = f"%{query}%"
    rows = get_db().execute(
        "SELECT id, name, product_code, manufacturer, supplier_ref, supplier, purchase_ttc, sale_ttc, "
        "vat_rate, extra_cost_ttc, service_cost_ttc, competitors_json "
        "FROM products WHERE user_id = ? AND (name LIKE ? COLLATE NOCASE OR product_code LIKE ? COLLATE NOCASE "
        "OR manufacturer LIKE ? COLLATE NOCASE OR supplier_ref LIKE ? COLLATE NOCASE OR supplier LIKE ? COLLATE NOCASE) "
        "ORDER BY CASE WHEN name = ? COLLATE NOCASE THEN 0 ELSE 1 END, name COLLATE NOCASE LIMIT 10",
        (g.user["id"], pattern, pattern, pattern, pattern, pattern, query),
    ).fetchall()
    return jsonify(products=[{
        "id": row["id"], "name": row["name"], "product_code": row["product_code"],
        "manufacturer": row["manufacturer"], "supplier_ref": row["supplier_ref"],
        "supplier": row["supplier"], "purchase_ttc": row["purchase_ttc"],
        "sale_ttc": row["sale_ttc"], "vat_rate": row["vat_rate"],
        "extra_cost_ttc": row["extra_cost_ttc"], "service_cost_ttc": row["service_cost_ttc"],
        "competitors": stored_competitors(row["competitors_json"]),
    } for row in rows])


@app.get("/produit/<int:product_id>")
@login_required
def product_detail(product_id):
    product = get_db().execute(
        "SELECT * FROM products WHERE id = ? AND user_id = ?",
        (product_id, g.user["id"]),
    ).fetchone()
    if product is None:
        abort(404)
    product = dict(product)
    product["competitors"] = stored_competitors(product.get("competitors_json"))
    factor = 1 + product["vat_rate"] / 100
    purchase_ht = product["purchase_ttc"] / factor
    sale_ht = product["sale_ttc"] / factor
    margin_value = sale_ht - purchase_ht
    margin_percent = margin_value / sale_ht * 100 if sale_ht else 0
    return render_template(
        "product_detail.html", product=product,
        purchase_ht=purchase_ht, sale_ht=sale_ht,
        fees_ht=product["extra_cost_ttc"] / factor,
        margin_value=margin_value, margin_total=margin_value * product["quantity"],
        margin_percent=margin_percent,
        coefficient=product["sale_ttc"] / purchase_ht if purchase_ht else 0,
        currency_symbol=CURRENCIES.get(g.user["currency"], "€"),
    )


@app.get("/produit/<int:product_id>/photo")
@login_required
def product_photo(product_id):
    row = get_db().execute(
        "SELECT photo_path FROM products WHERE id = ? AND user_id = ?",
        (product_id, g.user["id"]),
    ).fetchone()
    if row is None or not row["photo_path"]:
        abort(404)
    response = send_from_directory(PRODUCT_IMAGE_DIR, Path(row["photo_path"]).name, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/api/produit/<int:product_id>/cellules", methods=["PATCH"])
@login_required
def update_product_cells(product_id):
    product = get_db().execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"])).fetchone()
    if product is None:
        return jsonify(error="Produit introuvable."), 404
    values = json_object()
    purchase_ht = parse_price(str(values.get("purchase_ht", "")))
    sale_ht = parse_price(str(values.get("sale_ht", "")))
    purchase_ttc_input = parse_price(str(values.get("purchase_ttc", ""))) if "purchase_ttc" in values else None
    sale_ttc_input = parse_price(str(values.get("sale_ttc", ""))) if "sale_ttc" in values else None
    extra_ht = parse_price(str(values.get("extra_cost_ht", "0")))
    vat_rate = parse_rate(str(values.get("vat_rate", "")))
    product_code = str(values.get("product_code", "")).strip()
    barcode = str(values.get("barcode", "")).strip()
    supplier = str(values.get("supplier", "")).strip()
    service_cost_ttc = parse_price(str(values.get("service_cost_ttc", "0") or "0"))
    try:
        quantity_value = float(values.get("quantity", 0))
        quantity = int(quantity_value)
        if not math.isfinite(quantity_value) or quantity_value != quantity or quantity < 1 or quantity > 1_000_000:
            raise ValueError
    except (TypeError, ValueError):
        quantity = None
    if None in (purchase_ht, sale_ht, extra_ht, vat_rate, quantity) or ("purchase_ttc" in values and purchase_ttc_input is None) or ("sale_ttc" in values and sale_ttc_input is None):
        return jsonify(error=translate("Valeurs invalides : montants positifs, TVA entre 0 et 100 %, quantité de 1 à 1 000 000.")), 400
    if len(product_code) > 80 or len(barcode) > 128 or len(supplier) > 160:
        return jsonify(error=translate("Code produit, code-barres ou fournisseur trop long.")), 400
    if service_cost_ttc is None:
        return jsonify(error=translate("Le montant de la prestation doit être positif ou nul.")), 400
    duplicate = barcode_conflict(barcode, g.user["id"], product_id)
    if duplicate:
        if g.language == "en":
            return jsonify(error=f"This barcode is already used by “{duplicate['name']}”."), 409
        return jsonify(error=f"Ce code-barres est déjà utilisé par « {duplicate['name']} »."), 409
    factor = 1 + vat_rate / 100
    if "purchase_ttc" in values:
        purchase_ht = purchase_ttc_input / factor
    if "sale_ttc" in values:
        sale_ht = sale_ttc_input / factor
    db = get_db()
    new_purchase_ttc = round(purchase_ttc_input, 2) if "purchase_ttc" in values else round(purchase_ht * factor, 2)
    new_sale_ttc = round(sale_ttc_input, 2) if "sale_ttc" in values else round(sale_ht * factor, 2)
    old_audit = product_audit_snapshot(product, CURRENCIES.get(g.user["currency"], "€"))
    new_audit = dict(old_audit)
    new_audit.update({
        "Code produit": product_code, "Code-barres": barcode, "Fournisseur": supplier,
        "Prestation incluse TTC": service_cost_ttc, "Prix d’achat TTC": new_purchase_ttc,
        "Prix de vente TTC": new_sale_ttc, "TVA": vat_rate,
        "Frais annexes TTC": round(extra_ht * factor, 2), "Quantité": quantity,
    })
    record_price_change(db, g.user["id"], product_id, product["purchase_ttc"], product["sale_ttc"], product["vat_rate"],
                        new_purchase_ttc, new_sale_ttc, vat_rate)
    record_product_changes(db, g.user["id"], product_id, g.user["name"] or g.user["email"], old_audit, new_audit)
    db.execute("""UPDATE products SET product_code = ?, barcode = ?, supplier = ?, service_cost_ttc = ?, purchase_price = ?, sale_price = ?, purchase_ttc = ?,
        sale_ttc = ?, vat_rate = ?, extra_cost_ttc = ?, quantity = ?
        WHERE id = ? AND user_id = ?""",
        (product_code, barcode, supplier, service_cost_ttc, purchase_ht, sale_ht, new_purchase_ttc, new_sale_ttc,
         vat_rate, round(extra_ht * factor, 2), quantity, product_id, g.user["id"]))
    db.commit()
    return jsonify(saved=True)


@app.route("/api/preferences/devise", methods=["PATCH"])
@login_required
def update_currency():
    values = json_object()
    currency = str(values.get("currency", "")).upper()
    if currency not in CURRENCIES:
        return jsonify(error=translate("Devise non prise en charge.")), 400
    get_db().execute("UPDATE users SET currency = ? WHERE id = ?", (currency, g.user["id"]))
    get_db().commit()
    return jsonify(saved=True, currency=currency, symbol=CURRENCIES[currency])


@app.get("/api/code-barres/verifier")
@login_required
def check_barcode():
    barcode = request.args.get("barcode", "").strip()
    exclude_id = request.args.get("exclude", type=int)
    duplicate = barcode_conflict(barcode, g.user["id"], exclude_id)
    return jsonify(duplicate=bool(duplicate), name=duplicate["name"] if duplicate else "")


@app.route("/produits/export.csv")
@login_required
def export_products():
    products = get_db().execute("SELECT * FROM products WHERE user_id = ? ORDER BY name COLLATE NOCASE", (g.user["id"],)).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Produit", "Code produit", "Fabricant", "Ref Fou", "Code-barres", "Fournisseur", "Devise", "Achat TTC", "Achat HT", "Vente TTC", "Vente HT", "TVA %", "Frais TTC", "Prestation incluse TTC", "Marge valeur HT / unité", "Marge valeur HT totale", "Marge %", "Coefficient", "Quantité", "Notes"])
    for product in products:
        factor = 1 + product["vat_rate"] / 100
        purchase_ht = product["purchase_ttc"] / factor
        sale_ht = product["sale_ttc"] / factor
        margin_value = sale_ht - purchase_ht
        margin_percent = margin_value / sale_ht * 100 if sale_ht else 0
        coefficient = product["sale_ttc"] / purchase_ht if purchase_ht else 0
        writer.writerow([product["name"], product["product_code"], product["manufacturer"], product["supplier_ref"], product["barcode"], product["supplier"], g.user["currency"], product["purchase_ttc"], round(purchase_ht, 2), product["sale_ttc"], round(sale_ht, 2), product["vat_rate"], product["extra_cost_ttc"], product["service_cost_ttc"], round(margin_value, 2), round(margin_value * product["quantity"], 2), round(margin_percent, 1), round(coefficient, 2), product["quantity"], product["notes"]])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=nombro-produits.csv"})


@app.get("/produits/export.xlsx")
@login_required
def export_products_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    products = get_db().execute(
        "SELECT * FROM products WHERE user_id = ? ORDER BY name COLLATE NOCASE",
        (g.user["id"],),
    ).fetchall()
    currency_symbol = CURRENCIES[g.user["currency"]]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Produits"
    sheet.append([
        "Produit", "Code produit", "Fabricant", "Ref Fou", "Code-barres", "Fournisseur", "Prestation incluse TTC",
        "Achat TTC", "Achat HT", "Vente TTC", "Vente HT", "TVA %", "Frais TTC",
        "Marge HT / unité", "Marge HT totale", "Marge %", "Coefficient", "Quantité", "Notes",
    ])
    competitor_sheet = workbook.create_sheet("Concurrence")
    competitor_sheet.append([
        "Produit", "Code produit", "Enseigne", "Prix concurrent TTC", "Vente TTC",
        "Écart vs vente TTC", "Lien", "Note",
    ])

    header_fill = PatternFill("solid", fgColor="2C7657")
    header_font = Font(color="FFFFFF", bold=True)
    border = Border(bottom=Side(style="thin", color="DCE5DD"))
    currency_format = f'#,##0.00 "{currency_symbol}"'
    for current_sheet in (sheet, competitor_sheet):
        current_sheet.freeze_panes = "A2"
        for cell in current_sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        current_sheet.row_dimensions[1].height = 30

    for product in products:
        factor = 1 + product["vat_rate"] / 100
        purchase_ht = product["purchase_ttc"] / factor
        sale_ht = product["sale_ttc"] / factor
        margin_value = sale_ht - purchase_ht
        margin_percent = margin_value / sale_ht * 100 if sale_ht else 0
        coefficient = product["sale_ttc"] / purchase_ht if purchase_ht else 0
        sheet.append([
            product["name"], product["product_code"], product["manufacturer"], product["supplier_ref"], product["barcode"], product["supplier"],
            product["service_cost_ttc"], product["purchase_ttc"], round(purchase_ht, 2),
            product["sale_ttc"], round(sale_ht, 2), product["vat_rate"], product["extra_cost_ttc"],
            round(margin_value, 2), round(margin_value * product["quantity"], 2),
            round(margin_percent, 1), round(coefficient, 2), product["quantity"], product["notes"],
        ])
        for competitor in stored_competitors(product["competitors_json"]):
            competitor_sheet.append([
                product["name"], product["product_code"], competitor.get("brand", ""),
                competitor.get("price", 0), product["sale_ttc"],
                round(float(competitor.get("price", 0)) - product["sale_ttc"], 2),
                competitor.get("url", ""), competitor.get("notes", ""),
            ])

    for row in sheet.iter_rows(min_row=2):
        for index in (6, 7, 8, 9, 10, 12, 13, 14):
            row[index].number_format = currency_format
        row[9].number_format = '0.00"%"'
        row[13].number_format = '0.0"%"'
        row[14].number_format = "0.00"
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (1, 3, 4, 20))
    for row in competitor_sheet.iter_rows(min_row=2):
        for index in (3, 4, 5):
            row[index].number_format = currency_format
        if row[6].value:
            row[6].hyperlink = row[6].value
            row[6].style = "Hyperlink"
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in (1, 3, 7, 8))

    product_widths = [26, 18, 22, 18, 18, 22, 34, 16, 16, 16, 16, 10, 16, 20, 20, 12, 12, 10, 36]
    competitor_widths = [26, 18, 22, 21, 16, 20, 44, 36]
    for current_sheet, widths in ((sheet, product_widths), (competitor_sheet, competitor_widths)):
        current_sheet.auto_filter.ref = current_sheet.dimensions
        for index, width in enumerate(widths, start=1):
            current_sheet.column_dimensions[get_column_letter(index)].width = width

    output = io.BytesIO()
    workbook.save(output)
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=nombro-produits.xlsx", "Cache-Control": "no-store"},
    )


@app.get("/produits/export.pdf")
@login_required
def export_products_pdf():
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    products = get_db().execute(
        "SELECT * FROM products WHERE user_id = ? ORDER BY name COLLATE NOCASE",
        (g.user["id"],),
    ).fetchall()
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), rightMargin=10 * mm, leftMargin=10 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title="Nombro - catalogue et marges", author="Nombro",
    )
    font_path = next((path for path in (
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ) if path.is_file()), None)
    if font_path:
        pdfmetrics.registerFont(TTFont("NombroSans", str(font_path)))
        font_name = "NombroSans"
    else:
        font_name = "Helvetica"
    styles = getSampleStyleSheet()
    body = ParagraphStyle("NombroBody", parent=styles["BodyText"], fontName=font_name, fontSize=7, leading=9, alignment=TA_LEFT)
    title = ParagraphStyle("NombroTitle", parent=styles["Title"], fontName=font_name, fontSize=17, textColor=colors.HexColor("#205c42"), alignment=TA_LEFT)
    rows = [["Produit", "Fournisseur", "Achat TTC", "Vente TTC", "Marge HT / unité", "Marge %", "Coeff.", "Qté", "État"]]
    total_margin = 0
    below_target = 0
    for product in products:
        factor = 1 + product["vat_rate"] / 100
        purchase_ht = product["purchase_ttc"] / factor
        sale_ht = product["sale_ttc"] / factor
        margin_value = sale_ht - purchase_ht
        margin_percent = margin_value / sale_ht * 100 if sale_ht else 0
        total_margin += margin_value * product["quantity"]
        target_low = margin_percent < g.user["min_margin_percent"]
        below_target += int(target_low)
        status = "À perte" if margin_value < 0 else "Sous seuil" if target_low else "Rentable" if margin_value > 0 else "Équilibre"
        rows.append([
            Paragraph(escape(product["name"]), body), Paragraph(escape(product["supplier"] or "—"), body),
            f"{product['purchase_ttc']:.2f} {CURRENCIES[g.user['currency']]}",
            f"{product['sale_ttc']:.2f} {CURRENCIES[g.user['currency']]}",
            f"{margin_value:.2f} {CURRENCIES[g.user['currency']]}", f"{margin_percent:.1f}%",
            f"{(product['sale_ttc'] / purchase_ht if purchase_ht else 0):.2f}",
            str(product["quantity"]), status,
        ])
    story = [Paragraph("Nombro · Catalogue et marges", title), Spacer(1, 4 * mm),
             Paragraph(f"{len(products)} produit(s) · Marge totale estimée : {total_margin:.2f} {CURRENCIES[g.user['currency']]} HT · {below_target} sous le seuil de {g.user['min_margin_percent']:.1f}%", body), Spacer(1, 5 * mm)]
    table = Table(rows, repeatRows=1, colWidths=[46 * mm, 34 * mm, 27 * mm, 27 * mm, 31 * mm, 20 * mm, 18 * mm, 13 * mm, 23 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf1eb")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#205c42")),
        ("FONTNAME", (0, 0), (-1, -1), font_name), ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9e2da")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8faf8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    document.build(story)
    return Response(output.getvalue(), mimetype="application/pdf", headers={
        "Content-Disposition": "attachment; filename=nombro-catalogue.pdf", "Cache-Control": "no-store",
    })


@app.get("/sauvegarde/produits.json")
@login_required
def download_backup():
    products = get_db().execute(
        "SELECT name, product_code, manufacturer, supplier_ref, barcode, supplier, purchase_price, sale_price, purchase_ttc, sale_ttc, "
        "vat_rate, extra_cost_ttc, quantity, notes, service_description, service_cost_ttc, competitors_json, created_at "
        "FROM products WHERE user_id = ? ORDER BY id",
        (g.user["id"],),
    ).fetchall()
    backup = {
        "application": "Nombro",
        "format_version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "currency": g.user["currency"],
        "products": [dict(product) for product in products],
    }
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    filename = f"nombro-sauvegarde-{datetime.now().strftime('%Y-%m-%d')}.json"
    return Response(content, mimetype="application/json; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})


@app.post("/sauvegarde/restaurer")
@login_required
def restore_backup():
    upload = request.files.get("backup_file")
    mode = request.form.get("restore_mode", "merge")
    if mode not in {"merge", "replace"}:
        mode = "merge"
    if mode == "replace" and request.form.get("confirm_replace") != "yes":
        flash("Confirme le remplacement du catalogue avant de continuer.", "error")
        return redirect(url_for("profile"))
    if not upload or not (upload.filename or "").lower().endswith(".json"):
        flash("Sélectionne un fichier de sauvegarde JSON Nombro.", "error")
        return redirect(url_for("profile"))
    try:
        content = upload.stream.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("La sauvegarde dépasse la limite de 2 Mo.")
        backup = json.loads(content.decode("utf-8"))
        if backup.get("application") != "Nombro" or backup.get("format_version") != 1:
            raise ValueError("Ce fichier n’est pas une sauvegarde Nombro prise en charge.")
        raw_products = backup.get("products")
        if not isinstance(raw_products, list) or not raw_products:
            raise ValueError("La sauvegarde ne contient aucun produit.")

        products = []
        seen_barcodes = set()
        for line, row in enumerate(raw_products, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"La ligne {line} de la sauvegarde est invalide.")
            name = str(row.get("name", "")).strip()
            purchase = parse_price(str(row.get("purchase_ttc", "")))
            sale = parse_price(str(row.get("sale_ttc", "")))
            vat = parse_rate(str(row.get("vat_rate", "20")))
            fees = parse_price(str(row.get("extra_cost_ttc", "0")))
            service_description = str(row.get("service_description", "")).strip()
            raw_service_cost = row.get("service_cost_ttc", service_description or "0")
            service_cost = parse_price(str(raw_service_cost))
            if service_cost is None and "service_cost_ttc" not in row:
                service_cost = 0
            competitors, competitor_error = parse_competitors(str(row.get("competitors_json", "[]")))
            try:
                quantity = int(row.get("quantity", 1))
            except (TypeError, ValueError):
                quantity = 0
            candidate = {
                "name": name,
                "product_code": str(row.get("product_code", "")).strip(),
                "manufacturer": str(row.get("manufacturer", "")).strip(),
                "supplier_ref": str(row.get("supplier_ref", "")).strip(),
                "barcode": str(row.get("barcode", "")).strip(),
                "supplier": str(row.get("supplier", "")).strip(),
                "purchase_ttc": purchase,
                "sale_ttc": sale,
                "vat_rate": vat,
                "extra_cost_ttc": fees,
                "quantity": quantity,
                "notes": str(row.get("notes", "")).strip(),
                "service_description": service_description,
                "service_cost_ttc": service_cost,
                "competitors": competitors,
                "created_at": str(row.get("created_at") or datetime.utcnow().isoformat()),
            }
            if (
                not name or len(name) > 120 or None in (purchase, sale, vat, fees, service_cost)
                or len(service_description) > 1000 or competitor_error
                or not 1 <= quantity <= 1_000_000
                or len(candidate["product_code"]) > 80 or len(candidate["barcode"]) > 128
                or len(candidate["manufacturer"]) > 160 or len(candidate["supplier_ref"]) > 128
                or len(candidate["supplier"]) > 160 or len(candidate["notes"]) > 2000
            ):
                raise ValueError(f"La ligne {line} contient des valeurs invalides.")
            if candidate["barcode"]:
                if candidate["barcode"] in seen_barcodes:
                    raise ValueError(f"Le code-barres de la ligne {line} apparaît plusieurs fois.")
                seen_barcodes.add(candidate["barcode"])
            products.append(candidate)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError) as error:
        flash(str(error) or "Impossible de lire la sauvegarde.", "error")
        return redirect(url_for("profile"))

    db = get_db()
    existing = set()
    old_photo_paths = []
    if mode == "merge":
        existing = {row["barcode"] for row in db.execute(
            "SELECT barcode FROM products WHERE user_id = ? AND barcode != ''", (g.user["id"],)
        ).fetchall()}
    else:
        old_photo_paths = [row["photo_path"] for row in db.execute(
            "SELECT photo_path FROM products WHERE user_id = ? AND photo_path != ''", (g.user["id"],)
        ).fetchall()]
    added = skipped = 0
    try:
        db.execute("BEGIN")
        if mode == "replace":
            db.execute("DELETE FROM products WHERE user_id = ?", (g.user["id"],))
        for product in products:
            if product["barcode"] and product["barcode"] in existing:
                skipped += 1
                continue
            factor = 1 + product["vat_rate"] / 100
            cursor = db.execute(
                "INSERT INTO products (user_id, name, product_code, manufacturer, supplier_ref, barcode, supplier, purchase_price, sale_price, "
                "purchase_ttc, sale_ttc, vat_rate, extra_cost_ttc, quantity, notes, service_description, service_cost_ttc, competitors_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (g.user["id"], product["name"], product["product_code"], product["manufacturer"], product["supplier_ref"], product["barcode"], product["supplier"],
                 round(product["purchase_ttc"] / factor, 2), round(product["sale_ttc"] / factor, 2),
                 product["purchase_ttc"], product["sale_ttc"], product["vat_rate"], product["extra_cost_ttc"],
                 product["quantity"], product["notes"], product["service_description"], product["service_cost_ttc"],
                 json.dumps(product["competitors"], ensure_ascii=False), product["created_at"]),
            )
            record_product_created(db, g.user["id"], cursor.lastrowid, {**product, "photo_path": ""})
            save_competitor_brands(db, g.user["id"], product["competitors"])
            added += 1
            if product["barcode"]:
                existing.add(product["barcode"])
        if mode == "replace" and backup.get("currency") in CURRENCIES:
            db.execute("UPDATE users SET currency = ? WHERE id = ?", (backup["currency"], g.user["id"]))
        db.commit()
        for photo_path in old_photo_paths:
            remove_product_photo(photo_path)
    except sqlite3.DatabaseError:
        db.rollback()
        flash("La restauration a échoué. Le catalogue n’a pas été modifié.", "error")
        return redirect(url_for("profile"))
    flash(f"{added}{translate(' lignes ajoutées, ')}{skipped}{translate(' doublon(s) ignoré(s).')}", "success")
    return redirect(url_for("spreadsheet"))


@app.route("/produit/nouveau", methods=["GET", "POST"])
@login_required
def new_product():
    if request.method == "POST":
        data, error = parse_product_form(request.form)
        competitors, competitor_error = parse_competitors(request.form.get("competitors_json", "[]"))
        if not error and competitor_error:
            error = competitor_error
        duplicate = barcode_conflict(data["barcode"], g.user["id"])
        if not error and duplicate:
            error = f"Ce code-barres est déjà utilisé par « {duplicate['name']} »."
        photo_path, photo_error = store_product_photo(request.files.get("photo")) if not error else (None, None)
        if not error and photo_error:
            error = photo_error
        if error:
            flash(error, "error")
        else:
            db = get_db()
            factor = 1 + data["vat_rate"] / 100
            purchase_ht = round(data["purchase"] / factor, 2)
            sale_ht = round(data["sale"] / factor, 2)
            cursor = db.execute("""INSERT INTO products
                (user_id, name, product_code, manufacturer, supplier_ref, barcode, supplier, purchase_price, sale_price, purchase_ttc, sale_ttc, vat_rate, extra_cost_ttc, quantity, notes, photo_path, service_description, service_cost_ttc, competitors_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g.user["id"], data["name"], data["product_code"], data["manufacturer"], data["supplier_ref"], data["barcode"], data["supplier"], purchase_ht, sale_ht,
                 data["purchase"], data["sale"], data["vat_rate"], data["extra_costs"], data["quantity"], data["notes"], photo_path or "",
                 "", data["service_cost_ttc"], json.dumps(competitors, ensure_ascii=False), datetime.utcnow().isoformat()))
            created_product = {
                "name": data["name"], "product_code": data["product_code"], "barcode": data["barcode"],
                "manufacturer": data["manufacturer"], "supplier_ref": data["supplier_ref"],
                "supplier": data["supplier"], "purchase_ttc": data["purchase"], "sale_ttc": data["sale"],
                "vat_rate": data["vat_rate"], "extra_cost_ttc": data["extra_costs"],
                "quantity": data["quantity"], "notes": data["notes"], "photo_path": photo_path or "",
                "service_cost_ttc": data["service_cost_ttc"], "competitors_json": json.dumps(competitors, ensure_ascii=False),
            }
            record_product_changes(db, g.user["id"], cursor.lastrowid, g.user["name"] or g.user["email"], {},
                                   product_audit_snapshot(created_product, CURRENCIES.get(g.user["currency"], "€")))
            save_competitor_brands(db, g.user["id"], competitors)
            db.commit()
            flash("La ligne a été ajoutée à la grille.", "success")
            return redirect(url_for("spreadsheet"))
    else:
        competitors = []
    return render_template("new_product.html", suppliers=supplier_options(g.user["id"]),
                           competitor_brands=competitor_brand_options(g.user["id"]), competitors=competitors)


@app.route("/produit/<int:product_id>/modifier", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"])).fetchone()
    if product is None:
        abort(404)
    if request.method == "POST":
        data, error = parse_product_form(request.form)
        competitors, competitor_error = parse_competitors(request.form.get("competitors_json", "[]"))
        if not error and competitor_error:
            error = competitor_error
        duplicate = barcode_conflict(data["barcode"], g.user["id"], product_id)
        if not error and duplicate:
            error = f"Ce code-barres est déjà utilisé par « {duplicate['name']} »."
        photo_upload = request.files.get("photo")
        photo_path = product["photo_path"]
        remove_photo = request.form.get("remove_photo") == "yes"
        new_photo_path, photo_error = store_product_photo(photo_upload) if not error else (None, None)
        if not error and photo_error:
            error = photo_error
        if error:
            flash(error, "error")
        else:
            if new_photo_path:
                photo_path = new_photo_path
            elif remove_photo:
                photo_path = ""
            factor = 1 + data["vat_rate"] / 100
            new_purchase = data["purchase"]
            new_sale = data["sale"]
            old_audit = product_audit_snapshot(product, CURRENCIES.get(g.user["currency"], "€"))
            new_audit = {
                "Nom du produit": data["name"], "Code produit": data["product_code"],
                "Fabricant": data["manufacturer"], "Réf. fournisseur": data["supplier_ref"],
                "Code-barres": data["barcode"], "Fournisseur": data["supplier"],
                "Prix d’achat TTC": data["purchase"], "Prix de vente TTC": data["sale"],
                "TVA": data["vat_rate"], "Frais annexes TTC": data["extra_costs"],
                "Prestation incluse TTC": data["service_cost_ttc"], "Quantité": data["quantity"],
                "Notes": data["notes"], "Photo": bool(photo_path),
                "Concurrence": "; ".join(f"{item['brand']} — {item['price']:.2f} {CURRENCIES.get(g.user['currency'], '€')}" for item in competitors),
            }
            record_price_change(
                db, g.user["id"], product_id,
                product["purchase_ttc"], product["sale_ttc"], product["vat_rate"],
                new_purchase, new_sale, data["vat_rate"],
            )
            record_product_changes(db, g.user["id"], product_id, g.user["name"] or g.user["email"], old_audit, new_audit)
            db.execute("""UPDATE products SET name = ?, product_code = ?, manufacturer = ?, supplier_ref = ?, barcode = ?, supplier = ?, purchase_price = ?, sale_price = ?,
                purchase_ttc = ?, sale_ttc = ?, vat_rate = ?, extra_cost_ttc = ?, quantity = ?, notes = ?, photo_path = ?,
                service_cost_ttc = ?, competitors_json = ?
                WHERE id = ? AND user_id = ?""",
                (data["name"], data["product_code"], data["manufacturer"], data["supplier_ref"], data["barcode"], data["supplier"], round(data["purchase"] / factor, 2),
                 round(data["sale"] / factor, 2), data["purchase"], data["sale"], data["vat_rate"], data["extra_costs"],
                 data["quantity"], data["notes"], photo_path, data["service_cost_ttc"],
                 json.dumps(competitors, ensure_ascii=False), product_id, g.user["id"]))
            save_competitor_brands(db, g.user["id"], competitors)
            db.commit()
            if product["photo_path"] and product["photo_path"] != photo_path:
                remove_product_photo(product["photo_path"])
            flash("La ligne a été mise à jour.", "success")
            return redirect(url_for("spreadsheet"))
    else:
        competitors = stored_competitors(product["competitors_json"])
    return render_template("new_product.html", product=product, suppliers=supplier_options(g.user["id"]),
                           competitor_brands=competitor_brand_options(g.user["id"]), competitors=competitors)


@app.get("/produit/<int:product_id>/historique")
@login_required
def product_history(product_id):
    db = get_db()
    product = db.execute(
        "SELECT id, name FROM products WHERE id = ? AND user_id = ?",
        (product_id, g.user["id"]),
    ).fetchone()
    if product is None:
        abort(404)
    activity_rows = db.execute(
        "SELECT * FROM product_change_log WHERE product_id = ? AND user_id = ? ORDER BY changed_at DESC",
        (product_id, g.user["id"]),
    ).fetchall()
    history = []
    for event in activity_rows:
        try:
            changes = json.loads(event["changes_json"])
        except (TypeError, json.JSONDecodeError):
            changes = {}
        for label, values in changes.items():
            history.append({
                "changed_at": event["changed_at"], "actor": event["actor_name"] or "—",
                "field": label, "old": values.get("old", "—"), "new": values.get("new", "—"),
            })
    # Keep displaying price edits made by older versions of Nombro.
    cutoff = min((event["changed_at"] for event in activity_rows), default="")
    legacy_query = "SELECT * FROM price_history WHERE product_id = ? AND user_id = ?"
    legacy_params = [product_id, g.user["id"]]
    if cutoff:
        legacy_query += " AND changed_at < ?"
        legacy_params.append(cutoff)
    legacy_rows = db.execute(legacy_query + " ORDER BY changed_at DESC", legacy_params).fetchall()
    currency_symbol = CURRENCIES.get(g.user["currency"], "€")
    for event in legacy_rows:
        for field, old_value, new_value in (
            ("Prix d’achat TTC", event["old_purchase_ttc"], event["new_purchase_ttc"]),
            ("Prix de vente TTC", event["old_sale_ttc"], event["new_sale_ttc"]),
            ("TVA", event["old_vat_rate"], event["new_vat_rate"]),
        ):
            suffix = " %" if field == "TVA" else f" {currency_symbol}"
            history.append({
                "changed_at": event["changed_at"], "actor": "—", "field": field,
                "old": f"{old_value:.2f}{suffix}", "new": f"{new_value:.2f}{suffix}",
            })
    history.sort(key=lambda item: item["changed_at"], reverse=True)
    return render_template("product_history.html", product=product, history=history)


def import_cell_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).strip()


def read_excel_products(content):
    from openpyxl import load_workbook
    import unicodedata

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    headers = next(rows, None)
    if not headers:
        workbook.close()
        raise ValueError("Le fichier Excel ne contient pas de tableau.")

    aliases = {
        "produit": "Produit", "nom": "Produit", "nom du produit": "Produit", "name": "Produit", "product": "Produit", "product name": "Produit",
        "code produit": "Code produit", "reference": "Code produit", "sku": "Code produit",
        "fabricant": "Fabricant", "manufacturer": "Fabricant", "marque": "Fabricant", "brand": "Fabricant",
        "ref fou": "Ref Fou", "réf fou": "Ref Fou", "ref fournisseur": "Ref Fou", "reference fournisseur": "Ref Fou", "supplier reference": "Ref Fou", "vendor part number": "Ref Fou",
        "code barres": "Code-barres", "code barre": "Code-barres", "barcode": "Code-barres", "ean": "Code-barres",
        "fournisseur": "Fournisseur", "supplier": "Fournisseur", "vendor": "Fournisseur",
        "achat ttc": "Achat TTC", "pa ttc": "Achat TTC", "prix achat ttc": "Achat TTC", "prix d achat ttc": "Achat TTC", "purchase ttc": "Achat TTC", "purchase price": "Achat TTC", "purchase price incl tax": "Achat TTC",
        "vente ttc": "Vente TTC", "pv ttc": "Vente TTC", "prix vente ttc": "Vente TTC", "prix de vente ttc": "Vente TTC", "sale ttc": "Vente TTC", "selling price": "Vente TTC", "sale price incl tax": "Vente TTC",
        "achat ht": "Achat HT", "pa ht": "Achat HT", "prix achat ht": "Achat HT", "prix d achat ht": "Achat HT", "purchase ht": "Achat HT", "purchase price excl tax": "Achat HT",
        "vente ht": "Vente HT", "pv ht": "Vente HT", "prix vente ht": "Vente HT", "prix de vente ht": "Vente HT", "sale ht": "Vente HT", "sale price excl tax": "Vente HT",
        "tva": "TVA %", "tva %": "TVA %", "vat": "TVA %", "vat %": "TVA %",
        "frais ttc": "Frais TTC", "frais annexes ttc": "Frais TTC", "extra costs": "Frais TTC",
        "prestation incluse ttc": "Prestation incluse TTC", "service cost ttc": "Prestation incluse TTC",
        "quantite": "Quantité", "quantity": "Quantité", "qty": "Quantité",
        "notes": "Notes", "description": "Notes",
    }

    def canonical(value):
        normalized = unicodedata.normalize("NFKD", import_cell_text(value)).encode("ascii", "ignore").decode().lower()
        for punctuation in "_().’'-":
            normalized = normalized.replace(punctuation, " ")
        normalized = " ".join(normalized.split())
        return aliases.get(normalized)

    mapped_headers = [canonical(header) for header in headers]
    mapped = set(mapped_headers)
    if "Produit" not in mapped or not ("Achat TTC" in mapped or "Achat HT" in mapped) or not ("Vente TTC" in mapped or "Vente HT" in mapped):
        workbook.close()
        raise ValueError("Colonnes Excel requises : Produit et prix d’achat/vente TTC ou HT. TVA et quantité sont facultatives.")

    records = []
    for index, values in enumerate(rows, start=2):
        if index > 10_001:
            workbook.close()
            raise ValueError("Le fichier Excel est limité à 10 000 lignes.")
        if not values or not any(value is not None for value in values):
            continue
        record = {}
        for header, value in zip(mapped_headers, values):
            if header and header not in record:
                record[header] = import_cell_text(value)
        records.append(record)
    workbook.close()
    return records


@app.route("/produits/import.csv", methods=["GET", "POST"])
@login_required
def import_products():
    if request.method == "POST" and request.form.get("action") == "confirm":
        stage_id = session.pop("product_import_stage", "") or session.pop("csv_import_stage", "")
        staged_path = INSTANCE_DIR / "imports" / f"{stage_id}.json"
        if not stage_id or not staged_path.is_file():
            flash("L’aperçu d’import a expiré. Sélectionnez à nouveau votre fichier.", "error")
            return redirect(url_for("import_products"))
        try:
            rows = json.loads(staged_path.read_text(encoding="utf-8"))
        finally:
            staged_path.unlink(missing_ok=True)
        db = get_db()
        imported = 0
        existing_barcodes = {row["barcode"] for row in db.execute(
            "SELECT barcode FROM products WHERE user_id = ? AND barcode != ''", (g.user["id"],)).fetchall()}
        for row in rows:
            if row.get("barcode") and row["barcode"] in existing_barcodes:
                continue
            factor = 1 + row["vat_rate"] / 100
            cursor = db.execute("""INSERT INTO products
                (user_id, name, product_code, barcode, supplier, purchase_price, sale_price, purchase_ttc, sale_ttc,
                 vat_rate, extra_cost_ttc, service_cost_ttc, quantity, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (g.user["id"], row["name"], row["product_code"], row["barcode"], row["supplier"],
                 round(row["purchase_ttc"] / factor, 2), round(row["sale_ttc"] / factor, 2), row["purchase_ttc"],
                 row["sale_ttc"], row["vat_rate"], row["extra_cost_ttc"], row["service_cost_ttc"], row["quantity"], row["notes"],
                 datetime.utcnow().isoformat()))
            record_product_created(db, g.user["id"], cursor.lastrowid, {**row, "photo_path": "", "competitors": []})
            imported += 1
            if row.get("barcode"):
                existing_barcodes.add(row["barcode"])
        db.commit()
        flash(f"{imported} produit(s) importé(s). Les doublons de code-barres ont été ignorés.", "success")
        return redirect(url_for("spreadsheet"))

    if request.method == "POST":
        upload = request.files.get("file")
        extension = Path(upload.filename or "").suffix.lower() if upload else ""
        if not upload or extension not in {".csv", ".xlsx"}:
            flash("Choisissez un fichier CSV ou Excel (.xlsx).", "error")
            return redirect(url_for("import_products"))
        try:
            content = upload.stream.read(5_000_001)
            if len(content) > 5_000_000:
                raise ValueError("Le fichier dépasse la limite de 5 Mo.")
            if extension == ".csv":
                text_stream = io.StringIO(content.decode("utf-8-sig"), newline="")
                reader = csv.DictReader(text_stream, delimiter=";")
                required = {"Produit", "Code produit", "Code-barres", "Fournisseur", "Achat TTC", "Vente TTC", "TVA %", "Frais TTC", "Quantité"}
                if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                    raise ValueError("Les colonnes ne correspondent pas à un export CSV Nombro.")
                source_rows = reader
            else:
                try:
                    source_rows = read_excel_products(content)
                except ValueError:
                    raise
                except Exception as exc:
                    raise ValueError("Impossible de lire ce fichier Excel. Vérifiez qu’il s’agit d’un fichier .xlsx valide.") from exc
            valid, errors = [], []
            seen_barcodes = set()
            existing_barcodes = {row["barcode"] for row in get_db().execute(
                "SELECT barcode FROM products WHERE user_id = ? AND barcode != ''", (g.user["id"],)).fetchall()}
            for line, row in enumerate(source_rows, start=2):
                name = (row.get("Produit") or "").strip()
                vat_text = (row.get("TVA %") or "").strip()
                vat = parse_rate(vat_text) if vat_text else 20.0
                purchase = parse_price((row.get("Achat TTC") or "").strip())
                sale = parse_price((row.get("Vente TTC") or "").strip())
                if purchase is None and row.get("Achat HT"):
                    purchase_ht = parse_price(row["Achat HT"])
                    purchase = round(purchase_ht * (1 + vat / 100), 2) if purchase_ht is not None and vat is not None else None
                if sale is None and row.get("Vente HT"):
                    sale_ht = parse_price(row["Vente HT"])
                    sale = round(sale_ht * (1 + vat / 100), 2) if sale_ht is not None and vat is not None else None
                fees = parse_price((row.get("Frais TTC") or "0").strip())
                service_cost = parse_price((row.get("Prestation incluse TTC") or "0").strip())
                try:
                    quantity = int((row.get("Quantité") or "1").strip())
                    if not 1 <= quantity <= 1_000_000:
                        raise ValueError
                except ValueError:
                    quantity = None
                if not name or len(name) > 120 or None in (purchase, sale, vat, fees, service_cost, quantity):
                    errors.append(f"{'Row' if g.language == 'en' else 'Ligne'} {line}: {translate('nom, prix, TVA ou quantité invalide.')}")
                    continue
                candidate = {
                    "name": name,
                    "product_code": (row.get("Code produit") or "").strip(),
                    "manufacturer": (row.get("Fabricant") or "").strip(),
                    "supplier_ref": (row.get("Ref Fou") or "").strip(),
                    "barcode": (row.get("Code-barres") or "").strip(),
                    "supplier": (row.get("Fournisseur") or "").strip(),
                    "purchase_ttc": purchase, "sale_ttc": sale, "vat_rate": vat,
                    "extra_cost_ttc": fees, "quantity": quantity,
                    "service_cost_ttc": service_cost,
                    "notes": (row.get("Notes") or "").strip()[:2000],
                }
                if (len(candidate["product_code"]) > 80 or len(candidate["manufacturer"]) > 160
                    or len(candidate["supplier_ref"]) > 128 or len(candidate["barcode"]) > 128
                    or len(candidate["supplier"]) > 160):
                    errors.append(f"{'Row' if g.language == 'en' else 'Ligne'} {line}: {translate('Code produit, fabricant, référence fournisseur, code-barres ou fournisseur trop long.')}")
                    continue
                if candidate["barcode"] and (candidate["barcode"] in existing_barcodes or candidate["barcode"] in seen_barcodes):
                    errors.append(f"{'Row' if g.language == 'en' else 'Ligne'} {line}: {translate('code-barres déjà présent, ligne ignorée.')}")
                    continue
                valid.append(candidate)
                if candidate["barcode"]:
                    seen_barcodes.add(candidate["barcode"])
            if not valid:
                raise ValueError("Aucune ligne valide à importer.")
            stage_dir = INSTANCE_DIR / "imports"
            stage_dir.mkdir(exist_ok=True)
            old_stage = session.pop("product_import_stage", "") or session.pop("csv_import_stage", "")
            if old_stage:
                (stage_dir / f"{old_stage}.json").unlink(missing_ok=True)
            stage_id = secrets.token_hex(20)
            (stage_dir / f"{stage_id}.json").write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
            session["product_import_stage"] = stage_id
            return render_template("import_products.html", rows=valid, errors=errors)
        except (UnicodeDecodeError, csv.Error, ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
            flash(str(exc) or "Impossible de lire le fichier CSV.", "error")
    return render_template("import_products.html")


@app.post("/produit/<int:product_id>/supprimer")
@login_required
def delete_product(product_id):
    db = get_db()
    product = db.execute("SELECT photo_path FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"])).fetchone()
    cursor = db.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, g.user["id"]))
    db.commit()
    if cursor.rowcount:
        remove_product_photo(product["photo_path"] if product else "")
        flash("La ligne a été supprimée.", "success")
    else:
        abort(404)
    return redirect(url_for("spreadsheet"))


if __name__ == "__main__":
    from waitress import serve

    try:
        serve(app, host=app.config["HOST"], port=app.config["PORT"])
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"Le port {app.config['PORT']} est déjà utilisé. "
                "Nombro tourne peut-être déjà dans une autre fenêtre."
            ) from None
        raise
