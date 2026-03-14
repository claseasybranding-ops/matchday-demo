import os
import sqlite3
import requests
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_secret_key" # Modul 7: Sesjonshåndtering

# --- KONFIGURASJON ---
DB_PATH = 'matchday_pro.db'
# Din oppdaterte API-nøkkel:
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

# ---------------------------------------------------------
# DATABASE INITIALISERING
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Modul 2 & 3: Fixtures
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id INTEGER, home_team TEXT, 
                  away_team TEXT, home_logo TEXT, away_logo TEXT, 
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER)''')
    
    # Modul 4 & 5: Bets og Poeng
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT, user_name TEXT, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0)''')
    
    # Modul 10: Premier
    c.execute('''CREATE TABLE IF NOT EXISTS prizes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT, title TEXT, description TEXT, image_url TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# MODUL 5: POENG-LOGIKK (3p for resultat, 1p for HUB)
# ---------------------------------------------------------
def calculate_points(u_h, u_a, a_h, a_a):
    if a_h is None or a_a is None:
        return 0
    
    # Konverter til int for sikker sammenligning
    u_h, u_a, a_h, a_a = int(u_h), int(u_a), int(a_h), int(a_a)
    
    # 3 poeng for korrekt resultat
    if u_h == a_h and u_a == a_a:
        return 3
        
    # Finn HUB-tegn
    u_hub = 'H' if u_h > u_a else ('B' if u_h < u_a else 'U')
    a_hub = 'H' if a_h > a_a else ('B' if a_h < a_a else 'U')
    
    # 1 poeng for riktig tegn (HUB)
    return 1 if u_hub == a_hub else 0

# ---------------------------------------------------------
# MODUL 2: API-IMPORT (Robust import med din nøkkel)
# ---------------------------------------------------------
@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    fra_dato = datetime.now().strftime('%Y-%m-%d')
    til_dato = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&from={fra_dato}&to={til_dato}&timezone=Europe/Oslo"
    headers = {
        'x-apisports-key': API_KEY, 
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Fallback hvis dagsplanen er begrenset
        if res.get('errors') and 'plan' in str(res.get('errors')):
            url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&last=10"
            res = requests.get(url, headers=headers).json()

        data = res.get('response', [])
        if not data:
            return jsonify({"status": "Fant ingen kamper i API-et."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("""INSERT OR REPLACE INTO fixtures 
                         (id, league_id, home_team, away_team, home_logo, away_logo, date, status) 
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Importerte {len(data)} kamper."})
    except Exception as e:
        return jsonify({"status": f"API-feil: {str(e)}"})

# ---------------------------------------------------------
# MODUL 5: OPPDATER LIVE-SCORES & POENG
# ---------------------------------------------------------
@app.route('/api/update_live_scores')
def update_live_scores():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Henter alle tips og faktiske resultater for kamper som har score
    c.execute("""
        SELECT b.id, b.home_score, b.away_score, f.home_actual, f.away_actual 
        FROM bets b
        JOIN fixtures f ON b.fixture_id = f.id
        WHERE f.home_actual IS NOT NULL
    """)
    
    all_bets = c.fetchall()
    for b_id, u_h, u_a, a_h, a_a in all_bets:
        new_points = calculate_points(u_h, u_a, a_h, a_a)
        c.execute("UPDATE bets SET points = ? WHERE id = ?", (new_points, b_id))
        
    conn.commit()
    conn.close()
    return jsonify({"status": "Poeng og leaderboard er oppdatert!"})

# ---------------------------------------------------------
# VISNINGS-RUTER
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/group/<group_id>')
def group_view(group_id):
    return render_template('group_view.html', group_id=group_id)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
