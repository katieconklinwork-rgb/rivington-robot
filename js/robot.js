// Rivington Robot: shared place data, map and dice.
// Data: data/places.json, built by tools/build_site_data.py.
(function () {
  const CENTER = [40.72203, -73.99198];
  const RING_M = 805; // half a mile, the 10-minute walking ring
  const COLORS = { food: '#E24B4A', shops: '#EF9F27', going: '#F0C040', parks: '#639922', culture: '#7F77DD', wellness: '#D4537E', essentials: '#378ADD' };
  const CHIP = { food: 'c-red', shops: 'c-orange', going: 'c-yellow', parks: 'c-green', culture: 'c-purple', wellness: 'c-pink', essentials: 'c-blue' };

  let dataPromise = null;
  function load() {
    if (!dataPromise) {
      dataPromise = fetch('data/places.json', { cache: 'no-cache' })
        .then(r => { if (!r.ok) throw new Error('places ' + r.status); return r.json(); })
        .then(d => {
          d.places.forEach((p, i) => { p.i = i; p.cat = d.categories[p.c]; });
          return d;
        });
    }
    return dataPromise;
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function typeLabel(p) {
    if (!p.k) return p.cat;
    const k = p.k.replace(/_/g, ' ').replace(/^Restaurant - /i, '');
    return k.charAt(0).toUpperCase() + k.slice(1);
  }
  function walkUrl(p) {
    return 'https://www.google.com/maps/dir/?api=1&destination=' + p.y + ',' + p.x + '&travelmode=walking';
  }
  function safeUrl(u) {
    return /^https?:\/\//i.test(u || '') ? u : null;
  }
  function popupHtml(p) {
    const bits = [];
    bits.push('<div class="pop-name">' + esc(p.n) + '</div>');
    bits.push('<div class="pop-sub">' + esc(typeLabel(p)) + ' · about ' + p.m + ' min walk' + (p.note ? ' · ' + esc(p.note) : '') + '</div>');
    if (p.a) bits.push('<div class="pop-sub">' + esc(p.a) + '</div>');
    if (p.h) bits.push('<div class="pop-sub">' + esc(p.h) + '</div>');
    if (p.v && p.v.length) bits.push('<div class="pop-sub">' + esc(p.v.join(', ')) + (p.vg ? ' (guessed from type)' : '') + '</div>');
    const links = ['<a href="' + walkUrl(p) + '" target="_blank" rel="noopener">Walk there</a>'];
    const w = safeUrl(p.w);
    if (w) links.push('<a href="' + esc(w) + '" target="_blank" rel="noopener">Website</a>');
    if (p.p) links.push('<a href="tel:' + esc(p.p.replace(/[^+\d]/g, '')) + '">Call</a>');
    bits.push('<div class="pop-links">' + links.join(' · ') + '</div>');
    return bits.join('');
  }

  // ---------- MAP ----------
  function buildChips(el, d, onChange) {
    if (!el) return new Set(Object.keys(d.groups));
    const on = new Set(Object.keys(d.groups));
    const counts = {};
    d.places.forEach(p => { if (p.t !== 'm') counts[p.g] = (counts[p.g] || 0) + 1; });
    el.innerHTML = Object.entries(d.groups).map(([g, label]) =>
      '<span class="filter-chip active ' + CHIP[g] + '" data-cat="' + g + '">● ' + esc(label) + ' <span class="chip-n">' + (counts[g] || 0) + '</span></span>').join('');
    el.querySelectorAll('.filter-chip').forEach(c => c.addEventListener('click', () => {
      c.classList.toggle('active');
      if (c.classList.contains('active')) on.add(c.dataset.cat); else on.delete(c.dataset.cat);
      onChange();
    }));
    return on;
  }

  function initMap(opts) {
    const el = document.getElementById(opts.mapId);
    if (!el || typeof L === 'undefined') return;
    const map = L.map(el, { zoomControl: true, scrollWheelZoom: !!opts.scrollZoom, preferCanvas: true }).setView(CENTER, opts.zoom || 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap', maxZoom: 19 }).addTo(map);
    L.circle(CENTER, { radius: RING_M, color: '#E24B4A', weight: 2, fill: false, dashArray: '4 6', interactive: false }).addTo(map);
    const renderer = L.canvas({ padding: 0.5 });

    load().then(d => {
      const layer = L.layerGroup().addTo(map);
      let showAll = false;
      let on;
      function draw() {
        layer.clearLayers();
        // smaller dots first so picks sit on top
        const list = d.places.filter(p => on.has(p.g) && (showAll || p.t !== 'm'));
        list.sort((a, b) => (a.t === 'p') - (b.t === 'p'));
        list.forEach(p => {
          const pick = p.t === 'p';
          L.circleMarker([p.y, p.x], {
            renderer, radius: pick ? 7 : 4, color: 'white', weight: pick ? 2 : 1,
            fillColor: COLORS[p.g], fillOpacity: pick ? 1 : 0.85
          }).bindPopup(() => popupHtml(p)).addTo(layer);
        });
        if (opts.countId) {
          const c = document.getElementById(opts.countId);
          if (c) c.textContent = list.length.toLocaleString() + ' places';
        }
      }
      on = buildChips(document.getElementById(opts.chipsId), d, () => { draw(); if (opts.onFilter) opts.onFilter(on, showAll); });
      const all = opts.showAllId && document.getElementById(opts.showAllId);
      if (all) all.addEventListener('change', () => { showAll = all.checked; draw(); if (opts.onFilter) opts.onFilter(on, showAll); });
      draw();
      // home on top of everything
      L.circleMarker(CENTER, { radius: 9, color: '#E24B4A', weight: 3, fillColor: '#2C2A24', fillOpacity: 1 })
        .addTo(map).bindPopup('<div class="pop-name">8 Rivington St</div><div class="pop-sub">Home base</div>');
      if (opts.onReady) opts.onReady(d, on, () => showAll);
    }).catch(err => {
      el.insertAdjacentHTML('afterend', '<p class="load-err">The place list didn\'t load. Pull down to refresh.</p>');
      console.error(err);
    });
  }

  // ---------- LIST (map page) ----------
  function initList(opts) {
    const box = document.getElementById(opts.listId);
    const search = document.getElementById(opts.searchId);
    const more = document.getElementById(opts.moreId);
    if (!box) return;
    let state = { d: null, on: null, showAll: false, limit: 60 };
    function render() {
      if (!state.d) return;
      const q = (search && search.value || '').trim().toLowerCase();
      const rows = state.d.places.filter(p => state.on.has(p.g) && (state.showAll || p.t !== 'm') &&
        (!q || (p.n + ' ' + (p.k || '') + ' ' + p.cat + ' ' + (p.a || '') + ' ' + (p.v || []).join(' ')).toLowerCase().includes(q)));
      box.innerHTML = rows.slice(0, state.limit).map(p =>
        '<div class="place-row">' +
          '<span class="place-dot" style="background:' + COLORS[p.g] + '"></span>' +
          '<div class="place-body"><div class="place-name">' + esc(p.n) + (p.t === 'p' ? ' <span class="pick-badge">robot pick</span>' : '') + '</div>' +
          '<div class="place-sub">' + esc(typeLabel(p)) + (p.a ? ' · ' + esc(p.a) : '') + '</div></div>' +
          '<div class="place-min">' + p.m + '<span class="unit">MIN</span></div>' +
          '<a class="place-go" href="' + walkUrl(p) + '" target="_blank" rel="noopener">Go</a>' +
        '</div>').join('') || '<p class="place-empty">Nothing matches that. Try another word.</p>';
      if (more) {
        more.style.display = rows.length > state.limit ? '' : 'none';
        more.textContent = 'Show more (' + (rows.length - state.limit).toLocaleString() + ' left)';
      }
      if (opts.countId) {
        const c = document.getElementById(opts.countId);
        if (c) c.textContent = rows.length.toLocaleString() + (q ? ' matches' : ' places');
      }
    }
    if (search) search.addEventListener('input', () => { state.limit = 60; render(); });
    if (more) more.addEventListener('click', () => { state.limit += 120; render(); });
    return {
      ready(d, on, showAllFn) { state.d = d; state.on = on; state.showAll = showAllFn(); render(); },
      filter(on, showAll) { state.on = on; state.showAll = showAll; state.limit = 60; render(); }
    };
  }

  // ---------- DICE ----------
  function initDice(opts) {
    const btn = document.getElementById(opts.btnId);
    if (!btn) return;
    const vibeEls = document.querySelectorAll('#' + opts.vibesId + ' .vibe');
    const hint = document.getElementById(opts.hintId);
    const selected = new Set([...vibeEls].filter(e => e.classList.contains('on')).map(e => e.dataset.vibe));
    let D = null;
    function pool() {
      // everything people can walk into: robot picks and core places, not the "more" pile
      const base = D.places.filter(p => p.t !== 'm' && p.g !== 'essentials');
      return selected.size === 0 ? base : base.filter(p => (p.v || []).some(v => selected.has(v)));
    }
    function updateHint() {
      if (!D) return;
      const n = pool().length;
      hint.textContent = selected.size === 0
        ? 'Pulling from ' + n.toLocaleString() + ' places inside your ring'
        : 'Picking from ' + n.toLocaleString() + ' ' + [...selected].join(' + ') + ' spots inside your ring';
    }
    vibeEls.forEach(el => el.addEventListener('click', () => {
      const v = el.dataset.vibe;
      if (selected.has(v)) { selected.delete(v); el.classList.remove('on'); } else { selected.add(v); el.classList.add('on'); }
      updateHint();
    }));
    let last = null;
    function roll() {
      if (!D) return;
      const pl = pool();
      const nameEl = document.getElementById(opts.nameId), metaEl = document.getElementById(opts.metaId);
      if (!pl.length) {
        nameEl.textContent = 'No spots match those vibes';
        metaEl.textContent = 'Try fewer filters';
      } else {
        // robot picks come up more often than the rest
        const weights = pl.map(p => (p.t === 'p' ? 12 : 1) * (p === last ? 0 : 1));
        let r = Math.random() * weights.reduce((a, b) => a + b, 0), pick = pl[0];
        for (let i = 0; i < pl.length; i++) { r -= weights[i]; if (r <= 0) { pick = pl[i]; break; } }
        last = pick;
        nameEl.textContent = pick.n;
        const parts = [typeLabel(pick), 'about ' + pick.m + ' min from your door'];
        if (pick.a) parts.push(pick.a);
        if (pick.v && pick.v.length && !pick.vg) parts.push(pick.v.join(', '));
        metaEl.innerHTML = esc(parts.join(' · ')) + '<br><a href="' + walkUrl(pick) + '" target="_blank" rel="noopener">Walk there →</a>' +
          (safeUrl(pick.w) ? ' &nbsp; <a href="' + esc(pick.w) + '" target="_blank" rel="noopener">Website</a>' : '');
      }
      document.getElementById(opts.resultId).classList.add('show');
    }
    btn.addEventListener('click', roll);
    load().then(d => { D = d; updateHint(); }).catch(() => { hint.textContent = 'The place list didn\'t load. Pull down to refresh.'; });
  }

  window.Robot = { load, initMap, initList, initDice };
})();
