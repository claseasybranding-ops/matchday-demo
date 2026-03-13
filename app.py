from flask import Flask, render_template, request, jsonify
import requests, os

app = Flask(__name__)

# Her kan vi senere legge inn ekte API-kall til API-Sports
def hent_kamper():
    return [
        {
            "id": 1, 
            "h_navn": "Liverpool", "h_logo": "https://media.api-sports.io/football/teams/40.png",
            "b_navn": "Chelsea", "b_logo": "https://media.api-sports.io/football/teams/49.png",
            "h_score": 0, "b_score": 0
        },
        {
            "id": 2, 
            "h_navn": "Bodø/Glimt", "h_logo": "https://media.api-sports.io/football/teams/933.png",
            "b_navn": "Fredrikstad", "b_logo": "https://media.api-sports.io/football/teams/3501.png",
            "h_score": 0, "b_score": 0
        }
    ]

@app.route('/')
def index():
    return render_template('index.html', kamper=hent_kamper())

@app.route('/send_tips', methods=['POST'])
def send_tips():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
