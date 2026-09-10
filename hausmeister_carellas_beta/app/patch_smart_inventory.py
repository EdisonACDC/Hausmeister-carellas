from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

if 'def inventory_qr_label_page(' not in text:
    detail_anchor = "    delete_action = f'{detail_root}/delete'\n"
    if detail_anchor not in text:
        raise SystemExit('Material detail anchor not found')
    text = text.replace(detail_anchor, detail_anchor + "    qr_url = f'{detail_root}/label'\n", 1)

    detail_image = "<div class=\"grid\"><div class=\"card span-5\">{image}<h2 style=\"margin-top:14px\">"
    if detail_image not in text:
        raise SystemExit('Material QR button anchor not found')
    text = text.replace(detail_image, "<div class=\"grid\"><div class=\"card span-5\">{image}<div style=\"margin-top:12px\"><a class=\"btn\" href=\"{qr_url}\">▣ QR articolo</a></div><h2 style=\"margin-top:14px\">", 1)

    helper_marker = '\n\ninit_db()\n'
    helper = r"""

def inventory_qr_label_page(item, photo_url: str = ''):
    qr_payload = f'MAGAZZINO|ID={item["id"]}|CODICE={item["code"] or ""}|POSIZIONE={item["location"] or ""}|NOME={item["name"]}'
    qr = qrcode.make(qr_payload)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    qr64 = base64.b64encode(buf.getvalue()).decode()
    photo_html = f'<img src="{esc(photo_url)}" style="width:90px;height:70px;object-fit:contain" alt="Foto articolo">' if item['photo_stored_name'] else ''
    body = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Etichetta {esc(item['name'])}</title><style>body{{font-family:Arial,sans-serif;background:#eee;padding:20px}}.toolbar{{max-width:700px;margin:0 auto 15px}}.label{{width:640px;max-width:100%;margin:auto;background:white;border:2px solid #222;border-radius:12px;padding:18px;display:grid;grid-template-columns:190px 1fr;gap:18px}}.qr{{width:180px}}h1{{font-size:24px;margin:4px 0 10px}}.pos{{font-size:28px;font-weight:800}}button,a{{display:inline-block;padding:10px 14px;border-radius:8px;border:0;background:#536d33;color:white;text-decoration:none;font-weight:700}}@media(max-width:600px){{.label{{grid-template-columns:1fr;text-align:center}}}}@media print{{body{{background:white;padding:0}}.toolbar{{display:none}}.label{{border:1px solid #000;width:95mm;padding:4mm;grid-template-columns:30mm 1fr;gap:4mm;text-align:left}}.qr{{width:29mm}}h1{{font-size:14pt}}.pos{{font-size:18pt}}}}</style></head><body><div class="toolbar"><button onclick="window.print()">🖨 Stampa etichetta</button> <a href="../">← Torna all’articolo</a></div><div class="label"><div><img class="qr" src="data:image/png;base64,{qr64}" alt="QR articolo"></div><div><b>Carellas Ristorante · MAGAZZINO MATERIALI</b><h1>{esc(item['name'])}</h1><div>Codice: <b>{esc(item['code'] or '—')}</b></div><div>Categoria: {esc(item['category'] or '—')}</div><div class="pos">Posizione: {esc(item['location'] or '—')}</div>{photo_html}</div></div></body></html>'''
    return HTMLResponse(body)
"""
    if helper_marker not in text:
        raise SystemExit('Inventory QR helper marker not found')
    text = text.replace(helper_marker, helper + helper_marker, 1)

    admin_marker = "\n\n@admin_app.post('/pin')\n"
    admin_routes = r'''

@admin_app.get('/material/{material_id}/label', response_class=HTMLResponse)
@admin_app.get('/materials/{material_id}/label', response_class=HTMLResponse)
def admin_material_qr_label(material_id: int):
    con = db()
    item = con.execute('SELECT * FROM materials WHERE id=?', (material_id,)).fetchone()
    con.close()
    if not item:
        raise HTTPException(404, 'Articolo non trovato')
    return inventory_qr_label_page(item, f'../{material_id}/photo')
'''
    if admin_marker not in text:
        raise SystemExit('Admin material QR route marker not found')
    text = text.replace(admin_marker, admin_routes + admin_marker, 1)

    manager_marker = "\n\n@public_app.post('/manager/zone')\n"
    manager_routes = r'''

@public_app.get('/manager/material/{material_id}/label', response_class=HTMLResponse)
def manager_material_qr_label(request: Request, material_id: int):
    if not manager_session_valid(request):
        return RedirectResponse('/manager/login', status_code=303)
    con = db()
    item = con.execute('SELECT * FROM materials WHERE id=?', (material_id,)).fetchone()
    con.close()
    if not item:
        raise HTTPException(404, 'Articolo non trovato')
    return inventory_qr_label_page(item, f'../{material_id}/photo')
'''
    if manager_marker not in text:
        raise SystemExit('Manager material QR route marker not found')
    text = text.replace(manager_marker, manager_routes + manager_marker, 1)

if 'import base64\n' not in text:
    text = text.replace('import hashlib\n', 'import base64\nimport hashlib\n', 1)

path.write_text(text, encoding='utf-8')
