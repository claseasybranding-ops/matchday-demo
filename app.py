import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_final_v6_solid"

DB_PATH = 'matchday_v3.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    # Kamp-lager
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id TEXT, home_team TEXT, away_team TEXT, 
                  home_logo TEXT, away_logo TEXT, date TEXT, status TEXT, 
                  home_actual INTEGER, away_actual INTEGER, first_goal_min INTEGER DEFAULT NULL)''')
    
    # Grupper
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, group_id_str TEXT, 
                  admin_name TEXT, mode TEXT DEFAULT 'multi', prize_info TEXT)''')
    
    # Brukertabell
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_name TEXT UNIQUE, 
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Medlemskap
    c.execute('''CREATE TABLE IF NOT EXISTS memberships
                 (user_id INTEGER, group_id_str TEXT, PRIMARY KEY (user_id, group_id_str))''')

    # Kamp-kobling
    c.execute('''CREATE TABLE IF NOT EXISTS group_matches
                 (group_id_str TEXT, fixture_id INTEGER)''')

    # Tips
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_id INTEGER, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0, golden_goal INTEGER)''')
    
    # Tilleggsspørsmål
    c.execute('''CREATE TABLE IF NOT EXISTS extra_questions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, fixture_id INTEGER, question_text TEXT)''')
    
    # Svar på tilleggsspørsmål
    c.execute('''CREATE TABLE IF NOT EXISTS extra_bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_id INTEGER, 
                  question_id INTEGER, user_answer TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- HJELPEFUNKSJONER ---

def get_or_create_user(name):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE user_name = ?", (name,))
    user = c.fetchone()
    if user:
        uid = user[0]
    else:
        c.execute("INSERT INTO users (user_name) VALUES (?)", (name,))
        uid = c.lastrowid
    conn.commit(); conn.close()
    return uid

def get_round_start(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("""
        SELECT MIN(f.date) FROM fixtures f 
        JOIN group_matches gm ON f.id = gm.fixture_id 
        WHERE gm.group_id_str = ?""", (group_id_str,))
    res = c.fetchone()[0]
    conn.close()
    if res:
        return datetime.fromisoformat(res.replace('Z', '+00:00')).replace(tzinfo=None)
    return None

def get_players_from_api(fixture_id):
    headers = {'X-Auth-Token': API_KEY}
    players = []
    try:
        res = requests.get(f"https://api.football-data.org/v4/matches/{fixture_id}", headers=headers, timeout=5).json()
        for team in ['homeTeam', 'awayTeam']:
            t_id = res[team]['id']
            t_name = res[team]['shortName']
            s_res = requests.get(f"https://api.football-data.org/v4/teams/{t_id}", headers=headers, timeout=5).json()
            for p in s_res.get('squad', []):
                players.append({'name': p['name'], 'team': t_name})
    except: pass
    return players

def update_points_logic():
    """Oppdatert motor: Legger sammen poeng (+=) og håndterer GG nærmest (+2p)."""
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT DISTINCT league_id FROM fixtures")
    leagues = [row[0] for row in c.fetchall()]
    headers = {'X-Auth-Token': API_KEY}
    now = datetime.utcnow()

    for league in leagues:
        try:
            url = f"https://api.football-data.org/v4/competitions/{league}/matches"
            res = requests.get(url, headers=headers).json()
            if 'matches' not in res: continue
            
            for m in res.get('matches', []):
                mid = m['id']
                h_act = m['score']['fullTime']['home']
                a_act = m['score']['fullTime']['away']
                status = m['status'].lower()
                m_time = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
                
                if status in ['finished', 'live', 'in_play'] or now > m_time:
                    h_score = h_act if h_act is not None else 0
                    a_score = a_act if a_act is not None else 0
                    f_goal = 25 if (h_score + a_score > 0) else 0 # Demo-verdi
                    
                    c.execute("UPDATE fixtures SET home_actual=?, away_actual=?, status=?, first_goal_min=? WHERE id=?", 
                             (h_score, a_score, status, f_goal, mid))
                    
                    c.execute("SELECT id, user_id, home_score, away_score, golden_goal, group_id_str FROM bets WHERE fixture_id=?", (mid,))
                    for bet_id, uid, u_h, u_a, u_gg, gid in c.fetchall():
                        total_pts = 0
                        # 1. Resultat (3p) / HUB (1p)
                        if u_h == h_score and u_a == a_score: total_pts += 3
                        elif (u_h > u_a and h_score > a_score) or (u_h < u_a and h_score < a_score) or (u_h == u_a and h_score == a_score): total_pts += 1
                        
                        # 2. Tilleggsspørsmål (Målscorer etc) -> +2p
                        c.execute("""SELECT eb.user_answer FROM extra_bets eb 
                                     JOIN extra_questions eq ON eb.question_id = eq.id 
                                     WHERE eb.user_id = ? AND eq.fixture_id = ?""", (uid, mid))
                        ans = c.fetchone()
                        if ans and ans[0] == 'JA' and (h_score + a_score > 0): total_pts += 2

                        # 3. Golden Goal Spot On (+5p)
                        if f_goal > 0 and u_gg == f_goal: total_pts += 5
                        
                        c.execute("UPDATE bets SET points=? WHERE id=?", (total_pts, bet_id))

                    # 4. Golden Goal Nærmest (+2p) - Kun når ferdig
                    if status == 'finished' and f_goal > 0:
                        c.execute("SELECT DISTINCT group_id_str FROM bets WHERE fixture_id=?", (mid,))
                        for (g_id,) in c.fetchall():
                            c.execute("SELECT MIN(ABS(golden_goal - ?)) FROM bets WHERE fixture_id=? AND group_id_str=? AND golden_goal != ?", (f_goal, mid, g_id, f_goal))
                            min_diff = c.fetchone()[0]
                            if min_diff is not None:
                                c.execute("""UPDATE bets SET points = points + 2 
                                             WHERE fixture_id=? AND group_id_str=? AND ABS(golden_goal - ?) = ? AND golden_goal != ?""", 
                                          (mid, g_id, f_goal, min_diff, f_goal))
        except: continue
    conn.commit(); conn.close()

# --- RUTENE ---

@app.route('/')
def index(): return render_template('index.html')

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id_str = ?", (group_id_str,))
    raw = c.fetchall(); kamper = []
    round_start = get_round_start(group_id_str)
    is_locked = (datetime.utcnow() > round_start) if round_start else False
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall(); conn.close()
    return render_template('group_view.html', group=group, kamper=kamper, questions=questions, is_locked=is_locked)

@app.route('/group/<group_id_str>/leaderboard')
def leaderboard(group_id_str):
    update_points_logic()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    rs = get_round_start(group_id_str)
    rs_str = rs.strftime("%d.%m kl %H:%M") if rs else "--:--"
    c.execute("""SELECT u.user_name, SUM(b.points) as total FROM bets b 
                 JOIN users u ON b.user_id = u.id WHERE b.group_id_str = ? 
                 GROUP BY u.user_name ORDER BY total DESC, u.user_name ASC""", (group_id_str,))
    rows = c.fetchall(); conn.close()
    return render_template('leaderboard.html', group=group, leaderboard=rows, start_time=rs_str)

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json(); g_id = data['group_id']
    u_id = get_or_create_user(data['user_name'].strip())
    rs = get_round_start(g_id)
    if rs and datetime.utcnow() > rs: return jsonify({"status": "LOCKED"}), 403
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO memberships (user_id, group_id_str) VALUES (?, ?)", (u_id, g_id))
    c.execute("DELETE FROM bets WHERE group_id_str = ? AND user_id = ?", (g_id, u_id))
    for t in data['tips']:
        c.execute("INSERT INTO bets (group_id_str, user_id, fixture_id, home_score, away_score, golden_goal) VALUES (?,?,?,?,?,?)", 
                 (g_id, u_id, int(t['match_id']), int(t['h']), int(t['a']), data.get('golden_goal', 0)))
    if 'extras' in data:
        c.execute("DELETE FROM extra_bets WHERE group_id_str = ? AND user_id = ?", (g_id, u_id))
        for qid, val in data['extras'].items():
            c.execute("INSERT INTO extra_bets (group_id_str, user_id, question_id, user_answer) VALUES (?,?,?,?)", (g_id, u_id, int(qid), val))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups"); grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC"); raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/api/import_league/<league_code>')
def import_league(league_code):
    """Henter kun aktuelle kamper (14 dager frem)."""
    start_date = datetime.utcnow().strftime('%Y-%m-%d')
    end_date = (datetime.utcnow() + timedelta(days=14)).strftime('%Y-%m-%d')
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?dateFrom={start_date}&dateTo={end_date}"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM fixtures"); c.execute("DELETE FROM group_matches")
    for m in res.get('matches', []):
        if m['status'] in ['TIMED', 'SCHEDULED']:
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                (m['id'], league_code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC"); alle = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id_str = ?", (group_id_str,))
    valgte = [r[0] for r in c.fetchall()]
    players = get_players_from_api(valgte[0]) if valgte else []
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall(); conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, questions=questions, players=players)

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.get_json(); conn = get_db(); c = conn.cursor()
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE group_id_str = ?", (data.get('mode', 'multi'), data.get('prize', ''), data['group_id_str']))
    c.execute("DELETE FROM group_matches WHERE group_id_str = ?", (data['group_id_str'],))
    for mid in data['matches']:
        c.execute("INSERT INTO group_matches (group_id_str, fixture_id) VALUES (?, ?)", (data['group_id_str'], int(mid)))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/add_smart_question', methods=['POST'])
def add_smart_question():
    data = request.get_json(); conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO extra_questions (group_id_str, fixture_id, question_text) VALUES (?,?,?)", (data['group_id_str'], data['match_id'], data['text']))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/delete_question', methods=['POST'])
def delete_question():
    data = request.get_json(); conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM extra_questions WHERE id = ?", (data['q_id'],))
    c.execute("DELETE FROM extra_bets WHERE question_id = ?", (data['q_id'],)) 
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json(); gid_str = data['name'].lower().replace(" ", "-")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (data['name'], gid_str, data['admin_name']))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/get_user_bets/<group_id_str>/<user_name>')
def get_user_bets(group_id_str, user_name):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE user_name = ?", (user_name,))
    uid_res = c.fetchone()
    if not uid_res: return jsonify({'main': [], 'extras': []})
    uid = uid_res[0]
    c.execute("SELECT b.home_score, b.away_score, b.points, b.golden_goal, f.home_team, f.away_team, f.home_logo, f.away_logo FROM bets b JOIN fixtures f ON b.fixture_id = f.id WHERE b.group_id_str = ? AND b.user_id = ?", (group_id_str, uid))
    main = c.fetchall()
    c.execute("SELECT q.question_text, eb.user_answer FROM extra_bets eb JOIN extra_questions q ON eb.question_id = q.id WHERE eb.group_id_str = ? AND eb.user_id = ?", (group_id_str, uid))
    extras = c.fetchall(); conn.close()
    return jsonify({
        'main': [{'h': b[0], 'a': b[1], 'pts': b[2], 'gg': b[3], 'ht': b[4], 'at': b[5], 'hl': b[6], 'al': b[7]} for b in main],
        'extras': [{'q': e[0], 'ans': e[1]} for e in extras]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
