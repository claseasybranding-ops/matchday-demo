@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi henter fra i dag og 7 dager frem i tid
    today = datetime.now().strftime('%Y-%m-%d')
    next_week = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Vi fjerner 'season' parameteren helt for å la API-et velge riktig sesong selv
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&from={today}&to={next_week}&timezone=Europe/Oslo"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])
        
        # Hvis det fortsatt er tomt, prøver vi en siste gang uten dato, men med 'next=10'
        # (Selv om noen planer nekter 'next', fungerer det ofte som fallback uten 'season')
        if not data:
            url_fallback = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=10"
            res = requests.get(url_fallback, headers=headers).json()
            data = res.get('response', [])

        if not data:
            return jsonify({"status": f"Ingen kamper funnet. API-svar: {res}"})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Hentet {len(data)} kamper."})
    except Exception as e:
        return jsonify({"status": f"Feil: {str(e)}"})
