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

# --- SIDER ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    return render_template('super_admin.html')

@app.route('/group/<group_id>')
def group_view(group_id):
    return render_template('group_view.html', group_id=group_id)

@app.route('/group/<group_id>/admin')
def group_admin(group_id):
    return render_template('group_admin.html', group_id=group_id)

# --- API (Fikset for å fjerne JSON-feilen) ---
@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=15"
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])
        
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
        
        # Sender rent JSON-svar tilbake til knappen
        return jsonify({"status": "success", "count": len(data)})
    except Exception as e:
        # Sender feilmelding som JSON så knappen ikke kræsjer
        return jsonify({"status": "error", "message": str(e)})

# --- RENDER OPPSTART ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
