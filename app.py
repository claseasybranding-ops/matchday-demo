import sqlite3
from flask import Flask, render_template, request, jsonify
import requests, os
from datetime import datetime

app = Flask(__name__)
DB_PATH = "matchday_pro.db"
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, admin_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, PRIMARY KEY(group_id, fixture_id))''')
    conn.commit()
    conn.close()

init_db()

@app.route('/super_admin_dashboard')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    kamper = c.fetchall()
    c.execute("SELECT * FROM groups")
    grupper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=kamper, grupper=grupper)

@app.route('/api/create_group', methods=['POST'])
def create_group():
    data = request.json
    name = data.get('name')
    slug = name.lower().replace(" ", "-")
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO groups (name, slug, admin_name) VALUES (?, ?, ?)", 
                  (name, slug, data.get('admin_name')))
        conn.commit()
        conn.close()
        return jsonify({"status": "Suksess!"})
    except:
        return jsonify({"status": "Feil: Navnet er kanskje tatt?"})

@app.route('/api/import_league/<string:league_code>')
def import_league(league_code):
    url = f"https://api.football-data.org/v4/competitions/{league_code}/matches?status=SCHEDULED"
    headers = { 'X-Auth-Token': API_KEY }
    res = requests.get(url, headers=headers).json()
    matches = res.get('matches', [])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for m in matches[:30]:
        c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                  (m['id'], league_code, m['homeTeam']['shortName'], m['awayTeam']['shortName'], 
                   m['homeTeam']['crest'], m['awayTeam']['crest'], m['utcDate'], 'upcoming'))
    conn.commit()
    conn.close()
    return jsonify({"status": "Importert!"})

if __name__ == '__main__':
    app.run(debug=True)
