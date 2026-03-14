import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Render-spesifikk banekonfigurasjon
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "matchday_pro.db")
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 1. Lageret for alle kamper fra API
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    
    # 2. Grupper / Kunder
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, admin_name TEXT)''')
    
    # 3. Valgte kamper per gruppe (med kolonne for Single-game status)
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, is_single_game INTEGER DEFAULT 0, 
                  PRIMARY KEY(group_id, fixture_id))''')
    
    # 4. Tabell for lagring av selve tipsene fra brukerne
    c.execute('''CREATE TABLE IF NOT EXISTS predictions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, fixture_id INTEGER, 
                  user_name TEXT, h_score INTEGER, b_score INTEGER, extra_data TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# --- RUTENE (SIDENE) ---

@app.route('/')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    kamper = c.fetchall()
    c.execute("SELECT * FROM groups")
    grupper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=kamper, grupper=grupper)

@app.route('/group/<slug>/admin')
def group_admin(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group:
        conn.close()
        return "Gruppe ikke funnet", 404
    
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    all_fixtures = c.fetchall()
    
    # Henter ut hvilke kamper som allerede er valgt
    c.execute("SELECT fixture_id FROM group_selections WHERE group_id = ?", (group[0],))
    selected_ids = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group:
        conn.close()
        return "Gruppe ikke funnet", 404
    
    # Henter kamper og sjekker om de er Single-game (is_single_game er m[8])
    c.execute('''SELECT f.*, gs.is_single_game FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id 
                 WHERE gs.group_id = ? ORDER BY f.date ASC''', (group[0],))
    matches = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, matches=matches)

# --- API ENDEPUNKTER (LOGIKK) ---

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.json
    name = data.get('name')
    admin = data.get('admin_name')
    slug = name.lower().replace(" ", "-").replace("æ","ae").replace("ø","o").replace("å","a")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO groups (name, slug, admin_name) VALUES (?, ?, ?)", (name, slug, admin))
        conn.commit()
        res = {"status": "Suksess"}
    except:
        res = {"status": "Slug eksisterer allerede"}
    conn.close()
    return jsonify(res)

@app.route('/api/import_league/<string:league_code>')
def import_league(league_code):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    res = requests.get(url, headers=headers).json()
    matches = res.get('matches', [])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for m in matches[:30]:
        c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                  (m['id'], league_code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], 
                   m['homeTeam']['crest'], m['awayTeam']['crest'], m['utcDate'], 'upcoming'))
    conn.commit()
    conn.close()
    return jsonify({"status": "Importert!"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.json
    gid, fid = data.get('group_id'), data.get('fixture_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    if c.fetchone():
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", (gid, fid))
        action = "fjernet"
    else:
        c.execute("INSERT INTO group_selections (group_id, fixture_id) VALUES (?, ?)", (gid, fid))
        action = "lagt til"
    conn.commit()
    conn.close()
    return jsonify({"action": action})

@app.route('/api/toggle_single_game', methods=['POST'])
def toggle_single_game():
    data = request.json
    gid, fid = data.get('group_id'), data.get('fixture_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_single_game FROM group_selections WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    row = c.fetchone()
    new_status = 0
    if row:
        new_status = 1 if row[0] == 0 else 0
        c.execute("UPDATE group_selections SET is_single_game = ? WHERE group_id = ? AND fixture_id = ?", (new_status, gid, fid))
        conn.commit()
    conn.close()
    return jsonify({"status": "oppdatert", "new_status": new_status})

# --- START SERVER ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
