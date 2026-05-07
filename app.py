from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "finance_app_secret"
DB_PATH = "finance.db"


def fmt_cfa(amount):
    """Formate un montant en FCFA avec espaces comme séparateurs de milliers. Ex: 1 250 000 FCFA"""
    try:
        n = int(round(float(amount)))
        # Séparateur d'espaces insécables
        formatted = f"{n:,}".replace(",", "\u202f")
        return f"{formatted} FCFA"
    except:
        return "0 FCFA"


app.jinja_env.filters['cfa'] = fmt_cfa


def cfa(amount):
    """Formate pour les f-strings Python (flash messages, alertes)."""
    try:
        n = int(round(float(amount)))
        return f"{n:,}".replace(",", " ") + " FCFA"
    except:
        return "0 FCFA"


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
        spent REAL DEFAULT 0,
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

    CREATE TABLE IF NOT EXISTS savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        target_amount REAL NOT NULL,
        deadline TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS category_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL UNIQUE,
        weekly_limit REAL NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    );

    CREATE TABLE IF NOT EXISTS recurring_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category_id INTEGER,
        source TEXT DEFAULT 'auto',
        frequency TEXT NOT NULL,
        next_date TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        FOREIGN KEY (category_id) REFERENCES categories(id)
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
    # Migrations automatiques
    cols = [r[1] for r in c.execute("PRAGMA table_info(daily_budgets)").fetchall()]
    if 'spent' not in cols:
        c.execute("ALTER TABLE daily_budgets ADD COLUMN spent REAL DEFAULT 0")
    if 'note' not in cols:
        c.execute("ALTER TABLE daily_budgets ADD COLUMN note TEXT")

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


def add_expense_smart(conn, montant, description, category_id, date, source='auto'):
    """
    Logique dépense :
    - source='auto'    : budget semaine d'abord, réserve en complément si insuffisant
    - source='budget'  : uniquement depuis le budget semaine
    - source='reserve' : uniquement depuis la réserve
    Refuse si les fonds sont insuffisants dans la source choisie.
    """
    budget_bal = get_balance('budget')
    reserve_bal = get_balance('reserve')

    if source == 'budget':
        # Uniquement depuis le budget semaine
        if montant > budget_bal:
            return False, f"Budget semaine insuffisant. Disponible : {cfa(budget_bal)}"
        create_ledger_entry(conn, 'budget', 'depense', montant,
                            'expense', description, category_id, date)

    elif source == 'reserve':
        # Uniquement depuis la réserve
        if montant > reserve_bal:
            return False, f"Réserve insuffisante. Disponible : {cfa(reserve_bal)}"
        create_ledger_entry(conn, 'reserve', 'depense', montant,
                            'expense_reserve', description, category_id, date)

    else:
        # Mode automatique : budget d'abord, réserve en complément
        if montant > budget_bal + reserve_bal:
            return False, f"Fonds insuffisants. Disponible : {cfa(budget_bal + reserve_bal)} (budget {cfa(budget_bal)} + réserve {cfa(reserve_bal)})"
        if montant <= budget_bal:
            create_ledger_entry(conn, 'budget', 'depense', montant,
                                'expense', description, category_id, date)
        else:
            from_budget = budget_bal
            from_reserve = round(montant - from_budget, 2)
            if from_budget > 0:
                create_ledger_entry(
                    conn, 'budget', 'depense', from_budget, 'expense', description, category_id, date)
            create_ledger_entry(conn, 'reserve', 'depense', from_reserve,
                                'expense_reserve', description, category_id, date)

    # Mettre à jour le spent du daily_budget du jour
    try:
        conn.execute(
            "UPDATE daily_budgets SET spent = COALESCE(spent,0) + ? WHERE date = ?",
            (montant, date)
        )
    except Exception:
        pass  # La colonne spent peut ne pas exister sur ancienne base
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
        week_end = week_start + timedelta(days=6)

        # Solde réel du compte budget (identique à la clôture manuelle)
        reste = round(get_balance('budget'), 2)
        if reste > 0:
            create_ledger_entry(
                conn, 'budget', 'reserve', reste, 'week_close',
                f"Clôture semaine {w['week_start']} → réserve",
                date=str(week_end)
            )

        conn.execute(
            "UPDATE weekly_budgets SET closed=1 WHERE id=?", (w['id'],))

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
    Le reste d'un jour = budget_réel - dépenses du jour.

    Nouvelle logique :
    - reste positif  → ajouté au lendemain
    - reste négatif → retiré du lendemain
    """
    conn = get_db()
    days = conn.execute(
        "SELECT * FROM daily_budgets WHERE weekly_budget_id=? ORDER BY date",
        (weekly_budget_id,)
    ).fetchall()

    carry = 0.0
    for day in days:
        current_carry = round(carry, 2)

        # Mettre à jour le carry du jour (positif ou négatif)
        conn.execute(
            "UPDATE daily_budgets SET carry=? WHERE id=?",
            (current_carry, day['id'])
        )

        real_budget = round(day['planned'] + current_carry, 2)

        # Dépenses du jour depuis le ledger — uniquement les dépenses budget (pas reserve)
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date=?",
            (day['date'],)
        ).fetchone()[0]

        reste = round(real_budget - spent, 2)
        carry = reste

    conn.commit()
    conn.close()

# ─── ROUTES ───────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    close_week_if_needed()
    apply_recurring_expenses()

    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    reserve_bal = get_balance('reserve')
    budget_bal = get_balance('budget')

    # Budget semaine actif
    conn = get_db()
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0",
        (str(week_start),)
    ).fetchone()

    # Dépenses de la semaine — uniquement budget (cohérent avec la page budget)
    weekly_spent = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date BETWEEN ? AND ?",
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
            today_real_budget = round(
                today_day['planned'] + (today_day['carry'] or 0), 2)
        today_spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date=?",
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
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?", (
            f"{month}%",)
    ).fetchone()[0]
    monthly_expenses = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?", (
            f"{month}%",)
    ).fetchone()[0]

    loans_count = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE status='active'").fetchone()[0]
    # Montant total des prêts actifs donnés
    loans_total = conn.execute(
        "SELECT COALESCE(SUM(remaining),0) FROM loans WHERE status='active' AND direction='given'"
    ).fetchone()[0]

    conn.close()
    return render_template("index.html",
                           reserve_bal=reserve_bal, budget_bal=budget_bal,
                           weekly=weekly, weekly_spent=round(weekly_spent, 2),
                           today_day=today_day, today_real_budget=today_real_budget,
                           today_spent=round(today_spent, 2),
                           recent=recent, by_cat=by_cat,
                           monthly_income=round(monthly_income, 2), monthly_expenses=round(monthly_expenses, 2),
                           loans_count=loans_count, loans_total=round(
                               loans_total, 2),
                           today=str(today), week_start=str(week_start)
                           )

# ── REVENUS ───────────────────────────────────────────────────────────────────


@app.route("/revenu", methods=["GET", "POST"])
def revenu():
    if request.method == "POST":
        montant = float(request.form['montant'])
        description = request.form.get('description', 'Revenu')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        mode = request.form.get('mode', 'auto')

        if mode == 'manuel':
            # Montants saisis directement
            reserve_part = float(request.form.get('reserve_montant') or 0)
            budget_part = float(request.form.get('budget_montant') or 0)
            # Sécurité : on s'assure que la somme ne dépasse pas le montant
            if reserve_part + budget_part > montant + 1:
                flash("⚠️ La somme des montants dépasse le revenu total.", "error")
                return redirect(url_for('revenu'))
        else:
            # Mode automatique : calcul par pourcentage
            reserve_pct = float(request.form.get('reserve_pct', 30)) / 100
            reserve_part = round(montant * reserve_pct, 2)
            budget_part = round(montant - reserve_part, 2)

        reserve_part = round(reserve_part, 2)
        budget_part = round(budget_part, 2)

        conn = get_db()
        create_ledger_entry(conn, 'external', 'income',
                            montant, 'income', description, date=date)
        if reserve_part > 0:
            create_ledger_entry(conn, 'income', 'reserve', reserve_part,
                                'allocation', f"{description} → réserve", date=date)
        if budget_part > 0:
            create_ledger_entry(conn, 'income', 'budget', budget_part,
                                'allocation', f"{description} → budget", date=date)
        conn.commit()
        conn.close()
        flash(
            f"✅ Revenu de {cfa(montant)} enregistré — Réserve : +{cfa(reserve_part)} | Budget : +{cfa(budget_part)}", "success")
        return redirect(url_for('index'))

    return render_template("revenu.html")

# ── DÉPENSES ──────────────────────────────────────────────────────────────────


@app.route("/depense", methods=["GET", "POST"])
def depense():
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        montant = float(request.form['montant'])
        description = request.form.get('description', '')
        cat_id = request.form.get('category_id')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        source = request.form.get('source', 'auto')

        ok, msg = add_expense_smart(
            conn, montant, description, cat_id, date, source)
        if ok:
            conn.commit()
            flash(f"✅ Dépense de {cfa(montant)} enregistrée.", "success")
            conn.close()
            return redirect(url_for('index'))
        else:
            conn.close()
            flash(f"⚠️ {msg}", "error")
            conn = get_db()
            categories = conn.execute("SELECT * FROM categories").fetchall()

    budget_bal = get_balance('budget')
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
        flash(f"⚠️ Réserve insuffisante ({cfa(reserve_bal)}).", "error")
    else:
        conn = get_db()
        create_ledger_entry(conn, 'reserve', 'budget', montant,
                            'transfer', 'Transfert réserve → budget')
        conn.commit()
        conn.close()
        flash(f"✅ {cfa(montant)} transféré vers le budget.", "success")
    return redirect(url_for('index'))

# ── BUDGET SEMAINE ────────────────────────────────────────────────────────────


@app.route("/budget", methods=["GET", "POST"])
def budget():
    today = datetime.now().date()
    # Navigation semaines : ?week=YYYY-MM-DD pour voir une semaine passée
    week_param = request.args.get('week')
    if week_param:
        try:
            nav_date = datetime.strptime(week_param, '%Y-%m-%d').date()
            week_start = nav_date - timedelta(days=nav_date.weekday())
        except ValueError:
            week_start = today - timedelta(days=today.weekday())
    else:
        week_start = today - timedelta(days=today.weekday())

    is_current_week = (week_start == today - timedelta(days=today.weekday()))
    prev_week = week_start - timedelta(days=7)
    next_week = week_start + timedelta(days=7)

    if request.method == "POST":
        montant = float(request.form['montant'])
        daily = round(montant / 7, 2)
        conn = get_db()

        # F3 : Vérification budget vs solde réel du compte budget
        budget_bal = get_balance('budget')
        if montant > budget_bal + 0.01:
            conn.close()
            flash(f"⚠️ Budget ({cfa(montant)}) supérieur au solde disponible ({cfa(budget_bal)}). Alimente d'abord le budget via un revenu ou un transfert.", "error")
            return redirect(url_for('budget'))

        # Supprimer l'ancien budget de la semaine si existant
        old = conn.execute(
            "SELECT id FROM weekly_budgets WHERE week_start=?", (str(week_start),)).fetchone()
        if old:
            conn.execute(
                "DELETE FROM daily_budgets WHERE weekly_budget_id=?", (old['id'],))
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
        flash(f"✅ Budget de {cfa(montant)} défini — {cfa(daily)}/jour pendant 7 jours.", "success")
        return redirect(url_for('budget'))

    conn = get_db()
    # Chercher le budget de la semaine naviguée (ouvert ou fermé)
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=?", (str(week_start),)
    ).fetchone()

    daily_list = []
    if weekly:
        if not weekly['closed']:
            propagate_carry(weekly['id'])
        raw = conn.execute(
            "SELECT * FROM daily_budgets WHERE weekly_budget_id=? ORDER BY date",
            (weekly['id'],)
        ).fetchall()

        for d in raw:
            spent = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date=?",
                (d['date'],)
            ).fetchone()[0]
            real = round(d['planned'] + (d['carry'] or 0), 2)
            daily_list.append({
                'date': d['date'],
                'planned': d['planned'],
                'carry': d['carry'] or 0,
                'real': real,
                'spent': round(spent, 2),
                'reste': round(real - spent, 2),
                'note': d['note'] or ''
            })

    # Liste des semaines passées pour la navigation
    past_weeks = conn.execute(
        "SELECT week_start, total_amount, closed FROM weekly_budgets ORDER BY week_start DESC LIMIT 10"
    ).fetchall()

    conn.close()
    return render_template("budget.html", weekly=weekly, daily_list=daily_list,
                           week_start=week_start, today=str(today),
                           is_current_week=is_current_week,
                           prev_week=str(prev_week), next_week=str(next_week),
                           past_weeks=past_weeks)

# ── MODIFIER BUDGET JOURNALIER ────────────────────────────────────────────────


@app.route("/budget/modifier_jour", methods=["POST"])
def modifier_jour():
    date_str = request.form.get('date', '')
    planned_raw = request.form.get('planned', '').strip()
    week_start = request.form.get('week_start', '')

    if not planned_raw:
        flash("⚠️ Saisis un montant avant de modifier.", "error")
        return redirect(url_for('budget'))

    try:
        nouveau = float(planned_raw)
    except ValueError:
        flash("⚠️ Montant invalide.", "error")
        return redirect(url_for('budget'))

    if nouveau < 0:
        flash("⚠️ Le budget ne peut pas être négatif.", "error")
        return redirect(url_for('budget'))

    conn = get_db()
    wb = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (week_start,)).fetchone()
    if wb:
        # Vérifier que la somme des budgets ne dépasse pas le total
        autres = conn.execute(
            "SELECT COALESCE(SUM(planned),0) FROM daily_budgets WHERE weekly_budget_id=? AND date!=?",
            (wb['id'], date_str)
        ).fetchone()[0]
        if autres + nouveau > wb['total_amount'] + 0.01:
            flash(
                f"⚠️ La somme des budgets journaliers dépasse le budget semaine ({cfa(wb["total_amount"])}).", "error")
        else:
            conn.execute("UPDATE daily_budgets SET planned=? WHERE weekly_budget_id=? AND date=?",
                         (nouveau, wb['id'], date_str))
            conn.commit()
            propagate_carry(wb['id'])
            flash("✅ Budget journalier mis à jour.", "success")
    conn.close()
    return redirect(url_for('budget'))

# ── NOTE SUR UN JOUR ─────────────────────────────────────────────────────────

@app.route("/budget/noter_jour", methods=["POST"])
def noter_jour():
    date_str = request.form.get('date', '')
    note = request.form.get('note', '').strip()
    week_start = request.form.get('week_start', '')
    conn = get_db()
    wb = conn.execute("SELECT id FROM weekly_budgets WHERE week_start=?", (week_start,)).fetchone()
    if wb:
        conn.execute("UPDATE daily_budgets SET note=? WHERE weekly_budget_id=? AND date=?",
                     (note or None, wb['id'], date_str))
        conn.commit()
    conn.close()
    return redirect(url_for('budget', week=week_start))


# ── CLÔTURE MANUELLE DE SEMAINE ───────────────────────────────────────────────


@app.route("/budget/cloturer", methods=["POST"])
def cloturer_semaine():
    week_start_str = request.form['week_start']
    conn = get_db()
    w = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (week_start_str,)).fetchone()
    if w:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        week_end = week_start + timedelta(days=6)
        budget_bal = get_balance('budget')
        if budget_bal > 0:
            create_ledger_entry(conn, 'budget', 'reserve', budget_bal, 'week_close',
                                f"Clôture semaine {week_start_str} → réserve", date=str(week_end))
            flash(
                f"✅ Semaine clôturée. {cfa(budget_bal)} transféré vers la réserve.", "success")
        conn.execute(
            "UPDATE weekly_budgets SET closed=1 WHERE id=?", (w['id'],))
        conn.commit()
    conn.close()
    return redirect(url_for('budget'))

# ── PRÊTS ─────────────────────────────────────────────────────────────────────


@app.route("/prets", methods=["GET", "POST"])
def prets():
    conn = get_db()

    if request.method == "POST":
        action = request.form.get('action')

        if action == 'add':
            montant = float(request.form['amount'])
            direction = request.form['direction']
            date = request.form.get(
                'date', datetime.now().strftime('%Y-%m-%d'))
            person = request.form['person_name']
            desc = request.form.get('description', '')

            if direction == 'given':
                # Prêt donné : argent sort de la réserve
                reserve_bal = get_balance('reserve')
                if reserve_bal < montant:
                    flash(
                        f"⚠️ Réserve insuffisante ({cfa(reserve_bal)}) pour ce prêt.", "error")
                    conn.close()
                    loans = conn.execute(
                        "SELECT * FROM loans ORDER BY status, date DESC").fetchall() if False else []
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
            date = request.form.get(
                'date', datetime.now().strftime('%Y-%m-%d'))
            note = request.form.get('note', '').strip()
            loan = conn.execute(
                "SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()

            if loan:
                montant = min(montant, loan['remaining'])
                if loan['direction'] == 'given':
                    create_ledger_entry(conn, f'loan_{loan["person_name"]}', 'reserve', montant,
                                        'repayment', f"Remboursement de {loan['person_name']}{' — ' + note if note else ''}", date=date)
                else:
                    reserve_bal = get_balance('reserve')
                    if reserve_bal < montant:
                        flash(
                            f"⚠️ Réserve insuffisante pour ce remboursement.", "error")
                        conn.close()
                        return redirect(url_for('prets'))
                    create_ledger_entry(conn, 'reserve', f'loan_{loan["person_name"]}', montant,
                                        'repayment', f"Remboursement à {loan['person_name']}{' — ' + note if note else ''}", date=date)

                conn.execute("INSERT INTO loan_payments (loan_id,amount,date,note) VALUES (?,?,?,?)",
                             (loan_id, montant, date, note or None))
                conn.execute(
                    "UPDATE loans SET remaining=remaining-? WHERE id=?", (montant, loan_id))
                conn.execute(
                    "UPDATE loans SET status='paid' WHERE id=? AND remaining<=0.01", (loan_id,))
                flash(
                    f"✅ Remboursement de {cfa(montant)} enregistré.", "success")

        if action == 'add':
            flash("✅ Prêt enregistré.", "success")

        conn.commit()
        conn.close()
        return redirect(url_for('prets'))

    loans = conn.execute(
        "SELECT * FROM loans ORDER BY status ASC, date DESC").fetchall()
    reserve_bal = get_balance('reserve')

    # Historique des remboursements par prêt
    payments_by_loan = {}
    for loan in loans:
        payments = conn.execute(
            "SELECT * FROM loan_payments WHERE loan_id=? ORDER BY date DESC",
            (loan['id'],)
        ).fetchall()
        payments_by_loan[loan['id']] = payments

    conn.close()
    return render_template("prets.html", loans=loans, reserve_bal=reserve_bal,
                           payments_by_loan=payments_by_loan)

# ── HISTORIQUE ────────────────────────────────────────────────────────────────


@app.route("/historique")
def historique():
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories").fetchall()
    filter_type = request.args.get('type', '')
    filter_cat = request.args.get('cat', '')
    filter_month = request.args.get('month', datetime.now().strftime('%Y-%m'))

    query = """
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

    filter_search = request.args.get('search', '').strip()
    if filter_search:
        query += " AND l.description LIKE ?"
        params.append(f"%{filter_search}%")

    transactions = conn.execute(query, params).fetchall()
    total_in = sum(t['amount'] for t in transactions if t['type'] in ('income', 'allocation',
                   'repayment', 'week_close') and t['destination'] in ('reserve', 'budget', 'income'))
    total_out = sum(t['amount'] for t in transactions if t['type']
                    in ('expense', 'expense_reserve'))
    conn.close()
    return render_template("historique.html",
                           transactions=transactions, categories=categories,
                           filter_type=filter_type, filter_cat=filter_cat, filter_month=filter_month,
                           filter_search=filter_search,
                           total_in=round(total_in, 2), total_out=round(total_out, 2)
                           )


# ── SUPPRIMER UNE TRANSACTION ─────────────────────────────────────────────────

@app.route("/transaction/supprimer/<int:tid>", methods=["POST"])
def supprimer_transaction(tid):
    conn = get_db()
    t = conn.execute("SELECT * FROM ledger WHERE id=?", (tid,)).fetchone()
    if t:
        # Recalculer le spent du daily_budget si c'était une dépense budget
        if t['type'] == 'expense':
            conn.execute(
                "UPDATE daily_budgets SET spent = MAX(0, spent - ?) WHERE date=?",
                (t['amount'], t['date'])
            )
        conn.execute("DELETE FROM ledger WHERE id=?", (tid,))
        conn.commit()
        flash(f"✅ Transaction supprimée ({cfa(t['amount'])}).", "success")
    conn.close()
    return redirect(request.referrer or url_for('historique'))


# ── MODIFIER UNE TRANSACTION ──────────────────────────────────────────────────

@app.route("/transaction/modifier/<int:tid>", methods=["GET", "POST"])
def modifier_transaction(tid):
    conn = get_db()
    t = conn.execute("SELECT * FROM ledger WHERE id=?", (tid,)).fetchone()
    if not t:
        flash("Transaction introuvable.", "error")
        conn.close()
        return redirect(url_for('historique'))

    categories = conn.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        new_desc = request.form.get('description', t['description'])
        new_cat  = request.form.get('category_id') or None
        new_date = request.form.get('date', t['date'])
        try:
            new_amount = round(float(request.form['amount']), 2)
        except (ValueError, KeyError):
            new_amount = t['amount']

        # Recorriger le spent si dépense budget
        if t['type'] == 'expense':
            diff = new_amount - t['amount']
            conn.execute(
                "UPDATE daily_budgets SET spent = MAX(0, spent + ?) WHERE date=?",
                (diff, t['date'])
            )
            # Si la date change, corriger les deux jours
            if new_date != t['date']:
                conn.execute(
                    "UPDATE daily_budgets SET spent = MAX(0, spent - ?) WHERE date=?",
                    (t['amount'], t['date'])
                )
                conn.execute(
                    "UPDATE daily_budgets SET spent = COALESCE(spent,0) + ? WHERE date=?",
                    (new_amount, new_date)
                )

        conn.execute(
            "UPDATE ledger SET description=?, category_id=?, date=?, amount=? WHERE id=?",
            (new_desc, new_cat, new_date, new_amount, tid)
        )
        conn.commit()
        conn.close()
        flash("✅ Transaction modifiée.", "success")
        return redirect(url_for('historique'))

    conn.close()
    return render_template("modifier_transaction.html", t=t, categories=categories,
                           today=datetime.now().strftime('%Y-%m-%d'))


# ── STATISTIQUES ──────────────────────────────────────────────────────────────


@app.route("/stats")
def stats():
    conn = get_db()
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    month = today.strftime('%Y-%m')

    # ── Dépenses par catégorie ce mois ──
    by_cat_month = [dict(r) for r in conn.execute("""
        SELECT c.name, c.color, c.icon, COALESCE(SUM(l.amount),0) as total
        FROM categories c
        LEFT JOIN ledger l ON l.category_id=c.id
            AND l.type IN ('expense','expense_reserve') AND l.date LIKE ?
        GROUP BY c.id HAVING total > 0 ORDER BY total DESC
    """, (f"{month}%",)).fetchall()]

    # ── Dépenses par catégorie cette semaine ──
    by_cat_week = [dict(r) for r in conn.execute("""
        SELECT c.name, c.color, c.icon, COALESCE(SUM(l.amount),0) as total
        FROM categories c
        LEFT JOIN ledger l ON l.category_id=c.id
            AND l.type IN ('expense','expense_reserve')
            AND l.date BETWEEN ? AND ?
        GROUP BY c.id HAVING total > 0 ORDER BY total DESC
    """, (str(week_start), str(week_start + timedelta(days=6)))).fetchall()]

    # ── Évolution des dépenses sur les 6 derniers mois ──
    monthly_trend = []
    for i in range(5, -1, -1):
        year = today.year
        month_num = today.month - i
        while month_num <= 0:
            month_num += 12
            year -= 1
        m_label = f"{year}-{month_num:02d}"
        exp = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?",
            (f"{m_label}%",)
        ).fetchone()[0]
        inc = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?",
            (f"{m_label}%",)
        ).fetchone()[0]
        monthly_trend.append(
            {'month': m_label, 'expenses': round(exp, 2), 'income': round(inc, 2)})

    # ── Dépenses par jour cette semaine ──
    daily_week = []
    jours = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (str(
            week_start),)
    ).fetchone()
    for i in range(7):
        day = week_start + timedelta(days=i)
        spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date=?",
            (str(day),)
        ).fetchone()[0]
        budget_day = 0
        if weekly:
            db = conn.execute(
                "SELECT planned, carry FROM daily_budgets WHERE weekly_budget_id=? AND date=?",
                (weekly['id'], str(day))
            ).fetchone()
            if db:
                budget_day = round(db['planned'] + (db['carry'] or 0), 2)
        daily_week.append({'label': jours[i], 'spent': round(
            spent, 2), 'budget': budget_day, 'is_today': str(day) == str(today)})

    # ── Totaux mois ──
    total_month_exp = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?", (
            f"{month}%",)
    ).fetchone()[0]
    total_month_inc = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?", (
            f"{month}%",)
    ).fetchone()[0]

    # ── Totaux semaine ──
    total_week_exp = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date BETWEEN ? AND ?",
        (str(week_start), str(week_start + timedelta(days=6)))
    ).fetchone()[0]

    reserve_bal = get_balance('reserve')
    budget_bal = get_balance('budget')

    conn.close()
    return render_template("stats.html",
                           by_cat_month=by_cat_month, by_cat_week=by_cat_week,
                           monthly_trend=monthly_trend, daily_week=daily_week,
                           total_month_exp=round(total_month_exp, 2), total_month_inc=round(total_month_inc, 2),
                           total_week_exp=round(total_week_exp, 2),
                           reserve_bal=reserve_bal, budget_bal=budget_bal,
                           weekly=weekly, week_start=str(week_start), today=str(today), month=month
                           )

# ── API ALERTES (appelée en JS depuis le dashboard) ──────────────────────────


@app.route("/api/alertes")
def api_alertes():
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    alertes = []

    conn = get_db()
    weekly = conn.execute(
        "SELECT * FROM weekly_budgets WHERE week_start=? AND closed=0", (str(
            week_start),)
    ).fetchone()

    if weekly:
        today_day = conn.execute(
            "SELECT * FROM daily_budgets WHERE weekly_budget_id=? AND date=?",
            (weekly['id'], str(today))
        ).fetchone()
        if today_day:
            real_budget = round(
                today_day['planned'] + (today_day['carry'] or 0), 2)
            spent = conn.execute(
                "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date=?",
                (str(today),)
            ).fetchone()[0]
            pct = (spent / real_budget * 100) if real_budget > 0 else 0
            reste = real_budget - spent

            if pct >= 100:
                alertes.append(
                    {'level': 'danger', 'msg': f"⛔ Budget journalier dépassé ! Tu as dépensé {cfa(spent)} sur {cfa(real_budget)} prévu."})
            elif pct >= 80:
                alertes.append(
                    {'level': 'warning', 'msg': f"⚠️ Attention — il te reste seulement {cfa(reste)} pour aujourd'hui ({100-pct:.0f}%)."})
            elif pct >= 60:
                alertes.append(
                    {'level': 'info', 'msg': f"💡 Tu as utilisé {pct:.0f}% de ton budget journalier. Reste : {cfa(reste)}."})

        # Alerte budget semaine — uniquement budget (cohérent avec la page budget)
        week_spent = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='expense' AND date BETWEEN ? AND ?",
            (str(week_start), str(week_start + timedelta(days=6)))
        ).fetchone()[0]
        week_pct = (week_spent / weekly['total_amount']
                    * 100) if weekly['total_amount'] > 0 else 0
        if week_pct >= 90:
            alertes.append(
                {'level': 'warning', 'msg': f"⚠️ Budget semaine presque épuisé — {100-week_pct:.0f}% restant."})

    # Alertes plafonds par catégorie (cette semaine)
    cat_limits = conn.execute("""
        SELECT cb.weekly_limit, c.name, c.icon,
               COALESCE(SUM(l.amount),0) as spent
        FROM category_budgets cb
        JOIN categories c ON c.id = cb.category_id
        LEFT JOIN ledger l ON l.category_id = cb.category_id
            AND l.type IN ('expense','expense_reserve')
            AND l.date BETWEEN ? AND ?
        GROUP BY cb.category_id
    """, (str(week_start), str(week_start + timedelta(days=6)))).fetchall()
    for cl in cat_limits:
        pct = cl['spent'] / cl['weekly_limit'] * 100 if cl['weekly_limit'] > 0 else 0
        if pct >= 100:
            alertes.append({'level': 'danger', 'msg': f"⛔ Plafond {cl['icon']} {cl['name']} dépassé ({cfa(cl['spent'])} / {cfa(cl['weekly_limit'])})."})
        elif pct >= 80:
            alertes.append({'level': 'warning', 'msg': f"⚠️ {cl['icon']} {cl['name']} : {pct:.0f}% du plafond hebdo atteint."})

    # Alerte réserve faible
    reserve_bal = get_balance('reserve')
    budget_bal = get_balance('budget')
    if reserve_bal < budget_bal * 0.5 and reserve_bal < 10000:
        alertes.append(
            {'level': 'info', 'msg': f"💰 Réserve faible ({cfa(reserve_bal)}). Pense à alimenter ton épargne."})

    conn.close()
    from flask import jsonify
    return jsonify(alertes)


@app.context_processor
def inject_now():
    return {"now": datetime.now()}

# ── RÉSERVE ───────────────────────────────────────────────────────────────────


@app.route("/reserve", methods=["GET", "POST"])
def reserve():
    if request.method == "POST":
        action = request.form.get('action')
        montant = float(request.form.get('montant', 0))
        description = request.form.get('description', '')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))

        if montant <= 0:
            flash("⚠️ Le montant doit être supérieur à 0.", "error")
            return redirect(url_for('reserve'))

        conn = get_db()

        if action == 'credit':
            # Alimenter la réserve directement (sans passer par revenu)
            create_ledger_entry(conn, 'external', 'reserve', montant, 'reserve_credit',
                                description or 'Alimentation réserve', date=date)
            conn.commit()
            conn.close()
            flash(f"✅ Réserve créditée de {cfa(montant)}.", "success")

        elif action == 'debit':
            # Retrait direct depuis la réserve (dépense imprévue hors budget)
            reserve_bal = get_balance('reserve')
            if montant > reserve_bal:
                conn.close()
                flash(
                    f"⚠️ Réserve insuffisante. Disponible : {cfa(reserve_bal)}.", "error")
                return redirect(url_for('reserve'))
            create_ledger_entry(conn, 'reserve', 'external', montant, 'reserve_debit',
                                description or 'Retrait réserve', date=date)
            conn.commit()
            conn.close()
            flash(f"✅ {cfa(montant)} retiré de la réserve.", "success")

        elif action == 'ajustement':
            # Forcer la réserve à un montant précis
            reserve_bal = get_balance('reserve')
            nouveau = montant
            diff = round(nouveau - reserve_bal, 2)
            if diff == 0:
                conn.close()
                flash("ℹ️ Le solde est déjà à ce montant.", "error")
                return redirect(url_for('reserve'))
            if diff > 0:
                create_ledger_entry(conn, 'external', 'reserve', diff, 'adjustment',
                                    description or f'Ajustement réserve (+{cfa(diff)})', date=date)
            else:
                create_ledger_entry(conn, 'reserve', 'external', abs(diff), 'adjustment',
                                    description or f'Ajustement réserve ({cfa(diff)})', date=date)
            conn.commit()
            conn.close()
            flash(
                f"✅ Réserve ajustée à {cfa(nouveau)} (différence : {cfa(diff)}).", "success")

        return redirect(url_for('reserve'))

    # GET
    reserve_bal = get_balance('reserve')
    budget_bal = get_balance('budget')
    conn = get_db()
    # Historique des opérations sur la réserve (20 dernières)
    historique = conn.execute("""
        SELECT * FROM ledger
        WHERE source='reserve' OR destination='reserve'
        ORDER BY date DESC, id DESC LIMIT 20
    """).fetchall()
    conn.close()
    return render_template("reserve.html",
                           reserve_bal=reserve_bal, budget_bal=budget_bal,
                           historique=historique, today=datetime.now().strftime('%Y-%m-%d'))


# ── CATÉGORIES PERSONNALISABLES ───────────────────────────────────────────────

@app.route("/categories", methods=["GET", "POST"])
def categories():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get('action')
        if action == 'add':
            name  = request.form.get('name', '').strip()
            color = request.form.get('color', '#6366f1')
            icon  = request.form.get('icon', '📌').strip() or '📌'
            if name:
                conn.execute("INSERT INTO categories (name, color, icon) VALUES (?,?,?)", (name, color, icon))
                conn.commit()
                flash(f"✅ Catégorie « {name} » créée.", "success")
        elif action == 'edit':
            cid   = int(request.form['cat_id'])
            name  = request.form.get('name', '').strip()
            color = request.form.get('color', '#6366f1')
            icon  = request.form.get('icon', '📌').strip() or '📌'
            if name:
                conn.execute("UPDATE categories SET name=?, color=?, icon=? WHERE id=?", (name, color, icon, cid))
                conn.commit()
                flash("✅ Catégorie mise à jour.", "success")
        elif action == 'delete':
            cid = int(request.form['cat_id'])
            used = conn.execute("SELECT COUNT(*) FROM ledger WHERE category_id=?", (cid,)).fetchone()[0]
            if used > 0:
                flash("⚠️ Impossible de supprimer : cette catégorie est utilisée dans des transactions.", "error")
            else:
                conn.execute("DELETE FROM category_budgets WHERE category_id=?", (cid,))
                conn.execute("DELETE FROM categories WHERE id=?", (cid,))
                conn.commit()
                flash("✅ Catégorie supprimée.", "success")
        conn.close()
        return redirect(url_for('categories'))

    cats = conn.execute("""
        SELECT c.*, cb.weekly_limit,
               COUNT(l.id) as usage_count
        FROM categories c
        LEFT JOIN category_budgets cb ON cb.category_id = c.id
        LEFT JOIN ledger l ON l.category_id = c.id
        GROUP BY c.id ORDER BY c.name
    """).fetchall()
    conn.close()
    return render_template("categories.html", cats=cats)


# ── BUDGET PAR CATÉGORIE ──────────────────────────────────────────────────────

@app.route("/categories/budget", methods=["POST"])
def set_category_budget():
    cat_id = int(request.form['cat_id'])
    try:
        limit = float(request.form['weekly_limit'])
    except (ValueError, KeyError):
        flash("⚠️ Montant invalide.", "error")
        return redirect(url_for('categories'))
    conn = get_db()
    if limit <= 0:
        conn.execute("DELETE FROM category_budgets WHERE category_id=?", (cat_id,))
        flash("✅ Plafond supprimé.", "success")
    else:
        conn.execute("""
            INSERT INTO category_budgets (category_id, weekly_limit)
            VALUES (?,?) ON CONFLICT(category_id) DO UPDATE SET weekly_limit=excluded.weekly_limit
        """, (cat_id, limit))
        flash("✅ Plafond hebdomadaire enregistré.", "success")
    conn.commit()
    conn.close()
    return redirect(url_for('categories'))


# ── OBJECTIFS D'ÉPARGNE ───────────────────────────────────────────────────────

@app.route("/objectifs", methods=["GET", "POST"])
def objectifs():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get('action')
        if action == 'add':
            name   = request.form.get('name', '').strip()
            target = float(request.form.get('target_amount', 0))
            deadline = request.form.get('deadline') or None
            if name and target > 0:
                conn.execute("INSERT INTO savings_goals (name, target_amount, deadline) VALUES (?,?,?)",
                             (name, target, deadline))
                conn.commit()
                flash(f"✅ Objectif « {name} » créé.", "success")
        elif action == 'delete':
            gid = int(request.form['goal_id'])
            conn.execute("DELETE FROM savings_goals WHERE id=?", (gid,))
            conn.commit()
            flash("✅ Objectif supprimé.", "success")
        conn.close()
        return redirect(url_for('objectifs'))

    goals = conn.execute("SELECT * FROM savings_goals ORDER BY created_at DESC").fetchall()
    reserve_bal = get_balance('reserve')
    today = datetime.now().date()

    goals_data = []
    for g in goals:
        pct = min(reserve_bal / g['target_amount'] * 100, 100) if g['target_amount'] > 0 else 0
        reste = max(g['target_amount'] - reserve_bal, 0)
        # Calcul du montant hebdo nécessaire pour atteindre l'objectif à temps
        weekly_needed = None
        if g['deadline']:
            try:
                deadline_date = datetime.strptime(g['deadline'], '%Y-%m-%d').date()
                weeks_left = max((deadline_date - today).days / 7, 1)
                weekly_needed = round(reste / weeks_left, 0) if reste > 0 else 0
            except ValueError:
                pass
        goals_data.append({**dict(g), 'pct': round(pct, 1), 'reste': reste, 'weekly_needed': weekly_needed})

    conn.close()
    return render_template("objectifs.html", goals=goals_data, reserve_bal=reserve_bal,
                           today=datetime.now().strftime('%Y-%m-%d'))


# ── DÉPENSES RÉCURRENTES ──────────────────────────────────────────────────────

def apply_recurring_expenses():
    """Injecte les dépenses récurrentes dont la date est passée."""
    today = datetime.now().date()
    conn = get_db()
    recs = conn.execute(
        "SELECT * FROM recurring_expenses WHERE active=1 AND next_date<=?", (str(today),)
    ).fetchall()
    for r in recs:
        ok, _ = add_expense_smart(conn, r['amount'], r['description'], r['category_id'],
                                  r['next_date'], r['source'])
        if ok:
            # Calculer la prochaine date
            freq = r['frequency']
            base = datetime.strptime(r['next_date'], '%Y-%m-%d').date()
            if freq == 'daily':
                next_d = base + timedelta(days=1)
            elif freq == 'weekly':
                next_d = base + timedelta(days=7)
            elif freq == 'monthly':
                m = base.month + 1 if base.month < 12 else 1
                y = base.year if base.month < 12 else base.year + 1
                next_d = base.replace(year=y, month=m)
            else:
                next_d = base + timedelta(days=30)
            conn.execute("UPDATE recurring_expenses SET next_date=? WHERE id=?",
                         (str(next_d), r['id']))
    conn.commit()
    conn.close()


@app.route("/recurrentes", methods=["GET", "POST"])
def recurrentes():
    conn = get_db()
    categories = conn.execute("SELECT * FROM categories").fetchall()

    if request.method == "POST":
        action = request.form.get('action')
        if action == 'add':
            desc     = request.form.get('description', '').strip()
            amount   = float(request.form.get('amount', 0))
            cat_id   = request.form.get('category_id') or None
            source   = request.form.get('source', 'auto')
            freq     = request.form.get('frequency', 'monthly')
            next_d   = request.form.get('next_date', datetime.now().strftime('%Y-%m-%d'))
            if desc and amount > 0:
                conn.execute("""
                    INSERT INTO recurring_expenses (description, amount, category_id, source, frequency, next_date)
                    VALUES (?,?,?,?,?,?)
                """, (desc, amount, cat_id, source, freq, next_d))
                conn.commit()
                flash(f"✅ Dépense récurrente « {desc} » enregistrée.", "success")
        elif action == 'toggle':
            rid = int(request.form['rec_id'])
            conn.execute("UPDATE recurring_expenses SET active = 1 - active WHERE id=?", (rid,))
            conn.commit()
            flash("✅ Statut mis à jour.", "success")
        elif action == 'delete':
            rid = int(request.form['rec_id'])
            conn.execute("DELETE FROM recurring_expenses WHERE id=?", (rid,))
            conn.commit()
            flash("✅ Dépense récurrente supprimée.", "success")
        conn.close()
        return redirect(url_for('recurrentes'))

    recs = conn.execute("""
        SELECT r.*, c.name as cat_name, c.icon as cat_icon
        FROM recurring_expenses r
        LEFT JOIN categories c ON c.id = r.category_id
        ORDER BY r.active DESC, r.next_date
    """).fetchall()
    conn.close()
    return render_template("recurrentes.html", recs=recs, categories=categories,
                           today=datetime.now().strftime('%Y-%m-%d'))


# ── EXPORT CSV ────────────────────────────────────────────────────────────────

@app.route("/export")
def export_csv():
    import csv, io
    from flask import Response
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    conn = get_db()
    rows = conn.execute("""
        SELECT l.date, l.type, l.source, l.destination, l.amount, l.description,
               c.name as category
        FROM ledger l
        LEFT JOIN categories c ON c.id = l.category_id
        WHERE l.date LIKE ?
        ORDER BY l.date DESC, l.id DESC
    """, (f"{month}%",)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Type', 'Source', 'Destination', 'Montant (FCFA)', 'Description', 'Catégorie'])
    for r in rows:
        writer.writerow([r['date'], r['type'], r['source'], r['destination'],
                         r['amount'], r['description'] or '', r['category'] or ''])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=finances_{month}.csv'}
    )


# ── BILAN MENSUEL ─────────────────────────────────────────────────────────────

@app.route("/bilan")
@app.route("/bilan/<month>")
def bilan(month=None):
    today = datetime.now().date()
    if not month:
        month = today.strftime('%Y-%m')
    conn = get_db()

    income     = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?", (f"{month}%",)).fetchone()[0]
    expenses   = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?", (f"{month}%",)).fetchone()[0]
    epargne    = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='allocation' AND destination='reserve' AND date LIKE ?", (f"{month}%",)).fetchone()[0]

    by_cat = conn.execute("""
        SELECT c.name, c.icon, c.color, COALESCE(SUM(l.amount),0) as total
        FROM categories c
        LEFT JOIN ledger l ON l.category_id=c.id AND l.type IN ('expense','expense_reserve') AND l.date LIKE ?
        GROUP BY c.id HAVING total > 0 ORDER BY total DESC
    """, (f"{month}%",)).fetchall()

    # Mois précédent pour comparaison
    y, m = int(month[:4]), int(month[5:7])
    pm = m - 1 if m > 1 else 12
    py = y if m > 1 else y - 1
    prev_month = f"{py}-{pm:02d}"
    prev_expenses = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type IN ('expense','expense_reserve') AND date LIKE ?", (f"{prev_month}%",)).fetchone()[0]
    prev_income   = conn.execute("SELECT COALESCE(SUM(amount),0) FROM ledger WHERE type='income' AND date LIKE ?", (f"{prev_month}%",)).fetchone()[0]

    # Liste des mois disponibles
    months_available = conn.execute("""
        SELECT DISTINCT substr(date,1,7) as m FROM ledger ORDER BY m DESC LIMIT 24
    """).fetchall()

    taux_epargne = round(epargne / income * 100, 1) if income > 0 else 0
    solde_net    = round(income - expenses, 2)

    conn.close()
    return render_template("bilan.html",
                           month=month, income=round(income,2), expenses=round(expenses,2),
                           epargne=round(epargne,2), taux_epargne=taux_epargne,
                           solde_net=solde_net, by_cat=by_cat,
                           prev_month=prev_month, prev_expenses=round(prev_expenses,2),
                           prev_income=round(prev_income,2),
                           months_available=[r['m'] for r in months_available])


if __name__ == "__main__":
    init_db()
    apply_recurring_expenses()
    print("\n🚀 Application démarrée → http://127.0.0.1:8080")
    print("📱 Accès réseau local  → http://192.168.1.82:8080\n")
    app.run(host="0.0.0.0", debug=True, port=8080)
