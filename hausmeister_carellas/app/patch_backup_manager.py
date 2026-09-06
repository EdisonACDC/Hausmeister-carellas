from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

helpers_marker = '\n\ninit_db()\n'
if "BACKUP_DIR = DATA_DIR / 'backups'" not in text:
    helpers = r'''

BACKUP_DIR = DATA_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def create_managed_backup():
    filename = f'hausmeister-manual-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
    target = BACKUP_DIR / filename
    snapshot = BACKUP_DIR / f'.snapshot-{secrets.token_hex(6)}.db'
    source = db()
    dest = sqlite3.connect(snapshot)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    manifest = {'application': 'Hausmeister Carellas', 'format': 1, 'app_version': APP_VERSION, 'created_at': now_iso()}
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'hausmeister.db')
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            if OPTIONS_PATH.exists():
                archive.write(OPTIONS_PATH, 'options.json')
            if UPLOAD_DIR.exists():
                for item in UPLOAD_DIR.iterdir():
                    if item.is_file():
                        archive.write(item, f'uploads/{item.name}')
    finally:
        try: snapshot.unlink()
        except OSError: pass
    return target


def managed_backup_path(filename):
    name = Path(filename).name
    if name != filename or not name.startswith('hausmeister-') or not name.endswith('.zip'):
        raise HTTPException(400, 'Nome backup non valido')
    return BACKUP_DIR / name
'''
    if helpers_marker not in text:
        raise SystemExit('init marker not found')
    text = text.replace(helpers_marker, helpers + helpers_marker, 1)

start_marker = "@admin_app.get('/settings/backup')\ndef backup_data():\n"
alt_start_marker = "@admin_app.get('/settings/backup')\ndef backup_data():\n"
end_marker = "\n\n@admin_app.get('/zone/{zone_id}', response_class=HTMLResponse)"
if start_marker not in text or end_marker not in text:
    raise SystemExit('backup route markers not found')
start = text.index(start_marker)
end = text.index(end_marker, start)
routes = r'''@admin_app.get('/settings/backup', response_class=HTMLResponse)
def backup_page(message: str = ''):
    files = sorted(BACKUP_DIR.glob('hausmeister-*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = ''
    for item in files:
        modified = datetime.fromtimestamp(item.stat().st_mtime).strftime('%d/%m/%Y %H:%M')
        size_mb = item.stat().st_size / (1024 * 1024)
        name = esc(item.name)
        rows += f'<div class="zone-row"><div><b>{name}</b><br><span class="muted">{modified} · {size_mb:.1f} MB</span></div><a class="btn" href="backup/file/{name}" target="_blank" rel="noopener">Scarica</a></div>'
    if not rows:
        rows = '<p class="muted">Nessun backup creato.</p>'
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid"><div class="card span-12"><h2>Backup Hausmeister</h2><p>Prima crea il backup. Il file rimane salvato nell’add-on e può essere scaricato successivamente.</p><form method="post" action="backup/create"><button type="submit">💾 Crea backup adesso</button></form></div><div class="card span-12"><h2>Backup disponibili</h2>{rows}</div></div>'''
    return page('Backup', body, back_url='../settings')


@admin_app.post('/settings/backup/create')
def backup_create():
    target = create_managed_backup()
    return RedirectResponse('../backup?message=' + urllib.parse.quote(f'Backup creato correttamente: {target.name}'), status_code=303)


@admin_app.get('/settings/backup/file/{filename}')
def backup_file(filename: str):
    target = managed_backup_path(filename)
    if not target.exists():
        raise HTTPException(404, 'Backup non trovato')
    return FileResponse(target, media_type='application/octet-stream', filename=target.name, content_disposition_type='attachment', headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
'''
text = text[:start] + routes + text[end:]
path.write_text(text, encoding='utf-8')
