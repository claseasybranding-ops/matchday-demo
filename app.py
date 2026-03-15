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
    # Tabell for alle kamper fra API
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id INTEGER, home_team TEXT, 
                  away_team TEXT, home_logo TEXT, away_logo TEXT, 
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER)''')
    # Tabell for supporterklubber/kunder
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, group_id_str TEXT, 
                  admin_name TEXT, mode TEXT DEFAULT 'multi', prize_info TEXT)''')
    # Tabell for hvilke kamper hver gruppe har valgt
    c.execute('''CREATE TABLE IF NOT EXISTS group_matches
                 (group_id INTEGER, fixture_id INTEGER)''')
    # Tabell for tips/bets
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- HJELPEFUNKSJON: POENG-LOGIKK ---
def calc_points(u_h, u_a, a_h, a_a):
    if a_h is None or a_a is None: return 0
    if int(u_h) == int(a_h) and int(u_a) == int(a_a): return 3
    u_res = "H" if int(u_h) > int(u_a) else ("B" if int(u_h) < int(u_a) else "U")
    a_res = "H" if int(a_h) > int(a_a) else ("B" if int(a_h) < int(a_a) else "U")
    return 1 if u_res == a_res else 0

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
    c.execute("SELECT * FROM fixtures ORDER BY date DESC LIMIT 20")
    kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db()
    c = conn.cursor()
    # Finn gruppen
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "Gruppe ikke funnet", 404
    
    # Finn valgte kamper for denne gruppen
    c.execute("""SELECT f.* FROM fixtures f 
                 JOIN group_matches gm ON f.id = gm.fixture_id 
                 WHERE gm.group_id = ?""", (group[0],))
    kamper = c.fetchall()
    
    # Leaderboard
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
    
    c.execute("SELECT * FROM fixtures ORDER BY date DESC LIMIT 20")
    all_fixtures = c.fetchall()
    
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    selected_ids = [r[0] for r in c.fetchall()]
    
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

# --- API ---

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    name = data.get('name')
    admin = data.get('admin_name')
    gid = name.lower().replace(" ", "-")
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (name, gid, admin))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/import_league/<code>')
def import_league(code):
    # Enkel mapping: PL = 39 (Premier League)
    l_id = 39 if code == 'PL' else 39
    url = f"https://v3.football.api-sports.io/fixtures?league={l_id}&season=2025&next=15"
    headers = {'x-apisports-key': API_KEY}
    res = requests.get(url, headers=headers).json()
    for f in res.get('response', []):
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO fixtures (id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?)",
                  (f['fixture']['id'], f['teams']['home']['name'], f['teams']['away']['name'], f['teams']['home']['logo'], f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
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
    for s in data.get('scores', []):
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = 'finished' WHERE id = ?", (s['h'], s['b'], s['match_id']))
        # Oppdater poeng for alle som har tippet på denne kampen
        c.execute("SELECT id, home_score, away_score FROM bets WHERE fixture_id = ?", (s['match_id'],))
        for b_id, u_h, u_a in c.fetchall():
            pts = calc_points(u_h, u_a, s['h'], s['b'])
            c.execute("UPDATE bets SET points = ? WHERE id = ?", (pts, b_id))
        conn.commit()
    return jsonify({"status": "Suksess"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
