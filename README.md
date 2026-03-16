# 💰 Finance Perso

> Application de gestion financière personnelle — locale, sans connexion internet.

---

## 🚀 Lancement rapide

### Windows
Double-cliquer sur **`lancer.bat`**

L'application démarre et le navigateur s'ouvre automatiquement sur `http://127.0.0.1:5000`.

### Mac / Linux
```bash
chmod +x lancer.sh
./lancer.sh
```

### Lancement manuel
```bash
pip install flask      # une seule fois
python app.py
```
Puis ouvrir `http://127.0.0.1:5000` dans le navigateur.

---

## 📦 Fonctionnalités

| Module | Description |
|---|---|
| 🏠 Tableau de bord | Soldes, budget du jour, alertes, dernières opérations |
| 📥 Revenus | Répartition automatique (%) ou manuelle (montants directs) |
| 📤 Dépenses | Prélèvement intelligent : budget d'abord, réserve si besoin |
| 📅 Budget | Planning hebdomadaire avec report journalier automatique |
| 🏦 Réserve | Alimentation, retrait, ajustement direct du solde |
| 🤝 Prêts | Suivi des prêts donnés/reçus et remboursements |
| 📊 Statistiques | Graphiques semaine, mois, tendance 6 mois |
| 📋 Historique | Journal complet filtrable |

---

## 🧠 Logique financière

```
Revenu
  ├──► Réserve (épargne)
  └──► Budget semaine
            ├── Planification journalière (÷7, modifiable)
            ├── Reste du jour → reporté au lendemain
            └── Dépenses (budget d'abord → réserve si insuffisant)
                      └── Reste de semaine → Réserve (clôture)
```

**Règles clés :**
- La réserve ne peut jamais être négative
- Dépense impossible si montant > budget + réserve
- Tout est tracé dans un ledger immuable (journal des transactions)

---

## 🗃️ Données

Toutes les données sont dans **`finance.db`** (SQLite, créé automatiquement).

| Action | Opération |
|---|---|
| Sauvegarder | Copier `finance.db` |
| Réinitialiser | Supprimer `finance.db` |
| Migrer vers un autre PC | Copier tout le dossier |

---

## 📁 Structure du projet

```
finance-perso/
├── app.py                  ← Application principale
├── finance.db              ← Base de données (auto-créée)
├── requirements.txt        ← Dépendances Python
├── lancer.bat              ← Lancement rapide Windows
├── lancer.sh               ← Lancement rapide Mac/Linux
├── README.md               ← Ce fichier
└── templates/
    ├── base.html           ← Template de base + navigation
    ├── index.html          ← Tableau de bord
    ├── revenu.html         ← Saisie des revenus
    ├── depense.html        ← Saisie des dépenses
    ├── budget.html         ← Budget hebdomadaire
    ├── reserve.html        ← Gestion de la réserve
    ├── prets.html          ← Prêts et remboursements
    ├── stats.html          ← Statistiques et graphiques
    └── historique.html     ← Historique des transactions
```

---

## 🛠️ Stack technique

- **Python 3** + **Flask** — backend et logique métier
- **SQLite** — base de données locale
- **Jinja2** — templating HTML
- **Chart.js** — graphiques
- **Monnaie** — Franc CFA (FCFA)

---

## 📋 Livrables du projet

- `documentation_technique.docx` — Architecture, base de données, moteur financier
- `cahier_des_charges_final.docx` — Spécifications et règles métier

---

*Finance Perso v1.0 — Projet personnel*
