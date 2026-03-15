import os
import sqlite3
import requests
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

DB_PATH = 'matchday_pro.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id INTEGER, home_team TEXT, 
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

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date DESC")
    kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "Siden finnes ikke", 404
    c.execute("""SELECT f.* FROM fixtures f 
                 JOIN group_matches gm ON f.id = gm.fixture_id 
                 WHERE gm.group_id = ?""", (group[0],))
    kamper = c.fetchall()
    c.execute("""SELECT user_name, SUM(points) as total FROM bets 
                 WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC""", (group_id_str,))
    leaderboard = c.fetchall()
    conn.close()
    return render_template('group_view.html', group_id=group_id_str, group=group, kamper=kamper, leaderboard=leaderboard)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT * FROM fixtures ORDER BY date DESC LIMIT 30")
    all_fixtures = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    selected_ids = [r[0] for r in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

# --- API (Denne er nå oppdatert for å garantert finne kamper) ---
@app.route('/api/import_league/<code>')
def import_league(code):
    l_id = 39 # Premier League
    # Vi fjerner "season" og bruker "next=20" for å hente de kommende kampene
    url = f"https://v3.football.api-sports.io/fixtures?league={l_id}&next=20&timezone=Europe/Oslo"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        res = requests.get(url, headers=headers).json()
        fixtures = res.get('response', [])
        
        if not fixtures:
            # Hvis "next" er tom, prøver vi å hente dagens kamper i stedet
            url = f"https://v3.football.api-sports.io/fixtures?league={l_id}&date=2026-03-15"
            res = requests.get(url, headers=headers).json()
            fixtures = res.get('response', [])

        conn = get_db()
        c = conn.cursor()
        for f in fixtures:
            c.execute("""INSERT OR REPLACE INTO fixtures 
                (id, league_id, home_team, away_team, home_logo, away_logo, date, status) 
                VALUES (?,?,?,?,?,?,?,?)""",
                (f['fixture']['id'], l_id, f['teams']['home']['name'], f['teams']['away']['name'],
                 f['teams']['home']['logo'], f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {len(fixtures)} kamper."})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    name = data.get('name')
    admin = data.get('admin_name')
    gid = name.lower().replace(" ", "-").replace("æ","ae").replace("ø","o").replace("å","aa")
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (name, gid, admin))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.get_json()
    gid, fid = data.get('group_id'), data.get('fixture_id')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    if c.fetchone():
        c.execute("DELETE FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    else:
        c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (gid, fid))
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/admin_push_scores', methods=['POST'])
def admin_push_scores():
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    for s in data.get('scores', []):
        c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = 'finished' WHERE id = ?", (s['h'], s['b'], s['match_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
