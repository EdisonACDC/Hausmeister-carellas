from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

old = '''    contact_buttons = ''.join(
        f'<a class="btn" style="background:#16883f;margin:5px 5px 5px 0" href="{ticket_id}/whatsapp/{c["id"]}" target="_blank" rel="noopener">WhatsApp · {esc(c["name"])}</a>'
        for c in whatsapp_contacts
    )
    if not contact_buttons:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
'''

new = '''    contact_buttons = ''
    wa_base = whatsapp_public_base_url()
    if whatsapp_contacts and wa_base:
        wa_token = whatsapp_ticket_token(ticket_id)
        ticket_link = f'{wa_base}/w/{urllib.parse.quote(wa_token, safe="")}'
        for c in whatsapp_contacts:
            wa_message = (
                f'🔧 Nuovo intervento Hausmeister Carellas\\n'
                f'Ticket: {t["ticket_code"]}\\n'
                f'Zona: {t["zone_name"]}\\n'
                f'Categoria: {t["category"]}\\n'
                f'Priorità: {t["priority"] or "Normale"}\\n'
                f'Problema: {t["description_original"][:700]}\\n\\n'
                f'📋 Ticket completo e foto: {ticket_link}'
            )
            wa_url = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_message)}'
            contact_buttons += f'<a class="btn" style="background:#16883f;margin:5px 5px 5px 0" href="{esc(wa_url)}" target="_top">WhatsApp · {esc(c["name"])}</a>'
    elif whatsapp_contacts:
        contact_buttons = '<div class="notice warning">Configura URL pubblico o tunnel pubblico della Beta per poter inserire nel messaggio il link al ticket.</div>'
    else:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
'''

if old not in text:
    raise SystemExit('WhatsApp button marker not found')

text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
