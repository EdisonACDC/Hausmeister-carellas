from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

if 'import base64\n' not in text:
    text = text.replace('import hashlib\n', 'import base64\nimport hashlib\n', 1)

legacy_marker = "@admin_app.get('/materials', response_class=HTMLResponse)"
if legacy_marker in text:
    text = text.replace(legacy_marker, "@admin_app.get('/materials-legacy', response_class=HTMLResponse)", 1)

insert_marker = "@admin_app.get('/materials-legacy', response_class=HTMLResponse)"
smart_marker = "@admin_app.get('/materials', response_class=HTMLResponse)\ndef smart_materials"

if smart_marker not in text:
    routes = r"""
def ensure_smart_material_columns():
    con = db()
    columns = {row['name'] for row in con.execute('PRAGMA table_info(materials)').fetchall()}
    for name, sql_type in (
        ('brand', 'TEXT'), ('price', 'REAL'), ('tags', 'TEXT'), ('barcode', 'TEXT')
    ):
        if name not in columns:
            con.execute(f'ALTER TABLE materials ADD COLUMN {name} {sql_type}')
    con.commit(); con.close()


def inventory_ai_settings():
    options = load_options()
    return (
        (options.get('vision_url') or '').strip(),
        (options.get('vision_model') or '').strip(),
        (options.get('vision_api_key') or '').strip(),
    )


def inventory_ai_recognize(image_bytes: bytes, content_type: str):
    url, model, api_key = inventory_ai_settings()
    if not url or not model:
        return {}, 'Riconoscimento AI non configurato. Puoi comunque completare i campi manualmente.'
    prompt = (
        'Analizza la foto di un articolo da magazzino tecnico. Restituisci SOLO JSON valido con queste chiavi: '
        'name, category, brand, code, description, unit, price, tags. '
        'category deve essere una categoria breve in italiano; unit normalmente pz. price numero o null; tags stringa separata da virgole. '
        'Non inventare codici o marchi non leggibili: usa stringa vuota.'
    )
    data_url = f'data:{content_type};base64,{base64.b64encode(image_bytes).decode()}'
    payload = {
        'model': model,
        'temperature': 0.1,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': data_url}},
            ],
        }],
    }
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.loads(response.read().decode())
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        content = (content or '').strip()
        if content.startswith('```'):
            content = content.strip('`').replace('json\n', '', 1).strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError('Risposta AI non valida')
        return parsed, 'Dati riconosciuti dalla foto. Controllali prima di salvare.'
    except Exception as exc:
        return {}, f'Riconoscimento non riuscito: {type(exc).__name__}. Compila o correggi i campi manualmente.'


def smart_inventory_page(values=None, temp_photo='', notice=''):
    ensure_smart_material_columns()
    values = values or {}
    con = db()
    items = con.execute('SELECT * FROM materials ORDER BY name COLLATE NOCASE').fetchall()
    con.close()
    def v(key, default=''):
        return esc(values.get(key, default))
    photo_preview = ''
    if temp_photo:
        photo_preview = f'<img src="materials/temp-photo/{esc(temp_photo)}" style="width:100%;max-height:320px;object-fit:contain;border-radius:12px;background:#f4f4f4">'
    else:
        photo_preview = '<div style="height:280px;border:2px dashed #c8d2dc;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#6b7785">Scatta o carica la foto dell’articolo</div>'
    rows = ''
    for item in items:
        low = int(item['quantity'] or 0) <= int(item['reorder_level'] or 3)
        qstyle = 'background:#ffe2e2;color:#a40000' if low else 'background:#dcf7e4;color:#176b36'
        photo = f'<img src="materials/item-photo/{item["id"]}" style="width:44px;height:44px;object-fit:cover;border-radius:8px">' if item['photo_stored_name'] else '📦'
        rows += (
            f'<tr><td>{photo}</td><td><b>{esc(item["name"])}</b></td><td>{esc(item["code"] or "")}</td>'
            f'<td>{esc(item["category"] or "")}</td><td><span style="{qstyle};padding:5px 10px;border-radius:999px;font-weight:700">{item["quantity"]}</span></td>'
            f'<td><span style="background:#eef2f6;padding:5px 10px;border-radius:999px">{esc(item["location"] or "—")}</span></td>'
            f'<td><a class="btn" href="materials/{item["id"]}/label" target="_blank">▣ QR</a></td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="7" class="muted">Nessun articolo presente.</td></tr>'
    notice_html = f'<div class="notice">{esc(notice)}</div>' if notice else ''
    body = f'''
    <style>
      .mi-flow{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:14px}}
      .mi-step{{background:#fff;border:1px solid #dfe6ec;border-radius:12px;padding:12px;font-weight:700;text-align:center}}
      .mi-step b{{display:inline-flex;width:28px;height:28px;border-radius:50%;align-items:center;justify-content:center;background:#168eea;color:#fff;margin-right:7px}}
      .mi-layout{{display:grid;grid-template-columns:1.05fr 1.35fr .9fr;gap:14px}}
      .mi-card{{background:#fff;border:1px solid #dfe6ec;border-radius:14px;padding:16px}}
      .mi-grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
      .mi-table{{width:100%;border-collapse:collapse}} .mi-table th,.mi-table td{{padding:9px;border-bottom:1px solid #e7ebef;text-align:left}}
      .mi-primary{{background:#168eea!important;color:#fff!important}}
      .mi-label{{border:1px solid #cbd5df;border-radius:12px;padding:16px;text-align:center}}
      @media(max-width:900px){{.mi-flow{{grid-template-columns:1fr}}.mi-layout{{grid-template-columns:1fr}}.mi-grid2{{grid-template-columns:1fr}}}}
    </style>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px">
      <div><h1 style="margin:0">📦 Magazzino Materiali</h1><div class="muted">Una foto. Tutte le informazioni.</div></div>
      <a class="btn" href="materials-legacy">Vista classica</a>
    </div>
    {notice_html}
    <div class="mi-flow">
      <div class="mi-step"><b>1</b>📷 Scatta la foto</div><div class="mi-step"><b>2</b>🔎 Riconoscimento</div><div class="mi-step"><b>3</b>✎ Verifica e completa</div><div class="mi-step"><b>4</b>▣ Salva e genera QR</div><div class="mi-step"><b>5</b>🖨 Stampa etichetta</div>
    </div>
    <div class="mi-layout">
      <div class="mi-card"><h2>Nuovo articolo da foto</h2>{photo_preview}
        <form method="post" enctype="multipart/form-data" action="materials/recognize" style="margin-top:12px">
          <input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" capture="environment" required>
          <button class="mi-primary" type="submit">🧠 Riconoscimento automatico</button>
        </form>
        <p class="muted">L’AI legge testo e caratteristiche visibili e precompila i campi. Controlla sempre i dati prima di salvare.</p>
      </div>
      <div class="mi-card"><h2>Dati articolo</h2>
        <form method="post" action="materials/create-smart">
          <input type="hidden" name="temp_photo" value="{esc(temp_photo)}">
          <label>Nome articolo *</label><input name="name" value="{v('name')}" required>
          <div class="mi-grid2"><div><label>Categoria *</label><input name="category" value="{v('category')}" required></div><div><label>Marca</label><input name="brand" value="{v('brand')}"></div></div>
          <label>Codice articolo</label><input name="code" value="{v('code')}">
          <label>Descrizione</label><textarea name="description" rows="4">{v('description')}</textarea>
          <div class="mi-grid2"><div><label>Unità di misura</label><input name="unit" value="{v('unit','pz')}"></div><div><label>Prezzo €</label><input name="price" type="number" step="0.01" value="{v('price')}"></div></div>
          <div class="mi-grid2"><div><label>Quantità iniziale</label><input name="quantity" type="number" value="{v('quantity','0')}"></div><div><label>Scorta minima</label><input name="reorder_level" type="number" value="{v('reorder_level','3')}"></div></div>
          <label>Posizione scaffale *</label><input name="location" value="{v('location')}" placeholder="Es. A-02" required>
          <label>Tag</label><input name="tags" value="{v('tags')}" placeholder="raccordo, ottone, 1/2, idraulica">
          <button class="mi-primary" type="submit">💾 Salva articolo e genera QR</button>
        </form>
      </div>
      <div class="mi-card"><h2>Anteprima etichetta</h2><div class="mi-label"><div style="font-size:52px">▣</div><b>QR articolo + posizione</b><p class="muted">Dopo il salvataggio avrai l’etichetta pronta da stampare e incollare sullo scaffale.</p></div></div>
    </div>
    <div class="mi-card" style="margin-top:14px"><h2>Vista magazzino</h2><div style="overflow:auto"><table class="mi-table"><thead><tr><th>Foto</th><th>Nome</th><th>Codice</th><th>Categoria</th><th>Quantità</th><th>Posizione</th><th>Azioni</th></tr></thead><tbody>{rows}</tbody></table></div></div>
    '''
    return page('Magazzino Materiali', body)


@admin_app.get('/materials', response_class=HTMLResponse)
def smart_materials():
    return smart_inventory_page()


@admin_app.post('/materials/recognize', response_class=HTMLResponse)
async def smart_material_recognize(photo: UploadFile = File(...)):
    stored = ''
    try:
        if not photo.filename or photo.content_type not in ALLOWED_TYPES:
            return smart_inventory_page(notice='Formato foto non supportato. Usa JPG, PNG o WEBP.')
        content = await photo.read(MAX_UPLOAD_BYTES + 1)
        if not content:
            return smart_inventory_page(notice='La foto ricevuta è vuota. Riprova.')
        if len(content) > MAX_UPLOAD_BYTES:
            return smart_inventory_page(notice='Foto troppo grande. Il limite è 8 MB.')
        suffix = Path(photo.filename).suffix.lower()[:8] or '.jpg'
        stored = 'material_tmp_' + secrets.token_hex(16) + suffix
        (UPLOAD_DIR / stored).write_bytes(content)
        values, notice = inventory_ai_recognize(content, photo.content_type)
        return smart_inventory_page(values, stored, notice)
    except Exception as exc:
        return smart_inventory_page(
            temp_photo=stored,
            notice=f'Compilazione automatica non riuscita ({type(exc).__name__}: {str(exc)[:180]}). Puoi riprovare o compilare i campi manualmente.'
        )


@admin_app.get('/materials/temp-photo/{stored_name}')
def smart_material_temp_photo(stored_name: str):
    if not stored_name.startswith('material_tmp_'):
        raise HTTPException(404)
    target = UPLOAD_DIR / Path(stored_name).name
    if not target.exists(): raise HTTPException(404)
    return FileResponse(target)


@admin_app.get('/materials/item-photo/{material_id}')
def smart_material_item_photo(material_id: int):
    con = db(); item = con.execute('SELECT * FROM materials WHERE id=?', (material_id,)).fetchone(); con.close()
    if not item or not item['photo_stored_name']: raise HTTPException(404)
    target = UPLOAD_DIR / Path(item['photo_stored_name']).name
    if not target.exists(): raise HTTPException(404)
    return FileResponse(target, media_type=item['photo_content_type'] or 'image/jpeg')


@admin_app.post('/materials/create-smart')
def smart_material_create(name: str = Form(...), category: str = Form(...), brand: str = Form(''), code: str = Form(''), description: str = Form(''), unit: str = Form('pz'), price: str = Form(''), quantity: int = Form(0), reorder_level: int = Form(3), location: str = Form(...), tags: str = Form(''), temp_photo: str = Form('')):
    ensure_smart_material_columns()
    name=name.strip(); category=category.strip(); location=location.strip(); code=code.strip(); brand=brand.strip(); tags=tags.strip()
    if not name or not category or not location: raise HTTPException(400, 'Nome, categoria e posizione sono obbligatori')
    try: price_value = float(price.replace(',', '.')) if price.strip() else None
    except ValueError: price_value = None
    stored_name = original_name = content_type = None
    if temp_photo.startswith('material_tmp_'):
        source = UPLOAD_DIR / Path(temp_photo).name
        if source.exists():
            stored_name = 'material_' + secrets.token_hex(16) + source.suffix.lower()[:8]
            target = UPLOAD_DIR / stored_name
            source.replace(target)
            original_name = 'foto_articolo' + target.suffix
            content_type = 'image/jpeg' if target.suffix.lower() in {'.jpg','.jpeg'} else ('image/png' if target.suffix.lower()=='.png' else 'image/webp')
    now = now_iso()
    con=db(); cur=con.execute('''INSERT INTO materials(name,code,category,description,location,supplier,unit,quantity,reorder_level,photo_stored_name,photo_original_name,photo_content_type,created_at,updated_at,brand,price,tags,barcode) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (name,code,category,description.strip(),location,'',unit.strip() or 'pz',max(0,quantity),max(0,reorder_level),stored_name,original_name,content_type,now,now,brand,price_value,tags,code or None)); material_id=cur.lastrowid; con.commit(); con.close()
    return RedirectResponse(f'{material_id}/label', status_code=303)


@admin_app.get('/materials/{material_id}/label', response_class=HTMLResponse)
def smart_material_label(material_id: int):
    ensure_smart_material_columns()
    con=db(); item=con.execute('SELECT * FROM materials WHERE id=?',(material_id,)).fetchone(); con.close()
    if not item: raise HTTPException(404,'Articolo non trovato')
    qr_payload = f'MAGAZZINO|ID={item["id"]}|CODICE={item["code"] or ""}|POSIZIONE={item["location"] or ""}|NOME={item["name"]}'
    qr = qrcode.make(qr_payload); buf=io.BytesIO(); qr.save(buf, format='PNG'); qr64=base64.b64encode(buf.getvalue()).decode()
    photo_html = f'<img src="../item-photo/{item["id"]}" style="width:90px;height:70px;object-fit:contain">' if item['photo_stored_name'] else ''
    body=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Etichetta {esc(item['name'])}</title><style>body{{font-family:Arial,sans-serif;background:#eee;padding:20px}}.toolbar{{max-width:700px;margin:0 auto 15px}}.label{{width:640px;max-width:100%;margin:auto;background:white;border:2px solid #222;border-radius:12px;padding:18px;display:grid;grid-template-columns:190px 1fr;gap:18px}}.qr{{width:180px}}h1{{font-size:24px;margin:4px 0 10px}}.pos{{font-size:28px;font-weight:800}}@media print{{body{{background:white;padding:0}}.toolbar{{display:none}}.label{{border:1px solid #000;width:95mm;padding:4mm;grid-template-columns:30mm 1fr;gap:4mm}}.qr{{width:29mm}}h1{{font-size:14pt}}.pos{{font-size:18pt}}}}</style></head><body><div class="toolbar"><button onclick="window.print()">🖨 Stampa etichetta</button> <a href="../">← Torna al magazzino</a></div><div class="label"><div><img class="qr" src="data:image/png;base64,{qr64}"></div><div><b>Carellas Ristorante · MAGAZZINO MATERIALI</b><h1>{esc(item['name'])}</h1><div>Codice: <b>{esc(item['code'] or '—')}</b></div><div>Categoria: {esc(item['category'] or '—')}</div><div>Marca: {esc(item['brand'] or '—')}</div><div class="pos">Posizione: {esc(item['location'] or '—')}</div>{photo_html}</div></div></body></html>'''
    return HTMLResponse(body)


"""
    if insert_marker not in text:
        raise SystemExit('Smart inventory insertion marker not found')
    text = text.replace(insert_marker, routes + insert_marker, 1)

path.write_text(text, encoding='utf-8')

