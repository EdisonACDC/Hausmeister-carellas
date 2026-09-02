# Hausmeister-carellas

Add-on Home Assistant per la gestione delle segnalazioni di manutenzione del ristorante e delle camere del personale.

## Funzioni della versione 1.3.0

- Interfaccia amministrativa dentro Home Assistant tramite Ingress.
- Creazione zone personalizzate.
- Token univoco e QR automatico per ogni zona.
- PIN condiviso salvato solo come hash Argon2.
- Portale pubblico separato su porta 8080.
- Nome e cognome obbligatori per chi segnala.
- Categoria guasto e descrizione.
- Fino a 5 immagini per ticket, massimo 8 MB ciascuna.
- Database SQLite persistente in `/data`.
- Ticket con codice progressivo e stato iniziale `Nuovo`.
- Dashboard con conteggi e ticket recenti.
- Ricerca e filtro dei ticket, con esportazione CSV.
- Gestione stato, priorità, note interne e traduzione italiana.
- Traduzione automatica opzionale tramite endpoint compatibile LibreTranslate.
- Visualizzazione protetta delle fotografie nell'interfaccia Ingress.
- Notifiche tramite un servizio `notify` di Home Assistant.
- Apertura diretta del ticket corretto toccando la notifica, tramite collegamento firmato e temporaneo.
- Gestione di più telefoni dalle Impostazioni: aggiunta, rinomina, modifica dell'entità, attivazione, prova ed eliminazione.
- Rilevamento automatico dei dispositivi mobili registrati in Home Assistant, con diagnostica del collegamento e aggiunta manuale di riserva.
- Errori della password mostrati nella pagina del QR in italiano o tedesco, senza schermate JSON tecniche.
- Portale Titolare esterno e separato da Home Assistant, con credenziali dedicate e interfaccia italiana/tedesca.
- Il titolare può consultare ticket, foto e traduzioni, cambiare stato e priorità, scrivere note ed eliminare soltanto ticket risolti.
- Il titolare non può accedere a PIN, QR, zone, dispositivi di notifica o configurazioni tecniche.
- Attivazione/disattivazione delle zone e rigenerazione dei QR.
- Download e stampa dei QR.
- Protezione contro tentativi ripetuti del PIN.
- Backup ZIP di database e fotografie.
- Eliminazione definitiva dei ticket risolti e delle fotografie collegate.
- Dashboard con contatori, ticket recenti e zone; creazione zone e gestione PIN restano nelle sezioni dedicate.
- Rinomina ed eliminazione delle zone; eliminando una zona vengono rimossi anche i relativi ticket e file.
- PIN delle zone visibile dopo il nuovo salvataggio.
- Secondo PIN visibile e indipendente per il QR che raggruppa tutte le zone attive.
- Traduzione dei ticket sia in italiano sia in tedesco.
- Password alfanumeriche per QR singoli e di gruppo, con tastiera completa su iPhone e caratteri coperti durante l'accesso.
- Traduzione automatica preconfigurata in italiano e tedesco per i nuovi ticket, con pulsante "Traduci ora" per quelli già esistenti.
- Secondo servizio automatico di riserva per la traduzione e messaggio diagnostico visibile quando entrambi i servizi non rispondono.
- Portale pubblico automaticamente in italiano o tedesco in base alla lingua impostata nel browser dell'operatore.
- Aggiornamento immediato della lista dopo la creazione di una zona, senza dover uscire e rientrare nell'add-on.
- Evidenziazione rossa dei ticket aperti con priorità Alta o Urgente nella dashboard, nella lista e nella scheda del ticket.
- Uscita controllata dal modulo: il tasto Indietro chiude la sessione, torna alla password e poi alla Fotocamera o alla pagina precedente.
- Migrazione automatica dei dati dalle versioni precedenti.

## Installazione in Home Assistant

1. Vai in **Impostazioni > Add-on > Negozio add-on**.
2. Apri il menu in alto a destra e scegli **Repository**.
3. Aggiungi questo repository:
   `https://github.com/EdisonACDC/Hausmeister-carellas`
4. Aggiorna il negozio add-on.
5. Installa **Hausmeister Carellas**.
6. Avvia l'add-on e attiva **Mostra nella barra laterale**.

## Prima configurazione

Apri l'interfaccia dell'add-on da Home Assistant e:

1. imposta il PIN condiviso;
2. crea una zona;
3. nelle opzioni add-on imposta `public_base_url` quando sarà pronto l'indirizzo HTTPS pubblico definitivo;
4. genera il QR della zona.

Per questa installazione l'URL pubblico è:

`https://homeassistant.9ceepe4a2ca5c03h.myfritz.net`

Non aggiungere la porta `8089` all'URL stampato nel QR: il reverse proxy riceve HTTPS sulla porta 443 e inoltra internamente al portale.

La porta `8099` è riservata alla gestione privata via Ingress. La porta `8080` del container serve esclusivamente il portale pubblico ed è pubblicata da Home Assistant sulla porta host configurata (nel vostro caso `8089`). Le regole FRITZ!Box già necessarie al collegamento non devono essere rimosse.

## Notifiche

I telefoni si gestiscono direttamente nella pagina **Impostazioni** dell'add-on. Il pulsante **Rileva dispositivi da Home Assistant** legge automaticamente le azioni `mobile_app`; l'aggiunta manuale resta disponibile come riserva. Il vecchio valore `notify_service` viene importato automaticamente al primo avvio. Le notifiche sono normali: non forzano suono o volume e rispettano la modalità silenziosa dell'iPhone.

## Traduzione

Per tradurre automaticamente le descrizioni, inserire in `translation_url` l'endpoint completo di un servizio compatibile LibreTranslate (per esempio `https://server/translate`) e, se richiesto, la chiave in `translation_api_key`. Se il servizio non è configurato o non risponde, il ticket viene comunque creato e la traduzione può essere inserita manualmente.

## Aggiornamento

Aggiornare l'add-on senza disinstallarlo. Database, PIN, zone, QR, ticket e fotografie restano in `/data` e vengono conservati. Dopo l'aggiornamento verificare `/health`, la dashboard e un QR esistente.
