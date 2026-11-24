"""Pull every Overture Maps place within 0.6 mi of 8 Rivington St.

Usage: python3 tools/refresh/overture.py <out raw.json>

Reads the newest Overture release straight from its public S3 bucket, using
HTTP range requests so only the row groups near the apartment are downloaded.
No account or key is needed. Prints the release it used.
"""
import io, json, math, os, re, ssl, sys, urllib.request
import pyarrow.parquet as pq

OUT = sys.argv[1]
BASE = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/'
HOME = (40.72203, -73.99198)
R = 0.6  # miles, a bit beyond the 0.5 circle
dlat = R / 69.0
dlng = R / (69.0 * math.cos(math.radians(HOME[0])))
BB = (HOME[1] - dlng, HOME[0] - dlat, HOME[1] + dlng, HOME[0] + dlat)
ctx = ssl.create_default_context(cafile=os.environ.get('CA_BUNDLE') or None)


def get(url, start=None, end=None):
    req = urllib.request.Request(url)
    if start is not None:
        req.add_header('Range', f'bytes={start}-{end}')
    err = None
    for _ in range(4):
        try:
            return urllib.request.urlopen(req, context=ctx, timeout=120).read()
        except Exception as e:  # network blips: retry
            err = e
    raise err


class RangeFile(io.RawIOBase):
    def __init__(s, url, size): s.url, s.size, s.pos = url, size, 0
    def seekable(s): return True
    def readable(s): return True
    def tell(s): return s.pos
    def seek(s, o, w=0):
        s.pos = o if w == 0 else (s.pos + o if w == 1 else s.size + o)
        return s.pos
    def readinto(s, b):
        n = min(len(b), s.size - s.pos)
        if n <= 0:
            return 0
        d = get(s.url, s.pos, s.pos + n - 1)
        b[:len(d)] = d
        s.pos += len(d)
        return len(d)


def latest_release():
    x = get(BASE + '?list-type=2&delimiter=/&prefix=release/').decode()
    rels = re.findall(r'<Prefix>release/([0-9][^<]*)/</Prefix>', x)
    rels = [r for r in rels if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.\d+', r)]
    return sorted(rels, key=lambda r: (r.split('.')[0], int(r.split('.')[1])))[-1]


def list_files(prefix):
    files, token = [], None
    while True:
        u = BASE + '?list-type=2&prefix=' + prefix + ('&continuation-token=' + urllib.request.quote(token) if token else '')
        x = get(u).decode()
        files += re.findall(r'<Key>([^<]+\.parquet)</Key>.*?<Size>(\d+)</Size>', x)
        m = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', x)
        if not m:
            return files
        token = m.group(1)


def mi(la, lo):
    la1, lo1, la2, lo2 = map(math.radians, (HOME[0], HOME[1], la, lo))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(d))


def hit_groups(md, names):
    ix = {n: i for i, n in enumerate(names)}
    out = []
    for g in range(md.num_row_groups):
        rg = md.row_group(g)
        st = {k: rg.column(ix[k]).statistics for k in ('bbox.xmin', 'bbox.xmax', 'bbox.ymin', 'bbox.ymax')}
        if any(v is None or not v.has_min_max for v in st.values()):
            out.append(g)
            continue
        if st['bbox.xmax'].max < BB[0] or st['bbox.xmin'].min > BB[2] or st['bbox.ymax'].max < BB[1] or st['bbox.ymin'].min > BB[3]:
            continue
        out.append(g)
    return out


COLS = ['id', 'names', 'categories', 'basic_category', 'taxonomy', 'confidence', 'websites', 'socials', 'phones',
        'addresses', 'brand', 'operating_status', 'bbox', 'sources']

rel = latest_release()
files = list_files(f'release/{rel}/theme=places/type=place/')
print('release', rel, len(files), 'files', flush=True)
rows = []
for key, size in files:
    f = pq.ParquetFile(RangeFile(BASE + key, int(size)), buffer_size=0)
    md = f.metadata
    names = [md.schema.column(i).path for i in range(md.num_columns)]
    hits = hit_groups(md, names)
    have = set(f.schema_arrow.names)
    cols = [c for c in COLS if c in have]
    for g in hits:
        for r in f.read_row_group(g, columns=cols).to_pylist():
            b = r['bbox']
            la, lo = (b['ymin'] + b['ymax']) / 2, (b['xmin'] + b['xmax']) / 2
            if BB[1] <= la <= BB[3] and BB[0] <= lo <= BB[2]:
                d = mi(la, lo)
                if d <= R:
                    r['lat'], r['lng'], r['miles'] = round(la, 6), round(lo, 6), round(d, 3)
                    del r['bbox']
                    rows.append(r)
    print(key.rsplit('/', 1)[-1][:40], len(hits), 'row groups read, kept so far', len(rows), flush=True)
json.dump({'release': rel, 'places': rows}, open(OUT, 'w'), default=str)
print('TOTAL', len(rows))
