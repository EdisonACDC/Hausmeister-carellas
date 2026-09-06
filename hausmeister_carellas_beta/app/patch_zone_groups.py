from pathlib import Path
import re

path = Path('/app/app/main.py')
if not path.exists():
    path = Path(__file__).with_name('main.py')
text = path.read_text(encoding='utf-8')

# Database: gruppi di zone e collegamento opzionale dalla zona al gruppo.
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

# Dashboard: carica il nome del gruppo per ogni zona.
text = text.replace(
    "    zones = con.execute('SELECT * FROM zones ORDER BY name').fetchall()\n",
    "    zones = con.execute('SELECT z.*, g.name AS group_name FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id ORDER BY COALESCE(g.name, \'ZZZZZZ\'), z.name').fetchall()\n",
    1,
)

# Dashboard: mostra prima i gruppi invece di tutte le zone.
pattern = re.compile(r"^    zone_rows = ''\.join\(.*?\) or '<p class=\\\"muted\\\">Nessuna zona</p>'$", re.M)
replacement = '''    group_map = {}
    for z in zones:
        key = z['group_id'] or 0
        if key not in group_map:
            group_map[key] = {'name': z['group_name'] or 'Senza gruppo', 'zones': []}
        group_map[key]['zones'].append(z)
    zone_rows = ''.join(
        f'<a class="zone-row" style="text-decoration:none" href="zone-group/{group_id}"><div><b>📁 {esc(data["name"])}</b><br><span class="muted">{len(data["zones"])} zone</span></div><span class="btn">Apri →</span></a>'
        for group_id, data in group_map.items()
    ) or '<p class="muted">Nessuna zona</p>' '''
if pattern.search(text):
    text = pattern.sub(replacement.rstrip(), text, count=1)
elif "group_map = {}" not in text:
    raise SystemExit('Dashboard zone_rows marker not found')

# Pagina Zone/QR: aggiunge accesso alla gestione gruppi e colonna gruppo.
old_query = "    zones = con.execute('SELECT z.*, COUNT(t.id) ticket_count FROM zones z LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY z.name').fetchall()"
new_query = "    zones = con.execute('SELECT z.*, g.name AS group_name, COUNT(t.id) ticket_count FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY COALESCE(g.name, \'ZZZZZZ\'), z.name').fetchall()"
text = text.replace(old_query, new_query, 1)

old_rows = "    rows = ''.join(f'''<tr{' class=\\\"new-zone\\\"' if z['id'] == created else ''}><td><b>{esc(z['name'])}</b></td><td>{'Attiva' if z['active'] else 'Disattivata'}</td><td>{z['ticket_count']}</td><td><a class=\\\"btn\\\" href=\\\"zone/{z['id']}\\\">Gestisci / QR</a></td></tr>''' for z in zones) or '<tr><td colspan=\\\"4\\\">Nessuna zona</td></tr>'"
new_rows = "    rows = ''.join(f'''<tr{' class=\\\"new-zone\\\"' if z['id'] == created else ''}><td><b>{esc(z['name'])}</b></td><td>{esc(z['group_name'] or 'Senza gruppo')}</td><td>{'Attiva' if z['active'] else 'Disattivata'}</td><td>{z['ticket_count']}</td><td><a class=\\\"btn\\\" href=\\\"zone/{z['id']}\\\">Gestisci / QR</a></td></tr>''' for z in zones) or '<tr><td colspan=\\\"5\\\">Nessuna zona</td></tr>'"
text = text.replace(old_rows, new_rows, 1)

old_page = "<div class=\"card span-8\"><h2>Zone esistenti</h2><div class=\"table-wrap\"><table><tr><th>Zona</th><th>Stato</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class=\"card span-4\"><h2>Nuova zona</h2>"
new_page = "<div class=\"card span-8\"><div class=\"actions\" style=\"justify-content:space-between\"><h2>Zone esistenti</h2><a class=\"btn\" href=\"zone-groups\">📁 Gestisci gruppi</a></div><div class=\"table-wrap\"><table><tr><th>Zona</th><th>Gruppo</th><th>Stato</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class=\"card span-4\"><h2>Nuova zona</h2>"
text = text.replace(old_page, new_page, 1)

# Rotte per gruppi e pagina di navigazione del singolo gruppo.
route_marker = "@admin_app.get('/materials', response_class=HTMLResponse)"
if "@admin_app.get('/zone-groups'" not in text:
    routes = r"""
@admin_app.get('/zone-groups', response_class=HTMLResponse)
def zone_groups_page(message: str = ''):
    con = db()
    groups = con.execute('SELECT g.*, COUNT(z.id) AS zone_count FROM zone_groups g LEFT JOIN zones z ON z.group_id=g.id GROUP BY g.id ORDER BY g.name').fetchall()
    ungrouped = con.execute('SELECT COUNT(*) AS n FROM zones WHERE group_id IS NULL').fetchone()['n']
    con.close()
    rows = ''.join(f'<div class="zone-row"><div><b>📁 {esc(g["name"])}</b><br><span class="muted">{g["zone_count"]} zone</span></div><div class="actions"><a class="btn" href="zone-group/{g["id"]}">Apri</a><a class="btn" href="zone-group/{g["id"]}/edit">Modifica</a></div></div>' for g in groups)
    if ungrouped:
        rows += f'<div class="zone-row"><div><b>📁 Senza gruppo</b><br><span class="muted">{ungrouped} zone</span></div><a class="btn" href="zone-group/0">Apri</a></div>'
    if not rows:
        rows = '<p class="muted">Nessun gruppo creato.</p>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Gruppi di zone', f'''{notice}<div class="grid"><div class="card span-8"><h2>Gruppi</h2>{rows}</div><div class="card span-4"><h2>Nuovo gruppo</h2><form method="post" action="zone-groups/create"><label>Nome gruppo</label><input name="name" maxlength="80" required placeholder="Es. Ristorante"><button>📁 Crea gruppo</button></form></div></div>''', back_url='zones')


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
        return RedirectResponse('zone-groups?message=' + urllib.parse.quote('Esiste già un gruppo con questo nome.'), status_code=303)
    con.close()
    return RedirectResponse('zone-groups?message=' + urllib.parse.quote(f'Gruppo "{name}" creato.'), status_code=303)


@admin_app.get('/zone-group/{group_id}', response_class=HTMLResponse)
def zone_group_view(group_id: int):
    con = db()
    if group_id == 0:
        name = 'Senza gruppo'
        zones = con.execute('SELECT * FROM zones WHERE group_id IS NULL ORDER BY name').fetchall()
    else:
        group = con.execute('SELECT * FROM zone_groups WHERE id=?', (group_id,)).fetchone()
        if not group:
            con.close()
            raise HTTPException(404, 'Gruppo non trovato')
        name = group['name']
        zones = con.execute('SELECT * FROM zones WHERE group_id=? ORDER BY name', (group_id,)).fetchall()
    con.close()
    rows = ''.join(f'<div class="zone-row"><div><a href="quick-ticket/{z["id"]}" style="text-decoration:none" title="Apri un ticket"><b>{esc(z["name"])}</b></a><br><span class="muted">{"Attiva" if z["active"] else "Disattivata"}</span></div><div class="actions"><a class="btn" href="quick-ticket/{z["id"]}">＋ Ticket</a><a class="btn" href="zone/{z["id"]}">QR →</a></div></div>' for z in zones) or '<p class="muted">Nessuna zona in questo gruppo.</p>'
    edit = f'<a class="btn" href="{group_id}/edit">⚙ Modifica gruppo</a>' if group_id else ''
    return page(f'Gruppo · {name}', f'<div class="card"><div class="actions" style="justify-content:space-between"><div><h2>📁 {esc(name)}</h2><p class="muted">{len(zones)} zone</p></div>{edit}</div>{rows}</div>', back_url='../')


@admin_app.get('/zone-group/{group_id}/edit', response_class=HTMLResponse)
def zone_group_edit(group_id: int):
    if group_id == 0:
        return RedirectResponse('../../zone-groups', status_code=303)
    con = db()
    group = con.execute('SELECT * FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    zones = con.execute('SELECT z.*, g.name AS current_group FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id ORDER BY z.name').fetchall()
    con.close()
    if not group:
        raise HTTPException(404, 'Gruppo non trovato')
    checks = ''.join(f'<label style="display:flex;gap:10px;align-items:center;padding:10px;border-bottom:1px solid var(--line)"><input style="width:auto" type="checkbox" name="zone_ids" value="{z["id"]}" {"checked" if z["group_id"] == group_id else ""}><span><b>{esc(z["name"])}</b>' + (f'<br><small class="muted">Ora in: {esc(z["current_group"])}</small>' if z['current_group'] and z['group_id'] != group_id else '') + '</span></label>' for z in zones)
    return page(f'Modifica gruppo · {group["name"]}', f'''<div class="grid"><div class="card span-8"><h2>Zone nel gruppo</h2><form method="post" action="save"><p class="muted">Seleziona tutte le zone che vuoi mettere in <b>{esc(group['name'])}</b>. Una zona può appartenere a un solo gruppo.</p>{checks}<button>Salva assegnazione</button></form></div><div class="card span-4"><h2>Gruppo</h2><p><b>{esc(group['name'])}</b></p><form method="post" action="delete" onsubmit="return confirm('Eliminare questo gruppo? Le zone non verranno eliminate.')"><button class="danger">Elimina gruppo</button></form></div></div>''', back_url='../')


@admin_app.post('/zone-group/{group_id}/edit/save')
def zone_group_save(group_id: int, zone_ids: list[int] = Form(default=[])):
    con = db()
    group = con.execute('SELECT * FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    if not group:
        con.close()
        raise HTTPException(404, 'Gruppo non trovato')
    con.execute('UPDATE zones SET group_id=NULL WHERE group_id=?', (group_id,))
    for zone_id in zone_ids:
        con.execute('UPDATE zones SET group_id=? WHERE id=?', (group_id, int(zone_id)))
    con.commit()
    con.close()
    return RedirectResponse('../../../zone-groups?message=' + urllib.parse.quote('Assegnazione zone salvata.'), status_code=303)


@admin_app.post('/zone-group/{group_id}/edit/delete')
def zone_group_delete(group_id: int):
    con = db()
    group = con.execute('SELECT * FROM zone_groups WHERE id=?', (group_id,)).fetchone()
    if not group:
        con.close()
        raise HTTPException(404, 'Gruppo non trovato')
    con.execute('UPDATE zones SET group_id=NULL WHERE group_id=?', (group_id,))
    con.execute('DELETE FROM zone_groups WHERE id=?', (group_id,))
    con.commit()
    con.close()
    return RedirectResponse('../../../zone-groups?message=' + urllib.parse.quote('Gruppo eliminato. Le zone sono rimaste disponibili.'), status_code=303)


"""
    if route_marker not in text:
        raise SystemExit('Route insertion marker not found')
    text = text.replace(route_marker, routes + route_marker, 1)

path.write_text(text, encoding='utf-8')
