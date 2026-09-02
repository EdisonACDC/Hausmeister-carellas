# Hausmeister-carellas

Add-on Home Assistant per la gestione delle segnalazioni di manutenzione del ristorante e delle camere del personale.

## Funzioni della versione 1.0.2

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
- Attivazione/disattivazione delle zone e rigenerazione dei QR.
- Download e stampa dei QR.
- Protezione contro tentativi ripetuti del PIN.
- Backup ZIP di database e fotografie.
- Eliminazione definitiva dei ticket risolti e delle fotografie collegate.
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

Nelle opzioni dell'add-on, `notify_service` deve contenere il nome del servizio senza il prefisso `notify.`. Esempio: per `notify.mobile_app_iphone`, inserire `mobile_app_iphone`. La pagina **Impostazioni** contiene un pulsante di prova.

## Traduzione

Per tradurre automaticamente le descrizioni, inserire in `translation_url` l'endpoint completo di un servizio compatibile LibreTranslate (per esempio `https://server/translate`) e, se richiesto, la chiave in `translation_api_key`. Se il servizio non è configurato o non risponde, il ticket viene comunque creato e la traduzione può essere inserita manualmente.

## Aggiornamento

Aggiornare l'add-on senza disinstallarlo. Database, PIN, zone, QR, ticket e fotografie restano in `/data` e vengono conservati. Dopo l'aggiornamento verificare `/health`, la dashboard e un QR esistente.
