from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Exact strategy used by Dimensionamento Climatizzazione Pro:
# client-side dictionary + localStorage + language buttons + MutationObserver.
# Here the localStorage key also contains the authenticated HA user id.

ctx = "CURRENT_INGRESS_IS_ADMIN = ContextVar('current_ingress_is_admin', default=True)\n"
if ctx in text and "CURRENT_HA_USER_ID = ContextVar" not in text:
    text = text.replace(ctx, ctx + "CURRENT_HA_USER_ID = ContextVar('current_ha_user_id', default='')\n", 1)

apps = "public_app = FastAPI(title='Hausmeister Carellas Public')\n"
if apps in text and "async def hm_language_user_context" not in text:
    mw = r'''

@admin_app.middleware('http')
async def hm_language_user_context(request: Request, call_next):
    identity = ingress_identity(request)
    token = CURRENT_HA_USER_ID.set((identity.get('id') or '').strip())
    try:
        return await call_next(request)
    finally:
        CURRENT_HA_USER_ID.reset(token)

'''
    text = text.replace(apps, apps + mw, 1)

start = text.find("def page(")
end = text.find("\n\ndef session_zone", start)
if start < 0 or end < 0:
    raise SystemExit("page block not found")
block = text[start:end]

# Replace the old POST selector with the same local-only language buttons used by HVAC Pro.
lines = block.splitlines()
for idx, line in enumerate(lines):
    if "language_selector =" in line:
        indent = line[:len(line)-len(line.lstrip())]
        lines[idx] = indent + """language_selector = '''<div class="hm-language-switch" role="group" aria-label="Lingua / Sprache / Limbă"><button type="button" data-language="it">IT</button><button type="button" data-language="de">DE</button><button type="button" data-language="ro">RO</button></div>'''"""
        break
block = "\n".join(lines)

# Disable earlier experimental server-side replacement. HVAC Pro translates client-side.
block = block.replace(
    "return translate_admin_html(html_page, lang) if not public and not manager else html_page",
    "return html_page",
)

page_header = "def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):\n"
if page_header not in block:
    raise SystemExit("page header not found")

script_var = r'''def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):
    hm_user_id = CURRENT_HA_USER_ID.get() or 'anonymous'
    hm_saved = get_setting('ha_user_language_' + hm_user_id, '').strip().lower() if hm_user_id != 'anonymous' else ''
    hm_default_language = hm_saved if hm_saved in ('it','de','ro') else 'it'
    hvac_style_i18n = f"""<style>
.hm-language-switch{{display:flex;gap:6px;margin:10px 0 14px}}
.hm-language-switch button{{min-height:38px;padding:7px 11px;border:1px solid #ffffff35;background:#24343e;color:#fff;border-radius:8px}}
.hm-language-switch button.active{{background:#6e7d08;border-color:#9aaa23}}
</style><script>
(function(){{
  const messagesDe = {{
    'Gestione manutenzioni Carellas':'Carellas Wartungsverwaltung','Add-on in esecuzione':'Add-on läuft','Accesso titolare':'Inhaberzugang',
    'Indietro':'Zurück','Dashboard':'Dashboard','Ticket':'Tickets','Zone / QR':'Bereiche / QR','Magazzino materiali':'Materiallager',
    'Manutenzioni':'Wartungen','Impostazioni':'Einstellungen','Materiali da acquistare':'Material nachbestellen',
    'Totale ticket':'Tickets gesamt','Aperti':'Offen','In lavorazione':'In Bearbeitung','Risolti':'Erledigt',
    'Ticket recenti':'Aktuelle Tickets','Vedi tutti i ticket':'Alle Tickets anzeigen','Zona':'Bereich','Zone':'Bereiche',
    'Segnalato da':'Gemeldet von','Priorità':'Priorität','Stato':'Status','Categoria':'Kategorie',
    'Urgente':'Dringend','Alta':'Hoch','Normale':'Normal','Bassa':'Niedrig','Nuovo':'Neu','Preso in carico':'Übernommen',
    'Da verificare':'Zu prüfen','Risolto':'Erledigt','Senza gruppo':'Ohne Gruppe','Attiva':'Aktiv','Disattivata':'Deaktiviert',
    'Zone esistenti':'Vorhandene Bereiche','Nuova zona':'Neuer Bereich','Nome':'Name','Crea zona e QR':'Bereich und QR erstellen',
    'Gestisci / QR':'Verwalten / QR','Crea ticket':'Ticket erstellen','Scarica QR':'QR herunterladen','Stampa':'Drucken',
    'Modifica zona':'Bereich bearbeiten','Nome della zona':'Bereichsname','Salva nome':'Name speichern','Elimina zona':'Bereich löschen',
    'Ticket collegati':'Verknüpfte Tickets','Cerca':'Suchen','Tutti gli stati':'Alle Status','Tutti gli articoli':'Alle Artikel',
    'Solo da acquistare':'Nur nachzubestellen','Nuovo articolo':'Neuer Artikel','Descrizione':'Beschreibung','Posizione':'Position',
    'Fornitore':'Lieferant','Quantità':'Menge','Salva articolo':'Artikel speichern','Carica materiale':'Material einlagern',
    'Scarica materiale':'Material entnehmen','Movimenti recenti':'Letzte Bewegungen','Note interne / soluzione':'Interne Notizen / Lösung',
    'Salva modifiche':'Änderungen speichern','Foto':'Fotos','Nessuna foto':'Keine Fotos','Scorta disponibile':'Bestand verfügbar',
    'Da acquistare':'Nachbestellen','Codice articolo':'Artikelnummer','Unità':'Einheit','Nuovo ticket':'Neues Ticket',
    'Tipo di guasto':'Störungsart','Descrivi il problema nel dettaglio':'Problem ausführlich beschreiben',
    'Nome e cognome':'Vor- und Nachname','Invia segnalazione':'Meldung senden','Nessuna zona':'Keine Bereiche',
    'Gruppi di zone':'Bereichsgruppen','Gestisci gruppi':'Gruppen verwalten','Assegna zone':'Bereiche zuweisen',
    'Nuovo gruppo':'Neue Gruppe','Nome gruppo':'Gruppenname','Crea gruppo':'Gruppe erstellen','Elimina':'Löschen',
    'Salva assegnazione':'Zuordnung speichern','QR Zone':'Bereichs-QR','Scarica tutti i QR':'Alle QR herunterladen'
  }};
  const messagesRo = {{
    'Gestione manutenzioni Carellas':'Gestionare mentenanță Carellas','Add-on in esecuzione':'Add-on activ','Accesso titolare':'Acces proprietar',
    'Indietro':'Înapoi','Dashboard':'Panou de control','Ticket':'Tichete','Zone / QR':'Zone / QR','Magazzino materiali':'Depozit materiale',
    'Manutenzioni':'Mentenanțe','Impostazioni':'Setări','Materiali da acquistare':'Materiale de cumpărat',
    'Totale ticket':'Total tichete','Aperti':'Deschise','In lavorazione':'În lucru','Risolti':'Rezolvate',
    'Ticket recenti':'Tichete recente','Vedi tutti i ticket':'Vezi toate tichetele','Zona':'Zonă','Zone':'Zone',
    'Segnalato da':'Raportat de','Priorità':'Prioritate','Stato':'Stare','Categoria':'Categorie',
    'Urgente':'Urgent','Alta':'Ridicată','Normale':'Normală','Bassa':'Scăzută','Nuovo':'Nou','Preso in carico':'Preluat',
    'Da verificare':'De verificat','Risolto':'Rezolvat','Senza gruppo':'Fără grup','Attiva':'Activă','Disattivata':'Dezactivată',
    'Zone esistenti':'Zone existente','Nuova zona':'Zonă nouă','Nome':'Nume','Crea zona e QR':'Creează zona și QR',
    'Gestisci / QR':'Gestionează / QR','Crea ticket':'Creează tichet','Scarica QR':'Descarcă QR','Stampa':'Tipărește',
    'Modifica zona':'Modifică zona','Nome della zona':'Numele zonei','Salva nome':'Salvează numele','Elimina zona':'Șterge zona',
    'Ticket collegati':'Tichete asociate','Cerca':'Caută','Tutti gli stati':'Toate stările','Tutti gli articoli':'Toate articolele',
    'Solo da acquistare':'Doar de cumpărat','Nuovo articolo':'Articol nou','Descrizione':'Descriere','Posizione':'Poziție',
    'Fornitore':'Furnizor','Quantità':'Cantitate','Salva articolo':'Salvează articolul','Carica materiale':'Încarcă material',
    'Scarica materiale':'Descarcă material','Movimenti recenti':'Mișcări recente','Note interne / soluzione':'Note interne / soluție',
    'Salva modifiche':'Salvează modificările','Foto':'Fotografii','Nessuna foto':'Nicio fotografie','Nuovo ticket':'Tichet nou',
    'Tipo di guasto':'Tip defecțiune','Nome e cognome':'Nume și prenume','Invia segnalazione':'Trimite sesizarea',
    'Nessuna zona':'Nicio zonă','Gruppi di zone':'Grupuri de zone','Gestisci gruppi':'Gestionează grupurile',
    'Assegna zone':'Atribuie zone','Nuovo gruppo':'Grup nou','Nome gruppo':'Numele grupului','Crea gruppo':'Creează grup',
    'Elimina':'Șterge','Salva assegnazione':'Salvează atribuirea','QR Zone':'QR Zone','Scarica tutti i QR':'Descarcă toate QR-urile'
  }};

  const reverseDe = Object.fromEntries(Object.entries(messagesDe).map(([it,de])=>[de,it]));
  const reverseRo = Object.fromEntries(Object.entries(messagesRo).map(([it,ro])=>[ro,it]));
  const storageKey = 'hausmeister-language:' + {json.dumps(hm_user_id)};
  let language = localStorage.getItem(storageKey);
  if (!['it','de','ro'].includes(language)) language = {json.dumps(hm_default_language)};
  let applying = false;

  function canonical(value) {{
    const text=String(value ?? '');
    return reverseDe[text] || reverseRo[text] || text;
  }}
  function translate(value,target=language) {{
    const original=String(value ?? '');
    const base=canonical(original);
    if(target==='de') return messagesDe[base] || base;
    if(target==='ro') return messagesRo[base] || base;
    return base;
  }}
  function translateNode(node) {{
    if(node.nodeType===Node.TEXT_NODE) {{
      const m=node.nodeValue.match(/^(\\s*)(.*?)(\\s*)$/s);
      if(m && m[2]) node.nodeValue=m[1]+translate(m[2])+m[3];
      return;
    }}
    if(node.nodeType!==Node.ELEMENT_NODE || ['SCRIPT','STYLE'].includes(node.tagName)) return;
    ['placeholder','aria-label','title'].forEach(attr=>{{
      if(node.hasAttribute(attr)) node.setAttribute(attr,translate(node.getAttribute(attr)));
    }});
    [...node.childNodes].forEach(translateNode);
  }}
  function apply(root=document.documentElement) {{
    if(applying) return;
    applying=true;
    document.documentElement.lang=language;
    translateNode(root);
    document.title=translate(document.title);
    document.querySelectorAll('[data-language]').forEach(button=>{{
      const active=button.dataset.language===language;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    }});
    applying=false;
  }}
  function setLanguage(next) {{
    if(!['it','de','ro'].includes(next) || next===language) return;
    language=next;
    localStorage.setItem(storageKey,language);
    apply();
    window.dispatchEvent(new CustomEvent('app-language-changed',{{detail:{{language}}}}));
  }}
  window.HausmeisterI18n={{apply,getLanguage:()=>language,setLanguage,translate}};
  document.addEventListener('DOMContentLoaded',()=>{{
    document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.language)));
    apply();
    new MutationObserver(records=>{{
      if(applying) return;
      records.forEach(record=>record.addedNodes.forEach(translateNode));
    }}).observe(document.body,{{childList:true,subtree:true}});
  }});
}})();
</script>"""
'''
block = block.replace(page_header, script_var, 1)

# Append script to final HTML. Preserve all older functionality, but this script runs last.
if "{hvac_style_i18n}</body></html>" not in block:
    block = block.replace("</body></html>", "{hvac_style_i18n}</body></html>", 1)

text = text[:start] + block + text[end:]
path.write_text(text, encoding='utf-8')
