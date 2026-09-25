from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# One clean manager/admin patch. Language logic follows Dimensionamento Climatizzazione Pro:
# data-language buttons + localStorage + client-side dictionary + MutationObserver.

# Keep displayed version aligned.
text = text.replace("APP_VERSION = '1.5.16'", "APP_VERSION = '1.5.42'", 1)

# Make dashboard metric cards clickable without changing the working tickets route.
metric_replacements = {
    '''<div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></div>''':
    '''<a class="card span-3" href="/manager/tickets" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></a>''',
    '''<div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></div>''':
    '''<a class="card span-3" href="/manager/tickets?status=Nuovo" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></a>''',
    '''<div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></div>''':
    '''<a class="card span-3" href="/manager/tickets?status=In%20lavorazione" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></a>''',
    '''<div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></div>''':
    '''<a class="card span-3" href="/manager/tickets?status=Risolto" style="text-decoration:none;color:inherit"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></a>''',
}
for old,new in metric_replacements.items():
    if old in text:
        text = text.replace(old,new,1)

# Add direct ticket creation from owner zone detail.
zone_action = '''<div class="actions" style="margin-top:12px"><a class="btn" href="/manager/zone/{zone_id}/qr?download=1">'''
if zone_action in text:
    text = text.replace(
        zone_action,
        '''<div class="actions" style="margin-top:12px"><a class="btn" href="{esc(url)}">➕ Crea ticket</a><a class="btn" href="/manager/zone/{zone_id}/qr?download=1">''',
        1,
    )

# Context var with the HA user id, so localStorage is separate per user.
ctx = "CURRENT_INGRESS_IS_ADMIN = ContextVar('current_ingress_is_admin', default=True)\n"
if ctx in text and "CURRENT_HA_USER_ID = ContextVar" not in text:
    text = text.replace(ctx, ctx + "CURRENT_HA_USER_ID = ContextVar('current_ha_user_id', default='')\n", 1)

apps = "public_app = FastAPI(title='Hausmeister Carellas Public')\n"
if apps in text and "async def hm_user_context" not in text:
    middleware = r'''

@admin_app.middleware('http')
async def hm_user_context(request: Request, call_next):
    identity = ingress_identity(request)
    token = CURRENT_HA_USER_ID.set((identity.get('id') or '').strip())
    try:
        return await call_next(request)
    finally:
        CURRENT_HA_USER_ID.reset(token)

'''
    text = text.replace(apps, apps + middleware, 1)

# Patch page() directly.
start = text.find("def page(")
end = text.find("\n\ndef session_zone", start)
if start < 0 or end < 0:
    raise SystemExit("page() block not found")
block = text[start:end]

header = "def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):\n"
if header not in block:
    raise SystemExit("page header not found")

new_header = r'''def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):
    hm_user_id = CURRENT_HA_USER_ID.get() or 'anonymous'
    saved_language = get_setting('ha_user_language_' + hm_user_id, '').strip().lower() if hm_user_id != 'anonymous' else ''
    default_language = saved_language if saved_language in ('it','de','ro') else 'it'
    language_selector = '<div class="hm-language-switch" role="group" aria-label="Lingua / Sprache / Limbă"><button type="button" data-language="it">IT</button><button type="button" data-language="de">DE</button><button type="button" data-language="ro">RO</button></div>'
    hm_i18n = r"""<style>
.hm-language-switch{display:flex;gap:6px;margin:10px 0 14px}
.hm-language-switch button{min-height:38px;padding:7px 11px;border:1px solid #ffffff35;background:#24343e;color:#fff;border-radius:8px}
.hm-language-switch button.active{background:#6e7d08;border-color:#9aaa23}
.hm-group-ticket{display:inline-flex;margin:0 10px 8px;padding:8px 11px;border-radius:9px;background:#6e7d08;color:#fff;text-decoration:none;font-weight:700}
</style><script>
(function(){
  const messagesDe={
    'Gestione manutenzioni Carellas':'Carellas Wartungsverwaltung','Add-on in esecuzione':'Add-on läuft','Accesso titolare':'Inhaberzugang',
    'Indietro':'Zurück','Dashboard':'Dashboard','Ticket recenti':'Aktuelle Tickets','Ticket':'Tickets','Zone / QR':'Bereiche / QR',
    'Magazzino materiali':'Materiallager','Manutenzioni':'Wartungen','Impostazioni':'Einstellungen','Materiali da acquistare':'Material nachbestellen',
    'Totale ticket':'Tickets gesamt','Aperti':'Offen','In lavorazione':'In Bearbeitung','Risolti':'Erledigt','Vedi tutti i ticket':'Alle Tickets anzeigen',
    'Zona':'Bereich','Zone':'Bereiche','Segnalato da':'Gemeldet von','Priorità':'Priorität','Stato':'Status','Categoria':'Kategorie',
    'Urgente':'Dringend','Alta':'Hoch','Normale':'Normal','Bassa':'Niedrig','Nuovo':'Neu','Preso in carico':'Übernommen','Da verificare':'Zu prüfen',
    'Risolto':'Erledigt','Senza gruppo':'Ohne Gruppe','Attiva':'Aktiv','Disattivata':'Deaktiviert','Zone esistenti':'Vorhandene Bereiche',
    'Nuova zona':'Neuer Bereich','Nome':'Name','Crea zona e QR':'Bereich und QR erstellen','Gestisci / QR':'Verwalten / QR',
    'Crea ticket':'Ticket erstellen','Scarica QR':'QR herunterladen','Stampa':'Drucken','Modifica zona':'Bereich bearbeiten',
    'Nome della zona':'Bereichsname','Salva nome':'Name speichern','Elimina zona':'Bereich löschen','Ticket collegati':'Verknüpfte Tickets',
    'Cerca':'Suchen','Tutti gli stati':'Alle Status','Tutti gli articoli':'Alle Artikel','Solo da acquistare':'Nur nachzubestellen',
    'Nuovo articolo':'Neuer Artikel','Descrizione':'Beschreibung','Posizione':'Position','Fornitore':'Lieferant','Quantità':'Menge',
    'Salva articolo':'Artikel speichern','Carica materiale':'Material einlagern','Scarica materiale':'Material entnehmen',
    'Movimenti recenti':'Letzte Bewegungen','Note interne / soluzione':'Interne Notizen / Lösung','Salva modifiche':'Änderungen speichern',
    'Foto':'Fotos','Nessuna foto':'Keine Fotos','Scorta disponibile':'Bestand verfügbar','Da acquistare':'Nachbestellen',
    'Codice articolo':'Artikelnummer','Unità':'Einheit','Nuovo ticket':'Neues Ticket','Tipo di guasto':'Störungsart',
    'Descrivi il problema nel dettaglio':'Problem ausführlich beschreiben','Nome e cognome':'Vor- und Nachname','Invia segnalazione':'Meldung senden',
    'Nessuna zona':'Keine Bereiche','Gruppi di zone':'Bereichsgruppen','Gestisci gruppi':'Gruppen verwalten','Assegna zone':'Bereiche zuweisen',
    'Nuovo gruppo':'Neue Gruppe','Nome gruppo':'Gruppenname','Crea gruppo':'Gruppe erstellen','Elimina':'Löschen',
    'Salva assegnazione':'Zuordnung speichern','QR Zone':'Bereichs-QR','Scarica tutti i QR':'Alle QR herunterladen'
  };
  const messagesRo={
    'Gestione manutenzioni Carellas':'Gestionare mentenanță Carellas','Add-on in esecuzione':'Add-on activ','Accesso titolare':'Acces proprietar',
    'Indietro':'Înapoi','Dashboard':'Panou de control','Ticket recenti':'Tichete recente','Ticket':'Tichete','Zone / QR':'Zone / QR',
    'Magazzino materiali':'Depozit materiale','Manutenzioni':'Mentenanțe','Impostazioni':'Setări','Materiali da acquistare':'Materiale de cumpărat',
    'Totale ticket':'Total tichete','Aperti':'Deschise','In lavorazione':'În lucru','Risolti':'Rezolvate','Vedi tutti i ticket':'Vezi toate tichetele',
    'Zona':'Zonă','Zone':'Zone','Segnalato da':'Raportat de','Priorità':'Prioritate','Stato':'Stare','Categoria':'Categorie',
    'Urgente':'Urgent','Alta':'Ridicată','Normale':'Normală','Bassa':'Scăzută','Nuovo':'Nou','Preso in carico':'Preluat','Da verificare':'De verificat',
    'Risolto':'Rezolvat','Senza gruppo':'Fără grup','Attiva':'Activă','Disattivata':'Dezactivată','Zone esistenti':'Zone existente',
    'Nuova zona':'Zonă nouă','Nome':'Nume','Crea zona e QR':'Creează zona și QR','Gestisci / QR':'Gestionează / QR',
    'Crea ticket':'Creează tichet','Scarica QR':'Descarcă QR','Stampa':'Tipărește','Modifica zona':'Modifică zona',
    'Nome della zona':'Numele zonei','Salva nome':'Salvează numele','Elimina zona':'Șterge zona','Ticket collegati':'Tichete asociate',
    'Cerca':'Caută','Tutti gli stati':'Toate stările','Tutti gli articoli':'Toate articolele','Solo da acquistare':'Doar de cumpărat',
    'Nuovo articolo':'Articol nou','Descrizione':'Descriere','Posizione':'Poziție','Fornitore':'Furnizor','Quantità':'Cantitate',
    'Salva articolo':'Salvează articolul','Carica materiale':'Încarcă material','Scarica materiale':'Descarcă material',
    'Movimenti recenti':'Mișcări recente','Note interne / soluzione':'Note interne / soluție','Salva modifiche':'Salvează modificările',
    'Foto':'Fotografii','Nessuna foto':'Nicio fotografie','Nuovo ticket':'Tichet nou','Tipo di guasto':'Tip defecțiune',
    'Nome e cognome':'Nume și prenume','Invia segnalazione':'Trimite sesizarea','Nessuna zona':'Nicio zonă',
    'Gruppi di zone':'Grupuri de zone','Gestisci gruppi':'Gestionează grupurile','Assegna zone':'Atribuie zone',
    'Nuovo gruppo':'Grup nou','Nome gruppo':'Numele grupului','Crea gruppo':'Creează grup','Elimina':'Șterge',
    'Salva assegnazione':'Salvează atribuirea','QR Zone':'QR Zone','Scarica tutti i QR':'Descarcă toate QR-urile'
  };
  Object.assign(messagesDe,{
    'Password zone singole':'Passwort für einzelne Bereiche',
    'Usata dai QR che aprono direttamente una zona.':'Wird von QR-Codes verwendet, die direkt einen Bereich öffnen.',
    'Password salvata':'Gespeichertes Passwort','Inserisci nuovamente la password':'Passwort erneut eingeben',
    'Salva password zone':'Bereichspasswort speichern','Password QR di gruppo':'Gruppen-QR-Passwort',
    'È diversa dalla password delle singole zone e permette di scegliere una delle zone attive.':'Es unterscheidet sich vom Passwort der einzelnen Bereiche und ermöglicht die Auswahl eines aktiven Bereichs.',
    'Password di gruppo salvata':'Gespeichertes Gruppenpasswort','Crea la password di gruppo':'Gruppenpasswort erstellen',
    'Salva password di gruppo':'Gruppenpasswort speichern','QR con tutte le zone':'QR mit allen Bereichen',
    'Prima salva la password di gruppo.':'Speichere zuerst das Gruppenpasswort.','Configurazione':'Konfiguration',
    'URL pubblico:':'Öffentliche URL:','Traduzione automatica:':'Automatische Übersetzung:',
    'Automatica integrata (Google con MyMemory di riserva)':'Integrierte Automatik (Google mit MyMemory als Reserve)',
    "URL e traduzione si modificano nella scheda Configurazione dell'add-on di Home Assistant.":"URL und Übersetzung werden in der Konfiguration des Home-Assistant-Add-ons geändert.",
    'Dispositivi per le notifiche':'Geräte für Benachrichtigungen',
    'I nuovi ticket vengono inviati a tutti i dispositivi attivi. Puoi modificarli anche quando cambi telefono.':'Neue Tickets werden an alle aktiven Geräte gesendet. Du kannst sie auch nach einem Telefonwechsel ändern.',
    'Rileva dispositivi da Home Assistant':'Geräte aus Home Assistant erkennen','Diagnostica rilevamento:':'Erkennungsdiagnose:',
    'Aggiunta manuale':'Manuell hinzufügen','Nome dispositivo':'Gerätename','Entità/azione di notifica':'Benachrichtigungs-Entität/Aktion',
    'Entità/azione':'Entität/Aktion','Aggiungi dispositivo':'Gerät hinzufügen','Dispositivo attivo':'Gerät aktiv',
    'Invia prova':'Test senden','Eliminare questo dispositivo?':'Dieses Gerät löschen?','Nessun dispositivo configurato.':'Kein Gerät konfiguriert.',
    'Accesso degli utenti Home Assistant':'Zugriff für Home-Assistant-Benutzer',
    'Abilita uno o più utenti Home Assistant non amministratori. Gli utenti abilitati avranno la stessa interfaccia operativa dell’amministratore per ticket, zone, QR e magazzino; l’intera area Impostazioni resterà riservata agli amministratori.':'Aktiviere einen oder mehrere Home-Assistant-Benutzer ohne Administratorrechte. Aktivierte Benutzer erhalten dieselbe Bedienoberfläche für Tickets, Bereiche, QR und Lager; der gesamte Bereich Einstellungen bleibt Administratoren vorbehalten.',
    'Utente':'Benutzer','Azione':'Aktion','Abilita':'Aktivieren','Disabilita':'Deaktivieren','Abilitato':'Aktiviert','Disabilitato':'Deaktiviert',
    'non rilevato in Home Assistant':'in Home Assistant nicht erkannt','Nessun utente Home Assistant non amministratore disponibile.':'Kein Home-Assistant-Benutzer ohne Administratorrechte verfügbar.',
    'Diagnostica:':'Diagnose:','Apri almeno una volta Home Assistant con il nuovo utente e torna qui.':'Öffne Home Assistant mindestens einmal mit dem neuen Benutzer und kehre dann hierher zurück.',
    'Utenti non amministratori disponibili:':'Verfügbare Benutzer ohne Administratorrechte:',
    'Accesso del titolare esterno':'Externer Inhaberzugang',
    'Portale separato da Home Assistant. Il titolare può gestire ticket, zone, QR e magazzino materiali. Impostazioni, PIN, telefoni e configurazioni tecniche restano riservati all’amministratore.':'Separates Portal von Home Assistant. Der Inhaber kann Tickets, Bereiche, QR-Codes und das Materiallager verwalten. Einstellungen, PINs, Telefone und technische Konfigurationen bleiben dem Administrator vorbehalten.',
    'Indirizzo del portale:':'Portaladresse:','Nome utente del titolare':'Benutzername des Inhabers','Nuova password':'Neues Passwort',
    'Lascia vuoto per conservare la password attuale.':'Leer lassen, um das aktuelle Passwort beizubehalten.',
    'Crea una password di almeno 8 caratteri.':'Erstelle ein Passwort mit mindestens 8 Zeichen.',
    'La password viene protetta e non può essere visualizzata: se viene dimenticata, puoi sostituirla qui.':'Das Passwort wird geschützt und kann nicht angezeigt werden. Falls es vergessen wird, kann es hier ersetzt werden.',
    'Portale Titolare attivo':'Inhaberportal aktiv','Salva accesso titolare esterno':'Externen Inhaberzugang speichern',
    'Backup':'Sicherung','Scarica database e fotografie in un unico archivio ZIP.':'Datenbank und Fotos in einem einzigen ZIP-Archiv herunterladen.',
    'Scarica backup':'Sicherung herunterladen','Non configurato':'Nicht konfiguriert',
    'La vecchia password è protetta e non recuperabile: salvala nuovamente una sola volta per renderla visibile.':'Das alte Passwort ist geschützt und kann nicht wiederhergestellt werden. Speichere es einmal neu, damit es sichtbar wird.',
    'Imposta la password per i QR delle singole zone.':'Lege das Passwort für die QR-Codes der einzelnen Bereiche fest.',
    'Esporta CSV':'CSV exportieren','Codice, zona, nome o descrizione':'Code, Bereich, Name oder Beschreibung',
    'Nessun ticket trovato':'Keine Tickets gefunden','Nessun ticket':'Keine Tickets','Scorte basse':'Niedriger Bestand',
    'Ticket totali':'Tickets gesamt','Nuovi':'Neu','Sola lettura:':'Nur Lesen:','Dispositivo':'Gerät'
  });
  Object.assign(messagesRo,{
    'Password zone singole':'Parolă pentru zone individuale',
    'Usata dai QR che aprono direttamente una zona.':'Folosită de codurile QR care deschid direct o zonă.',
    'Password salvata':'Parolă salvată','Inserisci nuovamente la password':'Introdu din nou parola',
    'Salva password zone':'Salvează parola zonelor','Password QR di gruppo':'Parolă QR de grup',
    'È diversa dalla password delle singole zone e permette di scegliere una delle zone attive.':'Este diferită de parola zonelor individuale și permite alegerea unei zone active.',
    'Password di gruppo salvata':'Parolă de grup salvată','Crea la password di gruppo':'Creează parola de grup',
    'Salva password di gruppo':'Salvează parola de grup','QR con tutte le zone':'QR cu toate zonele',
    'Prima salva la password di gruppo.':'Mai întâi salvează parola de grup.','Configurazione':'Configurare',
    'URL pubblico:':'URL public:','Traduzione automatica:':'Traducere automată:',
    'Automatica integrata (Google con MyMemory di riserva)':'Automată integrată (Google cu MyMemory de rezervă)',
    "URL e traduzione si modificano nella scheda Configurazione dell'add-on di Home Assistant.":"URL-ul și traducerea se modifică în configurația add-on-ului Home Assistant.",
    'Dispositivi per le notifiche':'Dispozitive pentru notificări',
    'I nuovi ticket vengono inviati a tutti i dispositivi attivi. Puoi modificarli anche quando cambi telefono.':'Tichetele noi sunt trimise tuturor dispozitivelor active. Le poți modifica și când schimbi telefonul.',
    'Rileva dispositivi da Home Assistant':'Detectează dispozitive din Home Assistant','Diagnostica rilevamento:':'Diagnostic detectare:',
    'Aggiunta manuale':'Adăugare manuală','Nome dispositivo':'Nume dispozitiv','Entità/azione di notifica':'Entitate/acțiune notificare',
    'Entità/azione':'Entitate/acțiune','Aggiungi dispositivo':'Adaugă dispozitiv','Dispositivo attivo':'Dispozitiv activ',
    'Invia prova':'Trimite test','Eliminare questo dispositivo?':'Ștergi acest dispozitiv?','Nessun dispositivo configurato.':'Niciun dispozitiv configurat.',
    'Accesso degli utenti Home Assistant':'Acces utilizatori Home Assistant',
    'Abilita uno o più utenti Home Assistant non amministratori. Gli utenti abilitati avranno la stessa interfaccia operativa dell’amministratore per ticket, zone, QR e magazzino; l’intera area Impostazioni resterà riservata agli amministratori.':'Activează unul sau mai mulți utilizatori Home Assistant fără drepturi de administrator. Utilizatorii activați vor avea aceeași interfață pentru tichete, zone, QR și depozit; zona Setări rămâne rezervată administratorilor.',
    'Utente':'Utilizator','Azione':'Acțiune','Abilita':'Activează','Disabilita':'Dezactivează','Abilitato':'Activat','Disabilitato':'Dezactivat',
    'non rilevato in Home Assistant':'nedetectat în Home Assistant','Nessun utente Home Assistant non amministratore disponibile.':'Niciun utilizator Home Assistant fără drepturi de administrator disponibil.',
    'Diagnostica:':'Diagnostic:','Apri almeno una volta Home Assistant con il nuovo utente e torna qui.':'Deschide Home Assistant cel puțin o dată cu noul utilizator și revino aici.',
    'Utenti non amministratori disponibili:':'Utilizatori fără drepturi de administrator disponibili:',
    'Accesso del titolare esterno':'Acces extern proprietar',
    'Portale separato da Home Assistant. Il titolare può gestire ticket, zone, QR e magazzino materiali. Impostazioni, PIN, telefoni e configurazioni tecniche restano riservati all’amministratore.':'Portal separat de Home Assistant. Proprietarul poate gestiona tichete, zone, QR și depozitul de materiale. Setările, PIN-urile, telefoanele și configurațiile tehnice rămân rezervate administratorului.',
    'Indirizzo del portale:':'Adresa portalului:','Nome utente del titolare':'Nume utilizator proprietar','Nuova password':'Parolă nouă',
    'Lascia vuoto per conservare la password attuale.':'Lasă gol pentru a păstra parola actuală.',
    'Crea una password di almeno 8 caratteri.':'Creează o parolă de cel puțin 8 caractere.',
    'La password viene protetta e non può essere visualizzata: se viene dimenticata, puoi sostituirla qui.':'Parola este protejată și nu poate fi afișată. Dacă este uitată, o poți înlocui aici.',
    'Portale Titolare attivo':'Portal proprietar activ','Salva accesso titolare esterno':'Salvează accesul extern al proprietarului',
    'Backup':'Copie de siguranță','Scarica database e fotografie in un unico archivio ZIP.':'Descarcă baza de date și fotografiile într-o singură arhivă ZIP.',
    'Scarica backup':'Descarcă copia de siguranță','Non configurato':'Neconfigurat',
    'La vecchia password è protetta e non recuperabile: salvala nuovamente una sola volta per renderla visibile.':'Parola veche este protejată și nu poate fi recuperată. Salveaz-o din nou o singură dată pentru a deveni vizibilă.',
    'Imposta la password per i QR delle singole zone.':'Setează parola pentru codurile QR ale zonelor individuale.',
    'Esporta CSV':'Exportă CSV','Codice, zona, nome o descrizione':'Cod, zonă, nume sau descriere',
    'Nessun ticket trovato':'Niciun tichet găsit','Nessun ticket':'Niciun tichet','Scorte basse':'Stoc redus',
    'Ticket totali':'Total tichete','Nuovi':'Noi','Sola lettura:':'Doar citire:','Dispositivo':'Dispozitiv'
  });
  const reverseEntries=[];
  Object.entries(messagesDe).forEach(([it,v])=>reverseEntries.push([v,it]));
  Object.entries(messagesRo).forEach(([it,v])=>reverseEntries.push([v,it]));
  reverseEntries.sort((a,b)=>b[0].length-a[0].length);
  const sourceDe=Object.entries(messagesDe).sort((a,b)=>b[0].length-a[0].length);
  const sourceRo=Object.entries(messagesRo).sort((a,b)=>b[0].length-a[0].length);
  const storageKey='hausmeister-language:__USER_ID__';
  let language=localStorage.getItem(storageKey);
  if(!['it','de','ro'].includes(language)) language='__DEFAULT_LANG__';
  let applying=false;

  function canonical(value){
    let text=String(value??'');
    for(const [translated,it] of reverseEntries){
      if(translated && text.includes(translated)) text=text.split(translated).join(it);
    }
    return text;
  }
  function translate(value,target=language){
    let base=canonical(value);
    if(target==='it') return base;
    const entries=target==='de'?sourceDe:sourceRo;
    for(const [it,translated] of entries){
      if(it && base.includes(it)) base=base.split(it).join(translated);
    }
    return base;
  }
  function dynamicTranslate(text){
    let base=canonical(text);
    const m=base.match(/^(\\d+) zone$/);
    if(m && language==='de') return m[1]+' Bereiche';
    if(m && language==='ro') return m[1]+' zone';
    return translate(base);
  }
  function translateNode(node){
    if(node.nodeType===Node.TEXT_NODE){
      const match=node.nodeValue.match(/^(\s*)(.*?)(\s*)$/s);
      if(match&&match[2]) node.nodeValue=match[1]+dynamicTranslate(match[2])+match[3];
      return;
    }
    if(node.nodeType!==Node.ELEMENT_NODE||['SCRIPT','STYLE'].includes(node.tagName)) return;
    ['placeholder','aria-label','title'].forEach(attr=>{
      if(node.hasAttribute(attr)) node.setAttribute(attr,dynamicTranslate(node.getAttribute(attr)));
    });
    [...node.childNodes].forEach(translateNode);
  }
  function addGroupTicketButtons(){
    document.querySelectorAll('details a[href^="zone/"]').forEach(a=>{
      const m=(a.getAttribute('href')||'').match(/^zone\/(\d+)$/);
      if(!m||a.parentElement.querySelector('.hm-group-ticket[data-zone="'+m[1]+'"]')) return;
      const b=document.createElement('a');
      b.className='hm-group-ticket'; b.dataset.zone=m[1]; b.href='quick-ticket/'+m[1];
      b.textContent=translate('Crea ticket');
      a.insertAdjacentElement('afterend',b);
    });
  }
  function apply(root=document.documentElement){
    if(applying) return;
    applying=true;
    document.documentElement.lang=language;
    translateNode(root);
    document.title=translate(document.title);
    document.querySelectorAll('[data-language]').forEach(button=>{
      const active=button.dataset.language===language;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    addGroupTicketButtons();
    applying=false;
  }
  function setLanguage(next){
    if(!['it','de','ro'].includes(next)||next===language) return;
    language=next; localStorage.setItem(storageKey,language); apply();
    window.dispatchEvent(new CustomEvent('app-language-changed',{detail:{language}}));
  }
  window.HausmeisterI18n={apply,getLanguage:()=>language,setLanguage,translate};
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.language)));
    apply();
    new MutationObserver(records=>{
      if(applying) return;
      records.forEach(record=>record.addedNodes.forEach(translateNode));
      addGroupTicketButtons();
    }).observe(document.body,{childList:true,subtree:true});
  });
})();
</script>""".replace('__USER_ID__', hm_user_id.replace("'", "")).replace('__DEFAULT_LANG__', default_language)
'''
block = block.replace(header, new_header, 1)

# Remove any previous language_selector definition still present later in page().
lines = block.splitlines()
seen = False
clean = []
for line in lines:
    if line.lstrip().startswith("language_selector =") and seen:
        continue
    if line.lstrip().startswith("language_selector ="):
        seen = True
    clean.append(line)
block = "\n".join(clean)

# Ensure selector is visible in both sidebars.
if "{settings_link}{language_selector}" not in block:
    block = block.replace("{settings_link}<div class=\"side-foot\">", "{settings_link}{language_selector}<div class=\"side-foot\">", 1)
manager_anchor = '<a class="side-link" href="/manager/logout">⇥ {manager_text(lang, \'logout\')}</a>'
if manager_anchor in block and "{language_selector}" not in block[block.find(manager_anchor):block.find(manager_anchor)+500]:
    block = block.replace(manager_anchor, manager_anchor + "{language_selector}", 1)

# Append our script last. The page footer is a normal Python string, not an f-string,
# so {hm_i18n} must be concatenated as a Python variable; putting it inside the
# literal footer would only print the characters "{hm_i18n}" and no JS would run.
footer = "+'''</div></body></html>'''"
if footer in block:
    block = block.replace(footer, "+'''</div>'''+hm_i18n+'''</body></html>'''", 1)
else:
    raise SystemExit("page footer marker not found for i18n injection")

text = text[:start] + block + text[end:]
path.write_text(text, encoding='utf-8')
