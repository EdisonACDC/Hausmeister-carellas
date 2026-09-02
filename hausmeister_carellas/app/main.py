import hashlib
import html
import io
import json
import secrets
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import qrcode
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
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
APP_VERSION = '1.0.1'
STATUSES = ('Nuovo', 'Preso in carico', 'In lavorazione', 'Da verificare', 'Risolto')
PRIORITIES = ('Bassa', 'Normale', 'Alta', 'Urgente')
PIN_ATTEMPTS = {}
PIN_MAX_ATTEMPTS = 5
PIN_WINDOW_SECONDS = 15 * 60


def esc(value):
    return html.escape(str(value or ''), quote=True)


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
    columns = {row['name'] for row in con.execute('PRAGMA table_info(tickets)').fetchall()}
    for name, sql_type, default in (
        ('updated_at', 'TEXT', None),
        ('resolution_notes', 'TEXT', None),
        ('priority', 'TEXT', "'Normale'"),
    ):
        if name not in columns:
            default_sql = f' DEFAULT {default}' if default else ''
            con.execute(f'ALTER TABLE tickets ADD COLUMN {name} {sql_type}{default_sql}')
    con.execute('CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_tickets_zone ON tickets(zone_id)')
    con.execute('PRAGMA journal_mode=WAL')
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


def notify_home_assistant(message: str, title: str = 'Hausmeister Carellas'):
    options = load_options()
    service = (options.get('notify_service') or '').strip().replace('notify.', '')
    token = __import__('os').environ.get('SUPERVISOR_TOKEN', '')
    if not service or not token:
        return False, 'Servizio di notifica non configurato'
    request = urllib.request.Request(
        f'http://supervisor/core/api/services/notify/{service}',
        data=json.dumps({'title': title, 'message': message}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300, 'Notifica inviata'
    except Exception as exc:
        return False, f'Errore notifica: {exc}'


def translate_to_italian(text: str):
    options = load_options()
    endpoint = (options.get('translation_url') or '').strip()
    if not endpoint:
        return None, 'pending'
    payload = {'q': text, 'source': 'auto', 'target': 'it', 'format': 'text'}
    api_key = (options.get('translation_api_key') or '').strip()
    if api_key:
        payload['api_key'] = api_key
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode())
        translated = (data.get('translatedText') or '').strip()
        return (translated, 'completed') if translated else (None, 'failed')
    except Exception:
        return None, 'failed'


def public_url_for(zone):
    base = public_base_url()
    return f'{base}/r/{zone["token"]}' if base else f'/r/{zone["token"]}'


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
input,textarea,select{{width:100%;padding:13px 14px;margin:7px 0 15px;border:1px solid #cfd6dc;border-radius:10px;background:#fff;font-size:16px}}textarea{{resize:vertical;min-height:130px}}label{{font-weight:600;font-size:14px}}button,.btn{{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;padding:12px 16px;background:var(--olive);color:#fff;text-decoration:none;font-weight:700;cursor:pointer;min-height:44px}}button:hover,.btn:hover{{background:var(--olive-dark)}}.back-btn{{background:#f1f3f4;color:#263238}}.back-btn:hover{{background:#e5e7e9}}.danger{{background:var(--danger)}}.inline{{display:inline-block;margin:4px 8px 4px 0}}.actions{{display:flex;gap:9px;flex-wrap:wrap}}.table-wrap{{overflow:auto;width:100%;-webkit-overflow-scrolling:touch}}table{{width:100%;border-collapse:collapse;min-width:620px}}th,td{{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}th{{font-size:13px;color:#4b5563}}img.qr{{width:240px;max-width:100%;height:auto}}.zone-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}}.zone-row:last-child{{border-bottom:0}}.photos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.photos a{{display:block}}.photos img{{width:100%;height:160px;object-fit:cover;border-radius:10px;border:1px solid var(--line)}}.notice{{padding:12px;border-radius:10px;background:#eef7ea;margin-bottom:14px}}.warning{{background:#fff3dc}}.filters{{display:grid;grid-template-columns:2fr 1fr auto;gap:8px;align-items:end}}.filters input,.filters select{{margin-bottom:0}}
.public-shell{{min-height:100vh;background:linear-gradient(145deg,#fff 0%,var(--cream) 100%);display:grid;place-items:center;padding:24px}}.public-wrap{{width:min(720px,100%);margin:auto}}.public-brand{{width:300px;max-width:80%;margin:0 auto 12px}}.public-card{{background:#fff;border:1px solid #ebe8dc;border-radius:18px;padding:24px;box-shadow:0 12px 35px #0000000f}}.public-card h1{{text-align:center;margin-bottom:6px}}.public-card>.muted{{text-align:center;display:block;margin-bottom:20px}}.public-card button{{width:100%;background:var(--olive)}}.success{{text-align:center;padding:22px 6px}}.success-mark{{width:64px;height:64px;border-radius:50%;background:#eef7ea;color:#2e7d32;display:grid;place-items:center;margin:0 auto 15px;font-size:34px}}
@media(max-width:1000px){{.admin-shell{{grid-template-columns:1fr}}.sidebar{{height:auto;position:relative;padding:10px 12px;display:flex;align-items:center;gap:8px;overflow-x:auto}}.sidebar .brand-wrap{{min-width:155px;margin:0;padding:5px}}.sidebar .brand-logo{{width:145px}}.side-link{{white-space:nowrap;margin:0}}.side-foot{{display:none}}.span-3{{grid-column:span 6}}.span-4,.span-5,.span-7,.span-8{{grid-column:span 12}}}}
@media(max-width:640px){{.topbar{{padding:12px 14px}}.topbar h1{{font-size:20px}}.status-dot{{display:none}}main{{padding:12px}}.grid{{gap:10px}}.span-3,.span-4,.span-5,.span-7,.span-8,.span-12{{grid-column:span 12}}.card{{padding:15px;border-radius:14px}}.metric strong{{font-size:24px}}.public-shell{{padding:14px}}.public-card{{padding:18px 15px}}.public-brand{{max-width:88%;width:270px}}.actions button,.actions .btn{{flex:1 1 140px}}.nav{{margin-bottom:8px}}.filters{{grid-template-columns:1fr}}}}
</style><script>function adminGo(path){{const marker='/api/hassio_ingress/';const current=location.pathname;const start=current.indexOf(marker);if(start>=0){{const after=start+marker.length;const slash=current.indexOf('/',after);const base=slash>=0?current.slice(0,slash+1):current+'/';location.href=base+path;}}else{{location.href='/'+path;}}return false;}}</script></head><body><div class="page {shell_class}">'''+(
    f'''<aside class="sidebar"><div class="brand-wrap">{brand_logo()}</div><a class="side-link" href="./" onclick="return adminGo('')">⌂ Dashboard</a><a class="side-link" href="tickets" onclick="return adminGo('tickets')">☷ Ticket</a><a class="side-link" href="zones" onclick="return adminGo('zones')">⌖ Zone / QR</a><a class="side-link" href="settings" onclick="return adminGo('settings')">⚙ Impostazioni</a><div class="side-foot">Hausmeister Carellas<br>v{APP_VERSION}</div></aside><div class="content"><header class="topbar"><div><h1>{esc(title)}</h1><small>Gestione manutenzioni Carellas</small></div><div class="status-dot">● Add-on in esecuzione</div></header><main><div class="nav">{back}</div>{body}</main></div>''' if not public else f'''<div class="public-wrap"><div class="public-brand">{brand_logo()}</div><div class="nav">{back}</div>{body}</div>''')+'''</div></body></html>'''


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


@admin_app.middleware('http')
async def admin_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@public_app.middleware('http')
async def public_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    return response


@admin_app.get('/', response_class=HTMLResponse)
def admin_home():
    con = db()
    zones = con.execute('SELECT * FROM zones ORDER BY name').fetchall()
    tickets = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC LIMIT 50').fetchall()
    counts = {row['status']: row['n'] for row in con.execute('SELECT status, COUNT(*) n FROM tickets GROUP BY status').fetchall()}
    total = con.execute('SELECT COUNT(*) n FROM tickets').fetchone()['n']
    con.close()
    open_count = counts.get('Nuovo', 0)
    work_count = counts.get('Preso in carico', 0) + counts.get('In lavorazione', 0)
    done_count = counts.get('Risolto', 0)
    zone_rows = ''.join(f'<div class="zone-row"><div><b>{esc(z["name"])}</b><br><span class="muted">{"Attiva" if z["active"] else "Disattivata"}</span></div><a class="btn" href="zone/{z["id"]}">QR →</a></div>' for z in zones) or '<p class="muted">Nessuna zona</p>'
    ticket_rows = ''.join(f'<tr><td><a href="ticket/{t["id"]}"><b>{esc(t["ticket_code"])}</b></a></td><td>{esc(t["zone_name"])}</td><td>{esc(t["reporter_name"])}</td><td><span class="pill {"done" if t["status"] == "Risolto" else "open"}">{esc(t["status"])}</span></td></tr>' for t in tickets) or '<tr><td colspan="4">Nessun ticket</td></tr>'
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
      <div class="card span-8"><h2>Ticket recenti</h2><div class="table-wrap"><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Stato</th></tr>{ticket_rows}</table></div><p><a class="btn" href="tickets">Vedi tutti i ticket</a></p></div>
      <div class="span-4 grid" style="grid-template-columns:1fr">
        <div class="card span-12"><h2>Zone</h2>{zone_rows}<hr style="border:0;border-top:1px solid var(--line);margin:15px 0"><form method="post" action="zone"><label>Nuova zona</label><input name="name" required placeholder="Es. Cucina, Camera 7"><button>Crea zona e QR</button></form></div>
        <div class="card span-12"><h2>PIN di accesso</h2><p><b>{pin_state}</b></p><form method="post" action="pin"><input type="password" name="pin" minlength="6" required placeholder="Nuovo PIN"><div class="actions"><button type="submit">{pin_button}</button>{delete_pin}</div></form><p class="muted">Nel database viene salvato solo l'hash Argon2.</p></div>
      </div>
    </div>''')


@admin_app.get('/tickets', response_class=HTMLResponse)
def tickets_page(q: str = '', status: str = '', message: str = ''):
    query = '''SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE 1=1'''
    params = []
    if q.strip():
        query += ' AND (t.ticket_code LIKE ? OR t.reporter_name LIKE ? OR t.description_original LIKE ? OR z.name LIKE ?)'
        term = f'%{q.strip()}%'
        params.extend([term] * 4)
    if status in STATUSES:
        query += ' AND t.status=?'
        params.append(status)
    query += ' ORDER BY t.id DESC'
    con = db()
    tickets = con.execute(query, params).fetchall()
    con.close()
    rows = ''.join(f'''<tr><td><a href="ticket/{t['id']}"><b>{esc(t['ticket_code'])}</b></a></td><td>{esc(t['zone_name'])}</td><td>{esc(t['reporter_name'])}</td><td>{esc(t['category'])}</td><td>{esc(t['priority'] or 'Normale')}</td><td><span class="pill {'done' if t['status'] == 'Risolto' else 'open'}">{esc(t['status'])}</span></td></tr>''' for t in tickets) or '<tr><td colspan="6">Nessun ticket trovato</td></tr>'
    options = '<option value="">Tutti gli stati</option>' + ''.join(f'<option value="{esc(s)}" {"selected" if status == s else ""}>{esc(s)}</option>' for s in STATUSES)
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Ticket', f'''{notice}<div class="card"><form class="filters" method="get"><div><label>Cerca</label><input name="q" value="{esc(q)}" placeholder="Codice, zona, nome o descrizione"></div><div><label>Stato</label><select name="status">{options}</select></div><button>Cerca</button></form><div class="actions" style="margin:14px 0"><a class="btn" href="tickets/export.csv">Esporta CSV</a></div><div class="table-wrap"><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Categoria</th><th>Priorità</th><th>Stato</th></tr>{rows}</table></div></div>''')


@admin_app.get('/tickets/export.csv')
def tickets_export():
    import csv
    con = db()
    rows = con.execute('''SELECT t.ticket_code,z.name,t.reporter_name,t.category,t.priority,t.status,t.description_original,t.description_it,t.resolution_notes,t.created_at,t.updated_at FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC''').fetchall()
    con.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ticket', 'Zona', 'Segnalato da', 'Categoria', 'Priorità', 'Stato', 'Descrizione', 'Traduzione IT', 'Note', 'Creato', 'Aggiornato'])
    writer.writerows([list(row) for row in rows])
    return StreamingResponse(iter([output.getvalue().encode('utf-8-sig')]), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="ticket-carellas.csv"'})


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


@admin_app.get('/zones', response_class=HTMLResponse)
def zones_page():
    con = db()
    zones = con.execute('SELECT z.*, COUNT(t.id) ticket_count FROM zones z LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY z.name').fetchall()
    con.close()
    rows = ''.join(f'''<tr><td><a href="zone/{z['id']}"><b>{esc(z['name'])}</b></a></td><td>{'Attiva' if z['active'] else 'Disattivata'}</td><td>{z['ticket_count']}</td><td><a class="btn" href="zone/{z['id']}">Apri QR</a></td></tr>''' for z in zones) or '<tr><td colspan="4">Nessuna zona</td></tr>'
    return page('Zone / QR', f'''<div class="grid"><div class="card span-8"><div class="table-wrap"><table><tr><th>Zona</th><th>Stato</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class="card span-4"><h2>Nuova zona</h2><form method="post" action="zone"><label>Nome</label><input name="name" maxlength="80" required placeholder="Es. Cucina"><button>Crea zona e QR</button></form></div></div>''')


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


@admin_app.get('/settings', response_class=HTMLResponse)
def settings_page(message: str = ''):
    options = load_options()
    pin_state = 'Configurato' if get_setting('pin_hash') else 'NON configurato'
    base = options.get('public_base_url') or 'Non configurato'
    notify = options.get('notify_service') or 'Non configurato'
    translation = options.get('translation_url') or 'Non configurata (inserimento manuale disponibile)'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Impostazioni', f'''{notice}<div class="grid"><div class="card span-6"><h2>Configurazione</h2><p><b>URL pubblico:</b><br>{esc(base)}</p><p><b>Servizio notifiche:</b><br>{esc(notify)}</p><p><b>Traduzione automatica:</b><br>{esc(translation)}</p><p class="muted">Questi valori si modificano nella scheda Configurazione dell'add-on di Home Assistant.</p><form method="post" action="settings/test-notification"><button>Invia notifica di prova</button></form></div><div class="card span-6"><h2>PIN condiviso</h2><p><b>{pin_state}</b></p><form method="post" action="pin"><label>Nuovo PIN (minimo 6 caratteri)</label><input type="password" name="pin" minlength="6" required><button>Salva nuovo PIN</button></form><p class="muted">Il PIN non può essere recuperato: si può soltanto sostituire. Le sessioni già aperte scadono dopo 24 ore.</p></div><div class="card span-12"><h2>Backup</h2><p>Scarica database e fotografie in un unico archivio ZIP.</p><a class="btn" href="settings/backup">Scarica backup</a></div></div>''')


@admin_app.post('/settings/test-notification')
def test_notification():
    ok, message = notify_home_assistant('Notifica di prova inviata correttamente.')
    return RedirectResponse(f'../settings?message={urllib.parse.quote(message)}', status_code=303)


@admin_app.get('/settings/backup')
def backup_data():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        if DB_PATH.exists():
            archive.write(DB_PATH, 'hausmeister.db')
        for path in UPLOAD_DIR.iterdir():
            if path.is_file():
                archive.write(path, f'uploads/{path.name}')
    buffer.seek(0)
    filename = f'hausmeister-backup-{datetime.now().strftime("%Y%m%d-%H%M")}.zip'
    return StreamingResponse(buffer, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@admin_app.get('/zone/{zone_id}', response_class=HTMLResponse)
def zone_detail(zone_id: int):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    url = public_url_for(zone)
    warning = '' if public_base_url() else '<div class="notice warning"><b>Attenzione:</b> imposta public_base_url nelle opzioni add-on prima di stampare il QR definitivo.</div>'
    active_label = 'Disattiva zona' if zone['active'] else 'Attiva zona'
    return page(zone['name'], f'''<div class="grid"><div class="card span-12"><h2>{esc(zone["name"])}</h2>{warning}<p><a href="{esc(url)}" target="_blank">{esc(url)}</a></p><img class="qr" src="{zone_id}/qr"><div class="actions" style="margin-top:12px"><a class="btn" href="{zone_id}/qr?download=1">Scarica QR</a><button onclick="window.print()">Stampa</button><form method="post" action="{zone_id}/toggle"><button type="submit">{active_label}</button></form><form method="post" action="{zone_id}/regenerate" onsubmit="return confirm('Il vecchio QR smetterà subito di funzionare. Continuare?')"><button class="danger" type="submit">Rigenera QR</button></form></div></div></div>''')


@admin_app.post('/zone/{zone_id}/toggle')
def zone_toggle(zone_id: int):
    con = db()
    con.execute('UPDATE zones SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (zone_id,))
    con.commit()
    con.close()
    return RedirectResponse(f'../{zone_id}', status_code=303)


@admin_app.post('/zone/{zone_id}/regenerate')
def zone_regenerate(zone_id: int):
    con = db()
    con.execute('UPDATE zones SET token=? WHERE id=?', (secrets.token_urlsafe(18), zone_id))
    con.commit()
    con.close()
    return RedirectResponse(f'../{zone_id}', status_code=303)


@admin_app.get('/zone/{zone_id}/qr')
def zone_qr(zone_id: int, download: int = 0):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    url = public_url_for(zone)
    image = qrcode.make(url)
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    disposition = 'attachment' if download else 'inline'
    return StreamingResponse(buf, media_type='image/png', headers={'Content-Disposition': f'{disposition}; filename="zona-{zone_id}.png"'})


@admin_app.get('/ticket/{ticket_id}', response_class=HTMLResponse)
def ticket_detail(ticket_id: int):
    con = db()
    t = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=?', (ticket_id,)).fetchall()
    con.close()
    if not t:
        raise HTTPException(404)
    photos = ''.join(f'<a href="{ticket_id}/file/{f["id"]}" target="_blank"><img src="{ticket_id}/file/{f["id"]}" alt="{esc(f["original_name"])}"><span class="muted">{esc(f["original_name"])}</span></a>' for f in files) or '<p class="muted">Nessuna foto</p>'
    status_options = ''.join(f'<option value="{esc(s)}" {"selected" if t["status"] == s else ""}>{esc(s)}</option>' for s in STATUSES)
    priority_options = ''.join(f'<option value="{esc(p)}" {"selected" if (t["priority"] or "Normale") == p else ""}>{esc(p)}</option>' for p in PRIORITIES)
    delete_form = ''
    if t['status'] == 'Risolto':
        photo_text = f' e le sue {len(files)} foto' if files else ''
        delete_form = f'''<hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h2>Elimina ticket</h2><p class="muted">Questa operazione libera spazio ma non può essere annullata.</p><form method="post" action="{ticket_id}/delete" onsubmit="return confirm('Eliminare definitivamente il ticket {esc(t['ticket_code'])}{photo_text}?')"><button class="danger" type="submit">Elimina ticket e foto</button></form>'''
    return page(t['ticket_code'], f'''<div class="grid"><div class="card span-7"><h2>{esc(t["ticket_code"])}</h2><p><b>Zona:</b> {esc(t["zone_name"])}</p><p><b>Segnalato da:</b> {esc(t["reporter_name"])}</p><p><b>Categoria:</b> {esc(t["category"])}</p><h3>Descrizione originale</h3><p style="white-space:pre-wrap">{esc(t["description_original"])}</p><h3>Traduzione italiana</h3><p style="white-space:pre-wrap">{esc(t["description_it"] or "In attesa")}</p><form method="post" action="{ticket_id}/translation"><label>Correggi/inserisci traduzione</label><textarea name="description_it" maxlength="4000">{esc(t["description_it"] or "")}</textarea><button>Salva traduzione</button></form></div><div class="card span-5"><h2>Gestione</h2><form method="post" action="{ticket_id}/update"><label>Stato</label><select name="status">{status_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Note interne / soluzione</label><textarea name="resolution_notes" maxlength="4000">{esc(t["resolution_notes"] or "")}</textarea><button>Salva modifiche</button></form><h2 style="margin-top:22px">Foto</h2><div class="photos">{photos}</div>{delete_form}</div></div>''')


@admin_app.post('/ticket/{ticket_id}/delete')
def ticket_delete(ticket_id: int):
    con = db()
    ticket = con.execute('SELECT ticket_code,status FROM tickets WHERE id=?', (ticket_id,)).fetchone()
    if not ticket:
        con.close()
        raise HTTPException(404, 'Ticket non trovato')
    if ticket['status'] != 'Risolto':
        con.close()
        raise HTTPException(409, 'Puoi eliminare soltanto un ticket risolto')
    files = con.execute('SELECT stored_name FROM ticket_files WHERE ticket_id=?', (ticket_id,)).fetchall()
    con.execute('DELETE FROM ticket_files WHERE ticket_id=?', (ticket_id,))
    con.execute('DELETE FROM tickets WHERE id=?', (ticket_id,))
    con.commit()
    con.close()
    deleted_photos = 0
    upload_root = UPLOAD_DIR.resolve()
    for row in files:
        path = (UPLOAD_DIR / row['stored_name']).resolve()
        if path.parent == upload_root and path.is_file():
            try:
                path.unlink()
                deleted_photos += 1
            except OSError:
                pass
    message = f'Ticket {ticket["ticket_code"]} eliminato. Foto eliminate: {deleted_photos}.'
    return RedirectResponse(f'../../tickets?message={urllib.parse.quote(message)}', status_code=303)


@admin_app.post('/ticket/{ticket_id}/update')
def ticket_update(ticket_id: int, status: str = Form(...), priority: str = Form('Normale'), resolution_notes: str = Form('')):
    if status not in STATUSES or priority not in PRIORITIES:
        raise HTTPException(400, 'Valore non valido')
    con = db()
    con.execute('UPDATE tickets SET status=?, priority=?, resolution_notes=?, updated_at=? WHERE id=?', (status, priority, resolution_notes.strip(), now_iso(), ticket_id))
    con.commit()
    con.close()
    return RedirectResponse(f'../{ticket_id}', status_code=303)


@admin_app.post('/ticket/{ticket_id}/translation')
def ticket_translation(ticket_id: int, description_it: str = Form('')):
    con = db()
    con.execute('UPDATE tickets SET description_it=?, translation_status=?, updated_at=? WHERE id=?', (description_it.strip() or None, 'manual' if description_it.strip() else 'pending', now_iso(), ticket_id))
    con.commit()
    con.close()
    return RedirectResponse(f'../{ticket_id}', status_code=303)


@admin_app.get('/ticket/{ticket_id}/file/{file_id}')
def ticket_file(ticket_id: int, file_id: int):
    con = db()
    row = con.execute('SELECT * FROM ticket_files WHERE id=? AND ticket_id=?', (file_id, ticket_id)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404)
    path = UPLOAD_DIR / row['stored_name']
    if not path.is_file() or path.parent != UPLOAD_DIR:
        raise HTTPException(404)
    filename = Path(row['original_name']).name.replace('"', '').replace('\r', '').replace('\n', '')
    return FileResponse(path, media_type=row['content_type'], filename=filename, content_disposition_type='inline', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=300'})


@public_app.get('/health')
def health():
    return {'ok': True, 'version': APP_VERSION}


@public_app.get('/', response_class=HTMLResponse)
def public_home():
    return page('Hausmeister Carellas', '<div class="public-card"><div class="success"><h1>Portale segnalazioni</h1><p>Per aprire una segnalazione, scansiona il QR della zona.</p></div></div>', public=True)


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
        return page('Segnalazione guasto', f'''<div class="public-card"><h1>Segnalazione guasto</h1><span class="muted">Zona: <b>{esc(zone["name"])}</b> · Inserisci il PIN per accedere</span><form method="post" action="{esc(token)}/unlock"><label>PIN di accesso</label><input type="password" name="pin" autocomplete="one-time-code" inputmode="numeric" placeholder="Inserisci PIN" required><button>Accedi</button></form></div>''', public=True)
    return page('Nuova segnalazione', f'''<div class="public-card"><h1>Nuova segnalazione</h1><span class="muted">Zona selezionata: <b>{esc(zone["name"])}</b></span><form method="post" enctype="multipart/form-data" action="{esc(token)}/submit"><label>Nome e cognome *</label><input name="reporter_name" maxlength="120" required placeholder="Inserisci il tuo nome e cognome"><label>Tipo di guasto *</label><select name="category" required><option value="">Seleziona la categoria</option><option value="Elettrico">Elettrico</option><option value="Idraulico">Idraulico</option><option value="Climatizzazione">Climatizzazione</option><option value="Porta/Finestra">Porta/Finestra</option><option value="Attrezzatura cucina">Attrezzatura cucina</option><option value="Altro">Altro</option></select><label>Priorità</label><select name="priority"><option>Normale</option><option>Bassa</option><option>Alta</option><option>Urgente</option></select><label>Descrizione *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="Descrivi il problema nel dettaglio"></textarea><label>Foto (opzionale, massimo 5)</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple><button>➤ Invia segnalazione</button></form></div>''', public=True)


@public_app.post('/r/{token}/unlock')
def unlock(request: Request, token: str, pin: str = Form(...)):
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    client = request.client.host if request.client else 'unknown'
    key = f'{client}:{token}'
    current = time.time()
    attempts = [stamp for stamp in PIN_ATTEMPTS.get(key, []) if current - stamp < PIN_WINDOW_SECONDS]
    if len(attempts) >= PIN_MAX_ATTEMPTS:
        raise HTTPException(429, 'Troppi tentativi. Riprova tra 15 minuti.')
    pin_hash = get_setting('pin_hash')
    try:
        valid = bool(pin_hash and argon2.verify(pin, pin_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        raise HTTPException(403, 'PIN non valido')
    PIN_ATTEMPTS.pop(key, None)
    value = serializer().dumps({'zone': token})
    response = RedirectResponse(f'../{token}', status_code=303)
    response.set_cookie('hm_session', value, max_age=86400, httponly=True, secure=True, samesite='lax')
    return response


@public_app.post('/r/{token}/submit', response_class=HTMLResponse)
async def submit_ticket(request: Request, token: str, reporter_name: str = Form(...), category: str = Form(...), priority: str = Form('Normale'), description: str = Form(...), photos: list[UploadFile] = File(default=[])):
    if not session_zone(request, token):
        raise HTTPException(403, 'Sessione scaduta')
    reporter_name = reporter_name.strip()
    description = description.strip()
    if not reporter_name or not description or len(reporter_name) > 120 or len(description) > 4000:
        raise HTTPException(400, 'Nome e descrizione sono obbligatori')
    allowed_categories = {'Elettrico', 'Idraulico', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro'}
    if category not in allowed_categories or priority not in PRIORITIES:
        raise HTTPException(400, 'Categoria o priorità non valida')
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    if not zone:
        con.close()
        raise HTTPException(404)
    description_it, translation_status = translate_to_italian(description)
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description_it, translation_status, now_iso(), now_iso()))
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
    notify_home_assistant(f'Nuovo ticket {code} · Zona {zone["name"]} · {category} · Priorità {priority}')
    return page('Segnalazione ricevuta', f'''<div class="public-card"><div class="success"><div class="success-mark">✓</div><h1>Segnalazione ricevuta</h1><p>Grazie, la segnalazione è stata registrata.</p><p><b>Ticket:</b> {esc(code)}<br><b>Zona:</b> {esc(zone["name"])}</p></div></div>''', public=True)
