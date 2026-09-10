from pathlib import Path

path = Path('/app/app/main.py')
if not path.exists():
    path = Path(__file__).with_name('main.py')

text = path.read_text(encoding='utf-8')

# iPhone/iOS: sostituisce il selettore multiplo con 5 campi progressivi.
old = '<label>{public_text(lang, \'photos\')}</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple><button>➤ {public_text(lang, \'send\')}</button>'
new = '''<label>{public_text(lang, 'photos')}</label><div id="photo-slots"><div class="photo-slot"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif"></div></div><script>function showNextPhotoSlot(input){{if(!input.files||!input.files.length)return;const slot=input.closest('.photo-slot');const next=slot&&slot.nextElementSibling;if(next)next.style.display='block';}}</script><button>➤ {public_text(lang, 'send')}</button>'''
if old in text:
    text = text.replace(old, new, 1)
elif 'id="photo-slots"' not in text:
    raise SystemExit('Photo form pattern not found; patch not applied')

# Funzione JS per uscire dall'ingress e tornare alla Home di Home Assistant.
js_old = '<script>function adminGo(path){{'
js_new = '<script>function exitHomeAssistant(){{try{{window.top.location.href=\'/\';}}catch(e){{location.href=\'/\';}}return false;}}function adminGo(path){{'
if js_old in text and 'function exitHomeAssistant()' not in text:
    text = text.replace(js_old, js_new, 1)

# Pulsante ben visibile nella Dashboard dell'add-on.
dash_old = '''    {stock_warning_dashboard()}\n    <div class="grid">'''
dash_new = '''    <div class="actions" style="margin-bottom:14px"><a class="btn back-btn" href="/" onclick="return exitHomeAssistant()">← Home Assistant</a></div>\n    {stock_warning_dashboard()}\n    <div class="grid">'''
if dash_old in text and '← Home Assistant</a></div>\n    {stock_warning_dashboard()}' not in text:
    text = text.replace(dash_old, dash_new, 1)

# Nella Dashboard il nome della zona apre direttamente un nuovo ticket interno, senza password.
zone_dash_old = '''zone_rows = ''.join(f'<div class="zone-row"><div><b>{esc(z["name"])}</b><br><span class="muted">{"Attiva" if z["active"] else "Disattivata"}</span></div><a class="btn" href="zone/{z["id"]}">QR →</a></div>' for z in zones)'''
zone_dash_new = '''zone_rows = ''.join(f'<div class="zone-row"><div><a href="quick-ticket/{z["id"]}" title="Apri un nuovo ticket per questa zona"><b>{esc(z["name"])}</b></a><br><span class="muted">{"Attiva" if z["active"] else "Disattivata"}</span></div><a class="btn" href="zone/{z["id"]}">QR →</a></div>' for z in zones)'''
if zone_dash_old in text:
    text = text.replace(zone_dash_old, zone_dash_new, 1)

# Anche nella pagina Zone / QR il nome della zona apre direttamente il nuovo ticket.
zone_list_old = '''<td><b>{esc(z['name'])}</b></td><td>{'Attiva' if z['active'] else 'Disattivata'}</td>'''
zone_list_new = '''<td><a href="quick-ticket/{z['id']}" title="Apri un nuovo ticket per questa zona"><b>{esc(z['name'])}</b></a></td><td>{'Attiva' if z['active'] else 'Disattivata'}</td>'''
if zone_list_old in text:
    text = text.replace(zone_list_old, zone_list_new, 1)

# Route interne dell'add-on per creare ticket senza PIN. Sono protette dall'ingress di Home Assistant.
route_marker = "@admin_app.get('/tickets', response_class=HTMLResponse)"
quick_marker = "@admin_app.get('/quick-ticket/{zone_id}', response_class=HTMLResponse)"
if quick_marker not in text:
    quick_routes = r'''
@admin_app.get('/quick-ticket/{zone_id}', response_class=HTMLResponse)
def admin_quick_ticket_form(zone_id: int):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Zona non trovata')
    categories = ('Elettrico', 'Idraulico', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro')
    category_options = '<option value="">Seleziona la categoria</option>' + ''.join(f'<option value="{esc(value)}">{esc(value)}</option>' for value in categories)
    priority_options = ''.join(f'<option value="{esc(value)}">{esc(value)}</option>' for value in ('Normale', 'Bassa', 'Alta', 'Urgente'))
    inactive_notice = '<div class="notice warning"><b>Attenzione:</b> questa zona è disattivata, ma puoi comunque creare un ticket interno.</div>' if not zone['active'] else ''
    photos = ''.join(f'<label>Foto {i} (opzionale)</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif">' for i in range(1, 6))
    body = f"""{inactive_notice}<div class="card" style="max-width:760px;margin:0 auto"><h2>Nuovo ticket</h2><p><b>Zona:</b> {esc(zone['name'])}</p><p class="muted">Accesso interno Home Assistant: nessuna password richiesta.</p><form method="post" enctype="multipart/form-data" action="{zone_id}/submit"><label>Nome e cognome *</label><input name="reporter_name" maxlength="120" required placeholder="Inserisci nome e cognome"><label>Tipo di guasto *</label><select name="category" required>{category_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Descrizione *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="Descrivi il problema nel dettaglio"></textarea>{photos}<button type="submit">➤ Crea ticket</button></form></div>"""
    return page(f'Nuovo ticket · {zone["name"]}', body, back_url='../')


@admin_app.post('/quick-ticket/{zone_id}/submit')
async def admin_quick_ticket_submit(zone_id: int, reporter_name: str = Form(...), category: str = Form(...), priority: str = Form('Normale'), description: str = Form(...), photos: list[UploadFile] = File(default=[])):
    reporter_name = reporter_name.strip()
    description = description.strip()
    if not reporter_name or not description or len(reporter_name) > 120 or len(description) > 4000:
        raise HTTPException(400, 'Nome e descrizione sono obbligatori')
    allowed_categories = {'Elettrico', 'Idraulico', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro'}
    if category not in allowed_categories or priority not in PRIORITIES:
        raise HTTPException(400, 'Categoria o priorità non valida')
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    if not zone:
        con.close()
        raise HTTPException(404, 'Zona non trovata')
    description_it, status_it = translate_text(description, 'it')
    description_de, status_de = translate_text(description, 'de')
    translation_status = 'completed' if status_it == 'completed' and status_de == 'completed' else ('failed' if 'failed' in (status_it, status_de) else 'pending')
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,description_de,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description_it, description_de, translation_status, now_iso(), now_iso()))
    ticket_id = cur.lastrowid
    code = f'{datetime.now().year}-{ticket_id:05d}'
    con.execute('UPDATE tickets SET ticket_code=? WHERE id=?', (code, ticket_id))
    for upload in photos[:5]:
        if not upload.filename or upload.content_type not in ALLOWED_TYPES:
            continue
        content = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            continue
        suffix = Path(upload.filename).suffix.lower()[:8]
        stored = hashlib.sha256((secrets.token_hex(16) + upload.filename).encode()).hexdigest() + suffix
        (UPLOAD_DIR / stored).write_bytes(content)
        con.execute('INSERT INTO ticket_files(ticket_id,stored_name,original_name,content_type,created_at) VALUES(?,?,?,?,?)', (ticket_id, stored, Path(upload.filename).name, upload.content_type, now_iso()))
    con.commit()
    con.close()
    direct_url = ticket_notification_url(ticket_id)
    title = f'{"URGENTE · " if priority == "Urgente" else ""}Ticket {code}'
    message = f'Zona {zone["name"]} · {category} · Priorità {priority}\n{description[:250]}'
    notify_home_assistant(message, title, direct_url)
    return RedirectResponse(f'../../ticket/{ticket_id}', status_code=303)


'''
    if route_marker not in text:
        raise SystemExit('Quick ticket insertion marker not found; patch not applied')
    text = text.replace(route_marker, quick_routes + route_marker, 1)

path.write_text(text, encoding='utf-8')
