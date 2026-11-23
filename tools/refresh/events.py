"""Gather upcoming events near 8 Rivington St into data/events.json.

Usage: python3 tools/refresh/events.py [out=data/events.json]

Each source is tried on its own; one that fails or changes its page is skipped
and named in the file, so the rest still come through. Events more than about
a mile away, or more than three weeks out, are left out. If every source fails,
the previous file is kept with past events dropped.
"""
import datetime as dt, html, json, math, os, re, sys, urllib.request
from zoneinfo import ZoneInfo

OUT = sys.argv[1] if len(sys.argv) > 1 else 'data/events.json'
NY = ZoneInfo('America/New_York')
HOME = (40.72203, -73.99198)
NOW = dt.datetime.now(NY)
HORIZON = NOW + dt.timedelta(days=21)
UA = 'Mozilla/5.0 (compatible; RivingtonRobot/1.0; weekly neighborhood calendar)'

# Venues and listings inside or next to the ring. 'near' is the walk from the apartment.
SOURCES = [
    dict(name='Bowery Ballroom', url='https://www.boweryballroom.com/events', kind='jsonld', near='2 min walk'),
    dict(name='Mercury Lounge', url='https://www.mercuryloungenyc.com/events', kind='jsonld', near='4 min walk'),
    dict(name='Rockwood Music Hall', url='https://www.rockwoodmusichall.com/', kind='jsonld', near='6 min walk'),
    dict(name="Arlene's Grocery", url='https://www.arlenesgrocery.net/', kind='jsonld', near='6 min walk'),
    dict(name='Pianos', url='https://www.pianosnyc.com/', kind='jsonld', near='6 min walk'),
    dict(name='Metrograph', url='https://metrograph.com/calendar/', kind='jsonld', near='10 min walk'),
    dict(name='New Museum', url='https://www.newmuseum.org/calendar', kind='jsonld', near='4 min walk'),
    dict(name='Tenement Museum', url='https://www.tenement.org/events/', kind='jsonld', near='6 min walk'),
    dict(name='DoNYC', url='https://donyc.com/events/today', kind='jsonld'),
    dict(name='NYC Parks', url='https://www.nycgovparks.org/xml/events_300_rss.json', kind='nycparks'),
]


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/json,*/*'})
    return urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'replace')


def miles(la, lo):
    a, b, c, d = map(math.radians, (HOME[0], HOME[1], la, lo))
    x = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(x))


def when(s):
    """ISO date or date-time -> aware datetime in New York, or None."""
    if not s:
        return None
    s = str(s).strip().replace('Z', '+00:00')
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        try:
            d = dt.datetime.combine(dt.date.fromisoformat(s[:10]), dt.time(0))
        except ValueError:
            return None
    return d.replace(tzinfo=NY) if d.tzinfo is None else d.astimezone(NY)


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))).strip()


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def from_jsonld(src, page):
    out = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for o in walk(data):
            t = o.get('@type')
            t = ' '.join(t) if isinstance(t, list) else str(t or '')
            if 'Event' not in t or not o.get('startDate'):
                continue
            loc = o.get('location') or {}
            loc = loc[0] if isinstance(loc, list) and loc else loc
            loc = loc if isinstance(loc, dict) else {'name': str(loc)}
            addr = loc.get('address') or ''
            if isinstance(addr, dict):
                addr = addr.get('streetAddress') or ''
            geo = loc.get('geo') or {}
            ev = dict(name=clean(o.get('name')), start=when(o.get('startDate')), end=when(o.get('endDate')),
                      venue=clean(loc.get('name')) or src['name'], address=clean(addr),
                      url=o.get('url') if str(o.get('url', '')).startswith('http') else src['url'], source=src['name'])
            try:
                ev['lat'], ev['lng'] = float(geo['latitude']), float(geo['longitude'])
            except (KeyError, TypeError, ValueError):
                pass
            if src.get('near'):
                ev['near'] = src['near']
            out.append(ev)
    return out


def from_nycparks(src, page):
    data = json.loads(page)
    items = data if isinstance(data, list) else data.get('items') or data.get('events') or []
    out = []
    for o in items:
        if not isinstance(o, dict):
            continue
        day = o.get('startdate') or o.get('start_date') or o.get('date')
        tm = o.get('starttime') or o.get('start_time') or ''
        start = when(day)
        if start and tm:
            m = re.match(r'(\d{1,2}):(\d{2})\s*([ap])', tm.strip(), re.I)
            if m:
                h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == 'p' else 0)
                start = start.replace(hour=h, minute=int(m.group(2)))
        ev = dict(name=clean(o.get('title')), start=start, end=None, venue=clean(o.get('location') or o.get('parknames')),
                  address='', url=o.get('link') if str(o.get('link', '')).startswith('http') else src['url'], source=src['name'])
        c = o.get('coordinates') or ''
        m = re.findall(r'-?\d+\.\d+', str(c))
        if len(m) >= 2:
            a, b = float(m[0]), float(m[1])
            ev['lat'], ev['lng'] = (a, b) if a > 0 else (b, a)
        out.append(ev)
    return out


PARSERS = {'jsonld': from_jsonld, 'nycparks': from_nycparks}
events, ok, failed = [], [], []
for src in SOURCES:
    try:
        got = PARSERS[src['kind']](src, get(src['url']))
    except Exception as e:  # a site that is down or changed: skip it
        failed.append(src['name'])
        print('FAILED', src['name'], type(e).__name__, str(e)[:120])
        continue
    keep = []
    for ev in got:
        if not ev['name'] or not ev['start'] or ev['start'] > HORIZON:
            continue
        if (ev['end'] or ev['start']) < NOW - dt.timedelta(hours=3):
            continue
        if 'lat' in ev:
            d = miles(ev['lat'], ev['lng'])
            if d > 1.0:
                continue
            ev.setdefault('near', f'{max(1, round(d * 1.25 / 3 * 60))} min walk')
        elif not src.get('near'):
            continue  # a city-wide listing with no location: can't tell if it's nearby
        keep.append(ev)
    print(src['name'], len(got), 'found,', len(keep), 'kept')
    (ok if got else failed).append(src['name'])
    events += keep

seen, final = set(), []
for ev in sorted(events, key=lambda e: e['start']):
    k = (re.sub(r'[^a-z0-9]', '', ev['name'].lower())[:40], ev['start'].date())
    if k in seen:
        continue
    seen.add(k)
    ev['start'] = ev['start'].isoformat()
    ev['end'] = ev['end'].isoformat() if ev['end'] else None
    final.append(ev)

if not final and os.path.exists(OUT):
    old = json.load(open(OUT))
    final = [e for e in old.get('events', []) if when(e.get('end') or e['start']) and when(e.get('end') or e['start']) > NOW]
    print('no new events found; kept', len(final), 'upcoming from last time')

json.dump({'built': NOW.isoformat(timespec='minutes'), 'sources_ok': ok, 'sources_failed': failed, 'events': final},
          open(OUT, 'w'), indent=1, ensure_ascii=False)
print('EVENTS', len(final), 'from', ok, 'failed', failed)
