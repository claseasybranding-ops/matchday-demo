import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

DB_PATH = 'matchday_pro.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def format_date(iso_date):
    try:
        iso_date = iso_date.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m kl %H:%M")
    except: return iso_date

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
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0)''')
    conn.commit(); conn.close()

init_db()

def update_points_logic():
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        conn = get_db(); c = conn.cursor()
        for m in res.get('matches', []):
            if m['status'] in ['FINISHED', 'LIVE', 'IN_PLAY']:
                h_act = m['score']['fullTime']['home']
                a_act = m['score']['fullTime']['away']
                mid = m['id']
                c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = ? WHERE id = ?", 
                          (h_act, a_act, m['status'].lower(), mid))
                c.execute("SELECT id, home_score, away_score FROM bets WHERE fixture_id = ?", (mid,))
                for bet_id, u_h, u_a in c.fetchall():
                    pts = 0
                    if h_act is not None and a_act is not None:
                        if u_h == h_act and u_a == a_act: pts = 3
                        elif (u_h > u_a and h_act > a_act) or (u_h < u_a and h_act < a_act) or (u_h == u_a and h_act == a_act): pts = 1
                        c.execute("UPDATE bets SET points = ? WHERE id = ?", (pts, bet_id))
        conn.commit(); conn.close()
        return True
    except: return False

@app.route('/')
def index(): return render_template('index.html')

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    if not group: return "Gruppe ikke funnet", 404
    
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    raw = c.fetchall(); kamper = []
    now = datetime.now() # Her kan man legge til timedelta(hours=1) hvis server-tid er feil
    
    for f in raw:
        f_l = list(f)
        # Sjekk deadline (5 min før kampstart)
        match_time = datetime.fromisoformat(f[6].replace('Z', '+00:00')).replace(tzinfo=None)
        is_locked = now > (match_time - timedelta(minutes=5))
        
        f_l[6] = format_date(f[6])
        f_l = f_l + [is_locked] # Legger til lås-status som siste element i listen
        kamper.append(f_l)
        
    conn.close()
    return render_template('group_view.html', group=group, kamper=kamper)

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    now = datetime.now()
    
    rejected_matches = []
    
    for t in data['tips']:
        # Hent kampstart fra databasen
        c.execute("SELECT date FROM fixtures WHERE id = ?", (int(t['match_id']),))
        res = c.fetchone()
        if res:
            match_time = datetime.fromisoformat(res[0].replace('Z', '+00:00')).replace(tzinfo=None)
            if now > (match_time - timedelta(minutes=5)):
                rejected_matches.append(t['match_id'])
                continue # Hopper over denne kampen hvis den er låst
        
        # Slett og legg inn på nytt (som avtalt)
        c.execute("DELETE FROM bets WHERE group_id_str = ? AND user_name = ? AND fixture_id = ?", 
                  (data['group_id'], data['user_name'], int(t['match_id'])))
        c.execute("INSERT INTO bets (group_id_str, user_name, fixture_id, home_score, away_score) VALUES (?,?,?,?,?)",
                  (data['group_id'], data['user_name'], int(t['match_id']), int(t['h']), int(t['a'])))
    
    conn.commit(); conn.close()
    
    if rejected_matches:
        return jsonify({"status": "Noen tips ble avvist fordi kampene har startet eller er låst."}), 400
    return jsonify({"status": "Suksess"})

# ... Resten av app.py ruter (leaderboard, super_admin, osv) forblir de samme ...
# Husk å beholde leaderboard og get_user_bets som jeg ga deg sist.
