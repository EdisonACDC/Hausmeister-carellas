from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

if 'def direct_zone_ticket_url(' not in text:
    helper_marker = '\n\ndef ticket_notification_url(ticket_id: int):\n'
    helper = r'''

def direct_zone_ticket_url(zone):
    base = public_base_url()
    signed = serializer().dumps({
        'zone': zone['token'],
        'purpose': 'admin-direct-ticket',
    })
    suffix = f'/direct-ticket/{urllib.parse.quote(signed, safe="")}'
    return f'{base}{suffix}' if base else suffix
'''
    if helper_marker not in text:
        raise SystemExit('Direct ticket helper marker not found')
    text = text.replace(helper_marker, helper + helper_marker, 1)

    old_dashboard = 'f\'<a href="zone/{z["id"]}" style="text-decoration:none;color:inherit;display:flex;'
    new_dashboard = 'f\'<a href="{esc(direct_zone_ticket_url(z))}" style="text-decoration:none;color:inherit;display:flex;'
    if old_dashboard not in text:
        raise SystemExit('Admin dashboard zone link marker not found')
    text = text.replace(old_dashboard, new_dashboard, 1)

    old_zones = "<td><b>{esc(z['name'])}</b></td>"
    new_zones = "<td><a href=\"{esc(direct_zone_ticket_url(z))}\" style=\"color:inherit;text-decoration:underline;text-underline-offset:3px\"><b>{esc(z['name'])}</b></a></td>"
    if old_zones not in text:
        raise SystemExit('Admin zones name link marker not found')
    text = text.replace(old_zones, new_zones, 1)

    manager_name = "f'<div><b>{esc(zone[\"name\"])}</b><br>'"
    manager_name_link = "f'<div><a href=\"{esc(direct_zone_ticket_url(zone))}\" style=\"color:inherit;text-decoration:underline;text-underline-offset:3px\"><b>{esc(zone[\"name\"])}</b></a><br>'"
    if manager_name in text:
        text = text.replace(manager_name, manager_name_link, 1)

    route_marker = "\n\n@public_app.get('/r/{token}', response_class=HTMLResponse)\n"
    route = r'''

@public_app.get('/direct-ticket/{signed_token}')
def direct_ticket_login(signed_token: str):
    try:
        payload = serializer().loads(signed_token, max_age=5 * 60)
        if payload.get('purpose') != 'admin-direct-ticket':
            raise BadSignature('Invalid purpose')
        zone_token = str(payload['zone'])
    except (BadSignature, KeyError, TypeError, ValueError):
        raise HTTPException(403, 'Collegamento diretto non valido o scaduto')
    con = db()
    zone = con.execute('SELECT id FROM zones WHERE token=? AND active=1', (zone_token,)).fetchone()
    con.close()
    if not zone:
        raise HTTPException(404, 'Zona non valida o disattivata')
    response = RedirectResponse(f'../r/{urllib.parse.quote(zone_token, safe="")}', status_code=303)
    response.set_cookie(
        'hm_session', serializer().dumps({'zone': zone_token}),
        max_age=86400, httponly=True, secure=True, samesite='lax', path='/'
    )
    return response
'''
    if route_marker not in text:
        raise SystemExit('Direct ticket public route marker not found')
    text = text.replace(route_marker, route + route_marker, 1)

path.write_text(text, encoding='utf-8')
