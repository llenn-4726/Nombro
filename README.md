# Nombro

Application Flask pour suivre les prix et marges des produits. Chaque compte possède son catalogue privé.

## Lancer l'application

Tu peux double-cliquer sur **Nombro** sur le Bureau : le raccourci démarre le serveur dans Konsole et ouvre Firefox directement sur l'application. Laisse Konsole ouverte pendant l'utilisation ; `Ctrl+C` arrête le serveur. Si Nombro tourne déjà, un nouveau clic ouvre Firefox sans lancer un deuxième serveur.

Pour le lancer depuis un terminal :

```bash
cd "/home/llenn/Documents/Codex/2026-11-18/fai"
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Pour ce lancement manuel aussi, garde le terminal ouvert, puis ouvre Firefox sur http://localhost:5000. Une clé de session aléatoire est créée et conservée dans `instance/secret_key` ; tu peux aussi fournir `FLASK_SECRET_KEY`. Les sessions restent actives jusqu'à 30 jours. Les comptes et produits sont stockés dans `instance/plusvalue.sqlite3`.

## Sauvegarde automatique et restauration

Les archives Nombro incluent une copie cohérente de la base SQLite, les photos et la clé de session. Chaque archive est vérifiée (intégrité SQLite et empreintes des fichiers), créée de façon atomique et conservée 30 jours. Au démarrage, Nombro détecte une base absente ou corrompue et restaure la dernière archive valide. Si seules des photos référencées manquent, elles sont récupérées sans remplacer la base actuelle. Les fichiers précédents sont gardés dans `instance/recovery/`.

Pour installer la sauvegarde quotidienne sur le PC qui héberge Nombro (par exemple le nouveau PC Linux), lance d’abord Nombro une fois pour initialiser sa base si c’est une nouvelle installation, arrête-le, puis lance depuis le dossier du projet :

```bash
bash scripts/install-backup-timer.sh
```

Choisis un dossier de sauvegarde accessible à ce PC. Pour survivre à une panne ou à la perte de ce PC, indique un dossier de partage réseau ou un disque externe et confirme qu’il doit être monté. Le minuteur refusera alors d’écrire sur le disque local si le partage n’est pas monté. La sauvegarde s’exécute tous les jours à 13 h, selon l’heure locale. L’ordinateur doit être allumé à cette heure ; `Persistent=true` lance la sauvegarde au prochain démarrage si l’horaire a été manqué.

Le dossier choisi est enregistré dans `backup.env` à côté de `app.py`, afin que le chemin soit encore connu si le dossier `instance/` est endommagé. On peut le modifier manuellement, par exemple `NOMBRO_BACKUP_DIR="/mnt/nombro-backup"`, puis redémarrer le minuteur :

```bash
systemctl --user restart nombro-backup.timer
systemctl --user list-timers nombro-backup.timer
journalctl --user -u nombro-backup.service -n 20
```

Pour migrer Nombro sur un autre ordinateur, copie le projet et le dossier `instance/` (qui contient la base, les photos et la clé), installe les dépendances comme décrit plus haut, puis lance l’installateur du minuteur sur ce nouvel ordinateur. Une archive de secours peut être restaurée manuellement, application arrêtée, avec :

```bash
.venv/bin/python nombro_backup.py restore /chemin/vers/nombro-backup-AAAAmmjj-HHMMSS.zip
```

La restauration manuelle conserve l’ancienne base et les anciennes photos dans `instance/recovery/`. Pour arrêter la sauvegarde planifiée : `systemctl --user disable --now nombro-backup.timer`.

## Grille de prix et calculs

- Les prix d'achat, de vente et les frais sont saisis TTC.
- HT = TTC ÷ (1 + taux de TVA).
- Marge en valeur = prix de vente HT − prix d’achat HT.
- Marge en pourcentage = marge en valeur ÷ prix de vente HT × 100.
- Coefficient = prix de vente TTC ÷ prix d’achat HT.
- Marge totale = marge en valeur × quantité.

Les frais annexes restent affichés séparément et ne sont pas inclus dans ces formules de marge. Les fiches créées avec l'ancienne version sont conservées et reprises comme des prix HT avec une TVA par défaut de 20 %.

Le tableau de bord est une page récapitulative avec les indicateurs et les produits en cartes. La page **Grille tableur** présente le catalogue sous forme de feuille large : code produit, code-barres, fournisseur, achat HT, vente HT, TVA, frais HT et quantité. Les cellules TTC, marge en valeur, marge en pourcentage et coefficient se recalculent aussitôt ; chaque ligne est enregistrée quand on quitte une cellule. La grille comprend recherche, tri, filtres de rentabilité et export CSV.

La devise peut être réglée dans **Paramètres** ou depuis la grille (EUR, USD, GBP, RUB, JPY, CHF, CAD). Cela change l'unité des montants sans convertir les valeurs existantes. Le champ code-barres accepte la saisie clavier ou un scanner qui agit comme un clavier.
