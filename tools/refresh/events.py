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

# Neighborhoods counted as "near" on DoNYC (its own district names).
NEAR_DISTRICTS = ('lower east side', 'east village', 'chinatown', 'nolita', 'little italy', 'soho', 'noho', 'bowery', 'two bridges')
SOURCES = [
    dict(name='Bowery Ballroom', url='https://www.boweryballroom.com/events', kind='mercuryeast', venue='Bowery Ballroom',
         address='6 Delancey St', near='2 min walk'),
    dict(name='Mercury Lounge', url='https://www.mercuryloungenyc.com/events', kind='mercuryeast', venue='Mercury Lounge',
         address='217 E Houston St', near='4 min walk'),
    dict(name='DoNYC', url='https://donyc.com/events', kind='donyc'),
]
DONYC_DAYS = 14   # days ahead to read
DONYC_PAGES = 15  # pages per day at most (20 events a page, city-wide)


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


MONTHS = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
                                      'october', 'november', 'december'], 1)}


def from_mercuryeast(src, page):
    """Bowery Ballroom and Mercury Lounge list shows as 'Name | 24 November 7:00 PM'."""
    out, seen = [], set()
    for url, title in re.findall(r'<div class="tw-name">\s*<a href="([^"]+)"[^>]*title="Event Name - ([^"]+)"', page):
        m = re.match(r'(.+?) \| (\d{1,2}) ([A-Za-z]+) (\d{1,2}):(\d{2}) ([AP]M)', html.unescape(title))
        if not m or m.group(3).lower() not in MONTHS:
            continue
        mon, day = MONTHS[m.group(3).lower()], int(m.group(2))
        year = NOW.year + (1 if mon < NOW.month - 1 else 0)
        hour = int(m.group(4)) % 12 + (12 if m.group(6) == 'PM' else 0)
        try:
            start = dt.datetime(year, mon, day, hour, int(m.group(5)), tzinfo=NY)
        except ValueError:
            continue
        if (url, start) in seen:
            continue
        seen.add((url, start))
        out.append(dict(name=clean(m.group(1)), start=start, end=None, venue=src['venue'], address=src['address'],
                        url=url if url.startswith('https://') else src['url'], source=src['name'], near=src['near']))
    return out


DONYC_EVENT = re.compile(r'title:"((?:[^"\\]|\\.)*)",permalink:"(/events/[^"]+)".*?'
                         r'tz_adjusted_begin_time:"([^"]+)",tz_adjusted_end_time:(null|"[^"]*"),event_type:"([a-z_]+)".*?'
                         r'category:(null|"[^"]*").*?venue:\{id:\d+,title:"((?:[^"\\]|\\.)*)",.*?district_name:(null|"[^"]*"),'
                         r'.*?area_name:(null|"[^"]*")', re.S)


def from_donyc(src, _page):
    """DoNYC's day pages carry their listings as data; keep the ones in nearby neighborhoods."""
    import time
    out = []
    for d in range(DONYC_DAYS):
        day = (NOW + dt.timedelta(days=d)).date()
        for pg in range(1, DONYC_PAGES + 1):
            url = f'https://donyc.com/events/{day.year}/{day.month}/{day.day}' + (f'?page={pg}' if pg > 1 else '')
            try:
                page = get(url)
            except Exception:
                break
            time.sleep(0.4)
            chunks = re.split(r'\{id:\d+,type:"event",', page)[1:]  # one chunk per listing
            found = [m.groups() for m in (DONYC_EVENT.search(c) for c in chunks) if m]
            for title, link, begin, end, kind, cat, venue, district, area in found:
                where = ' '.join(x.strip('"') for x in (district, area) if x != 'null').lower()
                if not any(n in where for n in NEAR_DISTRICTS):
                    continue
                start = when(begin)
                if kind != 'single_day' and start:  # a run of shows: list it on this day only
                    continue
                out.append(dict(name=clean(json.loads('"' + title + '"')), start=start,
                                end=when(end.strip('"')) if end != 'null' else None,
                                venue=clean(json.loads('"' + venue + '"')), address='', url='https://donyc.com' + link,
                                source='DoNYC', near=district.strip('"') if district != 'null' else '',
                                category=cat.strip('"') if cat != 'null' else ''))
            if f'page={pg + 1}' not in page:
                break
    return out


PARSERS = {'mercuryeast': from_mercuryeast, 'donyc': from_donyc}
events, ok, failed = [], [], []
for src in SOURCES:
    try:
        got = PARSERS[src['kind']](src, '' if src['kind'] == 'donyc' else get(src['url']))
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
        keep.append(ev)
    print(src['name'], len(got), 'found,', len(keep), 'kept')
    (ok if got else failed).append(src['name'])
    events += keep

seen, final = set(), []
for ev in sorted(events, key=lambda e: e['start']):
    k = (re.sub(r'[^a-z0-9]', '', ev['name'].lower())[:24], ev['start'].date())
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
