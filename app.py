import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

DB_PATH = 'matchday_pro.db'
# Din ekte nøkkel fra e-posten:
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

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
    kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

# --- NY IMPORT-FUNKSJON TILPASSET DIN EKTE API-NØKKEL ---
@app.route('/api/import_league/<code>')
def import_league(code):
    # Football-data.org bruker 'PL' for Premier League
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
            # Vi henter kamper som er planlagt (SCHEDULED) eller som spilles i dag
            if m['status'] in ['SCHEDULED', 'TIMED', 'LIVE']:
                mid = m['id']
                home = m['homeTeam']['name']
                away = m['awayTeam']['name']
                # Football-data gir ofte ikke direkte bilde-URL i denne pakken, 
                # så vi bruker en placeholder hvis logo mangler
                h_logo = m['homeTeam'].get('crest', 'https://via.placeholder.com/50')
                a_logo = m['awayTeam'].get('crest', 'https://via.placeholder.com/50')
                m_date = m['utcDate']
                
                c.execute("""INSERT OR REPLACE INTO fixtures 
                    (id, league_id, home_team, away_team, home_logo, away_logo, date, status) 
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (mid, 'PL', home, away, h_logo, a_logo, m_date, 'upcoming'))
                count += 1
            
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {count} kamper fra Football-Data.org"})
    except Exception as e:
        return jsonify({"status": f"Feil ved henting: {str(e)}"})

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.get_json()
    name, admin = data.get('name'), data.get('admin_name')
    gid = name.lower().replace(" ", "-")
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)", (name, gid, admin))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/group/<group_id_str>')
def group_view(group_id_str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE group_id_str = ?", (group_id_str,))
    group = c.fetchone()
    c.execute("SELECT f.* FROM fixtures f JOIN group_matches gm ON f.id = gm.fixture_id WHERE gm.group_id = ?", (group[0],))
    kamper = c.fetchall()
    c.execute("SELECT user_name, SUM(points) as total FROM bets WHERE group_id_str = ? GROUP BY user_name ORDER BY total DESC", (group_id_str,))
    leaderboard = c.fetchall()
    conn.close()
    return render_template('group_view.html', group_id=group_id_str, group=group, kamper=kamper, leaderboard=leaderboard)

@app.route('/')
def index(): return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
