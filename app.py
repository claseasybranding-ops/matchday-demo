import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_final_v3_key"

DB_PATH = 'matchday_v3.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id TEXT, home_team TEXT, 
                  away_team TEXT, home_logo TEXT, away_logo TEXT, 
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, group_id_str TEXT, 
                  admin_name TEXT, mode TEXT DEFAULT 'multi', prize_info TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_matches
                 (group_id INTEGER, fixture_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0, golden_goal INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extra_questions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, fixture_id INTEGER, 
                  question_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extra_bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  question_id INTEGER, user_answer TEXT)''')
    conn.commit(); conn.close()

init_db()

def update_points_logic():
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        if 'matches' not in res: return False
        conn = get_db(); c = conn.cursor()
        now = datetime.utcnow()
        for m in res.get('matches', []):
            mid = m['id']
            h_act = m['score']['fullTime']['home']
            a_act = m['score']['fullTime']['away']
            status = m['status'].lower()
            m_time = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
            if status in ['finished', 'live', 'in_play', 'paused'] or now > m_time:
                h_score = h_act if h_act is not None else 0
                a_score = a_act if a_act is not None else 0
                c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = ? WHERE id = ?", (h_score, a_score, status, mid))
                c.execute("SELECT id, home_score, away_score FROM bets WHERE fixture_id = ?", (mid,))
                for bet_id, u_h, u_a in c.fetchall():
                    pts = 0
                    if u_h == h_score and u_a == a_score: pts = 3
                    elif (u_h > u_a and h_score > a_score) or (u_h < u_a and h_score < a_score) or (u_h == u_a and h_score == a_score): pts = 1
                    c.execute("UPDATE bets SET points = ? WHERE id = ?", (pts, bet_id))
        conn.commit(); conn.close()
        return True
    except: return False

@app.route('/')
def index(): return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    # Henter kamper, men viser kun de som er i fremtiden eller nylig startet
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    # Her filtrerer vi knallhardt på dato for å slippe rot
    now_iso = (datetime.utcnow() - timedelta(hours=3)).isoformat()
    c.execute("SELECT * FROM fixtures WHERE date > ? ORDER BY date ASC LIMIT 20", (now_iso,))
    alle = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    valgte = [r[0] for r in c.fetchall()]
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall()
    conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, questions=questions)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); m_time = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = m_time.strftime("%H:%M"); kamper.append(f_l)
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, kamper=kamper, questions=questions)

@app.route('/api/import_league/<code>')
def import_league(code):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    now = datetime.utcnow()
    for m in res.get('matches', []):
        m_date = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
        # VIKTIG: Vi importerer kun kamper som ikke er ferdigspilt (fra i dag og fremover)
        if m_date > (now - timedelta(days=1)):
            h = m['homeTeam']['shortName'] or m['homeTeam']['name']
            a = m['awayTeam']['shortName'] or m['awayTeam']['name']
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                (m['id'], 'PL', h, a, m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

# ... (Resten av API-rutene forblir som før)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
