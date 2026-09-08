from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')
start = text.find('def inventory_ai_recognize(image_bytes: bytes, content_type: str):')
end = text.find('\ndef smart_inventory_page(', start)
if start < 0 or end < 0:
    raise SystemExit('Inventory AI function not found')

new_func = r'''def inventory_ai_recognize(image_bytes: bytes, content_type: str):
    """Compila i dati articolo usando l'AI Task configurata in Home Assistant."""
    token = os.environ.get('SUPERVISOR_TOKEN', '').strip()
    if not token:
        return {}, 'AI di Home Assistant non disponibile: token Supervisor mancante.'

    media_dir = Path('/media/hausmeister_inventory')
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = '.png' if content_type == 'image/png' else '.webp' if content_type == 'image/webp' else '.jpg'
    filename = 'inventory_ai_' + secrets.token_hex(12) + ext
    media_file = media_dir / filename
    media_file.write_bytes(image_bytes)

    instructions = (
        "Usa la foto allegata per compilare una scheda di magazzino. "
        "Leggi etichette, confezione e caratteristiche visibili. Non inventare dati non leggibili. "
        "Restituisci i campi in italiano. Per name usa un nome articolo chiaro; category una categoria breve; "
        "brand la marca; code il codice/modello solo se leggibile; description includi le caratteristiche tecniche "
        "visibili utili (misure, potenza, temperatura colore, lumen, materiale, ecc.); unit normalmente pz; "
        "price solo se un prezzo e' visibile; tags parole chiave separate da virgole."
    )
    structure = {
        'name': {'description': 'Nome articolo', 'required': True, 'selector': {'text': {}}},
        'category': {'description': 'Categoria articolo', 'required': True, 'selector': {'text': {}}},
        'brand': {'description': 'Marca, vuoto se non leggibile', 'selector': {'text': {}}},
        'code': {'description': 'Codice o modello, vuoto se non leggibile', 'selector': {'text': {}}},
        'description': {'description': 'Descrizione e caratteristiche tecniche visibili', 'selector': {'text': {'multiline': True}}},
        'unit': {'description': 'Unita di misura, normalmente pz', 'selector': {'text': {}}},
        'price': {'description': 'Prezzo visibile oppure vuoto', 'selector': {'text': {}}},
        'tags': {'description': 'Parole chiave separate da virgole', 'selector': {'text': {}}},
    }
    payload = {
        'task_name': 'Compilazione automatica articolo magazzino Hausmeister',
        'instructions': instructions,
        'structure': structure,
        'attachments': [{
            'media_content_id': f'media-source://media_source/local/hausmeister_inventory/{filename}',
            'media_content_type': content_type,
        }],
    }
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        req = urllib.request.Request(
            'http://supervisor/core/api/services/ai_task/generate_data?return_response',
            data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
        response_data = result[0].get('service_response', {}) if isinstance(result, list) and result else result.get('service_response', {})
        values = response_data.get('data', response_data) if isinstance(response_data, dict) else {}
        if not isinstance(values, dict) or not values.get('name'):
            raise ValueError('AI Task non ha restituito dati articolo')
        return values, 'Compilazione automatica completata. Controlla i dati e salva.'
    except Exception as exc:
        return {}, 'Compilazione automatica non disponibile. Configura in Home Assistant una AI Task che supporti le immagini.'
    finally:
        try:
            media_file.unlink(missing_ok=True)
        except Exception:
            pass

'''
text = text[:start] + new_func + text[end+1:]
path.write_text(text, encoding='utf-8')
