"""Publish Hausmeister Carellas data as Home Assistant sensor states.

This process is intentionally independent from the web application. It reads the
same SQLite database and refreshes the Home Assistant states periodically, so a
ticket or stock change appears in Lovelace without modifying every HTTP handler.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB_PATH = Path("/data/hausmeister.db")
DEFAULT_API_BASE = "http://supervisor/core/api"
ENTITY_PREFIX = "sensor.hausmeister_carellas"
REFRESH_SECONDS = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_text(value: object, limit: int = 100) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit] + ("…" if len(text) > limit else "")


def read_snapshot(db_path: Path) -> dict | None:
    if not db_path.exists():
        return None

    con = sqlite3.connect(db_path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        tickets = con.execute(
            """
            SELECT t.ticket_code, t.description_it, t.description_original,
                   t.priority, t.status, t.created_at, z.name AS zone_name
            FROM tickets t
            JOIN zones z ON z.id=t.zone_id
            WHERE t.status <> 'Risolto'
            ORDER BY CASE t.priority WHEN 'Urgente' THEN 0 WHEN 'Alta' THEN 1 ELSE 2 END,
                     t.id DESC
            LIMIT 30
            """
        ).fetchall()
        open_count = con.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE status <> 'Risolto'"
        ).fetchone()["n"]
        urgent_count = con.execute(
            """
            SELECT COUNT(*) AS n FROM tickets
            WHERE status <> 'Risolto' AND priority IN ('Alta', 'Urgente')
            """
        ).fetchone()["n"]
        low_stock = con.execute(
            """
            SELECT name, quantity, reorder_level, unit
            FROM materials
            WHERE quantity <= reorder_level
            ORDER BY quantity ASC, name ASC
            LIMIT 30
            """
        ).fetchall()
    finally:
        con.close()

    ticket_items = [
        {
            "id": row["ticket_code"],
            "title": compact_text(row["description_it"] or row["description_original"]),
            "zone": row["zone_name"],
            "priority": row["priority"] or "Normale",
            "status": row["status"],
            "date": str(row["created_at"] or "")[:16].replace("T", " "),
        }
        for row in tickets
    ]
    stock_items = [
        {
            "name": row["name"],
            "quantity": f'{row["quantity"]} {row["unit"]}'.strip(),
            "threshold": f'{row["reorder_level"]} {row["unit"]}'.strip(),
            "status": "Bassa",
        }
        for row in low_stock
    ]
    return {
        "updated_at": utc_now(),
        "open_count": open_count,
        "urgent_count": urgent_count,
        "low_stock_count": len(stock_items),
        "tickets": ticket_items,
        "items": stock_items,
    }


def sensor_payloads(snapshot: dict) -> dict[str, dict]:
    common = {"integration": "Hausmeister Carellas", "updated_at": snapshot["updated_at"]}
    return {
        f"{ENTITY_PREFIX}_ticket_aperti": {
            "state": str(snapshot["open_count"]),
            "attributes": {
                **common,
                "friendly_name": "Hausmeister Carellas · Ticket aperti",
                "icon": "mdi:ticket-confirmation-outline",
                "tickets": snapshot["tickets"],
            },
        },
        f"{ENTITY_PREFIX}_ticket_urgenti": {
            "state": str(snapshot["urgent_count"]),
            "attributes": {
                **common,
                "friendly_name": "Hausmeister Carellas · Ticket urgenti",
                "icon": "mdi:alert-circle",
            },
        },
        f"{ENTITY_PREFIX}_scorte_basse": {
            "state": str(snapshot["low_stock_count"]),
            "attributes": {
                **common,
                "friendly_name": "Hausmeister Carellas · Scorte basse",
                "icon": "mdi:package-variant-closed-alert",
                "items": snapshot["items"],
            },
        },
    }


def publish_state(api_base: str, token: str, entity_id: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/states/{entity_id}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"Home Assistant ha risposto HTTP {response.status}")


def publish_once(db_path: Path, api_base: str, token: str, dry_run: bool = False) -> bool:
    snapshot = read_snapshot(db_path)
    if snapshot is None:
        return False
    payloads = sensor_payloads(snapshot)
    if dry_run:
        print(json.dumps(payloads, ensure_ascii=False, indent=2), flush=True)
        return True
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN non disponibile")
    for entity_id, payload in payloads.items():
        publish_state(api_base, token, entity_id, payload)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", type=Path, default=Path(os.getenv("HA_SENSOR_DB_PATH", DEFAULT_DB_PATH)))
    parser.add_argument("--api-base", default=os.getenv("HA_SENSOR_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--interval", type=int, default=REFRESH_SECONDS)
    args = parser.parse_args()
    token = os.getenv("SUPERVISOR_TOKEN", "")

    while True:
        try:
            if publish_once(args.db, args.api_base, token, args.dry_run):
                if not args.dry_run:
                    print("Sensori Home Assistant aggiornati", flush=True)
            else:
                print("Database non ancora disponibile; nuovo tentativo in arrivo", flush=True)
        except (OSError, sqlite3.Error, urllib.error.URLError, RuntimeError) as exc:
            print(f"Aggiornamento sensori Home Assistant non riuscito: {exc}", flush=True)
        if args.once:
            break
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    main()
