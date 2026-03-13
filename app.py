from flask import Flask, render_template, request, jsonify
import requests, json, os, sqlite3

app = Flask(__name__)
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"
DB = "matchday.db"
STATUS_FIL = "live_state.json"

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS tips (navn TEXT, h_tips INT, b_tips INT, gg INT)')
        conn.commit()

init_db()

def hent_status():
    if os.path.exists(STATUS_FIL):
        with open(STATUS_FIL, 'r') as f: return json.load(f)
    return {"h_navn": "Liverpool", "b_navn": "Chelsea", "h_score": 0, "b_score": 0, "minutt": "0'", "hendelse": "Venter på kampstart"}

@app.route('/')
def index():
    status = hent_status()
    return render_template('index.html', s=status)

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

@app.route('/api/hent_neste')
def hent_neste():
    url = "https://v3.football.api-sports.io/fixtures?team=40&next=1"
    headers = {"x-apisports-key": API_KEY}
    try:
        res = requests.get(url, headers=headers).json()
        kamp = res['response'][0]
        ny_status = {
            "h_navn": kamp['teams']['home']['name'],
            "b_navn": kamp['teams']['away']['name'],
            "h_score": 0, "b_score": 0, "minutt": "0'",
            "hendelse": "Hentet fra API: " + kamp['fixture']['date']
        }
        with open(STATUS_FIL, 'w') as f: json.dump(ny_status, f)
        return jsonify({"status": "Suksess", "kamp": ny_status})
    except:
        return jsonify({"status": "Feil ved henting"})

@app.route('/send_tips', methods=['POST'])
def send_tips():
    d = request.json
    with sqlite3.connect(DB) as conn:
        conn.execute("INSERT INTO tips VALUES (?,?,?,?)", (d['navn'], d['h'], d['b'], d['gg']))
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
