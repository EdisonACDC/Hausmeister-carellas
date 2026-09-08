from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

replacements = {
    "return {}, 'Riconoscimento AI non configurato. Puoi comunque completare i campi manualmente.'": "return {}, 'Compilazione automatica non configurata. Puoi comunque completare i campi manualmente.'",
    "return parsed, 'Dati riconosciuti dalla foto. Controllali prima di salvare.'": "return parsed, 'Campi compilati automaticamente dalla foto. Controllali prima di salvare.'",
    "return {}, f'Riconoscimento non riuscito: {type(exc).__name__}. Compila o correggi i campi manualmente.'": "return {}, f'Compilazione automatica non riuscita: {type(exc).__name__}. Compila o correggi i campi manualmente.'",
    '<div class="mi-step"><b>1</b>📷 Scatta la foto</div><div class="mi-step"><b>2</b>🔎 Riconoscimento</div>': '<div class="mi-step"><b>1</b>📷 Foto o immagine</div><div class="mi-step"><b>2</b>✨ Compilazione automatica</div>',
    '<div class="mi-card"><h2>Nuovo articolo da foto</h2>{photo_preview}': '<div class="mi-card"><h2>Nuovo articolo da foto o immagine</h2>{photo_preview}',
    '<p class="muted">L’AI legge testo e caratteristiche visibili e precompila i campi. Controlla sempre i dati prima di salvare.</p>': '<p class="muted">Scatta una foto oppure carica un’immagine dell’articolo. I campi vengono compilati automaticamente; controllali prima di salvare.</p>',
}
for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new, 1)

old_form = '''        <form method="post" enctype="multipart/form-data" action="materials/recognize" style="margin-top:12px">
          <input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" capture="environment" required>
          <button class="mi-primary" type="submit">🧠 Riconoscimento automatico</button>
        </form>'''
new_form = '''        <div class="mi-grid2" style="margin-top:12px">
          <form method="post" enctype="multipart/form-data" action="materials/recognize">
            <label>Scatta foto articolo</label>
            <input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" capture="environment" required>
            <button class="mi-primary" type="submit">📷 Scatta foto e compila</button>
          </form>
          <form method="post" enctype="multipart/form-data" action="materials/recognize">
            <label>Inserisci immagine articolo</label>
            <input type="file" name="photo" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" required>
            <button class="mi-primary" type="submit">🖼 Carica immagine e compila</button>
          </form>
        </div>'''
if old_form in text:
    text = text.replace(old_form, new_form, 1)
elif 'Scatta foto e compila' not in text:
    raise SystemExit('Smart inventory form marker not found')

path.write_text(text, encoding='utf-8')
