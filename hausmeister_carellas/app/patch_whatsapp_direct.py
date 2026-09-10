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
        category_de = {'Elettrico':'Elektrik','Idraulico':'Sanitär / Wasser','Muratore':'Maurer / Bau','Climatizzazione':'Klimaanlage','Porta/Finestra':'Tür / Fenster','Attrezzatura cucina':'Küchengerät','Altro':'Sonstiges'}.get(t["category"], t["category"])
        category_ro = {'Elettrico':'Electric','Idraulico':'Instalații sanitare / Apă','Muratore':'Zidar / Construcții','Climatizzazione':'Climatizare','Porta/Finestra':'Ușă / Fereastră','Attrezzatura cucina':'Echipament bucătărie','Altro':'Altele'}.get(t["category"], t["category"])
        priority_it = t["priority"] or 'Normale'
        priority_de = {'Bassa':'Niedrig','Normale':'Normal','Alta':'Hoch','Urgente':'Dringend'}.get(priority_it, priority_it)
        priority_ro = {'Bassa':'Scăzută','Normale':'Normală','Alta':'Ridicată','Urgente':'Urgentă'}.get(priority_it, priority_it)
        wa_messages = {
            'it': f'🔧 Nuovo intervento Hausmeister Carellas\\nTicket: {t["ticket_code"]}\\nZona: {t["zone_name"]}\\nCategoria: {t["category"]}\\nPriorità: {priority_it}\\nProblema: {description_it[:700]}\\n\\n📋 Ticket completo e foto: {ticket_link}',
            'de': f'🔧 Neuer Einsatz Hausmeister Carellas\\nTicket: {t["ticket_code"]}\\nBereich: {t["zone_name"]}\\nKategorie: {category_de}\\nPriorität: {priority_de}\\nProblem: {description_de[:700]}\\n\\n📋 Vollständiges Ticket und Fotos: {ticket_link}',
            'ro': f'🔧 Intervenție nouă Hausmeister Carellas\\nTichet: {t["ticket_code"]}\\nZonă: {t["zone_name"]}\\nCategorie: {category_ro}\\nPrioritate: {priority_ro}\\nProblemă: {description_ro[:700]}\\n\\n📋 Tichet complet și fotografii: {ticket_link}'
        }
        for c in whatsapp_contacts:
            wa_it = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["it"])}'
            wa_de = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["de"])}'
            wa_ro = f'https://wa.me/{c["phone"]}?text={urllib.parse.quote(wa_messages["ro"])}'
            contact_buttons += f'<a class="btn wa-auto-language" style="background:#16883f;margin:5px 5px 5px 0" href="{esc(wa_it)}" data-wa-it="{esc(wa_it)}" data-wa-de="{esc(wa_de)}" data-wa-ro="{esc(wa_ro)}" target="_top">WhatsApp · {esc(c["name"])}</a>'
        contact_buttons += '<script>document.querySelectorAll(".wa-auto-language").forEach(function(a){a.addEventListener("click",function(){var l=(navigator.language||navigator.userLanguage||"it").toLowerCase();if(l.indexOf("de")===0)a.href=a.dataset.waDe;else if(l.indexOf("ro")===0)a.href=a.dataset.waRo;else a.href=a.dataset.waIt;});});</script>'
    elif whatsapp_contacts:
        contact_buttons = '<div class="notice warning">Configura URL pubblico o tunnel pubblico della Beta per poter inserire nel messaggio il link al ticket.</div>'
    else:
        contact_buttons = '<p class="muted">Nessun tecnico configurato. Vai in Impostazioni → WhatsApp tecnici.</p>'
'''

if old not in text:
    raise SystemExit('WhatsApp button marker not found')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
