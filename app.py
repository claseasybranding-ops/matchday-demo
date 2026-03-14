import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, os
from datetime import datetime, timedelta

app = Flask(__name__)
DB_PATH = "matchday_pro.db"
API_KEY = "c06ecd6de7644023a13c7b881248e5bc"

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
    # Henter alle kamper sortert på tid
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    alle_kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=alle_kamper)

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    # Vi prøver den absolutt enkleste metoden for gratiskontoer: 
    # Hent de neste 10 kampene i ligaen uavhengig av dato-intervall
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=10&timezone=Europe/Oslo"
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Hvis 'next' blir blokkert, prøver vi for i dag (lørdag 14. mars)
        if res.get('errors') and 'plan' in str(res.get('errors')):
            today = datetime.now().strftime('%Y-%m-%d')
            url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&date={today}&timezone=Europe/Oslo"
            res = requests.get(url, headers=headers).json()

        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": f"API fant ingen kamper. Svar: {res}"})

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
