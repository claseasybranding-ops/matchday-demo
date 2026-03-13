@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        # STEG 1: Finn ut hva som er "gjeldende runde" (Dette er alltid gratis)
        round_url = f"https://v3.football.api-sports.io/fixtures/rounds?league={league_id}&season=2025&current=true"
        round_res = requests.get(round_url, headers=headers).json()
        current_round = round_res.get('response', [None])[0]
        
        if not current_round:
            # Fallback hvis de ikke har en "current" runde akkurat nå
            current_round = "Regular Season - 30" 

        # STEG 2: Hent alle kamper i denne runden
        url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&round={current_round}&timezone=Europe/Oslo"
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])

        if not data:
            return jsonify({"status": f"Fant ingen kamper i {current_round}. API-svar: {res}"})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        
        return jsonify({"status": f"Suksess! Importerte {len(data)} kamper fra {current_round}."})
        
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})
