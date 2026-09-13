from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Needed for recurring due dates.
text = text.replace('from datetime import datetime, timezone', 'from datetime import datetime, timezone, timedelta', 1)

# Database tables.
if 'CREATE TABLE IF NOT EXISTS maintenances' not in text:
    marker = '    CREATE TABLE IF NOT EXISTS zones (\n'
    block = '''    CREATE TABLE IF NOT EXISTS maintenances (\n      id INTEGER PRIMARY KEY AUTOINCREMENT,\n      title TEXT NOT NULL,\n      maintenance_type TEXT NOT NULL,\n      zone_id INTEGER,\n      category TEXT NOT NULL DEFAULT 'Altro',\n      description TEXT NOT NULL DEFAULT '',\n      responsible TEXT NOT NULL DEFAULT '',\n      planned_date TEXT,\n      frequency_days INTEGER NOT NULL DEFAULT 0,\n      status TEXT NOT NULL DEFAULT 'Pianificata',\n      priority TEXT NOT NULL DEFAULT 'Normale',\n      estimated_cost REAL NOT NULL DEFAULT 0,\n      actual_cost REAL NOT NULL DEFAULT 0,\n      notes TEXT NOT NULL DEFAULT '',\n      last_done_at TEXT,\n      next_due_date TEXT,\n      created_at TEXT NOT NULL,\n      updated_at TEXT NOT NULL\n    );\n    CREATE TABLE IF NOT EXISTS maintenance_history (\n      id INTEGER PRIMARY KEY AUTOINCREMENT,\n      maintenance_id INTEGER NOT NULL,\n      completed_at TEXT NOT NULL,\n      notes TEXT NOT NULL DEFAULT '',\n      actual_cost REAL NOT NULL DEFAULT 0\n    );\n'''
    if marker not in text:
        raise SystemExit('Maintenance DB marker not found')
    text = text.replace(marker, block + marker, 1)

# Sidebar links: admin and manager.
manager_old = '<a class="side-link" href="/manager/materials">▦ {manager_text(lang, \'materials\')}</a>'
manager_new = manager_old + '<a class="side-link" href="/manager/maintenances">🛠 Manutenzioni</a>'
if manager_old in text and '/manager/maintenances' not in text:
    text = text.replace(manager_old, manager_new, 1)

admin_old = '<a class="side-link" href="materials" onclick="return adminGo(\'materials\')">▦ Magazzino materiali</a>'
admin_new = admin_old + '<a class="side-link" href="maintenances" onclick="return adminGo(\'maintenances\')">🛠 Manutenzioni</a>'
if admin_old in text and "adminGo('maintenances')" not in text:
    text = text.replace(admin_old, admin_new, 1)

route_marker = "@admin_app.get('/materials', response_class=HTMLResponse)"
if "@admin_app.get('/maintenances'" not in text:
    routes = r"""
MAINTENANCE_TYPES = ('Ordinaria', 'Straordinaria')
MAINTENANCE_STATUSES = ('Pianificata', 'Da fare', 'In lavorazione', 'Completata', 'Annullata')
MAINTENANCE_CATEGORIES = ('Elettrico', 'Idraulico', 'Muratore', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Pulizia', 'Sicurezza', 'Altro')


def maintenance_root(manager=False):
    return '/manager/maintenances' if manager else 'maintenances'


def maintenance_detail_root(item_id, manager=False):
    return f'/manager/maintenance/{item_id}' if manager else f'maintenance/{item_id}'


def maintenance_page(manager=False, lang='it', kind='', status='', message=''):
    query = '''SELECT m.*, z.name AS zone_name FROM maintenances m LEFT JOIN zones z ON z.id=m.zone_id WHERE 1=1'''
    params = []
    if kind in MAINTENANCE_TYPES:
        query += ' AND m.maintenance_type=?'; params.append(kind)
    if status in MAINTENANCE_STATUSES:
        query += ' AND m.status=?'; params.append(status)
    query += " ORDER BY CASE WHEN m.status IN ('Completata','Annullata') THEN 1 ELSE 0 END, COALESCE(m.next_due_date,m.planned_date,'9999-12-31'), m.id DESC"
    con = db()
    items = con.execute(query, params).fetchall()
    zones = con.execute('SELECT id,name FROM zones WHERE active=1 ORDER BY name').fetchall()
    con.close()
    today = datetime.now().date().isoformat()
    cards = ''
    for m in items:
        due = m['next_due_date'] or m['planned_date'] or ''
        overdue = bool(due and due < today and m['status'] not in ('Completata','Annullata'))
        badge = 'SCADUTA' if overdue else m['status']
        cards += f'''<a class="card" href="{maintenance_detail_root(m['id'], manager)}" style="text-decoration:none;display:block;border:{'2px solid #c62828' if overdue else '1px solid #e9ecef'}"><div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><span class="pill">{esc(m['maintenance_type'])}</span><h2 style="margin:9px 0 4px">{esc(m['title'])}</h2><span class="muted">{esc(m['zone_name'] or 'Nessuna zona')} · {esc(m['category'])}</span></div><span class="stock-badge {'low' if overdue else ''}">{esc(badge)}</span></div><p>{esc(m['description'])}</p><div class="muted"><b>Scadenza:</b> {esc(due or 'Non impostata')} · <b>Responsabile:</b> {esc(m['responsible'] or '—')}</div></a>'''
    if not cards:
        cards = '<div class="card"><p class="muted">Nessuna manutenzione presente.</p></div>'
    zone_options = '<option value="">Nessuna zona</option>' + ''.join(f'<option value="{z["id"]}">{esc(z["name"])}</option>' for z in zones)
    kind_options = ''.join(f'<option value="{k}">{k}</option>' for k in MAINTENANCE_TYPES)
    cat_options = ''.join(f'<option value="{c}">{c}</option>' for c in MAINTENANCE_CATEGORIES)
    filter_kind = '<option value="">Tutte</option>' + ''.join(f'<option value="{k}" {"selected" if kind==k else ""}>{k}</option>' for k in MAINTENANCE_TYPES)
    filter_status = '<option value="">Tutti</option>' + ''.join(f'<option value="{s}" {"selected" if status==s else ""}>{s}</option>' for s in MAINTENANCE_STATUSES)
    action = '/manager/maintenance' if manager else 'maintenance'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid"><div class="card span-12"><form class="filters" method="get"><div><label>Tipo</label><select name="kind">{filter_kind}</select></div><div><label>Stato</label><select name="status">{filter_status}</select></div><button>Filtra</button></form></div><details class="card span-12"><summary><b>＋ Nuova manutenzione</b></summary><form method="post" action="{action}" style="margin-top:16px"><div class="material-form-grid"><div><label>Titolo *</label><input name="title" maxlength="160" required placeholder="Es. Pulizia filtri climatizzatore"></div><div><label>Tipo *</label><select name="maintenance_type">{kind_options}</select></div><div><label>Zona</label><select name="zone_id">{zone_options}</select></div><div><label>Categoria</label><select name="category">{cat_options}</select></div><div><label>Data prevista</label><input type="date" name="planned_date"></div><div><label>Frequenza ordinaria</label><select name="frequency_days"><option value="0">Nessuna</option><option value="7">Settimanale</option><option value="30">Mensile</option><option value="90">Trimestrale</option><option value="180">Semestrale</option><option value="365">Annuale</option></select></div><div><label>Responsabile / ditta</label><input name="responsible" maxlength="160"></div><div><label>Costo previsto €</label><input type="number" name="estimated_cost" min="0" step="0.01" value="0"></div><div class="full"><label>Descrizione *</label><textarea name="description" maxlength="4000" required></textarea></div></div><button type="submit">Crea manutenzione</button></form></details><div class="span-12 inventory-grid">{cards}</div></div>'''
    return page('Manutenzioni', body, manager=manager, lang=lang, back_url='/manager' if manager else '')


def maintenance_detail_page(item_id, manager=False, lang='it', message=''):
    con = db()
    m = con.execute('SELECT m.*,z.name AS zone_name FROM maintenances m LEFT JOIN zones z ON z.id=m.zone_id WHERE m.id=?', (item_id,)).fetchone()
    history = con.execute('SELECT * FROM maintenance_history WHERE maintenance_id=? ORDER BY id DESC', (item_id,)).fetchall()
    zones = con.execute('SELECT id,name FROM zones ORDER BY name').fetchall()
    con.close()
    if not m: raise HTTPException(404, 'Manutenzione non trovata')
    zone_options = '<option value="">Nessuna zona</option>' + ''.join(f'<option value="{z["id"]}" {"selected" if m["zone_id"]==z["id"] else ""}>{esc(z["name"])}</option>' for z in zones)
    status_options = ''.join(f'<option value="{s}" {"selected" if m["status"]==s else ""}>{s}</option>' for s in MAINTENANCE_STATUSES)
    priority_options = ''.join(f'<option value="{p}" {"selected" if m["priority"]==p else ""}>{p}</option>' for p in PRIORITIES)
    history_html = ''.join(f'<div class="movement-row"><div><b>{esc(h["completed_at"][:10])}</b><br><span class="muted">{esc(h["notes"] or "Completata")}</span></div><span>{h["actual_cost"]:.2f} €</span></div>' for h in history) or '<p class="muted">Nessuna esecuzione registrata.</p>'
    root = f'/manager/maintenance/{item_id}' if manager else str(item_id)
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid"><div class="card span-7"><span class="pill">{esc(m['maintenance_type'])}</span><h2 style="margin-top:10px">{esc(m['title'])}</h2><p><b>Zona:</b> {esc(m['zone_name'] or 'Nessuna')}</p><p><b>Categoria:</b> {esc(m['category'])}</p><p style="white-space:pre-wrap">{esc(m['description'])}</p><p><b>Ultima esecuzione:</b> {esc((m['last_done_at'] or '—')[:10])}<br><b>Prossima scadenza:</b> {esc(m['next_due_date'] or m['planned_date'] or '—')}</p><h2>Storico</h2>{history_html}</div><div class="card span-5"><h2>Gestione</h2><form method="post" action="{root}/update"><label>Zona</label><select name="zone_id">{zone_options}</select><label>Stato</label><select name="status">{status_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Responsabile / ditta</label><input name="responsible" value="{esc(m['responsible'])}" maxlength="160"><label>Data prevista</label><input type="date" name="planned_date" value="{esc(m['planned_date'] or '')}"><label>Costo previsto €</label><input type="number" name="estimated_cost" min="0" step="0.01" value="{m['estimated_cost']}"><label>Note</label><textarea name="notes" maxlength="4000">{esc(m['notes'])}</textarea><button>Salva modifiche</button></form><h2 style="margin-top:24px">Completa intervento</h2><form method="post" action="{root}/complete"><label>Costo reale €</label><input type="number" name="actual_cost" min="0" step="0.01" value="{m['actual_cost']}"><label>Note esecuzione</label><textarea name="completion_notes" maxlength="2000"></textarea><button type="submit">✓ Segna completata</button></form><hr style="border:0;border-top:1px solid var(--line);margin:24px 0"><form method="post" action="{root}/delete" onsubmit="return confirm('Eliminare questa manutenzione e il suo storico?')"><button class="danger">Elimina manutenzione</button></form></div></div>'''
    return page(m['title'], body, manager=manager, lang=lang, back_url='/manager/maintenances' if manager else 'maintenances')


@admin_app.get('/maintenances', response_class=HTMLResponse)
def admin_maintenances(kind: str='', status: str='', message: str=''):
    return maintenance_page(False, 'it', kind, status, message)

@admin_app.post('/maintenance')
def admin_maintenance_create(title: str=Form(...), maintenance_type: str=Form(...), zone_id: str=Form(''), category: str=Form('Altro'), description: str=Form(...), responsible: str=Form(''), planned_date: str=Form(''), frequency_days: int=Form(0), estimated_cost: float=Form(0)):
    if maintenance_type not in MAINTENANCE_TYPES or category not in MAINTENANCE_CATEGORIES: raise HTTPException(400, 'Dati manutenzione non validi')
    zid = int(zone_id) if zone_id else None
    now = now_iso(); next_due = planned_date or None
    con=db(); con.execute('''INSERT INTO maintenances(title,maintenance_type,zone_id,category,description,responsible,planned_date,frequency_days,status,priority,estimated_cost,actual_cost,notes,next_due_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(title.strip(),maintenance_type,zid,category,description.strip(),responsible.strip(),planned_date or None,max(0,frequency_days),'Pianificata','Normale',max(0,estimated_cost),0,'',next_due,now,now)); con.commit(); con.close()
    return RedirectResponse('maintenances?message='+urllib.parse.quote('Manutenzione creata.'), status_code=303)

@admin_app.get('/maintenance/{item_id}', response_class=HTMLResponse)
def admin_maintenance_detail(item_id:int, message:str=''):
    return maintenance_detail_page(item_id, False, 'it', message)

@admin_app.post('/maintenance/{item_id}/update')
def admin_maintenance_update(item_id:int, zone_id:str=Form(''), status:str=Form(...), priority:str=Form('Normale'), responsible:str=Form(''), planned_date:str=Form(''), estimated_cost:float=Form(0), notes:str=Form('')):
    if status not in MAINTENANCE_STATUSES or priority not in PRIORITIES: raise HTTPException(400,'Valore non valido')
    zid=int(zone_id) if zone_id else None
    con=db(); con.execute('UPDATE maintenances SET zone_id=?,status=?,priority=?,responsible=?,planned_date=?,estimated_cost=?,notes=?,updated_at=? WHERE id=?',(zid,status,priority,responsible.strip(),planned_date or None,max(0,estimated_cost),notes.strip(),now_iso(),item_id)); con.commit(); con.close()
    return RedirectResponse(f'../{item_id}?message='+urllib.parse.quote('Manutenzione aggiornata.'), status_code=303)

@admin_app.post('/maintenance/{item_id}/complete')
def admin_maintenance_complete(item_id:int, actual_cost:float=Form(0), completion_notes:str=Form('')):
    con=db(); m=con.execute('SELECT * FROM maintenances WHERE id=?',(item_id,)).fetchone()
    if not m: con.close(); raise HTTPException(404)
    completed=datetime.now(); completed_iso=completed.replace(tzinfo=timezone.utc).isoformat(); next_due=None; new_status='Completata'
    if m['maintenance_type']=='Ordinaria' and m['frequency_days']>0:
        next_due=(completed.date()+timedelta(days=m['frequency_days'])).isoformat(); new_status='Pianificata'
    con.execute('INSERT INTO maintenance_history(maintenance_id,completed_at,notes,actual_cost) VALUES(?,?,?,?)',(item_id,completed_iso,completion_notes.strip(),max(0,actual_cost)))
    con.execute('UPDATE maintenances SET status=?,actual_cost=?,last_done_at=?,next_due_date=?,planned_date=COALESCE(?,planned_date),updated_at=? WHERE id=?',(new_status,max(0,actual_cost),completed_iso,next_due,next_due,now_iso(),item_id)); con.commit(); con.close()
    return RedirectResponse(f'../{item_id}?message='+urllib.parse.quote('Intervento registrato. Prossima scadenza aggiornata.'), status_code=303)

@admin_app.post('/maintenance/{item_id}/delete')
def admin_maintenance_delete(item_id:int):
    con=db(); con.execute('DELETE FROM maintenance_history WHERE maintenance_id=?',(item_id,)); con.execute('DELETE FROM maintenances WHERE id=?',(item_id,)); con.commit(); con.close()
    return RedirectResponse('../../maintenances?message='+urllib.parse.quote('Manutenzione eliminata.'), status_code=303)


@public_app.get('/manager/maintenances', response_class=HTMLResponse)
def manager_maintenances(request:Request, kind:str='', status:str='', message:str=''):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    return maintenance_page(True, public_language(request), kind, status, message)

@public_app.post('/manager/maintenance')
def manager_maintenance_create(request:Request, title:str=Form(...), maintenance_type:str=Form(...), zone_id:str=Form(''), category:str=Form('Altro'), description:str=Form(...), responsible:str=Form(''), planned_date:str=Form(''), frequency_days:int=Form(0), estimated_cost:float=Form(0)):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    if maintenance_type not in MAINTENANCE_TYPES or category not in MAINTENANCE_CATEGORIES: raise HTTPException(400,'Dati non validi')
    zid=int(zone_id) if zone_id else None; now=now_iso()
    con=db(); con.execute('''INSERT INTO maintenances(title,maintenance_type,zone_id,category,description,responsible,planned_date,frequency_days,status,priority,estimated_cost,actual_cost,notes,next_due_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(title.strip(),maintenance_type,zid,category,description.strip(),responsible.strip(),planned_date or None,max(0,frequency_days),'Pianificata','Normale',max(0,estimated_cost),0,'',planned_date or None,now,now)); con.commit(); con.close()
    return RedirectResponse('/manager/maintenances?message='+urllib.parse.quote('Manutenzione creata.'), status_code=303)

@public_app.get('/manager/maintenance/{item_id}', response_class=HTMLResponse)
def manager_maintenance_detail(request:Request,item_id:int,message:str=''):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    return maintenance_detail_page(item_id, True, public_language(request), message)

@public_app.post('/manager/maintenance/{item_id}/update')
def manager_maintenance_update(request:Request,item_id:int,zone_id:str=Form(''),status:str=Form(...),priority:str=Form('Normale'),responsible:str=Form(''),planned_date:str=Form(''),estimated_cost:float=Form(0),notes:str=Form('')):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    if status not in MAINTENANCE_STATUSES or priority not in PRIORITIES: raise HTTPException(400,'Valore non valido')
    zid=int(zone_id) if zone_id else None; con=db(); con.execute('UPDATE maintenances SET zone_id=?,status=?,priority=?,responsible=?,planned_date=?,estimated_cost=?,notes=?,updated_at=? WHERE id=?',(zid,status,priority,responsible.strip(),planned_date or None,max(0,estimated_cost),notes.strip(),now_iso(),item_id)); con.commit(); con.close()
    return RedirectResponse(f'/manager/maintenance/{item_id}?message='+urllib.parse.quote('Manutenzione aggiornata.'), status_code=303)

@public_app.post('/manager/maintenance/{item_id}/complete')
def manager_maintenance_complete(request:Request,item_id:int,actual_cost:float=Form(0),completion_notes:str=Form('')):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    con=db(); m=con.execute('SELECT * FROM maintenances WHERE id=?',(item_id,)).fetchone()
    if not m: con.close(); raise HTTPException(404)
    completed=datetime.now(); completed_iso=completed.replace(tzinfo=timezone.utc).isoformat(); next_due=None; new_status='Completata'
    if m['maintenance_type']=='Ordinaria' and m['frequency_days']>0: next_due=(completed.date()+timedelta(days=m['frequency_days'])).isoformat(); new_status='Pianificata'
    con.execute('INSERT INTO maintenance_history(maintenance_id,completed_at,notes,actual_cost) VALUES(?,?,?,?)',(item_id,completed_iso,completion_notes.strip(),max(0,actual_cost))); con.execute('UPDATE maintenances SET status=?,actual_cost=?,last_done_at=?,next_due_date=?,planned_date=COALESCE(?,planned_date),updated_at=? WHERE id=?',(new_status,max(0,actual_cost),completed_iso,next_due,next_due,now_iso(),item_id)); con.commit(); con.close()
    return RedirectResponse(f'/manager/maintenance/{item_id}?message='+urllib.parse.quote('Intervento registrato.'), status_code=303)

@public_app.post('/manager/maintenance/{item_id}/delete')
def manager_maintenance_delete(request:Request,item_id:int):
    if not manager_session_valid(request): return RedirectResponse('/manager/login', status_code=303)
    con=db(); con.execute('DELETE FROM maintenance_history WHERE maintenance_id=?',(item_id,)); con.execute('DELETE FROM maintenances WHERE id=?',(item_id,)); con.commit(); con.close()
    return RedirectResponse('/manager/maintenances?message='+urllib.parse.quote('Manutenzione eliminata.'), status_code=303)


"""
    if route_marker not in text:
        raise SystemExit('Maintenance route marker not found')
    text = text.replace(route_marker, routes + route_marker, 1)

path.write_text(text, encoding='utf-8')
