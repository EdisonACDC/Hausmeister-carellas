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
APP_VERSION = '1.1.7'
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
        ('description_de', 'TEXT', None),
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


def translate_text(text: str, target: str):
    options = load_options()
    endpoint = (options.get('translation_url') or '').strip()
    errors = []
    if endpoint:
        try:
            payload = {'q': text, 'source': 'auto', 'target': target, 'format': 'text'}
            api_key = (options.get('translation_api_key') or '').strip()
            if api_key:
                payload['api_key'] = api_key
            request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode())
            translated = (data.get('translatedText') or '').strip()
            if translated:
                delete_setting('translation_error')
                return translated, 'completed'
        except Exception as exc:
            errors.append(f'Servizio configurato: {type(exc).__name__}: {exc}')
    try:
        query = urllib.parse.urlencode({'client': 'gtx', 'sl': 'auto', 'tl': target, 'dt': 't', 'q': text})
        request = urllib.request.Request(f'https://translate.googleapis.com/translate_a/single?{query}', headers={'User-Agent': 'Hausmeister-Carellas/1.1'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode())
        translated = ''.join(part[0] for part in data[0] if part and part[0]).strip()
        if translated:
            delete_setting('translation_error')
            return translated, 'completed'
    except Exception as exc:
        errors.append(f'Google: {type(exc).__name__}: {exc}')
    try:
        lowered = f' {text.lower()} '
        german_words = (' der ', ' die ', ' das ', ' ist ', ' nicht ', ' kaputt', ' defekt', ' wasser', ' ofen', ' kühlschrank', ' tür ', ' licht')
        italian_words = (' il ', ' lo ', ' la ', ' è ', ' non ', ' rotto', ' guasto', ' acqua', ' forno', ' frigorifero', ' porta ', ' luce')
        source = 'de' if any(word in lowered for word in german_words) else ('it' if any(word in lowered for word in italian_words) else 'en')
        if source == target:
            delete_setting('translation_error')
            return text, 'completed'
        query = urllib.parse.urlencode({'q': text, 'langpair': f'{source}|{target}', 'mt': 1})
        request = urllib.request.Request(f'https://api.mymemory.translated.net/get?{query}', headers={'User-Agent': 'Hausmeister-Carellas/1.1'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode())
        translated = (data.get('responseData', {}).get('translatedText') or '').strip()
        if translated:
            delete_setting('translation_error')
            return translated, 'completed'
    except Exception as exc:
        errors.append(f'MyMemory: {type(exc).__name__}: {exc}')
    error = ' | '.join(errors) or 'Nessun servizio di traduzione ha restituito un risultato'
    set_setting('translation_error', error[:1000])
    print(f'Translation error ({target}): {error}', flush=True)
    return None, 'failed'


def public_url_for(zone):
    base = public_base_url()
    return f'{base}/r/{zone["token"]}' if base else f'/r/{zone["token"]}'


def group_token():
    token = get_setting('group_token')
    if not token:
        token = secrets.token_urlsafe(18)
        set_setting('group_token', token)
    return token


def group_public_url():
    base = public_base_url()
    token = group_token()
    return f'{base}/g/{token}' if base else f'/g/{token}'


def public_language(request: Request):
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    return 'de' if preferred.startswith('de') else 'it'


PUBLIC_TEXT = {
    'it': {
        'back': 'Indietro', 'report': 'Segnalazione guasto', 'new_report': 'Nuova segnalazione',
        'selected_zone': 'Zona selezionata', 'zone': 'Zona', 'enter_password': 'Inserisci la password per accedere',
        'password': 'Password di accesso', 'password_placeholder': 'Inserisci password', 'login': 'Accedi',
        'name': 'Nome e cognome', 'name_placeholder': 'Inserisci il tuo nome e cognome',
        'fault_type': 'Tipo di guasto', 'select_category': 'Seleziona la categoria', 'priority': 'Priorità',
        'description': 'Descrizione', 'description_placeholder': 'Descrivi il problema nel dettaglio',
        'photos': 'Foto (opzionale, massimo 5)', 'send': 'Invia segnalazione',
        'all_zones': 'Tutte le zone', 'group_password_help': 'Inserisci la password del QR di gruppo',
        'group_password': 'Password di gruppo', 'choose_zone': 'Scegli la zona',
        'choose_zone_help': 'Seleziona dove vuoi fare la segnalazione', 'no_zones': 'Nessuna zona attiva.',
        'not_configured': 'Servizio non configurato', 'unavailable': 'Servizio non disponibile',
        'configure_password': 'Il responsabile deve configurare la password.',
        'received': 'Segnalazione ricevuta', 'thanks': 'Grazie, la segnalazione è stata registrata.',
        'portal': 'Portale segnalazioni', 'scan_help': 'Per aprire una segnalazione, scansiona il QR della zona.',
    },
    'de': {
        'back': 'Zurück', 'report': 'Störung melden', 'new_report': 'Neue Störungsmeldung',
        'selected_zone': 'Ausgewählter Bereich', 'zone': 'Bereich', 'enter_password': 'Passwort eingeben, um fortzufahren',
        'password': 'Zugangspasswort', 'password_placeholder': 'Passwort eingeben', 'login': 'Anmelden',
        'name': 'Vor- und Nachname', 'name_placeholder': 'Vor- und Nachnamen eingeben',
        'fault_type': 'Art der Störung', 'select_category': 'Kategorie auswählen', 'priority': 'Priorität',
        'description': 'Beschreibung', 'description_placeholder': 'Problem genau beschreiben',
        'photos': 'Fotos (optional, maximal 5)', 'send': 'Störungsmeldung senden',
        'all_zones': 'Alle Bereiche', 'group_password_help': 'Passwort des Gruppen-QR-Codes eingeben',
        'group_password': 'Gruppenpasswort', 'choose_zone': 'Bereich auswählen',
        'choose_zone_help': 'Bereich der Störung auswählen', 'no_zones': 'Keine aktiven Bereiche.',
        'not_configured': 'Dienst nicht konfiguriert', 'unavailable': 'Dienst nicht verfügbar',
        'configure_password': 'Der Verantwortliche muss zuerst das Passwort konfigurieren.',
        'received': 'Störungsmeldung erhalten', 'thanks': 'Vielen Dank. Die Störungsmeldung wurde gespeichert.',
        'portal': 'Störungsmeldungsportal', 'scan_help': 'Zum Melden einer Störung den QR-Code des Bereichs scannen.',
    },
}


def public_text(lang: str, key: str):
    return PUBLIC_TEXT.get(lang, PUBLIC_TEXT['it']).get(key, key)


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


def page(title: str, body: str, public: bool = False, lang: str = 'it'):
    shell_class = 'public-shell' if public else 'admin-shell'
    back = f'<button type="button" class="back-btn" onclick="history.back()">← {public_text(lang, "back") if public else "Indietro"}</button>'
    return f'''<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#6e7d08"><title>{title}</title><style>
:root{{--olive:#6e7d08;--olive-dark:#586406;--cream:#fbfaf5;--ink:#17212b;--muted:#6b7280;--line:#e5e7eb;--danger:#c62828;--card:#fff;--nav:#18252d;--shadow:0 4px 18px #00000012}}
*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:#eef1f2}}
body{{overflow-x:hidden}}button,input,textarea,select{{font:inherit}}a{{color:inherit}}.brand-logo{{width:230px;max-width:100%;margin:0 auto}}.brand-logo svg{{display:block;width:100%;height:auto}}
.page{{min-height:100vh}}.admin-shell{{display:grid;grid-template-columns:245px minmax(0,1fr);min-height:100vh}}.sidebar{{background:var(--nav);color:#fff;padding:18px 14px;position:sticky;top:0;height:100vh}}.sidebar .brand-wrap{{background:#fff;border-radius:15px;padding:10px;margin-bottom:18px}}.side-link{{display:block;text-decoration:none;padding:11px 12px;border-radius:9px;margin:5px 0;color:#f6f7f8}}.side-link.active,.side-link:hover{{background:var(--olive)}}.side-foot{{position:absolute;bottom:18px;left:22px;right:22px;color:#cfd8dc;font-size:12px;text-align:center;border-top:1px solid #ffffff25;padding-top:12px}}
.content{{min-width:0}}.topbar{{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:16px 22px;background:#fff;border-bottom:1px solid var(--line)}}.topbar h1{{font-size:24px;margin:0}}.topbar small{{color:var(--muted)}}.status-dot{{padding:7px 11px;background:#eef7ea;border-radius:999px;color:#2e6c2f;font-size:13px;white-space:nowrap}}main{{padding:18px;max-width:1480px;margin:0 auto;width:100%}}.nav{{display:flex;align-items:center;gap:10px;margin:0 0 12px}}
.card{{background:var(--card);border-radius:16px;padding:18px;box-shadow:var(--shadow);border:1px solid #e9ecef;min-width:0;overflow-wrap:anywhere}}h1,h2,h3{{margin-top:0}}h2{{font-size:20px}}.grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}}.span-3{{grid-column:span 3}}.span-4{{grid-column:span 4}}.span-5{{grid-column:span 5}}.span-6{{grid-column:span 6}}.span-7{{grid-column:span 7}}.span-8{{grid-column:span 8}}.span-12{{grid-column:span 12}}.metric{{display:flex;align-items:center;gap:13px}}.metric-icon{{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;background:#eef1d8;color:var(--olive);font-size:20px}}.metric strong{{font-size:28px;display:block}}.muted{{color:var(--muted);font-size:14px}}.pill{{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2f7;font-size:12px}}.pill.open{{background:#fff2dd;color:#a75d00}}.pill.done{{background:#e8f6e5;color:#2f7c35}}
input,textarea,select{{width:100%;padding:13px 14px;margin:7px 0 15px;border:1px solid #cfd6dc;border-radius:10px;background:#fff;font-size:16px}}textarea{{resize:vertical;min-height:130px}}label{{font-weight:600;font-size:14px}}button,.btn{{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;padding:12px 16px;background:var(--olive);color:#fff;text-decoration:none;font-weight:700;cursor:pointer;min-height:44px}}button:hover,.btn:hover{{background:var(--olive-dark)}}.back-btn{{background:#f1f3f4;color:#263238}}.back-btn:hover{{background:#e5e7e9}}.danger{{background:var(--danger)}}.inline{{display:inline-block;margin:4px 8px 4px 0}}.actions{{display:flex;gap:9px;flex-wrap:wrap}}.table-wrap{{overflow:auto;width:100%;-webkit-overflow-scrolling:touch}}table{{width:100%;border-collapse:collapse;min-width:620px}}th,td{{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}th{{font-size:13px;color:#4b5563}}img.qr{{width:240px;max-width:100%;height:auto}}.zone-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}}.zone-row:last-child{{border-bottom:0}}.photos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.photos a{{display:block}}.photos img{{width:100%;height:160px;object-fit:cover;border-radius:10px;border:1px solid var(--line)}}.notice{{padding:12px;border-radius:10px;background:#eef7ea;margin-bottom:14px}}.warning{{background:#fff3dc}}.filters{{display:grid;grid-template-columns:2fr 1fr auto;gap:8px;align-items:end}}.filters input,.filters select{{margin-bottom:0}}
.public-shell{{min-height:100vh;background:linear-gradient(145deg,#fff 0%,var(--cream) 100%);display:grid;place-items:center;padding:24px}}.public-wrap{{width:min(720px,100%);margin:auto}}.public-brand{{width:300px;max-width:80%;margin:0 auto 12px}}.public-card{{background:#fff;border:1px solid #ebe8dc;border-radius:18px;padding:24px;box-shadow:0 12px 35px #0000000f}}.public-card h1{{text-align:center;margin-bottom:6px}}.public-card>.muted{{text-align:center;display:block;margin-bottom:20px}}.public-card button{{width:100%;background:var(--olive)}}.success{{text-align:center;padding:22px 6px}}.success-mark{{width:64px;height:64px;border-radius:50%;background:#eef7ea;color:#2e7d32;display:grid;place-items:center;margin:0 auto 15px;font-size:34px}}
@media(max-width:1000px){{.admin-shell{{grid-template-columns:1fr}}.sidebar{{height:auto;position:relative;padding:10px 12px;display:flex;align-items:center;gap:8px;overflow-x:auto}}.sidebar .brand-wrap{{min-width:155px;margin:0;padding:5px}}.sidebar .brand-logo{{width:145px}}.side-link{{white-space:nowrap;margin:0}}.side-foot{{display:none}}.span-3{{grid-column:span 6}}.span-4,.span-5,.span-6,.span-7,.span-8{{grid-column:span 12}}}}
@media(max-width:640px){{.topbar{{padding:12px 14px}}.topbar h1{{font-size:20px}}.status-dot{{display:none}}main{{padding:12px}}.grid{{gap:10px}}.span-3,.span-4,.span-5,.span-6,.span-7,.span-8,.span-12{{grid-column:span 12}}.card{{padding:15px;border-radius:14px}}.metric strong{{font-size:24px}}.public-shell{{padding:14px}}.public-card{{padding:18px 15px}}.public-brand{{max-width:88%;width:270px}}.actions button,.actions .btn{{flex:1 1 140px}}.nav{{margin-bottom:8px}}.filters{{grid-template-columns:1fr}}}}
</style><script>function adminGo(path){{const marker='/api/hassio_ingress/';const current=location.pathname;const start=current.indexOf(marker);if(start>=0){{const after=start+marker.length;const slash=current.indexOf('/',after);const base=slash>=0?current.slice(0,slash+1):current+'/';location.href=base+path;}}else{{location.href='/'+path;}}return false;}}</script></head><body><div class="page {shell_class}">'''+(
    f'''<aside class="sidebar"><div class="brand-wrap">{brand_logo()}</div><a class="side-link" href="./" onclick="return adminGo('')">⌂ Dashboard</a><a class="side-link" href="tickets" onclick="return adminGo('tickets')">☷ Ticket</a><a class="side-link" href="zones" onclick="return adminGo('zones')">⌖ Zone / QR</a><a class="side-link" href="settings" onclick="return adminGo('settings')">⚙ Impostazioni</a><div class="side-foot">Hausmeister Carellas<br>v{APP_VERSION}</div></aside><div class="content"><header class="topbar"><div><h1>{esc(title)}</h1><small>Gestione manutenzioni Carellas</small></div><div class="status-dot">● Add-on in esecuzione</div></header><main><div class="nav">{back}</div>{body}</main></div>''' if not public else f'''<div class="public-wrap"><div class="public-brand">{brand_logo()}</div><div class="nav">{back}</div>{body}</div>''')+'''</div></body></html>'''


def session_zone(request: Request, token: str):
    cookie = request.cookies.get('hm_session')
    if not cookie:
        return False
    try:
        data = serializer().loads(cookie, max_age=86400)
        return data.get('zone') == token or data.get('group') == group_token()
    except BadSignature:
        return False


init_db()
admin_app = FastAPI(title='Hausmeister Carellas Admin')
public_app = FastAPI(title='Hausmeister Carellas Public')


@admin_app.middleware('http')
async def admin_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
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
    return page('Dashboard', f'''
    <div class="grid">
      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Totale ticket</span><strong>{total}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Aperti</span><strong>{open_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{work_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">Risolti</span><strong>{done_count}</strong></div></div></div>
      <div class="card span-8"><h2>Ticket recenti</h2><div class="table-wrap"><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Stato</th></tr>{ticket_rows}</table></div><p><a class="btn" href="tickets">Vedi tutti i ticket</a></p></div>
      <div class="card span-4"><h2>Zone</h2>{zone_rows}</div>
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
    rows = con.execute('''SELECT t.ticket_code,z.name,t.reporter_name,t.category,t.priority,t.status,t.description_original,t.description_it,t.description_de,t.resolution_notes,t.created_at,t.updated_at FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC''').fetchall()
    con.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ticket', 'Zona', 'Segnalato da', 'Categoria', 'Priorità', 'Stato', 'Descrizione originale', 'Traduzione IT', 'Übersetzung DE', 'Note', 'Creato', 'Aggiornato'])
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
    message = urllib.parse.quote(f'Zona "{name}" creata correttamente. Ora è già visibile nella lista.')
    return RedirectResponse(f'zones?message={message}&created={zone_id}', status_code=303)


@admin_app.get('/zones', response_class=HTMLResponse)
def zones_page(message: str = '', created: int = 0):
    con = db()
    zones = con.execute('SELECT z.*, COUNT(t.id) ticket_count FROM zones z LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY z.name').fetchall()
    con.close()
    rows = ''.join(f'''<tr{' class="new-zone"' if z['id'] == created else ''}><td><b>{esc(z['name'])}</b></td><td>{'Attiva' if z['active'] else 'Disattivata'}</td><td>{z['ticket_count']}</td><td><a class="btn" href="zone/{z['id']}">Gestisci / QR</a></td></tr>''' for z in zones) or '<tr><td colspan="4">Nessuna zona</td></tr>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Zone / QR', f'''{notice}<style>.new-zone td{{background:#f1f8df}}</style><div class="grid"><div class="card span-8"><h2>Zone esistenti</h2><div class="table-wrap"><table><tr><th>Zona</th><th>Stato</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class="card span-4"><h2>Nuova zona</h2><form method="post" action="zone"><label>Nome</label><input name="name" maxlength="80" required placeholder="Es. Cucina"><button>Crea zona e QR</button></form></div></div>''')


@admin_app.post('/pin')
def save_pin(pin: str = Form(...)):
    pin = pin.strip()
    if len(pin) < 6 or len(pin) > 64:
        raise HTTPException(400, 'La password deve contenere da 6 a 64 caratteri')
    set_setting('pin_hash', argon2.hash(pin))
    set_setting('pin_plain', pin)
    return RedirectResponse('settings', status_code=303)


@admin_app.post('/pin/delete')
def remove_pin():
    delete_setting('pin_hash')
    delete_setting('pin_plain')
    return RedirectResponse('../', status_code=303)


@admin_app.post('/settings/group-pin')
def save_group_pin(pin: str = Form(...)):
    pin = pin.strip()
    if len(pin) < 6 or len(pin) > 64:
        raise HTTPException(400, 'La password di gruppo deve contenere da 6 a 64 caratteri')
    set_setting('group_pin_hash', argon2.hash(pin))
    set_setting('group_pin_plain', pin)
    group_token()
    return RedirectResponse('../settings', status_code=303)


@admin_app.get('/settings', response_class=HTMLResponse)
def settings_page(message: str = ''):
    options = load_options()
    pin_plain = get_setting('pin_plain', '')
    pin_hint = '' if pin_plain else ('La vecchia password è protetta e non recuperabile: salvala nuovamente una sola volta per renderla visibile.' if get_setting('pin_hash') else 'Imposta la password per i QR delle singole zone.')
    group_pin = get_setting('group_pin_plain', '')
    group_url = group_public_url()
    base = options.get('public_base_url') or 'Non configurato'
    notify = options.get('notify_service') or 'Non configurato'
    translation = options.get('translation_url') or 'Automatica integrata (Google con MyMemory di riserva)'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Impostazioni', f'''{notice}<div class="grid"><div class="card span-6"><h2>Password zone singole</h2><p class="muted">Usata dai QR che aprono direttamente una zona.</p><form method="post" action="pin"><label>Password salvata</label><input type="text" name="pin" value="{esc(pin_plain)}" minlength="6" maxlength="64" autocomplete="off" autocapitalize="none" required placeholder="Inserisci nuovamente la password"><button>Salva password zone</button></form>{f'<div class="notice warning">{esc(pin_hint)}</div>' if pin_hint else ''}</div><div class="card span-6"><h2>Password QR di gruppo</h2><p class="muted">È diversa dalla password delle singole zone e permette di scegliere una delle zone attive.</p><form method="post" action="settings/group-pin"><label>Password di gruppo salvata</label><input type="text" name="pin" value="{esc(group_pin)}" minlength="6" maxlength="64" autocomplete="off" autocapitalize="none" required placeholder="Crea la password di gruppo"><button>Salva password di gruppo</button></form></div><div class="card span-6"><h2>QR con tutte le zone</h2><p><a href="{esc(group_url)}" target="_blank">{esc(group_url)}</a></p>{'<img class="qr" src="settings/group-qr">' if group_pin else '<div class="notice warning">Prima salva la password di gruppo.</div>'}<div class="actions" style="margin-top:12px">{f'<a class="btn" href="settings/group-qr?download=1">Scarica QR di gruppo</a>' if group_pin else ''}</div></div><div class="card span-6"><h2>Configurazione</h2><p><b>URL pubblico:</b><br>{esc(base)}</p><p><b>Servizio notifiche:</b><br>{esc(notify)}</p><p><b>Traduzione automatica:</b><br>{esc(translation)}</p><p class="muted">Questi valori si modificano nella scheda Configurazione dell'add-on di Home Assistant.</p><form method="post" action="settings/test-notification"><button>Invia notifica di prova</button></form></div><div class="card span-12"><h2>Backup</h2><p>Scarica database e fotografie in un unico archivio ZIP.</p><a class="btn" href="settings/backup">Scarica backup</a></div></div>''')


@admin_app.get('/settings/group-qr')
def group_qr(download: int = 0):
    if not get_setting('group_pin_hash'):
        raise HTTPException(409, 'Prima configura il PIN di gruppo')
    image = qrcode.make(group_public_url())
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    disposition = 'attachment' if download else 'inline'
    return StreamingResponse(buffer, media_type='image/png', headers={'Content-Disposition': f'{disposition}; filename="qr-tutte-le-zone.png"'})


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
    ticket_count = con.execute('SELECT COUNT(*) n FROM tickets WHERE zone_id=?', (zone_id,)).fetchone()['n']
    con.close()
    if not zone:
        raise HTTPException(404)
    url = public_url_for(zone)
    warning = '' if public_base_url() else '<div class="notice warning"><b>Attenzione:</b> imposta public_base_url nelle opzioni add-on prima di stampare il QR definitivo.</div>'
    active_label = 'Disattiva zona' if zone['active'] else 'Attiva zona'
    delete_message = esc(f'Eliminare definitivamente la zona {zone["name"]}, i suoi {ticket_count} ticket e tutte le foto?')
    return page(zone['name'], f'''<div class="grid"><div class="card span-7"><h2>{esc(zone["name"])}</h2>{warning}<p><a href="{esc(url)}" target="_blank">{esc(url)}</a></p><img class="qr" src="{zone_id}/qr"><div class="actions" style="margin-top:12px"><a class="btn" href="{zone_id}/qr?download=1">Scarica QR</a><button onclick="window.print()">Stampa</button><form method="post" action="{zone_id}/toggle"><button type="submit">{active_label}</button></form><form method="post" action="{zone_id}/regenerate" onsubmit="return confirm('Il vecchio QR smetterà subito di funzionare. Continuare?')"><button class="danger" type="submit">Rigenera QR</button></form></div></div><div class="card span-5"><h2>Modifica zona</h2><form method="post" action="{zone_id}/rename"><label>Nome della zona</label><input name="name" value="{esc(zone['name'])}" maxlength="80" required><button>Salva nome</button></form><hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h2>Elimina zona</h2><p class="muted">Ticket collegati: {ticket_count}. Eliminando la zona saranno eliminati anche i suoi ticket e tutte le fotografie.</p><form method="post" action="{zone_id}/delete" data-confirm="{delete_message}" onsubmit="return confirm(this.dataset.confirm)"><button class="danger">Elimina zona</button></form></div></div>''')


@admin_app.post('/zone/{zone_id}/rename')
def zone_rename(zone_id: int, name: str = Form(...)):
    name = name.strip()
    if not name or len(name) > 80:
        raise HTTPException(400, 'Nome zona non valido')
    con = db()
    con.execute('UPDATE zones SET name=? WHERE id=?', (name, zone_id))
    con.commit()
    con.close()
    return RedirectResponse(f'../{zone_id}', status_code=303)


@admin_app.post('/zone/{zone_id}/delete')
def zone_delete(zone_id: int):
    con = db()
    zone = con.execute('SELECT name FROM zones WHERE id=?', (zone_id,)).fetchone()
    if not zone:
        con.close()
        raise HTTPException(404, 'Zona non trovata')
    files = con.execute('''SELECT f.stored_name FROM ticket_files f JOIN tickets t ON t.id=f.ticket_id WHERE t.zone_id=?''', (zone_id,)).fetchall()
    con.execute('DELETE FROM ticket_files WHERE ticket_id IN (SELECT id FROM tickets WHERE zone_id=?)', (zone_id,))
    con.execute('DELETE FROM tickets WHERE zone_id=?', (zone_id,))
    con.execute('DELETE FROM zones WHERE id=?', (zone_id,))
    con.commit()
    con.close()
    upload_root = UPLOAD_DIR.resolve()
    for row in files:
        path = (UPLOAD_DIR / row['stored_name']).resolve()
        if path.parent == upload_root and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
    return RedirectResponse('../../zones', status_code=303)


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
    translation_error = get_setting('translation_error', '')
    translation_notice = (
        f'<div class="notice warning"><b>Traduzione non riuscita:</b> {esc(translation_error)}</div>'
        if t['translation_status'] == 'failed' and translation_error else ''
    )
    delete_form = ''
    if t['status'] == 'Risolto':
        photo_text = f' e le sue {len(files)} foto' if files else ''
        delete_form = f'''<hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h2>Elimina ticket</h2><p class="muted">Questa operazione libera spazio ma non può essere annullata.</p><form method="post" action="{ticket_id}/delete" onsubmit="return confirm('Eliminare definitivamente il ticket {esc(t['ticket_code'])}{photo_text}?')"><button class="danger" type="submit">Elimina ticket e foto</button></form>'''
    return page(t['ticket_code'], f'''<div class="grid"><div class="card span-7"><h2>{esc(t["ticket_code"])}</h2><p><b>Zona:</b> {esc(t["zone_name"])}</p><p><b>Segnalato da:</b> {esc(t["reporter_name"])}</p><p><b>Categoria:</b> {esc(t["category"])}</p><h3>Descrizione originale</h3><p style="white-space:pre-wrap">{esc(t["description_original"])}</p>{translation_notice}<form method="post" action="{ticket_id}/auto-translate" style="margin-bottom:18px"><button type="submit">Traduci ora in italiano e tedesco</button></form><h3>Traduzione italiana</h3><p style="white-space:pre-wrap">{esc(t["description_it"] or "In attesa")}</p><h3>Traduzione tedesca / Deutsche Übersetzung</h3><p style="white-space:pre-wrap">{esc(t["description_de"] or "In attesa / Ausstehend")}</p><form method="post" action="{ticket_id}/translation"><label>Correggi traduzione italiana</label><textarea name="description_it" maxlength="4000">{esc(t["description_it"] or "")}</textarea><label>Correggi traduzione tedesca / Deutsche Übersetzung</label><textarea name="description_de" maxlength="4000">{esc(t["description_de"] or "")}</textarea><button>Salva correzioni</button></form></div><div class="card span-5"><h2>Gestione</h2><form method="post" action="{ticket_id}/update"><label>Stato</label><select name="status">{status_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Note interne / soluzione</label><textarea name="resolution_notes" maxlength="4000">{esc(t["resolution_notes"] or "")}</textarea><button>Salva modifiche</button></form><h2 style="margin-top:22px">Foto</h2><div class="photos">{photos}</div>{delete_form}</div></div>''')


@admin_app.post('/ticket/{ticket_id}/auto-translate')
def ticket_auto_translate(ticket_id: int):
    con = db()
    ticket = con.execute('SELECT description_original,description_it,description_de FROM tickets WHERE id=?', (ticket_id,)).fetchone()
    if not ticket:
        con.close()
        raise HTTPException(404, 'Ticket non trovato')
    description_it, status_it = translate_text(ticket['description_original'], 'it')
    description_de, status_de = translate_text(ticket['description_original'], 'de')
    description_it = description_it or ticket['description_it']
    description_de = description_de or ticket['description_de']
    state = 'completed' if status_it == 'completed' and status_de == 'completed' else 'failed'
    con.execute('UPDATE tickets SET description_it=?, description_de=?, translation_status=?, updated_at=? WHERE id=?', (description_it, description_de, state, now_iso(), ticket_id))
    con.commit()
    con.close()
    return RedirectResponse(f'../{ticket_id}', status_code=303)


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
def ticket_translation(ticket_id: int, description_it: str = Form(''), description_de: str = Form('')):
    con = db()
    state = 'manual' if description_it.strip() or description_de.strip() else 'pending'
    con.execute('UPDATE tickets SET description_it=?, description_de=?, translation_status=?, updated_at=? WHERE id=?', (description_it.strip() or None, description_de.strip() or None, state, now_iso(), ticket_id))
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
def public_home(request: Request):
    lang = public_language(request)
    return page('Hausmeister Carellas', f'<div class="public-card"><div class="success"><h1>{public_text(lang, "portal")}</h1><p>{public_text(lang, "scan_help")}</p></div></div>', public=True, lang=lang)


@public_app.get('/g/{token}', response_class=HTMLResponse)
def group_form(request: Request, token: str):
    lang = public_language(request)
    if token != group_token():
        raise HTTPException(404, 'Ungültiger Gruppen-QR-Code' if lang == 'de' else 'QR di gruppo non valido')
    if not get_setting('group_pin_hash'):
        return page(public_text(lang, 'not_configured'), f'<div class="public-card"><div class="success"><h1>{public_text(lang, "unavailable")}</h1><p>{public_text(lang, "configure_password")}</p></div></div>', public=True, lang=lang)
    cookie = request.cookies.get('hm_session')
    unlocked = False
    if cookie:
        try:
            unlocked = serializer().loads(cookie, max_age=86400).get('group') == token
        except BadSignature:
            pass
    if not unlocked:
        return page(public_text(lang, 'all_zones'), f'''<div class="public-card"><h1>{public_text(lang, 'all_zones')}</h1><span class="muted">{public_text(lang, 'group_password_help')}</span><form method="post" action="{esc(token)}/unlock"><label>{public_text(lang, 'group_password')}</label><input type="text" name="pin" minlength="6" maxlength="64" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" style="-webkit-text-security:disc" required placeholder="{public_text(lang, 'password_placeholder')}"><button>{public_text(lang, 'login')}</button></form></div>''', public=True, lang=lang)
    con = db()
    zones = con.execute('SELECT * FROM zones WHERE active=1 ORDER BY name').fetchall()
    con.close()
    buttons = ''.join(f'<a class="btn" style="width:100%;margin:6px 0" href="../../r/{esc(zone["token"])}">{esc(zone["name"])}</a>' for zone in zones) or f'<p class="muted">{public_text(lang, "no_zones")}</p>'
    return page(public_text(lang, 'choose_zone'), f'''<div class="public-card"><h1>{public_text(lang, 'choose_zone')}</h1><span class="muted">{public_text(lang, 'choose_zone_help')}</span>{buttons}</div>''', public=True, lang=lang)


@public_app.post('/g/{token}/unlock')
def group_unlock(request: Request, token: str, pin: str = Form(...)):
    lang = public_language(request)
    if token != group_token():
        raise HTTPException(404)
    client = request.headers.get('x-forwarded-for', '').split(',')[0].strip() or (request.client.host if request.client else 'unknown')
    key = f'{client}:group:{token}'
    current = time.time()
    attempts = [stamp for stamp in PIN_ATTEMPTS.get(key, []) if current - stamp < PIN_WINDOW_SECONDS]
    if len(attempts) >= PIN_MAX_ATTEMPTS:
        raise HTTPException(429, 'Zu viele Versuche. In 15 Minuten erneut versuchen.' if lang == 'de' else 'Troppi tentativi. Riprova tra 15 minuti.')
    pin_hash = get_setting('group_pin_hash')
    try:
        valid = bool(pin_hash and argon2.verify(pin, pin_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        raise HTTPException(403, 'Ungültiges Gruppenpasswort' if lang == 'de' else 'Password di gruppo non valida')
    PIN_ATTEMPTS.pop(key, None)
    response = RedirectResponse(f'../{token}', status_code=303)
    response.set_cookie('hm_session', serializer().dumps({'group': token}), max_age=86400, httponly=True, secure=True, samesite='lax')
    return response


@public_app.get('/r/{token}', response_class=HTMLResponse)
def report_form(request: Request, token: str):
    lang = public_language(request)
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Ungültiger Bereich' if lang == 'de' else 'Zona non valida')
    if not get_setting('pin_hash'):
        return page(public_text(lang, 'not_configured'), f'<div class="public-card"><div class="success"><h1>{public_text(lang, "unavailable")}</h1><p>{public_text(lang, "configure_password")}</p></div></div>', public=True, lang=lang)
    if not session_zone(request, token):
        return page(public_text(lang, 'report'), f'''<div class="public-card"><h1>{public_text(lang, 'report')}</h1><span class="muted">{public_text(lang, 'zone')}: <b>{esc(zone["name"])}</b> · {public_text(lang, 'enter_password')}</span><form method="post" action="{esc(token)}/unlock"><label>{public_text(lang, 'password')}</label><input type="text" name="pin" minlength="6" maxlength="64" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" style="-webkit-text-security:disc" placeholder="{public_text(lang, 'password_placeholder')}" required><button>{public_text(lang, 'login')}</button></form></div>''', public=True, lang=lang)
    categories = (
        (('Elettrico', 'Elektrik'), ('Idraulico', 'Sanitär / Wasser'), ('Climatizzazione', 'Klimaanlage'), ('Porta/Finestra', 'Tür / Fenster'), ('Attrezzatura cucina', 'Küchengerät'), ('Altro', 'Sonstiges'))
        if lang == 'de' else
        (('Elettrico', 'Elettrico'), ('Idraulico', 'Idraulico'), ('Climatizzazione', 'Climatizzazione'), ('Porta/Finestra', 'Porta / Finestra'), ('Attrezzatura cucina', 'Attrezzatura cucina'), ('Altro', 'Altro'))
    )
    priorities = (
        (('Normale', 'Normal'), ('Bassa', 'Niedrig'), ('Alta', 'Hoch'), ('Urgente', 'Dringend'))
        if lang == 'de' else
        (('Normale', 'Normale'), ('Bassa', 'Bassa'), ('Alta', 'Alta'), ('Urgente', 'Urgente'))
    )
    category_options = ''.join(f'<option value="{esc(value)}">{esc(label)}</option>' for value, label in categories)
    priority_options = ''.join(f'<option value="{esc(value)}">{esc(label)}</option>' for value, label in priorities)
    return page(public_text(lang, 'new_report'), f'''<div class="public-card"><h1>{public_text(lang, 'new_report')}</h1><span class="muted">{public_text(lang, 'selected_zone')}: <b>{esc(zone["name"])}</b></span><form method="post" enctype="multipart/form-data" action="{esc(token)}/submit"><label>{public_text(lang, 'name')} *</label><input name="reporter_name" maxlength="120" required placeholder="{public_text(lang, 'name_placeholder')}"><label>{public_text(lang, 'fault_type')} *</label><select name="category" required><option value="">{public_text(lang, 'select_category')}</option>{category_options}</select><label>{public_text(lang, 'priority')}</label><select name="priority">{priority_options}</select><label>{public_text(lang, 'description')} *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="{public_text(lang, 'description_placeholder')}"></textarea><label>{public_text(lang, 'photos')}</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple><button>➤ {public_text(lang, 'send')}</button></form></div>''', public=True, lang=lang)


@public_app.post('/r/{token}/unlock')
def unlock(request: Request, token: str, pin: str = Form(...)):
    lang = public_language(request)
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
        raise HTTPException(429, 'Zu viele Versuche. In 15 Minuten erneut versuchen.' if lang == 'de' else 'Troppi tentativi. Riprova tra 15 minuti.')
    pin_hash = get_setting('pin_hash')
    try:
        valid = bool(pin_hash and argon2.verify(pin, pin_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        raise HTTPException(403, 'Ungültiges Passwort' if lang == 'de' else 'Password non valida')
    PIN_ATTEMPTS.pop(key, None)
    value = serializer().dumps({'zone': token})
    response = RedirectResponse(f'../{token}', status_code=303)
    response.set_cookie('hm_session', value, max_age=86400, httponly=True, secure=True, samesite='lax')
    return response


@public_app.post('/r/{token}/submit', response_class=HTMLResponse)
async def submit_ticket(request: Request, token: str, reporter_name: str = Form(...), category: str = Form(...), priority: str = Form('Normale'), description: str = Form(...), photos: list[UploadFile] = File(default=[])):
    lang = public_language(request)
    if not session_zone(request, token):
        raise HTTPException(403, 'Sitzung abgelaufen' if lang == 'de' else 'Sessione scaduta')
    reporter_name = reporter_name.strip()
    description = description.strip()
    if not reporter_name or not description or len(reporter_name) > 120 or len(description) > 4000:
        raise HTTPException(400, 'Name und Beschreibung sind erforderlich' if lang == 'de' else 'Nome e descrizione sono obbligatori')
    allowed_categories = {'Elettrico', 'Idraulico', 'Climatizzazione', 'Porta/Finestra', 'Attrezzatura cucina', 'Altro'}
    if category not in allowed_categories or priority not in PRIORITIES:
        raise HTTPException(400, 'Ungültige Kategorie oder Priorität' if lang == 'de' else 'Categoria o priorità non valida')
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    if not zone:
        con.close()
        raise HTTPException(404)
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
    notify_home_assistant(f'Nuovo ticket {code} · Zona {zone["name"]} · {category} · Priorità {priority}')
    return page(public_text(lang, 'received'), f'''<div class="public-card"><div class="success"><div class="success-mark">✓</div><h1>{public_text(lang, 'received')}</h1><p>{public_text(lang, 'thanks')}</p><p><b>Ticket:</b> {esc(code)}<br><b>{public_text(lang, 'zone')}:</b> {esc(zone["name"])}</p></div></div>''', public=True, lang=lang)
