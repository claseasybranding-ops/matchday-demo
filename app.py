import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime

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

# --- LOGIKK FOR POENGBEREGNING ---
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
                
                # Oppdater kampstatus i fixtures
                c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = ? WHERE id = ?", 
                         (h_act, a_act, m['status'].lower(), mid))
                
                # Finn alle tips for denne kampen
                c.execute("SELECT id, home_score, away_score FROM bets WHERE fixture_id = ?", (mid,))
                for bet_id, u_h, u_a in c.fetchall():
                    pts = 0
                    if h_act is not None and a_act is not None:
                        # 3 poeng for helt riktig score
                        if u_h == h_act and u_a == a_act:
                            pts = 3
                        # 1 poeng for riktig HUB
                        elif (u_h > u_a and h_act > a_act) or (u_h < u_a and h_act < a_act) or (u_h == u_a and h_act == a_act):
                            pts = 1
                        c.execute("UPDATE bets SET points = ? WHERE id = ?", (pts, bet_id))
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(f"Feil ved oppdatering: {e}")
        return False

# --- RUTER ---

@app.route('/api/refresh_data')
def refresh_data():
    success = update_points_logic()
    return jsonify({"status": "Oppdatert" if success else "Feil"})

@app.route('/group/<group_id_str>/leaderboard')
def leaderboard(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    # Henter oppdatert tabell
    c.execute("""SELECT user_name, SUM(points) as total FROM bets 
                 WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC""", (group_id_str,))
    rows = c.fetchall()
    conn.close()
    return render_template('leaderboard.html', group=group, leaderboard=rows)

# Gjenbruk resten av rutinene fra forrige app.py (super_admin, group_admin, group_view, submit_tips osv.)
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
        f_l = list(f); f_l[6] = format_date(f[6]); kamper.append(f_l)
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw = c.fetchall(); all_fixtures = []
    for f in raw:
        f_l = list(f); f_l[6] = format_date(f[6]); all_fixtures.append(f_l)
    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    selected_ids = [r[0] for r in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    raw = c.fetchall(); kamper = []
    for f in raw:
        f_l = list(f); f_l[6] = format_date(f[6]); kamper.append(f_l)
    conn.close()
    return render_template('group_view.html', group_id=group_id_str, group=group, kamper=kamper)

@app.route('/api/submit_tips', methods=['POST'])
def submit_tips():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    for t in data['tips']:
        c.execute("INSERT OR REPLACE INTO bets (group_id_str, user_name, fixture_id, home_score, away_score) VALUES (?,?,?,?,?)",
                  (data['group_id'], data['user_name'], t['match_id'], t['h'], t['a']))
    conn.commit(); conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/api/update_group_settings', methods=['POST'])
def update_settings():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE groups SET mode = ?, prize_info = ? WHERE id = ?", (data['mode'], data['prize_info'], data['group_id']))
    conn.commit(); conn.close()
    return jsonify({"status": "OK"})

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM group_matches WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    if c.fetchone(): c.execute("DELETE FROM group_matches WHERE group_id = ? AND fixture_id = ?", (data['group_id'], data['fixture_id']))
    else: c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (data['group_id'], data['fixture_id']))
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
