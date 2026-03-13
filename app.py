import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, json, os

app = Flask(__name__)
DB_PATH = "matchday_pro.db"

# Din oppdaterte API-nøkkel
API_KEY = "c06ecd6de7644023e13c7b881248e5bc"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabell for kamper
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id INTEGER, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    # Tabell for grupper/kunder
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, admin_code TEXT, 
                  active_fixtures TEXT, mode TEXT)''')
    conn.commit()
    conn.close()

# Start databasen
init_db()

@app.route('/')
def index():
    return "Hovedsiden er under oppbygging. Gå til /super_admin_dashboard"

@app.route('/super_admin_dashboard')
def super_admin():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Henter alle kamper sortert på dato
        c.execute("SELECT * FROM fixtures ORDER BY date ASC")
        alle_kamper = c.fetchall()
        conn.close()
        return render_template('super_admin.html', kamper=alle_kamper)
    except Exception as e:
        return f"Databasefeil: {str(e)}"

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi henter de neste 50 kampene uten strengt års-filter for å være sikre på treff
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=50"
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])
        
        # Hvis 'next=50' ikke ga treff, prøver vi å spesifisere sesong 2025
        if not data:
            url_alt = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=50"
            res = requests.get(url_alt, headers=headers).json()
            data = res.get('response', [])

        if not data:
            msg = res.get('errors', 'Ingen kamper funnet')
            return jsonify({"status": f"API-feil eller ingen kamper: {msg}"})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Importerte {len(data)} kamper."})
        
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
