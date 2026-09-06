from pathlib import Path

path = Path('/app/app/main.py')
if not path.exists():
    path = Path(__file__).with_name('main.py')

text = path.read_text(encoding='utf-8')
old = '<label>{public_text(lang, \'photos\')}</label><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple><button>➤ {public_text(lang, \'send\')}</button>'
new = '''<label>{public_text(lang, 'photos')}</label><div id="photo-slots"><div class="photo-slot"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" onchange="showNextPhotoSlot(this)"></div><div class="photo-slot" style="display:none"><input type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif"></div></div><script>function showNextPhotoSlot(input){{if(!input.files||!input.files.length)return;const slot=input.closest('.photo-slot');const next=slot&&slot.nextElementSibling;if(next)next.style.display='block';}}</script><button>➤ {public_text(lang, 'send')}</button>'''

if old in text:
    path.write_text(text.replace(old, new, 1), encoding='utf-8')
elif 'id="photo-slots"' not in text:
    raise SystemExit('Photo form pattern not found; patch not applied')
