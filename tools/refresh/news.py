"""Gather hyperlocal LES/East Village news for the weekly roundup.

Usage: python3 tools/refresh/news.py [out=data/news.json]

Pulls the RSS feeds of four local blogs (The Lo-Down, EV Grieve,
Bowery Boogie, The Village Sun), keeps posts from the last ~7 days,
and writes a short list with title, url, source, date and blurb.
Each source is tried on its own; one that fails is skipped and named
in the file so the rest still come through.
"""
import datetime as dt, html, json, re, sys, urllib.request, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

OUT = sys.argv[1] if len(sys.argv) > 1 else 'data/news.json'
NY = ZoneInfo('America/New_York')
NOW = dt.datetime.now(NY)
DAYS = 8  # a little slack past 7 so items on the edge still make it in
UA = 'Mozilla/5.0 (compatible; RivingtonRobot/1.0; weekly neighborhood roundup)'

SOURCES = [
    dict(name='The Lo-Down',    url='https://www.thelodownny.com/leslog/feed'),
    dict(name='EV Grieve',      url='https://evgrieve.com/feeds/posts/default?alt=rss'),
    dict(name='Bowery Boogie',  url='https://www.boweryboogie.com/feed/'),
    dict(name='The Village Sun', url='https://thevillagesun.com/feed'),
]


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/rss+xml, application/xml, text/xml, */*'})
    return urllib.request.urlopen(req, timeout=40).read()


_PARSERS = [
    '%a, %d %b %Y %H:%M:%S %z',
    '%a, %d %b %Y %H:%M:%S %Z',
    '%Y-%m-%dT%H:%M:%S%z',
    '%Y-%m-%dT%H:%M:%SZ',
    '%Y-%m-%dT%H:%M:%S.%f%z',
]


def parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    # tz as "GMT" or "UTC" with %z fails; normalize to +0000
    s2 = re.sub(r'\s(GMT|UTC)$', ' +0000', s)
    for fmt in _PARSERS:
        try:
            d = dt.datetime.strptime(s2, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            return d.astimezone(NY)
        except ValueError:
            continue
    return None


# Strip HTML tags, collapse whitespace, decode entities, cap length.
def clean_blurb(raw, limit=220):
    if not raw:
        return ''
    t = html.unescape(raw)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(' ', 1)[0]
    return cut + '…'


# Both RSS 2.0 and Atom land here; tag is checked in both namespaces.
NS = {'atom': 'http://www.w3.org/2005/Atom'}


def pick_atom(entry, tag):
    el = entry.find('atom:' + tag, NS)
    return el.text if el is not None and el.text else ''


def pick_atom_link(entry):
    # atom: <link rel="alternate" href="..." />
    for link in entry.findall('atom:link', NS):
        if link.attrib.get('rel', 'alternate') == 'alternate':
            href = link.attrib.get('href')
            if href:
                return href
    el = entry.find('atom:link', NS)
    return el.attrib.get('href', '') if el is not None else ''


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    # RSS 2.0: <rss><channel><item>
    for item in root.iter('item'):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        pub = (item.findtext('pubDate') or '').strip()
        desc = item.findtext('description') or ''
        # content:encoded if there's no description
        if not desc:
            for child in item:
                if child.tag.endswith('}encoded'):
                    desc = child.text or ''
                    break
        items.append((title, link, parse_date(pub), clean_blurb(desc)))
    # Atom: <feed><entry>
    for entry in root.iter('{http://www.w3.org/2005/Atom}entry'):
        title = pick_atom(entry, 'title').strip()
        link = pick_atom_link(entry)
        pub = pick_atom(entry, 'published') or pick_atom(entry, 'updated')
        summary = pick_atom(entry, 'summary') or pick_atom(entry, 'content')
        items.append((title, link, parse_date(pub), clean_blurb(summary)))
    return items


def pull(src):
    body = get(src['url'])
    rows = []
    cutoff = NOW - dt.timedelta(days=DAYS)
    for (title, link, d, blurb) in parse_feed(body):
        if not title or not link or not d:
            continue
        if d < cutoff:
            continue
        rows.append(dict(title=title, url=link, source=src['name'],
                         date=d.strftime('%a %b %-d'),
                         date_iso=d.isoformat(),
                         blurb=blurb))
    return rows


def main():
    everything, ok, failed = [], [], []
    for src in SOURCES:
        try:
            got = pull(src)
            everything.extend(got)
            ok.append(src['name'])
            print(src['name'], 'ok', len(got))
        except Exception as e:  # network blip, 403, bad XML — skip but keep going
            failed.append(src['name'])
            print(src['name'], 'FAIL', repr(e))
    # newest first, then take up to 12 across all sources — enough for a weekly
    # read without overwhelming the roundup page.
    everything.sort(key=lambda r: r['date_iso'], reverse=True)
    trimmed = everything[:12]
    for r in trimmed:
        r.pop('date_iso', None)
    out = {'built': NOW.date().isoformat(), 'sources_ok': ok, 'sources_failed': failed, 'news': trimmed}
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('NEWS wrote', len(trimmed), 'items; ok:', ','.join(ok), 'failed:', ','.join(failed))


if __name__ == '__main__':
    main()
