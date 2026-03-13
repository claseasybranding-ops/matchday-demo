@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # VIKTIG: Bytt ut denne med den du kopierte akkurat nå fra dashbordet
    API_KEY = "c06ecd6de7644023a13c7b881248e5bc"
    
    # Vi prøver den absolutt enkleste metoden først
    url = f"https://v3.football.api-sports.io/status"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        res = requests.get(url, headers=headers).json()
        # Dette vil fortelle oss om nøkkelen virker i det hele tatt
        if res.get('errors'):
            return jsonify({"status": f"API-et sier NEI: {res['errors']}"})
        
        # Hvis status var OK, henter vi kamper
        url_fixtures = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=20"
        res_fixtures = requests.get(url_fixtures, headers=headers).json()
        
        data = res_fixtures.get('response', [])
        if not data:
            return jsonify({"status": f"Nøkkel OK, men fant ingen kamper. Svar: {res_fixtures}"})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": "Suksess! Nøkkelen virker og kamper er lagret."})
        
    except Exception as e:
        return jsonify({"status": f"Systemet feilet: {str(e)}"})
