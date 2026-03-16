from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "finance_app_secret"
DB_PATH = "finance.db"

# ─── BASE DE DONNÉES ──────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        source TEXT NOT NULL,
        destination TEXT NOT NULL,
        amount REAL NOT NULL,
        type TEXT NOT NULL,
        description TEXT,
        category_id INTEGER,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        color TEXT DEFAULT '#6366f1',
        icon TEXT DEFAULT '💰'
    );

    CREATE TABLE IF NOT EXISTS weekly_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start TEXT NOT NULL UNIQUE,
        total_amount REAL NOT NULL,
        closed INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS daily_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        weekly_budget_id INTEGER NOT NULL,
        date TEXT NOT NULL UNIQUE,
        planned REAL NOT NULL,
        carry REAL DEFAULT 0,
        FOREIGN KEY (weekly_budget_id) REFERENCES weekly_budgets(id)
    );

    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        person_name TEXT NOT NULL,
        direction TEXT NOT NULL,
        amount REAL NOT NULL,
        remaining REAL NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS loan_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        date TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY (loan_id) REFERENCES loans(id)
    );
    """)

    c.execute("SELECT COUNT(*) FROM accounts")
    if c.fetchone()[0] == 0:
        c.executescript("""
        INSERT INTO accounts (name, type) VALUES ('Réserve', 'reserve');
        INSERT INTO accounts (name, type) VALUES ('Budget Semaine', 'budget');
        INSERT INTO categories (name, color, icon) VALUES ('Alimentation', '#10b981', '🍽️');
        INSERT INTO categories (name, color, icon) VALUES ('Transport', '#3b82f6', '🚗');
        INSERT INTO categories (name, color, icon) VALUES ('Logement', '#8b5cf6', '🏠');
        INSERT INTO categories (name, color, icon) VALUES ('Santé', '#ef4444', '💊');
        INSERT INTO categories (name, color, icon) VALUES ('Loisirs', '#f59e0b', '🎮');
        INSERT INTO categories (name, color, icon) VALUES ('Internet', '#06b6d4', '📶');
        INSERT INTO categories (name, color, icon) VALUES ('Imprévu', '#6b7280', '⚡');
        INSERT INTO categories (name, color, icon) VALUES ('Autre', '#6366f1', '📌');
        """)
    conn.commit()
    conn.close()

# ─── MOTEUR FINANCIER (LEDGER) ────────────────────────────────────────────────

def get_balance(account):
    """Calcule le solde d'un compte depuis le ledger."""
    conn = get_db()
    incoming = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE destination=?", (account,)
    ).fetchone()[0]
    outgoing = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE source=?", (account,)
    ).fetchone()[0]
    conn.close()
    return round(incoming - outgoing, 2)

def create_ledger_entry(conn, source, destination, amount, type_, description='', category_id=None, date=None):
    """Enregistre une transaction dans le ledger."""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    conn.execute(
        "INSERT INTO ledger (date, source, destination, amount, type, description, category_id) VALUES (?,?,?,?,?,?,?)",
        (date, source, destination, round(amount, 2), type_, description, category_id)
    )

def add_expense_smart(conn, montant, description, category_id, date):
    """
    Logique dépense : budget semaine d'abord, puis réserve pour l'excédent.
    Refuse si budget + réserve < montant.
    """
    budget_bal  = get_balance('budget')
    reserve_bal = get_balance('reserve')

    if montant > budget_bal + reserve_bal:
        return False, f"Fonds insuffisants. Disponible : {budget_bal + reserve_bal:.2f} (budget {budget_bal:.2f} + réserve {reserve_bal:.2f})"

    if montant <= budget_bal:
        create_ledger_entry(conn, 'budget', 'depense', montant, 'expense', description, category_id, date)
    else:
        from_budget  = budget_bal
        from_reserve = round(montant - from_budget, 2)
        if from_budget > 0:
            create_ledger_entry(conn, 'budget', 'depense', from_budget, 'expense', description, category_id, date)
        create_ledger_entry(conn, 'reserve', 'depense', from_reserve, 'expense_reserve', description, category_id, date)

    # Mettre à jour le spent du daily_budget du jour
    conn.execute(
        "UPDATE daily_budgets SET spent = COALESCE(spent,0) + ? WHERE date = ?",
        (montant, date)
    )
    return True, "ok"

# ─── CLÔTURE DE SEMAINE ───────────────────────────────────────────────────────

def close_week_if_needed():
    """Clôture les semaines passées non fermées : reste budget → réserve."""
    today = datetime.now().date()
    conn = get_db()
    old_weeks = conn.execute(
        "SELECT * FROM weekly_budgets WHERE closed=0 AND week_start < ?",
        (str(today - timedelta(days=today.weekday())),)
    ).fetchall()

    for w in old_weeks:
        week_start = datetime.strptime(w['week_start'], '%Y-%m-%d').date()
        week_end   = week_start + timedelta(days=6)

        # Calcul dépenses de la semaine depuis le ledger
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date BETWEEN ? AND ?",
            (str(week_start), str(week_end))
        ).fetchone()[0]

        # Argent alloué au budget cette semaine
        allocated = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE destination='budget' AND date BETWEEN ? AND ?",
            (str(week_start), str(week_end))
        ).fetchone()[0]

        reste = round(allocated - spent, 2)
        if reste > 0:
            create_ledger_entry(
                conn, 'budget', 'reserve', reste, 'week_close',
                f"Clôture semaine {w['week_start']} → réserve",
                date=str(week_end)
            )

        conn.execute("UPDATE weekly_budgets SET closed=1 WHERE id=?", (w['id'],))

    conn.commit()
    conn.close()

# ─── REPORT DU RESTE JOURNALIER ───────────────────────────────────────────────

def compute_daily_real_budget(weekly_budget_id, date_str):
    """Budget réel du jour = planifié + carry (reste de la veille)."""
    conn = get_db()
    day = conn.execute(
        "SELECT * FROM daily_budgets WHERE weekly_budget_id=? AND date=?",
        (weekly_budget_id, date_str)
    ).fetchone()
    conn.close()
    if not day:
        return 0
    return round(day['planned'] + (day['carry'] or 0), 2)

def propagate_carry(weekly_budget_id):
    """
    Calcule et propage le report (carry) pour chaque jour de la semaine.
    Le reste d'un jour = budget_réel - dépenses du jour → ajouté au lendemain.
    """
    conn = get_db()
    days = conn.execute(
        "SELECT * FROM daily_budgets WHERE weekly_budget_id=? ORDER BY date",
        (weekly_budget_id,)
    ).fetchall()

    carry = 0.0
    for day in days:
        # Mettre à jour le carry du jour
        conn.execute("UPDATE daily_budgets SET carry=? WHERE id=?", (round(carry, 2), day['id']))
        real_budget = day['planned'] + carry

        # Dépenses du jour depuis le ledger
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date=?",
            (day['date'],)
        ).fetchone()[0]

        reste = real_budget - spent
        carry = max(reste, 0)  # on ne propage pas un déficit

    conn.commit()
    conn.close()

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    close_week_if_needed()

    today      = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    reserve_bal = get_balance('reserve')
    budget_bal  = get_balance('budget')

    # Budget semaine actif
    conn = get_db()
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0",
        (str(week_start),)
    ).fetchone()

    # Dépenses de la semaine
    weekly_spent = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date BETWEEN ? AND ?",
        (str(week_start), str(week_start + timedelta(days=6)))
    ).fetchone()[0]

    # Budget et dépenses du jour
    today_day = None
    today_real_budget = 0
    today_spent = 0
    if weekly:
        propagate_carry(weekly['id'])
        today_day = conn.execute(
            "SELECT * FROM daily_budgets WHERE weekly_budget_id=? AND date=?",
            (weekly['id'], str(today))
        ).fetchone()
        if today_day:
            today_real_budget = round(today_day['planned'] + (today_day['carry'] or 0), 2)
        today_spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date=?",
            (str(today),)
        ).fetchone()[0]

    # Dernières transactions
    recent = conn.execute("""
        SELECT l.*, c.name as cat_name, c.icon as cat_icon, c.color as cat_color
        FROM ledger l
        LEFT JOIN categories c ON l.category_id = c.id
        ORDER BY l.created_at DESC LIMIT 7
    """).fetchall()

    # Dépenses par catégorie ce mois
    month = today.strftime('%Y-%m')
    by_cat = conn.execute("""
        SELECT c.name, c.color, c.icon, COALESCE(SUM(l.amount),0) as total
        FROM categories c
        LEFT JOIN ledger l ON l.category_id=c.id AND l.type IN ('expense','expense_reserve') AND l.date LIKE ?
        GROUP BY c.id HAVING total > 0
        ORDER BY total DESC
    """, (f"{month}%",)).fetchall()

    # Revenus et dépenses du mois
    monthly_income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?", (f"{month}%",)
    ).fetchone()[0]
    monthly_expenses = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?", (f"{month}%",)
    ).fetchone()[0]

    loans_count = conn.execute("SELECT COUNT(*) FROM loans WHERE status='active'").fetchone()[0]
    # Montant total des prêts actifs donnés
    loans_total = conn.execute(
        "SELECT COALESCE(SUM(remaining),0) FROM loans WHERE status='active' AND direction='given'"
    ).fetchone()[0]

    conn.close()
    return render_template("index.html",
        reserve_bal=reserve_bal, budget_bal=budget_bal,
        weekly=weekly, weekly_spent=round(weekly_spent,2),
        today_day=today_day, today_real_budget=today_real_budget,
        today_spent=round(today_spent,2),
        recent=recent, by_cat=by_cat,
        monthly_income=round(monthly_income,2), monthly_expenses=round(monthly_expenses,2),
        loans_count=loans_count, loans_total=round(loans_total,2),
        today=str(today), week_start=str(week_start)
    )

# ── REVENUS ───────────────────────────────────────────────────────────────────
@app.route("/revenu", methods=["GET","POST"])
def revenu():
    if request.method == "POST":
        montant     = float(request.form['montant'])
        description = request.form.get('description', 'Revenu')
        reserve_pct = float(request.form.get('reserve_pct', 30)) / 100
        reserve_part = round(montant * reserve_pct, 2)
        budget_part  = round(montant - reserve_part, 2)
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

        conn = get_db()
        # Entrée du revenu
        create_ledger_entry(conn, 'external', 'income', montant, 'income', description, date=date)
        # Répartition
        if reserve_part > 0:
            create_ledger_entry(conn, 'income', 'reserve', reserve_part, 'allocation', f"{description} → réserve", date=date)
        if budget_part > 0:
            create_ledger_entry(conn, 'income', 'budget', budget_part, 'allocation', f"{description} → budget", date=date)
        conn.commit()
        conn.close()
        flash(f"✅ Revenu de {montant:.2f} enregistré — Réserve: +{reserve_part:.2f} | Budget: +{budget_part:.2f}", "success")
        return redirect(url_for('index'))

    return render_template("revenu.html")

# ── DÉPENSES ──────────────────────────────────────────────────────────────────
@app.route("/depense", methods=["GET","POST"])
def depense():
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        montant     = float(request.form['montant'])
        description = request.form.get('description','')
        cat_id      = request.form.get('category_id')
        date        = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

        ok, msg = add_expense_smart(conn, montant, description, cat_id, date)
        if ok:
            conn.commit()
            flash(f"✅ Dépense de {montant:.2f} enregistrée.", "success")
            conn.close()
            return redirect(url_for('index'))
        else:
            conn.close()
            flash(f"⚠️ {msg}", "error")
            conn = get_db()
            categories = conn.execute("SELECT * FROM categories").fetchall()

    budget_bal  = get_balance('budget')
    reserve_bal = get_balance('reserve')
    conn.close()
    return render_template("depense.html", categories=categories,
                           budget_bal=budget_bal, reserve_bal=reserve_bal,
                           today=datetime.now().strftime('%Y-%m-%d'))

# ── TRANSFERT RÉSERVE → BUDGET ────────────────────────────────────────────────
@app.route("/transfert", methods=["POST"])
def transfert():
    montant = float(request.form['montant'])
    reserve_bal = get_balance('reserve')
    if reserve_bal < montant:
        flash(f"⚠️ Réserve insuffisante ({reserve_bal:.2f}).", "error")
    else:
        conn = get_db()
        create_ledger_entry(conn, 'reserve', 'budget', montant, 'transfer', 'Transfert réserve → budget')
        conn.commit()
        conn.close()
        flash(f"✅ {montant:.2f} transféré vers le budget.", "success")
    return redirect(url_for('index'))

# ── BUDGET SEMAINE ────────────────────────────────────────────────────────────
@app.route("/budget", methods=["GET","POST"])
def budget():
    today      = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    if request.method == "POST":
        montant = float(request.form['montant'])
        daily   = round(montant / 7, 2)
        conn = get_db()

        # Supprimer l'ancien budget de la semaine si existant
        old = conn.execute("SELECT id FROM weekly_budgets WHERE week_start=?", (str(week_start),)).fetchone()
        if old:
            conn.execute("DELETE FROM daily_budgets WHERE weekly_budget_id=?", (old['id'],))
            conn.execute("DELETE FROM weekly_budgets WHERE id=?", (old['id'],))

        wb = conn.execute("INSERT INTO weekly_budgets (week_start, total_amount) VALUES (?,?)",
            (str(week_start), montant))
        wb_id = wb.lastrowid

        for i in range(7):
            day = week_start + timedelta(days=i)
            conn.execute("INSERT INTO daily_budgets (weekly_budget_id, date, planned) VALUES (?,?,?)",
                (wb_id, str(day), daily))

        conn.commit()
        conn.close()
        flash(f"✅ Budget de {montant:.2f} défini — {daily:.2f}/jour pendant 7 jours.", "success")
        return redirect(url_for('budget'))

    conn = get_db()
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (str(week_start),)
    ).fetchone()

    daily_list = []
    if weekly:
        propagate_carry(weekly['id'])
        raw = conn.execute(
            "SELECT * FROM daily_budgets WHERE weekly_budget_id=? ORDER BY date",
            (weekly['id'],)
        ).fetchall()

        # Enrichir avec les dépenses réelles et le budget réel
        for d in raw:
            spent = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date=?",
                (d['date'],)
            ).fetchone()[0]
            real = round(d['planned'] + (d['carry'] or 0), 2)
            daily_list.append({
                'date': d['date'],
                'planned': d['planned'],
                'carry': d['carry'] or 0,
                'real': real,
                'spent': round(spent, 2),
                'reste': round(real - spent, 2)
            })

    conn.close()
    return render_template("budget.html", weekly=weekly, daily_list=daily_list,
                           week_start=week_start, today=str(today))

# ── MODIFIER BUDGET JOURNALIER ────────────────────────────────────────────────
@app.route("/budget/modifier_jour", methods=["POST"])
def modifier_jour():
    date_str   = request.form['date']
    nouveau    = float(request.form['planned'])
    week_start = request.form['week_start']

    conn = get_db()
    wb = conn.execute("SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (week_start,)).fetchone()
    if wb:
        # Vérifier que la somme des budgets ne dépasse pas le total
        autres = conn.execute(
            "SELECT COALESCE(SUM(planned),0) FROM daily_budgets WHERE weekly_budget_id=? AND date!=?",
            (wb['id'], date_str)
        ).fetchone()[0]
        if autres + nouveau > wb['total_amount'] + 0.01:
            flash(f"⚠️ La somme des budgets journaliers dépasse le budget semaine ({wb['total_amount']:.2f}).", "error")
        else:
            conn.execute("UPDATE daily_budgets SET planned=? WHERE weekly_budget_id=? AND date=?",
                (nouveau, wb['id'], date_str))
            conn.commit()
            propagate_carry(wb['id'])
            flash("✅ Budget journalier mis à jour.", "success")
    conn.close()
    return redirect(url_for('budget'))

# ── CLÔTURE MANUELLE DE SEMAINE ───────────────────────────────────────────────
@app.route("/budget/cloturer", methods=["POST"])
def cloturer_semaine():
    week_start_str = request.form['week_start']
    conn = get_db()
    w = conn.execute("SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (week_start_str,)).fetchone()
    if w:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        week_end   = week_start + timedelta(days=6)
        budget_bal = get_balance('budget')
        if budget_bal > 0:
            create_ledger_entry(conn, 'budget', 'reserve', budget_bal, 'week_close',
                f"Clôture semaine {week_start_str} → réserve", date=str(week_end))
            flash(f"✅ Semaine clôturée. {budget_bal:.2f} transféré vers la réserve.", "success")
        conn.execute("UPDATE weekly_budgets SET closed=1 WHERE id=?", (w['id'],))
        conn.commit()
    conn.close()
    return redirect(url_for('budget'))

# ── PRÊTS ─────────────────────────────────────────────────────────────────────
@app.route("/prets", methods=["GET","POST"])
def prets():
    conn = get_db()

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            montant   = float(request.form['amount'])
            direction = request.form['direction']
            date      = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
            person    = request.form['person_name']
            desc      = request.form.get('description','')

            if direction == 'given':
                # Prêt donné : argent sort de la réserve
                reserve_bal = get_balance('reserve')
                if reserve_bal < montant:
                    flash(f"⚠️ Réserve insuffisante ({reserve_bal:.2f}) pour ce prêt.", "error")
                    conn.close()
                    loans = conn.execute("SELECT * FROM loans ORDER BY status, date DESC").fetchall() if False else []
                    return redirect(url_for('prets'))
                create_ledger_entry(conn, 'reserve', f'loan_{person}', montant, 'loan',
                    f"Prêt à {person} — {desc}", date=date)
            else:
                # Argent emprunté : entre dans la réserve
                create_ledger_entry(conn, f'loan_{person}', 'reserve', montant, 'loan_received',
                    f"Emprunt de {person} — {desc}", date=date)

            conn.execute(
                "INSERT INTO loans (person_name,direction,amount,remaining,description,date) VALUES (?,?,?,?,?,?)",
                (person, direction, montant, montant, desc, date)
            )

        elif action == 'payment':
            loan_id = int(request.form['loan_id'])
            montant = float(request.form['amount'])
            date    = datetime.now().strftime('%Y-%m-%d')
            loan    = conn.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()

            if loan:
                montant = min(montant, loan['remaining'])  # ne pas rembourser plus que le restant
                if loan['direction'] == 'given':
                    # Remboursement reçu → réserve
                    create_ledger_entry(conn, f'loan_{loan["person_name"]}', 'reserve', montant,
                        'repayment', f"Remboursement de {loan['person_name']}", date=date)
                else:
                    # On rembourse ce qu'on a emprunté → sort de la réserve
                    reserve_bal = get_balance('reserve')
                    if reserve_bal < montant:
                        flash(f"⚠️ Réserve insuffisante pour ce remboursement.", "error")
                        conn.close()
                        return redirect(url_for('prets'))
                    create_ledger_entry(conn, 'reserve', f'loan_{loan["person_name"]}', montant,
                        'repayment', f"Remboursement à {loan['person_name']}", date=date)

                conn.execute("INSERT INTO loan_payments (loan_id,amount,date) VALUES (?,?,?)",
                    (loan_id, montant, date))
                conn.execute("UPDATE loans SET remaining=remaining-? WHERE id=?", (montant, loan_id))
                conn.execute("UPDATE loans SET status='paid' WHERE id=? AND remaining<=0.01", (loan_id,))

        conn.commit()
        conn.close()
        flash("✅ Opération enregistrée.", "success")
        return redirect(url_for('prets'))

    loans = conn.execute("SELECT * FROM loans ORDER BY status ASC, date DESC").fetchall()
    reserve_bal = get_balance('reserve')
    conn.close()
    return render_template("prets.html", loans=loans, reserve_bal=reserve_bal)

# ── HISTORIQUE ────────────────────────────────────────────────────────────────
@app.route("/historique")
def historique():
    conn = get_db()
    categories   = conn.execute("SELECT * FROM categories").fetchall()
    filter_type  = request.args.get('type','')
    filter_cat   = request.args.get('cat','')
    filter_month = request.args.get('month', datetime.now().strftime('%Y-%m'))

    query  = """
        SELECT l.*, c.name as cat_name, c.icon as cat_icon, c.color as cat_color
        FROM ledger l
        LEFT JOIN categories c ON l.category_id = c.id
        WHERE l.date LIKE ?
    """
    params = [f"{filter_month}%"]
    if filter_type:
        if filter_type == 'expense':
            query += " AND l.type IN ('expense','expense_reserve')"
        else:
            query += " AND l.type=?"
            params.append(filter_type)
    if filter_cat:
        query += " AND l.category_id=?"
        params.append(filter_cat)
    query += " ORDER BY l.date DESC, l.id DESC"

    transactions = conn.execute(query, params).fetchall()
    total_in  = sum(t['amount'] for t in transactions if t['type'] in ('income','allocation','repayment','week_close') and t['destination'] in ('reserve','budget','income'))
    total_out = sum(t['amount'] for t in transactions if t['type'] in ('expense','expense_reserve'))
    conn.close()
    return render_template("historique.html",
        transactions=transactions, categories=categories,
        filter_type=filter_type, filter_cat=filter_cat, filter_month=filter_month,
        total_in=round(total_in,2), total_out=round(total_out,2)
    )

@app.context_processor
def inject_now():
    return {"now": datetime.now()}

if __name__ == "__main__":
    init_db()
    print("\n🚀 Application démarrée → http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
