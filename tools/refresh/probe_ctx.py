"""Test helper: print text around patterns on a page (setup branch only)."""
import re, sys, urllib.request
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
for line in sys.stdin.read().strip().split('\n'):
    url, *pats = line.split(' ')
    try:
        t = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30).read().decode('utf-8', 'replace')
    except Exception as e:
        print('ERR', url, e); continue
    print('==== PAGE', url, len(t))
    for p in pats:
        ms = list(re.finditer(p, t))
        print('-- PAT', p, len(ms))
        for m in ms[:3]:
            print('   >>', re.sub(r'\s+', ' ', t[max(0, m.start() - 250): m.end() + 450]))
