from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Dashboard cards -> filtered ticket lists.
# Apply to admin, external manager, and owner views.

# --- ADMIN dashboard cards ---
admin_cards = {
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Totale ticket</span><strong>{total}</strong></div></div></div>''':
'''      <a class="card span-3" href="tickets?view=all" onclick="return adminGo('tickets?view=all')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Totale ticket</span><strong>{total}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Aperti</span><strong>{open_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="tickets?view=open" onclick="return adminGo('tickets?view=open')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Aperti</span><strong>{open_count}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{work_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="tickets?view=working" onclick="return adminGo('tickets?view=working')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{work_count}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">Risolti</span><strong>{done_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="tickets?view=resolved" onclick="return adminGo('tickets?view=resolved')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">Risolti</span><strong>{done_count}</strong></div></div></a>'''
}
for old,new in admin_cards.items():
    if old in text:
        text = text.replace(old,new,1)

# Admin tickets supports dashboard view filters.
old = "def tickets_page(q: str = '', status: str = '', message: str = ''):"
new = "def tickets_page(q: str = '', status: str = '', view: str = '', message: str = ''):"
if old in text:
    text = text.replace(old,new,1)

old_filter = """    if status in STATUSES:
        query += ' AND t.status=?'
        params.append(status)
"""
new_filter = """    if view == 'open':
        query += " AND t.status='Nuovo'"
        status = 'Nuovo'
    elif view == 'working':
        query += " AND t.status IN ('Preso in carico','In lavorazione')"
        status = ''
    elif view == 'resolved':
        query += " AND t.status='Risolto'"
        status = 'Risolto'
    elif status in STATUSES:
        query += ' AND t.status=?'
        params.append(status)
"""
if old_filter in text:
    text = text.replace(old_filter,new_filter,1)

# Preserve selected dashboard view while using search/filter form.
old_form = """<form class="filters" method="get"><div><label>Cerca</label>"""
new_form = """<form class="filters" method="get"><input type="hidden" name="view" value="{esc(view)}"><div><label>Cerca</label>"""
if old_form in text:
    text = text.replace(old_form,new_form,1)

# --- MANAGER dashboard cards ---
manager_cards = {
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></div>''':
'''      <a class="card span-3" href="/manager/tickets?view=all" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">{manager_text(lang, 'total')}</span><strong>{total}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="/manager/tickets?view=open" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">{manager_text(lang, 'open')}</span><strong>{open_count}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="/manager/tickets?view=working" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">{manager_text(lang, 'working')}</span><strong>{work_count}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></div>''':
'''      <a class="card span-3" href="/manager/tickets?view=resolved" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">✓</div><div><span class="muted">{manager_text(lang, 'resolved')}</span><strong>{done_count}</strong></div></div></a>'''
}
for old,new in manager_cards.items():
    if old in text:
        text = text.replace(old,new,1)

old = "def manager_tickets_page(request: Request, q: str = '', status: str = '', message: str = ''):"
new = "def manager_tickets_page(request: Request, q: str = '', status: str = '', view: str = '', message: str = ''):"
if old in text:
    text = text.replace(old,new,1)

# Replace next occurrence of status filter for manager route.
manager_pos = text.find("def manager_tickets_page(")
if manager_pos >= 0:
    filter_pos = text.find(old_filter, manager_pos)
    if filter_pos >= 0:
        text = text[:filter_pos] + new_filter + text[filter_pos+len(old_filter):]
    form_pos = text.find("""<form class="filters" method="get"><div><label>{manager_text(lang, 'search')}</label>""", manager_pos)
    if form_pos >= 0:
        old_mgr_form = """<form class="filters" method="get"><div><label>{manager_text(lang, 'search')}</label>"""
        new_mgr_form = """<form class="filters" method="get"><input type="hidden" name="view" value="{esc(view)}"><div><label>{manager_text(lang, 'search')}</label>"""
        text = text[:form_pos] + text[form_pos:].replace(old_mgr_form,new_mgr_form,1)

# --- OWNER dashboard ---
owner_cards = {
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Ticket totali</span><strong>{total}</strong></div></div></div>''':
'''      <a class="card span-3" href="owner/tickets?view=all" onclick="return adminGo('owner/tickets?view=all')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">☷</div><div><span class="muted">Ticket totali</span><strong>{total}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Nuovi</span><strong>{counts.get('Nuovo', 0)}</strong></div></div></div>''':
'''      <a class="card span-3" href="owner/tickets?view=open" onclick="return adminGo('owner/tickets?view=open')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">⌛</div><div><span class="muted">Nuovi</span><strong>{counts.get('Nuovo', 0)}</strong></div></div></a>''',
'''      <div class="card span-3"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{counts.get('In lavorazione', 0)}</strong></div></div></div>''':
'''      <a class="card span-3" href="owner/tickets?view=working" onclick="return adminGo('owner/tickets?view=working')" style="text-decoration:none;color:inherit;cursor:pointer"><div class="metric"><div class="metric-icon">🔧</div><div><span class="muted">In lavorazione</span><strong>{counts.get('In lavorazione', 0)}</strong></div></div></a>'''
}
for old,new in owner_cards.items():
    if old in text:
        text = text.replace(old,new,1)

old = "def ha_owner_tickets(q: str = '', status: str = ''):"
new = "def ha_owner_tickets(q: str = '', status: str = '', view: str = ''):"
if old in text:
    text = text.replace(old,new,1)

owner_pos = text.find("def ha_owner_tickets(")
if owner_pos >= 0:
    owner_filter = """    if status in STATUSES:
        sql += ' AND t.status=?'
        params.append(status)
"""
    owner_new = """    if view == 'open':
        sql += " AND t.status='Nuovo'"
        status = 'Nuovo'
    elif view == 'working':
        sql += " AND t.status IN ('Preso in carico','In lavorazione')"
        status = ''
    elif view == 'resolved':
        sql += " AND t.status='Risolto'"
        status = 'Risolto'
    elif status in STATUSES:
        sql += ' AND t.status=?'
        params.append(status)
"""
    fp = text.find(owner_filter, owner_pos)
    if fp >= 0:
        text = text[:fp] + owner_new + text[fp+len(owner_filter):]

path.write_text(text, encoding='utf-8')
