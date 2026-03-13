@app.route('/api/import_league/<int:league_id>')
def import_league(league_id):
    # Vi spesifiserer sesong 2025 (som dekker mars 2026)
    # Vi henter de neste 50 kampene
    url = f"https://v3.football.api-sports.io/fixtures?league={league_id}&season=2025&next=50"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        response = requests.get(url, headers=headers)
        res = response.json()
        data = res.get('response', [])
        
        # Logg for feilsøking (ses i Render-loggen)
        print(f"API Svar for liga {league_id}: {res}")

        if not data:
            # Hvis 2025 er tom, prøver vi uten sesong-filter som en siste utvei
            url_fallback = f"https://v3.football.api-sports.io/fixtures?league={league_id}&next=50"
            res = requests.get(url_fallback, headers=headers).json()
            data = res.get('response', [])

        if not data:
            return jsonify({"status": "API returnerte 0 kamper. Sjekk API-nøkkel eller om ligaen har kamper nå."})

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for f in data:
            # Vi lagrer dataene
            c.execute("INSERT OR REPLACE INTO fixtures VALUES (?,?,?,?,?,?,?,?)",
                      (f['fixture']['id'], league_id, f['teams']['home']['name'], 
                       f['teams']['away']['name'], f['teams']['home']['logo'], 
                       f['teams']['away']['logo'], f['fixture']['date'], 'upcoming'))
        
        conn.commit()
        conn.close()
        return jsonify({"status": f"Suksess! Importerte {len(data)} kamper."})
    except Exception as e:
        return jsonify({"status": f"Systemfeil: {str(e)}"})
