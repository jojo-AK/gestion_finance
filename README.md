# 💰 Finance Perso

> Application web de gestion financière personnelle — locale, sans connexion internet, développée en Python.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=flat&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-41%2F41%20✅-10b981?style=flat)
![Status](https://img.shields.io/badge/Status-Production-10b981?style=flat)

---

## 📌 À propos

**Finance Perso** est une application de gestion financière personnelle pensée et développée from scratch.

Elle repose sur un **moteur financier basé sur un ledger** (journal de transactions immuable) — le même principe utilisé dans les systèmes bancaires — garantissant l'intégrité et la traçabilité complète de toutes les opérations.

L'application tourne entièrement en local. Aucune donnée ne quitte votre machine.

---

## ✨ Fonctionnalités

| Module | Description |
|---|---|
| 🏠 **Tableau de bord** | Vue globale : soldes, budget du jour, alertes automatiques, dernières opérations |
| 📥 **Revenus** | Répartition automatique (%) ou manuelle (montants directs) vers réserve et budget |
| 📤 **Dépenses** | Choix de la source : budget semaine, réserve directe, ou automatique (budget → réserve) |
| 📅 **Budget hebdomadaire** | Planning sur 7 jours avec report automatique du reste journalier (carry) |
| 🏦 **Réserve** | Alimentation directe, retrait, ajustement à un solde précis, historique complet |
| 🤝 **Prêts** | Prêts donnés/reçus avec historique des remboursements, date, note, statut automatique |
| 📊 **Statistiques** | 3 onglets : semaine, mois, tendance 6 mois — graphiques Chart.js |
| 📋 **Historique** | Journal complet filtrable par date, type et catégorie |

---

## 🧠 Logique financière

L'application implémente un système de comptabilité par entrées doubles simplifié :

```
Revenu
  ├──► Réserve (épargne)
  └──► Budget semaine
            ├── Planification journalière (÷7, modifiable)
            ├── Reste du jour → reporté automatiquement au lendemain
            └── Dépenses (3 modes : auto / budget / réserve)
                  ├── Budget semaine d'abord (mode auto)
                  ├── Réserve en complément si insuffisant
                  └── Refusée si montant > budget + réserve
                            └── Reste de semaine → Réserve (clôture auto)
```

**Règles métier clés :**
- 🔒 La réserve ne peut **jamais** être négative
- 📊 Les soldes sont calculés dynamiquement depuis le ledger — jamais stockés directement
- 🔄 Toute opération est enregistrée de façon immuable dans le ledger
- ⚡ Alertes automatiques à 60%, 80% et 100% du budget journalier
- 🔁 Migration automatique de la base au démarrage — les données sont toujours préservées

---

## 🛠️ Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python 3 + Flask |
| Base de données | SQLite (fichier local, migration automatique) |
| Templating | Jinja2 (filtres personnalisés : `\|cfa`, `\|tojson`) |
| Graphiques | Chart.js 4.4 (CDN) |
| Frontend | HTML5 + CSS3 + JavaScript vanilla |
| Monnaie | Franc CFA (FCFA) avec séparateurs d'espaces insécables |
| Tests | Script tests.py — 41 tests automatiques |

---

## 🚀 Installation et lancement

### Prérequis
- Python 3.8+ — [télécharger ici](https://www.python.org)
- Git

### Cloner le projet
```bash
git clone https://github.com/jojo-AK/gestion_finance.git
cd gestion_finance
```

### Installer les dépendances
```bash
pip install flask
```

### Lancer l'application

**Windows** — double-cliquer sur `lancer.bat`

**Mac / Linux :**
```bash
chmod +x lancer.sh
./lancer.sh
```

**Manuellement :**
```bash
python app.py
```

Puis ouvrir dans le navigateur : **http://127.0.0.1:5000**

---

## 🧪 Lancer les tests

```bash
python tests.py
```

Le script vérifie automatiquement tous les modules sur une base temporaire sans toucher à `finance.db` :

```
✅ PASS  Formatage FCFA (5 tests)
✅ PASS  Base de données (9 tests)
✅ PASS  Moteur financier — Ledger (4 tests)
✅ PASS  Logique des dépenses (6 tests)
✅ PASS  Budget hebdomadaire et report journalier (3 tests)
✅ PASS  Prêts et remboursements (3 tests)
✅ PASS  Routes Flask — pages accessibles (8 tests)
✅ PASS  Intégrité du ledger (3 tests)

🎉 Tous les tests passent — 41/41
```

---

## 📁 Structure du projet

```
gestion_finance/
├── app.py                    # Application principale (routes + moteur financier)
├── tests.py                  # Script de tests automatiques (41 tests)
├── requirements.txt          # Dépendances Python
├── lancer.bat                # Lancement rapide Windows
├── lancer.sh                 # Lancement rapide Mac/Linux
├── README.md
└── templates/
    ├── base.html             # Template de base + navigation + styles dark mode
    ├── index.html            # Tableau de bord + alertes dynamiques
    ├── revenu.html           # Saisie des revenus (mode auto et manuel)
    ├── depense.html          # Saisie des dépenses (choix de source)
    ├── budget.html           # Budget hebdomadaire + planning journalier
    ├── reserve.html          # Gestion directe de la réserve
    ├── prets.html            # Prêts, remboursements et historique
    ├── stats.html            # Statistiques et graphiques Chart.js
    └── historique.html       # Journal complet filtrable
```

---

## 🗄️ Architecture de la base de données

Le système repose sur une table centrale **`ledger`** (journal des transactions) :

```
ledger          → toutes les opérations financières (immuable)
weekly_budgets  → budgets hebdomadaires (lundi → dimanche)
daily_budgets   → planification journalière + carry (report) + spent
categories      → 8 catégories de dépenses avec couleur et icône
loans           → prêts actifs et clôturés (given/received)
loan_payments   → historique des remboursements avec date et note
```

Les soldes ne sont **jamais stockés** — ils sont recalculés dynamiquement :

```
solde = Σ(entrées vers ce compte) − Σ(sorties depuis ce compte)
```

La base se **migre automatiquement** au démarrage si des colonnes manquent — tes données ne sont jamais perdues.

---

## 🗺️ Roadmap

- [x] Moteur financier basé sur ledger (principe bancaire)
- [x] Budget hebdomadaire avec report journalier automatique
- [x] Statistiques et graphiques Chart.js (semaine, mois, 6 mois)
- [x] Alertes automatiques budget journalier (60% / 80% / 100%)
- [x] Gestion complète des prêts et remboursements avec historique
- [x] Monnaie FCFA avec formatage espaces insécables
- [x] Choix de la source de dépense (auto / budget / réserve)
- [x] Page Réserve dédiée (alimentation, retrait, ajustement)
- [x] Mode manuel pour les revenus (saisie directe des montants)
- [x] Scripts de lancement rapide (lancer.bat / lancer.sh)
- [x] Tests automatiques — 41/41 ✅
- [x] Migration automatique de la base de données
- [ ] Export PDF du résumé mensuel
- [ ] Plafonds de dépenses par catégorie
- [ ] Application mobile

---

## 👤 Auteur

**Joseph** — Étudiant en informatique (IA/BIG DATA)

🔗 [github.com/jojo-AK](https://github.com/jojo-AK)

---

## 📄 Licence

Ce projet est sous licence MIT.