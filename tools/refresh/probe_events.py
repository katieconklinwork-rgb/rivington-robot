"""Test helper: show what each event source's page looks like from GitHub."""
import re, sys, urllib.request
sys.argv = sys.argv[:1]
import importlib.util
spec = importlib.util.spec_from_file_location('ev', 'tools/refresh/events.py')
src = open('tools/refresh/events.py').read()
SOURCES = eval(src[src.index('SOURCES = [') + 10: src.index(']\n', src.index('SOURCES = [')) + 1])
EXTRA = sys.stdin.read().split() if not sys.stdin.isatty() else []
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
for s in (EXTRA or [x['url'] for x in SOURCES]):
    try:
        r = urllib.request.urlopen(urllib.request.Request(s, headers={'User-Agent': UA, 'Accept': 'text/html,*/*'}), timeout=30)
        t = r.read().decode('utf-8', 'replace')
        if t.lstrip()[:1] in '[{':
            print('JSON', s, r.status, len(t), t[:900].replace('\n', ' '))
            continue
        ld = re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', t, re.S | re.I)
        kw = [k for k in ('__NEXT_DATA__', 'wp-json', 'tribe-events', 'ticketweb', 'seetickets', 'dice.fm', 'eventbrite', 'axs.com', 'ticketmaster', 'etix', 'opendate', 'tixr', '.ics', 'application/rss', 'squarespace', 'webflow', 'Event"') if k in t]
        links = sorted(set(re.findall(r'href="([^"]*(?:ical|\.ics|feed|rss|/events?/[^"]{0,60}|json)[^"]*)"', t)))[:8]
        print('OK', s, r.status, len(t), 'ld+json', len(ld), [re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', b)[:6] for b in ld[:3]], (ld[0].strip()[:500] if ld and 'Event' in ld[0] else ''), kw, links)
    except Exception as e:
        print('ERR', s, type(e).__name__, str(e)[:100])
