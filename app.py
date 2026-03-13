import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, json, os

app = Flask(__name__)
DB_PATH = "matchday_pro.db"
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Tabell for kamper hentet fra API
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id INTEGER, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    # Tabell for grupper (dine kunder)
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_name TEXT, admin_code TEXT, 
                  active_fixtures TEXT, mode TEXT)''')
    conn.commit()
    conn.close()

# Kjører databasen med en gang appen starter
init_db()

@app.route('/')
def index():
    return "Hovedsiden er under oppbygging. Gå til /super_admin_dashboard"

@app.route('/super_admin_dashboard')
def super_admin():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM fixtures ORDER BY date ASC")
        alle_kamper = c.fetchall()
        conn.close()
        # Her sender vi en tom liste hvis databasen er tom, i stedet for å krasje
        return render_template('super_admin.html', kamper=alle_kamper if alle_kamper else [])
    except Exception as e:
        return f"Databasefeil: {str(e)}"

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Henter neste 20 kamper
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=20"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        res = requests.get(url, headers=headers).json()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for f in res.get('response', []):
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Importerte {len(res.get('response', []))} kamper."})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
