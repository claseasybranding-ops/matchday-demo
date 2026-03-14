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
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT, h_score INTEGER, b_score INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, 
                  admin_name TEXT, mode TEXT DEFAULT "multi", prize_info TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, PRIMARY KEY(group_id, fixture_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, player_name TEXT, 
                  match_data TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

def get_lb(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT player_name, match_data FROM bets WHERE group_id = ?", (group_id,))
    bets = c.fetchall()
    c.execute('''SELECT f.id, f.h_score, f.b_score FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id WHERE gs.group_id = ?''', (group_id,))
    res = {r[0]: {'h': r[1], 'b': r[2]} for r in c.fetchall()}
    lb = []
    for name, m_json in bets:
        pts = 0
        try:
            for tip in json.loads(m_json):
                m_id = int(tip['match_id'])
                if m_id in res and res[m_id]['h'] is not None:
                    ah, ab = res[m_id]['h'], res[m_id]['b']
                    th, ta = int(tip['h']), int(tip['a'])
                    if th == ah and ta == ab: pts += 3
                    elif (th > ta and ah > ab) or (th < ta and ah < ab) or (th == ta and ah == ab): pts += 1
        except: pass
        lb.append({'name': name, 'points': pts})
    conn.close()
    return sorted(lb, key=lambda x: x['points'], reverse=True)

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
    c.execute("SELECT fixture_id FROM group_selections WHERE group_id = ?", (group[0],))
    sel_ids = [r[0] for r in c.fetchall()]
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    all_f = c.fetchall()
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_f, selected_ids=sel_ids)

@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    c.execute('''SELECT f.* FROM fixtures f JOIN group_selections gs ON f.id = gs.fixture_id WHERE gs.group_id = ?''', (group[0],))
    matches = c.fetchall()
    leaderboard = get_lb(group[0])
    conn.close()
    return render_template('group_view.html', group=group, matches=matches, leaderboard=leaderboard)

@app.route('/api/admin_push_scores', methods=['POST'])
def admin_push_scores():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for m in data['scores']:
        c.execute("UPDATE fixtures SET h_score = ?, b_score = ? WHERE id = ?", (m['h'], m['b'], m['match_id']))
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
        c.execute("INSERT INTO groups (name, slug, admin_name) VALUES (?, ?, ?)", (data['name'], slug, data['admin_name']))
        conn.commit()
        return jsonify({"status": "Suksess"})
    except:
        return jsonify({"status": "Navnet er opptatt"})
    finally: conn.close()

@app.route('/api/import_league/<string:code>')
def import_league(code):
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    res = requests.get(url, headers=headers).json()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for m in res.get('matches', []):
        c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, h_navn, b_navn, h_logo, b_logo, date, status) VALUES (?,?,?,?,?,?,?,?)", 
                  (m['id'], code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], m['homeTeam']['crest'], m['awayTeam']['crest'], m['utcDate'], 'upcoming'))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", (data['mode'], data['prize_info'], data['group_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    if c.fetchone():
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    else:
        c.execute("INSERT INTO group_selections (group_id, fixture_id) VALUES (?, ?)", (data['group_id'], data['fixture_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/submit_bet', methods=['POST'])
def submit_bet():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO bets (group_id, player_name, match_data) VALUES (?, ?, ?)", (data['group_id'], data['player_name'], json.dumps(data['matches'])))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
