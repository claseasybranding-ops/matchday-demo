import os
import sqlite3
import requests
import random
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

# --- KONFIGURASJON ---
DB_PATH = 'matchday_pro.db'
API_KEY = '58f8589c07824c2495869fa6b7b815e5' 

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures
                 (id INTEGER PRIMARY KEY, league_id INTEGER, home_team TEXT, 
                  away_team TEXT, home_logo TEXT, away_logo TEXT, 
                  date TEXT, status TEXT, home_actual INTEGER, away_actual INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT, user_name TEXT, 
                  fixture_id INTEGER, home_score INTEGER, away_score INTEGER, points INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- MODUL 5: POENG-LOGIKK ---
def calculate_points(u_h, u_a, a_h, a_a):
    if a_h is None or a_a is None: return 0
    u_h, u_a, a_h, a_a = int(u_h), int(u_a), int(a_h), int(a_a)
    if u_h == a_h and u_a == a_a: return 3
    u_hub = 'H' if u_h > u_a else ('B' if u_h < u_a else 'U')
    a_hub = 'H' if a_h > a_a else ('B' if a_h < a_a else 'U')
    return 1 if u_hub == a_hub else 0

# --- SMART FUNKSJON: FYLL GRUPPEN MED GHOST-DELTAKERE ---
@app.route('/api/generate_ghost_players/<group_id>')
def generate_ghost_players(group_id):
    """Lager 10 fiktive deltakere for å fylle leaderboardet"""
    names = ["Thomas", "Kari B.", "Petter", "Lise", "Morten", "Siri", "Arne", "Heidi", "Jonas", "Berit"]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Finn alle kamper som er importert
    c.execute("SELECT id FROM fixtures")
    match_ids = [row[0] for row in c.fetchall()]
    
    if not match_ids:
        return jsonify({"status": "Ingen kamper i DB. Importer kamper først!"})

    for name in names:
        for m_id in match_ids:
            # Sjekk om ghost-spilleren allerede har tippet
            c.execute("SELECT id FROM bets WHERE user_name = ? AND fixture_id = ?", (name, m_id))
            if not c.fetchone():
                h_tip = random.randint(0, 3)
                a_tip = random.randint(0, 3)
                c.execute("INSERT INTO bets (group_id, user_name, fixture_id, home_score, away_score) VALUES (?,?,?,?,?)",
                          (group_id, name, m_id, h_tip, a_tip))
    
    conn.commit()
    conn.close()
    return jsonify({"status": f"Lagt til {len(names)} ghost-deltakere i {group_id}!"})

# --- MODUL 2: API-IMPORT ---
@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=10&timezone=Europe/Oslo"
    headers = {'x-apisports-key': API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}
    try:
        res = requests.get(url, headers=headers).json()
        data = res.get('response', [])
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures (id, league_id, home_team, away_team, home_logo, away_logo, date, status) VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], f['teams']['away']['name'], f['teams']['home']['logo'], f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Importerte {len(data)} kamper."})
    except Exception as e:
        return jsonify({"status": str(e)})

# --- MODUL 5: LIVE UPDATES ---
@app.route('/api/update_live_scores')
def update_live_scores():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT b.id, b.home_score, b.away_score, f.home_actual, f.away_actual FROM bets b JOIN fixtures f ON b.fixture_id = f.id WHERE f.home_actual IS NOT NULL")
    for b_id, u_h, u_a, a_h, a_a in c.fetchall():
        c.execute("UPDATE bets SET points = ? WHERE id = ?", (calculate_points(u_h, u_a, a_h, a_a), b_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "Oppdatert!"})

@app.route('/')
def index(): return render_template('index.html')

@app.route('/group/<group_id>')
def group_view(group_id): return render_template('group_view.html', group_id=group_id)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
