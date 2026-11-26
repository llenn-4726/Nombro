# Présenter Nombro à son supérieur

## Pitch d’ouverture

> Nombro est un outil de suivi des prix et de la rentabilité des produits. Il rassemble dans une même interface les prix d’achat et de vente, la TVA, les frais et les prix concurrents. Les calculs de marge sont mis à jour automatiquement, ce qui permet de consulter rapidement la rentabilité de chaque produit.

## Le besoin auquel répond l’application

Le suivi des prix et des marges demande souvent de consulter plusieurs informations et de refaire des calculs. Nombro regroupe ces données dans un catalogue consultable et modifiable depuis un navigateur, afin de faciliter le suivi et la comparaison des produits.

## Fonctionnalités principales

- **Grille de prix** : produits, codes, fournisseur, prix, TVA, frais et quantités réunis dans un tableau modifiable.
- **Calcul automatique** : montants HT, marge unitaire et totale, taux de marge et coefficient recalculés à partir des valeurs saisies.
- **Suivi concurrentiel** : comparaison des prix concurrents, avec possibilité de conserver leurs liens et remarques.
- **Fiches produit** : consultation des informations, prix, photo et concurrence de chaque produit.
- **Recherche et filtres** : accès plus rapide aux lignes du catalogue et repérage des produits selon leur rentabilité.
- **Import et export** : prise en charge de fichiers CSV et Excel, avec export des données.
- **Sauvegardes** : téléchargement d’une copie du catalogue depuis les paramètres et sauvegardes automatiques quotidiennes configurées sur le PC serveur.

## Démonstration conseillée

1. Ouvrir Nombro dans le navigateur et présenter le récapitulatif du catalogue.
2. Passer à **Grille tableur** pour montrer les produits et les champs de prix.
3. Modifier un prix ou un taux de TVA, puis quitter la cellule pour illustrer le recalcul et l’enregistrement.
4. Ouvrir une **fiche produit** pour présenter les détails, la photo et les prix concurrents.
5. Montrer les options d’import/export et la section de sauvegarde dans les paramètres.

## Fonctionnement côté utilisateur

Nombro s’ouvre dans un navigateur sur le réseau local de l’entreprise. L’utilisateur se connecte avec son compte. Les produits du compte sont enregistrés sur le PC qui héberge le serveur et peuvent être consultés depuis un autre ordinateur du même réseau.

Les modifications de la grille sont envoyées au serveur lorsqu’on quitte la cellule. L’interface affiche un message d’enregistrement. Une nouvelle fiche créée en cas de coupure peut rester temporairement dans le navigateur et être renvoyée lorsque le serveur redevient accessible.

## Bénéfices attendus

- Réduire les calculs manuels de prix et de marge.
- Consulter les informations produit au même endroit.
- Repérer plus facilement les produits dont la rentabilité mérite une vérification.
- Faciliter la comparaison avec les prix du marché.
- Partager le même catalogue entre plusieurs postes connectés au réseau local.

## Points de fonctionnement à préciser

- L’accès depuis un poste client nécessite que le serveur soit allumé et joignable sur le réseau local.
- L’application est conçue ici pour un usage sur le réseau local ; cette configuration ne correspond pas à un accès depuis Internet.
- Les sauvegardes automatiques sont exécutées sur le PC serveur, chaque jour à 13 h selon l’heure locale, si le PC est allumé. Pour mieux protéger les données contre la panne du serveur, le dossier de sauvegarde peut être placé sur un partage réseau ou un disque externe.
- L’application utilise actuellement une connexion HTTP sur le réseau local. Si un accès depuis l’extérieur ou une protection renforcée est nécessaire, la configuration devra évoluer avant cet usage.

## Conclusion proposée

> Nombro apporte une vue claire et centralisée des prix et de la rentabilité du catalogue. Il automatise les calculs et facilite la consultation depuis plusieurs postes du réseau local. La prochaine étape pourrait être de valider son usage sur un catalogue réel et de confirmer les besoins en matière d’accès et de sauvegarde.
