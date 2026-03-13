from datetime import datetime, timedelta

@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi henter dato for i dag og 14 dager frem i tid
    fra_dato = datetime.now().strftime('%Y-%m-%d')
    til_dato = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
    
    # Vi bruker 'from' og 'to' i stedet for 'next' (Dette er gratis!)
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&from={fra_dato}&to={til_dato}"
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": f"Ingen kamper funnet mellom {fra_dato} og {til_dato}. Sjekk om ligaen spiller nå."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for f in data:
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        conn.commit()
        conn.close()
        
        return jsonify({"status": f"Suksess! Importerte {len(data)} kamper for de neste 14 dagene."})
        
    except Exception as e:
        return jsonify({"status": f"Feil ved import: {str(e)}"})
