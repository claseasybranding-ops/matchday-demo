@app.route('/super_admin_dashboard')
def super_admin():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Vi henter alt uten filter først for å se at det virker
        c.execute("SELECT * FROM fixtures")
        alle_kamper = c.fetchall()
        conn.close()
        
        # Logg til konsollen (for feilsøking i Render-loggen)
        print(f"Fant {len(alle_kamper)} kamper i databasen")
        
        return render_template('super_admin.html', kamper=alle_kamper)
    except Exception as e:
        return f"Databasefeil: {str(e)}"
