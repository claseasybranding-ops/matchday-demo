from flask import Flask, render_template, request, jsonify
import json, os

app = Flask(__name__)

# Enkel funksjon for å styre status uten database-krøll i starten
def hent_status():
    return {
        "h_navn": "Liverpool", 
        "b_navn": "Chelsea", 
        "h_score": 0, 
        "b_score": 0, 
        "minutt": "0'", 
        "hendelse": "Venter på kampstart"
    }

@app.route('/')
def index():
    # Vi sender statusen til det lyse designet
    return render_template('index.html', s=hent_status())

@app.route('/admin_secret_fFK')
def admin():
    return render_template('admin.html', s=hent_status())

@app.route('/send_tips', methods=['POST'])
def send_tips():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
