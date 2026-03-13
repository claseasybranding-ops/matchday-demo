@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi bruker dagens dato
    fra_dato = datetime.now().strftime('%Y-%m-%d')
    # Vi henter for de neste 10 dagene for å holde oss innenfor grensene
    til_dato = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
    
    # Vi legger til timezone=Europe/Oslo (viktig for gratis-planen)
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&from={fra_dato}&to={til_dato}&timezone=Europe/Oslo"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        
        # Hvis vi fortsatt får feil, prøver vi en siste "nød-metode" uten dato-filter
        if res.get('errors') and 'plan' in str(res.get('errors')):
            # Denne henter bare de absolutt neste kampene uansett plan
            url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&last=10"
            response = requests.get(url, headers=headers)
            res = response.json()

        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": f"Fant ingen kamper. API-svar: {res}"})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        
        return jsonify({"status": f"Suksess! Importerte {len(data)} kamper."})
        
    except Exception as e:
        return jsonify({"status": f"Feil ved import: {str(e)}"})
