import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, os
from datetime import datetime, timedelta

app = Flask(__name__)
DB_PATH = "matchday_pro.db"

# Din nye, fungerende nøkkel:
API_KEY = "67426ace3170141fe1072055b5825f1e"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id INTEGER, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/super_admin_dashboard')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    alle_kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=alle_kamper)

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Her har jeg lagt til &season=2025 som API-et ba om i feilmeldingen din
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&from={today}&to={next_week}&timezone=Europe/Oslo"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        if res.get('errors'):
            return jsonify({"status": f"API-feil: {res['errors']}"})
            
        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": f"Fant ingen kamper i sesong 2025 mellom {today} og {next_week}."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {len(data)} kamper."})
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
