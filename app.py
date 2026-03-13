import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, os
from datetime import datetime

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
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    alle_kamper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=alle_kamper)

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi bruker KUN dato. Ingen 'next', ingen 'last', ingen 'round'.
    # Dette er den tryggeste gratis-spørringen.
    today = datetime.now().strftime('%Y-%m-%d')
    
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&date={today}&timezone=Europe/Oslo"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        res = requests.get(url, headers=headers).json()
        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": f"Ingen kamper i dag ({today}). Prøv igjen i morgen eller sjekk en annen liga."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {len(data)} kamper for i dag."})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
