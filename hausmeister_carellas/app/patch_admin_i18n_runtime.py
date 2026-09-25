from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# 1) Make the language choice truly per HA user: on every ingress request,
# refresh the browser cookie from the preference stored under that HA user id.
old_admin = """    if identity['is_admin']:
        return await call_next(request)
"""
new_admin = """    if identity['is_admin']:
        response = await call_next(request)
        saved_lang = get_setting('ha_user_language_' + identity['id'], '').strip().lower()
        if saved_lang in ('it','de','ro'):
            response.set_cookie('hm_user_lang', saved_lang, max_age=31536000, samesite='lax', path='/')
        return response
"""
if old_admin in text:
    text = text.replace(old_admin, new_admin, 1)

old_nonadmin = """    context_token = CURRENT_INGRESS_IS_ADMIN.set(False)
    try:
        return await call_next(request)
    finally:
        CURRENT_INGRESS_IS_ADMIN.reset(context_token)
"""
new_nonadmin = """    context_token = CURRENT_INGRESS_IS_ADMIN.set(False)
    try:
        response = await call_next(request)
        saved_lang = get_setting('ha_user_language_' + identity['id'], '').strip().lower()
        if saved_lang in ('it','de','ro'):
            response.set_cookie('hm_user_lang', saved_lang, max_age=31536000, samesite='lax', path='/')
        return response
    finally:
        CURRENT_INGRESS_IS_ADMIN.reset(context_token)
"""
if old_nonadmin in text:
    text = text.replace(old_nonadmin, new_nonadmin, 1)

# 2) Language POST must set the cookie immediately, then reload the same page.
old_post = """@admin_app.post('/user-language')
def admin_user_language(request: Request, language: str = Form(...)):
    _save_user_language(request, language)
    return RedirectResponse(request.headers.get('referer') or './', status_code=303)
"""
new_post = """@admin_app.post('/user-language')
def admin_user_language(request: Request, language: str = Form(...)):
    _save_user_language(request, language)
    response = RedirectResponse(request.headers.get('referer') or './', status_code=303)
    response.set_cookie('hm_user_lang', language, max_age=31536000, samesite='lax', path='/')
    return response
"""
if old_post in text:
    text = text.replace(old_post, new_post, 1)

old_manager_post = """@public_app.post('/manager/user-language')
def manager_user_language(request: Request, language: str = Form(...)):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    _save_user_language(request, language)
    return RedirectResponse(request.headers.get('referer') or '/manager', status_code=303)
"""
new_manager_post = """@public_app.post('/manager/user-language')
def manager_user_language(request: Request, language: str = Form(...)):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    _save_user_language(request, language)
    response = RedirectResponse(request.headers.get('referer') or '/manager', status_code=303)
    response.set_cookie('hm_user_lang', language, max_age=31536000, samesite='lax', path='/')
    return response
"""
if old_manager_post in text:
    text = text.replace(old_manager_post, new_manager_post, 1)

# 3) Client-side translation for the admin interface. This is necessary because
# many admin pages were historically written directly in Italian instead of using MANAGER_TEXT.
page_marker = """    access_label = 'Add-on in esecuzione' if CURRENT_INGRESS_IS_ADMIN.get() else 'Accesso titolare'
"""
if page_marker in text and "hmApplyUiLanguage" not in text:
    locale_block = """    locale_script = r'''<script>
function hmCookie(name){
  const hit=document.cookie.split('; ').find(x=>x.startsWith(name+'='));
  return hit?decodeURIComponent(hit.substring(name.length+1)):'';
}
const HM_I18N={
de:{
'Dashboard':'Dashboard','Ticket':'Tickets','Zone / QR':'Bereiche / QR','Magazzino materiali':'Materiallager',
'Impostazioni':'Einstellungen','Indietro':'Zurück','Home Assistant':'Home Assistant',
'Gestione manutenzioni Carellas':'Carellas Wartungsverwaltung','Add-on in esecuzione':'Add-on läuft',
'Accesso titolare':'Inhaberzugang','Totale ticket':'Tickets gesamt','Aperti':'Offen',
'In lavorazione':'In Bearbeitung','Risolti':'Erledigt','Ticket recenti':'Aktuelle Tickets',
'Vedi tutti i ticket':'Alle Tickets anzeigen','Materiali da acquistare':'Material nachbestellen',
'Zone esistenti':'Vorhandene Bereiche','Nuova zona':'Neuer Bereich','Nome':'Name',
'Crea zona e QR':'Bereich und QR erstellen','Attiva':'Aktiv','Disattivata':'Deaktiviert',
'Gestisci / QR':'Verwalten / QR','Crea ticket':'Ticket erstellen','Scarica QR':'QR herunterladen',
'Stampa':'Drucken','Modifica zona':'Bereich bearbeiten','Nome della zona':'Bereichsname',
'Salva nome':'Name speichern','Elimina zona':'Bereich löschen','Ticket collegati':'Verknüpfte Tickets',
'Cerca':'Suchen','Stato':'Status','Tutti gli stati':'Alle Status','Zona':'Bereich',
'Segnalato da':'Gemeldet von','Categoria':'Kategorie','Priorità':'Priorität','Nuovo':'Neu',
'Preso in carico':'Übernommen','Da verificare':'Zu prüfen','Risolto':'Erledigt',
'Materiali':'Material','Tutti gli articoli':'Alle Artikel','Solo da acquistare':'Nur nachzubestellen',
'Nuovo articolo':'Neuer Artikel','Descrizione':'Beschreibung','Posizione':'Position',
'Fornitore':'Lieferant','Quantità':'Menge','Salva articolo':'Artikel speichern',
'Carica materiale':'Material einlagern','Scarica materiale':'Material entnehmen',
'Movimenti recenti':'Letzte Bewegungen','Note interne / soluzione':'Interne Notizen / Lösung',
'Salva modifiche':'Änderungen speichern','Foto':'Fotos','Nessuna foto':'Keine Fotos'
},
ro:{
'Dashboard':'Panou de control','Ticket':'Tichete','Zone / QR':'Zone / QR','Magazzino materiali':'Depozit materiale',
'Impostazioni':'Setări','Indietro':'Înapoi','Home Assistant':'Home Assistant',
'Gestione manutenzioni Carellas':'Gestionare mentenanță Carellas','Add-on in esecuzione':'Add-on activ',
'Accesso titolare':'Acces proprietar','Totale ticket':'Total tichete','Aperti':'Deschise',
'In lavorazione':'În lucru','Risolti':'Rezolvate','Ticket recenti':'Tichete recente',
'Vedi tutti i ticket':'Vezi toate tichetele','Materiali da acquistare':'Materiale de cumpărat',
'Zone esistenti':'Zone existente','Nuova zona':'Zonă nouă','Nome':'Nume',
'Crea zona e QR':'Creează zona și QR','Attiva':'Activă','Disattivata':'Dezactivată',
'Gestisci / QR':'Gestionează / QR','Crea ticket':'Creează tichet','Scarica QR':'Descarcă QR',
'Stampa':'Tipărește','Modifica zona':'Modifică zona','Nome della zona':'Numele zonei',
'Salva nome':'Salvează numele','Elimina zona':'Șterge zona','Ticket collegati':'Tichete asociate',
'Cerca':'Caută','Stato':'Stare','Tutti gli stati':'Toate stările','Zona':'Zonă',
'Segnalato da':'Raportat de','Categoria':'Categorie','Priorità':'Prioritate','Nuovo':'Nou',
'Preso in carico':'Preluat','Da verificare':'De verificat','Risolto':'Rezolvat',
'Materiali':'Materiale','Tutti gli articoli':'Toate articolele','Solo da acquistare':'Doar de cumpărat',
'Nuovo articolo':'Articol nou','Descrizione':'Descriere','Posizione':'Poziție',
'Fornitore':'Furnizor','Quantità':'Cantitate','Salva articolo':'Salvează articolul',
'Carica materiale':'Încarcă material','Scarica materiale':'Descarcă material',
'Movimenti recenti':'Mișcări recente','Note interne / soluzione':'Note interne / soluție',
'Salva modifiche':'Salvează modificările','Foto':'Fotografii','Nessuna foto':'Nicio fotografie'
}};
function hmApplyUiLanguage(){
  const lang=hmCookie('hm_user_lang')||'it';
  const select=document.querySelector('select[name="language"]');
  if(select) select.value=lang;
  if(lang==='it'||!HM_I18N[lang]) return;
  const dict=HM_I18N[lang];
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  const nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(n=>{
    const raw=n.nodeValue, t=raw.trim();
    if(dict[t]) n.nodeValue=raw.replace(t,dict[t]);
  });
  document.querySelectorAll('input[placeholder],textarea[placeholder]').forEach(el=>{
    const p=el.getAttribute('placeholder'); if(dict[p]) el.setAttribute('placeholder',dict[p]);
  });
  document.documentElement.lang=lang;
}
document.addEventListener('DOMContentLoaded',hmApplyUiLanguage);
</script>'''
"""
    text = text.replace(page_marker, page_marker + locale_block, 1)
    text = text.replace('<head>{locale_sync}', '<head>{locale_sync}{locale_script}', 1)
    if '<head>{locale_sync}{locale_script}' not in text:
        text = text.replace('<head><meta charset=', '<head>{locale_script}<meta charset=', 1)

path.write_text(text, encoding='utf-8')
