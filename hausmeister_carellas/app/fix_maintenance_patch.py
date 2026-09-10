from pathlib import Path

path = Path('/app/app/patch_maintenance.py')
text = path.read_text(encoding='utf-8')
start = "    routes = r'''\n"
end = "\n\n'''\n    if route_marker not in text:\n"
if start not in text:
    raise SystemExit('Maintenance routes start marker not found')
if end not in text:
    raise SystemExit('Maintenance routes end marker not found')
text = text.replace(start, '    routes = r"""\n', 1)
text = text.replace(end, '\n\n"""\n    if route_marker not in text:\n', 1)
path.write_text(text, encoding='utf-8')
