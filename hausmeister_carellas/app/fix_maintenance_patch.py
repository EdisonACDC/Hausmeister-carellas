from pathlib import Path

path = Path('/app/app/patch_maintenance.py')
text = path.read_text(encoding='utf-8')
start = "    routes = r'''\n"
end = "\n\n'''\n    if route_marker not in text:\n"
fixed_start = '    routes = r"""\n'
fixed_end = '\n\n"""\n    if route_marker not in text:\n'
if start in text and end in text:
    text = text.replace(start, fixed_start, 1)
    text = text.replace(end, fixed_end, 1)
elif fixed_start not in text or fixed_end not in text:
    raise SystemExit('Maintenance routes markers not found')
path.write_text(text, encoding='utf-8')
