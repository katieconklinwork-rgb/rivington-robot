"""Merge the Overture pull with the census and the robot picks into one list.

Usage: python3 tools/refresh/merge.py <raw.json from overture.py> <out site-data.json>

Writes the compact list that tools/build_site_data.py turns into data/places.json:
  n name, c category index, y lat, x lng, t tier (p robot pick, c core, m more),
  a address, k type, w website, p phone, h hours, v vibes.
Closed places, low-confidence listings and offices are left out.
"""
import collections, datetime, json, math, os, re, sys

RAW, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(RAW))
release, raw = raw['release'], raw['places']
census = json.load(open(os.path.join(HERE, 'census_places.json')))
picks = json.load(open(os.path.join(HERE, 'picks.json')))
HOME = (40.72203, -73.99198)


def m_between(a, b):
    return 1609.34 * math.hypot((a[0] - b[0]) * 69.0, (a[1] - b[1]) * 69.0 * math.cos(math.radians(40.72)))


# app categories from Overture taxonomy hierarchy
def appcat(h, basic):
    s = set(h or []); leaf = (h or [''])[-1]
    def any_(*k): return any(x in s for x in k)
    if not s: return None
    if any_('parking'): return 'Getting around'
    if any_('park', 'playground', 'dog_park', 'garden', 'community_garden', 'botanical_garden', 'plaza', 'public_plaza', 'beach'): return 'Parks & outdoors'
    if any_('museum', 'art_gallery') or leaf.endswith('_museum'): return 'Museums & galleries'
    if any_('alcoholic_beverage_venue', 'nightlife_venue'): return 'Bars & nightlife'
    if any_('performing_arts_venue', 'movie_theater', 'event_venue', 'gaming_venue', 'music_venue', 'arts_and_crafts_space', 'amusement_attraction', 'escape_room'): return 'Things to do'
    if any_('non_alcoholic_beverage_venue', 'bakery', 'dessert_shop', 'ice_cream_shop', 'donut_shop', 'bagel_shop', 'coffee_shop', 'cafe', 'tea_room', 'candy_store', 'chocolatier', 'patisserie'): return 'Coffee, bakeries & sweets'
    if any_('food_and_drink'): return 'Restaurants'
    if any_('pharmacy', 'drug_store') or any_('health_care'): return 'Health & pharmacy'
    if any_('food_and_beverage_store', 'convenience_store', 'market', 'grocery_store', 'supermarket'): return 'Groceries & markets'
    if any_('sport_or_fitness_facility', 'sport_or_recreation_club', 'wellness_service', 'spa', 'massage_therapy', 'sports_and_recreation'): return 'Fitness & wellness'
    if any_('personal_or_beauty_service'): return 'Beauty & grooming'
    if any_('bookstore', 'books_music_and_video_store', 'music_store', 'record_store', 'comic_book_store', 'vinyl_record_store'): return 'Books & records'
    if any_('second_hand_store') or 'vintage' in leaf or 'thrift' in leaf or 'antique' in leaf: return 'Vintage & thrift'
    if any_('fashion_and_apparel_store'): return 'Clothing & style'
    if any_('flowers_and_gifts_store', 'gift_shop', 'florist'): return 'Flowers & gifts'
    if any_('shopping'): return 'Shops'
    if any_('lodging'): return 'Hotels'
    if any_('place_of_worship', 'religious_organization') or leaf.endswith('place_of_worship'): return 'Places of worship'
    if any_('library'): return 'Libraries & schools'
    if any_('education'): return 'Libraries & schools'
    if any_('bank_or_credit_union', 'bank', 'atm', 'credit_union'): return 'Banks & ATMs'
    if any_('laundry_service', 'shipping_or_delivery_service', 'animal_or_pet_service', 'key_and_locksmith', 'post_office', 'shoe_repair', 'tailor', 'dry_cleaning', 'it_service_and_computer_repair', 'luggage_storage', 'printing_service', 'mobile_phone_repair'): return 'Everyday services'
    if any_('cultural_and_historic'): return 'Landmarks & history'
    if any_('ground_transport_facility_or_service', 'bike_rental', 'vehicle_service', 'gas_station'): return 'Getting around'
    if any_('community_and_government'): return 'Civic & community'
    if any_('arts_and_entertainment'): return 'Things to do'
    return 'Offices & other'

SKIP = {'Offices & other'}


def norm(s):
    s = (s or '').lower().replace('&', ' and ')
    s = re.sub(r"[^a-z0-9 ]", ' ', s)
    s = re.sub(r'\b(the|inc|llc|corp|corporation|co|ltd|nyc|ny|new york|of)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


kept = []
for z in raw:
    if z['miles'] > 0.5 or z.get('operating_status') in ('permanently_closed', 'temporarily_closed'):
        continue
    conf = z.get('confidence') or 0
    ds = {s.get('dataset') for s in (z.get('sources') or [])} - {'Overture', 'Overture-signals'}
    tax = z.get('taxonomy') or {}
    cat = appcat(tax.get('hierarchy') or [], z.get('basic_category'))
    name = (z.get('names') or {}).get('primary')
    if cat is None or not name:
        continue
    registry_only = ds <= {'BrightQuery'}
    if registry_only and (cat in SKIP or conf < 0.75):
        continue
    if not registry_only and conf < 0.5:
        continue
    addr = (z.get('addresses') or [{}])[0] or {}
    kept.append(dict(name=name, category=cat, type=tax.get('primary') or z.get('basic_category'), lat=z['lat'], lng=z['lng'],
                     address=addr.get('freeform'), website=(z.get('websites') or [None])[0],
                     phone=(z.get('phones') or [None])[0], confidence=conf, registry_only=registry_only, src='overture'))

# same name within 60 m: keep the most confident one
kept.sort(key=lambda x: -x['confidence'])
byname, final = collections.defaultdict(list), []
for x in kept:
    k = norm(x['name'])
    if any(m_between((x['lat'], x['lng']), (y['lat'], y['lng'])) < 60 for y in byname[k]):
        continue
    byname[k].append(x)
    final.append(x)

# robot picks lend their vibes and hours to the matching listing, or join as their own row
PC = {'Park': 'Parks & outdoors', 'Garden': 'Parks & outdoors', 'Playground': 'Parks & outdoors', 'Dog run': 'Parks & outdoors',
      'Museum': 'Museums & galleries', 'Market': 'Groceries & markets', 'Library': 'Libraries & schools', 'Post office': 'Everyday services',
      'Grocery': 'Groceries & markets', 'Hardware': 'Shops', 'Laundry': 'Everyday services', 'Cafe': 'Coffee, bakeries & sweets',
      'Bakery': 'Coffee, bakeries & sweets', 'Bagels': 'Coffee, bakeries & sweets', 'Restaurant': 'Restaurants', 'Deli': 'Restaurants',
      'Burgers': 'Restaurants', 'Pizza': 'Restaurants', 'Dumplings': 'Restaurants', 'Noodles': 'Restaurants', 'Bar': 'Bars & nightlife',
      'Wine bar': 'Bars & nightlife', 'Music venue': 'Things to do', 'Cinema': 'Things to do', 'Comedy': 'Things to do', 'Yoga': 'Fitness & wellness'}
extra = []
for p in picks:
    k = norm(p['name'])
    hit = byname.get(k) or [x for x in final if norm(x['name']).startswith(k[:12]) and m_between((x['lat'], x['lng']), (p['lat'], p['lng'])) < 80]
    if hit:
        for h in hit:
            if p.get('vibes'): h['vibes'] = p['vibes']
            if p.get('hours'): h['hours'] = p['hours']
            h['pick'] = True
        continue
    if p['miles'] <= 0.7:
        extra.append(dict(name=p['name'], category=PC.get(p.get('category'), 'Things to do'), lat=p['lat'], lng=p['lng'],
                          address=p.get('address'), hours=p.get('hours'), vibes=p.get('vibes'), pick=True, src='places_search'))

allp = final + census + extra


def tier(x):
    if x.get('vibes') or x.get('pick'): return 'p'
    if x['category'] in SKIP: return None
    if x['src'] != 'overture': return 'c'
    if x.get('registry_only'): return 'm'
    return 'c' if (x.get('confidence') or 0) >= 0.8 else 'm'


CAT = sorted({x['category'] for x in allp})
out = []
for x in allp:
    t = tier(x)
    if t is None or x.get('lat') is None:
        continue
    o = {'n': x['name'], 'c': CAT.index(x['category']), 'y': round(x['lat'], 6), 'x': round(x['lng'], 6), 't': t}
    if x.get('address'):
        a = x['address'].split(',')[0].strip()
        o['a'] = a.title() if a.isupper() else a
    if x.get('type') and x['type'] != x['category']: o['k'] = x['type']
    if x.get('website'): o['w'] = x['website']
    if x.get('phone'): o['p'] = x['phone']
    if x.get('hours'): o['h'] = x['hours']
    if x.get('vibes'): o['v'] = x['vibes']
    out.append(o)

# one row per place: same name within about 100 m, best tier wins, gaps filled from the others
rank = {'p': 0, 'c': 1, 'm': 2}
keep, grid = [], {}
for p in sorted(out, key=lambda p: rank[p['t']]):
    k = ' '.join(re.sub(r'\b(the|inc|llc|nyc|ny)\b', '', re.sub(r'[^a-z0-9 ]', ' ', p['n'].lower().replace('&', ' and '))).split())
    dup = None
    for q in grid.get(k, []):
        if math.hypot((p['y'] - q['y']) * 69, (p['x'] - q['x']) * 52.4) < 0.06:
            dup = q
            break
    if dup:
        for f in ('a', 'w', 'p', 'h', 'v', 'k'):
            if f not in dup and f in p: dup[f] = p[f]
        continue
    keep.append(p)
    grid.setdefault(k, []).append(p)

site = {'home': {'lat': HOME[0], 'lng': HOME[1], 'radius_mi': 0.5}, 'built': datetime.date.today().isoformat(),
        'sources': f"Overture Maps places release {release}; Katie's 826-business census (NYC DOHMH/DCWP/Google); Google Maps place lookups read 2026-11-23",
        'release': release,
        'tiers': {'p': 'robot pick (has vibe tags)', 'c': 'core: shown by default and eligible for the dice', 'm': 'more: shown when "show everything" is on'},
        'categories': CAT, 'places': keep}
json.dump(site, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print('release', release, 'kept', len(keep), collections.Counter(p['t'] for p in keep))
