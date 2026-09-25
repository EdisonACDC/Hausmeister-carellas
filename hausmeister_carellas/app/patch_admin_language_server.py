from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Context locale per request, independent for every Home Assistant user/session.
ctx_marker = "CURRENT_INGRESS_IS_ADMIN = ContextVar('current_ingress_is_admin', default=True)\n"
if ctx_marker in text and "CURRENT_UI_LANG = ContextVar" not in text:
    text = text.replace(
        ctx_marker,
        ctx_marker + "CURRENT_UI_LANG = ContextVar('current_ui_lang', default='it')\n",
        1,
    )

# Resolve locale from the preference stored for the authenticated HA user.
apps_marker = "public_app = FastAPI(title='Hausmeister Carellas Public')\n"
if apps_marker in text and "async def ingress_language_context" not in text:
    middleware = r'''

def ingress_user_language(request: Request):
    identity = ingress_identity(request)
    user_id = (identity.get('id') or '').strip()
    if user_id:
        saved = get_setting('ha_user_language_' + user_id, '').strip().lower()
        if saved in ('it', 'de', 'ro'):
            return saved
    cookie_lang = (request.cookies.get('hm_user_lang') or '').strip().lower()
    if cookie_lang in ('it', 'de', 'ro'):
        return cookie_lang
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].strip().lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'


@admin_app.middleware('http')
async def ingress_language_context(request: Request, call_next):
    token = CURRENT_UI_LANG.set(ingress_user_language(request))
    try:
        return await call_next(request)
    finally:
        CURRENT_UI_LANG.reset(token)

'''
    text = text.replace(apps_marker, apps_marker + middleware, 1)

# Server-side dictionary. This covers the admin interface, not only the owner portal.
helper_marker = "def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):\n"
if helper_marker in text and "def translate_admin_html(" not in text:
    helpers = r'''
ADMIN_UI_TEXT = {
    'de': {
        'Gestione manutenzioni Carellas': 'Carellas Wartungsverwaltung',
        'Add-on in esecuzione': 'Add-on läuft',
        'Accesso titolare': 'Inhaberzugang',
        'Indietro': 'Zurück',
        'Dashboard': 'Dashboard',
        'Ticket': 'Tickets',
        'Zone / QR': 'Bereiche / QR',
        'Magazzino materiali': 'Materiallager',
        'Manutenzioni': 'Wartungen',
        'Impostazioni': 'Einstellungen',
        'Materiali da acquistare': 'Material nachbestellen',
        'Totale ticket': 'Tickets gesamt',
        'Aperti': 'Offen',
        'In lavorazione': 'In Bearbeitung',
        'Risolti': 'Erledigt',
        'Ticket recenti': 'Aktuelle Tickets',
        'Zona': 'Bereich',
        'Zone': 'Bereiche',
        'Segnalato da': 'Gemeldet von',
        'Priorità': 'Priorität',
        'Stato': 'Status',
        'Categoria': 'Kategorie',
        'Urgente': 'Dringend',
        'Alta': 'Hoch',
        'Normale': 'Normal',
        'Bassa': 'Niedrig',
        'Nuovo': 'Neu',
        'Preso in carico': 'Übernommen',
        'Da verificare': 'Zu prüfen',
        'Risolto': 'Erledigt',
        'Senza gruppo': 'Ohne Gruppe',
        'zone': 'Bereiche',
        'Attiva': 'Aktiv',
        'Disattivata': 'Deaktiviert',
        'Zone esistenti': 'Vorhandene Bereiche',
        'Nuova zona': 'Neuer Bereich',
        'Nome': 'Name',
        'Crea zona e QR': 'Bereich und QR erstellen',
        'Gestisci / QR': 'Verwalten / QR',
        'Crea ticket': 'Ticket erstellen',
        'Scarica QR': 'QR herunterladen',
        'Stampa': 'Drucken',
        'Modifica zona': 'Bereich bearbeiten',
        'Nome della zona': 'Bereichsname',
        'Salva nome': 'Name speichern',
        'Elimina zona': 'Bereich löschen',
        'Ticket collegati': 'Verknüpfte Tickets',
        'Cerca': 'Suchen',
        'Tutti gli stati': 'Alle Status',
        'Vedi tutti i ticket': 'Alle Tickets anzeigen',
        'Tutti gli articoli': 'Alle Artikel',
        'Solo da acquistare': 'Nur nachzubestellen',
        'Nuovo articolo': 'Neuer Artikel',
        'Descrizione': 'Beschreibung',
        'Posizione': 'Position',
        'Fornitore': 'Lieferant',
        'Quantità': 'Menge',
        'Salva articolo': 'Artikel speichern',
        'Carica materiale': 'Material einlagern',
        'Scarica materiale': 'Material entnehmen',
        'Movimenti recenti': 'Letzte Bewegungen',
        'Note interne / soluzione': 'Interne Notizen / Lösung',
        'Salva modifiche': 'Änderungen speichern',
        'Foto': 'Fotos',
        'Nessuna foto': 'Keine Fotos',
    },
    'ro': {
        'Gestione manutenzioni Carellas': 'Gestionare mentenanță Carellas',
        'Add-on in esecuzione': 'Add-on activ',
        'Accesso titolare': 'Acces proprietar',
        'Indietro': 'Înapoi',
        'Dashboard': 'Panou de control',
        'Ticket': 'Tichete',
        'Zone / QR': 'Zone / QR',
        'Magazzino materiali': 'Depozit materiale',
        'Manutenzioni': 'Mentenanțe',
        'Impostazioni': 'Setări',
        'Materiali da acquistare': 'Materiale de cumpărat',
        'Totale ticket': 'Total tichete',
        'Aperti': 'Deschise',
        'In lavorazione': 'În lucru',
        'Risolti': 'Rezolvate',
        'Ticket recenti': 'Tichete recente',
        'Zona': 'Zonă',
        'Zone': 'Zone',
        'Segnalato da': 'Raportat de',
        'Priorità': 'Prioritate',
        'Stato': 'Stare',
        'Categoria': 'Categorie',
        'Urgente': 'Urgent',
        'Alta': 'Ridicată',
        'Normale': 'Normală',
        'Bassa': 'Scăzută',
        'Nuovo': 'Nou',
        'Preso in carico': 'Preluat',
        'Da verificare': 'De verificat',
        'Risolto': 'Rezolvat',
        'Senza gruppo': 'Fără grup',
        'zone': 'zone',
        'Attiva': 'Activă',
        'Disattivata': 'Dezactivată',
        'Zone esistenti': 'Zone existente',
        'Nuova zona': 'Zonă nouă',
        'Nome': 'Nume',
        'Crea zona e QR': 'Creează zona și QR',
        'Gestisci / QR': 'Gestionează / QR',
        'Crea ticket': 'Creează tichet',
        'Scarica QR': 'Descarcă QR',
        'Stampa': 'Tipărește',
        'Modifica zona': 'Modifică zona',
        'Nome della zona': 'Numele zonei',
        'Salva nome': 'Salvează numele',
        'Elimina zona': 'Șterge zona',
        'Ticket collegati': 'Tichete asociate',
        'Cerca': 'Caută',
        'Tutti gli stati': 'Toate stările',
        'Vedi tutti i ticket': 'Vezi toate tichetele',
        'Tutti gli articoli': 'Toate articolele',
        'Solo da acquistare': 'Doar de cumpărat',
        'Nuovo articolo': 'Articol nou',
        'Descrizione': 'Descriere',
        'Posizione': 'Poziție',
        'Fornitore': 'Furnizor',
        'Quantità': 'Cantitate',
        'Salva articolo': 'Salvează articolul',
        'Carica materiale': 'Încarcă material',
        'Scarica materiale': 'Descarcă material',
        'Movimenti recenti': 'Mișcări recente',
        'Note interne / soluzione': 'Note interne / soluție',
        'Salva modifiche': 'Salvează modificările',
        'Foto': 'Fotografii',
        'Nessuna foto': 'Nicio fotografie',
    },
}


def translate_admin_html(value: str, lang: str):
    if lang not in ADMIN_UI_TEXT:
        return value
    result = value
    # Longer labels first to avoid partial replacements.
    for source, target in sorted(ADMIN_UI_TEXT[lang].items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace('>' + source + '<', '>' + target + '<')
        result = result.replace('>' + source + ' ', '>' + target + ' ')
        result = result.replace(' ' + source + '<', ' ' + target + '<')
        result = result.replace('placeholder="' + source + '"', 'placeholder="' + target + '"')
        result = result.replace('title="' + source + '"', 'title="' + target + '"')
    return result


'''
    text = text.replace(helper_marker, helpers + helper_marker, 1)

# page() must use the locale belonging to the current ingress user even if callers omit lang.
page_body_marker = "    shell_class = 'admin-shell' if manager else ('public-shell' if public else 'admin-shell')\n"
if page_body_marker in text and "CURRENT_UI_LANG.get()" not in text[text.find(helper_marker):text.find(helper_marker)+800]:
    text = text.replace(
        page_body_marker,
        "    if not public and not manager:\n        current_lang = CURRENT_UI_LANG.get()\n        if current_lang in ('it','de','ro'):\n            lang = current_lang\n" + page_body_marker,
        1,
    )

# Convert the page return to a variable and translate only the admin interface.
start = "    return f'''<!doctype html><html lang="
if start in text:
    text = text.replace(start, "    html_page = f'''<!doctype html><html lang=", 1)
    tail = "+'''</div></body></html>'''\n\n\ndef session_zone"
    if tail in text:
        text = text.replace(
            tail,
            "+'''</div></body></html>'''\n    return translate_admin_html(html_page, lang) if not public and not manager else html_page\n\n\ndef session_zone",
            1,
        )

path.write_text(text, encoding='utf-8')
