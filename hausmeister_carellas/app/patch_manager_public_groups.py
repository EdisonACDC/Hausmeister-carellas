from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# --- Portale titolare: Dashboard con gruppi a tendina ---
old = "    zones = con.execute('SELECT * FROM zones ORDER BY name').fetchall()\n    tickets = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC LIMIT 50').fetchall()"
new = "    zones = con.execute(\"SELECT z.*, g.name AS group_name FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id ORDER BY COALESCE(g.name, 'ZZZZZZ'), z.name\").fetchall()\n    tickets = con.execute('SELECT t.*, z.name AS zone_name FROM tickets t JOIN zones z ON z.id=t.zone_id ORDER BY t.id DESC LIMIT 50').fetchall()"
if old in text:
    text = text.replace(old, new, 1)
elif 'SELECT z.*, g.name AS group_name FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id' not in text:
    raise SystemExit('Manager dashboard zone query marker not found')

old = "    zone_rows = ''.join(f'<div class=\"zone-row\"><div><b>{esc(z[\"name\"])}</b><br><span class=\"muted\">{manager_text(lang, \"active\") if z[\"active\"] else manager_text(lang, \"inactive\")}</span></div><a class=\"btn\" href=\"/manager/zone/{z[\"id\"]}\">QR →</a></div>' for z in zones) or f'<p class=\"muted\">{manager_text(lang, \"no_zones\")}</p>'"
new = '''    manager_grouped_zones = {}
    for z in zones:
        group_name = z['group_name'] or ('Ohne Gruppe' if lang == 'de' else 'Senza gruppo')
        manager_grouped_zones.setdefault(group_name, []).append(z)
    zone_rows = ''
    for group_name, group_zones in manager_grouped_zones.items():
        initial = esc((group_name.strip()[:1] or 'Z').upper())
        zone_items = ''.join(
            f'<a href="/manager/zone/{z["id"]}" style="text-decoration:none;color:inherit;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 13px;margin:7px 9px;border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.025)"><div style="display:flex;align-items:center;gap:10px"><span style="width:10px;height:10px;border-radius:50%;background:{"#39d98a" if z["active"] else "#77808f"}"></span><div><b>{esc(z["name"])}</b><br><span class="muted">{manager_text(lang, "active") if z["active"] else manager_text(lang, "inactive")}</span></div></div><span style="font-size:22px;opacity:.65">›</span></a>'
            for z in group_zones
        )
        zone_rows += f'<details style="overflow:hidden;border:1px solid var(--line);border-radius:17px;margin-bottom:10px;background:linear-gradient(135deg,rgba(25,105,190,.16),rgba(255,255,255,.025))"><summary style="cursor:pointer;padding:14px;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:10px"><span style="display:flex;align-items:center;gap:12px"><span style="width:40px;height:40px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;font-weight:800;background:linear-gradient(145deg,#2388ee,#1559a7);color:white">{initial}</span><span><b>{esc(group_name)}</b><br><span class="muted">{len(group_zones)} {"Bereiche" if lang == "de" else "zone"}</span></span></span><span style="font-size:20px">⌄</span></summary><div style="padding:0 1px 7px">{zone_items}</div></details>'
    if not zone_rows:
        zone_rows = f'<p class="muted">{manager_text(lang, "no_zones")}</p>' '''
if old in text:
    text = text.replace(old, new.rstrip(), 1)
elif 'manager_grouped_zones = {}' not in text:
    raise SystemExit('Manager dashboard zone rows marker not found')

# --- Portale titolare: pagina Zone / QR raggruppata ---
old = "    zones = con.execute('SELECT z.*, COUNT(t.id) ticket_count FROM zones z LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY z.name').fetchall()"
new = "    zones = con.execute(\"SELECT z.*, g.name AS group_name, COUNT(t.id) ticket_count FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id LEFT JOIN tickets t ON t.zone_id=z.id GROUP BY z.id ORDER BY COALESCE(g.name, 'ZZZZZZ'), z.name\").fetchall()"
if old in text:
    text = text.replace(old, new, 1)
elif 'g.name AS group_name, COUNT(t.id) ticket_count' not in text:
    raise SystemExit('Manager zones query marker not found')

old = "    rows = ''.join(f'''<tr{' class=\"new-zone\"' if z['id'] == created else ''}><td><b>{esc(z['name'])}</b></td><td>{manager_text(lang, 'active') if z['active'] else manager_text(lang, 'inactive')}</td><td>{z['ticket_count']}</td><td><a class=\"btn\" href=\"/manager/zone/{z['id']}\">{manager_text(lang, 'manage_qr')}</a></td></tr>''' for z in zones) or f'<tr><td colspan=\"4\">{manager_text(lang, \"no_zones\")}</td></tr>'"
new = '''    manager_zone_groups = {}
    for z in zones:
        group_name = z['group_name'] or ('Ohne Gruppe' if lang == 'de' else 'Senza gruppo')
        manager_zone_groups.setdefault(group_name, []).append(z)
    rows = ''
    for group_name, group_zones in manager_zone_groups.items():
        items = ''.join(
            f'<div class="zone-row" {"style=\\"box-shadow:0 0 0 2px #8fc63d inset\\"" if z["id"] == created else ""}><div><b>{esc(z["name"])}</b><br><span class="muted">{manager_text(lang, "active") if z["active"] else manager_text(lang, "inactive")} · Ticket: {z["ticket_count"]}</span></div><a class="btn" href="/manager/zone/{z["id"]}">{manager_text(lang, "manage_qr")}</a></div>'
            for z in group_zones
        )
        rows += f'<details style="border:1px solid var(--line);border-radius:16px;margin-bottom:11px;overflow:hidden"><summary style="cursor:pointer;padding:14px;display:flex;justify-content:space-between;align-items:center;list-style:none;background:rgba(25,105,190,.10)"><span><b>{esc(group_name)}</b><br><span class="muted">{len(group_zones)} {"Bereiche" if lang == "de" else "zone"}</span></span><span>⌄</span></summary><div style="padding:8px">{items}</div></details>'
    if not rows:
        rows = f'<p class="muted">{manager_text(lang, "no_zones")}</p>' '''
if old in text:
    text = text.replace(old, new.rstrip(), 1)
elif 'manager_zone_groups = {}' not in text:
    raise SystemExit('Manager zones rows marker not found')

old = "    body = f'''{notice}<style>.new-zone td{{background:#f1f8df}}</style><div class=\"grid\"><div class=\"card span-8\"><h2>{manager_text(lang, 'existing_zones')}</h2><div class=\"table-wrap\"><table><tr><th>{manager_text(lang, 'zone')}</th><th>{manager_text(lang, 'status')}</th><th>Ticket</th><th></th></tr>{rows}</table></div></div><div class=\"card span-4\"><h2>{manager_text(lang, 'new_zone')}</h2><form method=\"post\" action=\"/manager/zone\"><label>{manager_text(lang, 'name')}</label><input name=\"name\" maxlength=\"80\" required placeholder=\"Es. Cucina\"><button>{manager_text(lang, 'create_zone')}</button></form></div></div>'''"
new = "    body = f'''{notice}<div class=\"grid\"><div class=\"card span-8\"><h2>{manager_text(lang, 'existing_zones')}</h2>{rows}</div><div class=\"card span-4\"><h2>{manager_text(lang, 'new_zone')}</h2><form method=\"post\" action=\"/manager/zone\"><label>{manager_text(lang, 'name')}</label><input name=\"name\" maxlength=\"80\" required placeholder=\"Es. Cucina\"><button>{manager_text(lang, 'create_zone')}</button></form></div></div>'''"
if old in text:
    text = text.replace(old, new, 1)

# --- QR di gruppo pubblico: gruppi a tendina + Senza gruppo ---
old = "    zones = con.execute('SELECT * FROM zones WHERE active=1 ORDER BY name').fetchall()\n    con.close()\n    buttons = ''.join(f'<a class=\"btn\" style=\"width:100%;margin:6px 0\" href=\"../../r/{esc(zone[\"token\"])}\">{esc(zone[\"name\"])}</a>' for zone in zones) or f'<p class=\"muted\">{public_text(lang, \"no_zones\")}</p>'"
new = '''    zones = con.execute("SELECT z.*, g.name AS group_name FROM zones z LEFT JOIN zone_groups g ON g.id=z.group_id WHERE z.active=1 ORDER BY COALESCE(g.name, 'ZZZZZZ'), z.name").fetchall()
    con.close()
    public_groups = {}
    for zone in zones:
        group_name = zone['group_name'] or ('Ohne Gruppe' if lang == 'de' else 'Senza gruppo')
        public_groups.setdefault(group_name, []).append(zone)
    buttons = ''
    for group_name, group_zones in public_groups.items():
        zone_buttons = ''.join(
            f'<a class="btn" style="display:block;width:100%;margin:7px 0;text-align:left" href="../../r/{esc(zone["token"])}">{esc(zone["name"])} <span style="float:right">›</span></a>'
            for zone in group_zones
        )
        buttons += f'<details style="border:1px solid var(--line);border-radius:16px;margin:12px 0;overflow:hidden"><summary style="cursor:pointer;list-style:none;padding:14px 15px;display:flex;justify-content:space-between;align-items:center;background:rgba(25,105,190,.10)"><span><b>{esc(group_name)}</b><br><span class="muted">{len(group_zones)} {"Bereiche" if lang == "de" else "zone"}</span></span><span style="font-size:20px">⌄</span></summary><div style="padding:5px 12px 10px">{zone_buttons}</div></details>'
    if not buttons:
        buttons = f'<p class="muted">{public_text(lang, "no_zones")}</p>' '''
if old in text:
    text = text.replace(old, new.rstrip(), 1)
elif 'public_groups = {}' not in text:
    raise SystemExit('Public group QR marker not found')

path.write_text(text, encoding='utf-8')
