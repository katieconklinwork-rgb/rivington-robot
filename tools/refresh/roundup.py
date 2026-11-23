"""Write this week's roundup: what's new, what's gone, and the week's events.

Usage: python3 tools/refresh/roundup.py <old places.json> <new places.json> <events.json> [out=data/roundup.json]

"New" and "gone" compare last week's map with this week's, counting only the
places shown by default (robot picks and core places).
"""
import datetime as dt, json, math, re, sys
from zoneinfo import ZoneInfo

OLD, NEW, EV = sys.argv[1:4]
OUT = sys.argv[4] if len(sys.argv) > 4 else 'data/roundup.json'
NY = ZoneInfo('America/New_York')
today = dt.datetime.now(NY)


def load(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def shown(s):
    return [p for p in (s or {}).get('places', []) if p.get('t') in ('p', 'c')]


def key(p):
    return re.sub(r'[^a-z0-9]', '', p['n'].lower())


def same(a, b):
    return key(a) == key(b) and math.hypot((a['y'] - b['y']) * 69, (a['x'] - b['x']) * 52.4) < 0.1


def diff(a, b):
    idx = {}
    for p in b:
        idx.setdefault(key(p), []).append(p)
    return [p for p in a if not any(same(p, q) for q in idx.get(key(p), []))]


old, new = load(OLD), load(NEW)
cats = (new or {}).get('categories', [])


def card(p):
    return {k: v for k, v in dict(n=p['n'], k=p.get('k') or (cats[p['c']] if p['c'] < len(cats) else None), a=p.get('a'), m=p.get('m'), y=p['y'], x=p['x']).items() if v is not None}


opened = diff(shown(new), shown(old)) if old else []
closed = diff(shown(old), shown(new)) if old else []
opened.sort(key=lambda p: p.get('m', 99))
closed.sort(key=lambda p: p.get('m', 99))
week = today + dt.timedelta(days=7)
evs = [e for e in (load(EV) or {}).get('events', []) if dt.datetime.fromisoformat(e['start']) <= week][:10]
out = {'edition': today.date().isoformat(), 'new_count': len(opened), 'gone_count': len(closed),
       'new': [card(p) for p in opened[:12]], 'gone': [card(p) for p in closed[:12]], 'events': evs}
json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
print('ROUNDUP', out['edition'], 'new', len(opened), 'gone', len(closed), 'events', len(evs))
