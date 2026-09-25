from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

start = text.find("def page(")
end = text.find("\n\ndef session_zone", start)
if start < 0 or end < 0:
    raise SystemExit("page() block not found")

block = text[start:end]
if "function hmHaFrontendLanguage" not in block:
    marker = "def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):\n"
    bridge = r'''def page(title: str, body: str, public: bool = False, lang: str = 'it', back_url: str = '', close_on_back: bool = False, manager: bool = False):
    ha_frontend_language_bridge = r"""<script>
(function(){
  const translations = {
    de: {
      "Gestione manutenzioni Carellas":"Carellas Wartungsverwaltung",
      "Add-on in esecuzione":"Add-on läuft",
      "Accesso titolare":"Inhaberzugang",
      "Indietro":"Zurück",
      "Dashboard":"Dashboard",
      "Ticket recenti":"Aktuelle Tickets",
      "Ticket":"Tickets",
      "Zone / QR":"Bereiche / QR",
      "Zone esistenti":"Vorhandene Bereiche",
      "Zone":"Bereiche",
      "Zona":"Bereich",
      "Magazzino materiali":"Materiallager",
      "Manutenzioni":"Wartungen",
      "Impostazioni":"Einstellungen",
      "Materiali da acquistare":"Material nachbestellen",
      "Totale ticket":"Tickets gesamt",
      "Aperti":"Offen",
      "In lavorazione":"In Bearbeitung",
      "Risolti":"Erledigt",
      "Segnalato da":"Gemeldet von",
      "Priorità":"Priorität",
      "Stato":"Status",
      "Categoria":"Kategorie",
      "Urgente":"Dringend",
      "Alta":"Hoch",
      "Normale":"Normal",
      "Bassa":"Niedrig",
      "Nuovo":"Neu",
      "Preso in carico":"Übernommen",
      "Da verificare":"Zu prüfen",
      "Risolto":"Erledigt",
      "Senza gruppo":"Ohne Gruppe",
      "Attiva":"Aktiv",
      "Disattivata":"Deaktiviert",
      "Nuova zona":"Neuer Bereich",
      "Nome":"Name",
      "Crea zona e QR":"Bereich und QR erstellen",
      "Gestisci / QR":"Verwalten / QR",
      "Crea ticket":"Ticket erstellen",
      "Scarica QR":"QR herunterladen",
      "Stampa":"Drucken",
      "Modifica zona":"Bereich bearbeiten",
      "Nome della zona":"Bereichsname",
      "Salva nome":"Name speichern",
      "Elimina zona":"Bereich löschen",
      "Ticket collegati":"Verknüpfte Tickets",
      "Cerca":"Suchen",
      "Tutti gli stati":"Alle Status",
      "Vedi tutti i ticket":"Alle Tickets anzeigen",
      "Tutti gli articoli":"Alle Artikel",
      "Solo da acquistare":"Nur nachzubestellen",
      "Nuovo articolo":"Neuer Artikel",
      "Descrizione":"Beschreibung",
      "Posizione":"Position",
      "Fornitore":"Lieferant",
      "Quantità":"Menge",
      "Salva articolo":"Artikel speichern",
      "Carica materiale":"Material einlagern",
      "Scarica materiale":"Material entnehmen",
      "Movimenti recenti":"Letzte Bewegungen",
      "Note interne / soluzione":"Interne Notizen / Lösung",
      "Salva modifiche":"Änderungen speichern",
      "Foto":"Fotos",
      "Nessuna foto":"Keine Fotos",
      "Scorta disponibile":"Bestand verfügbar",
      "Da acquistare":"Nachbestellen",
      "Codice articolo":"Artikelnummer",
      "Unità":"Einheit",
      "Fornitore":"Lieferant",
      "Nuovo ticket":"Neues Ticket",
      "Tipo di guasto":"Störungsart",
      "Descrivi il problema nel dettaglio":"Problem ausführlich beschreiben",
      "Nome e cognome":"Vor- und Nachname",
      "Invia segnalazione":"Meldung senden"
    },
    ro: {
      "Gestione manutenzioni Carellas":"Gestionare mentenanță Carellas",
      "Add-on in esecuzione":"Add-on activ",
      "Accesso titolare":"Acces proprietar",
      "Indietro":"Înapoi",
      "Dashboard":"Panou de control",
      "Ticket recenti":"Tichete recente",
      "Ticket":"Tichete",
      "Zone / QR":"Zone / QR",
      "Zone esistenti":"Zone existente",
      "Zone":"Zone",
      "Zona":"Zonă",
      "Magazzino materiali":"Depozit materiale",
      "Manutenzioni":"Mentenanțe",
      "Impostazioni":"Setări",
      "Materiali da acquistare":"Materiale de cumpărat",
      "Totale ticket":"Total tichete",
      "Aperti":"Deschise",
      "In lavorazione":"În lucru",
      "Risolti":"Rezolvate",
      "Segnalato da":"Raportat de",
      "Priorità":"Prioritate",
      "Stato":"Stare",
      "Categoria":"Categorie",
      "Urgente":"Urgent",
      "Alta":"Ridicată",
      "Normale":"Normală",
      "Bassa":"Scăzută",
      "Nuovo":"Nou",
      "Preso in carico":"Preluat",
      "Da verificare":"De verificat",
      "Risolto":"Rezolvat",
      "Senza gruppo":"Fără grup",
      "Attiva":"Activă",
      "Disattivata":"Dezactivată",
      "Nuova zona":"Zonă nouă",
      "Nome":"Nume",
      "Crea zona e QR":"Creează zona și QR",
      "Gestisci / QR":"Gestionează / QR",
      "Crea ticket":"Creează tichet",
      "Scarica QR":"Descarcă QR",
      "Stampa":"Tipărește",
      "Modifica zona":"Modifică zona",
      "Nome della zona":"Numele zonei",
      "Salva nome":"Salvează numele",
      "Elimina zona":"Șterge zona",
      "Ticket collegati":"Tichete asociate",
      "Cerca":"Caută",
      "Tutti gli stati":"Toate stările",
      "Vedi tutti i ticket":"Vezi toate tichetele",
      "Tutti gli articoli":"Toate articolele",
      "Solo da acquistare":"Doar de cumpărat",
      "Nuovo articolo":"Articol nou",
      "Descrizione":"Descriere",
      "Posizione":"Poziție",
      "Fornitore":"Furnizor",
      "Quantità":"Cantitate",
      "Salva articolo":"Salvează articolul",
      "Carica materiale":"Încarcă material",
      "Scarica materiale":"Descarcă material",
      "Movimenti recenti":"Mișcări recente",
      "Note interne / soluzione":"Note interne / soluție",
      "Salva modifiche":"Salvează modificările",
      "Foto":"Fotografii",
      "Nessuna foto":"Nicio fotografie",
      "Nuovo ticket":"Tichet nou",
      "Tipo di guasto":"Tip defecțiune",
      "Nome e cognome":"Nume și prenume",
      "Invia segnalazione":"Trimite sesizarea"
    }
  };

  function hmHaFrontendLanguage(){
    const windows = [];
    try { if (window.parent) windows.push(window.parent); } catch(e) {}
    try { if (window.top && window.top !== window.parent) windows.push(window.top); } catch(e) {}
    for (const w of windows) {
      try {
        const root = w.document && w.document.querySelector('home-assistant');
        const hass = root && (root.hass || root._hass);
        const lang = hass && (hass.language || (hass.locale && hass.locale.language));
        if (lang) return String(lang).toLowerCase().split('-')[0].split('_')[0];
      } catch(e) {}
    }
    return '';
  }

  function fallbackLanguage(){
    try {
      const select = document.querySelector('select[name="language"]');
      if (select && ['it','de','ro'].includes(select.value)) return select.value;
    } catch(e) {}
    try {
      const hit = document.cookie.split('; ').find(x => x.startsWith('hm_user_lang='));
      if (hit) {
        const value = decodeURIComponent(hit.substring('hm_user_lang='.length)).toLowerCase();
        if (['it','de','ro'].includes(value)) return value;
      }
    } catch(e) {}
    return 'it';
  }

  function translatePage(lang){
    if (!['de','ro'].includes(lang)) {
      document.documentElement.lang='it';
      return;
    }
    const dict = translations[lang];
    const keys = Object.keys(dict).sort((a,b)=>b.length-a.length);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const nodes=[];
    while(walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent=node.parentElement;
      if (!parent || ['SCRIPT','STYLE','TEXTAREA'].includes(parent.tagName)) continue;
      let raw=node.nodeValue;
      for (const key of keys) {
        if (raw.includes(key)) raw=raw.split(key).join(dict[key]);
      }
      node.nodeValue=raw;
    }
    document.querySelectorAll('input[placeholder],textarea[placeholder],[title]').forEach(el=>{
      for (const key of keys) {
        const p=el.getAttribute('placeholder');
        if (p && p.includes(key)) el.setAttribute('placeholder',p.split(key).join(dict[key]));
        const t=el.getAttribute('title');
        if (t && t.includes(key)) el.setAttribute('title',t.split(key).join(dict[key]));
      }
    });
    const select=document.querySelector('select[name="language"]');
    if (select) select.value=lang;
    document.documentElement.lang=lang;
  }

  function apply(){
    const haLang=hmHaFrontendLanguage();
    const lang=['it','de','ro'].includes(haLang)?haLang:fallbackLanguage();
    const previous=sessionStorage.getItem('hm_effective_lang')||'';
    if (previous && previous!==lang) {
      sessionStorage.setItem('hm_effective_lang',lang);
      location.reload();
      return;
    }
    sessionStorage.setItem('hm_effective_lang',lang);
    translatePage(lang);
  }

  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded',apply);
  else apply();
  setTimeout(apply,350);
  setTimeout(apply,1200);
})();
</script>"""
'''
    block = block.replace(marker, bridge, 1)
    block = block.replace("</body></html>", "{ha_frontend_language_bridge}</body></html>", 1)
    text = text[:start] + block + text[end:]

path.write_text(text, encoding='utf-8')
