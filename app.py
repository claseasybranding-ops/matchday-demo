import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
DB_PATH = "matchday_pro.db"

# Din nye Football-Data.org Token
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Vi bruker TEXT på league_id siden Football-Data bruker koder som 'PL'
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
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

@app.route('/api/import_league/<string:league_code>')
def import_league(league_code):
    # Henter alle planlagte kamper (SCHEDULED) for ligaen
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        matches = res.get('matches', [])
        
        if not matches:
            return jsonify({"status": f"Ingen kamper funnet. Sjekk om ligaen er støttet i gratis-planen din."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        count = 0
        for m in matches:
            # Lag-navn og logoer
            h_navn = m['homeTeam']['shortName'] or m['homeTeam']['name']
            b_navn = m['awayTeam']['shortName'] or m['awayTeam']['name']
            h_logo = m['homeTeam']['crest']
            b_logo = m['awayTeam']['crest']
            
            # Datoformat fra API: '2026-03-14T15:00:00Z'
            match_date = m['utcDate']
            
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (m['id'], league_code, h_navn, b_navn, h_logo, b_logo, match_date, 'upcoming'))
            count += 1
            if count >= 30: break # Vi henter de neste 30 kampene

        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {count} kommende kamper fra {league_code}."})
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
