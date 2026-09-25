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