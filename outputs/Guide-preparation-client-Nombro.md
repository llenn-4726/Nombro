# Guide de préparation — PC client Nombro

Ce guide concerne uniquement le PC qui utilise Nombro à distance. Le serveur Nombro doit déjà être installé et démarré sur un autre ordinateur.

## 1. Préparer le PC client

- Connecte le PC au même réseau local que le serveur (même Wi-Fi ou réseau Ethernet).
- Ouvre Firefox ou un autre navigateur récent.
- Demande l’adresse IP locale du PC serveur. Elle ressemble à `192.168.1.25`.
- Dans la barre d’adresse, saisis `http://ADRESSE-IP:5000`, en remplaçant `ADRESSE-IP` par l’adresse reçue. Exemple : `http://192.168.1.25:5000`.
- N’utilise pas `localhost` sur le PC client : cela désigne le PC client lui-même.

## 2. Se connecter

- Connecte-toi avec l’adresse e-mail et le mot de passe de ton compte Nombro.
- Les comptes et le catalogue sont ceux du serveur. Si le catalogue paraît vide, vérifie que tu es connecté au bon serveur et au bon compte.
- Pour garder la page à portée de main dans Firefox, ouvre Nombro puis appuie sur **Ctrl+D** pour l’ajouter aux marque-pages.

## 3. Utiliser le catalogue

- **Récapitulatif** affiche les produits sous forme de fiches.
- **Grille tableur** affiche les produits et permet de modifier les cellules.
- Dans la grille, quitte la cellule modifiée pour déclencher son enregistrement. Attends le message **« Toutes les modifications sont enregistrées »** avant de fermer la page.
- Pour créer un produit, utilise **Ajouter une ligne** et envoie le formulaire.

Les produits sont enregistrés sur le serveur et associés à ton compte. Tu peux retrouver le même catalogue depuis un autre appareil en ouvrant la même adresse et en utilisant le même compte.

## 4. Si le serveur est momentanément inaccessible

Lorsqu’une fiche produit est envoyée alors que le serveur n’est pas joignable, Nombro peut la garder temporairement dans le navigateur du PC client et la renvoyer automatiquement quand la connexion revient. Le formulaire affiche alors un message indiquant qu’elle est conservée sur cet ordinateur.

- Rétablis la connexion au réseau local et laisse Nombro ouvert pour que l’envoi automatique puisse reprendre.
- Vérifie que la fiche apparaît dans la grille après le retour de la connexion.
- Ne vide pas les données du navigateur et ne supprime pas son profil avant que la fiche ait été transmise.

Les modifications de lignes déjà présentes dans la grille doivent être envoyées au serveur. Si le message d’enregistrement signale une erreur, reconnecte-toi au réseau et vérifie que la modification est bien enregistrée avant de fermer la page.

## 5. Télécharger une copie du catalogue depuis le client

Dans **Paramètres**, section **Sauvegarde**, utilise **Télécharger la sauvegarde** pour enregistrer un fichier JSON sur le PC client. Garde ce fichier dans un endroit sûr. Il s’agit d’une copie téléchargée depuis le navigateur ; les sauvegardes automatiques quotidiennes sont gérées sur le PC serveur.

## Dépannage rapide

1. Vérifie que le PC client et le serveur sont sur le même réseau.
2. Vérifie l’adresse IP et le port `5000` dans l’adresse du navigateur.
3. Vérifie que tu as saisi `http://` et non `https://`.
4. Recharge la page avec **Ctrl+F5**.
5. Si la page reste inaccessible, le serveur doit être démarré sur l’autre PC. Contacte la personne qui le gère.
