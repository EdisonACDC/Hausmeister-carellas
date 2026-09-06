from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

start_marker = "@admin_app.get('/settings/backup')\ndef backup_data():\n"
end_marker = "\n\n@admin_app.get('/zone/{zone_id}', response_class=HTMLResponse)"

if start_marker not in text or end_marker not in text:
    raise SystemExit('Backup route marker not found')

start = text.index(start_marker)
end = text.index(end_marker, start)

replacement = r'''@admin_app.get('/settings/backup')
def backup_data():
    export_dir = DATA_DIR / 'backups'
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = f'hausmeister-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'
    target = export_dir / filename
    snapshot = export_dir / f'.snapshot-{secrets.token_hex(6)}.db'
    source = db()
    destination = sqlite3.connect(snapshot)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, 'hausmeister.db')
            if OPTIONS_PATH.exists():
                archive.write(OPTIONS_PATH, 'options.json')
            if UPLOAD_DIR.exists():
                for item in UPLOAD_DIR.iterdir():
                    if item.is_file():
                        archive.write(item, f'uploads/{item.name}')
    finally:
        try:
            snapshot.unlink()
        except OSError:
            pass
    return FileResponse(
        target,
        media_type='application/octet-stream',
        filename=filename,
        content_disposition_type='attachment',
        headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'},
    )
'''

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')
