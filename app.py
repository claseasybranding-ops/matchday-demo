@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        # 1. Finn ut hvilken runde som pågår eller er neste
        round_url = f"https://v3.football.api-sports.io/fixtures/rounds?league={league_id}&season=2025&current=true"
        r_res = requests.get(round_url, headers=headers).json()
        current_round = r_res.get('response', [None])[0]
        
        if not current_round:
            return jsonify({"status": "Fant ingen aktiv runde akkurat nå."})

        # 2. Hent alle kampene i den runden
        url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&round={current_round}&timezone=Europe/Oslo"
        res = requests.get(url, headers=headers).json()
        data = res.get('response', [])

        if not data:
            return jsonify({"status": f"Runden {current_round} er tom."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        
        return jsonify({"status": f"Suksess! Hentet {len(data)} kamper fra {current_round}"})
        
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})
