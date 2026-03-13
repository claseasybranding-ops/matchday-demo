from flask import Flask, render_template, request, jsonify
import requests, os

app = Flask(__name__)

# Din unike nøkkel til fotballdata
API_KEY = "c06ec6de7644023e13c7b881248ef5bc"

def hent_live_kamper():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {
        'x-apisports-key': API_KEY
    }
    
    try:
        response = requests.get(url, headers=headers).json()
        kamper = []
        
        # Vi henter ut de 3 første live-kampene som et bevis på at det funker
        for i in range(min(3, len(response['response']))):
            item = response['response'][i]
            kamper.append({
                "id": item['fixture']['id'],
                "h_navn": item['teams']['home']['name'],
                "h_logo": item['teams']['home']['logo'],
                "b_navn": item['teams']['away']['name'],
                "b_logo": item['teams']['away']['logo'],
                "h_score": item['goals']['home'],
                "b_score": item['goals']['away']
            })
        
        # Hvis ingen kamper er live, viser vi Liverpool som backup
        if not kamper:
            return [{
                "id": 1, 
                "h_navn": "Liverpool", "h_logo": "https://media.api-sports.io/football/teams/40.png",
                "b_navn": "Chelsea", "b_logo": "https://media.api-sports.io/football/teams/49.png",
                "h_score": 0, "b_score": 0
            }]
        return kamper
    except:
        return []

@app.route('/')
def index():
    return render_template('index.html', kamper=hent_live_kamper())

@app.route('/send_tips', methods=['POST'])
def send_tips():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True)
