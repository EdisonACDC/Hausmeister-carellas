# Hausmeister-carellas

Add-on Home Assistant per la gestione delle segnalazioni di manutenzione del ristorante e delle camere del personale.

## Funzioni già presenti nella versione 0.1.0

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
- Campi già predisposti per traduzione automatica in italiano.

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

La porta `8099` è riservata alla gestione privata via Ingress. La porta `8080` serve esclusivamente il portale pubblico delle segnalazioni.

## Prossimi passi

- traduzione locale automatica verso italiano;
- notifica Home Assistant solo al dispositivo configurato;
- cambio stato ticket;
- visualizzazione sicura delle foto;
- blocco tentativi PIN e rate limiting;
- rigenerazione/revoca QR;
- esportazione e stampa QR.
