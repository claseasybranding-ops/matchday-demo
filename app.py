@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi fjerner sesong-filteret og ber om kommende kamper (fixtures)
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=50"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        res = requests.get(url, headers=headers).json()
        data = res.get('response', [])
        
        if not data:
            return jsonify({"status": "API-et returnerte ingen kamper. Sjekk om liga-ID er korrekt eller om sesongen er over."})

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
        return jsonify({"status": f"Feil: {str(e)}"})
