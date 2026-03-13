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
    # VIKTIG: Vi bruker KUN league og season. Dette SKAL alle planer ha tilgang til.
    # Vi henter alle kamper for sesongen, og filtrerer i koden i stedet for i API-et.
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&timezone=Europe/Oslo"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Hvis du fortsatt får "Next" feil her, så er det RENDER som ikke har oppdatert seg.
        if 'Next' in str(res):
            return jsonify({"status": "FEIL: Render kjører fortsatt gammel kode. Vennligst slett 'Matchday' på Render og lag ny."})

        data = res.get('response', [])
        if not data:
            return jsonify({"status": "Fant ingen data i API-et."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        count = 0
        for f in data:
            # Vi lagrer kun kamper som ikke har startet ennå (upcoming)
            match_date = f['fixture']['date']
            if match_date > datetime.now().isoformat():
                c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                          (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                           f['teams']['away']['name'], f['teams']['home']['logo'], 
                           f['teams']['away']['logo'], match_date, 'upcoming'))
                count += 1
        
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Importerte {count} kommende kamper."})
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
