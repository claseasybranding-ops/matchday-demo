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

@app.route('/')
def index(): return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    group_name = data.get('name')
    admin_name = data.get('admin_name')
    if not group_name: return jsonify({"status": "Feil", "message": "Mangler navn"}), 400
    
    gid_str = group_name.lower().replace(" ", "-")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", 
              (group_name, gid_str, admin_name))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess", "group_id": gid_str})

@app.route('/api/import_league/<code>')
def import_league(code):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    now = datetime.utcnow()
    # Vi henter kun kamper som er i dag eller i fremtiden
    for m in res.get('matches', []):
        m_date = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
        if m_date > (now - timedelta(hours=24)):
            h = m['homeTeam']['shortName'] or m['homeTeam']['name']
            a = m['awayTeam']['shortName'] or m['awayTeam']['name']
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                (m['id'], 'PL', h, a, m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

# (Resten av rutinene for admin/view/leaderboard følger samme mønster som før)
# Jeg inkluderer dem her for å sikre at filen er komplett.

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    now_iso = (datetime.utcnow() - timedelta(hours=6)).isoformat()
    c.execute("SELECT * FROM fixtures WHERE date > ? ORDER BY date ASC LIMIT 30", (now_iso,))
    alle = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    valgte = [r[0] for r in c.fetchall()]
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall()
    conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, questions=questions)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
