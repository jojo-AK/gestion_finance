# jofinance

> Application web de gestion financière personnelle — locale, sans connexion internet, développée en Python/Flask.

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=flat&logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-CDN-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-41%2F41%20✅-10b981?style=flat)
![Status](https://img.shields.io/badge/Status-Production-10b981?style=flat)

---

## À propos

**jofinance** est une application de gestion financière personnelle pensée et développée from scratch.

Elle repose sur un **moteur financier basé sur un ledger** (journal de transactions immuable) — le même principe utilisé dans les systèmes bancaires — garantissant l'intégrité et la traçabilité complète de toutes les opérations.

L'application tourne entièrement en local. **Aucune donnée ne quitte votre machine.**

---

## Fonctionnalités

| Module | Route | Description |
|---|---|---|
| 🏠 **Dashboard** | `/` | Vue globale : soldes, budget du jour, alertes automatiques, dernières opérations, répartition par catégorie |
| 📥 **Revenus** | `/revenu` | Répartition automatique (%) ou manuelle (montants directs) vers réserve et budget |
| 📤 **Dépenses** | `/depense` | Source au choix : budget semaine, réserve, ou automatique (budget → réserve en complément) |
| 📅 **Budget** | `/budget` | Planning sur 7 jours, navigation entre semaines, report journalier (carry), notes par jour, clôture manuelle |
| 🏦 **Réserve** | `/reserve` | Alimentation directe, retrait, ajustement à un solde précis, historique complet |
| 🤝 **Prêts** | `/prets` | Prêts donnés/reçus, historique des remboursements partiels, statut automatique |
| 📊 **Statistiques** | `/stats` | 3 onglets : semaine / mois / tendance 6 mois — graphiques Chart.js dynamiques |
| 📋 **Historique** | `/historique` | Journal filtrable (mois, type, catégorie, mot-clé), actions modifier/supprimer, export CSV |
| 📈 **Bilan mensuel** | `/bilan` | 4 KPIs, comparaison mois précédent, répartition catégories, taux d'épargne |
| 🎯 **Objectifs** | `/objectifs` | Objectifs d'épargne avec barre de progression, countdown, calcul épargne/semaine nécessaire |
| 🔄 **Récurrentes** | `/recurrentes` | Dépenses automatiques (quotidiennes/hebdo/mensuelles), exécution auto au chargement du dashboard |
| 🗂️ **Catégories** | `/categories` | Création/édition/suppression, icône, couleur, plafond hebdomadaire avec alertes 80%/100% |
| ✏️ **Modifier** | `/transaction/modifier/<id>` | Édition d'une transaction existante (montant, description, catégorie, date) |

---

## Interface

- **Sidebar fixe** (desktop) avec navigation groupée par section
- **Menu hamburger** sur mobile (slide-in + overlay)
- **Mode clair / Mode sombre** — toggle persistant via `localStorage`, activé en bas de la sidebar
- Police **Plus Jakarta Sans** (Google Fonts)
- Cartes glassmorphism avec coins arrondis, barres de progression 24px avec dégradés
- Couleurs sémantiques : Bleu (budget), Émeraude (réserve), Rouge (dépenses/dettes), Amber (alertes)

---

## Logique financière

```
Revenu
  ├──► Réserve (épargne)
  └──► Budget semaine
            ├── Planification journalière (÷7, modifiable par jour)
            ├── Carry : reste du jour → reporté automatiquement au lendemain
            └── Dépenses (3 modes)
                  ├── auto   : budget d'abord, réserve en complément
                  ├── budget : budget semaine uniquement
                  └── reserve: réserve uniquement
                        └── Clôture semaine : reste → Réserve
```

**Règles métier clés :**
- La réserve ne peut **jamais** être négative
- Les soldes sont calculés **dynamiquement** depuis le ledger — jamais stockés directement
- Toute opération est enregistrée de façon **immuable** dans le ledger
- Alertes automatiques à **80% et 100%** du plafond hebdomadaire par catégorie
- Les dépenses récurrentes s'exécutent **automatiquement** à chaque chargement du dashboard
- Migration automatique de la base au démarrage — les données sont toujours préservées

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python 3 + Flask |
| Base de données | SQLite (fichier local, migration automatique) |
| Templating | Jinja2 (filtres personnalisés : `\|cfa`, `\|tojson`) |
| Graphiques | Chart.js 4.4 (CDN) |
| CSS | Tailwind CSS CDN (dark mode `class`, config custom) |
| Police | Plus Jakarta Sans (Google Fonts) |
| JavaScript | Vanilla JS (pas de framework) |
| Monnaie | Franc CFA (FCFA) — formatage espaces insécables |
| Tests | `tests.py` — 41 tests automatiques |

---

## Installation

### Prérequis
- Python 3.8+
- Git

### Cloner et lancer

```bash
git clone https://github.com/jojo-AK/gestion_finance.git
cd gestion_finance
pip install flask
```

**Windows** — double-cliquer sur `lancer.bat`

**Mac / Linux :**
```bash
chmod +x lancer.sh && ./lancer.sh
```

**Manuellement :**
```bash
python app.py
```

Ouvrir dans le navigateur : **http://127.0.0.1:5000**

---

## Tests

```bash
python tests.py
```

Le script vérifie tous les modules sur une base temporaire sans toucher à `finance.db` :

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

## Structure du projet

```
jofinance/
├── app.py                    # Application principale (routes + moteur financier)
├── tests.py                  # Script de tests automatiques (41 tests)
├── finance.db                # Base SQLite (générée au premier lancement)
├── requirements.txt          # Dépendances Python
├── lancer.bat                # Lancement rapide Windows
├── lancer.sh                 # Lancement rapide Mac/Linux
├── README.md
└── templates/
    ├── base.html             # Layout sidebar + dark/light mode + design system
    ├── index.html            # Dashboard : KPIs, actions rapides, alertes
    ├── revenu.html           # Revenus : mode auto (%) et manuel (montants)
    ├── depense.html          # Dépenses : prévisualisation source en temps réel
    ├── budget.html           # Budget hebdo : navigation semaines + carry + notes
    ├── reserve.html          # Réserve : alimenter / retirer / ajuster
    ├── prets.html            # Prêts : suivi remboursements partiels
    ├── stats.html            # Statistiques : 3 onglets + graphiques Chart.js
    ├── historique.html       # Historique : filtres + modifier/supprimer + export CSV
    ├── bilan.html            # Bilan mensuel : KPIs + comparaison + catégories
    ├── objectifs.html        # Objectifs d'épargne : progression + calcul hebdo
    ├── recurrentes.html      # Dépenses récurrentes : pause / activation / suppression
    ├── categories.html       # Catégories : couleur, icône, plafond hebdo
    └── modifier_transaction.html  # Édition d'une transaction existante
```

---

## Architecture de la base de données

Le système repose sur une table centrale **`ledger`** (journal immuable) :

```
ledger              → toutes les opérations financières (source, destination, montant, type)
weekly_budgets      → budgets hebdomadaires (lundi → dimanche), flag closed
daily_budgets       → planification journalière + carry (report) + note
categories          → catégories de dépenses (nom, icône, couleur)
category_budgets    → plafonds hebdomadaires par catégorie
loans               → prêts actifs et clôturés (given/received)
loan_payments       → remboursements avec date et note
savings_goals       → objectifs d'épargne (cible, deadline)
recurring_expenses  → dépenses automatiques (fréquence, next_date, active)
```

Les soldes ne sont **jamais stockés** — ils sont recalculés dynamiquement :
```
solde(compte) = Σ(entrées vers ce compte) − Σ(sorties depuis ce compte)
```

---

## Roadmap

- [x] Moteur financier basé sur ledger (principe bancaire)
- [x] Budget hebdomadaire avec report journalier automatique (carry)
- [x] Statistiques et graphiques Chart.js (semaine, mois, 6 mois)
- [x] Alertes automatiques sur budget catégorie (80% / 100%)
- [x] Gestion complète des prêts et remboursements avec historique
- [x] Monnaie FCFA avec formatage espaces insécables
- [x] Choix de la source de dépense (auto / budget / réserve)
- [x] Page Réserve dédiée (alimentation, retrait, ajustement précis)
- [x] Mode manuel pour les revenus (saisie directe des montants)
- [x] Modification et suppression de transactions
- [x] Export CSV par mois
- [x] Bilan mensuel avec comparaison mois précédent
- [x] Objectifs d'épargne avec progression et calcul hebdomadaire
- [x] Dépenses récurrentes (auto-exécution quotidienne/hebdo/mensuelle)
- [x] Catégories personnalisables avec plafonds hebdomadaires
- [x] Navigation entre les semaines passées dans le budget
- [x] Notes par jour dans le planning budgétaire
- [x] Refonte visuelle complète — sidebar + mode sombre + design system
- [x] Tests automatiques — 41/41
- [x] Migration automatique de la base de données
- [ ] Export PDF du bilan mensuel
- [ ] Application mobile

---

## Auteur

**Joseph** — Étudiant en informatique (IA/BIG DATA)

[github.com/jojo-AK](https://github.com/jojo-AK)

---

## Licence

Ce projet est sous licence MIT.
