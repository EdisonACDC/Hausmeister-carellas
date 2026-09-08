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

        description_it = t["description_it"] or t["description_original"]
        description_de = t["description_de"] or t["description_original"]
        description_ro, _description_ro_status = translate_text(t["description_original"], 'ro')
        description_ro = description_ro or t["description_original"]

        category_de = {
            'Elettrico': 'Elektrik', 'Idraulico': 'Sanitär / Wasser', 'Muratore': 'Maurer / Bau',
            'Climatizzazione': 'Klimaanlage', 'Porta/Finestra': 'Tür / Fenster',
            'Attrezzatura cucina': 'Küchengerät', 'Altro': 'Sonstiges'
        }.get(t["category"], t["category"])
        category_ro = {
            'Elettrico': 'Electric', 'Idraulico': 'Instalații sanitare / Apă', 'Muratore': 'Zidar / Construcții',
            'Climatizzazione': 'Climatizare', 'Porta/Finestra': 'Ușă / Fereastră',
            'Attrezzatura cucina': 'Echipament bucătărie', 'Altro': 'Altele'
        }.get(t["category"], t["category"])
        priority_it = t["priority"] or 'Normale'
        priority_de = {'Bassa':'Niedrig', 'Normale':'Normal', 'Alta':'Hoch', 'Urgente':'Dringend'}.get(priority_it, priority_it)
        priority_ro = {'Bassa':'Scăzută', 'Normale':'Normală', 'Alta':'Ridicată', 'Urgente':'Urgentă'}.get(priority_it, priority_it)

        wa_messages = {
            'it': (
                f'🔧 Nuovo intervento Hausmeister Carellas\\n'
                f'Ticket: {t["ticket_code"]}\\n'
                f'Zona: {t["zone_name"]}\\n'
                f'Categoria: {t["category"]}\\n'
                f'Priorità: {priority_it}\\n'
                f'Problema: {description_it[:700]}\\n\\n'
                f'📋 Ticket completo e foto: {ticket_link}'
            ),
            'de': (
                f'🔧 Neuer Einsatz Hausmeister Carellas\\n'
                f'Ticket: {t["ticket_code"]}\\n'
                f'Bereich: {t["zone_name"]}\\n'
                f'Kategorie: {category_de}\\n'
                f'Priorität: {priority_de}\\n'
                f'Problem: {description_de[:700]}\\n\\n'
                f'📋 Vollständiges Ticket und Fotos: {ticket_link}'
            ),
            'ro': (
                f'🔧 Intervenție nouă Hausmeister Carellas\\n'
                f'Tichet: {t["ticket_code"]}\\n'
                f'Zonă: {t["zone_name"]}\\n'
                f'Categorie: {category_ro}\\n'
                f'Prioritate: {priority_ro}\\n'
                f'Problemă: {description_ro[:700]}\\n\\n'
                f'📋 Tichet complet și fotografii: {ticket_link}'
            ),
        }

        for c in whatsapp_contacts:
            wa_it = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["it"])}'
            wa_de = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["de"])}'
            wa_ro = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["ro"])}'
            contact_buttons += (
                f'<a class="btn" style="background:#16883f;margin:5px 5px 5px 0" '
                f'href="{esc(wa_it)}" data-wa-it="{esc(wa_it)}" data-wa-de="{esc(wa_de)}" data-wa-ro="{esc(wa_ro)}" '
                f'onclick="var l=(navigator.language||navigator.userLanguage||\'it\').toLowerCase();'
                f'if(l.indexOf(\'de\')===0)this.href=this.dataset.waDe;'
                f'else if(l.indexOf(\'ro\')===0)this.href=this.dataset.waRo;'
                f'else this.href=this.dataset.waIt;" target="_top">WhatsApp · {esc(c["name"])}</a>'
            )
    elif whatsapp_contacts:
        contact_buttons = '<div class="notice warning">Configura URL pubblico o tunnel pubblico della Beta per poter inserire nel messaggio il link al ticket.</div>'
    else:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
'''

if old not in text:
    raise SystemExit('WhatsApp button marker not found')

text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
