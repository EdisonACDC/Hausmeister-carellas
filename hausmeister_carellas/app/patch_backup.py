from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

if 'import threading\n' not in text:
    text = text.replace('import time\n', 'import time\nimport threading\n', 1)

helpers_marker = '\n\ninit_db()\n'
if "BACKUP_DIR = DATA_DIR / 'backups'" not in text:
    helpers = r'''

BACKUP_DIR = DATA_DIR / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_MAX_UPLOAD = 512 * 1024 * 1024
_backup_scheduler_started = False


def backup_filename(kind='manual'):
    kind = kind if kind in {'manual', 'daily', 'weekly', 'monthly', 'safety'} else 'manual'
    return f'hausmeister-{kind}-{datetime.now().strftime("%Y%m%d-%H%M%S")}.zip'


def create_backup_file(kind='manual'):
    target = BACKUP_DIR / backup_filename(kind)
    snapshot = BACKUP_DIR / f'.snapshot-{secrets.token_hex(6)}.db'
    source = db()
    dest = sqlite3.connect(snapshot)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    manifest = {
        'application': 'Hausmeister Carellas',
        'format': 1,
        'app_version': APP_VERSION,
        'created_at': now_iso(),
        'kind': kind,
    }
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
        try:
            snapshot.unlink()
        except OSError:
            pass
    return target


def backup_files():
    return sorted(
        [p for p in BACKUP_DIR.glob('hausmeister-*.zip') if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def prune_backups():
    for kind, limit in {'daily': 7, 'weekly': 4, 'monthly': 6, 'safety': 3}.items():
        files = sorted(BACKUP_DIR.glob(f'hausmeister-{kind}-*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[limit:]:
            try:
                old.unlink()
            except OSError:
                pass


def safe_backup_path(filename):
    name = Path(filename).name
    if name != filename or not name.startswith('hausmeister-') or not name.endswith('.zip'):
        raise HTTPException(400, 'Nome backup non valido')
    target = (BACKUP_DIR / name).resolve()
    if target.parent != BACKUP_DIR.resolve():
        raise HTTPException(400, 'Percorso backup non valido')
    return target


def validate_backup_archive(archive):
    names = archive.namelist()
    if 'hausmeister.db' not in names or 'manifest.json' not in names:
        raise HTTPException(400, 'Il file non è un backup Hausmeister valido')
    for name in names:
        p = Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise HTTPException(400, 'Archivio non sicuro')
    try:
        manifest = json.loads(archive.read('manifest.json').decode('utf-8'))
    except Exception:
        raise HTTPException(400, 'Manifest del backup non valido')
    if manifest.get('application') != 'Hausmeister Carellas' or int(manifest.get('format', 0)) != 1:
        raise HTTPException(400, 'Formato backup non compatibile')
    return manifest


def restore_backup_file(target):
    if not target.exists() or not target.is_file():
        raise HTTPException(404, 'Backup non trovato')
    create_backup_file('safety')
    temp_db = BACKUP_DIR / f'.restore-{secrets.token_hex(6)}.db'
    temp_uploads = BACKUP_DIR / f'.restore-uploads-{secrets.token_hex(6)}'
    temp_uploads.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(target, 'r') as archive:
            validate_backup_archive(archive)
            temp_db.write_bytes(archive.read('hausmeister.db'))
            check = sqlite3.connect(temp_db)
            try:
                row = check.execute('PRAGMA integrity_check').fetchone()
                if not row or row[0] != 'ok':
                    raise HTTPException(400, 'Database del backup danneggiato')
            finally:
                check.close()
            for name in archive.namelist():
                if name.startswith('uploads/') and not name.endswith('/'):
                    base = Path(name).name
                    if base:
                        (temp_uploads / base).write_bytes(archive.read(name))
        for suffix in ('-wal', '-shm'):
            try:
                Path(str(DB_PATH) + suffix).unlink()
            except OSError:
                pass
        temp_db.replace(DB_PATH)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        for item in list(UPLOAD_DIR.iterdir()):
            if item.is_file():
                try:
                    item.unlink()
                except OSError:
                    pass
        for item in temp_uploads.iterdir():
            if item.is_file():
                item.replace(UPLOAD_DIR / item.name)
        prune_backups()
    finally:
        try:
            temp_db.unlink()
        except OSError:
            pass
        if temp_uploads.exists():
            for item in list(temp_uploads.iterdir()):
                try:
                    item.unlink()
                except OSError:
                    pass
            try:
                temp_uploads.rmdir()
            except OSError:
                pass


def backup_scheduler_loop():
    while True:
        time.sleep(60)
        try:
            if get_setting('backup_auto_enabled', '1') != '1':
                continue
            try:
                hour = int(get_setting('backup_auto_hour', '3'))
            except (TypeError, ValueError):
                hour = 3
            hour = max(0, min(23, hour))
            now = datetime.now()
            day_key = now.strftime('%Y-%m-%d')
            if now.hour != hour or get_setting('backup_last_auto_day', '') == day_key:
                continue
            create_backup_file('daily')
            if now.weekday() == 0:
                create_backup_file('weekly')
            if now.day == 1:
                create_backup_file('monthly')
            prune_backups()
            set_setting('backup_last_auto_day', day_key)
            set_setting('backup_last_result', f'Backup automatico completato: {now.strftime("%d/%m/%Y %H:%M")}')
        except Exception as exc:
            try:
                set_setting('backup_last_result', f'Errore backup automatico: {type(exc).__name__}: {exc}'[:500])
            except Exception:
                pass
'''
    if helpers_marker not in text:
        raise SystemExit('Backup helpers marker not found')
    text = text.replace(helpers_marker, helpers + helpers_marker, 1)

apps_marker = "public_app = FastAPI(title='Hausmeister Carellas Public')\n"
if 'def start_backup_scheduler():' not in text:
    startup = r'''

@admin_app.on_event('startup')
def start_backup_scheduler():
    global _backup_scheduler_started
    if _backup_scheduler_started:
        return
    _backup_scheduler_started = True
    threading.Thread(target=backup_scheduler_loop, name='hausmeister-backup', daemon=True).start()
'''
    if apps_marker not in text:
        raise SystemExit('Backup startup marker not found')
    text = text.replace(apps_marker, apps_marker + startup + '\n', 1)

old_card = '<div class="card span-12"><h2>Backup</h2><p>Scarica database e fotografie in un unico archivio ZIP.</p><a class="btn" href="settings/backup">Scarica backup</a></div>'
new_card = '<div class="card span-12"><h2>Backup</h2><p>Backup automatici e manuali di database e fotografie, con ripristino controllato.</p><a class="btn" href="settings/backup">Gestisci backup</a></div>'
if old_card in text:
    text = text.replace(old_card, new_card, 1)

start_marker = "@admin_app.get('/settings/backup')\ndef backup_data():\n"
end_marker = "\n\n@admin_app.get('/zone/{zone_id}', response_class=HTMLResponse)"
if "@admin_app.post('/settings/backup/create')" not in text:
    if start_marker not in text or end_marker not in text:
        raise SystemExit('Existing backup route marker not found')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    routes = r"""@admin_app.get('/settings/backup', response_class=HTMLResponse)
def backup_page(message: str = ''):
    rows = ''
    for item in backup_files():
        stat = item.stat()
        size_mb = stat.st_size / (1024 * 1024)
        modified = datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M')
        name = esc(item.name)
        rows += f'''<tr><td><b>{name}</b></td><td>{modified}</td><td>{size_mb:.1f} MB</td><td><div class="actions"><a class="btn" href="backup/file/{name}">Scarica</a><form method="post" action="backup/restore/{name}" onsubmit="return confirm('Ripristinare questo backup? Prima verrà creato un backup di sicurezza.')"><button type="submit">Ripristina</button></form><form method="post" action="backup/delete/{name}" onsubmit="return confirm('Eliminare questo backup?')"><button type="submit" class="danger">Elimina</button></form></div></td></tr>'''
    if not rows:
        rows = '<tr><td colspan="4">Nessun backup interno presente.</td></tr>'
    enabled = get_setting('backup_auto_enabled', '1') == '1'
    hour = get_setting('backup_auto_hour', '3')
    last_result = get_setting('backup_last_result', 'Non ancora eseguito')
    notice = f'<div class="notice">{esc(message)}</div>' if message else ''
    body = f'''{notice}<div class="grid"><div class="card span-6"><h2>Backup manuale</h2><p>Crea subito una copia di database, ticket, fotografie e magazzino.</p><form method="post" action="backup/create"><button type="submit">💾 Crea backup adesso</button></form></div><div class="card span-6"><h2>Backup automatico</h2><form method="post" action="backup/config"><label style="display:flex;gap:10px;align-items:center"><input style="width:auto" type="checkbox" name="enabled" value="1" {'checked' if enabled else ''}> Attivo</label><label>Ora giornaliera (0-23)</label><input type="number" min="0" max="23" name="hour" value="{esc(hour)}" required><p class="muted">Conservazione: 7 giornalieri, 4 settimanali, 6 mensili e fino a 3 copie di sicurezza prima dei ripristini.</p><button type="submit">Salva pianificazione</button></form><div class="notice" style="margin-top:12px"><b>Ultimo risultato:</b><br>{esc(last_result)}</div></div><div class="card span-12"><h2>Carica e ripristina un backup</h2><p class="muted">Sono accettati soltanto ZIP creati da Hausmeister. Il file viene verificato prima del ripristino.</p><form method="post" action="backup/upload" enctype="multipart/form-data" onsubmit="return confirm('Procedere con il ripristino del backup selezionato?')"><input type="file" name="backup" accept="application/zip,.zip" required><button type="submit">⬆ Carica e ripristina</button></form></div><div class="card span-12"><h2>Backup disponibili</h2><div class="table-wrap"><table><tr><th>File</th><th>Data</th><th>Dimensione</th><th>Azioni</th></tr>{rows}</table></div></div></div>'''
    return page('Backup', body, back_url='../settings')


@admin_app.post('/settings/backup/create')
def backup_create_now():
    target = create_backup_file('manual')
    set_setting('backup_last_result', f'Backup manuale creato: {target.name}')
    return RedirectResponse('../backup?message=' + urllib.parse.quote(f'Backup creato: {target.name}'), status_code=303)


@admin_app.post('/settings/backup/config')
def backup_config(enabled: str = Form(''), hour: int = Form(3)):
    if hour < 0 or hour > 23:
        raise HTTPException(400, 'Ora non valida')
    set_setting('backup_auto_enabled', '1' if enabled == '1' else '0')
    set_setting('backup_auto_hour', str(hour))
    return RedirectResponse('../backup?message=' + urllib.parse.quote('Pianificazione backup salvata.'), status_code=303)


@admin_app.get('/settings/backup/file/{filename}')
def backup_download(filename: str):
    target = safe_backup_path(filename)
    if not target.exists():
        raise HTTPException(404, 'Backup non trovato')
    return FileResponse(target, media_type='application/zip', filename=target.name)


@admin_app.post('/settings/backup/delete/{filename}')
def backup_delete(filename: str):
    target = safe_backup_path(filename)
    if not target.exists():
        raise HTTPException(404, 'Backup non trovato')
    target.unlink()
    return RedirectResponse('../../backup?message=' + urllib.parse.quote('Backup eliminato.'), status_code=303)


@admin_app.post('/settings/backup/restore/{filename}')
def backup_restore_existing(filename: str):
    target = safe_backup_path(filename)
    restore_backup_file(target)
    set_setting('backup_last_result', f'Ripristino completato da {target.name}')
    return RedirectResponse('../../backup?message=' + urllib.parse.quote('Ripristino completato. Riavvia l’add-on per applicare completamente i dati.'), status_code=303)


@admin_app.post('/settings/backup/upload')
async def backup_upload_restore(backup: UploadFile = File(...)):
    filename = Path(backup.filename or '').name
    if not filename.lower().endswith('.zip'):
        raise HTTPException(400, 'Seleziona un file ZIP')
    temp = BACKUP_DIR / f'.upload-{secrets.token_hex(8)}.zip'
    total = 0
    try:
        with temp.open('wb') as handle:
            while True:
                chunk = await backup.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > BACKUP_MAX_UPLOAD:
                    raise HTTPException(400, 'Il backup supera 512 MB')
                handle.write(chunk)
        with zipfile.ZipFile(temp, 'r') as archive:
            validate_backup_archive(archive)
        restore_backup_file(temp)
        set_setting('backup_last_result', f'Ripristino completato dal file caricato {filename}')
    except zipfile.BadZipFile:
        raise HTTPException(400, 'File ZIP danneggiato o non valido')
    finally:
        try:
            temp.unlink()
        except OSError:
            pass
    return RedirectResponse('../backup?message=' + urllib.parse.quote('Backup caricato e ripristinato. Riavvia l’add-on per applicare completamente i dati.'), status_code=303)
"""
    text = text[:start] + routes + text[end:]

path.write_text(text, encoding='utf-8')
