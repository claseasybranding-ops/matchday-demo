import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

DB_PATH = 'matchday_pro.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def format_date(iso_date):
    try:
        iso_date = iso_date.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m kl %H:%M")
    except:
        return iso_date

def init_db():
    conn = get_db()
    c = conn.cursor()
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
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- DASHBOARDS ---

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw_fixtures = c.fetchall()
    kamper = []
    for f in raw_fixtures:
        f_list = list(f); f_list[6] = format_date(f[6]); kamper.append(f_list)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "Gruppen ble ikke funnet", 404
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw_fixtures = c.fetchall()
    all_fixtures = []
    for f in raw_fixtures:
        f_list = list(f); f_list[6] = format_date(f[6]); all_fixtures.append(f_list)
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    selected_ids = [r[0] for r in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "Siden finnes ikke", 404
    
    # Henter de valgte kampene
    c.execute("""SELECT f.* FROM fixtures f 
                 JOIN group_matches gm ON f.id = gm.fixture_id 
                 WHERE gm.group_id = ?""", (group[0],))
    raw_fixtures = c.fetchall()
    kamper = []
    for f in raw_fixtures:
        f_list = list(f); f_list[6] = format_date(f[6]); kamper.append(f_list)
    
    # Leaderboard
    c.execute("""SELECT user_name, SUM(points) as total FROM bets 
                 WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC""", (group_id_str,))
    leaderboard = c.fetchall()
    conn.close()
    return render_template('group_view.html', group_id=group_id_str, group=group, kamper=kamper, leaderboard=leaderboard)

# --- API HANDLERS ---

@app.route('/api/update_group_settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    gid_int = data.get('group_id')
    mode = data.get('mode')
    prize = data.get('prize_info')
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", (mode, prize, gid_int))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json()
    group_id_str = data.get('group_id')
    user = data.get('user_name', 'Anonym')
    tips = data.get('tips', [])
    conn = get_db(); c = conn.cursor()
    for t in tips:
        c.execute("""INSERT OR REPLACE INTO bets (group_id_str, user_name, fixture_id, home_score, away_score) 
                     VALUES (?, ?, ?, ?, ?)""", 
                  (group_id_str, user, t['match_id'], t['h'], t['a']))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/import_league/<code>')
def import_league(code):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    matches = res.get('matches', [])
    conn = get_db(); c = conn.cursor()
    for m in matches:
        if m['status'] in ['SCHEDULED', 'TIMED', 'LIVE']:
            home = m['homeTeam']['shortName'] or m['homeTeam']['name']
            away = m['awayTeam']['shortName'] or m['awayTeam']['name']
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                (m['id'], 'PL', home, away, m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    name = data.get('name'); admin = data.get('admin_name')
    gid = name.lower().replace(" ", "-")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (name, gid, admin))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.get_json()
    gid, fid = data.get('group_id'), data.get('fixture_id')
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    if c.fetchone(): c.execute("DELETE FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    else: c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (gid, fid))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/')
def index(): return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
