from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# FastAPI BackgroundTasks lets us return the created ticket immediately while
# translations/notifications continue after the response.
old_import = "from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile"
new_import = "from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile"
if old_import in text:
    text = text.replace(old_import, new_import, 1)

# Create idempotency table once during DB initialization.
db_marker = "    con.execute('CREATE INDEX IF NOT EXISTS idx_tickets_zone ON tickets(zone_id)')"
if db_marker in text and "ticket_submission_tokens" not in text:
    db_insert = """    con.execute('''CREATE TABLE IF NOT EXISTS ticket_submission_tokens (
      token TEXT PRIMARY KEY,
      ticket_id INTEGER,
      created_at TEXT NOT NULL
    )''')
"""
    text = text.replace(db_marker, db_insert + db_marker, 1)

# Replace the internal quick-ticket photo inputs with explicit "Aggiungi foto" controls,
# plus a visible loading overlay/progress bar and one-shot submit protection.
old_photos = '''    photos = ''.join(f'<label>Foto {i} (opzionale)</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif">' for i in range(1, 6))
    body = f"""{inactive_notice}<div class="card" style="max-width:760px;margin:0 auto"><h2>Nuovo ticket</h2><p><b>Zona:</b> {esc(zone['name'])}</p><p class="muted">Accesso interno Home Assistant: nessuna password richiesta.</p><form method="post" enctype="multipart/form-data" action="{zone_id}/submit"><label>Nome e cognome *</label><input name="reporter_name" maxlength="120" required placeholder="Inserisci nome e cognome"><label>Tipo di guasto *</label><select name="category" required>{category_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Descrizione *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="Descrivi il problema nel dettaglio"></textarea>{photos}<button type="submit">➤ Crea ticket</button></form></div>"""
'''
new_photos = '''    submit_token = secrets.token_urlsafe(24)
    photos = ''.join(
        f"""<div class="ticket-photo-row" id="ticket-photo-row-{i}" {'style="display:none"' if i > 1 else ''}>
          <label>Foto {i} (opzionale)</label>
          <div class="ticket-photo-control">
            <input class="hm-ticket-photo-input" id="ticket-photo-{i}" type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" capture="environment" onchange="ticketPhotoSelected(this,{i})">
            <button class="btn ticket-photo-btn" type="button" onclick="document.getElementById('ticket-photo-{i}').click()">📷 Aggiungi foto</button>
            <span class="ticket-photo-name" id="ticket-photo-name-{i}">Nessuna foto selezionata</span>
          </div>
        </div>""" for i in range(1, 6)
    )
    body = f"""{inactive_notice}<style>
.ticket-photo-control{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:7px 0 15px}}
.hm-ticket-photo-input{{position:absolute!important;left:-9999px!important;width:1px!important;height:1px!important;opacity:0!important}}
.ticket-photo-btn{{min-width:155px}}
.ticket-photo-name{{color:var(--muted);font-size:14px;overflow-wrap:anywhere}}
#ticket-submit-overlay{{display:none;position:fixed;inset:0;background:#0008;z-index:99999;align-items:center;justify-content:center;padding:20px}}
#ticket-submit-overlay.show{{display:flex}}
.ticket-submit-box{{width:min(460px,92vw);background:#fff;border-radius:16px;padding:22px;box-shadow:0 15px 45px #0005}}
.ticket-submit-box h3{{margin:0 0 10px}}
.ticket-progress{{height:10px;background:#e6e9ec;border-radius:999px;overflow:hidden;margin-top:16px}}
.ticket-progress-bar{{height:100%;width:35%;background:var(--olive);border-radius:999px;animation:ticketProgress 1.15s ease-in-out infinite}}
@keyframes ticketProgress{{0%{{transform:translateX(-110%)}}50%{{transform:translateX(125%)}}100%{{transform:translateX(300%)}}}}
</style>
<div class="card" style="max-width:760px;margin:0 auto"><h2>Nuovo ticket</h2><p><b>Zona:</b> {esc(zone['name'])}</p><p class="muted">Accesso interno Home Assistant: nessuna password richiesta.</p>
<form id="quick-ticket-form" method="post" enctype="multipart/form-data" action="{zone_id}/submit" onsubmit="return prepareQuickTicketSubmit(this)">
<input type="hidden" name="submission_token" value="{esc(submit_token)}">
<label>Nome e cognome *</label><input name="reporter_name" maxlength="120" required placeholder="Inserisci nome e cognome">
<label>Tipo di guasto *</label><select name="category" required>{category_options}</select>
<label>Priorità</label><select name="priority">{priority_options}</select>
<label>Descrizione *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="Descrivi il problema nel dettaglio"></textarea>
{photos}
<button id="quick-ticket-submit" type="submit">➤ Crea ticket</button>
</form></div>
<div id="ticket-submit-overlay" aria-live="polite"><div class="ticket-submit-box"><h3>Creazione ticket in corso…</h3><p class="muted">Attendi la conferma. Non premere nuovamente il pulsante.</p><div class="ticket-progress"><div class="ticket-progress-bar"></div></div></div></div>
<script>
function ticketPhotoSelected(input,index){{
  const name=document.getElementById('ticket-photo-name-'+index);
  if(name) name.textContent=(input.files&&input.files.length)?input.files[0].name:'Nessuna foto selezionata';
  if(input.files&&input.files.length&&index<5){{
    const next=document.getElementById('ticket-photo-row-'+(index+1));
    if(next) next.style.display='block';
  }}
}}
function prepareQuickTicketSubmit(form){{
  if(form.dataset.submitting==='1') return false;
  if(!form.reportValidity()) return false;
  form.dataset.submitting='1';
  const button=document.getElementById('quick-ticket-submit');
  if(button){{button.disabled=true;button.textContent='Creazione in corso…';}}
  const overlay=document.getElementById('ticket-submit-overlay');
  if(overlay) overlay.classList.add('show');
  return true;
}}
</script>"""
'''
if old_photos in text:
    text = text.replace(old_photos, new_photos, 1)
else:
    raise SystemExit('Quick-ticket photo form pattern not found')

# Do not let the generic i18n file-input enhancer hide/replace our explicit ticket controls.
old_setup = """document.querySelectorAll('input[type="file"]').forEach(input=>{"""
new_setup = """document.querySelectorAll('input[type="file"]:not(.hm-ticket-photo-input)').forEach(input=>{"""
if old_setup in text:
    text = text.replace(old_setup, new_setup, 1)

# Background task: translate + notify after redirect, so confirmation is fast.
route_marker = "@admin_app.post('/quick-ticket/{zone_id}/submit')"
if route_marker in text and "def _finish_quick_ticket_background" not in text:
    helper = r'''
def _finish_quick_ticket_background(ticket_id: int, code: str, zone_name: str, category: str, priority: str, description: str):
    try:
        description_it, status_it = translate_text(description, 'it')
        description_de, status_de = translate_text(description, 'de')
        state = 'completed' if status_it == 'completed' and status_de == 'completed' else ('failed' if 'failed' in (status_it, status_de) else 'pending')
        con = db()
        con.execute('UPDATE tickets SET description_it=?,description_de=?,translation_status=?,updated_at=? WHERE id=?',
                    (description_it or description, description_de, state, now_iso(), ticket_id))
        con.commit()
        con.close()
    except Exception as exc:
        print(f'Quick ticket background translation failed: {exc}', flush=True)
    try:
        direct_url = ticket_notification_url(ticket_id)
        title = f'{"URGENTE · " if priority == "Urgente" else ""}Ticket {code}'
        message = f'Zona {zone_name} · {category} · Priorità {priority}\n{description[:250]}'
        notify_home_assistant(message, title, direct_url)
    except Exception as exc:
        print(f'Quick ticket background notification failed: {exc}', flush=True)


'''
    text = text.replace(route_marker, helper + route_marker, 1)

old_sig = """async def admin_quick_ticket_submit(zone_id: int, reporter_name: str = Form(...), category: str = Form(...), priority: str = Form('Normale'), description: str = Form(...), photos: list[UploadFile] = File(default=[])):"""
new_sig = """async def admin_quick_ticket_submit(background_tasks: BackgroundTasks, zone_id: int, reporter_name: str = Form(...), category: str = Form(...), priority: str = Form('Normale'), description: str = Form(...), submission_token: str = Form(''), photos: list[UploadFile] = File(default=[])):"""
if old_sig in text:
    text = text.replace(old_sig, new_sig, 1)
else:
    raise SystemExit('Quick-ticket submit signature not found')

# Replace synchronous translation + insert with idempotent immediate insert.
old_sync = """    description_it, status_it = translate_text(description, 'it')
    description_de, status_de = translate_text(description, 'de')
    translation_status = 'completed' if status_it == 'completed' and status_de == 'completed' else ('failed' if 'failed' in (status_it, status_de) else 'pending')
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,description_de,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description_it, description_de, translation_status, now_iso(), now_iso()))
    ticket_id = cur.lastrowid
"""
new_sync = """    submission_token = submission_token.strip()
    if not submission_token or len(submission_token) > 120:
        con.close()
        raise HTTPException(400, 'Token invio non valido')
    try:
        con.execute('INSERT INTO ticket_submission_tokens(token,ticket_id,created_at) VALUES(?,?,?)', (submission_token, None, now_iso()))
        con.commit()
    except sqlite3.IntegrityError:
        previous = con.execute('SELECT ticket_id FROM ticket_submission_tokens WHERE token=?', (submission_token,)).fetchone()
        previous_id = previous['ticket_id'] if previous else None
        con.close()
        if previous_id:
            return RedirectResponse(f'../../ticket/{previous_id}', status_code=303)
        raise HTTPException(409, 'Ticket già in creazione. Attendi la conferma.')
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,description_de,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description, None, 'pending', now_iso(), now_iso()))
    ticket_id = cur.lastrowid
"""
if old_sync in text:
    text = text.replace(old_sync, new_sync, 1)
else:
    raise SystemExit('Synchronous quick-ticket translation block not found')

# Store token -> ticket id before commit/redirect.
commit_marker = """    con.commit()
    con.close()
    direct_url = ticket_notification_url(ticket_id)
    title = f'{"URGENTE · " if priority == "Urgente" else ""}Ticket {code}'
    message = f'Zona {zone["name"]} · {category} · Priorità {priority}\n{description[:250]}'
    notify_home_assistant(message, title, direct_url)
    return RedirectResponse(f'../../ticket/{ticket_id}', status_code=303)
"""
commit_new = """    con.execute('UPDATE ticket_submission_tokens SET ticket_id=? WHERE token=?', (ticket_id, submission_token))
    con.commit()
    con.close()
    background_tasks.add_task(_finish_quick_ticket_background, ticket_id, code, zone['name'], category, priority, description)
    return RedirectResponse(f'../../ticket/{ticket_id}', status_code=303)
"""
if commit_marker in text:
    text = text.replace(commit_marker, commit_new, 1)
else:
    raise SystemExit('Quick-ticket commit/notification block not found')

path.write_text(text, encoding='utf-8')
