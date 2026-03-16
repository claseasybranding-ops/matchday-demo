import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_v5_pro_ultra_final_complete"

# Bruker samme database-fil som før
DB_PATH = 'matchday_v3.db'
# Din API-nøkkel
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    # Row gjør at vi kan hente data med navn (f.eks. row['group_name'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    # Oppretter alle nødvendige tabeller hvis de ikke finnes
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
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, 
                  points INTEGER DEFAULT 0, golden_goal INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS extra_questions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, fixture_id INTEGER, 
                  question_text TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS extra_bets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id_str TEXT, user_name TEXT, 
                  question_id INTEGER, user_answer TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- LOGIKK FOR POENGBEREGNING (3p, 1p, +5p for GG, +2p for nærmest) ---
def update_points_logic():
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        if 'matches' not in res: return False
        conn = get_db(); c = conn.cursor()
        
        for m in res.get('matches', []):
            mid = m['id']
            status = m['status'].lower()
            
            # Oppdaterer kun kamper som har startet eller er ferdige
            if status in ['finished', 'in_play', 'live', 'timed']:
                h_act = m['score']['fullTime']['home']
                a_act = m['score']['fullTime']['away']
                h_score = h_act if h_act is not None else 0
                a_score = a_act if a_act is not None else 0
                
                f_goal = 0
                c.execute("SELECT first_goal_min FROM fixtures WHERE id=?", (mid,))
                stored = c.fetchone()
                
                # Henter målminutt hvis vi har mål og ikke har lagret det før
                if (h_score + a_score) > 0:
                    if stored and stored['first_goal_min']:
                        f_goal = stored['first_goal_min']
                    else:
                        try:
                            m_url = f"https://api.football-data.org/v4/matches/{mid}"
                            m_res = requests.get(m_url, headers=headers, timeout=5).json()
                            if 'goals' in m_res and len(m_res['goals']) > 0:
                                f_goal = m_res['goals'][0].get('minute', 0)
                        except: pass

                c.execute("UPDATE fixtures SET home_actual=?, away_actual=?, status=?, first_goal_min=? WHERE id=?", 
                         (h_score, a_score, status, f_goal, mid))
                
                # Beregn poeng for hver bet
                c.execute("SELECT id, group_id_str, home_score, away_score, golden_goal FROM bets WHERE fixture_id=?", (mid,))
                for bet in c.fetchall():
                    pts = 0
                    # 3 poeng for korrekt resultat
                    if bet['home_score'] == h_score and bet['away_score'] == a_score:
                        pts = 3
                    # 1 poeng for riktig HUB (hjemme, uavgjort, borte)
                    elif (bet['home_score'] > bet['away_score'] and h_score > a_score) or \
                         (bet['home_score'] < bet['away_score'] and h_score < a_score) or \
                         (bet['home_score'] == bet['away_score'] and h_score == a_score):
                        pts = 1
                    
                    # +5 poeng for nøyaktig Golden Goal
                    if f_goal > 0 and bet['golden_goal'] == f_goal:
                        pts += 5
                    
                    c.execute("UPDATE bets SET points=? WHERE id=?", (pts, bet['id']))

                # Tie-breaker: +2 poeng til den som er nærmest Golden Goal i hver gruppe
                if f_goal > 0:
                    c.execute("SELECT DISTINCT group_id_str FROM bets WHERE fixture_id=?", (mid,))
                    for (gid,) in c.fetchall():
                        c.execute("""SELECT MIN(ABS(golden_goal - ?)) FROM bets 
                                     WHERE fixture_id=? AND group_id_str=? AND golden_goal > 0 AND golden_goal != ?""", 
                                  (f_goal, mid, gid, f_goal))
                        min_diff = c.fetchone()[0]
                        if min_diff is not None:
                            c.execute("""UPDATE bets SET points = points + 2 
                                         WHERE fixture_id=? AND group_id_str=? AND ABS(golden_goal - ?) = ?""", 
                                      (mid, gid, f_goal, min_diff))
        conn.commit(); conn.close()
        return True
    except: return False

# Henter spillerstaller for "Tilleggsspørsmål"
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

# --- HOVEDSIDER ---

@app.route('/')
def index(): return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db(); c = conn.cursor()
    # Henter alle grupper (Kunder)
    grupper = [dict(row) for row in c.execute("SELECT * FROM groups").fetchall()]
    # Henter de 50 første kampene i lageret
    kamper = []
    for f in c.execute("SELECT * FROM fixtures ORDER BY date ASC LIMIT 50").fetchall():
        f_l = list(f)
        dt = datetime.fromisoformat(f['date'].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m %H:%M")
        kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    group = c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,)).fetchone()
    if not group: return "Gruppe ikke funnet", 404
    
    # Henter alle tilgjengelige kamper
    alle_raw = c.execute("SELECT * FROM fixtures ORDER BY date ASC").fetchall()
    alle_list = []
    for f in alle_raw:
        f_l = list(f)
        dt = datetime.fromisoformat(f['date'].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m %H:%M")
        alle_list.append(f_l)
    
    # Henter de kampene som er valgt for denne gruppa
    valgte = [r[0] for r in c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group['id'],)).fetchall()]
    
    # Henter spillere for målscorer-spørsmål
    players = get_players_from_api(valgte[0]) if valgte else []
    
    # Henter ekstra spørsmål
    questions = c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,)).fetchall()
    
    conn.close()
    return render_template('group_admin.html', group=group, kamper=alle_list, valgte=valgte, players=players, questions=questions)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    group = c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,)).fetchone()
    if not group: return "Siden finnes ikke", 404
    
    # Henter kun de kampene som admin har valgt ut
    raw = c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group['id'],)).fetchall()
    kamper = []
    for f in raw:
        f_l = list(f)
        dt = datetime.fromisoformat(f['date'].replace('Z', '+00:00'))
        f_l[6] = dt.strftime("%d.%m %H:%M")
        kamper.append(f_l)
        
    questions = c.execute("SELECT id, question_text FROM extra_questions WHERE group_id_str = ?", (group_id_str,)).fetchall()
    conn.close()
    return render_template('group_view.html', group=group, kamper=kamper, questions=questions)

@app.route('/group/<group_id_str>/leaderboard')
def leaderboard(group_id_str):
    update_points_logic() # Oppdaterer poeng automatisk når man ser på tabellen
    conn = get_db(); c = conn.cursor()
    group = c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,)).fetchone()
    
    # Finner start-tid for runden (første kamp)
    start_raw = c.execute("SELECT MIN(f.date) FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group['id'],)).fetchone()[0]
    start_time = datetime.fromisoformat(start_raw.replace('Z', '+00:00')).strftime("%d.%m %H:%M") if start_raw else ""
    
    # Grupperer poeng per bruker
    rows = c.execute("SELECT user_name, SUM(points) as total FROM bets WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC, user_name ASC", (group_id_str,)).fetchall()
    conn.close()
    return render_template('leaderboard.html', group=group, leaderboard=rows, start_time=start_time)

# --- API ENDEPUNKTER ---

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    # Lager en URL-vennlig ID (f.eks "TV 2" blir "tv-2")
    gid_str = data['name'].lower().replace(" ", "-").replace("æ","ae").replace("ø","o").replace("å","a")
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", 
             (data['name'], gid_str, data['admin_name']))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/update_group_settings', methods=['POST'])
def update_group_settings():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    # Oppdaterer modus og premie
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE group_id_str = ?", 
             (data.get('mode', 'multi'), data.get('prize', ''), data['group_id_str']))
    
    group = c.execute("SELECT id FROM groups WHERE group_id_str = ?", (data['group_id_str'],)).fetchone()
    
    # Oppdaterer hvilke kamper som skal være med i runden
    c.execute("DELETE FROM group_matches WHERE group_id = ?", (group['id'],))
    for mid in data['matches']:
        c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (group['id'], int(mid)))
    
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

@app.route('/api/delete_question/<int:q_id>', methods=['POST'])
def delete_question(q_id):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM extra_questions WHERE id = ?", (q_id,))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    try:
        data = request.get_json()
        conn = get_db(); c = conn.cursor()
        # Sletter gamle tips for å unngå dubletter
        c.execute("DELETE FROM bets WHERE group_id_str = ? AND user_name = ?", (data['group_id'], data['user_name']))
        
        gg = int(data.get('golden_goal', 0)) if data.get('golden_goal') else 0
        
        # Lagrer hvert kamptips
        for t in data['tips']:
            c.execute("INSERT INTO bets (group_id_str, user_name, fixture_id, home_score, away_score, golden_goal) VALUES (?,?,?,?,?,?)", 
                     (data['group_id'], data['user_name'], int(t['match_id']), int(t['h']), int(t['a']), gg))
        
        # Lagrer ekstra svar (målscorer etc)
        if 'extras' in data:
            c.execute("DELETE FROM extra_bets WHERE group_id_str = ? AND user_name = ?", (data['group_id'], data['user_name']))
            for q_id, val in data['extras'].items():
                c.execute("INSERT INTO extra_bets (group_id_str, user_name, question_id, user_answer) VALUES (?,?,?,?)", 
                         (data['group_id'], data['user_name'], int(q_id), val))
        
        conn.commit(); conn.close()
        return jsonify({"status": "OK"})
    except:
        return jsonify({"status": "Error"}), 500

@app.route('/api/import_league/PL')
def import_league():
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    res = requests.get(url, headers=headers).json()
    conn = get_db(); c = conn.cursor()
    # Sletter alt gammelt for å få en ren start (Viktig!)
    c.execute("DELETE FROM fixtures")
    c.execute("DELETE FROM extra_questions")
    c.execute("DELETE FROM extra_bets")
    c.execute("DELETE FROM group_matches")
    c.execute("DELETE FROM bets")
    
    for m in res['matches']:
        c.execute("INSERT INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)", 
                 (m['id'], 'PL', m['homeTeam']['shortName'], m['awayTeam']['shortName'], m['homeTeam'].get('crest',''), m['awayTeam'].get('crest',''), m['utcDate'], 'upcoming'))
    
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/get_user_bets/<group_id_str>/<user_name>')
def get_user_bets(group_id_str, user_name):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT b.*, f.home_team, f.away_team, f.home_logo, f.away_logo FROM bets b JOIN fixtures f ON b.fixture_id = f.id WHERE b.group_id_str = ? AND b.user_name = ?", (group_id_str, user_name))
    main = [dict(row) for row in c.fetchall()]
    
    c.execute("SELECT q.question_text, eb.user_answer FROM extra_bets eb JOIN extra_questions q ON eb.question_id = q.id WHERE eb.group_id_str = ? AND eb.user_name = ?", (group_id_str, user_name))
    extras = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return jsonify({'main': [{'h': b['home_score'], 'a': b['away_score'], 'pts': b['points'], 'gg': b['golden_goal'], 'ht': b['home_team'], 'at': b['away_team'], 'hl': b['home_logo'], 'al': b['away_logo']} for b in main], 'extras': [{'q': e['question_text'], 'ans': e['user_answer']} for e in extras]})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
