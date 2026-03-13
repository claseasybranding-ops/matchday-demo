import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, json, os

app = Flask(__name__)
DB_PATH = "matchday_pro.db"

# Din verifiserte API-nøkkel
API_KEY = "c06ecd6de7644023a13c7b881248e5bc"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                     (id INTEGER PRIMARY KEY, league_id INTEGER, h_navn TEXT, b_navn TEXT, 
                      h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS groups 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, admin_code TEXT, 
                      active_fixtures TEXT, mode TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database init feil: {e}")

init_db()

@app.route('/')
def index():
    return "Hovedside under oppbygging. Gå til /super_admin_dashboard"

@app.route('/super_admin_dashboard')
def super_admin():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM fixtures ORDER BY date ASC")
        alle_kamper = c.fetchall()
        conn.close()
        # VIKTIG: Her sender vi 'kamper' variabelen til HTML-en din
        return render_template('super_admin.html', kamper=alle_kamper)
    except Exception as e:
        return f"Systemet har en intern feil: {str(e)}"

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=20"
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Sjekk om API-et klager på nøkkelen
        if res.get('errors'):
            return jsonify({"status": f"API-feil: {res['errors']}"})
            
        data = res.get('response', [])
        if not data:
            return jsonify({"status": "Fant ingen kamper i API-et."})

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
        return jsonify({"status": f"Feil ved import: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
