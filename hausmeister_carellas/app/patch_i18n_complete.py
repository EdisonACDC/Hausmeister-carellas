from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Final i18n cleanup. This patch runs after patch_manager_ui_v3 and replaces only
# its client-side language engine. The structure mirrors the working HVAC Pro:
# localStorage + data-language buttons + reversible DOM translation + MutationObserver.

text = text.replace("APP_VERSION = '1.5.46'", "APP_VERSION = '1.5.59'", 1)

start = text.find('    hm_i18n = r"""<style>')
end = text.find("    shell_class = 'admin-shell'", start)
if start < 0 or end < 0:
    raise SystemExit('Hausmeister i18n block not found')

new_block = r'''    hm_i18n = r"""<style>
.hm-language-switch{display:flex;gap:6px;margin:10px 0 14px}
.hm-language-switch button{min-height:38px;padding:7px 11px;border:1px solid #ffffff35;background:#24343e;color:#fff;border-radius:8px}
.hm-language-switch button.active{background:#6e7d08;border-color:#9aaa23}
.hm-group-ticket{display:inline-flex;margin:0 10px 8px;padding:8px 11px;border-radius:9px;background:#6e7d08;color:#fff;text-decoration:none;font-weight:700}
.hm-file-wrap{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:7px 0 15px}
.hm-file-button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 14px;border:1px solid #cfd6dc;border-radius:10px;background:#f5f6f7;color:#17212b;font-weight:700;cursor:pointer}
.hm-file-name{color:#6b7280;font-size:14px}
</style><script>
(function(){
  const DE={
    "Home Assistant":"Home Assistant","Dashboard":"Dashboard","Ticket":"Tickets","TICKET":"Tickets",
    "Zone / QR":"Bereiche / QR","Zone":"Bereiche","Zona":"Bereich","Magazzino materiali":"Materiallager",
    "Materiali":"Material","Manutenzioni":"Wartungen","Impostazioni":"Einstellungen",
    "Gestione manutenzioni Carellas":"Carellas Wartungsverwaltung","Add-on in esecuzione":"Add-on läuft",
    "Accesso titolare":"Inhaberzugang","Indietro":"Zurück","Materiali da acquistare":"Material nachbestellen",
    "Totale ticket":"Tickets gesamt","Ticket totali":"Tickets gesamt","Aperti":"Offen","Nuovi":"Neu",
    "In lavorazione":"In Bearbeitung","Risolti":"Erledigt","Ticket recenti":"Aktuelle Tickets",
    "Vedi tutti i ticket":"Alle Tickets anzeigen","Segnalato da":"Gemeldet von","Categoria":"Kategorie",
    "Priorità":"Priorität","Stato":"Status","Urgente":"Dringend","Alta":"Hoch","Normale":"Normal",
    "Bassa":"Niedrig","Nuovo":"Neu","Preso in carico":"Übernommen","Da verificare":"Zu prüfen","Risolto":"Erledigt",
    "Attiva":"Aktiv","Attivo":"Aktiv","Disattivata":"Deaktiviert","Disabilitato":"Deaktiviert","Abilitato":"Aktiviert",
    "Senza gruppo":"Ohne Gruppe","Zone esistenti":"Vorhandene Bereiche","Nuova zona":"Neuer Bereich",
    "Nome":"Name","Crea zona e QR":"Bereich und QR erstellen","Gestisci / QR":"Verwalten / QR","QR →":"QR →",
    "Crea ticket":"Ticket erstellen","Apri un nuovo ticket per questa zona":"Neues Ticket für diesen Bereich öffnen",
    "Nuovo ticket":"Neues Ticket","Nuovo Ticket":"Neues Ticket",
    "Accesso interno Home Assistant: nessuna password richiesta.":"Interner Home-Assistant-Zugriff: kein Passwort erforderlich.",
    "Nome e cognome":"Vor- und Nachname","Nome e cognome *":"Vor- und Nachname *",
    "Inserisci nome e cognome":"Vor- und Nachname eingeben","Tipo di guasto":"Störungsart","Tipo di guasto *":"Störungsart *",
    "Seleziona la categoria":"Kategorie auswählen","Descrizione":"Beschreibung","Descrizione *":"Beschreibung *",
    "Descrivi il problema nel dettaglio":"Problem ausführlich beschreiben","Foto":"Fotos","Fotografie":"Fotos",
    "Foto (opzionale)":"Fotos (optional)","Foto (opzionale, massimo 5)":"Fotos (optional, maximal 5)",
    "Nessuna foto":"Keine Fotos","Nessuna fotografia":"Keine Fotos","Nessuna foto allegata.":"Keine Fotos angehängt.",
    "Invia segnalazione":"Meldung senden","Invia ticket":"Ticket senden",
    "Elettrico":"Elektrik","Idraulico":"Sanitär / Wasser","Climatizzazione":"Klimaanlage",
    "Porta/Finestra":"Tür / Fenster","Attrezzatura cucina":"Küchengerät","Altro":"Sonstiges",
    "Scarica QR":"QR herunterladen","Stampa":"Drucken","Modifica zona":"Bereich bearbeiten",
    "Nome della zona":"Bereichsname","Salva nome":"Name speichern","Elimina zona":"Bereich löschen",
    "Ticket collegati":"Verknüpfte Tickets","Cerca":"Suchen","Cerca materiale":"Material suchen",
    "Codice, zona, nome o descrizione":"Code, Bereich, Name oder Beschreibung","Tutti gli stati":"Alle Status",
    "Tutti":"Alle","Tutte":"Alle","Nessun ticket":"Keine Tickets","Nessun ticket trovato":"Keine Tickets gefunden",
    "Nessuna zona":"Keine Bereiche","Nessuna zona disponibile":"Keine Bereiche verfügbar",
    "Esporta CSV":"CSV exportieren","Gestione":"Verwaltung","Descrizione originale":"Originalbeschreibung",
    "Traduzione italiana":"Italienische Übersetzung","Traduzione tedesca / Deutsche Übersetzung":"Deutsche Übersetzung",
    "Traduci ora in italiano e tedesco":"Jetzt ins Italienische und Deutsche übersetzen",
    "Correggi traduzione italiana":"Italienische Übersetzung korrigieren",
    "Correggi traduzione tedesca / Deutsche Übersetzung":"Deutsche Übersetzung korrigieren",
    "Salva correzioni":"Korrekturen speichern","Note interne / soluzione":"Interne Notizen / Lösung",
    "Salva modifiche":"Änderungen speichern","Elimina ticket":"Ticket löschen","Elimina ticket e foto":"Ticket und Fotos löschen",
    "Questa operazione libera spazio ma non può essere annullata.":"Dieser Vorgang gibt Speicher frei, kann aber nicht rückgängig gemacht werden.",
    "PRIORITÀ":"PRIORITÄT","intervenire rapidamente":"schnell eingreifen","Priorità alta o urgente":"Hohe oder dringende Priorität",
    "Magazzino materiali":"Materiallager","Tutti gli articoli":"Alle Artikel","Solo da acquistare":"Nur nachzubestellen",
    "Nuovo articolo":"Neuer Artikel","Nome, codice o categoria":"Name, Code oder Kategorie",
    "Codice articolo":"Artikelnummer","Posizione":"Position","Fornitore":"Lieferant","Unità":"Einheit","Quantità":"Menge",
    "Scorta disponibile":"Bestand verfügbar","Da acquistare":"Nachbestellen","Scorta attuale":"Aktueller Bestand",
    "Soglia avviso":"Meldeschwelle","Foto articolo":"Artikelfoto","Scatta o scegli una foto":"Foto aufnehmen oder auswählen",
    "Aggiungi articolo":"Artikel hinzufügen","Modifica articolo":"Artikel bearbeiten","Salva articolo":"Artikel speichern",
    "Carica materiale":"Material einlagern","Scarica materiale":"Material entnehmen","Quantità movimento":"Bewegungsmenge",
    "Nota":"Notiz","Movimenti recenti":"Letzte Bewegungen","Nessun movimento":"Keine Bewegungen",
    "Elimina articolo":"Artikel löschen","Cerca materiale":"Material suchen","Categoria:":"Kategorie:","Codice:":"Code:",
    "Posizione:":"Position:","Etichetta":"Etikett","Stampa etichetta":"Etikett drucken","Torna all’articolo":"Zurück zum Artikel",
    "QR articolo":"Artikel-QR","Carellas Ristorante · MAGAZZINO MATERIALI":"Carellas Restaurant · MATERIALLAGER",
    "Manutenzioni":"Wartungen","Nuova manutenzione":"Neue Wartung","Crea manutenzione":"Wartung erstellen",
    "Titolo *":"Titel *","Tipo":"Typ","Tipo *":"Typ *","Responsabile / ditta":"Verantwortlicher / Firma",
    "Responsabile:":"Verantwortlich:","Data prevista":"Geplantes Datum","Frequenza ordinaria":"Regelmäßige Häufigkeit",
    "Settimanale":"Wöchentlich","Mensile":"Monatlich","Trimestrale":"Vierteljährlich","Semestrale":"Halbjährlich","Annuale":"Jährlich",
    "Costo previsto €":"Geplante Kosten €","Costo reale €":"Tatsächliche Kosten €","Note":"Notizen","Note esecuzione":"Ausführungsnotizen",
    "Completa intervento":"Einsatz abschließen","Segna completata":"Als abgeschlossen markieren","Elimina manutenzione":"Wartung löschen",
    "Storico":"Verlauf","Ultima esecuzione:":"Letzte Ausführung:","Prossima scadenza:":"Nächster Termin:",
    "Scadenza:":"Termin:","Nessuna manutenzione presente.":"Keine Wartung vorhanden.",
    "Nessuna esecuzione registrata.":"Keine Ausführung erfasst.","Es. Pulizia filtri climatizzatore":"z. B. Klimaanlagenfilter reinigen",
    "Gruppi di zone":"Bereichsgruppen","Gestisci gruppi":"Gruppen verwalten","Assegna zone":"Bereiche zuweisen",
    "Nuovo gruppo":"Neue Gruppe","Nome gruppo":"Gruppenname","Crea gruppo":"Gruppe erstellen","Elimina":"Löschen",
    "Salva assegnazione":"Zuordnung speichern","Zone senza gruppo:":"Bereiche ohne Gruppe:","Nessun gruppo creato.":"Keine Gruppe erstellt.",
    "Non ci sono ancora zone.":"Es gibt noch keine Bereiche.",
    "Seleziona le zone che vuoi inserire in questo gruppo. Una zona può appartenere a un solo gruppo.":"Wähle die Bereiche für diese Gruppe. Ein Bereich kann nur zu einer Gruppe gehören.",
    "QR Zone":"Bereichs-QR","Scarica tutti i QR":"Alle QR herunterladen",
    "Scarica in una volta sola i QR di tutte le zone, con file separati per la stampa da telefono o PC.":"Lade die QR-Codes aller Bereiche auf einmal als getrennte Dateien für Telefon oder PC herunter.",
    "ZIP · PNG separati":"ZIP · einzelne PNG","ZIP · PDF separati":"ZIP · einzelne PDF","PDF unico":"Eine PDF",
    "Per Brother da iPhone usa":"Für Brother vom iPhone verwenden","ogni zona viene salvata come immagine PNG indipendente.":"Jeder Bereich wird als eigene PNG-Datei gespeichert.",
    "zone trovate. Gli export vengono creati al momento, quindi comprendono automaticamente anche le zone aggiunte in futuro.":"Bereiche gefunden. Exporte werden aktuell erzeugt und enthalten automatisch später hinzugefügte Bereiche.",
    "Password zone singole":"Passwort für einzelne Bereiche","Usata dai QR che aprono direttamente una zona.":"Wird von QR-Codes verwendet, die direkt einen Bereich öffnen.",
    "Password salvata":"Gespeichertes Passwort","Inserisci nuovamente la password":"Passwort erneut eingeben","Salva password zone":"Bereichspasswort speichern",
    "Password QR di gruppo":"Gruppen-QR-Passwort","È diversa dalla password delle singole zone e permette di scegliere una delle zone attive.":"Es unterscheidet sich vom Passwort einzelner Bereiche und ermöglicht die Auswahl eines aktiven Bereichs.",
    "Password di gruppo salvata":"Gespeichertes Gruppenpasswort","Crea la password di gruppo":"Gruppenpasswort erstellen",
    "Salva password di gruppo":"Gruppenpasswort speichern","QR con tutte le zone":"QR mit allen Bereichen",
    "Prima salva la password di gruppo.":"Speichere zuerst das Gruppenpasswort.","Configurazione":"Konfiguration",
    "URL pubblico:":"Öffentliche URL:","Traduzione automatica:":"Automatische Übersetzung:",
    "Automatica integrata (Google con MyMemory di riserva)":"Integrierte Automatik (Google mit MyMemory als Reserve)",
    "URL e traduzione si modificano nella scheda Configurazione dell'add-on di Home Assistant.":"URL und Übersetzung werden in der Add-on-Konfiguration von Home Assistant geändert.",
    "Dispositivi per le notifiche":"Geräte für Benachrichtigungen","I nuovi ticket vengono inviati a tutti i dispositivi attivi. Puoi modificarli anche quando cambi telefono.":"Neue Tickets werden an alle aktiven Geräte gesendet. Die Liste kann auch nach einem Telefonwechsel geändert werden.",
    "Rileva dispositivi da Home Assistant":"Geräte aus Home Assistant erkennen","Diagnostica rilevamento:":"Erkennungsdiagnose:",
    "Aggiunta manuale":"Manuell hinzufügen","Nome dispositivo":"Gerätename","Entità/azione di notifica":"Benachrichtigungs-Entität/Aktion",
    "Entità/azione":"Entität/Aktion","Aggiungi dispositivo":"Gerät hinzufügen","Dispositivo attivo":"Gerät aktiv",
    "Invia prova":"Test senden","Nessun dispositivo configurato.":"Kein Gerät konfiguriert.","Accesso degli utenti Home Assistant":"Zugriff für Home-Assistant-Benutzer",
    "Utente":"Benutzer","Azione":"Aktion","Abilita":"Aktivieren","Disabilita":"Deaktivieren","Accesso del titolare esterno":"Externer Inhaberzugang",
    "Indirizzo del portale:":"Portaladresse:","Nome utente del titolare":"Benutzername des Inhabers","Nuova password":"Neues Passwort",
    "Portale Titolare attivo":"Inhaberportal aktiv","Salva accesso titolare esterno":"Externen Inhaberzugang speichern",
    "Backup":"Sicherung","Scarica database e fotografie in un unico archivio ZIP.":"Datenbank und Fotos in einem einzigen ZIP-Archiv herunterladen.",
    "Scarica backup":"Sicherung herunterladen","Gestisci backup":"Sicherungen verwalten","Backup automatico":"Automatische Sicherung",
    "Backup manuale":"Manuelle Sicherung","Backup disponibili":"Verfügbare Sicherungen","Crea backup adesso":"Jetzt Sicherung erstellen",
    "Crea subito una copia di database, ticket, fotografie e magazzino.":"Jetzt eine Kopie von Datenbank, Tickets, Fotos und Lager erstellen.",
    "Salva pianificazione":"Zeitplan speichern","Carica e ripristina un backup":"Sicherung hochladen und wiederherstellen",
    "Sono accettati soltanto ZIP creati da Hausmeister. Il file viene verificato prima del ripristino.":"Es werden nur von Hausmeister erstellte ZIP-Dateien akzeptiert. Die Datei wird vor der Wiederherstellung geprüft.",
    "Data":"Datum","Dimensione":"Größe","Azioni":"Aktionen","Scarica":"Herunterladen","Ripristina":"Wiederherstellen",
    "Nessun backup interno presente.":"Keine interne Sicherung vorhanden.","Ora giornaliera (0-23)":"Tägliche Uhrzeit (0-23)",
    "Ultimo risultato:":"Letztes Ergebnis:","Contatti WhatsApp":"WhatsApp-Kontakte","WhatsApp tecnici":"WhatsApp-Techniker",
    "Aggiungi contatto":"Kontakt hinzufügen","Aggiungi tecnico":"Techniker hinzufügen","Nome / Ditta":"Name / Firma","Numero WhatsApp":"WhatsApp-Nummer",
    "Usa il prefisso internazionale (+49, +39, ecc.).":"Internationale Vorwahl verwenden (+49, +39 usw.).",
    "Tecnici suggeriti per:":"Vorgeschlagene Techniker für:","Invia a tecnico":"An Techniker senden","Apri WhatsApp":"WhatsApp öffnen",
    "Apertura WhatsApp…":"WhatsApp wird geöffnet…","Se WhatsApp non si apre automaticamente, premi il pulsante.":"Falls WhatsApp nicht automatisch öffnet, drücke die Schaltfläche.",
    "Problema":"Problem","Intervento":"Einsatz","Inviato a":"Gesendet an","Nessun tecnico configurato.":"Kein Techniker konfiguriert.",
    "Aggiungi foto":"Foto hinzufügen","Scegli file":"Datei auswählen","Nessun file selezionato":"Keine Datei ausgewählt","Notifiche":"Benachrichtigungen","Risposte ai ticket":"Ticket-Antworten","Qui trovi le risposte dei tecnici e le richieste di materiale.":"Hier findest du Antworten der Techniker und Materialanforderungen.","Risposta":"Antwort","Scrivi la risposta al tecnico":"Antwort an den Techniker schreiben","Apri anche WhatsApp con la risposta pronta":"WhatsApp ebenfalls mit vorbereiteter Antwort öffnen","Invia risposta":"Antwort senden","Tua risposta":"Deine Antwort","Risposta tecnico":"Technikerantwort","Nessuna risposta ricevuta.":"Keine Antworten erhalten.","Serve materiale":"Material erforderlich","Materiale necessario":"Benötigtes Material","Risposta salvata nel ticket.":"Antwort im Ticket gespeichert.","pz":"Stk.","conf.":"Pkg."
  };

  const RO={
    "Home Assistant":"Home Assistant","Dashboard":"Panou de control","Ticket":"Tichete","TICKET":"Tichete",
    "Zone / QR":"Zone / QR","Zone":"Zone","Zona":"Zonă","Magazzino materiali":"Depozit materiale","Materiali":"Materiale",
    "Manutenzioni":"Mentenanțe","Impostazioni":"Setări","Gestione manutenzioni Carellas":"Gestionare mentenanță Carellas",
    "Add-on in esecuzione":"Add-on activ","Accesso titolare":"Acces proprietar","Indietro":"Înapoi",
    "Materiali da acquistare":"Materiale de cumpărat","Totale ticket":"Total tichete","Ticket totali":"Total tichete",
    "Aperti":"Deschise","Nuovi":"Noi","In lavorazione":"În lucru","Risolti":"Rezolvate","Ticket recenti":"Tichete recente",
    "Vedi tutti i ticket":"Vezi toate tichetele","Segnalato da":"Raportat de","Categoria":"Categorie","Priorità":"Prioritate",
    "Stato":"Stare","Urgente":"Urgent","Alta":"Ridicată","Normale":"Normală","Bassa":"Scăzută","Nuovo":"Nou",
    "Preso in carico":"Preluat","Da verificare":"De verificat","Risolto":"Rezolvat","Attiva":"Activă","Attivo":"Activ",
    "Disattivata":"Dezactivată","Disabilitato":"Dezactivat","Abilitato":"Activat","Senza gruppo":"Fără grup",
    "Zone esistenti":"Zone existente","Nuova zona":"Zonă nouă","Nome":"Nume","Crea zona e QR":"Creează zona și QR",
    "Gestisci / QR":"Gestionează / QR","Crea ticket":"Creează tichet","Apri un nuovo ticket per questa zona":"Deschide un tichet nou pentru această zonă",
    "Nuovo ticket":"Tichet nou","Nuovo Ticket":"Tichet nou","Accesso interno Home Assistant: nessuna password richiesta.":"Acces intern Home Assistant: nu este necesară parola.",
    "Nome e cognome":"Nume și prenume","Nome e cognome *":"Nume și prenume *","Inserisci nome e cognome":"Introdu numele și prenumele",
    "Tipo di guasto":"Tip defecțiune","Tipo di guasto *":"Tip defecțiune *","Seleziona la categoria":"Selectează categoria",
    "Descrizione":"Descriere","Descrizione *":"Descriere *","Descrivi il problema nel dettaglio":"Descrie problema în detaliu",
    "Foto":"Fotografii","Fotografie":"Fotografii","Foto (opzionale)":"Fotografii (opțional)",
    "Foto (opzionale, massimo 5)":"Fotografii (opțional, maximum 5)","Nessuna foto":"Nicio fotografie",
    "Nessuna fotografia":"Nicio fotografie","Nessuna foto allegata.":"Nicio fotografie atașată.","Invia segnalazione":"Trimite sesizarea",
    "Invia ticket":"Trimite tichetul","Elettrico":"Electric","Idraulico":"Instalații / apă","Climatizzazione":"Climatizare",
    "Porta/Finestra":"Ușă / fereastră","Attrezzatura cucina":"Echipament bucătărie","Altro":"Altele",
    "Scarica QR":"Descarcă QR","Stampa":"Tipărește","Modifica zona":"Modifică zona","Nome della zona":"Numele zonei",
    "Salva nome":"Salvează numele","Elimina zona":"Șterge zona","Ticket collegati":"Tichete asociate","Cerca":"Caută",
    "Cerca materiale":"Caută material","Codice, zona, nome o descrizione":"Cod, zonă, nume sau descriere","Tutti gli stati":"Toate stările",
    "Tutti":"Toate","Tutte":"Toate","Nessun ticket":"Niciun tichet","Nessun ticket trovato":"Niciun tichet găsit",
    "Nessuna zona":"Nicio zonă","Nessuna zona disponibile":"Nicio zonă disponibilă","Esporta CSV":"Exportă CSV",
    "Gestione":"Gestionare","Descrizione originale":"Descriere originală","Traduzione italiana":"Traducere italiană",
    "Traduzione tedesca / Deutsche Übersetzung":"Traducere germană","Traduci ora in italiano e tedesco":"Tradu acum în italiană și germană",
    "Correggi traduzione italiana":"Corectează traducerea italiană","Correggi traduzione tedesca / Deutsche Übersetzung":"Corectează traducerea germană",
    "Salva correzioni":"Salvează corecturile","Note interne / soluzione":"Note interne / soluție","Salva modifiche":"Salvează modificările",
    "Elimina ticket":"Șterge tichetul","Elimina ticket e foto":"Șterge tichetul și fotografiile","Questa operazione libera spazio ma non può essere annullata.":"Această operație eliberează spațiu, dar nu poate fi anulată.",
    "Magazzino materiali":"Depozit materiale","Tutti gli articoli":"Toate articolele","Solo da acquistare":"Doar de cumpărat",
    "Nuovo articolo":"Articol nou","Nome, codice o categoria":"Nume, cod sau categorie","Codice articolo":"Cod articol",
    "Posizione":"Poziție","Fornitore":"Furnizor","Unità":"Unitate","Quantità":"Cantitate","Scorta disponibile":"Stoc disponibil",
    "Da acquistare":"De cumpărat","Scorta attuale":"Stoc actual","Soglia avviso":"Prag avertizare","Foto articolo":"Fotografie articol",
    "Scatta o scegli una foto":"Fă sau alege o fotografie","Aggiungi articolo":"Adaugă articol","Modifica articolo":"Modifică articol",
    "Salva articolo":"Salvează articol","Carica materiale":"Încarcă material","Scarica materiale":"Descarcă material",
    "Quantità movimento":"Cantitate mișcare","Nota":"Notă","Movimenti recenti":"Mișcări recente","Nessun movimento":"Nicio mișcare",
    "Elimina articolo":"Șterge articol","Categoria:":"Categorie:","Codice:":"Cod:","Posizione:":"Poziție:","Etichetta":"Etichetă",
    "Stampa etichetta":"Tipărește eticheta","Torna all’articolo":"Înapoi la articol","QR articolo":"QR articol",
    "Carellas Ristorante · MAGAZZINO MATERIALI":"Carellas Ristorante · DEPOZIT MATERIALE",
    "Nuova manutenzione":"Mentenanță nouă","Crea manutenzione":"Creează mentenanță","Titolo *":"Titlu *","Tipo":"Tip","Tipo *":"Tip *",
    "Responsabile / ditta":"Responsabil / firmă","Responsabile:":"Responsabil:","Data prevista":"Data planificată",
    "Frequenza ordinaria":"Frecvență periodică","Settimanale":"Săptămânal","Mensile":"Lunar","Trimestrale":"Trimestrial",
    "Semestrale":"Semestrial","Annuale":"Anual","Costo previsto €":"Cost estimat €","Costo reale €":"Cost real €",
    "Note":"Note","Note esecuzione":"Note execuție","Completa intervento":"Finalizează intervenția","Segna completata":"Marchează finalizată",
    "Elimina manutenzione":"Șterge mentenanța","Storico":"Istoric","Ultima esecuzione:":"Ultima execuție:",
    "Prossima scadenza:":"Următorul termen:","Scadenza:":"Termen:","Nessuna manutenzione presente.":"Nicio mentenanță prezentă.",
    "Nessuna esecuzione registrata.":"Nicio execuție înregistrată.","Es. Pulizia filtri climatizzatore":"Ex. Curățare filtre climatizare",
    "Gruppi di zone":"Grupuri de zone","Gestisci gruppi":"Gestionează grupurile","Assegna zone":"Atribuie zone",
    "Nuovo gruppo":"Grup nou","Nome gruppo":"Numele grupului","Crea gruppo":"Creează grup","Elimina":"Șterge",
    "Salva assegnazione":"Salvează atribuirea","Zone senza gruppo:":"Zone fără grup:","Nessun gruppo creato.":"Niciun grup creat.",
    "Non ci sono ancora zone.":"Nu există încă zone.","Seleziona le zone che vuoi inserire in questo gruppo. Una zona può appartenere a un solo gruppo.":"Selectează zonele pentru acest grup. O zonă poate aparține unui singur grup.",
    "QR Zone":"QR Zone","Scarica tutti i QR":"Descarcă toate QR-urile",
    "Scarica in una volta sola i QR di tutte le zone, con file separati per la stampa da telefono o PC.":"Descarcă toate codurile QR ale zonelor într-o singură operație, ca fișiere separate pentru telefon sau PC.",
    "ZIP · PNG separati":"ZIP · PNG separate","ZIP · PDF separati":"ZIP · PDF separate","PDF unico":"PDF unic",
    "Per Brother da iPhone usa":"Pentru Brother de pe iPhone folosește","ogni zona viene salvata come immagine PNG indipendente.":"fiecare zonă este salvată ca imagine PNG separată.",
    "Password zone singole":"Parolă zone individuale","Usata dai QR che aprono direttamente una zona.":"Folosită de codurile QR care deschid direct o zonă.",
    "Password salvata":"Parolă salvată","Inserisci nuovamente la password":"Introdu din nou parola","Salva password zone":"Salvează parola zonelor",
    "Password QR di gruppo":"Parolă QR de grup","Password di gruppo salvata":"Parolă de grup salvată","Crea la password di gruppo":"Creează parola de grup",
    "Salva password di gruppo":"Salvează parola de grup","QR con tutte le zone":"QR cu toate zonele","Prima salva la password di gruppo.":"Mai întâi salvează parola de grup.",
    "Configurazione":"Configurare","URL pubblico:":"URL public:","Traduzione automatica:":"Traducere automată:",
    "Dispositivi per le notifiche":"Dispozitive pentru notificări","Rileva dispositivi da Home Assistant":"Detectează dispozitive din Home Assistant",
    "Diagnostica rilevamento:":"Diagnostic detectare:","Aggiunta manuale":"Adăugare manuală","Nome dispositivo":"Nume dispozitiv",
    "Entità/azione di notifica":"Entitate/acțiune notificare","Entità/azione":"Entitate/acțiune","Aggiungi dispositivo":"Adaugă dispozitiv",
    "Dispositivo attivo":"Dispozitiv activ","Invia prova":"Trimite test","Nessun dispositivo configurato.":"Niciun dispozitiv configurat.",
    "Accesso degli utenti Home Assistant":"Acces utilizatori Home Assistant","Utente":"Utilizator","Azione":"Acțiune","Abilita":"Activează",
    "Disabilita":"Dezactivează","Accesso del titolare esterno":"Acces extern proprietar","Indirizzo del portale:":"Adresa portalului:",
    "Nome utente del titolare":"Nume utilizator proprietar","Nuova password":"Parolă nouă","Portale Titolare attivo":"Portal proprietar activ",
    "Salva accesso titolare esterno":"Salvează acces extern proprietar","Backup":"Copie de siguranță",
    "Scarica database e fotografie in un unico archivio ZIP.":"Descarcă baza de date și fotografiile într-o singură arhivă ZIP.",
    "Scarica backup":"Descarcă copia de siguranță","Gestisci backup":"Gestionează copiile de siguranță",
    "Backup automatico":"Copie automată","Backup manuale":"Copie manuală","Backup disponibili":"Copii disponibile",
    "Crea backup adesso":"Creează copia acum","Salva pianificazione":"Salvează programarea","Carica e ripristina un backup":"Încarcă și restaurează o copie",
    "Data":"Dată","Dimensione":"Dimensiune","Azioni":"Acțiuni","Scarica":"Descarcă","Ripristina":"Restaurează",
    "Nessun backup interno presente.":"Nicio copie internă prezentă.","Ora giornaliera (0-23)":"Ora zilnică (0-23)",
    "Ultimo risultato:":"Ultimul rezultat:","Contatti WhatsApp":"Contacte WhatsApp","WhatsApp tecnici":"Tehnicieni WhatsApp",
    "Aggiungi contatto":"Adaugă contact","Aggiungi tecnico":"Adaugă tehnician","Nome / Ditta":"Nume / Firmă",
    "Numero WhatsApp":"Număr WhatsApp","Tecnici suggeriti per:":"Tehnicieni sugerați pentru:","Invia a tecnico":"Trimite tehnicianului",
    "Apri WhatsApp":"Deschide WhatsApp","Apertura WhatsApp…":"Se deschide WhatsApp…","Problema":"Problemă","Intervento":"Intervenție",
    "Inviato a":"Trimis către","Nessun tecnico configurato.":"Niciun tehnician configurat.","Aggiungi foto":"Adaugă fotografie","Scegli file":"Alege fișier",
    "Nessun file selezionato":"Niciun fișier selectat","Notifiche":"Notificări","Risposte ai ticket":"Răspunsuri la tichete","Qui trovi le risposte dei tecnici e le richieste di materiale.":"Aici găsești răspunsurile tehnicienilor și cererile de materiale.","Risposta":"Răspuns","Scrivi la risposta al tecnico":"Scrie răspunsul pentru tehnician","Apri anche WhatsApp con la risposta pronta":"Deschide și WhatsApp cu răspunsul pregătit","Invia risposta":"Trimite răspunsul","Tua risposta":"Răspunsul tău","Risposta tecnico":"Răspuns tehnician","Nessuna risposta ricevuta.":"Niciun răspuns primit.","Serve materiale":"Este necesar material","Materiale necessario":"Material necesar","Risposta salvata nel ticket.":"Răspuns salvat în tichet.","pz":"buc.","conf.":"pachet"
  };

  const reverse={};
  Object.entries(DE).forEach(([it,tr])=>{if(tr)reverse[tr]=it});
  Object.entries(RO).forEach(([it,tr])=>{if(tr)reverse[tr]=it});
  const deEntries=Object.entries(DE).sort((a,b)=>b[0].length-a[0].length);
  const roEntries=Object.entries(RO).sort((a,b)=>b[0].length-a[0].length);
  const storageKey='hausmeister-language:__USER_ID__';
  let language=localStorage.getItem(storageKey);
  if(!['it','de','ro'].includes(language)) language='__DEFAULT_LANG__';
  let applying=false;

  function toItalianBase(raw){
    const text=String(raw??'');
    const trimmed=text.trim();
    if(reverse[trimmed]){
      const lead=text.slice(0,text.indexOf(trimmed));
      const tail=text.slice(text.indexOf(trimmed)+trimmed.length);
      return lead+reverse[trimmed]+tail;
    }
    return text;
  }
  function translateStatic(raw,target=language){
    let base=toItalianBase(raw);
    if(target==='it') return base;
    const entries=target==='de'?deEntries:roEntries;
    for(const [it,tr] of entries){
      if(it && base.includes(it)) base=base.split(it).join(tr);
    }
    if(target==='de') base=base.replace(/\b(\d+) zone\b/g,'$1 Bereiche').replace(/\bpz\b/g,'Stk.');
    if(target==='ro') base=base.replace(/\b(\d+) zone\b/g,'$1 zone').replace(/\bpz\b/g,'buc.');
    return base;
  }
  function hasStaticTranslation(raw){
    const base=toItalianBase(raw);
    return translateStatic(base,language)!==base;
  }

  function autoTranslateUrl(){
    const marker='/api/hassio_ingress/';
    const current=location.pathname;
    const start=current.indexOf(marker);
    if(start>=0){
      const after=start+marker.length;
      const slash=current.indexOf('/',after);
      const base=slash>=0?current.slice(0,slash+1):current+'/';
      return base+'i18n/translate';
    }
    return location.pathname.startsWith('/manager')?'/manager/i18n/translate':'/i18n/translate';
  }

  function isUserTextNode(node){
    const el=node.parentElement;
    if(!el) return false;
    if(el.closest('.hm-language-switch')) return false;
    if(el.matches('.zone-row b,.material-card h2,.material-card p,p[style*="white-space:pre-wrap"],.movement-row .muted')) return true;
    if(el.matches('summary b')){
      const details=el.closest('details');
      if(details && details.querySelector('a[href^="zone/"],a[href*="/zone/"]')) return true;
    }
    if(el.matches('.topbar h1')){
      const t=String(node.nodeValue||'').trim();
      if(!DE[t]&&!RO[t]&&!reverse[t]&&!/^\d{4}-\d{4}$/.test(t)) return true;
    }
    if(el.tagName==='TD'){
      const table=el.closest('table');
      const row=el.parentElement;
      if(table&&row){
        const idx=[...row.children].indexOf(el);
        const th=table.querySelector('tr th:nth-child('+(idx+1)+')');
        const header=th?toItalianBase(th.textContent.trim()):'';
        if(['Zona','Nome','Descrizione','Posizione'].includes(header)) return true;
      }
    }
    if(el.closest('.notice,.warning') && !hasStaticTranslation(String(node.nodeValue||'').trim())) return true;
    return false;
  }

  function shouldAutoTranslate(text,node){
    const t=String(text||'').trim();
    if(language==='it'||!isUserTextNode(node)||t.length<2||t.length>500) return false;
    if(!/[A-Za-zÀ-ÿ]/.test(t)) return false;
    if(/^https?:\/\//i.test(t)||/@/.test(t)||t.includes('Home Assistant')) return false;
    if(/^\d+(?:[.,]\d+)?(?:\s*(?:pz|kg|m|l|mm|cm|bar|°C|%))?$/i.test(t)) return false;
    if(/^\d{4}-\d{4}$/.test(t)) return false;
    if(/^[A-Z0-9_.\/-]{2,24}$/.test(t)&&!t.includes(' ')) return false;
    if(hasStaticTranslation(t)) return false;
    return true;
  }

  async function translateUserText(){
    if(language==='it') return;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    const groups=new Map();
    while(walker.nextNode()){
      const node=walker.currentNode;
      if(node._hmBaseText===undefined) node._hmBaseText=node.nodeValue;
      const raw=String(node._hmBaseText);
      const m=raw.match(/^(\s*)(.*?)(\s*)$/s);
      if(!m||!shouldAutoTranslate(m[2],node)) continue;
      const original=m[2];
      if(!groups.has(original)) groups.set(original,[]);
      groups.get(original).push([node,m[1],m[3]]);
    }
    const texts=[...groups.keys()].slice(0,24);
    if(!texts.length) return;
    try{
      const response=await fetch(autoTranslateUrl(),{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:language,texts})});
      if(!response.ok) return;
      const data=await response.json();
      const translated=data.translations||{};
      applying=true;
      for(const original of texts){
        const value=translated[original]||original;
        for(const [node,prefix,suffix] of groups.get(original)||[]){
          if(node.isConnected) node.nodeValue=prefix+value+suffix;
        }
      }
      applying=false;
    }catch(e){}
  }

  function translateNode(node){
    if(node.nodeType===Node.TEXT_NODE){
      if(node._hmBaseText===undefined) node._hmBaseText=node.nodeValue;
      node.nodeValue=translateStatic(node._hmBaseText,language);
      return;
    }
    if(node.nodeType!==Node.ELEMENT_NODE||['SCRIPT','STYLE'].includes(node.tagName)) return;
    ['placeholder','aria-label','title'].forEach(attr=>{
      if(!node.hasAttribute(attr)) return;
      const key='_hmBase_'+attr;
      if(node[key]===undefined) node[key]=node.getAttribute(attr);
      node.setAttribute(attr,translateStatic(node[key],language));
    });
    [...node.childNodes].forEach(translateNode);
  }

  function setupFileInputs(){
    document.querySelectorAll('input[type="file"]').forEach(input=>{
      if(input.dataset.hmFileReady==='1') return;
      input.dataset.hmFileReady='1';
      input.style.position='absolute';input.style.opacity='0';input.style.width='1px';input.style.height='1px';
      const wrap=document.createElement('div');wrap.className='hm-file-wrap';
      const button=document.createElement('button');button.type='button';button.className='hm-file-button';
      button.textContent=translateStatic('📷 Aggiungi foto',language);
      if(button.firstChild) button.firstChild._hmBaseText='📷 Aggiungi foto';
      const name=document.createElement('span');name.className='hm-file-name';
      name.textContent=translateStatic('Nessun file selezionato',language);
      if(name.firstChild) name.firstChild._hmBaseText='Nessun file selezionato';
      button.addEventListener('click',()=>input.click());
      input.addEventListener('change',()=>{
        if(input.files&&input.files.length){
          name.textContent=[...input.files].map(f=>f.name).join(', ');
          if(name.firstChild) name.firstChild._hmBaseText=name.textContent;
        }else{
          name.textContent=translateStatic('Nessun file selezionato',language);
          if(name.firstChild) name.firstChild._hmBaseText='Nessun file selezionato';
        }
      });
      wrap.append(button,name);input.insertAdjacentElement('afterend',wrap);
    });
  }

  function addGroupTicketButtons(){
    document.querySelectorAll('details a[href^="zone/"]').forEach(a=>{
      const m=(a.getAttribute('href')||'').match(/^zone\/(\d+)$/);
      if(!m||a.parentElement.querySelector('.hm-group-ticket[data-zone="'+m[1]+'"]')) return;
      const b=document.createElement('a');
      b.className='hm-group-ticket';b.dataset.zone=m[1];b.href='quick-ticket/'+m[1];b._hmBaseText='Crea ticket';
      b.textContent=translateStatic('Crea ticket',language);
      a.insertAdjacentElement('afterend',b);
    });
  }

  function apply(){
    if(applying) return;
    applying=true;
    document.documentElement.lang=language;
    translateNode(document.body);
    document.title=translateStatic(document.title,language);
    document.querySelectorAll('[data-language]').forEach(button=>{
      const active=button.dataset.language===language;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    setupFileInputs();
    addGroupTicketButtons();
    applying=false;
    setTimeout(translateUserText,0);
  }

  function setLanguage(next){
    if(!['it','de','ro'].includes(next)||next===language) return;
    language=next;
    localStorage.setItem(storageKey,language);
    apply();
    window.dispatchEvent(new CustomEvent('app-language-changed',{detail:{language}}));
  }

  window.HausmeisterI18n={apply,getLanguage:()=>language,setLanguage,translate:translateStatic};
  document.addEventListener('DOMContentLoaded',()=>{
    document.querySelectorAll('[data-language]').forEach(button=>button.addEventListener('click',()=>setLanguage(button.dataset.language)));
    apply();
    new MutationObserver(records=>{
      if(applying) return;
      if(records.some(record=>record.addedNodes&&record.addedNodes.length)) apply();
    }).observe(document.body,{childList:true,subtree:true});
  });
})();
</script>""".replace('__USER_ID__', hm_user_id.replace("'", "")).replace('__DEFAULT_LANG__', default_language)
'''

text = text[:start] + new_block + text[end:]
path.write_text(text, encoding='utf-8')
