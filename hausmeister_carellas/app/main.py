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
APP_VERSION = '1.3.3'
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


def normalize_notify_service(service: str):
    service = (service or '').strip().removeprefix('notify.')
    if service == 'iphone_marius':
        service = 'mobile_app_iphone_marius'
    return service


def save_notification_devices(devices):
    set_setting('notification_devices', json.dumps(devices, ensure_ascii=False))


def notification_devices():
    raw = get_setting('notification_devices', '')
    if raw:
        try:
            devices = json.loads(raw)
            if isinstance(devices, list):
                return devices
        except (TypeError, ValueError):
            pass
    service = normalize_notify_service(load_options().get('notify_service') or 'mobile_app_iphone_marius')
    devices = [{'id': secrets.token_hex(6), 'name': 'iPhone Marius', 'service': service, 'enabled': True}]
    save_notification_devices(devices)
    return devices


def discover_mobile_app_services():
    token = __import__('os').environ.get('SUPERVISOR_TOKEN', '')
    if not token:
        return [], 'Token Supervisor non disponibile'
    request = urllib.request.Request(
        'http://supervisor/core/api/services',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode())
        services = set()
        for domain in payload if isinstance(payload, list) else []:
            if not isinstance(domain, dict) or domain.get('domain') != 'notify':
                continue
            definitions = domain.get('services') or {}
            if not isinstance(definitions, dict):
                continue
            for service in definitions:
                service = normalize_notify_service(service)
                if service.startswith('mobile_app_'):
                    services.add(service)
        return sorted(services), ''
    except urllib.error.HTTPError as exc:
        return [], f'Home Assistant ha risposto con errore HTTP {exc.code}'
    except Exception as exc:
        return [], f'Impossibile leggere i dispositivi: {type(exc).__name__}: {exc}'


def mobile_device_name(service: str):
    words = service.removeprefix('mobile_app_').replace('_', ' ').split()
    return ' '.join(word.upper() if word.lower() in {'ios', 'ipad'} else word.capitalize() for word in words) or 'Dispositivo mobile'


def notify_device(service: str, message: str, title: str = 'Hausmeister Carellas', url: str = ''):
    service = normalize_notify_service(service)
    token = __import__('os').environ.get('SUPERVISOR_TOKEN', '')
    if not service or not token:
        return False, 'Servizio di notifica non configurato'
    payload = {'title': title, 'message': message}
    if url:
        payload['data'] = {'url': url}
    request = urllib.request.Request(
        f'http://supervisor/core/api/services/notify/{service}',
        data=json.dumps(payload).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300, 'Notifica inviata'
    except Exception as exc:
        return False, f'Errore notifica: {exc}'


def notify_home_assistant(message: str, title: str = 'Hausmeister Carellas', url: str = ''):
    enabled = [device for device in notification_devices() if device.get('enabled', True)]
    if not enabled:
        return False, 'Nessun dispositivo attivo'
    failures = []
    sent = 0
    for device in enabled:
        ok, result = notify_device(device.get('service', ''), message, title, url)
        if ok:
            sent += 1
        else:
            failures.append(f'{device.get("name", "Dispositivo")}: {result}')
    if failures:
        return False, f'Inviate {sent}/{len(enabled)} notifiche. ' + ' | '.join(failures)
    return True, f'Notifica inviata a {sent} dispositivi'


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


def ticket_notification_url(ticket_id: int):
    base = public_base_url()
    if not base:
        return ''
    token = serializer().dumps({'ticket': ticket_id, 'purpose': 'notification'})
    return f'{base}/n/{urllib.parse.quote(token, safe="")}'


def notification_ticket_id(signed_token: str):
    try:
        payload = serializer().loads(signed_token, max_age=90 * 86400)
        if payload.get('purpose') != 'notification':
            raise BadSignature('Invalid purpose')
        return int(payload['ticket'])
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(403, 'Collegamento non valido o scaduto')


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


def ticket_priority_class(ticket):
    if ticket['status'] == 'Risolto':
        return ''
    if ticket['priority'] == 'Urgente':
        return 'priority-urgent'
    if ticket['priority'] == 'Alta':
        return 'priority-high'
    return ''


def priority_dot(ticket):
    if ticket_priority_class(ticket):
        return '<span class="priority-dot" title="Priorità alta o urgente" aria-label="Priorità alta o urgente"></span>'
    return ''


MANAGER_TEXT = {
    'it': {
        'portal': 'Portale titolare', 'login': 'Accesso titolare', 'username': 'Nome utente',
        'password': 'Password', 'enter': 'Accedi', 'logout': 'Esci', 'tickets': 'Ticket',
        'no_tickets': 'Nessun ticket presente', 'zone': 'Zona', 'reporter': 'Segnalato da',
        'category': 'Categoria', 'priority': 'Priorità', 'status': 'Stato', 'original': 'Descrizione originale',
        'italian': 'Traduzione italiana', 'german': 'Traduzione tedesca', 'notes': 'Note interne / soluzione',
        'photos': 'Foto', 'no_photos': 'Nessuna foto', 'save': 'Salva modifiche', 'delete': 'Elimina ticket e foto',
        'invalid': 'Nome utente o password non validi', 'locked': 'Troppi tentativi. Riprova tra 15 minuti.',
        'disabled': 'Il Portale Titolare non è ancora stato attivato.', 'updated': 'Ticket aggiornato correttamente.',
        'dashboard': 'Dashboard', 'zones': 'Zone / QR', 'settings': 'Impostazioni',
        'total': 'Totale ticket', 'open': 'Aperti', 'working': 'In lavorazione', 'resolved': 'Risolti',
        'recent': 'Ticket recenti', 'all_tickets': 'Vedi tutti i ticket', 'active': 'Attiva',
        'inactive': 'Disattivata', 'no_zones': 'Nessuna zona', 'search': 'Cerca',
        'search_hint': 'Codice, zona, nome o descrizione', 'all_statuses': 'Tutti gli stati',
        'existing_zones': 'Zone esistenti', 'manage_qr': 'Gestisci / QR', 'new_zone': 'Nuova zona',
        'name': 'Nome', 'create_zone': 'Crea zona e QR', 'download_qr': 'Scarica QR', 'print': 'Stampa',
        'disable_zone': 'Disattiva zona', 'enable_zone': 'Attiva zona', 'regenerate_qr': 'Rigenera QR',
        'edit_zone': 'Modifica zona', 'zone_name': 'Nome della zona', 'save_name': 'Salva nome',
        'delete_zone': 'Elimina zona', 'linked_tickets': 'Ticket collegati',
        'delete_zone_help': 'Eliminando la zona saranno eliminati anche i suoi ticket e tutte le fotografie.',
        'admin_only': "Riservato all'amministratore",
    },
    'de': {
        'portal': 'Inhaberportal', 'login': 'Anmeldung für den Inhaber', 'username': 'Benutzername',
        'password': 'Passwort', 'enter': 'Anmelden', 'logout': 'Abmelden', 'tickets': 'Tickets',
        'no_tickets': 'Keine Tickets vorhanden', 'zone': 'Bereich', 'reporter': 'Gemeldet von',
        'category': 'Kategorie', 'priority': 'Priorität', 'status': 'Status', 'original': 'Originalbeschreibung',
        'italian': 'Italienische Übersetzung', 'german': 'Deutsche Übersetzung', 'notes': 'Interne Notizen / Lösung',
        'photos': 'Fotos', 'no_photos': 'Keine Fotos', 'save': 'Änderungen speichern', 'delete': 'Ticket und Fotos löschen',
        'invalid': 'Benutzername oder Passwort ungültig', 'locked': 'Zu viele Versuche. In 15 Minuten erneut versuchen.',
        'disabled': 'Das Inhaberportal wurde noch nicht aktiviert.', 'updated': 'Ticket erfolgreich aktualisiert.',
        'dashboard': 'Dashboard', 'zones': 'Bereiche / QR', 'settings': 'Einstellungen',
        'total': 'Tickets gesamt', 'open': 'Offen', 'working': 'In Bearbeitung', 'resolved': 'Erledigt',
        'recent': 'Aktuelle Tickets', 'all_tickets': 'Alle Tickets anzeigen', 'active': 'Aktiv',
        'inactive': 'Deaktiviert', 'no_zones': 'Keine Bereiche', 'search': 'Suchen',
        'search_hint': 'Code, Bereich, Name oder Beschreibung', 'all_statuses': 'Alle Status',
        'existing_zones': 'Vorhandene Bereiche', 'manage_qr': 'Verwalten / QR', 'new_zone': 'Neuer Bereich',
        'name': 'Name', 'create_zone': 'Bereich und QR erstellen', 'download_qr': 'QR herunterladen', 'print': 'Drucken',
        'disable_zone': 'Bereich deaktivieren', 'enable_zone': 'Bereich aktivieren', 'regenerate_qr': 'QR neu erzeugen',
        'edit_zone': 'Bereich bearbeiten', 'zone_name': 'Name des Bereichs', 'save_name': 'Name speichern',
        'delete_zone': 'Bereich löschen', 'linked_tickets': 'Verknüpfte Tickets',
        'delete_zone_help': 'Beim Löschen des Bereichs werden auch seine Tickets und alle Fotos gelöscht.',
        'admin_only': 'Nur für den Administrator',
    },
}


def manager_text(lang: str, key: str):
    return MANAGER_TEXT.get(lang, MANAGER_TEXT['it']).get(key, key)


def manager_status_text(lang: str, value: str):
    if lang != 'de':
        return value
    return {'Nuovo': 'Neu', 'Preso in carico': 'Übernommen', 'In lavorazione': 'In Bearbeitung', 'Da verificare': 'Zu prüfen', 'Risolto': 'Erledigt'}.get(value, value)


def manager_priority_text(lang: str, value: str):
    if lang != 'de':
        return value
    return {'Bassa': 'Niedrig', 'Normale': 'Normal', 'Alta': 'Hoch', 'Urgente': 'Dringend'}.get(value, value)


def manager_category_text(lang: str, value: str):
    if lang != 'de':
        return value
    return {'Elettrico': 'Elektrik', 'Idraulico': 'Sanitär / Wasser', 'Climatizzazione': 'Klimaanlage', 'Porta/Finestra': 'Tür / Fenster', 'Attrezzatura cucina': 'Küchengerät', 'Altro': 'Sonstiges'}.get(value, value)


def manager_portal_url():
    base = public_base_url()
    return f'{base}/manager/login' if base else '/manager/login'


def manager_session_valid(request: Request):
    if get_setting('manager_enabled', '0') != '1':
        return False
    cookie = request.cookies.get('hm_manager_session')
    if not cookie:
        return False
    try:
        data = serializer().loads(cookie, max_age=12 * 3600)
        return (
            data.get('purpose') == 'manager'
            and data.get('username') == get_setting('manager_username', '')
            and data.get('version') == get_setting('manager_session_version', '')
        )
    except BadSignature:
        return False


def delete_resolved_ticket(ticket_id: int):
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
    return ticket['ticket_code'], deleted_photos


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


def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):
    shell_class = 'admin-shell' if manager else ('public-shell' if public else 'admin-shell')
    back_label = public_text(lang, 'back') if public or manager else 'Indietro'
    if (public or manager) and back_url:
        back = f'<a class="btn back-btn" href="{esc(back_url)}">← {back_label}</a>'
    elif manager:
        back = ''
    elif public and close_on_back:
        back = f'<button type="button" class="back-btn" onclick="closePublicPage()">← {back_label}</button>'
    else:
        back = f'<button type="button" class="back-btn" onclick="history.back()">← {back_label}</button>'
    return f'''<!doctype html><html lang="{esc(lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#6e7d08"><title>{title}</title><style>
:root{{--olive:#6e7d08;--olive-dark:#586406;--cream:#fbfaf5;--ink:#17212b;--muted:#6b7280;--line:#e5e7eb;--danger:#c62828;--card:#fff;--nav:#18252d;--shadow:0 4px 18px #00000012}}
*{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:#eef1f2}}
body{{overflow-x:hidden}}button,input,textarea,select{{font:inherit}}a{{color:inherit}}.brand-logo{{width:230px;max-width:100%;margin:0 auto}}.brand-logo svg{{display:block;width:100%;height:auto}}
.page{{min-height:100vh}}.admin-shell{{display:grid;grid-template-columns:245px minmax(0,1fr);min-height:100vh}}.sidebar{{background:var(--nav);color:#fff;padding:18px 14px;position:sticky;top:0;height:100vh}}.sidebar .brand-wrap{{background:#fff;border-radius:15px;padding:10px;margin-bottom:18px}}.side-link{{display:block;text-decoration:none;padding:11px 12px;border-radius:9px;margin:5px 0;color:#f6f7f8}}.side-link.active,.side-link:hover{{background:var(--olive)}}.side-link.disabled{{opacity:.42;cursor:not-allowed;pointer-events:none}}.side-foot{{position:absolute;bottom:18px;left:22px;right:22px;color:#cfd8dc;font-size:12px;text-align:center;border-top:1px solid #ffffff25;padding-top:12px}}
.content{{min-width:0}}.topbar{{display:flex;align-items:center;justify-content:space-between;gap:15px;padding:16px 22px;background:#fff;border-bottom:1px solid var(--line)}}.topbar h1{{font-size:24px;margin:0}}.topbar small{{color:var(--muted)}}.status-dot{{padding:7px 11px;background:#eef7ea;border-radius:999px;color:#2e6c2f;font-size:13px;white-space:nowrap}}main{{padding:18px;max-width:1480px;margin:0 auto;width:100%}}.nav{{display:flex;align-items:center;gap:10px;margin:0 0 12px}}
.card{{background:var(--card);border-radius:16px;padding:18px;box-shadow:var(--shadow);border:1px solid #e9ecef;min-width:0;overflow-wrap:anywhere}}h1,h2,h3{{margin-top:0}}h2{{font-size:20px}}.grid{{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}}.span-3{{grid-column:span 3}}.span-4{{grid-column:span 4}}.span-5{{grid-column:span 5}}.span-6{{grid-column:span 6}}.span-7{{grid-column:span 7}}.span-8{{grid-column:span 8}}.span-12{{grid-column:span 12}}.metric{{display:flex;align-items:center;gap:13px}}.metric-icon{{width:44px;height:44px;border-radius:50%;display:grid;place-items:center;background:#eef1d8;color:var(--olive);font-size:20px}}.metric strong{{font-size:28px;display:block}}.muted{{color:var(--muted);font-size:14px}}.pill{{display:inline-block;padding:4px 9px;border-radius:999px;background:#eef2f7;font-size:12px}}.pill.open{{background:#fff2dd;color:#a75d00}}.pill.done{{background:#e8f6e5;color:#2f7c35}}.priority-dot{{display:inline-block;width:13px;height:13px;border-radius:50%;background:#f44336;box-shadow:0 0 0 4px #f4433630;margin-right:9px;vertical-align:-1px}}.priority-high td{{background:#ffebee}}.priority-high td:first-child{{box-shadow:inset 6px 0 #d32f2f}}.priority-urgent td{{background:#c62828;color:#fff;border-color:#e57373}}.priority-urgent a{{color:#fff}}.priority-urgent .pill{{background:#fff;color:#a91515}}.priority-urgent .priority-dot{{background:#fff;box-shadow:0 0 0 4px #ffffff45}}.priority-alert{{background:#c62828;color:#fff;padding:14px 16px;border-radius:12px;margin-bottom:14px;font-weight:800;font-size:17px}}
input,textarea,select{{width:100%;padding:13px 14px;margin:7px 0 15px;border:1px solid #cfd6dc;border-radius:10px;background:#fff;font-size:16px}}textarea{{resize:vertical;min-height:130px}}label{{font-weight:600;font-size:14px}}button,.btn{{display:inline-flex;align-items:center;justify-content:center;gap:7px;border:0;border-radius:10px;padding:12px 16px;background:var(--olive);color:#fff;text-decoration:none;font-weight:700;cursor:pointer;min-height:44px}}button:hover,.btn:hover{{background:var(--olive-dark)}}.back-btn{{background:#f1f3f4;color:#263238}}.back-btn:hover{{background:#e5e7e9}}.danger{{background:var(--danger)}}.inline{{display:inline-block;margin:4px 8px 4px 0}}.actions{{display:flex;gap:9px;flex-wrap:wrap}}.table-wrap{{overflow:auto;width:100%;-webkit-overflow-scrolling:touch}}table{{width:100%;border-collapse:collapse;min-width:620px}}th,td{{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);vertical-align:middle}}th{{font-size:13px;color:#4b5563}}img.qr{{width:240px;max-width:100%;height:auto}}.zone-row{{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}}.zone-row:last-child{{border-bottom:0}}.photos{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.photos a{{display:block}}.photos img{{width:100%;height:160px;object-fit:cover;border-radius:10px;border:1px solid var(--line)}}.notice{{padding:12px;border-radius:10px;background:#eef7ea;margin-bottom:14px}}.warning{{background:#fff3dc}}.filters{{display:grid;grid-template-columns:2fr 1fr auto;gap:8px;align-items:end}}.filters input,.filters select{{margin-bottom:0}}
.public-shell{{min-height:100vh;background:linear-gradient(145deg,#fff 0%,var(--cream) 100%);display:grid;place-items:center;padding:24px}}.public-wrap{{width:min(720px,100%);margin:auto}}.public-brand{{width:300px;max-width:80%;margin:0 auto 12px}}.public-card{{background:#fff;border:1px solid #ebe8dc;border-radius:18px;padding:24px;box-shadow:0 12px 35px #0000000f}}.public-card h1{{text-align:center;margin-bottom:6px}}.public-card>.muted{{text-align:center;display:block;margin-bottom:20px}}.public-card button{{width:100%;background:var(--olive)}}.success{{text-align:center;padding:22px 6px}}.success-mark{{width:64px;height:64px;border-radius:50%;background:#eef7ea;color:#2e7d32;display:grid;place-items:center;margin:0 auto 15px;font-size:34px}}.qr-size-picker{{width:auto;min-width:150px;margin:0;padding:11px 12px}}
@media print{{@page{{margin:10mm}}body.qr-printing{{background:#fff}}body.qr-printing *{{visibility:hidden!important}}body.qr-printing img.qr{{visibility:visible!important;position:fixed;left:10mm;top:10mm;width:var(--qr-print-size,10cm)!important;height:var(--qr-print-size,10cm)!important;max-width:none!important;object-fit:contain}}}}
@media(max-width:1000px){{.admin-shell{{grid-template-columns:1fr}}.sidebar{{height:auto;position:relative;padding:10px 12px;display:flex;align-items:center;gap:8px;overflow-x:auto}}.sidebar .brand-wrap{{min-width:155px;margin:0;padding:5px}}.sidebar .brand-logo{{width:145px}}.side-link{{white-space:nowrap;margin:0}}.side-foot{{display:none}}.span-3{{grid-column:span 6}}.span-4,.span-5,.span-6,.span-7,.span-8{{grid-column:span 12}}}}
@media(max-width:640px){{.topbar{{padding:12px 14px}}.topbar h1{{font-size:20px}}.status-dot{{display:none}}main{{padding:12px}}.grid{{gap:10px}}.span-3,.span-4,.span-5,.span-6,.span-7,.span-8,.span-12{{grid-column:span 12}}.card{{padding:15px;border-radius:14px}}.metric strong{{font-size:24px}}.public-shell{{padding:14px}}.public-card{{padding:18px 15px}}.public-brand{{max-width:88%;width:270px}}.actions button,.actions .btn{{flex:1 1 140px}}.nav{{margin-bottom:8px}}.filters{{grid-template-columns:1fr}}}}
</style><script>function adminGo(path){{const marker='/api/hassio_ingress/';const current=location.pathname;const start=current.indexOf(marker);if(start>=0){{const after=start+marker.length;const slash=current.indexOf('/',after);const base=slash>=0?current.slice(0,slash+1):current+'/';location.href=base+path;}}else{{location.href='/'+path;}}return false;}}function closePublicPage(){{window.close();setTimeout(function(){{if(!document.hidden&&history.length>1)history.back();}},180);}}function setupQrPrinting(){{document.querySelectorAll('button[onclick="window.print()"]') .forEach(function(button){{const german=document.documentElement.lang.toLowerCase().startsWith('de');const select=document.createElement('select');select.className='qr-size-picker';select.setAttribute('aria-label',german?'QR-Größe':'Dimensione QR');[[5,german?'5 cm (Minimum)':'5 cm (minimo)'],[7,'7 cm'],[10,'10 cm'],[12,'12 cm'],[15,'15 cm']].forEach(function(item){{const option=document.createElement('option');option.value=item[0];option.textContent=item[1];if(item[0]===10)option.selected=true;select.appendChild(option);}});button.parentNode.insertBefore(select,button);button.onclick=function(){{const size=Math.max(5,Math.min(15,Number(select.value)||10));document.documentElement.style.setProperty('--qr-print-size',size+'cm');document.body.classList.add('qr-printing');window.print();}};}});window.addEventListener('afterprint',function(){{document.body.classList.remove('qr-printing');}});}}document.addEventListener('DOMContentLoaded',setupQrPrinting);</script></head><body><div class="page {shell_class}">'''+(
    f'''<aside class="sidebar"><div class="brand-wrap">{brand_logo()}</div><a class="side-link" href="/manager">⌂ {manager_text(lang, 'dashboard')}</a><a class="side-link" href="/manager/tickets">☷ {manager_text(lang, 'tickets')}</a><a class="side-link" href="/manager/zones">⌖ {manager_text(lang, 'zones')}</a><span class="side-link disabled" aria-disabled="true" title="{manager_text(lang, 'admin_only')}">⚙ {manager_text(lang, 'settings')}</span><a class="side-link" href="/manager/logout">⇥ {manager_text(lang, 'logout')}</a><div class="side-foot">{manager_text(lang, 'portal')}<br>v{APP_VERSION}</div></aside><div class="content"><header class="topbar"><div><h1>{esc(title)}</h1><small>Carellas Ristorante</small></div><div class="status-dot">● {manager_text(lang, 'portal')}</div></header><main><div class="nav">{back}</div>{body}</main></div>''' if manager else f'''<aside class="sidebar"><div class="brand-wrap">{brand_logo()}</div><a class="side-link" href="./" onclick="return adminGo('')">⌂ Dashboard</a><a class="side-link" href="tickets" onclick="return adminGo('tickets')">☷ Ticket</a><a class="side-link" href="zones" onclick="return adminGo('zones')">⌖ Zone / QR</a><a class="side-link" href="settings" onclick="return adminGo('settings')">⚙ Impostazioni</a><div class="side-foot">Hausmeister Carellas<br>v{APP_VERSION}</div></aside><div class="content"><header class="topbar"><div><h1>{esc(title)}</h1><small>Gestione manutenzioni Carellas</small></div><div class="status-dot">● Add-on in esecuzione</div></header><main><div class="nav">{back}</div>{body}</main></div>''' if not public else f'''<div class="public-wrap"><div class="public-brand">{brand_logo()}</div><div class="nav">{back}</div>{body}</div>''')+'''</div></body></html>'''


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
    if request.url.path.startswith('/manager') or request.url.path.startswith('/n/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
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
    ticket_rows = ''.join(f'<tr class="{ticket_priority_class(t)}"><td><a href="ticket/{t["id"]}"><b>{esc(t["ticket_code"])}</b></a></td><td>{esc(t["zone_name"])}</td><td>{esc(t["reporter_name"])}</td><td>{priority_dot(t)}<b>{esc(t["priority"] or "Normale")}</b></td><td><span class="pill {"done" if t["status"] == "Risolto" else "open"}">{esc(t["status"])}</span></td></tr>' for t in tickets) or '<tr><td colspan="5">Nessun ticket</td></tr>'
    return page('Dashboard', f'''
    <div class="grid">
      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Totale ticket</span><strong>{total}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Aperti</span><strong>{open_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{work_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">Risolti</span><strong>{done_count}</strong></div></div></div>
      <div class="card span-8"><h2>Ticket recenti</h2><div class="table-wrap"><table><tr><th>ID</th><th>Zona</th><th>Segnalato da</th><th>Priorità</th><th>Stato</th></tr>{ticket_rows}</table></div><p><a class="btn" href="tickets">Vedi tutti i ticket</a></p></div>
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
    rows = ''.join(f'''<tr class="{ticket_priority_class(t)}"><td><a href="ticket/{t['id']}"><b>{esc(t['ticket_code'])}</b></a></td><td>{esc(t['zone_name'])}</td><td>{esc(t['reporter_name'])}</td><td>{esc(t['category'])}</td><td>{priority_dot(t)}<b>{esc(t['priority'] or 'Normale')}</b></td><td><span class="pill {'done' if t['status'] == 'Risolto' else 'open'}">{esc(t['status'])}</span></td></tr>''' for t in tickets) or '<tr><td colspan="6">Nessun ticket trovato</td></tr>'
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


@admin_app.post('/settings/manager')
def save_manager_account(username: str = Form(...), password: str = Form(''), enabled: str = Form('')):
    username = username.strip()
    password = password.strip()
    if len(username) < 3 or len(username) > 80:
        return RedirectResponse('../settings?message=' + urllib.parse.quote('Il nome utente deve contenere da 3 a 80 caratteri.'), status_code=303)
    if password and (len(password) < 8 or len(password) > 128):
        return RedirectResponse('../settings?message=' + urllib.parse.quote('La password deve contenere da 8 a 128 caratteri.'), status_code=303)
    if not password and not get_setting('manager_password_hash'):
        return RedirectResponse('../settings?message=' + urllib.parse.quote('Inserisci una password per il titolare.'), status_code=303)
    set_setting('manager_username', username)
    if password:
        set_setting('manager_password_hash', argon2.hash(password))
    set_setting('manager_enabled', '1' if enabled == '1' else '0')
    set_setting('manager_session_version', secrets.token_urlsafe(18))
    return RedirectResponse('../settings?message=' + urllib.parse.quote('Accesso del titolare aggiornato correttamente.'), status_code=303)


@admin_app.get('/settings', response_class=HTMLResponse)
def settings_page(message: str = ''):
    options = load_options()
    pin_plain = get_setting('pin_plain', '')
    pin_hint = '' if pin_plain else ('La vecchia password è protetta e non recuperabile: salvala nuovamente una sola volta per renderla visibile.' if get_setting('pin_hash') else 'Imposta la password per i QR delle singole zone.')
    group_pin = get_setting('group_pin_plain', '')
    group_url = group_public_url()
    base = options.get('public_base_url') or 'Non configurato'
    devices = notification_devices()
    device_cards = ''
    for device in devices:
        device_id = esc(device.get('id', ''))
        checked = 'checked' if device.get('enabled', True) else ''
        device_cards += f'''<div class="card span-6"><h3>{esc(device.get('name') or 'Dispositivo')}</h3><form method="post" action="settings/device/{device_id}/update"><label>Nome dispositivo</label><input name="name" value="{esc(device.get('name'))}" maxlength="80" required><label>Entità/azione di notifica</label><input name="service" value="{esc(device.get('service'))}" maxlength="120" placeholder="mobile_app_iphone_marius" required><label style="display:flex;align-items:center;gap:9px;margin-bottom:15px"><input type="checkbox" name="enabled" value="1" {checked} style="width:auto;margin:0"> Dispositivo attivo</label><button type="submit">Salva modifiche</button></form><div class="actions" style="margin-top:10px"><form method="post" action="settings/device/{device_id}/test"><button type="submit">Invia prova</button></form><form method="post" action="settings/device/{device_id}/delete" onsubmit="return confirm('Eliminare questo dispositivo?')"><button type="submit" class="danger">Elimina</button></form></div></div>'''
    if not device_cards:
        device_cards = '<div class="card span-12"><p class="muted">Nessun dispositivo configurato.</p></div>'
    discovery_status = get_setting('notification_discovery_status', 'Premi il pulsante per cercare automaticamente i telefoni registrati nell’app Home Assistant.')
    manager_username = get_setting('manager_username', '')
    manager_configured = bool(get_setting('manager_password_hash'))
    manager_checked = 'checked' if get_setting('manager_enabled', '0') == '1' else ''
    manager_url = manager_portal_url()
    manager_password_help = 'Lascia vuoto per conservare la password attuale.' if manager_configured else 'Crea una password di almeno 8 caratteri.'
    translation = options.get('translation_url') or 'Automatica integrata (Google con MyMemory di riserva)'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    return page('Impostazioni', f'''{notice}<div class="grid"><div class="card span-6"><h2>Password zone singole</h2><p class="muted">Usata dai QR che aprono direttamente una zona.</p><form method="post" action="pin"><label>Password salvata</label><input type="text" name="pin" value="{esc(pin_plain)}" minlength="6" maxlength="64" autocomplete="off" autocapitalize="none" required placeholder="Inserisci nuovamente la password"><button>Salva password zone</button></form>{f'<div class="notice warning">{esc(pin_hint)}</div>' if pin_hint else ''}</div><div class="card span-6"><h2>Password QR di gruppo</h2><p class="muted">È diversa dalla password delle singole zone e permette di scegliere una delle zone attive.</p><form method="post" action="settings/group-pin"><label>Password di gruppo salvata</label><input type="text" name="pin" value="{esc(group_pin)}" minlength="6" maxlength="64" autocomplete="off" autocapitalize="none" required placeholder="Crea la password di gruppo"><button>Salva password di gruppo</button></form></div><div class="card span-6"><h2>QR con tutte le zone</h2><p><a href="{esc(group_url)}" target="_blank">{esc(group_url)}</a></p>{'<img class="qr" src="settings/group-qr">' if group_pin else '<div class="notice warning">Prima salva la password di gruppo.</div>'}<div class="actions" style="margin-top:12px">{f'<a class="btn" href="settings/group-qr?download=1">Scarica QR di gruppo</a>' if group_pin else ''}</div></div><div class="card span-6"><h2>Configurazione</h2><p><b>URL pubblico:</b><br>{esc(base)}</p><p><b>Traduzione automatica:</b><br>{esc(translation)}</p><p class="muted">URL e traduzione si modificano nella scheda Configurazione dell'add-on di Home Assistant.</p></div><div class="card span-12"><h2>Dispositivi per le notifiche</h2><p class="muted">I nuovi ticket vengono inviati a tutti i dispositivi attivi. Puoi modificarli anche quando cambi telefono.</p><form method="post" action="settings/devices/discover"><button type="submit">⌕ Rileva dispositivi da Home Assistant</button></form><div class="notice" style="margin-top:12px"><b>Diagnostica rilevamento:</b><br>{esc(discovery_status)}</div><details><summary><b>Aggiunta manuale</b></summary><form method="post" action="settings/device" style="margin-top:12px"><div class="filters"><div><label>Nome dispositivo</label><input name="name" maxlength="80" placeholder="Es. iPhone Marius" required></div><div><label>Entità/azione</label><input name="service" maxlength="120" placeholder="mobile_app_iphone_marius" required></div><button type="submit">Aggiungi dispositivo</button></div></form></details></div>{device_cards}<div class="card span-12"><h2>Accesso del titolare</h2><p class="muted">Portale separato da Home Assistant. Il titolare può gestire i ticket ma non può modificare PIN, QR, zone, telefoni o configurazioni tecniche.</p><p><b>Indirizzo del portale:</b><br><a href="{esc(manager_url)}" target="_blank">{esc(manager_url)}</a></p><form method="post" action="settings/manager"><label>Nome utente del titolare</label><input name="username" value="{esc(manager_username)}" minlength="3" maxlength="80" autocomplete="username" required placeholder="Es. titolare"><label>Nuova password</label><input type="password" name="password" minlength="8" maxlength="128" autocomplete="new-password" placeholder="{esc(manager_password_help)}"><p class="muted">{esc(manager_password_help)} La password viene protetta e non può essere visualizzata: se viene dimenticata, puoi sostituirla qui.</p><label style="display:flex;align-items:center;gap:9px;margin-bottom:15px"><input type="checkbox" name="enabled" value="1" {manager_checked} style="width:auto;margin:0"> Portale Titolare attivo</label><button type="submit">Salva accesso titolare</button></form></div><div class="card span-12"><h2>Backup</h2><p>Scarica database e fotografie in un unico archivio ZIP.</p><a class="btn" href="settings/backup">Scarica backup</a></div></div>''')


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


def validate_notification_device(name: str, service: str):
    name = name.strip()
    service = normalize_notify_service(service)
    if not name or len(name) > 80:
        raise HTTPException(400, 'Nome dispositivo non valido')
    if not service or len(service) > 120 or not all(char.isalnum() or char == '_' for char in service):
        raise HTTPException(400, 'Entità di notifica non valida')
    return name, service


@admin_app.post('/settings/devices/discover')
def discover_notification_devices():
    services, error = discover_mobile_app_services()
    if error:
        set_setting('notification_discovery_status', error)
        return RedirectResponse('../../settings?message=' + urllib.parse.quote(error), status_code=303)
    devices = notification_devices()
    existing = {normalize_notify_service(device.get('service', '')) for device in devices}
    added = 0
    for service in services:
        if service not in existing:
            devices.append({'id': secrets.token_hex(6), 'name': mobile_device_name(service), 'service': service, 'enabled': True})
            existing.add(service)
            added += 1
    save_notification_devices(devices)
    status = f'Home Assistant collegato correttamente. Rilevati {len(services)} dispositivi mobili; aggiunti {added} nuovi.'
    if not services:
        status += ' Nessuna azione mobile_app trovata: apri almeno una volta l’app Home Assistant sul telefono e controlla la registrazione del dispositivo.'
    set_setting('notification_discovery_status', status)
    return RedirectResponse('../../settings?message=' + urllib.parse.quote(status), status_code=303)


@admin_app.post('/settings/device')
def add_notification_device(name: str = Form(...), service: str = Form(...)):
    name, service = validate_notification_device(name, service)
    devices = notification_devices()
    devices.append({'id': secrets.token_hex(6), 'name': name, 'service': service, 'enabled': True})
    save_notification_devices(devices)
    return RedirectResponse('../settings?message=Dispositivo%20aggiunto', status_code=303)


@admin_app.post('/settings/device/{device_id}/update')
def update_notification_device(device_id: str, name: str = Form(...), service: str = Form(...), enabled: str = Form('')):
    name, service = validate_notification_device(name, service)
    devices = notification_devices()
    for device in devices:
        if device.get('id') == device_id:
            device.update({'name': name, 'service': service, 'enabled': enabled == '1'})
            save_notification_devices(devices)
            return RedirectResponse('../../../settings?message=Dispositivo%20aggiornato', status_code=303)
    raise HTTPException(404, 'Dispositivo non trovato')


@admin_app.post('/settings/device/{device_id}/delete')
def delete_notification_device(device_id: str):
    devices = notification_devices()
    updated = [device for device in devices if device.get('id') != device_id]
    if len(updated) == len(devices):
        raise HTTPException(404, 'Dispositivo non trovato')
    save_notification_devices(updated)
    return RedirectResponse('../../../settings?message=Dispositivo%20eliminato', status_code=303)


@admin_app.post('/settings/device/{device_id}/test')
def test_notification_device(device_id: str):
    device = next((item for item in notification_devices() if item.get('id') == device_id), None)
    if not device:
        raise HTTPException(404, 'Dispositivo non trovato')
    ok, message = notify_device(device.get('service', ''), 'Notifica di prova inviata correttamente.')
    result = f'{device.get("name", "Dispositivo")}: {message}'
    return RedirectResponse(f'../../../settings?message={urllib.parse.quote(result)}', status_code=303)


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
    priority_notice = ''
    if ticket_priority_class(t):
        priority_notice = f'<div class="priority-alert">{priority_dot(t)} PRIORITÀ {esc(t["priority"].upper())}: intervenire rapidamente</div>'
    delete_form = ''
    if t['status'] == 'Risolto':
        photo_text = f' e le sue {len(files)} foto' if files else ''
        delete_form = f'''<hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h2>Elimina ticket</h2><p class="muted">Questa operazione libera spazio ma non può essere annullata.</p><form method="post" action="{ticket_id}/delete" onsubmit="return confirm('Eliminare definitivamente il ticket {esc(t['ticket_code'])}{photo_text}?')"><button class="danger" type="submit">Elimina ticket e foto</button></form>'''
    return page(t['ticket_code'], f'''{priority_notice}<div class="grid"><div class="card span-7"><h2>{esc(t["ticket_code"])}</h2><p><b>Zona:</b> {esc(t["zone_name"])}</p><p><b>Segnalato da:</b> {esc(t["reporter_name"])}</p><p><b>Categoria:</b> {esc(t["category"])}</p><h3>Descrizione originale</h3><p style="white-space:pre-wrap">{esc(t["description_original"])}</p>{translation_notice}<form method="post" action="{ticket_id}/auto-translate" style="margin-bottom:18px"><button type="submit">Traduci ora in italiano e tedesco</button></form><h3>Traduzione italiana</h3><p style="white-space:pre-wrap">{esc(t["description_it"] or "In attesa")}</p><h3>Traduzione tedesca / Deutsche Übersetzung</h3><p style="white-space:pre-wrap">{esc(t["description_de"] or "In attesa / Ausstehend")}</p><form method="post" action="{ticket_id}/translation"><label>Correggi traduzione italiana</label><textarea name="description_it" maxlength="4000">{esc(t["description_it"] or "")}</textarea><label>Correggi traduzione tedesca / Deutsche Übersetzung</label><textarea name="description_de" maxlength="4000">{esc(t["description_de"] or "")}</textarea><button>Salva correzioni</button></form></div><div class="card span-5"><h2>Gestione</h2><form method="post" action="{ticket_id}/update"><label>Stato</label><select name="status">{status_options}</select><label>Priorità</label><select name="priority">{priority_options}</select><label>Note interne / soluzione</label><textarea name="resolution_notes" maxlength="4000">{esc(t["resolution_notes"] or "")}</textarea><button>Salva modifiche</button></form><h2 style="margin-top:22px">Foto</h2><div class="photos">{photos}</div>{delete_form}</div></div>''')


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
    ticket_code, deleted_photos = delete_resolved_ticket(ticket_id)
    message = f'Ticket {ticket_code} eliminato. Foto eliminate: {deleted_photos}.'
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


@public_app.get('/n/{signed_token}', response_class=HTMLResponse)
def notification_ticket(request: Request, signed_token: str):
    ticket_id = notification_ticket_id(signed_token)
    con = db()
    ticket = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=? ORDER BY id', (ticket_id,)).fetchall()
    con.close()
    if not ticket:
        raise HTTPException(404, 'Ticket non trovato')
    lang = public_language(request)
    labels = {
        'it': {'title': 'Dettaglio ticket', 'zone': 'Zona', 'reporter': 'Segnalato da', 'category': 'Categoria', 'priority': 'Priorità', 'status': 'Stato', 'original': 'Descrizione originale', 'italian': 'Traduzione italiana', 'german': 'Traduzione tedesca', 'photos': 'Foto', 'none': 'Nessuna foto'},
        'de': {'title': 'Ticketdetails', 'zone': 'Bereich', 'reporter': 'Gemeldet von', 'category': 'Kategorie', 'priority': 'Priorität', 'status': 'Status', 'original': 'Originalbeschreibung', 'italian': 'Italienische Übersetzung', 'german': 'Deutsche Übersetzung', 'photos': 'Fotos', 'none': 'Keine Fotos'},
    }[lang]
    photos = ''.join(
        f'<a href="{esc(signed_token)}/file/{f["id"]}" target="_blank"><img src="{esc(signed_token)}/file/{f["id"]}" alt="{esc(f["original_name"])}"><span class="muted">{esc(f["original_name"])}</span></a>'
        for f in files
    ) or f'<p class="muted">{labels["none"]}</p>'
    priority_notice = ''
    if ticket_priority_class(ticket):
        priority_notice = f'<div class="priority-alert">{priority_dot(ticket)} {labels["priority"].upper()} {esc(ticket["priority"].upper())}</div>'
    body = f'''{priority_notice}<div class="public-card"><h1>{labels['title']}</h1><span class="muted">{esc(ticket['ticket_code'])}</span><p><b>{labels['zone']}:</b> {esc(ticket['zone_name'])}</p><p><b>{labels['reporter']}:</b> {esc(ticket['reporter_name'])}</p><p><b>{labels['category']}:</b> {esc(ticket['category'])}</p><p><b>{labels['priority']}:</b> {esc(ticket['priority'] or 'Normale')}</p><p><b>{labels['status']}:</b> {esc(ticket['status'])}</p><h2>{labels['original']}</h2><p style="white-space:pre-wrap">{esc(ticket['description_original'])}</p><h2>{labels['italian']}</h2><p style="white-space:pre-wrap">{esc(ticket['description_it'] or '—')}</p><h2>{labels['german']}</h2><p style="white-space:pre-wrap">{esc(ticket['description_de'] or '—')}</p><h2>{labels['photos']}</h2><div class="photos">{photos}</div></div>'''
    return page(f'{labels["title"]} {ticket["ticket_code"]}', body, public=True, lang=lang, close_on_back=True)


@public_app.get('/n/{signed_token}/file/{file_id}')
def notification_ticket_file(signed_token: str, file_id: int):
    ticket_id = notification_ticket_id(signed_token)
    con = db()
    row = con.execute('SELECT * FROM ticket_files WHERE id=? AND ticket_id=?', (file_id, ticket_id)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404)
    path = (UPLOAD_DIR / row['stored_name']).resolve()
    if not path.is_file() or path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(404)
    filename = Path(row['original_name']).name.replace('"', '').replace('\r', '').replace('\n', '')
    return FileResponse(path, media_type=row['content_type'], filename=filename, content_disposition_type='inline', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, max-age=300'})


@public_app.get('/', response_class=HTMLResponse)
def public_home(request: Request):
    lang = public_language(request)
    return page('Hausmeister Carellas', f'<div class="public-card"><div class="success"><h1>{public_text(lang, "portal")}</h1><p>{public_text(lang, "scan_help")}</p></div></div>', public=True, lang=lang, close_on_back=True)


@public_app.get('/manager/login', response_class=HTMLResponse)
def manager_login_page(request: Request, error: str = ''):
    lang = public_language(request)
    if manager_session_valid(request):
        return RedirectResponse('/manager', status_code=303)
    if get_setting('manager_enabled', '0') != '1' or not get_setting('manager_password_hash'):
        return page(manager_text(lang, 'portal'), f'''<div class="public-card"><div class="success"><h1>{manager_text(lang, 'portal')}</h1><p>{manager_text(lang, 'disabled')}</p></div></div>''', public=True, lang=lang, close_on_back=True)
    error_notice = f'<div class="notice warning" role="alert"><b>⚠ {esc(error)}</b></div>' if error else ''
    return page(manager_text(lang, 'login'), f'''<div class="public-card"><h1>{manager_text(lang, 'login')}</h1>{error_notice}<form method="post" action="/manager/login"><label>{manager_text(lang, 'username')}</label><input name="username" maxlength="80" autocomplete="username" required autofocus><label>{manager_text(lang, 'password')}</label><input type="password" name="password" maxlength="128" autocomplete="current-password" required><button type="submit">{manager_text(lang, 'enter')}</button></form></div>''', public=True, lang=lang, close_on_back=True)


@public_app.post('/manager/login')
def manager_login(request: Request, username: str = Form(...), password: str = Form(...)):
    lang = public_language(request)
    client = request.headers.get('x-forwarded-for', '').split(',')[0].strip() or (request.client.host if request.client else 'unknown')
    key = f'{client}:manager'
    current = time.time()
    attempts = [stamp for stamp in PIN_ATTEMPTS.get(key, []) if current - stamp < PIN_WINDOW_SECONDS]
    if len(attempts) >= PIN_MAX_ATTEMPTS:
        return RedirectResponse('/manager/login?error=' + urllib.parse.quote(manager_text(lang, 'locked')), status_code=303)
    stored_username = get_setting('manager_username', '')
    password_hash = get_setting('manager_password_hash', '')
    try:
        valid = bool(get_setting('manager_enabled', '0') == '1' and secrets.compare_digest(username.strip(), stored_username) and password_hash and argon2.verify(password, password_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        return RedirectResponse('/manager/login?error=' + urllib.parse.quote(manager_text(lang, 'invalid')), status_code=303)
    PIN_ATTEMPTS.pop(key, None)
    response = RedirectResponse('/manager', status_code=303)
    response.set_cookie('hm_manager_session', serializer().dumps({'purpose': 'manager', 'username': stored_username, 'version': get_setting('manager_session_version', '')}), max_age=12 * 3600, httponly=True, secure=True, samesite='lax', path='/')
    return response


@public_app.get('/manager/logout')
def manager_logout():
    response = RedirectResponse('/manager/login', status_code=303)
    response.delete_cookie('hm_manager_session', path='/')
    return response


@public_app.get('/manager', response_class=HTMLResponse)
def manager_home(request: Request, message: str = ''):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
    con = db()
    zones = con.execute('SELECT * FROM zones ORDER BY name').fetchall()
    tickets = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC LIMIT 50').fetchall()
    counts = {row['status']: row['n'] for row in con.execute('SELECT status, COUNT(*) n FROM tickets GROUP BY status').fetchall()}
    total = con.execute('SELECT COUNT(*) n FROM tickets').fetchone()['n']
    con.close()
    open_count = counts.get('Nuovo', 0)
    work_count = counts.get('Preso in carico', 0) + counts.get('In lavorazione', 0)
    done_count = counts.get('Risolto', 0)
    zone_rows = ''.join(f'<div class="zone-row"><div><b>{esc(z["name"])}</b><br><span class="muted">{manager_text(lang, "active") if z["active"] else manager_text(lang, "inactive")}</span></div><a class="btn" href="/manager/zone/{z["id"]}">QR →</a></div>' for z in zones) or f'<p class="muted">{manager_text(lang, "no_zones")}</p>'
    ticket_rows = ''.join(f'<tr class="{ticket_priority_class(t)}"><td><a href="/manager/ticket/{t["id"]}"><b>{esc(t["ticket_code"])}</b></a></td><td>{esc(t["zone_name"])}</td><td>{esc(t["reporter_name"])}</td><td>{priority_dot(t)}<b>{esc(manager_priority_text(lang, t["priority"] or "Normale"))}</b></td><td><span class="pill {"done" if t["status"] == "Risolto" else "open"}">{esc(manager_status_text(lang, t["status"]))}</span></td></tr>' for t in tickets) or f'<tr><td colspan="5">{manager_text(lang, "no_tickets")}</td></tr>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid">
      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></div>
      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></div>
      <div class="card span-8"><h2>{manager_text(lang, 'recent')}</h2><div class="table-wrap"><table><tr><th>ID</th><th>{manager_text(lang, 'zone')}</th><th>{manager_text(lang, 'reporter')}</th><th>{manager_text(lang, 'priority')}</th><th>{manager_text(lang, 'status')}</th></tr>{ticket_rows}</table></div><p><a class="btn" href="/manager/tickets">{manager_text(lang, 'all_tickets')}</a></p></div>
      <div class="card span-4"><h2>{manager_text(lang, 'zones')}</h2>{zone_rows}</div>
    </div>'''
    return page(manager_text(lang, 'dashboard'), body, manager=True, lang=lang)


@public_app.get('/manager/tickets', response_class=HTMLResponse)
def manager_tickets_page(request: Request, q: str = '', status: str = '', message: str = ''):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
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
    rows = ''.join(f'''<tr class="{ticket_priority_class(t)}"><td><a href="/manager/ticket/{t['id']}"><b>{esc(t['ticket_code'])}</b></a></td><td>{esc(t['zone_name'])}</td><td>{esc(t['reporter_name'])}</td><td>{esc(manager_category_text(lang, t['category']))}</td><td>{priority_dot(t)}<b>{esc(manager_priority_text(lang, t['priority'] or 'Normale'))}</b></td><td><span class="pill {'done' if t['status'] == 'Risolto' else 'open'}">{esc(manager_status_text(lang, t['status']))}</span></td></tr>''' for t in tickets) or f'<tr><td colspan="6">{manager_text(lang, "no_tickets")}</td></tr>'
    options = f'<option value="">{manager_text(lang, "all_statuses")}</option>' + ''.join(f'<option value="{esc(s)}" {"selected" if status == s else ""}>{esc(manager_status_text(lang, s))}</option>' for s in STATUSES)
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="card"><form class="filters" method="get"><div><label>{manager_text(lang, 'search')}</label><input name="q" value="{esc(q)}" placeholder="{manager_text(lang, 'search_hint')}"></div><div><label>{manager_text(lang, 'status')}</label><select name="status">{options}</select></div><button>{manager_text(lang, 'search')}</button></form><div class="table-wrap" style="margin-top:14px"><table><tr><th>ID</th><th>{manager_text(lang, 'zone')}</th><th>{manager_text(lang, 'reporter')}</th><th>{manager_text(lang, 'category')}</th><th>{manager_text(lang, 'priority')}</th><th>{manager_text(lang, 'status')}</th></tr>{rows}</table></div></div>'''
    return page(manager_text(lang, 'tickets'), body, manager=True, lang=lang)


@public_app.get('/manager/zones', response_class=HTMLResponse)
def manager_zones_page(request: Request, message: str = '', created: int = 0):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
    con = db()
    zones = con.execute('SELECT z.*, COUNT(t.id) ticket_count FROM zones z LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY z.name').fetchall()
    con.close()
    rows = ''.join(f'''<tr{' class="new-zone"' if z['id'] == created else ''}><td><b>{esc(z['name'])}</b></td><td>{manager_text(lang, 'active') if z['active'] else manager_text(lang, 'inactive')}</td><td>{z['ticket_count']}</td><td><a class="btn" href="/manager/zone/{z['id']}">{manager_text(lang, 'manage_qr')}</a></td></tr>''' for z in zones) or f'<tr><td colspan="4">{manager_text(lang, "no_zones")}</td></tr>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<style>.new-zone td{{background:#f1f8df}}</style><div class="grid"><div class="card span-8"><h2>{manager_text(lang, 'existing_zones')}</h2><div class="table-wrap"><table><tr><th>{manager_text(lang, 'zone')}</th><th>{manager_text(lang, 'status')}</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class="card span-4"><h2>{manager_text(lang, 'new_zone')}</h2><form method="post" action="/manager/zone"><label>{manager_text(lang, 'name')}</label><input name="name" maxlength="80" required placeholder="Es. Cucina"><button>{manager_text(lang, 'create_zone')}</button></form></div></div>'''
    return page(manager_text(lang, 'zones'), body, manager=True, lang=lang)


@public_app.post('/manager/zone')
def manager_create_zone(request: Request, name: str = Form(...)):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    name = name.strip()
    if not name or len(name) > 80:
        raise HTTPException(400, 'Nome zona non valido')
    con = db()
    cur = con.execute('INSERT INTO zones(name,token,created_at) VALUES(?,?,?)', (name, secrets.token_urlsafe(18), now_iso()))
    con.commit()
    zone_id = cur.lastrowid
    con.close()
    lang = public_language(request)
    message = urllib.parse.quote(f'Bereich "{name}" wurde erstellt.' if lang == 'de' else f'Zona "{name}" creata correttamente.')
    return RedirectResponse(f'/manager/zones?message={message}&created={zone_id}', status_code=303)


@public_app.get('/manager/zone/{zone_id}', response_class=HTMLResponse)
def manager_zone_detail(request: Request, zone_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    ticket_count = con.execute('SELECT COUNT(*) n FROM tickets WHERE zone_id=?', (zone_id,)).fetchone()['n']
    con.close()
    if not zone:
        raise HTTPException(404, 'Zona non trovata')
    url = public_url_for(zone)
    active_label = manager_text(lang, 'disable_zone') if zone['active'] else manager_text(lang, 'enable_zone')
    delete_message = esc((f'Bereich {zone["name"]}, seine {ticket_count} Tickets und alle Fotos endgültig löschen?' if lang == 'de' else f'Eliminare definitivamente la zona {zone["name"]}, i suoi {ticket_count} ticket e tutte le foto?'))
    regenerate_message = 'Der alte QR-Code funktioniert danach nicht mehr. Fortfahren?' if lang == 'de' else 'Il vecchio QR smetterà subito di funzionare. Continuare?'
    body = f'''<div class="grid"><div class="card span-7"><h2>{esc(zone['name'])}</h2><p><a href="{esc(url)}" target="_blank">{esc(url)}</a></p><img class="qr" src="/manager/zone/{zone_id}/qr"><div class="actions" style="margin-top:12px"><a class="btn" href="/manager/zone/{zone_id}/qr?download=1">{manager_text(lang, 'download_qr')}</a><button onclick="window.print()">{manager_text(lang, 'print')}</button><form method="post" action="/manager/zone/{zone_id}/toggle"><button type="submit">{active_label}</button></form><form method="post" action="/manager/zone/{zone_id}/regenerate" data-confirm="{esc(regenerate_message)}" onsubmit="return confirm(this.dataset.confirm)"><button class="danger" type="submit">{manager_text(lang, 'regenerate_qr')}</button></form></div></div><div class="card span-5"><h2>{manager_text(lang, 'edit_zone')}</h2><form method="post" action="/manager/zone/{zone_id}/rename"><label>{manager_text(lang, 'zone_name')}</label><input name="name" value="{esc(zone['name'])}" maxlength="80" required><button>{manager_text(lang, 'save_name')}</button></form><hr style="border:0;border-top:1px solid var(--line);margin:22px 0"><h2>{manager_text(lang, 'delete_zone')}</h2><p class="muted">{manager_text(lang, 'linked_tickets')}: {ticket_count}. {manager_text(lang, 'delete_zone_help')}</p><form method="post" action="/manager/zone/{zone_id}/delete" data-confirm="{delete_message}" onsubmit="return confirm(this.dataset.confirm)"><button class="danger">{manager_text(lang, 'delete_zone')}</button></form></div></div>'''
    return page(zone['name'], body, manager=True, lang=lang, back_url='/manager/zones')


@public_app.post('/manager/zone/{zone_id}/rename')
def manager_zone_rename(request: Request, zone_id: int, name: str = Form(...)):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    name = name.strip()
    if not name or len(name) > 80:
        raise HTTPException(400, 'Nome zona non valido')
    con = db()
    con.execute('UPDATE zones SET name=? WHERE id=?', (name, zone_id))
    con.commit()
    con.close()
    return RedirectResponse(f'/manager/zone/{zone_id}', status_code=303)


@public_app.post('/manager/zone/{zone_id}/toggle')
def manager_zone_toggle(request: Request, zone_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    con = db()
    con.execute('UPDATE zones SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?', (zone_id,))
    con.commit()
    con.close()
    return RedirectResponse(f'/manager/zone/{zone_id}', status_code=303)


@public_app.post('/manager/zone/{zone_id}/regenerate')
def manager_zone_regenerate(request: Request, zone_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    con = db()
    con.execute('UPDATE zones SET token=? WHERE id=?', (secrets.token_urlsafe(18), zone_id))
    con.commit()
    con.close()
    return RedirectResponse(f'/manager/zone/{zone_id}', status_code=303)


@public_app.post('/manager/zone/{zone_id}/delete')
def manager_zone_delete(request: Request, zone_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
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
    return RedirectResponse('/manager/zones', status_code=303)


@public_app.get('/manager/zone/{zone_id}/qr')
def manager_zone_qr(request: Request, zone_id: int, download: int = 0):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE id=?', (zone_id,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Zona non trovata')
    image = qrcode.make(public_url_for(zone))
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    disposition = 'attachment' if download else 'inline'
    return StreamingResponse(buf, media_type='image/png', headers={'Content-Disposition': f'{disposition}; filename="zona-{zone_id}.png"'})


@public_app.get('/manager/ticket/{ticket_id}', response_class=HTMLResponse)
def manager_ticket_detail(request: Request, ticket_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
    con = db()
    ticket = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id WHERE t.id=?', (ticket_id,)).fetchone()
    files = con.execute('SELECT * FROM ticket_files WHERE ticket_id=? ORDER BY id', (ticket_id,)).fetchall()
    con.close()
    if not ticket:
        raise HTTPException(404, 'Ticket non trovato')
    status_labels = {
        'it': {'Nuovo': 'Nuovo', 'Preso in carico': 'Preso in carico', 'In lavorazione': 'In lavorazione', 'Da verificare': 'Da verificare', 'Risolto': 'Risolto'},
        'de': {'Nuovo': 'Neu', 'Preso in carico': 'Übernommen', 'In lavorazione': 'In Bearbeitung', 'Da verificare': 'Zu prüfen', 'Risolto': 'Erledigt'},
    }[lang]
    priority_labels = {'it': {'Bassa': 'Bassa', 'Normale': 'Normale', 'Alta': 'Alta', 'Urgente': 'Urgente'}, 'de': {'Bassa': 'Niedrig', 'Normale': 'Normal', 'Alta': 'Hoch', 'Urgente': 'Dringend'}}[lang]
    status_options = ''.join(f'<option value="{esc(value)}" {"selected" if ticket["status"] == value else ""}>{esc(status_labels[value])}</option>' for value in STATUSES)
    priority_options = ''.join(f'<option value="{esc(value)}" {"selected" if (ticket["priority"] or "Normale") == value else ""}>{esc(priority_labels[value])}</option>' for value in PRIORITIES)
    photos = ''.join(f'<a href="/manager/ticket/{ticket_id}/file/{file["id"]}" target="_blank"><img src="/manager/ticket/{ticket_id}/file/{file["id"]}" alt="{esc(file["original_name"])}"><span class="muted">{esc(file["original_name"])}</span></a>' for file in files) or f'<p class="muted">{manager_text(lang, "no_photos")}</p>'
    priority_notice = f'<div class="priority-alert">{priority_dot(ticket)} {manager_text(lang, "priority").upper()} {esc(priority_labels.get(ticket["priority"], ticket["priority"]))}</div>' if ticket_priority_class(ticket) else ''
    delete_form = ''
    if ticket['status'] == 'Risolto':
        confirm_delete = 'Ticket und alle Fotos endgültig löschen?' if lang == 'de' else 'Eliminare definitivamente il ticket e tutte le foto?'
        delete_form = f'''<form method="post" action="/manager/ticket/{ticket_id}/delete" data-confirm="{esc(confirm_delete)}" onsubmit="return confirm(this.dataset.confirm)"><button type="submit" class="danger">{manager_text(lang, 'delete')}</button></form>'''
    body = f'''{priority_notice}<div class="public-card"><h1>{esc(ticket['ticket_code'])}</h1><p><b>{manager_text(lang, 'zone')}:</b> {esc(ticket['zone_name'])}</p><p><b>{manager_text(lang, 'reporter')}:</b> {esc(ticket['reporter_name'])}</p><p><b>{manager_text(lang, 'category')}:</b> {esc(manager_category_text(lang, ticket['category']))}</p><h2>{manager_text(lang, 'original')}</h2><p style="white-space:pre-wrap">{esc(ticket['description_original'])}</p><h2>{manager_text(lang, 'italian')}</h2><p style="white-space:pre-wrap">{esc(ticket['description_it'] or '—')}</p><h2>{manager_text(lang, 'german')}</h2><p style="white-space:pre-wrap">{esc(ticket['description_de'] or '—')}</p><form method="post" action="/manager/ticket/{ticket_id}/update"><label>{manager_text(lang, 'status')}</label><select name="status">{status_options}</select><label>{manager_text(lang, 'priority')}</label><select name="priority">{priority_options}</select><label>{manager_text(lang, 'notes')}</label><textarea name="resolution_notes" maxlength="4000">{esc(ticket['resolution_notes'] or '')}</textarea><button type="submit">{manager_text(lang, 'save')}</button></form><h2 style="margin-top:22px">{manager_text(lang, 'photos')}</h2><div class="photos">{photos}</div><div style="margin-top:22px">{delete_form}</div></div>'''
    return page(ticket['ticket_code'], body, manager=True, lang=lang, back_url='/manager/tickets')


@public_app.post('/manager/ticket/{ticket_id}/update')
def manager_ticket_update(request: Request, ticket_id: int, status: str = Form(...), priority: str = Form(...), resolution_notes: str = Form('')):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    if status not in STATUSES or priority not in PRIORITIES:
        raise HTTPException(400, 'Valore non valido')
    con = db()
    exists = con.execute('SELECT id FROM tickets WHERE id=?', (ticket_id,)).fetchone()
    if not exists:
        con.close()
        raise HTTPException(404, 'Ticket non trovato')
    con.execute('UPDATE tickets SET status=?, priority=?, resolution_notes=?, updated_at=? WHERE id=?', (status, priority, resolution_notes.strip(), now_iso(), ticket_id))
    con.commit()
    con.close()
    return RedirectResponse(f'/manager/ticket/{ticket_id}', status_code=303)


@public_app.post('/manager/ticket/{ticket_id}/delete')
def manager_ticket_delete(request: Request, ticket_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    code, deleted_photos = delete_resolved_ticket(ticket_id)
    message = f'Ticket {code} eliminato. Foto eliminate: {deleted_photos}.'
    return RedirectResponse('/manager/tickets?message=' + urllib.parse.quote(message), status_code=303)


@public_app.get('/manager/ticket/{ticket_id}/file/{file_id}')
def manager_ticket_file(request: Request, ticket_id: int, file_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    con = db()
    row = con.execute('SELECT * FROM ticket_files WHERE id=? AND ticket_id=?', (file_id, ticket_id)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404)
    path = (UPLOAD_DIR / row['stored_name']).resolve()
    if not path.is_file() or path.parent != UPLOAD_DIR.resolve():
        raise HTTPException(404)
    filename = Path(row['original_name']).name.replace('"', '').replace('\r', '').replace('\n', '')
    return FileResponse(path, media_type=row['content_type'], filename=filename, content_disposition_type='inline', headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})


@public_app.get('/g/{token}', response_class=HTMLResponse)
def group_form(request: Request, token: str, error: str = ''):
    lang = public_language(request)
    if token != group_token():
        raise HTTPException(404, 'Ungültiger Gruppen-QR-Code' if lang == 'de' else 'QR di gruppo non valido')
    if not get_setting('group_pin_hash'):
        return page(public_text(lang, 'not_configured'), f'<div class="public-card"><div class="success"><h1>{public_text(lang, "unavailable")}</h1><p>{public_text(lang, "configure_password")}</p></div></div>', public=True, lang=lang, close_on_back=True)
    cookie = request.cookies.get('hm_session')
    unlocked = False
    if cookie:
        try:
            unlocked = serializer().loads(cookie, max_age=86400).get('group') == token
        except BadSignature:
            pass
    if not unlocked:
        error_notice = f'<div class="notice warning" role="alert"><b>⚠ {esc(error)}</b></div>' if error else ''
        return page(public_text(lang, 'all_zones'), f'''<div class="public-card"><h1>{public_text(lang, 'all_zones')}</h1><span class="muted">{public_text(lang, 'group_password_help')}</span>{error_notice}<form method="post" action="{esc(token)}/unlock"><label>{public_text(lang, 'group_password')}</label><input type="text" name="pin" minlength="6" maxlength="64" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" style="-webkit-text-security:disc" required placeholder="{public_text(lang, 'password_placeholder')}" autofocus><button>{public_text(lang, 'login')}</button></form></div>''', public=True, lang=lang, close_on_back=True)
    con = db()
    zones = con.execute('SELECT * FROM zones WHERE active=1 ORDER BY name').fetchall()
    con.close()
    buttons = ''.join(f'<a class="btn" style="width:100%;margin:6px 0" href="../../r/{esc(zone["token"])}">{esc(zone["name"])}</a>' for zone in zones) or f'<p class="muted">{public_text(lang, "no_zones")}</p>'
    return page(public_text(lang, 'choose_zone'), f'''<div class="public-card"><h1>{public_text(lang, 'choose_zone')}</h1><span class="muted">{public_text(lang, 'choose_zone_help')}</span>{buttons}</div>''', public=True, lang=lang, back_url=f'/g/{esc(token)}/logout')


@public_app.get('/g/{token}/logout')
def group_logout(token: str):
    if token != group_token():
        raise HTTPException(404)
    response = RedirectResponse(f'../{token}', status_code=303)
    response.delete_cookie('hm_session', path='/')
    return response


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
        error = 'Zu viele Versuche. In 15 Minuten erneut versuchen.' if lang == 'de' else 'Troppi tentativi. Riprova tra 15 minuti.'
        return RedirectResponse(f'../{token}?error={urllib.parse.quote(error)}', status_code=303)
    pin_hash = get_setting('group_pin_hash')
    try:
        valid = bool(pin_hash and argon2.verify(pin, pin_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        error = 'Ungültiges Gruppenpasswort' if lang == 'de' else 'Password di gruppo non valida'
        return RedirectResponse(f'../{token}?error={urllib.parse.quote(error)}', status_code=303)
    PIN_ATTEMPTS.pop(key, None)
    response = RedirectResponse(f'../{token}', status_code=303)
    response.set_cookie('hm_session', serializer().dumps({'group': token}), max_age=86400, httponly=True, secure=True, samesite='lax')
    return response


@public_app.get('/r/{token}', response_class=HTMLResponse)
def report_form(request: Request, token: str, error: str = ''):
    lang = public_language(request)
    con = db()
    zone = con.execute('SELECT * FROM zones WHERE token=? AND active=1', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Ungültiger Bereich' if lang == 'de' else 'Zona non valida')
    if not get_setting('pin_hash'):
        return page(public_text(lang, 'not_configured'), f'<div class="public-card"><div class="success"><h1>{public_text(lang, "unavailable")}</h1><p>{public_text(lang, "configure_password")}</p></div></div>', public=True, lang=lang, close_on_back=True)
    if not session_zone(request, token):
        error_notice = f'<div class="notice warning" role="alert"><b>⚠ {esc(error)}</b></div>' if error else ''
        return page(public_text(lang, 'report'), f'''<div class="public-card"><h1>{public_text(lang, 'report')}</h1><span class="muted">{public_text(lang, 'zone')}: <b>{esc(zone["name"])}</b> · {public_text(lang, 'enter_password')}</span>{error_notice}<form method="post" action="{esc(token)}/unlock"><label>{public_text(lang, 'password')}</label><input type="text" name="pin" minlength="6" maxlength="64" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" style="-webkit-text-security:disc" placeholder="{public_text(lang, 'password_placeholder')}" required autofocus><button>{public_text(lang, 'login')}</button></form></div>''', public=True, lang=lang, close_on_back=True)
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
    return page(public_text(lang, 'new_report'), f'''<div class="public-card"><h1>{public_text(lang, 'new_report')}</h1><span class="muted">{public_text(lang, 'selected_zone')}: <b>{esc(zone["name"])}</b></span><form method="post" enctype="multipart/form-data" action="{esc(token)}/submit"><label>{public_text(lang, 'name')} *</label><input name="reporter_name" maxlength="120" required placeholder="{public_text(lang, 'name_placeholder')}"><label>{public_text(lang, 'fault_type')} *</label><select name="category" required><option value="">{public_text(lang, 'select_category')}</option>{category_options}</select><label>{public_text(lang, 'priority')}</label><select name="priority">{priority_options}</select><label>{public_text(lang, 'description')} *</label><textarea name="description" maxlength="4000" rows="6" required placeholder="{public_text(lang, 'description_placeholder')}"></textarea><label>{public_text(lang, 'photos')}</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple><button>➤ {public_text(lang, 'send')}</button></form></div>''', public=True, lang=lang, back_url=f'/r/{esc(token)}/logout')


@public_app.get('/r/{token}/logout')
def report_logout(token: str):
    con = db()
    zone = con.execute('SELECT id FROM zones WHERE token=?', (token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404)
    response = RedirectResponse(f'../{token}', status_code=303)
    response.delete_cookie('hm_session', path='/')
    return response


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
        error = 'Zu viele Versuche. In 15 Minuten erneut versuchen.' if lang == 'de' else 'Troppi tentativi. Riprova tra 15 minuti.'
        return RedirectResponse(f'../{token}?error={urllib.parse.quote(error)}', status_code=303)
    pin_hash = get_setting('pin_hash')
    try:
        valid = bool(pin_hash and argon2.verify(pin, pin_hash))
    except Exception:
        valid = False
    if not valid:
        attempts.append(current)
        PIN_ATTEMPTS[key] = attempts
        error = 'Ungültiges Passwort' if lang == 'de' else 'Password non valida'
        return RedirectResponse(f'../{token}?error={urllib.parse.quote(error)}', status_code=303)
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
    direct_url = ticket_notification_url(ticket_id)
    title = f'{"URGENTE · " if priority == "Urgente" else ""}Ticket {code}'
    message = f'Zona {zone["name"]} · {category} · Priorità {priority}\n{description[:250]}'
    notify_home_assistant(message, title, direct_url)
    return page(public_text(lang, 'received'), f'''<div class="public-card"><div class="success"><div class="success-mark">✓</div><h1>{public_text(lang, 'received')}</h1><p>{public_text(lang, 'thanks')}</p><p><b>Ticket:</b> {esc(code)}<br><b>{public_text(lang, 'zone')}:</b> {esc(zone["name"])}</p></div></div>''', public=True, lang=lang, back_url=f'/r/{esc(token)}/logout')
