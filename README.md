# Mimosa

Petite application Flask pour suivre la rentabilité de produits. Chaque compte possède son catalogue privé. Les fiches calculent le bénéfice par produit et le taux de marge sur coût d'achat.

## Lancer l'application

```bash
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

Définissez une clé de session avant le lancement, puis démarrez Flask :

```bash
export FLASK_SECRET_KEY="une-cle-secrete-longue-et-aleatoire"
python app.py
```

Ouvrez ensuite http://127.0.0.1:5000 et créez un compte. Le formulaire demande votre nom, votre e-mail et votre mot de passe ; le numéro de téléphone est facultatif. Les données sont stockées dans `instance/plusvalue.sqlite3` pour conserver les comptes déjà créés.

## Grille de prix et calculs

- Les prix d'achat, de vente et les frais sont saisis TTC.
- HT = TTC ÷ (1 + taux de TVA).
- Bénéfice HT = vente HT − achat HT − frais HT, puis multiplié par la quantité.
- Taux de marge = bénéfice HT ÷ (achat HT + frais HT) × 100.

Les frais utilisent le même taux de TVA que le produit. Les fiches créées avec l'ancienne version sont conservées et reprises comme des prix HT avec une TVA par défaut de 20 %.

Le tableau de bord est une page récapitulative avec les indicateurs et les produits en cartes. La page **Grille tableur** présente le catalogue sous forme de feuille large : code produit, code-barres, fournisseur, achat HT, vente HT, TVA, frais HT et quantité. Les cellules TTC, bénéfice en montant et marge en pourcentage se recalculent aussitôt ; chaque ligne est enregistrée quand on quitte une cellule. La grille comprend recherche, tri, filtres de rentabilité et export CSV.

La devise peut être réglée dans **Mon profil** ou depuis la grille (EUR, USD, GBP, RUB, JPY, CHF, CAD). Cela change l'unité des montants sans convertir les valeurs existantes. Le champ code-barres accepte la saisie clavier ou un scanner qui agit comme un clavier.
