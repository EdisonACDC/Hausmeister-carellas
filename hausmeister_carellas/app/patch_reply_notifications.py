from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Notification bell + two-way ticket replies for WhatsApp technicians.
# Runs after all other patches so it can safely extend the collaboration feature.

# 1) Extend collaboration schema with sender/read state.
schema_marker = "ensure_whatsapp_collaboration_schema()\nadmin_app = FastAPI(title='Hausmeister Carellas Admin')"
if schema_marker in text and "ensure_whatsapp_notification_schema" not in text:
    schema = """ensure_whatsapp_collaboration_schema()

def ensure_whatsapp_notification_schema():
    con = db()
    columns = {row['name'] for row in con.execute('PRAGMA table_info(whatsapp_ticket_comments)').fetchall()}
    if 'author_type' not in columns:
        con.execute("ALTER TABLE whatsapp_ticket_comments ADD COLUMN author_type TEXT NOT NULL DEFAULT 'technician'")
    if 'is_read' not in columns:
        con.execute("ALTER TABLE whatsapp_ticket_comments ADD COLUMN is_read INTEGER NOT NULL DEFAULT 0")
    con.execute('CREATE INDEX IF NOT EXISTS idx_whatsapp_comments_unread ON whatsapp_ticket_comments(author_type,is_read)')
    con.commit()
    con.close()

ensure_whatsapp_notification_schema()
admin_app = FastAPI(title='Hausmeister Carellas Admin')"""
    text = text.replace(schema_marker, schema, 1)

# 2) Technician responses become unread notifications.
old_insert = """    con.execute('INSERT INTO whatsapp_ticket_comments(ticket_id,contact_id,comment,needs_material,material_note,created_at) VALUES(?,?,?,?,?,?)',
                (ticket_id, contact_id, comment, needs, material_note, now_iso()))
    con.commit()
    con.close()
    return RedirectResponse(f'/w/{urllib.parse.quote(signed_token, safe="")}?sent=1', status_code=303)"""
new_insert = """    con.execute('INSERT INTO whatsapp_ticket_comments(ticket_id,contact_id,comment,needs_material,material_note,created_at,author_type,is_read) VALUES(?,?,?,?,?,?,?,?)',
                (ticket_id, contact_id, comment, needs, material_note, now_iso(), 'technician', 0))
    ticket_info = con.execute('SELECT ticket_code FROM tickets WHERE id=?', (ticket_id,)).fetchone()
    contact_info = con.execute('SELECT name FROM whatsapp_contacts WHERE id=?', (contact_id,)).fetchone()
    con.commit()
    con.close()
    try:
        contact_name = contact_info['name'] if contact_info else 'Tecnico'
        code = ticket_info['ticket_code'] if ticket_info else str(ticket_id)
        material_text = f' · Materiale: {material_note}' if needs and material_note else ''
        notify_home_assistant(
            f'{contact_name}: {comment or "Richiesta materiale"}{material_text}',
            f'🔔 Nuova risposta ticket {code}',
            ticket_notification_url(ticket_id),
        )
    except Exception as exc:
        print(f'WhatsApp reply notification failed: {exc}', flush=True)
    return RedirectResponse(f'/w/{urllib.parse.quote(signed_token, safe="")}?sent=1', status_code=303)"""
if old_insert in text:
    text = text.replace(old_insert, new_insert, 1)
else:
    raise SystemExit('Technician comment insert marker not found')

# 3) Public conversation shows admin replies as Hausmeister, not as the technician.
old_public_sender = """f'<div class="notice {"warning" if row["needs_material"] else ""}" style="margin-top:10px"><b>{esc(row["contact_name"] or "Tecnico")}</b> · {esc(row["created_at"][:16].replace("T"," "))}<br>{esc(row["comment"] or "")}{("<br><b>⚠ Materiale necessario:</b> " + esc(row["material_note"] or "Da definire")) if row["needs_material"] else ""}</div>'"""
new_public_sender = """f'<div class="notice {"warning" if row["needs_material"] else ""}" style="margin-top:10px"><b>{esc("Hausmeister Carellas" if row["author_type"] == "admin" else (row["contact_name"] or "Tecnico"))}</b> · {esc(row["created_at"][:16].replace("T"," "))}<br>{esc(row["comment"] or "")}{("<br><b>⚠ Materiale necessario:</b> " + esc(row["material_note"] or "Da definire")) if row["needs_material"] else ""}</div>'"""
if old_public_sender in text:
    text = text.replace(old_public_sender, new_public_sender, 1)

# Same correction inside the admin ticket's conversation.
old_admin_sender = """f'<div class="notice {"warning" if row["needs_material"] else ""}" style="margin-top:10px"><b>{esc(row["contact_name"] or "Tecnico")}</b> · {esc(row["created_at"][:16].replace("T"," "))}<br>{esc(row["comment"] or "")}{("<br><b>⚠ Materiale necessario:</b> " + esc(row["material_note"] or "Da definire")) if row["needs_material"] else ""}</div>'"""
if old_admin_sender in text:
    text = text.replace(old_admin_sender, new_public_sender, 1)

# 4) Bell helper before page().
page_marker = "def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):"
if page_marker in text and "def notification_bell_html" not in text:
    helper = r"""
def unread_technician_reply_count():
    try:
        con = db()
        count = con.execute("SELECT COUNT(*) n FROM whatsapp_ticket_comments WHERE author_type='technician' AND is_read=0").fetchone()['n']
        con.close()
        return int(count)
    except Exception:
        return 0


def notification_bell_html():
    count = unread_technician_reply_count()
    badge = f'<span class="notification-badge" id="notification-badge">{count}</span>' if count else '<span class="notification-badge" id="notification-badge" style="display:none">0</span>'
    return f'''<a class="notification-bell" href="notifications" onclick="return adminGo('notifications')" title="Notifiche" aria-label="Notifiche">🔔{badge}</a>
<script>
(function(){{
  function hmAdminUrl(path){{
    const marker='/api/hassio_ingress/';
    const current=location.pathname;
    const start=current.indexOf(marker);
    if(start>=0){{
      const after=start+marker.length;
      const slash=current.indexOf('/',after);
      const base=slash>=0?current.slice(0,slash+1):current+'/';
      return base+path;
    }}
    return '/'+path;
  }}
  async function refreshBell(){{
    try{{
      const r=await fetch(hmAdminUrl('notifications/count'),{{credentials:'same-origin',cache:'no-store'}});
      if(!r.ok)return;
      const d=await r.json();
      const b=document.getElementById('notification-badge');
      if(!b)return;
      const n=Number(d.count||0);
      b.textContent=String(n);
      b.style.display=n>0?'inline-flex':'none';
    }}catch(e){{}}
  }}
  setTimeout(refreshBell,800);
  setInterval(refreshBell,30000);
}})();
</script>'''


"""
    text = text.replace(page_marker, helper + page_marker, 1)

# Bell CSS.
css_marker = ".status-dot{{padding:7px 11px;background:#eef7ea;border-radius:999px;color:#2e6c2f;font-size:13px;white-space:nowrap}}"
if css_marker in text and ".notification-bell" not in text:
    css = css_marker + """.top-actions{{display:flex;align-items:center;gap:10px}}.notification-bell{{position:relative;display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:50%;background:#f4f6f7;text-decoration:none;font-size:22px;border:1px solid var(--line)}}.notification-bell:hover{{background:#eef1d8}}.notification-badge{{position:absolute;right:-4px;top:-5px;min-width:20px;height:20px;padding:0 5px;display:inline-flex;align-items:center;justify-content:center;border-radius:999px;background:#c62828;color:#fff;font-size:11px;font-weight:800;border:2px solid #fff}}"""
    text = text.replace(css_marker, css, 1)

# Add bell to the normal Ingress/admin topbar.
old_topbar = """<div class="status-dot">● {access_label}</div></header>"""
new_topbar = """<div class="top-actions">{notification_bell_html()}<div class="status-dot">● {access_label}</div></div></header>"""
if old_topbar in text:
    text = text.replace(old_topbar, new_topbar, 1)
else:
    raise SystemExit('Admin topbar marker not found for notification bell')

# 5) Notification center + reply route.
route_marker = "@admin_app.get('/tickets', response_class=HTMLResponse)"
if route_marker in text and "@admin_app.get('/notifications'" not in text:
    routes = r"""
@admin_app.get('/notifications/count')
def notification_count():
    return {'count': unread_technician_reply_count()}


@admin_app.get('/notifications', response_class=HTMLResponse)
def notifications_page(message: str = ''):
    con = db()
    rows = con.execute('''
        SELECT wc.*, c.name contact_name, c.phone contact_phone,
               t.ticket_code, t.id ticket_id, z.name zone_name
        FROM whatsapp_ticket_comments wc
        LEFT JOIN whatsapp_contacts c ON c.id=wc.contact_id
        JOIN tickets t ON t.id=wc.ticket_id
        JOIN zones z ON z.id=t.zone_id
        ORDER BY wc.id DESC
        LIMIT 100
    ''').fetchall()
    con.execute("UPDATE whatsapp_ticket_comments SET is_read=1 WHERE author_type='technician' AND is_read=0")
    con.commit()
    con.close()

    cards = ''
    for row in rows:
        is_admin = row['author_type'] == 'admin'
        sender = 'Hausmeister Carellas' if is_admin else (row['contact_name'] or 'Tecnico')
        material = ''
        if row['needs_material']:
            material = f'<div class="notice warning" style="margin-top:8px"><b>⚠ Serve materiale:</b> {esc(row["material_note"] or "Da definire")}</div>'
        reply = ''
        if not is_admin:
            reply = f'''<details style="margin-top:12px"><summary><b>↩ Rispondi</b></summary>
              <form method="post" action="notifications/{row["id"]}/reply" style="margin-top:12px">
                <label>Risposta</label>
                <textarea name="reply" maxlength="2000" rows="3" required placeholder="Scrivi la risposta al tecnico"></textarea>
                <label style="display:flex;align-items:center;gap:8px;margin-bottom:12px"><input type="checkbox" name="open_whatsapp" value="1" checked style="width:auto;margin:0"> Apri anche WhatsApp con la risposta pronta</label>
                <button type="submit">💬 Invia risposta</button>
              </form></details>'''
        cards += f'''<div class="card" style="margin-bottom:14px">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
            <div><b>{esc(sender)}</b> · <a href="ticket/{row["ticket_id"]}" onclick="return adminGo('ticket/{row["ticket_id"]}')">Ticket {esc(row["ticket_code"])}</a><br>
            <span class="muted">Zona: {esc(row["zone_name"])} · {esc(row["created_at"][:16].replace("T"," "))}</span></div>
            <span class="pill {"done" if is_admin else "open"}">{"Tua risposta" if is_admin else "Risposta tecnico"}</span>
          </div>
          <p style="white-space:pre-wrap;margin-bottom:8px">{esc(row["comment"] or "")}</p>
          {material}{reply}
        </div>'''

    if not cards:
        cards = '<div class="card"><p class="muted">Nessuna risposta ricevuta.</p></div>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Notifiche', f'''{notice}<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:14px"><div><h2 style="margin:0">🔔 Risposte ai ticket</h2><p class="muted" style="margin:4px 0 0">Qui trovi le risposte dei tecnici e le richieste di materiale.</p></div></div>{cards}''', back_url='./')


@admin_app.post('/notifications/{comment_id}/reply')
def notification_reply(comment_id: int, reply: str = Form(...), open_whatsapp: str = Form('')):
    reply = reply.strip()
    if not reply or len(reply) > 2000:
        raise HTTPException(400, 'Risposta non valida')
    con = db()
    source = con.execute('''
        SELECT wc.*, c.name contact_name, c.phone contact_phone,
               t.ticket_code, t.id ticket_id
        FROM whatsapp_ticket_comments wc
        LEFT JOIN whatsapp_contacts c ON c.id=wc.contact_id
        JOIN tickets t ON t.id=wc.ticket_id
        WHERE wc.id=?
    ''', (comment_id,)).fetchone()
    if not source:
        con.close()
        raise HTTPException(404, 'Notifica non trovata')
    con.execute('INSERT INTO whatsapp_ticket_comments(ticket_id,contact_id,comment,needs_material,material_note,created_at,author_type,is_read) VALUES(?,?,?,?,?,?,?,?)',
                (source['ticket_id'], source['contact_id'], reply, 0, '', now_iso(), 'admin', 1))
    con.execute('UPDATE whatsapp_ticket_comments SET is_read=1 WHERE id=?', (comment_id,))
    con.commit()
    con.close()

    if open_whatsapp == '1' and source['contact_phone']:
        base = whatsapp_public_base_url()
        token = whatsapp_ticket_token(source['ticket_id'], source['contact_id'])
        link = f'{base}/w/{urllib.parse.quote(token, safe="")}' if base else ''
        message = f'💬 Risposta Hausmeister Carellas\nTicket {source["ticket_code"]}\n\n{reply}'
        if link:
            message += f'\n\n📋 Apri il ticket: {link}'
        wa_url = f'https://wa.me/{source["contact_phone"]}?text={urllib.parse.quote(message)}'
        safe_url = esc(wa_url)
        body = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Apri WhatsApp</title></head><body style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;padding:24px;text-align:center"><h2>Risposta salvata</h2><p>Sto aprendo WhatsApp fuori da Home Assistant…</p><p><a target="_top" href="' + safe_url + '" style="display:inline-block;background:#16883f;color:#fff;text-decoration:none;padding:14px 20px;border-radius:12px;font-weight:700">Apri WhatsApp</a></p><script>setTimeout(function(){try{window.top.location.href=' + json.dumps(wa_url) + ';}catch(e){window.location.href=' + json.dumps(wa_url) + ';}},120);</script></body></html>'
        return HTMLResponse(body, headers={'Cache-Control':'no-store'})

    return RedirectResponse('../notifications?message=' + urllib.parse.quote('Risposta salvata nel ticket.'), status_code=303)


"""
    text = text.replace(route_marker, routes + route_marker, 1)
else:
    raise SystemExit('Notification routes insertion marker not found')

path.write_text(text, encoding='utf-8')
