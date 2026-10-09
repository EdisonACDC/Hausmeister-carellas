# Collaudo e correzioni prima della consegna commerciale — 2026-10-09

Stato: **non certificato**. Il README descrive le funzionalità, non fornisce prove di collaudo sull'installazione Carellas.

## P0 — Sicurezza e perdita dati
- Verificare autenticazione Ingress, portale pubblico QR e portale titolare: ruoli, scadenze sessioni, limiti PIN, autorizzazioni su foto e API.
- Testare backup ZIP e **ripristino effettivo** su installazione pulita; preservare database, foto, zone e utenti.
- Verificare accesso pubblico tramite Cloudflared senza esporre endpoint amministrativi.

## P1 — Affidabilità
- Testare apertura ticket IT/DE da iPhone, Android e PC, fino a 5 foto, filtri, priorità, notifiche e deep-link.
- Testare CRUD zone, rigenerazione QR, materiali e movimenti concorrenti di magazzino; nessuna quantità negativa.
- Verificare registri privi di eccezioni e restart/reinstallazione senza perdita dati.

## Accettazione
10 ticket consecutivi da QR e da interfaccia, 3 dispositivi, tutte le operazioni autorizzate, backup+ripristino riusciti e nessun accesso non autorizzato. Annotare versione, data, evidenze e responsabile.
