import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)

# Setter opp banen til databasen slik at den fungerer stabilt på Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "matchday_pro.db")

# Din fungerende API-nøkkel fra Football-Data.org
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabell for alle kamper (Lageret)
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    
    # Tabell for Grupper/Kunder
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, admin_name TEXT)''')
    
    # Tabell for hvilke kamper hver gruppe har valgt til sin kuppong
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, PRIMARY KEY(group_id, fixture_id))''')
    conn.commit()
    conn.close()

# Kjører database-oppsettet ved start
init_db()

# --- SUPER ADMIN DASHBOARD ---
@app.route('/super_admin_dashboard')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    kamper = c.fetchall()
    c.execute("SELECT * FROM groups")
    grupper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=kamper, grupper=grupper)

# --- GRUPPE ADMIN (Der Kåre plukker kamper) ---
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
    
    c.execute("SELECT fixture_id FROM group_selections WHERE group_id = ?", (group[0],))
    selected_ids = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

# --- GRUPPE VEGG (Siden medlemmene ser) ---
@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group:
        conn.close()
        return "Gruppe ikke funnet", 404
    
    c.execute('''SELECT f.* FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id 
                 WHERE gs.group_id = ? ORDER BY f.date ASC''', (group[0],))
    matches = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, matches=matches)

# --- API ENDEPUNKTER ---

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.json
    name = data.get('name')
    admin = data.get('admin_name')
    slug = name.lower().replace(" ", "-")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO groups (name, slug, admin_name) VALUES (?, ?, ?)", (name, slug, admin))
        conn.commit()
        conn.close()
        return jsonify({"status": "Suksess"})
    except Exception as e:
        return jsonify({"status": str(e)}), 400

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.json
    gid = data.get('group_id')
    fid = data.get('fixture_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    if c.fetchone():
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", (gid, fid))
        action = "fjernet"
    else:
        c.execute("INSERT INTO group_selections VALUES (?, ?)", (gid, fid))
        action = "lagt til"
    conn.commit()
    conn.close()
    return jsonify({"action": action})

@app.route('/api/import_league/<string:league_code>')
def import_league(league_code):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
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
    except Exception as e:
        return jsonify({"status": str(e)}), 500

# START KOMMANDO FOR RENDER
if __name__ == '__main__':
    # Henter port fra Render, ellers bruker den 5000 lokalt
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
