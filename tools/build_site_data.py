"""Turn the merged place list into data/places.json for the site.

Usage: python3 tools/build_site_data.py <merged places.json> [out=data/places.json]

Adds to every place:
  g  = map group (food, shops, going, parks, culture, wellness, essentials)
  v  = vibe tags. Robot picks keep their own; other places get a few tags
       guessed from their type (a cocktail bar gets "late night", a park
       "outdoors"), marked with vg=1 so the site can say they're guesses.
  m  = rough walking minutes from 8 Rivington (straight line x 1.25 street factor, 3 mph).
"""
import json, math, re, sys

HOME = (40.72203, -73.99198)
SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else 'data/places.json'

GROUP = {
    'Restaurants': 'food', 'Coffee, bakeries & sweets': 'food',
    'Clothing & style': 'shops', 'Shops': 'shops', 'Vintage & thrift': 'shops', 'Books & records': 'shops', 'Flowers & gifts': 'shops',
    'Bars & nightlife': 'going', 'Things to do': 'going',
    'Parks & outdoors': 'parks',
    'Museums & galleries': 'culture', 'Landmarks & history': 'culture',
    'Fitness & wellness': 'wellness', 'Beauty & grooming': 'wellness',
    'Groceries & markets': 'essentials', 'Health & pharmacy': 'essentials', 'Banks & ATMs': 'essentials', 'Everyday services': 'essentials',
    'Getting around': 'essentials', 'Civic & community': 'essentials', 'Libraries & schools': 'essentials', 'Hotels': 'essentials', 'Places of worship': 'essentials',
}

# vibe chips on the site: cozy, cheap, date night, outdoors, hidden gem, late night, lively, quiet
PICK_MAP = {'cheap eats': ['cheap'], 'hidden': ['hidden gem'], 'dive': ['late night', 'cheap'], 'live music': ['lively'],
            'cocktails': ['date night'], 'wine': ['date night'], 'comedy': ['lively'], 'trivia': ['lively'], 'chill': ['quiet'],
            'work from cafe': ['quiet'], 'rainy day': ['cozy'], 'movie night': ['date night'], 'splurge': ['date night']}

RULES = [  # (regex on type, vibes)
    (r'coffee|cafe|tea_room|tea$|bakery|Coffee/Tea', ['cozy']),
    (r'bookstore|book', ['cozy', 'quiet']),
    (r'pizza|fast_food|sandwich|delicatessen|deli|bagel|dumpling|taco|food_truck|hot_dog|falafel|noodle', ['cheap']),
    (r'dive_bar', ['late night', 'cheap']),
    (r'cocktail|wine_bar|speakeasy|lounge', ['date night', 'late night']),
    (r'italian|french|japanese|sushi|tapas|mediterranean|wine', ['date night']),
    (r'^bar$|pub|sports_bar|beer|brewery|karaoke|dance_club|nightclub', ['late night', 'lively']),
    (r'music_venue|comedy|theatre|jazz|performing_arts', ['lively']),
    (r'movie_theater|cinema', ['date night', 'cozy']),
    (r'park|playground|garden|plaza|beach', ['outdoors']),
    (r'library|museum|art_gallery|gallery|yoga|meditation|place_of_worship', ['quiet']),
    (r'second_hand|thrift|vintage|Secondhand', ['cheap', 'hidden gem']),
    (r'ice_cream|dessert|candy|chocolate|donut', ['cozy']),
]

def mi(la, lo):
    a, b, c, d = map(math.radians, (HOME[0], HOME[1], la, lo))
    x = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(x))

s = json.load(open(SRC))
cats = s['categories']

# Drop listings that are plainly not here: names in scripts this block doesn't use
# (Thai, Greek, Arabic, Bengali, Sinhala, styled unicode) and far-away landmarks.
def junk(p):
    n = p['n']
    if not re.search(r'[A-Za-z0-9\u4e00-\u9fff\u3400-\u4dbf]', n): return True
    if re.search(r'[\u0e00-\u0e7f\u0370-\u03ff\u0600-\u06ff\u0980-\u09ff\u0d80-\u0dff\U0001d400-\U0001d7ff]', n): return True
    if re.search(r'central park|times square|brooklyn bridge park', n, re.I): return True
    return False
s['places'] = [p for p in s['places'] if not junk(p)]

# Katie's own hand-placed picks from the first version of the site keep their vibes.
# Matched to the dataset by name; ones that couldn't be found anywhere are left out.
HAND = json.load(open(__file__.rsplit('/', 1)[0] + '/handpicked.json'))
ALIAS = {"Katz's Deli": "Katz's Delicatessen", 'Dirty French': 'Dirty French New York', 'Mercury Lounge': 'The Mercury Lounge',
         'Whole Foods Bowery': 'Whole Foods Market', 'Seward Park Library': 'Seward Park Library (NYPL)'}
EXTRA = {'169 Bar': dict(n='169 Bar', y=40.7138889, x=-73.9897222, a='169 E Broadway', h='Mon-Sun 2PM-4AM', k='dive_bar',
                         c=cats.index('Bars & nightlife'), t='p', note='just past the ring')}
byname = {}
for p in s['places']:
    byname.setdefault(p['n'], []).append(p)
for h in HAND:
    nm = ALIAS.get(h['name'], h['name'])
    cand = byname.get(nm, [])
    if not cand and h['name'] in EXTRA:
        e = dict(EXTRA[h['name']]); s['places'].append(e); cand = [e]
    if not cand:
        print('hand pick not found, left out:', h['name']); continue
    best = min(cand, key=lambda p: (p['y'] - h['lat']) ** 2 + (p['x'] - h['lng']) ** 2)
    best['v'] = sorted(set(best.get('v', []) + h['vibes'])); best['t'] = 'p'; best['hp'] = 1

out = []
for p in s['places']:
    cat = cats[p['c']]
    p['g'] = GROUP.get(cat, 'essentials')
    vib = []
    for v in p.get('v', []):
        vib += [v] + PICK_MAP.get(v, [])
    if vib:
        p['v'] = sorted(set(vib))
    else:
        t = (p.get('k') or '') + ' ' + cat
        g = []
        for rx, vs in RULES:
            if re.search(rx, p.get('k') or '', re.I):
                g += vs
        if cat == 'Parks & outdoors': g.append('outdoors')
        if re.search(r'24 ?hours|open 24', p.get('h') or '', re.I): g.append('late night')
        if g:
            p['v'] = sorted(set(g)); p['vg'] = 1
        else:
            p.pop('v', None)
    p['m'] = max(1, round(mi(p['y'], p['x']) * 1.25 / 3 * 60))
    out.append(p)
out.sort(key=lambda p: p['m'])
s['places'] = out
s['groups'] = {'food': 'Food', 'shops': 'Shops', 'going': 'Going out', 'parks': 'Parks', 'culture': 'Culture', 'wellness': 'Wellness & beauty', 'essentials': 'Essentials'}
json.dump(s, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
import collections
print(len(out), collections.Counter(p['g'] for p in out if p['t'] != 'm'))
print('with vibes (core+picks):', sum(1 for p in out if p['t'] != 'm' and p.get('v')))
