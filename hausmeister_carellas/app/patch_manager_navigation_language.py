from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Dashboard manager: metriche cliccabili e filtro gruppo "in lavorazione".
repls = {
'''<div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></div>''':
'''<a class="card span-3" href="/manager/tickets" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></a>''',
'''<div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></div>''':
'''<a class="card span-3" href="/manager/tickets?status=Nuovo" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></a>''',
'''<div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></div>''':
'''<a class="card span-3" href="/manager/tickets?status=In%20lavorazione" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></a>''',
'''<div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></div>''':
'''<a class="card span-3" href="/manager/tickets?status=Risolto" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></a>'''
}
for old,new in repls.items():
    if old in text: text=text.replace(old,new,1)

old="def manager_tickets_page(request: Request, q: str = '', status: str = '', message: str = ''):"
new="def manager_tickets_page(request: Request, q: str = '', status: str = '', message: str = ''):"
if old in text: text=text.replace(old,new,1)
old2="""    if status in STATUSES:
        query += ' AND t.status=?'
        params.append(status)
"""
new2="""    if status in STATUSES:
        query += ' AND t.status=?'
        params.append(status)
"""
if old2 in text: text=text.replace(old2,new2,1)

# Pulsante Crea ticket direttamente dalla pagina di ogni zona del Titolare.
needle='''<div class="actions" style="margin-top:12px"><a class="btn" href="/manager/zone/{zone_id}/qr?download=1">'''
if needle in text:
    text=text.replace(needle,'''<div class="actions" style="margin-top:12px"><a class="btn" href="{esc(url)}">➕ {manager_text(lang, 'new_ticket')}</a><a class="btn" href="/manager/zone/{zone_id}/qr?download=1">''',1)

# Testi necessari.
text=text.replace("'delete_material_confirm': 'Eliminare definitivamente questo articolo e la sua foto?',",
                  "'delete_material_confirm': 'Eliminare definitivamente questo articolo e la sua foto?', 'new_ticket': 'Crea ticket',",1)
text=text.replace("'delete_material_confirm': 'Diesen Artikel und sein Foto endgültig löschen?',",
                  "'delete_material_confirm': 'Diesen Artikel und sein Foto endgültig löschen?', 'new_ticket': 'Ticket erstellen',",1)

# Lingua automatica: public_language già legge Accept-Language; aggiunge rumeno con fallback IT.
# Duplica dizionario IT come base RO, sostituendo le etichette principali usate da dashboard/zone.
if "'ro': {" not in text:
    marker="    'de': {"
    ro="""    'ro': {
        'portal':'Portal proprietar','login':'Autentificare proprietar','username':'Nume utilizator','password':'Parolă','enter':'Autentificare','logout':'Ieșire','tickets':'Tichete','no_tickets':'Niciun tichet','zone':'Zonă','reporter':'Raportat de','category':'Categorie','priority':'Prioritate','status':'Stare','original':'Descriere originală','italian':'Traducere italiană','german':'Traducere germană','notes':'Note interne / soluție','photos':'Fotografii','no_photos':'Nicio fotografie','save':'Salvează modificările','delete':'Șterge tichetul și fotografiile','invalid':'Utilizator sau parolă incorectă','locked':'Prea multe încercări. Reîncearcă în 15 minute.','disabled':'Portalul proprietarului nu este activat.','updated':'Tichet actualizat.','dashboard':'Panou de control','zones':'Zone / QR','settings':'Setări','total':'Total tichete','open':'Deschise','working':'În lucru','resolved':'Rezolvate','recent':'Tichete recente','all_tickets':'Vezi toate tichetele','active':'Activă','inactive':'Dezactivată','no_zones':'Nicio zonă','search':'Caută','search_hint':'Cod, zonă, nume sau descriere','all_statuses':'Toate stările','existing_zones':'Zone existente','manage_qr':'Gestionează / QR','new_zone':'Zonă nouă','name':'Nume','create_zone':'Creează zona și QR','download_qr':'Descarcă QR','print':'Tipărește','disable_zone':'Dezactivează zona','enable_zone':'Activează zona','regenerate_qr':'Regenerează QR','edit_zone':'Modifică zona','zone_name':'Numele zonei','save_name':'Salvează numele','delete_zone':'Șterge zona','linked_tickets':'Tichete asociate','delete_zone_help':'Ștergerea zonei va șterge și tichetele și fotografiile sale.','new_ticket':'Creează tichet'
    },
"""
    if marker in text: text=text.replace(marker,ro+marker,1)

# Extinde le traduzioni degli stati/priorità/categorie al rumeno.
text=text.replace("""def manager_status_text(lang: str, value: str):
    if lang != 'de':
        return value
    return {'Nuovo': 'Neu', 'Preso in carico': 'Übernommen', 'In lavorazione': 'In Bearbeitung', 'Da verificare': 'Zu prüfen', 'Risolto': 'Erledigt'}.get(value, value)
""","""def manager_status_text(lang: str, value: str):
    if lang == 'de':
        return {'Nuovo':'Neu','Preso in carico':'Übernommen','In lavorazione':'In Bearbeitung','Da verificare':'Zu prüfen','Risolto':'Erledigt'}.get(value,value)
    if lang == 'ro':
        return {'Nuovo':'Nou','Preso in carico':'Preluat','In lavorazione':'În lucru','Da verificare':'De verificat','Risolto':'Rezolvat'}.get(value,value)
    return value
""")

path.write_text(text,encoding='utf-8')

# Automatic language including Romanian.
old_lang = """def public_language(request: Request):
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    return 'de' if preferred.startswith('de') else 'it'
"""
new_lang = """def public_language(request: Request):
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'
"""
if old_lang in text:
    text = text.replace(old_lang, new_lang, 1)
path.write_text(text,encoding='utf-8')


# Per-user language in Home Assistant Ingress.
# Home Assistant's own frontend language is not reliably forwarded as Accept-Language,
# so use a per-browser/session cookie populated client-side from HA/local browser locale.
old_public_language = """def public_language(request: Request):
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'
"""
new_public_language = """def public_language(request: Request):
    cookie_lang = (request.cookies.get('hm_user_lang') or '').lower()
    if cookie_lang in ('it','de','ro'):
        return cookie_lang
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'
"""
if old_public_language in text:
    text = text.replace(old_public_language, new_public_language, 1)

# Inject a tiny per-user locale synchronizer into every rendered page.
page_marker = "    return f'''<!doctype html><html lang=\"{esc(lang)}\"><head>"
if page_marker in text and "hm_user_lang" not in text[text.find("def page("):text.find("def page(")+5000]:
    replacement = """    locale_sync = '''<script>(function(){try{var l=(navigator.language||navigator.userLanguage||'it').toLowerCase().split('-')[0];if(!['it','de','ro'].includes(l))l='it';var m=document.cookie.match(/(?:^|; )hm_user_lang=([^;]+)/);var old=m?decodeURIComponent(m[1]):'';if(old!==l){document.cookie='hm_user_lang='+encodeURIComponent(l)+';path=/;max-age=31536000;SameSite=Lax';if(!sessionStorage.getItem('hm_lang_reload')){sessionStorage.setItem('hm_lang_reload','1');location.reload();}}else{sessionStorage.removeItem('hm_lang_reload');}}catch(e){}})();</script>'''
"""
    text = text.replace(page_marker, replacement + page_marker.replace("<head>","<head>{locale_sync}"), 1)

path.write_text(text,encoding='utf-8')

# Prefer locale hints forwarded by the Home Assistant session.\nold = "    cookie_lang = (request.cookies.get('hm_user_lang') or '').lower()\\n    if cookie_lang in ('it','de','ro'):\\n        return cookie_lang\\n"\nnew = "    header_lang = (request.headers.get('X-Hass-Language') or request.headers.get('X-Hass-Locale') or '').lower()\\n    if header_lang.startswith('de'):\\n        return 'de'\\n    if header_lang.startswith('ro'):\\n        return 'ro'\\n    if header_lang.startswith('it'):\\n        return 'it'\\n    cookie_lang = (request.cookies.get('hm_user_lang') or '').lower()\\n    if cookie_lang in ('it','de','ro'):\\n        return cookie_lang\\n"\nif old in text:\n    text=text.replace(old,new,1)\npath.write_text(text,encoding='utf-8')\n

# Per-user language bridge: the HA frontend can pass its current hass.language
# in the query string once; we store it only in that browser session cookie.
old_public_lang = """def public_language(request: Request):
    header_lang = (request.headers.get('X-Hass-Language') or request.headers.get('X-Hass-Locale') or '').lower()
    if header_lang.startswith('de'):
        return 'de'
    if header_lang.startswith('ro'):
        return 'ro'
    if header_lang.startswith('it'):
        return 'it'
    cookie_lang = (request.cookies.get('hm_user_lang') or '').lower()
    if cookie_lang in ('it','de','ro'):
        return cookie_lang
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'
"""
new_public_lang = """def public_language(request: Request):
    requested = (request.query_params.get('ha_lang') or '').lower().replace('_','-')
    if requested.startswith('de'):
        return 'de'
    if requested.startswith('ro'):
        return 'ro'
    if requested.startswith('it'):
        return 'it'
    cookie_lang = (request.cookies.get('hm_user_lang') or '').lower()
    if cookie_lang in ('it','de','ro'):
        return cookie_lang
    header_lang = (request.headers.get('X-Hass-Language') or request.headers.get('X-Hass-Locale') or '').lower()
    if header_lang.startswith('de'):
        return 'de'
    if header_lang.startswith('ro'):
        return 'ro'
    if header_lang.startswith('it'):
        return 'it'
    preferred = request.headers.get('accept-language', '').split(',', 1)[0].lower()
    if preferred.startswith('de'):
        return 'de'
    if preferred.startswith('ro'):
        return 'ro'
    return 'it'
"""
if old_public_lang in text:
    text = text.replace(old_public_lang,new_public_lang,1)

# Do not force navigator.language over a language already selected for this HA user.
old_sync = "var l=(navigator.language||navigator.userLanguage||'it').toLowerCase().split('-')[0];"
new_sync = "var p=new URLSearchParams(location.search);var l=(p.get('ha_lang')||'').toLowerCase().split('-')[0];if(!l){var m=document.cookie.match(/(?:^|; )hm_user_lang=([^;]+)/);l=m?decodeURIComponent(m[1]):'';}if(!l){l=(navigator.language||navigator.userLanguage||'it').toLowerCase().split('-')[0];}"
if old_sync in text:
    text = text.replace(old_sync,new_sync,1)

path.write_text(text,encoding='utf-8')


# Read the language preference stored by Home Assistant for the authenticated user.
HA_USER_LANG_CACHE = {}

def _ha_ws_user_language(user_id):
    if not user_id or websocket is None:
        return ''
    cached = HA_USER_LANG_CACHE.get(user_id)
    now = time.monotonic()
    if cached and now - cached[0] < 60:
        return cached[1]
    token = os.environ.get('SUPERVISOR_TOKEN', '')
    if not token:
        return ''
    connection = None
    try:
        connection = websocket.create_connection('ws://supervisor/core/websocket', timeout=5)
        hello = json.loads(connection.recv())
        if hello.get('type') != 'auth_required':
            return ''
        connection.send(json.dumps(dict(type='auth', access_token=token)))
        if json.loads(connection.recv()).get('type') != 'auth_ok':
            return ''
        # Home Assistant frontend preference is stored per user.
        commands = [
            dict(id=71, type='frontend/get_user_data', key='language', user_id=user_id),
            dict(id=72, type='frontend/get_user_data', user_id=user_id),
        ]
        for command in commands:
            connection.send(json.dumps(command))
            result = json.loads(connection.recv())
            if not result.get('success'):
                continue
            data = result.get('result')
            values = []
            if isinstance(data, str):
                values.append(data)
            elif isinstance(data, dict):
                for key in ('language','selectedLanguage','selected_language','locale'):
                    if data.get(key):
                        values.append(str(data[key]))
                nested = data.get('language')
                if isinstance(nested, dict):
                    values.extend(str(v) for v in nested.values() if v)
            for value in values:
                value = value.lower().replace('_','-')
                if value.startswith('de'):
                    HA_USER_LANG_CACHE[user_id] = (now,'de'); return 'de'
                if value.startswith('ro'):
                    HA_USER_LANG_CACHE[user_id] = (now,'ro'); return 'ro'
                if value.startswith('it'):
                    HA_USER_LANG_CACHE[user_id] = (now,'it'); return 'it'
    except Exception:
        pass
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    return ''

# Insert the authenticated HA user preference before browser/cookie fallbacks.
needle = """def public_language(request: Request):
    requested = (request.query_params.get('ha_lang') or '').lower().replace('_','-')
"""
replacement = """def public_language(request: Request):
    identity = ingress_identity(request)
    ha_lang = _ha_ws_user_language(identity.get('id',''))
    if ha_lang:
        return ha_lang
    requested = (request.query_params.get('ha_lang') or '').lower().replace('_','-')
"""
if needle in text:
    text = text.replace(needle,replacement,1)

path.write_text(text,encoding='utf-8')


# Deterministic language preference stored per authenticated Home Assistant user.
def _user_language_key(request):
    identity = ingress_identity(request)
    user_id = identity.get('id','').strip()
    return 'ha_user_language_' + user_id if user_id else ''

def _saved_user_language(request):
    key = _user_language_key(request)
    if not key:
        return ''
    value = get_setting(key, '').strip().lower()
    return value if value in ('it','de','ro') else ''

# Make saved per-user preference the first choice.
needle_lang = """def public_language(request: Request):
    identity = ingress_identity(request)
    ha_lang = _ha_ws_user_language(identity.get('id',''))
"""
replacement_lang = """def public_language(request: Request):
    saved_lang = _saved_user_language(request)
    if saved_lang:
        return saved_lang
    identity = ingress_identity(request)
    ha_lang = _ha_ws_user_language(identity.get('id',''))
"""
if needle_lang in text:
    text = text.replace(needle_lang,replacement_lang,1)

# Add a compact personal language selector to every authenticated manager/admin page.
page_needle = """    settings_link = '<a class="side-link" href="settings" onclick="return adminGo(\\'settings\\')">⚙ Impostazioni</a>' if CURRENT_INGRESS_IS_ADMIN.get() else ''
"""
page_repl = """    settings_link = '<a class="side-link" href="settings" onclick="return adminGo(\\'settings\\')">⚙ Impostazioni</a>' if CURRENT_INGRESS_IS_ADMIN.get() else ''
    language_selector = f'''<form method="post" action="user-language" onsubmit="return languageGo(this)" style="margin:10px 0 14px"><select name="language" onchange="languageGo(this.form)" style="margin:0;padding:9px 10px;background:#24343e;color:#fff;border:1px solid #ffffff30"><option value="it" {"selected" if lang=="it" else ""}>🇮🇹 Italiano</option><option value="de" {"selected" if lang=="de" else ""}>🇩🇪 Deutsch</option><option value="ro" {"selected" if lang=="ro" else ""}>🇷🇴 Română</option></select><input type="hidden" name="next_url" value=""></form>'''
"""
if page_needle in text:
    text = text.replace(page_needle,page_repl,1)

# Put selector in sidebar before footer where possible.
side_needle = """{settings_link}"""
if side_needle in text and "{language_selector}" not in text:
    text = text.replace(side_needle, side_needle + "{language_selector}", 1)

# Route on both admin ingress and public manager app.
route_marker = "@admin_app.get('/', response_class=HTMLResponse)"
routes = r'''
def _save_user_language(request: Request, language: str):
    if language not in ('it','de','ro'):
        raise HTTPException(400, 'Lingua non valida')
    key = _user_language_key(request)
    if key:
        set_setting(key, language)

@admin_app.post('/user-language')
def admin_user_language(request: Request, language: str = Form(...)):
    _save_user_language(request, language)
    return RedirectResponse(request.headers.get('referer') or './', status_code=303)

@public_app.post('/manager/user-language')
def manager_user_language(request: Request, language: str = Form(...)):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    _save_user_language(request, language)
    return RedirectResponse(request.headers.get('referer') or '/manager', status_code=303)

'''
if "@admin_app.post('/user-language')" not in text and route_marker in text:
    text = text.replace(route_marker,routes+route_marker,1)


# Make language switching ingress-safe: absolute /user-language points to Home Assistant and returns 404.
js_marker = "<script>function adminGo(path){{"
js_repl = """<script>function languageGo(form){try{const marker='/api/hassio_ingress/';const current=location.pathname;const start=current.indexOf(marker);if(start>=0){const after=start+marker.length;const slash=current.indexOf('/',after);const base=slash>=0?current.slice(0,slash+1):current+'/';form.action=base+'user-language';}else{form.action='/manager/user-language';}form.submit();}catch(e){form.submit();}return false;}function adminGo(path){{"""
if js_marker in text and "function languageGo(form)" not in text:
    text = text.replace(js_marker, js_repl, 1)

path.write_text(text,encoding='utf-8')
