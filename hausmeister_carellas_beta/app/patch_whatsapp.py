from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Database tables for WhatsApp contacts and send history.
if 'CREATE TABLE IF NOT EXISTS whatsapp_contacts' not in text:
    marker = '    CREATE TABLE IF NOT EXISTS zones (\n'
    block = '''    CREATE TABLE IF NOT EXISTS whatsapp_contacts (\n      id INTEGER PRIMARY KEY AUTOINCREMENT,\n      name TEXT NOT NULL,\n      phone TEXT NOT NULL,\n      category TEXT NOT NULL DEFAULT 'Tutte',\n      active INTEGER NOT NULL DEFAULT 1,\n      created_at TEXT NOT NULL\n    );\n    CREATE TABLE IF NOT EXISTS whatsapp_shares (\n      id INTEGER PRIMARY KEY AUTOINCREMENT,\n      ticket_id INTEGER NOT NULL,\n      contact_id INTEGER NOT NULL,\n      sent_at TEXT NOT NULL\n    );\n'''
    if marker not in text:
        raise SystemExit('WhatsApp DB marker not found')
    text = text.replace(marker, block + marker, 1)

# Add Muratore as a ticket category.
text = text.replace(
    "(('Elettrico', 'Elektrik'), ('Idraulico', 'Sanitär / Wasser'), ('Climatizzazione', 'Klimaanlage'), ('Porta/Finestra', 'Tür / Fenster'), ('Attrezzatura cucina', 'Küchengerät'), ('Altro', 'Sonstiges'))",
    "(('Elettrico', 'Elektrik'), ('Idraulico', 'Sanitär / Wasser'), ('Muratore', 'Maurer / Bau'), ('Climatizzazione', 'Klimaanlage'), ('Porta/Finestra', 'Tür / Fenster'), ('Attrezzatura cucina', 'Küchengerät'), ('Altro', 'Sonstiges'))",
)
text = text.replace(
    "(('Elettrico', 'Elettrico'), ('Idraulico', 'Idraulico'), ('Climatizzazione', 'Climatizzazione'), ('Porta/Finestra', 'Porta / Finestra'), ('Attrezzatura cucina', 'Attrezzatura cucina'), ('Altro', 'Altro'))",
    "(('Elettrico', 'Elettrico'), ('Idraulico', 'Idraulico'), ('Muratore', 'Muratore'), ('Climatizzazione', 'Climatizzazione'), ('Porta/Finestra', 'Porta / Finestra'), ('Attrezzatura cucina', 'Attrezzatura cucina'), ('Altro', 'Altro'))",
)
text = text.replace(
    "{'Elettrico', 'Idraulico', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro'}",
    "{'Elettrico', 'Idraulico', 'Muratore', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro'}",
)

# Settings entry.
backup_card = '<div class="card span-12"><h2>Backup</h2><p>Scarica database e fotografie in un unico archivio ZIP.</p><a class="btn" href="settings/backup">Scarica backup</a></div>'
whatsapp_card = '<div class="card span-12"><h2>WhatsApp tecnici</h2><p>Configura idraulici, muratori e altri tecnici da associare automaticamente ai ticket.</p><a class="btn" href="settings/whatsapp">🟢 Gestisci contatti WhatsApp</a></div>' + backup_card
if backup_card in text and 'settings/whatsapp' not in text:
    text = text.replace(backup_card, whatsapp_card, 1)

# Ticket detail: load contacts and share history.
old = "    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=?', (ticket_id,)).fetchall()\n    con.close()"
new = "    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=?', (ticket_id,)).fetchall()\n    whatsapp_contacts = con.execute(\"SELECT * FROM whatsapp_contacts WHERE active=1 AND (category=? OR category='Tutte') ORDER BY name\", (t['category'],)).fetchall()\n    if not whatsapp_contacts:\n        whatsapp_contacts = con.execute('SELECT * FROM whatsapp_contacts WHERE active=1 ORDER BY name').fetchall()\n    whatsapp_history = con.execute('SELECT s.sent_at,c.name FROM whatsapp_shares s JOIN whatsapp_contacts c ON c.id=s.contact_id WHERE s.ticket_id=? ORDER BY s.id DESC LIMIT 5', (ticket_id,)).fetchall()\n    con.close()"
if old in text:
    text = text.replace(old, new, 1)
elif 'whatsapp_history = con.execute' not in text:
    raise SystemExit('Ticket WhatsApp query marker not found')

marker = "    delete_form = ''\n"
if 'whatsapp_panel =' not in text:
    addition = '''    contact_buttons = ''.join(
        f'<a class="btn" style="background:#16883f;margin:5px 5px 5px 0" href="{ticket_id}/whatsapp/{c["id"]}" target="_blank">WhatsApp · {esc(c["name"])}</a>'
        for c in whatsapp_contacts
    )
    if not contact_buttons:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
    history_rows = ''.join(
        f'<div class="muted" style="margin-top:5px">Inviato a <b>{esc(h["name"])}</b> · {esc(h["sent_at"][:16].replace("T", " "))}</div>'
        for h in whatsapp_history
    )
    whatsapp_panel = f'<h2 style="margin-top:22px">🟢 Invia a tecnico</h2><p class="muted">Tecnici suggeriti per: <b>{esc(t["category"])}</b></p><div class="actions">{contact_buttons}</div>{history_rows}'
'''
    if marker not in text:
        raise SystemExit('Ticket WhatsApp panel marker not found')
    text = text.replace(marker, addition + marker, 1)

old = '<button>Salva modifiche</button></form><h2 style="margin-top:22px">Foto</h2>'
new = '<button>Salva modifiche</button></form>{whatsapp_panel}<h2 style="margin-top:22px">Foto</h2>'
if old in text:
    text = text.replace(old, new, 1)
elif '{whatsapp_panel}' not in text:
    raise SystemExit('Ticket WhatsApp UI marker not found')

# Admin routes.
route_marker = "@admin_app.get('/materials', response_class=HTMLResponse)"
if "@admin_app.get('/settings/whatsapp'" not in text:
    routes = r'''
WHATSAPP_CATEGORIES = ('Tutte', 'Elettrico', 'Idraulico', 'Muratore', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro')


def normalize_whatsapp_phone(phone: str):
    value = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if value.startswith('00'):
        value = value[2:]
    if len(value) < 8 or len(value) > 16:
        raise HTTPException(400, 'Numero WhatsApp non valido. Inserisci il prefisso internazionale, es. 491701234567.')
    return value


def whatsapp_ticket_token(ticket_id: int):
    return serializer().dumps({'ticket': int(ticket_id), 'purpose': 'whatsapp'})


def whatsapp_ticket_id(signed_token: str):
    try:
        data = serializer().loads(signed_token, max_age=30 * 86400)
        if data.get('purpose') != 'whatsapp':
            raise BadSignature('Invalid purpose')
        return int(data['ticket'])
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(403, 'Collegamento WhatsApp non valido o scaduto')


@admin_app.get('/settings/whatsapp', response_class=HTMLResponse)
def whatsapp_settings(message: str = ''):
    con = db()
    contacts = con.execute('SELECT * FROM whatsapp_contacts ORDER BY category,name').fetchall()
    con.close()
    rows = ''
    for contact in contacts:
        status = 'Attivo' if contact['active'] else 'Disattivato'
        toggle_label = 'Disattiva' if contact['active'] else 'Attiva'
        rows += f'<div class="zone-row"><div><b>{esc(contact["name"])}</b><br><span class="muted">{esc(contact["category"])} · +{esc(contact["phone"])} · {status}</span></div><div class="actions"><form method="post" action="whatsapp/{contact["id"]}/toggle"><button type="submit">{toggle_label}</button></form><form method="post" action="whatsapp/{contact["id"]}/delete" onsubmit="return confirm(\'Eliminare questo contatto?\')"><button type="submit" class="danger">Elimina</button></form></div></div>'
    if not rows:
        rows = '<p class="muted">Nessun tecnico configurato.</p>'
    options = ''.join(f'<option value="{esc(cat)}">{esc(cat)}</option>' for cat in WHATSAPP_CATEGORIES)
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'<div class="grid"><div class="card span-7"><h2>Contatti WhatsApp</h2>{notice}{rows}</div><div class="card span-5"><h2>Aggiungi tecnico</h2><form method="post" action="whatsapp/create"><label>Nome / Ditta</label><input name="name" maxlength="100" required placeholder="Es. Mario Rossi"><label>Numero WhatsApp</label><input name="phone" maxlength="30" required placeholder="Es. +49 170 1234567"><p class="muted">Usa il prefisso internazionale (+49, +39, ecc.).</p><label>Categoria</label><select name="category">{options}</select><button type="submit">Aggiungi contatto</button></form></div></div>'
    return page('WhatsApp tecnici', body, back_url='../settings')


@admin_app.post('/settings/whatsapp/create')
def whatsapp_contact_create(name: str = Form(...), phone: str = Form(...), category: str = Form('Tutte')):
    name = name.strip()
    if not name or len(name) > 100:
        raise HTTPException(400, 'Nome contatto non valido')
    if category not in WHATSAPP_CATEGORIES:
        raise HTTPException(400, 'Categoria non valida')
    phone = normalize_whatsapp_phone(phone)
    con = db()
    con.execute('INSERT INTO whatsapp_contacts(name,phone,category,active,created_at) VALUES(?,?,?,?,?)', (name, phone, category, 1, now_iso()))
    con.commit()
    con.close()
    return RedirectResponse('../whatsapp?message=' + urllib.parse.quote('Contatto WhatsApp aggiunto.'), status_code=303)


@admin_app.post('/settings/whatsapp/{contact_id}/toggle')
def whatsapp_contact_toggle(contact_id: int):
    con = db()
    con.execute('UPDATE whatsapp_contacts SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (contact_id,))
    con.commit()
    con.close()
    return RedirectResponse('../../whatsapp', status_code=303)


@admin_app.post('/settings/whatsapp/{contact_id}/delete')
def whatsapp_contact_delete(contact_id: int):
    con = db()
    con.execute('DELETE FROM whatsapp_shares WHERE contact_id=?', (contact_id,))
    con.execute('DELETE FROM whatsapp_contacts WHERE id=?', (contact_id,))
    con.commit()
    con.close()
    return RedirectResponse('../../whatsapp', status_code=303)


@admin_app.get('/ticket/{ticket_id}/whatsapp/{contact_id}')
def whatsapp_share_ticket(ticket_id: int, contact_id: int):
    con = db()
    ticket = con.execute('SELECT t.*,z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    contact = con.execute('SELECT * FROM whatsapp_contacts WHERE id=? AND active=1', (contact_id,)).fetchone()
    if not ticket or not contact:
        con.close()
        raise HTTPException(404, 'Ticket o contatto non trovato')
    base = public_base_url().rstrip('/')
    if not base:
        con.close()
        raise HTTPException(409, 'Configura prima URL pubblico nelle impostazioni dell’add-on.')
    token = whatsapp_ticket_token(ticket_id)
    link = f'{base}/w/{urllib.parse.quote(token, safe="")}'
    message = (
        f'🔧 Nuovo intervento Hausmeister Carellas\n'
        f'Ticket: {ticket["ticket_code"]}\n'
        f'Zona: {ticket["zone_name"]}\n'
        f'Categoria: {ticket["category"]}\n'
        f'Priorità: {ticket["priority"] or "Normale"}\n'
        f'Problema: {ticket["description_original"][:700]}\n\n'
        f'📋 Ticket completo e foto: {link}'
    )
    con.execute('INSERT INTO whatsapp_shares(ticket_id,contact_id,sent_at) VALUES(?,?,?)', (ticket_id, contact_id, now_iso()))
    con.commit()
    con.close()
    url = f'https://wa.me/{contact["phone"]}?text={urllib.parse.quote(message)}'
    return RedirectResponse(url, status_code=303)


'''
    if route_marker not in text:
        raise SystemExit('WhatsApp route marker not found')
    text = text.replace(route_marker, routes + route_marker, 1)

# Public technician-only ticket route.
public_marker = "@public_app.get('/health')"
if "@public_app.get('/w/{signed_token}'" not in text:
    public_routes = r'''
@public_app.get('/w/{signed_token}', response_class=HTMLResponse)
def whatsapp_public_ticket(request: Request, signed_token: str):
    ticket_id = whatsapp_ticket_id(signed_token)
    con = db()
    ticket = con.execute('SELECT t.*,z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=? ORDER BY id', (ticket_id,)).fetchall()
    con.close()
    if not ticket:
        raise HTTPException(404, 'Ticket non trovato')
    photos = ''.join(
        f'<a href="{esc(signed_token)}/file/{f["id"]}" target="_blank"><img src="{esc(signed_token)}/file/{f["id"]}" alt="Foto ticket"></a>'
        for f in files
    ) or '<p class="muted">Nessuna foto allegata.</p>'
    body = f'<div class="public-card"><h1>Intervento {esc(ticket["ticket_code"])}</h1><p><b>Zona:</b> {esc(ticket["zone_name"])}</p><p><b>Categoria:</b> {esc(ticket["category"])}</p><p><b>Priorità:</b> {esc(ticket["priority"] or "Normale")}</p><p><b>Stato:</b> {esc(ticket["status"])}</p><h2>Problema</h2><p style="white-space:pre-wrap">{esc(ticket["description_original"])}</p><h2>Foto</h2><div class="photos">{photos}</div></div>'
    return page(f'Intervento {ticket["ticket_code"]}', body, public=True, lang='it', close_on_back=True)


@public_app.get('/w/{signed_token}/file/{file_id}')
def whatsapp_public_file(signed_token: str, file_id: int):
    ticket_id = whatsapp_ticket_id(signed_token)
    con = db()
    row = con.execute('SELECT * FROM ticket_files WHERE id=? AND ticket_id=?', (file_id, ticket_id)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404)
    target = (UPLOAD_DIR / row['stored_name']).resolve()
    if not target.is_file() or target.parent != UPLOAD_DIR.resolve():
        raise HTTPException(404)
    return FileResponse(target, media_type=row['content_type'], content_disposition_type='inline', headers={'Cache-Control': 'private, no-store'})


'''
    if public_marker not in text:
        raise SystemExit('WhatsApp public route marker not found')
    text = text.replace(public_marker, public_routes + public_marker, 1)

path.write_text(text, encoding='utf-8')
