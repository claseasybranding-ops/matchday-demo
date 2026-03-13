from flask import Flask, render_template, request, jsonify
import json, os, requests

app = Flask(__name__)

# Innstillinger
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"
CONFIG_FIL = "konkurranse_oppsett.json"

# Funksjon for å hente eller lage standard-oppsett
def hent_oppsett():
    default = {
        "gruppe": "Liverbirds Fredrikstad",
        "modus": "singel",
        "kamper": [{
            "id": 1, 
            "h_navn": "Liverpool", "h_logo": "https://media.api-sports.io/football/teams/40.png",
            "b_navn": "Chelsea", "b_logo": "https://media.api-sports.io/football/teams/49.png"
        }]
    }
    if not os.path.exists(CONFIG_FIL):
        with open(CONFIG_FIL, 'w') as f:
            json.dump(default, f)
        return default
    
    with open(CONFIG_FIL, 'r') as f:
        try:
            return json.load(f)
        except:
            return default

@app.route('/')
def index():
    return render_template('index.html', o=hent_oppsett())

@app.route('/admin_secret_fFK', methods=['GET', 'POST'])
def admin():
    oppsett = hent_oppsett()
    if request.method == 'POST':
        nytt_oppsett = {
            "gruppe": request.form.get('gruppe'),
            "modus": request.form.get('modus'),
            "kamper": json.loads(request.form.get('kamp_data'))
        }
        with open(CONFIG_FIL, 'w') as f:
            json.dump(nytt_oppsett, f)
        return render_template('admin.html', o=nytt_oppsett, msg="Oppdatert!")
    
    return render_template('admin.html', o=oppsett)

@app.route('/send_tips', methods=['POST'])
def send_tips():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
