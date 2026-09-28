from pathlib import Path

path = Path('/app/app/main.py')
text = path.read_text(encoding='utf-8')

# Store timestamps in UTC, but display chat/reply times in the Home Assistant timezone.
# This prevents the 1/2-hour offset caused by slicing the raw UTC ISO timestamp.

import_marker = "from typing import Optional\n"
if import_marker in text and "from zoneinfo import ZoneInfo" not in text:
    text = text.replace(import_marker, import_marker + "from zoneinfo import ZoneInfo\n", 1)

helper_marker = "def now_iso():\n    return datetime.now(timezone.utc).isoformat()\n"
if helper_marker in text and "def format_local_datetime(" not in text:
    helper = r'''

_HA_TIMEZONE_CACHE = {'name': '', 'expires': 0.0}

def home_assistant_timezone_name():
    current = time.time()
    cached = _HA_TIMEZONE_CACHE.get('name') or ''
    if cached and current < float(_HA_TIMEZONE_CACHE.get('expires') or 0):
        return cached
    tz_name = ''
    token = os.environ.get('SUPERVISOR_TOKEN', '')
    if token:
        try:
            req = urllib.request.Request(
                'http://supervisor/core/api/config',
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                payload = json.loads(response.read().decode())
            tz_name = str(payload.get('time_zone') or '').strip()
        except Exception:
            tz_name = ''
    if not tz_name:
        tz_name = os.environ.get('TZ', '').strip() or 'Europe/Berlin'
    try:
        ZoneInfo(tz_name)
    except Exception:
        tz_name = 'Europe/Berlin'
    _HA_TIMEZONE_CACHE['name'] = tz_name
    _HA_TIMEZONE_CACHE['expires'] = current + 3600
    return tz_name


def format_local_datetime(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    try:
        stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        local = stamp.astimezone(ZoneInfo(home_assistant_timezone_name()))
        return local.strftime('%d.%m.%Y %H:%M')
    except Exception:
        return raw[:16].replace('T', ' ')

'''
    text = text.replace(helper_marker, helper_marker + helper, 1)

# Replace all chat/WhatsApp reply timestamp rendering with local timezone conversion.
text = text.replace(
    'esc(row["created_at"][:16].replace("T"," "))',
    'esc(format_local_datetime(row["created_at"]))'
)
text = text.replace(
    'esc(row["created_at"][:16].replace("T", " "))',
    'esc(format_local_datetime(row["created_at"]))'
)
text = text.replace(
    'esc(h["sent_at"][:16].replace("T", " "))',
    'esc(format_local_datetime(h["sent_at"]))'
)
text = text.replace(
    'esc(h["sent_at"][:16].replace("T"," "))',
    'esc(format_local_datetime(h["sent_at"]))'
)

path.write_text(text, encoding='utf-8')
