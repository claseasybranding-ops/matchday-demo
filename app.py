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
        # Håndterer både Z og +0000 format fra football-data.org
        iso_date = iso_date.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d.%m kl %H:%M")
    except:
        return iso_date

def init_db():
    conn = get_db()
    c = conn.cursor()
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
    conn.commit()
    conn.close()

init_db()

@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw_fixtures = c.fetchall()
    
    kamper = []
    for f in raw_fixtures:
        f_list = list(f)
        f_list[6] = format_date(f[6])
        kamper.append(f_list)
        
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

@app.route('/api/import_league/<code>')
def import_league(code):
    url = "https://api.football-data.org/v4/competitions/PL/matches"
    headers = {'X-Auth-Token': API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        matches = data.get('matches', [])
        
        conn = get_db()
        c = conn.cursor()
        count = 0
        for m in matches:
            if m['status'] in ['SCHEDULED', 'TIMED']:
                mid = m['id']
                home = m['homeTeam']['shortName'] or m['homeTeam']['name']
                away = m['awayTeam']['shortName'] or m['awayTeam']['name']
                h_logo = m['homeTeam'].get('crest', '')
                a_logo = m['awayTeam'].get('crest', '')
                m_date = m['utcDate']
                
                c.execute("""INSERT OR REPLACE INTO fixtures 
                    (id, league_id, home_team, away_team, home_logo, away_logo, date, status) 
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (mid, 'PL', home, away, h_logo, a_logo, m_date, 'upcoming'))
                count += 1
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {count} kamper."})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})

# --- DENNE RUTEN SØRGER FOR AT DU KOMMER TIL ADMIN-SIDEN FOR GRUPPA ---
@app.route('/group/<group_id_str>/admin')
def group_admin(group_id_str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    
    if not group:
        return "Gruppen ble ikke funnet", 404

    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    raw_fixtures = c.fetchall()
    all_fixtures = []
    for f in raw_fixtures:
        f_list = list(f)
        f_list[6] = format_date(f[6])
        all_fixtures.append(f_list)

    c.execute("SELECT fixture_id FROM group_matches WHERE group_id = ?", (group[0],))
    selected_ids = [r[0] for r in c.fetchall()]
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.get_json()
    gid, fid = data.get('group_id'), data.get('fixture_id')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    if c.fetchone():
        c.execute("DELETE FROM group_matches WHERE group_id = ? AND fixture_id = ?", (gid, fid))
    else:
        c.execute("INSERT INTO group_matches (group_id, fixture_id) VALUES (?, ?)", (gid, fid))
    conn.commit()
    conn.close()
    return jsonify({"status": "OK"})

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    raw_fixtures = c.fetchall()
    kamper = []
    for f in raw_fixtures:
        f_list = list(f)
        f_list[6] = format_date(f[6])
        kamper.append(f_list)
    conn.close()
    return render_template('group_view.html', group_id=group_id_str, group=group, kamper=kamper)

@app.route('/')
def index(): return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
