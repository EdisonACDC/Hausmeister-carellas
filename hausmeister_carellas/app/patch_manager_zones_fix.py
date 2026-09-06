from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

start_marker = "@public_app.get('/manager/zones', response_class=HTMLResponse)\ndef manager_zones_page"
end_marker = "\n\n@public_app.get('/manager/materials', response_class=HTMLResponse)"

if start_marker not in text or end_marker not in text:
    raise SystemExit('Manager zones function markers not found')

start = text.index(start_marker)
end = text.index(end_marker, start)

replacement = r'''@public_app.get('/manager/zones', response_class=HTMLResponse)
def manager_zones_page(request: Request, message: str = '', created: int = 0):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    lang = public_language(request)
    con = db()
    zones = con.execute("""
        SELECT z.*, g.name AS group_name, COUNT(t.id) AS ticket_count
        FROM zones z
        LEFT JOIN zone_groups g ON g.id = z.group_id
        LEFT JOIN tickets t ON t.zone_id = z.id
        GROUP BY z.id
        ORDER BY CASE WHEN g.name IS NULL THEN 1 ELSE 0 END, g.name, z.name
    """).fetchall()
    con.close()

    grouped = {}
    ungrouped_label = 'Ohne Gruppe' if lang == 'de' else 'Senza gruppo'
    for zone in zones:
        group_name = zone['group_name'] if zone['group_name'] else ungrouped_label
        grouped.setdefault(group_name, []).append(zone)

    rows = ''
    for group_name, group_zones in grouped.items():
        zone_items = ''
        for zone in group_zones:
            highlight = 'box-shadow:0 0 0 2px #8fc63d inset;' if zone['id'] == created else ''
            status_text = manager_text(lang, 'active') if zone['active'] else manager_text(lang, 'inactive')
            zone_items += (
                f'<div class="zone-row" style="{highlight}">'
                f'<div><b>{esc(zone["name"])}</b><br>'
                f'<span class="muted">{status_text} · Ticket: {zone["ticket_count"]}</span></div>'
                f'<a class="btn" href="/manager/zone/{zone["id"]}">{manager_text(lang, "manage_qr")}</a>'
                f'</div>'
            )
        unit = 'Bereiche' if lang == 'de' else 'zone'
        rows += (
            '<details style="border:1px solid var(--line);border-radius:16px;margin-bottom:11px;overflow:hidden">'
            '<summary style="cursor:pointer;padding:14px;display:flex;justify-content:space-between;align-items:center;list-style:none;background:rgba(25,105,190,.10)">'
            f'<span><b>{esc(group_name)}</b><br><span class="muted">{len(group_zones)} {unit}</span></span>'
            '<span style="font-size:20px">⌄</span></summary>'
            f'<div style="padding:8px">{zone_items}</div></details>'
        )

    if not rows:
        rows = f'<p class="muted">{manager_text(lang, "no_zones")}</p>'

    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = (
        f'{notice}<div class="grid">'
        f'<div class="card span-8"><h2>{manager_text(lang, "existing_zones")}</h2>{rows}</div>'
        f'<div class="card span-4"><h2>{manager_text(lang, "new_zone")}</h2>'
        f'<form method="post" action="/manager/zone">'
        f'<label>{manager_text(lang, "name")}</label>'
        f'<input name="name" maxlength="80" required placeholder="Es. Cucina">'
        f'<button>{manager_text(lang, "create_zone")}</button></form></div></div>'
    )
    return page(manager_text(lang, 'zones'), body, manager=True, lang=lang)
'''

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')
