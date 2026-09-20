from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# 1) Velocizza il ticket interno/Titolare: salva subito, traduzioni restano pending.
old = """    description_it, status_it = translate_text(description, 'it')
    description_de, status_de = translate_text(description, 'de')
    translation_status = 'completed' if status_it == 'completed' and status_de == 'completed' else ('failed' if 'failed' in (status_it, status_de) else 'pending')
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,description_de,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description_it, description_de, translation_status, now_iso(), now_iso()))"""
new = """    # Il ticket interno deve essere immediato: nessuna chiamata di rete prima del salvataggio.
    # Le traduzioni vengono lasciate pending e possono essere completate successivamente.
    description_it = description
    description_de = None
    translation_status = 'pending'
    cur = con.execute('INSERT INTO tickets(zone_id,reporter_name,category,priority,description_original,description_it,description_de,translation_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)', (zone['id'], reporter_name, category, priority, description, description_it, description_de, translation_status, now_iso(), now_iso()))"""
if old in text:
    text = text.replace(old, new, 1)

# 2) Pagina Impostazioni: aggiunge il collegamento QR Zone senza duplicarlo.
backup_card = '<div class="card span-12"><h2>Backup</h2>'
if 'settings/qr-export' not in text and backup_card in text:
    text = text.replace(
        backup_card,
        '<div class="card span-12"><h2>QR Zone</h2><p>Scarica in una volta sola i QR di tutte le zone, con file separati per la stampa da telefono o PC.</p><a class="btn" href="settings/qr-export">▣ Scarica tutti i QR</a></div>' + backup_card,
        1
    )

# 3) Route per esportazione massiva QR.
route_marker = "@admin_app.get('/tickets', response_class=HTMLResponse)"
if "@admin_app.get('/settings/qr-export'" not in text:
    routes = r'''\nimport io\nimport zipfile\nfrom fastapi.responses import StreamingResponse
def _qr_safe_name(value):
    import re
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', str(value or '').strip()).strip('._')
    return name or 'zona'

def _zone_qr_png(zone):
    url = public_url_for(zone)
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(url); qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    out = io.BytesIO(); image.save(out, format='PNG', optimize=True)
    return out.getvalue(), image

def _zone_qr_pdf_bytes(zone):
    _png, image = _zone_qr_png(zone)
    out = io.BytesIO()
    image.save(out, format='PDF', resolution=300.0)
    return out.getvalue()

@admin_app.get('/settings/qr-export', response_class=HTMLResponse)
def qr_export_settings():
    con = db(); zones = con.execute('SELECT * FROM zones ORDER BY name COLLATE NOCASE').fetchall(); con.close()
    count = len(zones)
    body = f"""
    <div class="card">
      <h2>▣ QR Zone</h2>
      <p><b>{count}</b> zone trovate. Gli export vengono creati al momento, quindi comprendono automaticamente anche le zone aggiunte in futuro.</p>
      <div class="actions" style="display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn" href="qr-export/png">📱 ZIP · PNG separati</a>
        <a class="btn" href="qr-export/pdf">📄 ZIP · PDF separati</a>
        <a class="btn" href="qr-export/pdf-unico">🖨 PDF unico</a>
      </div>
      <p class="muted" style="margin-top:14px">Per Brother da iPhone usa <b>ZIP · PNG separati</b>: ogni zona viene salvata come immagine PNG indipendente.</p>
    </div>
    """
    return page('QR Zone', body, back_url='../settings')

@admin_app.get('/settings/qr-export/png')
def qr_export_png_zip():
    con = db(); zones = con.execute('SELECT * FROM zones ORDER BY name COLLATE NOCASE').fetchall(); con.close()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for zone in zones:
            png, _image = _zone_qr_png(zone)
            archive.writestr(f'{_qr_safe_name(zone["name"])}.png', png)
    out.seek(0)
    return StreamingResponse(out, media_type='application/zip', headers={'Content-Disposition':'attachment; filename="QR_Zone_PNG.zip"'})

@admin_app.get('/settings/qr-export/pdf')
def qr_export_pdf_zip():
    con = db(); zones = con.execute('SELECT * FROM zones ORDER BY name COLLATE NOCASE').fetchall(); con.close()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for zone in zones:
            archive.writestr(f'{_qr_safe_name(zone["name"])}.pdf', _zone_qr_pdf_bytes(zone))
    out.seek(0)
    return StreamingResponse(out, media_type='application/zip', headers={'Content-Disposition':'attachment; filename="QR_Zone_PDF.zip"'})

@admin_app.get('/settings/qr-export/pdf-unico')
def qr_export_pdf_all():
    con = db(); zones = con.execute('SELECT * FROM zones ORDER BY name COLLATE NOCASE').fetchall(); con.close()
    if not zones:
        raise HTTPException(404, 'Nessuna zona disponibile')
    pages = []
    for zone in zones:
        _png, image = _zone_qr_png(zone)
        pages.append(image)
    out = io.BytesIO()
    pages[0].save(out, format='PDF', save_all=True, append_images=pages[1:], resolution=300.0)
    out.seek(0)
    return StreamingResponse(out, media_type='application/pdf', headers={'Content-Disposition':'attachment; filename="QR_Tutte_Le_Zone.pdf"'})

'''
    if route_marker not in text:
        raise SystemExit('QR export insertion marker not found')
    text = text.replace(route_marker, routes + route_marker, 1)

path.write_text(text, encoding='utf-8')
