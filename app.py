from flask import Flask, render_template, request, jsonify
import requests, json, os

app = Flask(__name__)
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"
CONFIG_FIL = "konkurranse_oppsett.json"

def hent_oppsett():
    if os.path.exists(CONFIG_FIL):
        with open(CONFIG_FIL, 'r') as f: return json.load(f)
    return {
        "gruppe": "Liverbirds Fredrikstad",
        "modus": "singel",
        "kamper": [{
            "id": 40, "h_navn": "Liverpool", "b_navn": "Chelsea", 
            "h_logo": "https://media.api-sports.io/football/teams/40.png",
            "b_logo": "https://media.api-sports.io/football/teams/49.png"
        }]
    }

@app.route('/')
def index():
    oppsett = hent_oppsett()
    return render_template('index.html', o=oppsett)

@app.route('/admin_secret_fFK', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # Her lagrer vi valgene dine fra admin-panelet
        nytt_oppsett = {
            "gruppe": request.form.get('gruppe'),
            "modus": request.form.get('modus'),
            "kamper": json.loads(request.form.get('kamp_data'))
        }
        with open(CONFIG_FIL, 'w') as f: json.dump(nytt_oppsett, f)
    return render_template('admin.html', o=hent_oppsett())

@app.route('/api/sok_kamp')
def sok_kamp():
    lag_navn = request.args.get('lag')
    url = f"https://v3.football.api-sports.io/teams?search={lag_navn}"
    headers = {'x-apisports-key': API_KEY}
    res = requests.get(url, headers=headers).json()
    return jsonify(res)

if __name__ == '__main__':
    app.run(debug=True)
