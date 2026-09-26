from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# WhatsApp collaboration:
# - edit technician name/number/tasks
# - allow multiple tasks per contact (stored comma-separated in existing category column)
# - unique signed ticket link per technician
# - technician comments + "material needed" response from the shared ticket page

# 1) Ensure collaboration table exists at runtime.
init_marker = "init_db()\nadmin_app = FastAPI(title='Hausmeister Carellas Admin')"
if init_marker in text and "whatsapp_ticket_comments" not in text:
    schema = """init_db()

def ensure_whatsapp_collaboration_schema():
    con = db()
    con.execute('''CREATE TABLE IF NOT EXISTS whatsapp_ticket_comments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id INTEGER NOT NULL,
      contact_id INTEGER,
      comment TEXT,
      needs_material INTEGER NOT NULL DEFAULT 0,
      material_note TEXT,
      created_at TEXT NOT NULL
    )''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_whatsapp_comments_ticket ON whatsapp_ticket_comments(ticket_id)')
    con.commit()
    con.close()

ensure_whatsapp_collaboration_schema()
admin_app = FastAPI(title='Hausmeister Carellas Admin')"""
    text = text.replace(init_marker, schema, 1)

# 2) Multiple tasks/categories per technician when suggesting contacts.
old_contacts_query = """    whatsapp_contacts = con.execute("SELECT * FROM whatsapp_contacts WHERE active=1 AND (category=? OR category='Tutte') ORDER BY name", (t['category'],)).fetchall()
    if not whatsapp_contacts:
        whatsapp_contacts = con.execute('SELECT * FROM whatsapp_contacts WHERE active=1 ORDER BY name').fetchall()
    whatsapp_history = con.execute('SELECT s.sent_at,c.name FROM whatsapp_shares s JOIN whatsapp_contacts c ON c.id=s.contact_id WHERE s.ticket_id=? ORDER BY s.id DESC LIMIT 5', (ticket_id,)).fetchall()
    con.close()"""
new_contacts_query = """    all_whatsapp_contacts = con.execute('SELECT * FROM whatsapp_contacts WHERE active=1 ORDER BY name').fetchall()
    whatsapp_contacts = [
        c for c in all_whatsapp_contacts
        if c['category'] == 'Tutte' or t['category'] in [part.strip() for part in (c['category'] or '').split(',') if part.strip()]
    ]
    if not whatsapp_contacts:
        whatsapp_contacts = all_whatsapp_contacts
    whatsapp_history = con.execute('SELECT s.sent_at,c.name FROM whatsapp_shares s JOIN whatsapp_contacts c ON c.id=s.contact_id WHERE s.ticket_id=? ORDER BY s.id DESC LIMIT 5', (ticket_id,)).fetchall()
    whatsapp_comments = con.execute('SELECT wc.*,c.name contact_name FROM whatsapp_ticket_comments wc LEFT JOIN whatsapp_contacts c ON c.id=wc.contact_id WHERE wc.ticket_id=? ORDER BY wc.id DESC', (ticket_id,)).fetchall()
    con.close()"""
if old_contacts_query in text:
    text = text.replace(old_contacts_query, new_contacts_query, 1)

# 3) Replace WhatsApp button block (created by patch_whatsapp_direct) with per-contact signed links.
start = text.find("    contact_buttons = ''\n    wa_base = whatsapp_public_base_url()")
end = text.find("    history_rows = ''.join(", start)
if start >= 0 and end >= 0:
    new_buttons = r'''    contact_buttons = ''
    wa_base = whatsapp_public_base_url()
    if whatsapp_contacts and wa_base:
        description_it = t["description_it"] or t["description_original"]
        description_de = t["description_de"] or t["description_original"]
        description_ro, _description_ro_status = translate_text(t["description_original"], 'ro')
        description_ro = description_ro or t["description_original"]
        category_de = {'Elettrico':'Elektrik','Idraulico':'Sanitär / Wasser','Muratore':'Maurer / Bau','Climatizzazione':'Klimaanlage','Porta/Finestra':'Tür / Fenster','Attrezzatura cucina':'Küchengerät','Altro':'Sonstiges'}.get(t["category"], t["category"])
        category_ro = {'Elettrico':'Electric','Idraulico':'Instalații sanitare / Apă','Muratore':'Zidar / Construcții','Climatizzazione':'Climatizare','Porta/Finestra':'Ușă / Fereastră','Attrezzatura cucina':'Echipament bucătărie','Altro':'Altele'}.get(t["category"], t["category"])
        priority_it = t["priority"] or 'Normale'
        priority_de = {'Bassa':'Niedrig','Normale':'Normal','Alta':'Hoch','Urgente':'Dringend'}.get(priority_it, priority_it)
        priority_ro = {'Bassa':'Scăzută','Normale':'Normală','Alta':'Ridicată','Urgente':'Urgentă'}.get(priority_it, priority_it)
        for c in whatsapp_contacts:
            wa_token = whatsapp_ticket_token(ticket_id, c["id"])
            ticket_link = f'{wa_base}/w/{urllib.parse.quote(wa_token, safe="")}'
            wa_messages = {
                'it': f'🔧 Nuovo intervento Hausmeister Carellas\nTicket: {t["ticket_code"]}\nZona: {t["zone_name"]}\nCategoria: {t["category"]}\nPriorità: {priority_it}\nProblema: {description_it[:700]}\n\n📋 Apri ticket, foto e rispondi: {ticket_link}',
                'de': f'🔧 Neuer Einsatz Hausmeister Carellas\nTicket: {t["ticket_code"]}\nBereich: {t["zone_name"]}\nKategorie: {category_de}\nPriorität: {priority_de}\nProblem: {description_de[:700]}\n\n📋 Ticket, Fotos öffnen und antworten: {ticket_link}',
                'ro': f'🔧 Intervenție nouă Hausmeister Carellas\nTichet: {t["ticket_code"]}\nZonă: {t["zone_name"]}\nCategorie: {category_ro}\nPrioritate: {priority_ro}\nProblemă: {description_ro[:700]}\n\n📋 Deschide tichetul, fotografiile și răspunde: {ticket_link}'
            }
            wa_it = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["it"])}'
            wa_de = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["de"])}'
            wa_ro = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["ro"])}'
            contact_buttons += f'<a class="btn wa-auto-language" style="background:#16883f;margin:5px 5px 5px 0" href="{esc(wa_it)}" data-wa-it="{esc(wa_it)}" data-wa-de="{esc(wa_de)}" data-wa-ro="{esc(wa_ro)}" target="_top">WhatsApp · {esc(c["name"])}</a>'
        contact_buttons += '<script>document.querySelectorAll(".wa-auto-language").forEach(function(a){a.addEventListener("click",function(){var l=(navigator.language||navigator.userLanguage||"it").toLowerCase();if(l.indexOf("de")===0)a.href=a.dataset.waDe;else if(l.indexOf("ro")===0)a.href=a.dataset.waRo;else a.href=a.dataset.waIt;});});</script>'
    elif whatsapp_contacts:
        contact_buttons = '<div class="notice warning">Configura URL pubblico o tunnel pubblico per inserire nel messaggio il link al ticket.</div>'
    else:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
'''
    text = text[:start] + new_buttons + text[end:]

# 4) Show technician comments/material requests inside the admin ticket.
panel_line = """    whatsapp_panel = f'<h2 style="margin-top:22px">🟢 Invia a tecnico</h2><p class="muted">Tecnici suggeriti per: <b>{esc(t["category"])}</b></p><div class="actions">{contact_buttons}</div>{history_rows}'"""
if panel_line in text:
    panel_new = panel_line + """
    comment_rows = ''.join(
        f'<div class="notice {"warning" if row["needs_material"] else ""}" style="margin-top:10px"><b>{esc(row["contact_name"] or "Tecnico")}</b> · {esc(row["created_at"][:16].replace("T"," "))}<br>{esc(row["comment"] or "")}{("<br><b>⚠ Materiale necessario:</b> " + esc(row["material_note"] or "Da definire")) if row["needs_material"] else ""}</div>'
        for row in whatsapp_comments
    )
    if comment_rows:
        whatsapp_panel += f'<h2 style="margin-top:22px">💬 Risposte tecnici</h2>{comment_rows}'"""
    text = text.replace(panel_line, panel_new, 1)

# 5) Signed token also carries the technician id, while old links remain valid.
old_token = """def whatsapp_ticket_token(ticket_id: int):
    return serializer().dumps({'ticket': int(ticket_id), 'purpose': 'whatsapp'})

def whatsapp_ticket_id(signed_token: str):
    try:
        data = serializer().loads(signed_token, max_age=30 * 86400)
        if data.get('purpose') != 'whatsapp':
            raise BadSignature('Invalid purpose')
        return int(data['ticket'])
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(403, 'Collegamento WhatsApp non valido o scaduto')
"""
new_token = """def whatsapp_ticket_token(ticket_id: int, contact_id: int = 0):
    payload = {'ticket': int(ticket_id), 'purpose': 'whatsapp'}
    if contact_id:
        payload['contact'] = int(contact_id)
    return serializer().dumps(payload)

def whatsapp_ticket_payload(signed_token: str):
    try:
        data = serializer().loads(signed_token, max_age=30 * 86400)
        if data.get('purpose') != 'whatsapp':
            raise BadSignature('Invalid purpose')
        data['ticket'] = int(data['ticket'])
        data['contact'] = int(data.get('contact') or 0)
        return data
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(403, 'Collegamento WhatsApp non valido o scaduto')

def whatsapp_ticket_id(signed_token: str):
    return whatsapp_ticket_payload(signed_token)['ticket']
"""
if old_token in text:
    text = text.replace(old_token, new_token, 1)

# 6) Replace WhatsApp settings page with editable contacts + multiple tasks.
settings_start = text.find("@admin_app.get('/settings/whatsapp', response_class=HTMLResponse)")
settings_end = text.find("@admin_app.post('/settings/whatsapp/create')", settings_start)
if settings_start >= 0 and settings_end >= 0:
    settings_func = r'''@admin_app.get('/settings/whatsapp', response_class=HTMLResponse)
def whatsapp_settings(message: str = ''):
    con = db()
    contacts = con.execute('SELECT * FROM whatsapp_contacts ORDER BY name').fetchall()
    con.close()
    rows = ''
    for contact in contacts:
        status = 'Attivo' if contact['active'] else 'Disattivato'
        toggle_label = 'Disattiva' if contact['active'] else 'Attiva'
        selected = {part.strip() for part in (contact['category'] or '').split(',') if part.strip()}
        category_checks = ''.join(
            f'<label style="display:flex;align-items:center;gap:7px;margin:6px 10px 6px 0"><input type="checkbox" name="categories" value="{esc(cat)}" {"checked" if cat in selected else ""} style="width:auto;margin:0">{esc(cat)}</label>'
            for cat in WHATSAPP_CATEGORIES
        )
        rows += f'''<div class="zone-row" style="align-items:flex-start">
          <div style="flex:1"><b>{esc(contact["name"])}</b><br><span class="muted">{esc(contact["category"])} · +{esc(contact["phone"])} · {status}</span>
          <details style="margin-top:10px"><summary><b>✎ Modifica contatto / mansioni</b></summary>
            <form method="post" action="whatsapp/{contact["id"]}/update" style="margin-top:12px">
              <label>Nome / Ditta</label><input name="name" value="{esc(contact["name"])}" maxlength="100" required>
              <label>Numero WhatsApp</label><input name="phone" value="+{esc(contact["phone"])}" maxlength="30" required>
              <label>Mansioni</label><div style="display:flex;flex-wrap:wrap">{category_checks}</div>
              <button type="submit">Salva modifiche</button>
            </form>
          </details></div>
          <div class="actions"><form method="post" action="whatsapp/{contact["id"]}/toggle"><button type="submit">{toggle_label}</button></form>
          <form method="post" action="whatsapp/{contact["id"]}/delete" onsubmit="return confirm('Eliminare questo contatto?')"><button type="submit" class="danger">Elimina</button></form></div>
        </div>'''
    if not rows:
        rows = '<p class="muted">Nessun tecnico configurato.</p>'
    category_checks_new = ''.join(
        f'<label style="display:flex;align-items:center;gap:7px;margin:6px 10px 6px 0"><input type="checkbox" name="categories" value="{esc(cat)}" {"checked" if cat == "Tutte" else ""} style="width:auto;margin:0">{esc(cat)}</label>'
        for cat in WHATSAPP_CATEGORIES
    )
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''<div class="grid"><div class="card span-7"><h2>Contatti WhatsApp</h2>{notice}{rows}</div>
    <div class="card span-5"><h2>Aggiungi tecnico</h2><form method="post" action="whatsapp/create">
    <label>Nome / Ditta</label><input name="name" maxlength="100" required placeholder="Es. Mario Rossi">
    <label>Numero WhatsApp</label><input name="phone" maxlength="30" required placeholder="Es. +49 170 1234567">
    <p class="muted">Usa il prefisso internazionale (+49, +39, ecc.).</p>
    <label>Mansioni</label><div style="display:flex;flex-wrap:wrap">{category_checks_new}</div>
    <button type="submit">Aggiungi contatto</button></form>
    <div class="notice" style="margin-top:18px"><b>Risposte ai ticket:</b> il tecnico può aprire il link ricevuto su WhatsApp, commentare il ticket e indicare se serve materiale.</div>
    </div></div>'''
    return page('WhatsApp tecnici', body, back_url='../settings')


'''
    text = text[:settings_start] + settings_func + text[settings_end:]

# 7) Create/update routes with multiple tasks.
create_start = text.find("@admin_app.post('/settings/whatsapp/create')")
create_end = text.find("@admin_app.post('/settings/whatsapp/{contact_id}/toggle')", create_start)
if create_start >= 0 and create_end >= 0:
    create_routes = r'''def normalize_whatsapp_categories(categories):
    valid = [cat for cat in categories if cat in WHATSAPP_CATEGORIES]
    if not valid:
        valid = ['Tutte']
    if 'Tutte' in valid:
        return 'Tutte'
    return ', '.join(dict.fromkeys(valid))

@admin_app.post('/settings/whatsapp/create')
def whatsapp_contact_create(name: str = Form(...), phone: str = Form(...), categories: list[str] = Form(default=[])):
    name = name.strip()
    if not name or len(name) > 100:
        raise HTTPException(400, 'Nome contatto non valido')
    phone = normalize_whatsapp_phone(phone)
    category = normalize_whatsapp_categories(categories)
    con = db()
    con.execute('INSERT INTO whatsapp_contacts(name,phone,category,active,created_at) VALUES(?,?,?,?,?)', (name, phone, category, 1, now_iso()))
    con.commit()
    con.close()
    return RedirectResponse('../whatsapp?message=' + urllib.parse.quote('Contatto WhatsApp aggiunto.'), status_code=303)

@admin_app.post('/settings/whatsapp/{contact_id}/update')
def whatsapp_contact_update(contact_id: int, name: str = Form(...), phone: str = Form(...), categories: list[str] = Form(default=[])):
    name = name.strip()
    if not name or len(name) > 100:
        raise HTTPException(400, 'Nome contatto non valido')
    phone = normalize_whatsapp_phone(phone)
    category = normalize_whatsapp_categories(categories)
    con = db()
    exists = con.execute('SELECT id FROM whatsapp_contacts WHERE id=?', (contact_id,)).fetchone()
    if not exists:
        con.close()
        raise HTTPException(404, 'Contatto non trovato')
    con.execute('UPDATE whatsapp_contacts SET name=?,phone=?,category=? WHERE id=?', (name, phone, category, contact_id))
    con.commit()
    con.close()
    return RedirectResponse('../../whatsapp?message=' + urllib.parse.quote('Contatto aggiornato.'), status_code=303)

'''
    text = text[:create_start] + create_routes + text[create_end:]

# 8) Public WhatsApp ticket: technician identity, comments and material request.
public_start = text.find("@public_app.get('/w/{signed_token}', response_class=HTMLResponse)")
public_end = text.find("@public_app.get('/w/{signed_token}/file/{file_id}')", public_start)
if public_start >= 0 and public_end >= 0:
    public_ticket = r'''@public_app.get('/w/{signed_token}', response_class=HTMLResponse)
def whatsapp_public_ticket(request: Request, signed_token: str, sent: int = 0):
    payload = whatsapp_ticket_payload(signed_token)
    ticket_id = payload['ticket']
    contact_id = payload.get('contact') or 0
    con = db()
    ticket = con.execute('SELECT t.*,z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=? ORDER BY id', (ticket_id,)).fetchall()
    contact = con.execute('SELECT * FROM whatsapp_contacts WHERE id=?', (contact_id,)).fetchone() if contact_id else None
    comments = con.execute('SELECT wc.*,c.name contact_name FROM whatsapp_ticket_comments wc LEFT JOIN whatsapp_contacts c ON c.id=wc.contact_id WHERE wc.ticket_id=? ORDER BY wc.id DESC', (ticket_id,)).fetchall()
    con.close()
    if not ticket:
        raise HTTPException(404, 'Ticket non trovato')
    base = whatsapp_public_base_url()
    token_q = urllib.parse.quote(signed_token, safe='')
    photos = ''.join(
        f'<a href="{esc(base)}/w/{esc(token_q)}/file/{f["id"]}" target="_blank"><img src="{esc(base)}/w/{esc(token_q)}/file/{f["id"]}" alt="Foto ticket" loading="eager"></a>'
        for f in files
    ) or '<p class="muted">Nessuna foto allegata.</p>'
    comments_html = ''.join(
        f'<div class="notice {"warning" if row["needs_material"] else ""}" style="margin-top:10px"><b>{esc(row["contact_name"] or "Tecnico")}</b> · {esc(row["created_at"][:16].replace("T"," "))}<br>{esc(row["comment"] or "")}{("<br><b>⚠ Materiale necessario:</b> " + esc(row["material_note"] or "Da definire")) if row["needs_material"] else ""}</div>'
        for row in comments
    ) or '<p class="muted">Nessuna risposta ancora.</p>'
    sent_notice = '<div class="notice">✓ Risposta salvata nel ticket.</div>' if sent else ''
    reply = ''
    if contact:
        reply = f'''<div class="public-card" style="margin-top:16px"><h2>Rispondi al ticket</h2>
        <p class="muted">Tecnico: <b>{esc(contact["name"])}</b></p>{sent_notice}
        <form method="post" action="/w/{esc(token_q)}/comment">
          <label>Commento / aggiornamento</label><textarea name="comment" maxlength="2000" rows="4" placeholder="Scrivi cosa hai verificato o cosa devi fare"></textarea>
          <label style="display:flex;align-items:center;gap:8px"><input type="checkbox" name="needs_material" value="1" style="width:auto;margin:0"> Serve materiale</label>
          <label>Materiale necessario</label><textarea name="material_note" maxlength="1000" rows="3" placeholder="Es. sifone 1 1/2, guarnizione, 2 raccordi..."></textarea>
          <button type="submit">💬 Salva risposta</button>
        </form></div>'''
    body = f'''<div class="public-card"><h1>Intervento {esc(ticket["ticket_code"])}</h1>
    <p><b>Zona:</b> {esc(ticket["zone_name"])}</p><p><b>Categoria:</b> {esc(ticket["category"])}</p>
    <p><b>Priorità:</b> {esc(ticket["priority"] or "Normale")}</p><p><b>Stato:</b> {esc(ticket["status"])}</p>
    <h2>Problema</h2><p style="white-space:pre-wrap">{esc(ticket["description_original"])}</p>
    <h2>Foto</h2><div class="photos">{photos}</div>
    <h2 style="margin-top:22px">Risposte tecnici</h2>{comments_html}</div>{reply}'''
    return page(f'Intervento {ticket["ticket_code"]}', body, public=True, lang='it', close_on_back=True)

@public_app.post('/w/{signed_token}/comment')
def whatsapp_public_comment(signed_token: str, comment: str = Form(''), needs_material: str = Form(''), material_note: str = Form('')):
    payload = whatsapp_ticket_payload(signed_token)
    ticket_id = payload['ticket']
    contact_id = payload.get('contact') or 0
    if not contact_id:
        raise HTTPException(403, 'Questo link non identifica il tecnico')
    comment = comment.strip()
    material_note = material_note.strip()
    needs = 1 if needs_material == '1' else 0
    if not comment and not (needs and material_note):
        raise HTTPException(400, 'Inserisci un commento oppure il materiale necessario')
    con = db()
    ticket = con.execute('SELECT id FROM tickets WHERE id=?', (ticket_id,)).fetchone()
    contact = con.execute('SELECT id FROM whatsapp_contacts WHERE id=?', (contact_id,)).fetchone()
    if not ticket or not contact:
        con.close()
        raise HTTPException(404)
    con.execute('INSERT INTO whatsapp_ticket_comments(ticket_id,contact_id,comment,needs_material,material_note,created_at) VALUES(?,?,?,?,?,?)',
                (ticket_id, contact_id, comment, needs, material_note, now_iso()))
    con.commit()
    con.close()
    return RedirectResponse(f'/w/{urllib.parse.quote(signed_token, safe="")}?sent=1', status_code=303)


'''
    text = text[:public_start] + public_ticket + text[public_end:]

path.write_text(text, encoding='utf-8')
