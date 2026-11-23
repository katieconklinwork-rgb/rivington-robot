#!/usr/bin/env bash
# Weekly refresh: places from Overture, events from venue sites, then the roundup.
# Run from the repo root. Writes data/places.json, data/events.json, data/roundup.json
# and a short summary for the pull request at $SUMMARY (default /tmp/summary.md).
set -u
SUMMARY=${SUMMARY:-/tmp/summary.md}
W=$(mktemp -d)
cp data/places.json "$W/old_places.json"

places_note="Places: unchanged (the map data pull didn't finish, so last week's places stay)."
if python3 tools/refresh/overture.py "$W/raw.json" \
   && python3 tools/refresh/merge.py "$W/raw.json" "$W/site.json" \
   && python3 tools/build_site_data.py "$W/site.json" "$W/places.json"; then
  n=$(python3 -c "import json,sys;s=json.load(open(sys.argv[1]));print(len(s['places']))" "$W/places.json")
  if [ "$n" -gt 5000 ]; then
    cp "$W/places.json" data/places.json
    places_note="Places: $n in and around the ring, from Overture release $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['release'])" "$W/site.json")."
  else
    places_note="Places: unchanged (the new pull only had $n places, which looks broken, so last week's stay)."
  fi
fi

python3 tools/refresh/events.py data/events.json || true
python3 tools/refresh/roundup.py "$W/old_places.json" data/places.json data/events.json data/roundup.json || true

python3 - "$SUMMARY" "$places_note" <<'PY'
import json, sys
out, note = sys.argv[1], sys.argv[2]
e = json.load(open('data/events.json')); r = json.load(open('data/roundup.json'))
lines = [
    "This week's update for Paul and Tina's site. Merge it to put it live; close it to skip this week.", '',
    f"- {note}",
    f"- New on the map since last week: {r['new_count']}. Gone: {r['gone_count']}.",
    f"- Events: {len(e['events'])} coming up within a mile. Sources that worked: {', '.join(e['sources_ok']) or 'none'}."
    + (f" Didn't work this week: {', '.join(e['sources_failed'])}." if e['sources_failed'] else ''),
]
if r['new']:
    lines += ['', 'Newly on the map: ' + ', '.join(p['n'] for p in r['new'][:8]) + ('…' if r['new_count'] > 8 else '')]
if r['gone']:
    lines += ['', 'No longer listed (closed or dropped from the data): ' + ', '.join(p['n'] for p in r['gone'][:8]) + ('…' if r['gone_count'] > 8 else '')]
lines += ['', 'Made by the weekly refresh in .github/workflows/weekly-refresh.yml.']
open(out, 'w').write('\n'.join(lines) + '\n')
print(open(out).read())
PY
