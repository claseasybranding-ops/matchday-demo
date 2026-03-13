from flask import Flask, render_template, request, jsonify
import requests, json, os, sqlite3
from datetime import datetime

app = Flask(__name__)
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"
DB = "matchday.db"

# --- SYSTEM-LOGIKK ---
def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS tips (navn TEXT, h_tips INT, b_tips INT, gg INT)')
        conn.commit()

init_db()

# Denne filen lagrer "Live"-statusen du styrer manuelt
STATUS_FIL = "live_state.json"

def hent_status():
    if os.path.exists(STATUS_FIL):
        with open(STATUS_FIL, 'r') as f: return json.load(f)
    return {"h_navn": "Liverpool", "b_navn": "Chelsea", "h_score": 0, "b_score": 0, "minutt": "0'", "hendelse": "Kampen starter snart"}

# --- RUTER FOR BRUKERE ---
@app.route('/')
def index():
    status = hent_status()
    return render_template('index.html', s=status)

@app.route('/send_tips', methods=['POST'])
def send_tips():
    d = request.json
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO tips VALUES (?,?,?,?)", (d['navn'], d['h'], d['b'], d['gg']))
    return jsonify({"status": "ok"})

# --- DEN HEMMELIGE ADMIN-OVERSTYRINGEN ---
# Denne bruker du under demoen for å "pushe" resultater live
@app.route('/admin_secret_fFK', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        ny_status = {
            "h_navn": request.form.get('h_navn'),
            "b_navn": request.form.get('b_navn'),
            "h_score": request.form.get('h_score'),
            "b_score": request.form.get('b_score'),
            "minutt": request.form.get('minutt'),
            "hendelse": request.form.get('hendelse')
        }
        with open(STATUS_FIL, 'w') as f: json.dump(ny_status, f)
    
    return render_template('admin.html', s=hent_status())

# API-bevis: Henter neste kamp for å vise teknologien
@app.route('/api_bevis')
def api_bevis():
    url = "https://v3.football.api-sports.io/fixtures?league=39&next=1"
    headers = {"x-apisports-key": API_KEY}
    res = requests.get(url, headers=headers).json()
    # Her kan du vise investoren JSON-dataene direkte for å bevise integrasjonen
    return jsonify(res)

if __name__ == '__main__':
    app.run(debug=True)
