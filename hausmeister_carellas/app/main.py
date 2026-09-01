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


def serializer():
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_urlsafe(48))
    return URLSafeTimedSerializer(SECRET_PATH.read_text().strip(), salt='hausmeister-public-session')


def public_base_url():
    return (load_options().get('public_base_url') or '').strip().rstrip('/')


def page(title: str, body: str):
    return f'''<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f4f6f8;margin:0;color:#17212b}}main{{max-width:900px;margin:0 auto;padding:18px}}.card{{background:white;border-radius:16px;padding:18px;margin:12px 0;box-shadow:0 2px 12px #00000012}}h1,h2{{margin-top:0}}input,textarea,select{{width:100%;box-sizing:border-box;padding:12px;margin:6px 0 14px;border:1px solid #cbd5df;border-radius:10px;font-size:16px}}button,.btn{{display:inline-block;border:0;border-radius:10px;padding:12px 16px;background:#1976d2;color:white;text-decoration:none;font-weight:600;cursor:pointer}}.muted{{color:#65727e;font-size:14px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e6ebef}}.pill{{display:inline-block;padding:4px 9px;border-radius:999px;background:#edf2f7}}img.qr{{width:220px;max-width:100%}}</style></head><body><main>{body}</main></body></html>'''


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
    zone_rows = ''.join(f'<tr><td>{z["name"]}</td><td>{"Attiva" if z["active"] else "Disattivata"}</td><td><a class="btn" href="zone/{z["id"]}">QR</a></td></tr>' for z in zones) or '<tr><td colspan="3">Nessuna zona</td></tr>'
    ticket_rows = ''.join(f'<tr><td><a href="ticket/{t["id"]}">{t["ticket_code"]}</a></td><td>{t["zone_name"]}</td><td>{t["reporter_name"]}</td><td><span class="pill">{t["status"]}</span></td></tr>' for t in tickets) or '<tr><td colspan="4">Nessun ticket</td></tr>'
    pin_state = 'Configurato' if get_setting('pin_hash') else 'NON configurato'
    return page('Hausmeister Carellas', f'''<div class="card"><h1>Hausmeister Carellas</h1><p>Gestione manutenzioni</p><p><b>PIN pubblico:</b> {pin_state}</p></div><div class="card"><h2>Crea zona</h2><form method="post" action="zone"><label>Nome zona</label><input name="name" required placeholder="Es. Cucina, Camera 7"><button>Crea zona e QR</button></form></div><div class="card"><h2>PIN condiviso</h2><form method="post" action="pin"><input type="password" name="pin" minlength="6" required placeholder="Nuovo PIN"><button>Salva PIN</button></form><p class="muted">Il PIN viene salvato nel database solo come hash Argon2.</p></div><div class="card"><h2>Zone</h2><table><tr><th>Zona</th><th>Stato</th><th></th></tr>{zone_rows}</table></div><div class="card"><h2>Ticket recenti</h2><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Stato</th></tr>{ticket_rows}</table></div>''')


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
    if len(pin) < 6:
        raise HTTPException(400, 'PIN troppo corto')
    set_setting('pin_hash', argon2.hash(pin))
    return RedirectResponse('./', status_code=303)


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
    return page(zone['name'], f'''<div class="card"><a href="../">← Indietro</a><h1>{zone["name"]}</h1>{warning}<p class="muted">{url}</p><img class="qr" src="{zone_id}/qr"><p><a class="btn" href="{zone_id}/qr">Apri QR</a></p></div>''')


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
    return page(t['ticket_code'], f'''<div class="card"><a href="../">← Indietro</a><h1>{t["ticket_code"]}</h1><p><b>Zona:</b> {t["zone_name"]}</p><p><b>Segnalato da:</b> {t["reporter_name"]}</p><p><b>Categoria:</b> {t["category"]}</p><p><b>Stato:</b> {t["status"]}</p><h2>Descrizione originale</h2><p>{t["description_original"]}</p><h2>Traduzione italiana</h2><p>{t["description_it"] or "In attesa"}</p><h2>Foto</h2><ul>{photos}</ul></div>''')


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
        return page('Servizio non configurato', '<div class="card"><h1>Servizio non disponibile</h1><p>Il responsabile deve configurare il PIN.</p></div>')
    if not session_zone(request, token):
        return page('Accesso segnalazione', f'''<div class="card"><h1>{zone["name"]}</h1><p>Inserisci il PIN per aprire una segnalazione.</p><form method="post" action="{token}/unlock"><input type="password" name="pin" autocomplete="off" required><button>Continua</button></form></div>''')
    return page('Nuova segnalazione', f'''<div class="card"><h1>Segnalazione guasto</h1><p><b>Zona:</b> {zone["name"]}</p><form method="post" enctype="multipart/form-data" action="{token}/submit"><label>Nome e cognome *</label><input name="reporter_name" required><label>Tipo di guasto *</label><select name="category" required><option value="Elettrico">Elettrico</option><option value="Idraulico">Idraulico</option><option value="Climatizzazione">Climatizzazione</option><option value="Porta/Finestra">Porta/Finestra</option><option value="Altro">Altro</option></select><label>Descrizione *</label><textarea name="description" rows="6" required></textarea><label>Foto</label><input type="file" name="photos" accept="image/*" multiple><button>Invia segnalazione</button></form></div>''')


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
    return page('Segnalazione ricevuta', f'''<div class="card"><h1>Segnalazione ricevuta</h1><p>Grazie, la segnalazione è stata registrata.</p><p><b>Ticket:</b> {code}</p><p><b>Zona:</b> {zone["name"]}</p></div>''')
