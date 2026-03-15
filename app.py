import os
import sqlite3
import requests
import random
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "matchday_secret_key"

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
    c.execute('''CREATE TABLE IF NOT EXISTS groups
                 (id TEXT PRIMARY KEY, group_name TEXT, company_name TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/super_admin_dashboard')
def super_admin():
    return render_template('super_admin.html')

# --- FIKSET: Denne funksjonen sender nå data i alle formater siden din kan be om ---
@app.route('/api/get_groups')
def get_groups():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, group_name, company_name FROM groups")
    rows = c.fetchall()
    conn.close()
    
    groups = []
    for r in rows:
        groups.append({
            "id": r[0],
            "group_id": r[0],        # Noen scripter bruker group_id
            "name": r[1],            # Noen scripter bruker name
            "group_name": r[1],      # Andre bruker group_name
            "company": r[2],         # Noen bruker company
            "company_name": r[2]     # Andre bruker company_name
        })
    return jsonify(groups)

@app.route('/api/create_group', methods=['POST'])
def create_group():
    try:
        data = request.get_json()
        # Vi henter ut data uansett om det heter group_name eller name
        g_name = data.get('group_name') or data.get('name')
        c_name = data.get('company_name') or data.get('company')
        g_id = data.get('group_id') or g_name.lower().replace(" ", "-")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO groups (id, group_name, company_name) VALUES (?, ?, ?)",
                  (g_id, g_name, c_name))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=15"
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
        return jsonify({"status": "success", "count": len(data)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
