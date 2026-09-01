import hashlib
import io
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from passlib.hash import argon2

DATA_DIR = Path('/data')
UPLOAD_DIR = DATA_DIR / 'uploads'
DB_PATH = DATA_DIR / 'hausmeister.db'
SECRET_PATH = DATA_DIR / 'session_secret'
OPTIONS_PATH = Path('/data/options.json')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS zones (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      token TEXT NOT NULL UNIQUE,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_code TEXT UNIQUE,
      zone_id INTEGER NOT NULL,
      reporter_name TEXT NOT NULL,
      category TEXT NOT NULL,
      description_original TEXT NOT NULL,
      description_it TEXT,
      source_language TEXT,
      translation_status TEXT NOT NULL DEFAULT 'pending',
      status TEXT NOT NULL DEFAULT 'Nuovo',
      created_at TEXT NOT NULL,
      FOREIGN KEY(zone_id) REFERENCES zones(id)
    );
    CREATE TABLE IF NOT EXISTS ticket_files (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id INTEGER NOT NULL,
      stored_name TEXT NOT NULL,
      original_name TEXT NOT NULL,
      content_type TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(ticket_id) REFERENCES tickets(id)
    );
    ''')
    con.commit()
    con.close()


def load_options():
    try:
        return json.loads(OPTIONS_PATH.read_text())
    except Exception:
        return {}


def get_setting(key: str, default: Optional[str] = None):
    con = db()
    row = con.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    con.close()
    return row['value'] if row else default


def set_setting(key: str, value: str):
    con = db()
    con.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    con.commit()
    con.close()


def delete_setting(key: str):
    con = db()
    con.execute('DELETE FROM settings WHERE key=?', (key,))
    con.commit()
    con.close()


def serializer():
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_urlsafe(48))
    return URLSafeTimedSerializer(SECRET_PATH.read_text().strip(), salt='hausmeister-public-session')


def public_base_url():
    return (load_options().get('public_base_url') or '').strip().rstrip('/')


def brand_logo():
    return '''<div class="brand-logo" aria-label="Carellas Ristorante">
    <svg viewBox="0 0 360 128" role="img" aria-label="Carellas Ristorante">
      <g fill="none" stroke="#6e7d08" stroke-width="7" stroke-linecap="round">
        <path d="M40 55 C55 22,115 22,132 55"/><path d="M30 65 C67 51,116 52,152 70"/><path d="M83 20 v-7"/>
      </g>
      <path d="M25 78 C67 62,123 66,169 83" fill="none" stroke="#333b35" stroke-width="8" stroke-linecap="round"/>
      <text x="169" y="74" font-size="26" fill="#333b35" font-style="italic" font-family="Georgia,serif">Carellas</text>
      <text x="52" y="112" font-size="42" fill="#6e7d08" font-style="italic" font-weight="700" font-family="Georgia,serif">Ristorante</text>
    </svg></div>'''


def page(title: str, body: str, public: bool = False):
    shell_class = 'public-shell' if public else 'admin-shell'
    back = '<button type="button" class="back-btn" onclick="history.back()">← Indietro</button>'
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#6e7d08"><title>{title}</title><style>
:root{{--olive:#6e7d08;--olive-dark:#586406;--cream:#fbfaf5;--ink:#17212b;--muted:#6b7280;--line:#e5e7eb;--danger:#c62828;--card:#fff;--nav:#18252d;--shadow:0 4px 18px #00000012}}
*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:#eef1f2}}
body{{overflow-x:hidden}}button,input,textarea,select{{font:inherit}}a{{color:inherit}}.brand-logo{{width:230px;max-width:100%;margin:0 auto}}.brand-logo svg{{display:block;width:100%;height:auto}}
.page{{min-height:100vh}}.admin-shell{{display:grid;grid-template-columns:245px minmax(0,1fr);min-height:100vh}}.sidebar{{background:var(--nav);color:#fff;padding:18px 14px;position:sticky;top:0;height:100vh}}.sidebar .brand-wrap{{background:#fff;border-radius:15px;padding:10px;margin-bottom:18px}}.side-link{{display:block;text-decoration:none;padding:11px 12px;border-radius:9px;margin:5px 0;color:#f6f7f8}}.side-link.active,.side-link:hover{{background:var(--olive)}}.side-foot{{position:absolute;bottom:18px;left:22px;right:22px;color:#cfd8dc;font-size:12px;text-align:center;border-top:1px solid #ffffff25;padding-top:12px}}
.content{{min-width:0}}.topbar{{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:16px 22px;background:#fff;border-bottom:1px solid var(--line)}}.topbar h1{{font-size:24px;margin:0}}.topbar small{{color:var(--muted)}}.status-dot{{padding:7px 11px;background:#eef7ea;border-radius:999px;color:#2e6c2f;font-size:13px;white-space:nowrap}}main{{padding:18px;max-width:1480px;margin:0 auto;width:100%}}.nav{{display:flex;align-items:center;gap:10px;margin:0 0 12px}}
.card{{background:var(--card);border-radius:16px;padding:18px;box-shadow:var(--shadow);border:1px solid #e9ecef}}h1,h2,h3{{margin-top:0}}h2{{font-size:20px}}.grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}}.span-3{{grid-column:span 3}}.span-4{{grid-column:span 4}}.span-5{{grid-column:span 5}}.span-7{{grid-column:span 7}}.span-8{{grid-column:span 8}}.span-12{{grid-column:span 12}}.metric{{display:flex;align-items:center;gap:13px}}.metric-icon{{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;background:#eef1d8;color:var(--olive);font-size:20px}}.metric strong{{font-size:28px;display:block}}.muted{{color:var(--muted);font-size:14px}}.pill{{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2f7;font-size:12px}}.pill.open{{background:#fff2dd;color:#a75d00}}.pill.done{{background:#e8f6e5;color:#2f7c35}}
input,textarea,select{{width:100%;padding:13px 14px;margin:7px 0 15px;border:1px solid #cfd6dc;border-radius:10px;background:#fff;font-size:16px}}textarea{{resize:vertical;min-height:130px}}label{{font-weight:600;font-size:14px}}button,.btn{{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;padding:12px 16px;background:var(--olive);color:#fff;text-decoration:none;font-weight:700;cursor:pointer;min-height:44px}}button:hover,.btn:hover{{background:var(--olive-dark)}}.back-btn{{background:#f1f3f4;color:#263238}}.back-btn:hover{{background:#e5e7e9}}.danger{{background:var(--danger)}}.inline{{display:inline-block;margin:4px 8px 4px 0}}.actions{{display:flex;gap:9px;flex-wrap:wrap}}.table-wrap{{overflow:auto;width:100%;-webkit-overflow-scrolling:touch}}table{{width:100%;border-collapse:collapse;min-width:620px}}th,td{{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}th{{font-size:13px;color:#4b5563}}img.qr{{width:240px;max-width:100%;height:auto}}.zone-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}}.zone-row:last-child{{border-bottom:0}}
.public-shell{{min-height:100vh;background:linear-gradient(145deg,#fff 0%,var(--cream) 100%);display:grid;place-items:center;padding:24px}}.public-wrap{{width:min(720px,100%);margin:auto}}.public-brand{{width:300px;max-width:80%;margin:0 auto 12px}}.public-card{{background:#fff;border:1px solid #ebe8dc;border-radius:18px;padding:24px;box-shadow:0 12px 35px #0000000f}}.public-card h1{{text-align:center;margin-bottom:6px}}.public-card>.muted{{text-align:center;display:block;margin-bottom:20px}}.public-card button{{width:100%;background:var(--olive)}}.success{{text-align:center;padding:22px 6px}}.success-mark{{width:64px;height:64px;border-radius:50%;background:#eef7ea;color:#2e7d32;display:grid;place-items:center;margin:0 auto 15px;font-size:34px}}
@media(max-width:1000px){{.admin-shell{{grid-template-columns:1fr}}.sidebar{{height:auto;position:relative;padding:10px 12px;display:flex;align-items:center;gap:8px;overflow-x:auto}}.sidebar .brand-wrap{{min-width:155px;margin:0;padding:5px}}.sidebar .brand-logo{{width:145px}}.side-link{{white-space:nowrap;margin:0}}.side-foot{{display:none}}.span-3{{grid-column:span 6}}.span-4,.span-5,.span-7,.span-8{{grid-column:span 12}}}}
@media(max-width:640px){{.sidebar{{display:none}}.topbar{{padding:12px 14px}}.topbar h1{{font-size:20px}}.status-dot{{display:none}}main{{padding:12px}}.grid{{gap:10px}}.span-3,.span-4,.span-5,.span-7,.span-8,.span-12{{grid-column:span 12}}.card{{padding:15px;border-radius:14px}}.metric strong{{font-size:24px}}.public-shell{{padding:14px}}.public-card{{padding:18px 15px}}.public-brand{{max-width:88%;width:270px}}.actions button,.actions .btn{{flex:1 1 140px}}.nav{{margin-bottom:8px}}}}
</style></head><body><div class="page {shell_class}">'''+(
    f'''<aside class="sidebar"><div class="brand-wrap">{brand_logo()}</div><a class="side-link active" href="./">⌂ Dashboard</a><a class="side-link" href="./">☷ Ticket</a><a class="side-link" href="./">⌖ Zone / QR</a><a class="side-link" href="./">⚙ Impostazioni</a><div class="side-foot">Hausmeister Carellas<br>v0.1.3</div></aside><div class="content"><header class="topbar"><div><h1>{title}</h1><small>Gestione manutenzioni Carellas</small></div><div class="status-dot">● Add-on in esecuzione</div></header><main><div class="nav">{back}</div>{body}</main></div>''' if not public else f'''<div class="public-wrap"><div class="public-brand">{brand_logo()}</div><div class="nav">{back}</div>{body}</div>''')+'''</div></body></html>'''


def session_zone(request: Request, token: str):
    cookie = request.cookies.get('hm_session')
    if not cookie:
        return False
    try:
        data = serializer().loads(cookie, max_age=86400)
        return data.get('zone') == token
    except BadSignature:
        return False


init_db()
admin_app = FastAPI(title='Hausmeister Carellas Admin')
public_app = FastAPI(title='Hausmeister Carellas Public')


@admin_app.get('/', response_class=HTMLResponse)
def admin_home():
    con = db()
    zones = con.execute('SELECT * FROM zones ORDER BY name').fetchall()
    tickets = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC LIMIT 50').fetchall()
    con.close()
    total = len(tickets)
    open_count = sum(1 for t in tickets if t['status'] == 'Nuovo')
    work_count = sum(1 for t in tickets if t['status'] in ('Preso in carico','In lavorazione'))
    done_count = sum(1 for t in tickets if t['status'] == 'Risolto')
    zone_rows = ''.join(f'<div class="zone-row"><div><b>{z["name"]}</b><br><span class="muted">{"Attiva" if z["active"] else "Disattivata"}</span></div><a class="btn" href="zone/{z["id"]}">QR →</a></div>' for z in zones) or '<p class="muted">Nessuna zona</p>'
    ticket_rows = ''.join(f'<tr><td><a href="ticket/{t["id"]}"><b>{t["ticket_code"]}</b></a></td><td>{t["zone_name"]}</td><td>{t["reporter_name"]}</td><td><span class="pill {"done" if t["status"] == "Risolto" else "open"}">{t["status"]}</span></td></tr>' for t in tickets) or '<tr><td colspan="4">Nessun ticket</td></tr>'
    pin_configured = bool(get_setting('pin_hash'))
    pin_state = 'Configurato' if pin_configured else 'NON configurato'
    pin_button = 'Modifica PIN' if pin_configured else 'Imposta PIN'
    delete_pin = '''<form class="inline" method="post" action="pin/delete" onsubmit="return confirm('Vuoi davvero eliminare il PIN condiviso? Il portale pubblico resterà bloccato finché non ne imposti uno nuovo.');"><button class="danger" type="submit">Elimina PIN</button></form>''' if pin_configured else ''
    return page('Dashboard', f'''
    <div class="grid">
      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Totale ticket</span><strong>{total}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Aperti</span><strong>{open_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{work_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">Risolti</span><strong>{done_count}</strong></div></div></div>
      <div class="card span-8"><h2>Ticket recenti</h2><div class="table-wrap"><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Stato</th></tr>{ticket_rows}</table></div></div>
      <div class="span-4 grid" style="grid-template-columns:1fr">
        <div class="card span-12"><h2>Zone</h2>{zone_rows}<hr style="border:0;border-top:1px solid var(--line);margin:15px 0"><form method="post" action="zone"><label>Nuova zona</label><input name="name" required placeholder="Es. Cucina, Camera 7"><button>Crea zona e QR</button></form></div>
        <div class="card span-12"><h2>PIN di accesso</h2><p><b>{pin_state}</b></p><form method="post" action="pin"><input type="password" name="pin" minlength="6" required placeholder="Nuovo PIN"><div class="actions"><button type="submit">{pin_button}</button>{delete_pin}</div></form><p class="muted">Nel database viene salvato solo l'hash Argon2.</p></div>
      </div>
    </div>''')


@admin_app.post('/zone')
def create_zone(name: str = Form(...)):
    name = name.strip()
    if not name:
        raise HTTPException(400, 'Nome zona obbligatorio')
    token = secrets.token_urlsafe(18)
    con = db()
    cur = con.execute('INSERT INTO zones(name,token,created_at) VALUES(?,?,?)', (name, token, now_iso()))
    con.commit()
    zone_id = cur.lastrowid
    con.close()
    return RedirectResponse(f'zone/{zone_id}', status_code=303)


@admin_app.post('/pin')
def save_pin(pin: str = Form(...)):
    pin = pin.strip()
    if len(pin) < 6:
        raise HTTPException(400, 'PIN troppo corto: minimo 6 caratteri')
    set_setting('pin_hash', argon2.hash(pin))
    return RedirectResponse('./', status_code=303)


@admin_app.post('/pin/delete')
def remove_pin():
    delete_setting('pin_hash')
    return RedirectResponse('../', status_code=303)


@admin_app.get('/zone/{zone_id}', response_class=HTMLResponse)
def zone_detail(zone_id: int):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    base = public_base_url()
    url = f'{base}/r/{zone["token"]}' if base else f'/r/{zone["token"]}'
    warning = '' if base else '<p><b>Attenzione:</b> imposta public_base_url nelle opzioni add-on prima di stampare il QR definitivo.</p>'
    return page(zone['name'], f'''<div class="grid"><div class="card span-12"><h2>{zone["name"]}</h2>{warning}<p class="muted">{url}</p><img class="qr" src="{zone_id}/qr"><div class="actions" style="margin-top:12px"><a class="btn" href="{zone_id}/qr">Apri QR</a></div></div></div>''')


@admin_app.get('/zone/{zone_id}/qr')
def zone_qr(zone_id: int):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    base = public_base_url()
    url = f'{base}/r/{zone["token"]}' if base else f'/r/{zone["token"]}'
    image = qrcode.make(url)
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return StreamingResponse(buf, media_type='image/png', headers={'Content-Disposition': f'inline; filename="zona-{zone_id}.png"'})


@admin_app.get('/ticket/{ticket_id}', response_class=HTMLResponse)
def ticket_detail(ticket_id: int):
    con = db()
    t = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=?', (ticket_id,)).fetchall()
    con.close()
    if not t:
        raise HTTPException(404)
    photos = ''.join(f'<li>{f["original_name"]}</li>' for f in files) or '<li>Nessuna foto</li>'
    return page(t['ticket_code'], f'''<div class="grid"><div class="card span-7"><h2>{t["ticket_code"]}</h2><p><b>Zona:</b> {t["zone_name"]}</p><p><b>Segnalato da:</b> {t["reporter_name"]}</p><p><b>Categoria:</b> {t["category"]}</p><p><b>Stato:</b> <span class="pill">{t["status"]}</span></p><h3>Descrizione originale</h3><p>{t["description_original"]}</p><h3>Traduzione italiana</h3><p>{t["description_it"] or "In attesa"}</p></div><div class="card span-5"><h2>Foto</h2><ul>{photos}</ul></div></div>''')


@public_app.get('/health')
def health():
    return {'ok': True}


@public_app.get('/r/{token}', response_class=HTMLResponse)
def report_form(request: Request, token: str):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Zona non valida')
    if not get_setting('pin_hash'):
        return page('Servizio non configurato', '<div class="public-card"><div class="success"><h1>Servizio non disponibile</h1><p>Il responsabile deve configurare il PIN.</p></div></div>', public=True)
    if not session_zone(request, token):
        return page('Segnalazione guasto', f'''<div class="public-card"><h1>Segnalazione guasto</h1><span class="muted">Zona: <b>{zone["name"]}</b> · Inserisci il PIN per accedere</span><form method="post" action="{token}/unlock"><label>PIN di accesso</label><input type="password" name="pin" autocomplete="off" placeholder="Inserisci PIN" required><button>Accedi</button></form></div>''', public=True)
    return page('Nuova segnalazione', f'''<div class="public-card"><h1>Nuova segnalazione</h1><span class="muted">Zona selezionata: <b>{zone["name"]}</b></span><form method="post" enctype="multipart/form-data" action="{token}/submit"><label>Nome e cognome *</label><input name="reporter_name" required placeholder="Inserisci il tuo nome e cognome"><label>Tipo di guasto *</label><select name="category" required><option value="">Seleziona la categoria</option><option value="Elettrico">Elettrico</option><option value="Idraulico">Idraulico</option><option value="Climatizzazione">Climatizzazione</option><option value="Porta/Finestra">Porta/Finestra</option><option value="Altro">Altro</option></select><label>Descrizione *</label><textarea name="description" rows="6" required placeholder="Descrivi il problema nel dettaglio"></textarea><label>Foto (opzionale)</label><input type="file" name="photos" accept="image/*" multiple><button>➤ Invia segnalazione</button></form></div>''', public=True)


@public_app.post('/r/{token}/unlock')
def unlock(token: str, pin: str = Form(...)):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    pin_hash = get_setting('pin_hash')
    if not pin_hash or not argon2.verify(pin, pin_hash):
        raise HTTPException(403, 'PIN non valido')
    value = serializer().dumps({'zone': token})
    response = RedirectResponse(f'../{token}', status_code=303)
    response.set_cookie('hm_session', value, max_age=86400, httponly=True, secure=True, samesite='lax')
    return response


@public_app.post('/r/{token}/submit', response_class=HTMLResponse)
async def submit_ticket(request: Request, token: str, reporter_name: str = Form(...), category: str = Form(...), description: str = Form(...), photos: list[UploadFile] = File(default=[])):
    if not session_zone(request, token):
        raise HTTPException(403, 'Sessione scaduta')
    reporter_name = reporter_name.strip()
    description = description.strip()
    if not reporter_name or not description:
        raise HTTPException(400, 'Nome e descrizione sono obbligatori')
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    if not zone:
        con.close()
        raise HTTPException(404)
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,description_original,created_at) VALUES(?,?,?,?,?)', (zone['id'], reporter_name, category, description, now_iso()))
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
    return page('Segnalazione ricevuta', f'''<div class="public-card"><div class="success"><div class="success-mark">✓</div><h1>Segnalazione ricevuta</h1><p>Grazie, la segnalazione è stata registrata.</p><p><b>Ticket:</b> {code}<br><b>Zona:</b> {zone["name"]}</p></div></div>''', public=True)
