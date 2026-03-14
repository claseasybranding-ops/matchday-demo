import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "matchday_pro.db")
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS fixtures (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, admin_name TEXT, mode TEXT DEFAULT "multi")')
    c.execute('CREATE TABLE IF NOT EXISTS group_selections (group_id INTEGER, fixture_id INTEGER, PRIMARY KEY(group_id, fixture_id))')
    conn.commit()
    conn.close()

init_db()

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
    c.execute('SELECT f.* FROM fixtures f JOIN group_selections gs ON f.id = gs.fixture_id WHERE gs.group_id = ?', (group[0],))
    matches = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, matches=matches)

@app.route('/api/import_league/<string:league_code>')
def import_league(league_code):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for m in res.get('matches', []):
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)", 
                      (m['id'], league_code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], 
                       m['homeTeam']['crest'], m['awayTeam']['crest'], m['utcDate'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": "Suksess"})
    except Exception as e:
        return jsonify({"status": str(e)}), 500

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
        return jsonify({"status": "Suksess"})
    except:
        return jsonify({"status": "Navnet er opptatt"}), 400
    finally:
        conn.close()

@app.route('/api/set_mode', methods=['POST'])
def set_mode():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE groups SET mode = ? WHERE id = ?", (data['mode'], data['group_id']))
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
    
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    if c.fetchone():
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    else:
        if mode == 'single':
            c.execute("DELETE FROM group_selections WHERE group_id = ?", (data['group_id'],))
        c.execute("INSERT INTO group_selections (group_id, fixture_id) VALUES (?, ?)", (data['group_id'], data['fixture_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
