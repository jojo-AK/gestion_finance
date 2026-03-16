# 💰 Application de Gestion Financière Personnelle

Application locale basée sur Python + Flask + SQLite.  
Aucune connexion internet requise. Vos données restent sur votre machine.

---

## 🚀 Lancement rapide

### 1. Installer Python (si pas déjà fait)
Télécharger sur https://www.python.org (version 3.8+)

### 2. Installer Flask
Ouvrir un terminal dans ce dossier, puis :

```bash
pip install flask
```

### 3. Lancer l'application

```bash
python app.py
```

### 4. Ouvrir dans le navigateur
Aller sur : **http://127.0.0.1:5000**

---

## 📦 Fonctionnalités

| Module | Fonctionnalité |
|--------|---------------|
| 🏠 Tableau de bord | Vue générale, soldes, résumé mensuel |
| 📥 Revenus | Ajout revenu + répartition automatique réserve/budget |
| 📤 Dépenses | Saisie par catégorie, depuis réserve ou budget |
| 📅 Budget | Budget hebdomadaire + planning journalier automatique |
| 🤝 Prêts | Suivi des prêts donnés/reçus + remboursements |
| 📋 Historique | Toutes les transactions avec filtres |

---

## 🗃️ Base de données

Le fichier `finance.db` est créé automatiquement au premier lancement.  
Il contient toutes vos données. Faites-en une copie régulière pour sauvegarde.

---

## 🔧 Commandes utiles

```bash
# Lancer normalement
python app.py

# Lancer sur un port différent (si 5000 est occupé)
# Modifier la dernière ligne de app.py : port=5001
```
