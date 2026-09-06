from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Database
if 'CREATE TABLE IF NOT EXISTS zone_groups' not in text:
    marker = '    CREATE TABLE IF NOT EXISTS zones (\n'
    block = '''    CREATE TABLE IF NOT EXISTS zone_groups (\n      id INTEGER PRIMARY KEY AUTOINCREMENT,\n      name TEXT NOT NULL UNIQUE,\n      created_at TEXT NOT NULL\n    );\n'''
    if marker not in text:
        raise SystemExit('Zone table marker not found')
    text = text.replace(marker, block + marker, 1)

if "PRAGMA table_info(zones)" not in text:
    marker = "    columns = {row['name'] for row in con.execute('PRAGMA table_info(tickets)').fetchall()}\n"
    addition = "    zone_columns = {row['name'] for row in con.execute('PRAGMA table_info(zones)').fetchall()}\n    if 'group_id' not in zone_columns:\n        con.execute('ALTER TABLE zones ADD COLUMN group_id INTEGER')\n    con.execute('CREATE INDEX IF NOT EXISTS idx_zones_group ON zones(group_id)')\n"
    if marker not in text:
        raise SystemExit('DB migration marker not found')
    text = text.replace(marker, addition + marker, 1)

# Pulsante nella pagina Zone / QR
old = '<div class="card span-8"><h2>Zone esistenti</h2>'
new = '<div class="card span-8"><div class="actions" style="justify-content:space-between"><h2>Zone esistenti</h2><a class="btn" href="zone-groups">📁 Gestisci gruppi</a></div>'
if old in text:
    text = text.replace(old, new, 1)
elif 'href="zone-groups"' not in text:
    raise SystemExit('Zones page marker not found')

# Rotte gruppi
route_marker = "@admin_app.get('/materials', response_class=HTMLResponse)"
if "@admin_app.get('/zone-groups'" not in text:
    routes = r"""
@admin_app.get('/zone-groups', response_class=HTMLResponse)
def zone_groups_page(message: str = ''):
    con = db()
    groups = con.execute('SELECT g.*, COUNT(z.id) AS zone_count FROM zone_groups g LEFT JOIN zones z ON z.group_id=g.id GROUP BY g.id ORDER BY g.name').fetchall()
    ungrouped = con.execute('SELECT COUNT(*) AS n FROM zones WHERE group_id IS NULL').fetchone()['n']
    con.close()
    rows = ''.join(f'<div class="zone-row"><div><b>📁 {esc(g["name"])}</b><br><span class="muted">{g["zone_count"]} zone</span></div><div class="actions"><a class="btn" href="zone-group/{g["id"]}/edit">Assegna zone</a><form method="post" action="zone-group/{g["id"]}/delete" onsubmit="return confirm(\'Eliminare il gruppo? Le zone resteranno disponibili.\')"><button class="danger" type="submit">Elimina</button></form></div></div>' for g in groups)
    if ungrouped:
        rows += f'<div class="notice">Zone senza gruppo: <b>{ungrouped}</b></div>'
    if not rows:
        rows = '<p class="muted">Nessun gruppo creato.</p>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid"><div class="card span-8"><h2>Gruppi di zone</h2>{rows}</div><div class="card span-4"><h2>Nuovo gruppo</h2><form method="post" action="zone-groups/create"><label>Nome gruppo</label><input name="name" maxlength="80" required placeholder="Es. Ristorante"><button type="submit">📁 Crea gruppo</button></form></div></div>'''
    return page('Gruppi di zone', body, back_url='zones')


@admin_app.post('/zone-groups/create')
def zone_group_create(name: str = Form(...)):
    name = name.strip()
    if not name or len(name) > 80:
        raise HTTPException(400, 'Nome gruppo non valido')
    con = db()
    try:
        con.execute('INSERT INTO zone_groups(name,created_at) VALUES(?,?)', (name, now_iso()))
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        return RedirectResponse('../zone-groups?message=' + urllib.parse.quote('Esiste già un gruppo con questo nome.'), status_code=303)
    con.close()
    return RedirectResponse('../zone-groups?message=' + urllib.parse.quote('Gruppo creato correttamente.'), status_code=303)


@admin_app.get('/zone-group/{group_id}/edit', response_class=HTMLResponse)
def zone_group_edit(group_id: int):
    con = db()
    group = con.execute('SELECT * FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    zones = con.execute('SELECT z.*, g.name AS current_group FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id ORDER BY z.name').fetchall()
    con.close()
    if not group:
        raise HTTPException(404, 'Gruppo non trovato')
    checks = ''
    for z in zones:
        checked = 'checked' if z['group_id'] == group_id else ''
        current = f' · ora in {esc(z["current_group"])}' if z['current_group'] and z['group_id'] != group_id else ''
        checks += f'<label style="display:flex;gap:10px;align-items:center;padding:12px;border-bottom:1px solid var(--line)"><input style="width:auto" type="checkbox" name="zone_ids" value="{z["id"]}" {checked}><span><b>{esc(z["name"])}</b><span class="muted">{current}</span></span></label>'
    if not checks:
        checks = '<p class="muted">Non ci sono ancora zone.</p>'
    body = f'''<div class="card"><h2>📁 {esc(group['name'])}</h2><p class="muted">Seleziona le zone che vuoi inserire in questo gruppo. Una zona può appartenere a un solo gruppo.</p><form method="post" action="edit/save">{checks}<button type="submit" style="margin-top:16px">Salva assegnazione</button></form></div>'''
    return page(f'Gruppo · {group["name"]}', body, back_url='../../zone-groups')


@admin_app.post('/zone-group/{group_id}/edit/save')
def zone_group_save(group_id: int, zone_ids: list[int] = Form(default=[])):
    con = db()
    group = con.execute('SELECT id FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    if not group:
        con.close()
        raise HTTPException(404, 'Gruppo non trovato')
    con.execute('UPDATE zones SET group_id=NULL WHERE group_id=?', (group_id,))
    for zone_id in zone_ids:
        con.execute('UPDATE zones SET group_id=? WHERE id=?', (group_id, int(zone_id)))
    con.commit()
    con.close()
    return RedirectResponse('../../../zone-groups?message=' + urllib.parse.quote('Zone assegnate correttamente.'), status_code=303)


@admin_app.post('/zone-group/{group_id}/delete')
def zone_group_delete(group_id: int):
    con = db()
    group = con.execute('SELECT id FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    if not group:
        con.close()
        raise HTTPException(404, 'Gruppo non trovato')
    con.execute('UPDATE zones SET group_id=NULL WHERE group_id=?', (group_id,))
    con.execute('DELETE FROM zone_groups WHERE id=?', (group_id,))
    con.commit()
    con.close()
    return RedirectResponse('../../zone-groups?message=' + urllib.parse.quote('Gruppo eliminato. Le zone non sono state eliminate.'), status_code=303)


"""
    if route_marker not in text:
        raise SystemExit('Route insertion marker not found')
    text = text.replace(route_marker, routes + route_marker, 1)

path.write_text(text, encoding='utf-8')