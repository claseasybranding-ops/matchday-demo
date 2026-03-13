from flask import Flask, render_template, request, jsonify
import json, os

app = Flask(__name__)

CONFIG_FIL = "oppsett.json"

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
        return default
    with open(CONFIG_FIL, 'r') as f:
        try: return json.load(f)
        except: return default

@app.route('/')
def index():
    return render_template('index.html', o=hent_oppsett())

@app.route('/admin_secret_fFK', methods=['GET', 'POST'])
def admin():
    oppsett = hent_oppsett()
    if request.method == 'POST':
        nytt = {
            "gruppe": request.form.get('gruppe'),
            "modus": request.form.get('modus'),
            "kamper": json.loads(request.form.get('kamp_data'))
        }
        with open(CONFIG_FIL, 'w') as f:
            json.dump(nytt, f)
        return render_template('admin.html', o=nytt, msg="Lagret!")
    return render_template('admin.html', o=oppsett)

@app.route('/send_tips', methods=['POST'])
def send_tips():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
