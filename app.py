import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import os
import json

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "matchday_pro.db")
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Hovedtabeller
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, 
                  admin_name TEXT, mode TEXT DEFAULT "multi", prize_info TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, PRIMARY KEY(group_id, fixture_id))''')

    # NY TABELL: bets (Lagrer supporterens tips)
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  group_id INTEGER, 
                  player_name TEXT, 
                  match_data TEXT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Sikkerhetssjekk for prize_info
    try:
        c.execute("ALTER TABLE groups ADD COLUMN prize_info TEXT")
    except:
        pass

    conn.commit()
    conn.close()

init_db()

# --- HOVEDSIDER ---

@app.route('/')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    fixtures = c.fetchall()
    c.execute("SELECT * FROM groups")
    groups = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=fixtures, grupper=groups)

@app.route('/group/<slug>/admin')
def group_admin(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group: return "Gruppe ikke funnet", 404
        
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    all_f = c.fetchall()
    
    c.execute("SELECT fixture_id FROM group_selections WHERE group_id = ?", (group[0],))
    sel_ids = [r[0] for r in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_f, selected_ids=sel_ids)

@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group: return "Gruppe ikke funnet", 404

    c.execute('''SELECT f.* FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id 
                 WHERE gs.group_id = ?''', (group[0],))
    matches = c.fetchall()
    
    # Hent alle eksisterende bets for leaderboardet
    c.execute("SELECT player_name, match_data FROM bets WHERE group_id = ? ORDER BY timestamp DESC", (group[0],))
    existing_bets = c.fetchall()
    conn.close()
    
    return render_template('group_view.html', group=group, matches=matches, leaderboard=existing_bets)

# --- API ENDEPUNKTER ---

@app.route('/api/submit_bet', methods=['POST'])
def submit_bet():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Vi lagrer match_data som en JSON-streng for å være fleksible
    # Dette inneholder score, straffer, rødt kort og golden goal
    match_json = json.dumps(data['matches'])
    
    c.execute("INSERT INTO bets (group_id, player_name, match_data) VALUES (?, ?, ?)", 
              (data['group_id'], data['player_name'], match_json))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "message": "Tips lagret!"})

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", 
              (data['mode'], data['prize_info'], data['group_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT mode FROM groups WHERE id = ?", (data['group_id'],))
    mode = c.fetchone()[0]
    
    if mode == 'single':
        c.execute("DELETE FROM group_selections WHERE group_id = ?", (data['group_id'],))
    
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", 
              (data['group_id'], data['fixture_id']))
    
    if c.fetchone():
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", 
                  (data['group_id'], data['fixture_id']))
    else:
        c.execute("INSERT INTO group_selections (group_id, fixture_id) VALUES (?, ?)", 
                  (data['group_id'], data['fixture_id']))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.json
    slug = data['name'].lower().strip().replace(" ", "-").replace("æ","ae").replace("ø","o").replace("å","a")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO groups (name, slug, admin_name) VALUES (?, ?, ?)", 
                  (data['name'], slug, data['admin_name']))
        conn.commit()
        status = "Suksess"
    except:
        status = "Feil: Navnet er opptatt"
    conn.close()
    return jsonify({"status": status})

@app.route('/api/import_league/<string:code>')
def import_league(code):
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    res = requests.get(url, headers=headers).json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for m in res.get('matches', []):
        c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)", 
                  (m['id'], code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], 
                   m['homeTeam']['crest'], m['awayTeam']['crest'], m['utcDate'], 'upcoming'))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
