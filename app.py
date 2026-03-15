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

def update_points_logic():
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        if 'matches' not in res: return False
        conn = get_db(); c = conn.cursor()
        now = datetime.utcnow()
        for m in res.get('matches', []):
            mid = m['id']
            h_act = m['score']['fullTime']['home']
            a_act = m['score']['fullTime']['away']
            status = m['status'].lower()
            m_time = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
            if status in ['finished', 'live', 'in_play', 'paused'] or now > m_time:
                h_score = h_act if h_act is not None else 0
                a_score = a_act if a_act is not None else 0
                c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = ? WHERE id = ?", (h_score, a_score, status, mid))
                c.execute("SELECT id, home_score, away_score FROM bets WHERE fixture_id = ?", (mid,))
                for bet_id, u_h, u_a in c.fetchall():
                    pts = 0
                    if u_h == h_score and u_a == a_score: pts = 3
                    elif (u_h > u_a and h_score > a_score) or (u_h < u_a and h_score < a_score) or (u_h == u_a and h_score == a_score): pts = 1
                    c.execute("UPDATE bets SET points = ? WHERE id = ?", (pts, bet_id))
        conn.commit(); conn.close()
        return True
    except: return False

def get_players(fixture_id):
    headers = {'X-Auth-Token': API_KEY}
    try:
        res = requests.get(f"https://api.football-data.org/v4/matches/{fixture_id}", headers=headers).json()
        players = []
        for team_key in ['homeTeam', 'awayTeam']:
            t_id = res[team_key]['id']
            t_res = requests.get(f"https://api.football-data.org/v4/teams/{t_id}", headers=headers).json()
            for p in t_res.get('squad', []):
                players.append({'id': p['id'], 'name': p['name'], 'team': res[team_key]['shortName']})
        return players
    except: return []

@app.route('/')
def index(): return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall(); c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

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
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall()
    conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, players=players, questions=questions)

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

@app.route('/group/<group_id_str>/leaderboard')
def leaderboard(group_id_str):
    update_points_logic()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT user_name, SUM(points) as total FROM bets WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC", (group_id_str,))
    rows = c.fetchall(); conn.close()
    return render_template('leaderboard.html', group=group, leaderboard=rows)

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM groups WHERE group_id_str = ?", (data['group_id_str'],))
    gid = c.fetchone()[0]
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", (data['mode'], data['prize'], gid))
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

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    gid = data['name'].lower().replace(" ", "-")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (data['name'], gid, data['admin_name']))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/import_league/<code>')
def import_league(code):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    for m in res.get('matches', []):
        h = m['homeTeam']['shortName'] or m['homeTeam']['name']
        a = m['awayTeam']['shortName'] or m['awayTeam']['name']
        c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
            (m['id'], 'PL', h, a, m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/refresh_data')
def refresh_data():
    success = update_points_logic()
    return jsonify({"status": "OK" if success else "Error"})

@app.route('/api/get_user_bets/<group_id_str>/<user_name>')
def get_user_bets(group_id_str, user_name):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT b.home_score, b.away_score, b.points, f.home_team, f.away_team, f.home_logo, f.away_logo FROM bets b JOIN fixtures f ON b.fixture_id = f.id WHERE b.group_id_str = ? AND b.user_name = ?", (group_id_str, user_name))
    bets = c.fetchall(); conn.close()
    return jsonify([{'home_score': b[0], 'away_score': b[1], 'points': b[2], 'home_team': b[3], 'away_team': b[4], 'home_logo': b[5], 'away_logo': b[6]} for b in bets])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
