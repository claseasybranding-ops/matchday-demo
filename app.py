from flask import Flask, render_template, request, jsonify
import requests, json, os, sqlite3

app = Flask(__name__)
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"
STATUS_FIL = "live_state.json"

def hent_status():
    if os.path.exists(STATUS_FIL):
        with open(STATUS_FIL, 'r') as f: return json.load(f)
    # Standard-oppsett hvis fila ikke finnes
    return [
        {"id": 1, "h_navn": "Liverpool", "b_navn": "Chelsea", "h_score": 0, "b_score": 0, "minutt": "0'", "hendelse": "Venter på kampstart"},
        {"id": 2, "h_navn": "Man City", "b_navn": "Arsenal", "h_score": 0, "b_score": 0, "minutt": "0'", "hendelse": "Venter på kampstart"},
        {"id": 3, "h_navn": "Bodø/Glimt", "b_navn": "Fredrikstad", "h_score": 0, "b_score": 0, "minutt": "0'", "hendelse": "Venter på kampstart"}
    ]

@app.route('/')
def index():
    kamper = hent_status()
    return render_template('index.html', kamper=kamper)

@app.route('/admin_secret_fFK')
def admin():
    return render_template('admin.html', kamper=hent_status())

@app.route('/api/oppdater_kamp', methods=['POST'])
def oppdater_kamp():
    ny_data = request.json
    with open(STATUS_FIL, 'w') as f: json.dump(ny_data, f)
    return jsonify({"status": "ok"})

@app.route('/api/hent_fra_api')
def hent_fra_api():
    # Her kobler vi til API-Sports for å hente ekte data (Modul 2)
    headers = {"x-apisports-key": API_KEY}
    # Eksempel: Henter neste Liverpool-kamp
    res = requests.get("https://v3.football.api-sports.io/fixtures?team=40&next=1", headers=headers).json()
    return jsonify(res)

if __name__ == '__main__':
    app.run(debug=True)
