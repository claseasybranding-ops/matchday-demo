# --- GRUPPE ADMIN SIDE (Der lederen plukker kamper) ---
@app.route('/group/<slug>/admin')
def group_admin(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Hent info om gruppen
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    
    # Hent alle tilgjengelige kamper fra bufféen
    c.execute("SELECT * FROM fixtures ORDER BY date ASC")
    all_fixtures = c.fetchall()
    
    # Hent ID-ene til kampene gruppen ALLEREDE har valgt
    c.execute("SELECT fixture_id FROM group_selections WHERE group_id = ?", (group[0],))
    selected_ids = [row[0] for row in c.fetchall()]
    
    conn.close()
    return render_template('group_admin.html', group=group, all_fixtures=all_fixtures, selected_ids=selected_ids)

# --- API FOR Å VELGE/FJERNE KAMP ---
@app.route('/api/toggle_match', methods=['POST'])
def toggle_match():
    data = request.json
    group_id = data.get('group_id')
    fixture_id = data.get('fixture_id')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Sjekk om kampen allerede er valgt
    c.execute("SELECT * FROM group_selections WHERE group_id = ? AND fixture_id = ?", (group_id, fixture_id))
    exists = c.fetchone()
    
    if exists:
        c.execute("DELETE FROM group_selections WHERE group_id = ? AND fixture_id = ?", (group_id, fixture_id))
        action = "fjernet"
    else:
        c.execute("INSERT INTO group_selections VALUES (?, ?)", (group_id, fixture_id))
        action = "lagt til"
        
    conn.commit()
    conn.close()
    return jsonify({"status": "Suksess", "action": action})

# --- GRUPPE VEGG (Siden folk ser via link) ---
@app.route('/group/<slug>')
def group_view(slug):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE slug = ?", (slug,))
    group = c.fetchone()
    
    # Hent KUN kampene denne gruppen har valgt
    c.execute('''SELECT f.* FROM fixtures f 
                 JOIN group_selections gs ON f.id = gs.fixture_id 
                 WHERE gs.group_id = ? ORDER BY f.date ASC''', (group[0],))
    matches = c.fetchall()
    conn.close()
    return render_template('group_view.html', group=group, matches=matches)
