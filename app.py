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
                  question_text TEXT, q_type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extra_bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  question_id INTEGER, user_answer TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- HJELPEFUNKSJON FOR Å HENTE SPILLERE ---
def get_players(fixture_id):
    headers = {'X-Auth-Token': API_KEY}
    # Vi henter kampdetaljer for å finne lag-IDene
    res = requests.get(f"https://api.football-data.org/v4/matches/{fixture_id}", headers=headers).json()
    players = []
    try:
        for team_key in ['homeTeam', 'awayTeam']:
            t_id = res[team_key]['id']
            t_res = requests.get(f"https://api.football-data.org/v4/teams/{t_id}", headers=headers).json()
            for p in t_res.get('squad', []):
                players.append({'id': p['id'], 'name': p['name'], 'team': res[team_key]['shortName']})
    except: pass
    return players

@app.route('/')
def index(): return render_template('index.html')

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

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    alle = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    valgte = [r[0] for r in c.fetchall()]
    
    players = []
    if group[4] == 'single' and valgte:
        players = get_players(valgte[0])
        
    conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, players=players)

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM groups WHERE group_id_str = ?", (data['group_id_str'],))
    gid = c.fetchone()[0]
    c.execute("UPDATE groups SET mode = ? WHERE id = ?", (data['mode'], gid))
    c.execute("DELETE FROM group_matches WHERE group_id = ?", (gid,))
    for mid in data['matches']:
        c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (gid, int(mid)))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/add_smart_question', methods=['POST'])
def add_smart_question():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO extra_questions (group_id_str, fixture_id, question_text) VALUES (?,?,?)",
              (data['group_id_str'], data['match_id'], data['text']))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM bets WHERE group_id_str = ? AND user_name = ?", (data['group_id'], data['user_name']))
    for t in data['tips']:
        c.execute("INSERT INTO bets (group_id_str, user_name, fixture_id, home_score, away_score, golden_goal) VALUES (?,?,?,?,?,?)",
                  (data['group_id'], data['user_name'], int(t['match_id']), int(t['h']), int(t['a']), data.get('golden_goal', 0)))
    
    if 'extras' in data:
        c.execute("DELETE FROM extra_bets WHERE group_id_str = ? AND user_name = ?", (data['group_id'], data['user_name']))
        for q_id, val in data['extras'].items():
            c.execute("INSERT INTO extra_bets (group_id_str, user_name, question_id, user_answer) VALUES (?,?,?,?)",
                      (data['group_id'], data['user_name'], int(q_id), val))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

# ... (Inkluder import_league og super_admin fra forrige versjon)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
