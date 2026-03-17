import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_ultimate_v10_final_fix"

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
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER,
                  first_goal_min INTEGER DEFAULT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, group_id_str TEXT, 
                  admin_name TEXT, mode TEXT DEFAULT 'multi', prize_info TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_matches
                 (group_id INTEGER, fixture_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0, 
                  golden_goal INTEGER, last_rank INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extra_questions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, fixture_id INTEGER, 
                  question_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS extra_bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  question_id INTEGER, user_answer TEXT)''')
    try:
        c.execute("ALTER TABLE bets ADD COLUMN last_rank INTEGER DEFAULT 0")
    except:
        pass
    conn.commit(); conn.close()

init_db()

# --- HJELPEFUNKSJONER ---

def get_round_start(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("""
        SELECT MIN(f.date) FROM fixtures f 
        JOIN group_matches gm ON f.id = gm.fixture_id 
        JOIN groups g ON gm.group_id = g.id 
        WHERE g.group_id_str = ?""", (group_id_str,))
    res = c.fetchone()[0]
    conn.close()
    if res:
        return datetime.fromisoformat(res.replace('Z', '+00:00')).replace(tzinfo=None)
    return None

def update_points_logic():
    conn = get_db(); c = conn.cursor()
    
    # 1. Trend-logikk: Lagre plassering før oppdatering
    c.execute("SELECT DISTINCT group_id_str FROM bets")
    all_groups = [r[0] for r in c.fetchall()]
    for gid in all_groups:
        c.execute("SELECT user_name, SUM(points) as total FROM bets WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC", (gid,))
        current_lb = c.fetchall()
        for rank, row in enumerate(current_lb, 1):
            c.execute("UPDATE bets SET last_rank = ? WHERE user_name = ? AND group_id_str = ?", (rank, row[0], gid))
    conn.commit()

    # 2. Hent API-data og beregn poeng
    c.execute("SELECT DISTINCT league_id FROM fixtures")
    leagues = [row[0] for row in c.fetchall()]
    headers = {'X-Auth-Token': API_KEY}
    for league in leagues:
        try:
            url = f"https://api.football-data.org/v4/competitions/{league}/matches"
            res = requests.get(url, headers=headers).json()
            if 'matches' not in res: continue
            for m in res.get('matches', []):
                mid = m['id']; h_act = m['score']['fullTime']['home']; a_act = m['score']['fullTime']['away']
                status = m['status'].lower()
                if h_act is not None:
                    c.execute("SELECT first_goal_min FROM fixtures WHERE id = ?", (mid,))
                    f_goal = c.fetchone()[0]
                    if (not f_goal or f_goal == 0) and (h_act + a_act > 0):
                        f_goal = 25 
                        c.execute("UPDATE fixtures SET first_goal_min = ? WHERE id = ?", (f_goal, mid))
                    
                    c.execute("UPDATE fixtures SET home_actual=?, away_actual=?, status=? WHERE id=?", (h_act, a_act, status, mid))
                    
                    c.execute("SELECT id, group_id_str, user_name, home_score, away_score, golden_goal FROM bets WHERE fixture_id=?", (mid,))
                    for bet_id, gid, user, u_h, u_a, u_gg in c.fetchall():
                        tp = 0
                        if u_h == h_act and u_a == a_act: tp += 3
                        elif (u_h > u_a and h_act > a_act) or (u_h < u_a and h_act < a_act) or (u_h == u_a and h_act == a_act): tp += 1
                        
                        c.execute("SELECT user_answer FROM extra_bets eb JOIN extra_questions eq ON eb.question_id = eq.id WHERE eb.user_name=? AND eq.fixture_id=? AND eb.group_id_str=?", (user, mid, gid))
                        ex = c.fetchone()
                        if ex and ex[0] == 'JA' and (h_act + a_act > 0): tp += 2
                        if f_goal and u_gg == f_goal: tp += 5
                        c.execute("UPDATE bets SET points=? WHERE id=?", (tp, bet_id))
                    
                    # Golden Goal tie-breaker (2p til nærmeste)
                    if f_goal and f_goal > 0:
                        c.execute("SELECT DISTINCT group_id_str FROM bets WHERE fixture_id=?", (mid,))
                        for (g_val,) in c.fetchall():
                            c.execute("SELECT MIN(ABS(golden_goal - ?)) FROM bets WHERE fixture_id=? AND group_id_str=? AND golden_goal > 0", (f_goal, mid, g_val))
                            min_diff = c.fetchone()[0]
                            if min_diff is not None:
                                c.execute("UPDATE bets SET points = points + 2 WHERE fixture_id=? AND group_id_str=? AND ABS(golden_goal - ?) = ?", (mid, g_val, f_goal, min_diff))
        except: continue
    conn.commit(); conn.close()

def get_players_from_api(fixture_id):
    headers = {'X-Auth-Token': API_KEY}; players = []
    try:
        res = requests.get(f"https://api.football-data.org/v4/matches/{fixture_id}", headers=headers, timeout=5).json()
        for team in ['homeTeam', 'awayTeam']:
            t_id = res[team]['id']; t_name = res[team]['shortName']
            s_res = requests.get(f"https://api.football-data.org/v4/teams/{t_id}", headers=headers, timeout=5).json()
            for p in s_res.get('squad', []): players.append({'name': p['name'], 'team': t_name})
    except: pass
    return players

# --- RUTER ---

@app.route('/')
def index(): return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); dt = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "404", 404
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    raw = c.fetchall(); kamper = []
    round_start = get_round_start(group_id_str)
    is_locked = datetime.utcnow() > round_start if round_start else False
    for f in raw:
        f_l = list(f); m_time = datetime.fromisoformat(f[6].replace('Z', '+00:00'))
        f_l[6] = m_time.strftime("%d.%m kl %H:%M"); kamper.append(f_l)
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall(); conn.close()
    return render_template('group_view.html', group=group, kamper=kamper, questions=questions, is_locked=is_locked)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    limit_date = datetime.utcnow().isoformat()
    c.execute("SELECT * FROM fixtures WHERE date >= ? ORDER BY date ASC", (limit_date,))
    alle = c.fetchall()
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    valgte = [r[0] for r in c.fetchall()]
    players = get_players_from_api(valgte[0]) if valgte else []
    c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,))
    questions = c.fetchall(); conn.close()
    return render_template('group_admin.html', group=group, kamper=alle, valgte=valgte, players=players, questions=questions)

@app.route('/group/<group_id_str>/leaderboard')
def leaderboard(group_id_str):
    update_points_logic()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("""
        SELECT user_name, SUM(points) as total, MAX(last_rank) as prev_rank 
        FROM bets WHERE group_id_str = ? 
        GROUP BY user_name ORDER BY total DESC, user_name ASC""", (group_id_str,))
    rows = c.fetchall(); conn.close()
    leaderboard_data = []
    for rank, r in enumerate(rows, 1):
        user, pts, prev = r
        trend = "stay"
        if prev > 0:
            if rank < prev: trend = "up"
            elif rank > prev: trend = "down"
        leaderboard_data.append({'name': user, 'points': pts, 'trend': trend})
    return render_template('leaderboard.html', group=group, leaderboard=leaderboard_data, current_user=session.get('user_name', ''))

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json(); group_id = data['group_id']; user = data['user_name'].strip(); session['user_name'] = user
    round_start = get_round_start(group_id)
    if round_start and datetime.utcnow() > round_start: return jsonify({"status": "LOCKED"}), 403
    conn = get_db(); c = conn.cursor(); c.execute("DELETE FROM bets WHERE group_id_str = ? AND user_name = ?", (group_id, user))
    for t in data['tips']:
        c.execute("INSERT INTO bets (group_id_str, user_name, fixture_id, home_score, away_score, golden_goal) VALUES (?,?,?,?,?,?)", 
                 (group_id, user, int(t['match_id']), int(t['h']), int(t['a']), data.get('golden_goal', 0)))
    if 'extras' in data:
        c.execute("DELETE FROM extra_bets WHERE group_id_str = ? AND user_name = ?", (group_id, user))
        for q_id, val in data['extras'].items():
            c.execute("INSERT INTO extra_bets (group_id_str, user_name, question_id, user_answer) VALUES (?,?,?,?)", (group_id, user, int(q_id), val))
    conn.commit(); conn.close(); return jsonify({"status": "OK"})

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.get_json(); conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM groups WHERE group_id_str = ?", (data['group_id_str'],))
    gid = c.fetchone()[0]
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", (data.get('mode', 'multi'), data.get('prize', ''), gid))
    c.execute("DELETE FROM group_matches WHERE group_id = ?", (gid,))
    for mid in data['matches']:
        c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (gid, int(mid)))
    conn.commit(); conn.close(); return jsonify({"status": "OK"})

@app.route('/api/add_smart_question', methods=['POST'])
def add_smart_question():
    data = request.get_json(); conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO extra_questions (group_id_str, fixture_id, question_text) VALUES (?,?,?)", (data['group_id_str'], data['match_id'], data['text']))
    conn.commit(); conn.close(); return jsonify({"status": "OK"})

@app.route('/api/delete_question', methods=['POST'])
def delete_question():
    data = request.get_json(); q_id = data.get('q_id')
    conn = get_db(); c = conn.cursor(); c.execute("DELETE FROM extra_questions WHERE id = ?", (q_id,))
    c.execute("DELETE FROM extra_bets WHERE question_id = ?", (q_id,)) 
    conn.commit(); conn.close(); return jsonify({"status": "OK"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json(); gid_str = data['name'].lower().replace(" ", "-")
    conn = get_db(); c = conn.cursor(); c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (data['name'], gid_str, data['admin_name']))
    conn.commit(); conn.close(); return jsonify({"status": "Suksess"})

@app.route('/api/import_league/<league_code>')
def import_league(league_code):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches"
    headers = {'X-Auth-Token': API_KEY}; res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    now = datetime.utcnow(); future = now + timedelta(days=14)
    c.execute("DELETE FROM fixtures"); c.execute("DELETE FROM extra_questions")
    c.execute("DELETE FROM extra_bets"); c.execute("DELETE FROM group_matches"); c.execute("DELETE FROM bets")
    for m in res.get('matches', []):
        m_date = datetime.fromisoformat(m['utcDate'].replace('Z', '+00:00')).replace(tzinfo=None)
        if m_date >= now and m_date <= future:
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                (m['id'], league_code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    conn.commit(); conn.close(); return jsonify({"status": "Suksess"})

@app.route('/api/get_user_bets/<group_id_str>/<user_name>')
def get_user_bets(group_id_str, user_name):
    conn = get_db(); c = conn.cursor(); user = user_name.strip()
    c.execute("SELECT b.home_score, b.away_score, b.points, b.golden_goal, f.home_team, f.away_team, f.home_logo, f.away_logo FROM bets b JOIN fixtures f ON b.fixture_id = f.id WHERE b.group_id_str = ? AND b.user_name = ?", (group_id_str, user))
    main_bet = c.fetchall()
    c.execute("SELECT q.question_text, eb.user_answer FROM extra_bets eb JOIN extra_questions q ON eb.question_id = q.id WHERE eb.group_id_str = ? AND eb.user_name = ?", (group_id_str, user))
    extras = c.fetchall()
    c.execute("SELECT status FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id JOIN groups g ON gm.group_id = g.id WHERE g.group_id_str = ? AND f.status NOT IN ('upcoming', 'timed')", (group_id_str,))
    is_live = 1 if c.fetchone() else 0
    conn.close()
    return jsonify({'main': [{'h': b[0], 'a': b[1], 'pts': b[2], 'gg': b[3], 'ht': b[4], 'at': b[5], 'hl': b[6], 'al': b[7]} for b in main_bet], 'extras': [{'q': e[0], 'ans': e[1]} for e in extras], 'is_live': is_live})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
