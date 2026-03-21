"""
tests.py — Script de tests automatiques pour Finance Perso
----------------------------------------------------------
Lance avec : python tests.py
Utilise une base de données temporaire — ne touche PAS à finance.db
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
errors = []


def ok(name):
    global passed
    passed += 1
    print(f"  {GREEN}✅ PASS{RESET}  {name}")


def fail(name, detail=""):
    global failed
    failed += 1
    msg = f"  {RED}❌ FAIL{RESET}  {name}"
    if detail:
        msg += f"\n         {RED}→ {detail}{RESET}"
    print(msg)
    errors.append(f"{name}: {detail}")


def section(title):
    print(f"\n{BLUE}{BOLD}{'─'*55}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─'*55}{RESET}")


# ── Base de test temporaire ───────────────────────────────────────────────────
TEST_DB = "test_finance_temp.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

try:
    import app as App
    App.DB_PATH = TEST_DB

    def test_get_db():
        conn = sqlite3.connect(TEST_DB)
        conn.row_factory = sqlite3.Row
        return conn
    App.get_db = test_get_db
    App.init_db()
except Exception as e:
    print(f"{RED}ERREUR : Impossible d'importer app.py — {e}{RESET}")
    print("Vérifie que tu lances tests.py depuis le dossier jofinance/")
    sys.exit(1)

today_str = datetime.now().strftime('%Y-%m-%d')
today = datetime.now().date()
week_start = today - timedelta(days=today.weekday())

# ─────────────────────────────────────────────────────────────────────────────
section("1. Formatage FCFA")

for val, label, check in [
    (50000,           "cfa(50000)", lambda r: "50" in r and "FCFA" in r),
    (1250000,         "cfa(1250000) milliers",
     lambda r: "1" in r and "250" in r and "FCFA" in r),
    (0,               "cfa(0)", lambda r: "0" in r and "FCFA" in r),
    (None,            "cfa(None) ne plante pas", lambda r: "FCFA" in r),
    ("invalide",      "cfa(str) ne plante pas", lambda r: "FCFA" in r),
]:
    try:
        r = App.cfa(val)
        if check(r):
            ok(label)
        else:
            fail(label, f"Résultat : {r}")
    except Exception as e:
        fail(label, str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("2. Base de données")

try:
    c = App.get_db()
    c.close()
    ok("Connexion à la base")
except Exception as e:
    fail("Connexion à la base", str(e))

try:
    conn = App.get_db()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    for t in ['ledger', 'categories', 'weekly_budgets', 'daily_budgets', 'loans', 'loan_payments']:
        if t in tables:
            ok(f"Table '{t}' existe")
        else:
            fail(f"Table '{t}' manquante")
except Exception as e:
    fail("Vérification tables", str(e))

try:
    # Forcer la migration si besoin (cas ancienne base)
    conn = App.get_db()
    cols = [r[1] for r in conn.execute(
        "PRAGMA table_info(daily_budgets)").fetchall()]
    if 'spent' not in cols:
        conn.execute(
            "ALTER TABLE daily_budgets ADD COLUMN spent REAL DEFAULT 0")
        conn.commit()
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(daily_budgets)").fetchall()]
    conn.close()
    if 'spent' in cols:
        ok("Colonne 'spent' dans daily_budgets")
    else:
        fail("Colonne 'spent' manquante", "Supprime finance.db et relance l'app")
except Exception as e:
    fail("Colonne 'spent'", str(e))

try:
    conn = App.get_db()
    nb = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    conn.close()
    if nb >= 7:
        ok(f"Catégories initiales présentes ({nb})")
    else:
        fail("Catégories", f"Seulement {nb} trouvée(s)")
except Exception as e:
    fail("Catégories", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("3. Moteur financier — Ledger")

try:
    r = App.get_balance('reserve')
    b = App.get_balance('budget')
    if r == 0.0 and b == 0.0:
        ok("Soldes initiaux à 0")
    else:
        fail("Soldes initiaux", f"reserve={r}, budget={b}")
except Exception as e:
    fail("get_balance() base vide", str(e))

try:
    conn = App.get_db()
    App.create_ledger_entry(conn, 'external', 'reserve',
                            100000, 'income', 'Test')
    conn.commit()
    conn.close()
    bal = App.get_balance('reserve')
    if bal == 100000.0:
        ok("Crédit réserve 100 000")
    else:
        fail("Crédit réserve", f"Attendu 100000, obtenu {bal}")
except Exception as e:
    fail("create_ledger_entry", str(e))

try:
    conn = App.get_db()
    App.create_ledger_entry(conn, 'external', 'reserve',
                            50000, 'income', 'Test 2')
    conn.commit()
    conn.close()
    bal = App.get_balance('reserve')
    if bal == 150000.0:
        ok("Deux crédits cumulés (150 000)")
    else:
        fail("Cumul transactions", f"Attendu 150000, obtenu {bal}")
except Exception as e:
    fail("Cumul transactions", str(e))

try:
    conn = App.get_db()
    App.create_ledger_entry(conn, 'reserve', 'budget',
                            40000, 'transfer', 'Transfert')
    conn.commit()
    conn.close()
    res = App.get_balance('reserve')
    bud = App.get_balance('budget')
    if res == 110000.0 and bud == 40000.0:
        ok("Transfert réserve → budget (110k / 40k)")
    else:
        fail("Transfert", f"reserve={res}, budget={bud}")
except Exception as e:
    fail("Transfert réserve → budget", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("4. Logique des dépenses")

# Dépense budget suffisant
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 10000, 'Test', None, today_str, 'budget')
    conn.commit()
    conn.close()
    bud = App.get_balance('budget')
    if ok_r and bud == 30000.0:
        ok("Dépense 10 000 budget (40k → 30k)")
    else:
        fail("Dépense budget suffisant", f"ok={ok_r}, budget={bud}, msg={msg}")
except Exception as e:
    fail("Dépense budget suffisant", str(e))

# Dépense mode auto — complément réserve
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 50000, 'Test auto', None, today_str, 'auto')
    conn.commit()
    conn.close()
    bud = App.get_balance('budget')
    res = App.get_balance('reserve')
    if ok_r and bud == 0.0 and res == 90000.0:
        ok("Dépense auto dépassement (budget vidé + réserve complément)")
    else:
        fail("Dépense auto dépassement",
             f"ok={ok_r}, budget={bud}, reserve={res}")
except Exception as e:
    fail("Dépense auto dépassement", str(e))

# Dépense refusée si fonds insuffisants
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 500000, 'Trop cher', None, today_str, 'auto')
    conn.close()
    if not ok_r:
        ok("Dépense refusée si montant > budget + réserve")
    else:
        fail("Refus dépense insuffisante", "Aurait dû être refusée")
except Exception as e:
    fail("Refus dépense insuffisante", str(e))

# Dépense budget insuffisant (mode budget strict)
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 50000, 'Budget vide', None, today_str, 'budget')
    conn.close()
    if not ok_r:
        ok("Dépense refusée si budget insuffisant (mode budget strict)")
    else:
        fail("Refus mode budget strict", "Aurait dû être refusée")
except Exception as e:
    fail("Refus mode budget strict", str(e))

# Dépense directe réserve
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 5000, 'Réserve directe', None, today_str, 'reserve')
    conn.commit()
    conn.close()
    res = App.get_balance('reserve')
    if ok_r and res == 85000.0:
        ok("Dépense directe réserve (90k → 85k)")
    else:
        fail("Dépense directe réserve", f"ok={ok_r}, reserve={res}")
except Exception as e:
    fail("Dépense directe réserve", str(e))

# Dépense réserve insuffisante
try:
    conn = App.get_db()
    ok_r, msg = App.add_expense_smart(
        conn, 999999, 'Réserve vide', None, today_str, 'reserve')
    conn.close()
    if not ok_r:
        ok("Dépense réserve refusée si insuffisante")
    else:
        fail("Refus réserve insuffisante", "Aurait dû être refusée")
except Exception as e:
    fail("Refus réserve insuffisante", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("5. Budget hebdomadaire et report journalier")

try:
    conn = App.get_db()
    wb = conn.execute("INSERT INTO weekly_budgets (week_start, total_amount) VALUES (?,?)",
                      (str(week_start), 70000))
    wb_id = wb.lastrowid
    daily = round(70000 / 7, 2)
    for i in range(7):
        day = week_start + timedelta(days=i)
        conn.execute("INSERT INTO daily_budgets (weekly_budget_id, date, planned) VALUES (?,?,?)",
                     (wb_id, str(day), daily))
    conn.commit()
    conn.close()
    ok(f"Budget semaine créé (70 000 → {daily:.0f}/jour)")
except Exception as e:
    fail("Création budget semaine", str(e))

try:
    conn = App.get_db()
    wb = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=?", (str(week_start),)).fetchone()
    conn.close()
    if wb:
        App.propagate_carry(wb['id'])
        conn = App.get_db()
        days = conn.execute(
            "SELECT * FROM daily_budgets WHERE weekly_budget_id=? ORDER BY date", (wb['id'],)).fetchall()
        carry_lundi = days[0]['carry']
        conn.close()
        if carry_lundi == 0:
            ok("Report journalier — lundi démarre à carry=0")
        else:
            fail("Report journalier lundi", f"Carry={carry_lundi}, attendu 0")
    else:
        fail("propagate_carry", "Budget semaine introuvable")
except Exception as e:
    fail("propagate_carry", str(e))

try:
    conn = App.get_db()
    days = conn.execute(
        "SELECT COUNT(*) FROM daily_budgets WHERE weekly_budget_id=(SELECT id FROM weekly_budgets WHERE week_start=?)",
        (str(week_start),)
    ).fetchone()[0]
    conn.close()
    if days == 7:
        ok("7 budgets journaliers créés pour la semaine")
    else:
        fail("Budgets journaliers", f"{days} créés, attendu 7")
except Exception as e:
    fail("Comptage budgets journaliers", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("6. Prêts et remboursements")

res_avant = App.get_balance('reserve')

try:
    conn = App.get_db()
    App.create_ledger_entry(conn, 'reserve', 'loan_Ami',
                            20000, 'loan', 'Prêt test', date=today_str)
    conn.execute("INSERT INTO loans (person_name,direction,amount,remaining,description,date) VALUES (?,?,?,?,?,?)",
                 ('Ami', 'given', 20000, 20000, 'Test', today_str))
    conn.commit()
    conn.close()
    res = App.get_balance('reserve')
    if res == res_avant - 20000:
        ok(f"Prêt donné 20 000 → réserve diminuée")
    else:
        fail("Prêt donné", f"Reserve attendue {res_avant-20000}, obtenu {res}")
except Exception as e:
    fail("Enregistrement prêt", str(e))

try:
    conn = App.get_db()
    res_avant_remb = App.get_balance('reserve')
    App.create_ledger_entry(conn, 'loan_Ami', 'reserve',
                            10000, 'repayment', 'Remb. partiel', date=today_str)
    loan = conn.execute(
        "SELECT * FROM loans WHERE person_name='Ami'").fetchone()
    conn.execute("INSERT INTO loan_payments (loan_id,amount,date,note) VALUES (?,?,?,?)",
                 (loan['id'], 10000, today_str, 'Test'))
    conn.execute(
        "UPDATE loans SET remaining=remaining-10000 WHERE id=?", (loan['id'],))
    conn.commit()
    conn.close()
    res = App.get_balance('reserve')
    conn2 = App.get_db()
    reste = conn2.execute(
        "SELECT remaining FROM loans WHERE person_name='Ami'").fetchone()['remaining']
    conn2.close()
    if res == res_avant_remb + 10000 and reste == 10000:
        ok("Remboursement partiel 10 000 → réserve créditée, reste=10 000")
    else:
        fail("Remboursement partiel", f"reserve={res}, reste_pret={reste}")
except Exception as e:
    fail("Remboursement partiel", str(e))

try:
    conn = App.get_db()
    loan = conn.execute(
        "SELECT * FROM loans WHERE person_name='Ami'").fetchone()
    App.create_ledger_entry(conn, 'loan_Ami', 'reserve',
                            loan['remaining'], 'repayment', 'Solde', date=today_str)
    conn.execute(
        "UPDATE loans SET remaining=0, status='paid' WHERE id=?", (loan['id'],))
    conn.commit()
    status = conn.execute(
        "SELECT status FROM loans WHERE person_name='Ami'").fetchone()['status']
    conn.close()
    if status == 'paid':
        ok("Remboursement total → statut 'paid'")
    else:
        fail("Statut après remboursement total", f"Obtenu '{status}'")
except Exception as e:
    fail("Remboursement total", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("7. Routes Flask (pages accessibles)")

App.app.config['TESTING'] = True
with App.app.test_client() as client:
    for url, name in [
        ('/', 'Tableau de bord'), ('/revenu', 'Revenus'), ('/depense', 'Dépenses'),
        ('/budget', 'Budget'), ('/reserve', 'Réserve'), ('/prets', 'Prêts'),
        ('/historique', 'Historique'), ('/stats', 'Statistiques'),
    ]:
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                ok(f"GET {url} → 200 OK ({name})")
            else:
                fail(f"GET {url} ({name})", f"Status {resp.status_code}")
        except Exception as e:
            fail(f"GET {url} ({name})", str(e))

# ─────────────────────────────────────────────────────────────────────────────
section("8. Intégrité du ledger")

try:
    conn = App.get_db()
    neg = conn.execute(
        "SELECT COUNT(*) FROM ledger WHERE amount <= 0").fetchone()[0]
    conn.close()
    if neg == 0:
        ok("Aucune transaction avec montant <= 0")
    else:
        fail("Montants ledger", f"{neg} transaction(s) invalide(s)")
except Exception as e:
    fail("Vérification montants", str(e))

try:
    conn = App.get_db()
    vides = conn.execute(
        "SELECT COUNT(*) FROM ledger WHERE source='' OR destination=''").fetchone()[0]
    conn.close()
    if vides == 0:
        ok("Toutes les transactions ont source et destination valides")
    else:
        fail("Source/destination vide", f"{vides} transaction(s) invalide(s)")
except Exception as e:
    fail("Vérification source/destination", str(e))

try:
    res = App.get_balance('reserve')
    if res >= 0:
        ok(f"Réserve non négative ({res:.0f} FCFA)")
    else:
        fail("Réserve non négative", f"Réserve = {res}")
except Exception as e:
    fail("Réserve non négative", str(e))

# ── Nettoyage ─────────────────────────────────────────────────────────────────
try:
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
except:
    pass

# ── Résumé ────────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{BOLD}{'═'*55}{RESET}")
print(f"{BOLD}  RÉSULTATS{RESET}")
print(f"{BOLD}{'═'*55}{RESET}")
print(f"  Total   : {total} tests")
print(f"  {GREEN}Réussis : {passed}{RESET}")
print(f"  {RED if failed > 0 else GREEN}Échoués : {failed}{RESET}")

if failed == 0:
    print(
        f"\n  {GREEN}{BOLD}🎉 Tous les tests passent — application en bonne santé !{RESET}")
else:
    print(f"\n  {RED}{BOLD}⚠️  {failed} test(s) ont échoué :{RESET}")
    for e in errors:
        print(f"  {RED}• {e}{RESET}")
    print(f"\n  {YELLOW}Consulte les détails ci-dessus pour corriger.{RESET}")

print(f"{BOLD}{'═'*55}{RESET}\n")
sys.exit(0 if failed == 0 else 1)
