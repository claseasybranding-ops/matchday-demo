import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

DB_PATH = 'matchday_pro.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id INTEGER, home_team TEXT, 
                  away_team TEXT, home_logo TEXT, away_logo TEXT, 
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, group_id_str TEXT, admin_name TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- HOVEDSIDE ADMIN ---
@app.route('/super_admin_dashboard')
def super_admin():
    conn = get_db()
    c = conn.cursor()
    # Henter grupper til listen
    c.execute("SELECT id, group_name, group_id_str, admin_name FROM groups")
    grupper = c.fetchall()
    # Henter kamper til bufféen
    c.execute("SELECT * FROM fixtures ORDER BY date DESC")
    kamper = c.fetchall()
    conn.close()
    # Her sender vi variablene nøyaktig slik HTML-filen din forventer dem
    return render_template('super_admin.html', grupper=grupper, kamper=kamper)

# --- OPPRETT GRUPPE ---
@app.route('/api/create_group', methods=['POST'])
def create_group():
    try:
        data = request.get_json()
        name = data.get('name')
        admin = data.get('admin_name')
        # Lager en URL-vennlig ID (f.eks "Liverbirds Fredrikstad" -> "liverbirds-fredrikstad")
        group_id_str = name.lower().replace(" ", "-")

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO groups (group_name, group_id_str, admin_name) VALUES (?, ?, ?)",
                  (name, group_id_str, admin))
        conn.commit()
        conn.close()
        # HTML-koden din sjekker etter "Suksess"
        return jsonify({"status": "Suksess"})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})

# --- IMPORT AV LIGA (Tilpasset 'PL' fra din HTML) ---
@app.route('/api/import_league/<code>')
def import_league(code):
    # Mapper 'PL' til riktig ID i API-et (Premier League = 39)
    league_id = 39 if code == 'PL' else 39 
    
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=15&timezone=Europe/Oslo"
    headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    
    try:
        res = requests.get(url, headers=headers).json()
        fixtures = res.get('response', [])
        
        conn = get_db()
        c = conn.cursor()
        for f in fixtures:
            c.execute("""INSERT OR REPLACE INTO fixtures 
                (id, league_id, home_team, away_team, home_logo, away_logo, date, status) 
                VALUES (?,?,?,?,?,?,?,?)""",
                (f['fixture']['id'], league_id, f['teams']['home']['name'], f['teams']['away']['name'],
                 f['teams']['home']['logo'], f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Hentet {len(fixtures)} kamper!"})
    except Exception as e:
        return jsonify({"status": f"Feil ved henting: {str(e)}"})

# --- PUSH RESULTATER (INVESTOR MODUS) ---
@app.route('/api/admin_push_scores', methods=['POST'])
def admin_push_scores():
    data = request.get_json()
    scores = data.get('scores', [])
    conn = get_db()
    c = conn.cursor()
    for s in scores:
        c.execute("UPDATE fixtures SET home_actual = ?, away_actual = ?, status = 'finished' WHERE id = ?",
                  (s['h'], s['b'], s['match_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess"})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
