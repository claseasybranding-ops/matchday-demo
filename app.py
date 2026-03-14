import sqlite3
from flask import Flask, render_template, request, jsonify
import requests
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "matchday_pro.db")
API_KEY = "58f8589c07824c2495869fa6b7b815e5"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fixtures 
                 (id INTEGER PRIMARY KEY, league_id TEXT, h_navn TEXT, b_navn TEXT, 
                  h_logo TEXT, b_logo TEXT, date TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, slug TEXT UNIQUE, admin_name TEXT)''')
    
    # Lagt til is_single_game her
    c.execute('''CREATE TABLE IF NOT EXISTS group_selections 
                 (group_id INTEGER, fixture_id INTEGER, is_single_game INTEGER DEFAULT 0, 
                  PRIMARY KEY(group_id, fixture_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS predictions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, fixture_id INTEGER, 
                  user_name TEXT, h_score INTEGER, b_score INTEGER, extra_data TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def super_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    kamper = c.fetchall()
    c.execute("SELECT * FROM groups")
    grupper = c.fetchall()
    conn.close()
    return render_template('super_admin.html', kamper=kamper, grupper=grupper)

@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    if not group:
        conn.close()
        return "Gruppe ikke funnet", 404
    
    # Henter kamper og info om det er single-game
    c.execute('''SELECT f.*, gs.is_single_game FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id 
                 WHERE gs.group_id = ? ORDER BY f.date ASC''', (group[0],))
    matches = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, matches=matches)

# API-funksjoner (Husk å beholde import_league, create_group osv som før)
# ... [Samme API-funksjoner som tidligere meldinger] ...

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
