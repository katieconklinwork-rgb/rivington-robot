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
  // Link into Google Maps for this exact place — reviews, photos, and the
  // live "popular times / busy now" chart all live on that page for free.
  function reviewsUrl(p) {
    const q = encodeURIComponent((p.n || '') + (p.a ? ', ' + p.a : '') + ', New York, NY');
    return 'https://www.google.com/maps/search/?api=1&query=' + q;
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
    links.push('<a href="' + reviewsUrl(p) + '" target="_blank" rel="noopener">Reviews &amp; busy times ★</a>');
    const w = safeUrl(p.w);
    if (w) links.push('<a href="' + esc(w) + '" target="_blank" rel="noopener">Website</a>');
    if (p.p) links.push('<a href="tel:' + esc(p.p.replace(/[^+\d]/g, '')) + '">Call</a>');
    bits.push('<div class="pop-links">' + links.join(' · ') + '</div>');
    return bits.join('');
  }

  // ---------- MAP ----------
  // Two-level chip filter:
  //   - row 1: 7 broad group chips. Tapping the body toggles the whole
  //     group on/off; tapping the small caret opens that group's sub-chips.
  //   - row 2 (sub-tray): the fine categories inside the expanded group.
  //     Only one group's sub-tray is open at a time. Toggling a sub-chip
  //     affects just that category; the parent group chip shows a "partial"
  //     state when some but not all of its children are on.
  // Underlying filter is always `on.has(p.c)`.
  function buildChips(el, d, onChange, state) {
    const includeAll = () => state && state.showAll;
    const usePlace = p => includeAll() ? true : p.t !== 'm';

    const catGroup = {};
    const countsByCat = {};
    const catsByGroup = {};
    d.places.forEach(p => {
      if (!usePlace(p)) return;
      catGroup[p.c] = p.g;
      countsByCat[p.c] = (countsByCat[p.c] || 0) + 1;
      (catsByGroup[p.g] = catsByGroup[p.g] || new Set()).add(p.c);
    });

    const allCats = new Set(Object.keys(countsByCat).map(n => parseInt(n, 10)));
    const on = new Set(allCats);
    if (!el) return on;

    // state.openGroup: which group's sub-tray is open (null = none)
    if (!('openGroup' in state)) state.openGroup = null;

    function render() {
      const groupCounts = {};
      Object.entries(catsByGroup).forEach(([g, set]) => {
        let n = 0; set.forEach(ci => n += countsByCat[ci] || 0);
        groupCounts[g] = n;
      });

      const mainChips = Object.entries(d.groups).map(([g, label]) => {
        const cats = catsByGroup[g] ? [...catsByGroup[g]] : [];
        if (!cats.length) return '';
        const allOn = cats.every(ci => on.has(ci));
        const someOn = !allOn && cats.some(ci => on.has(ci));
        const onCount = cats.filter(ci => on.has(ci)).length;
        const isOpen = state.openGroup === g;
        const cls = ['filter-chip', 'chip-group', CHIP[g] || 'c-blue'];
        if (allOn) cls.push('active');
        else if (someOn) cls.push('partial');
        if (isOpen) cls.push('open');
        const subLabel = someOn ? (onCount + '/' + cats.length) : groupCounts[g];
        return '<span class="' + cls.join(' ') + '" data-g="' + g + '">' +
          '<span class="chip-label">' + esc(label) + ' <span class="chip-n">' + subLabel + '</span></span>' +
          '<button type="button" class="chip-caret" data-caret="' + g + '" aria-label="Refine ' + esc(label) + '">▾</button>' +
          '</span>';
      }).join('');

      let trayHtml = '';
      if (state.openGroup && catsByGroup[state.openGroup]) {
        const g = state.openGroup;
        const label = d.groups[g] || g;
        const cats = [...catsByGroup[g]].sort((a, b) => (countsByCat[b] || 0) - (countsByCat[a] || 0));
        const allOn = cats.every(ci => on.has(ci));
        const inner = cats.map(ci => {
          const cname = d.categories[ci] || ('Cat ' + ci);
          return '<span class="filter-chip chip-sub ' + (on.has(ci) ? 'active ' : '') + (CHIP[g] || 'c-blue') + '" data-ci="' + ci + '">' + esc(cname) + ' <span class="chip-n">' + (countsByCat[ci] || 0) + '</span></span>';
        }).join('');
        trayHtml = '<div class="sub-tray">' +
          '<div class="sub-tray-head"><span class="sub-tray-title">Inside ' + esc(label) + '</span>' +
          '<button type="button" class="sub-tray-act" data-all-on>All on</button>' +
          '<button type="button" class="sub-tray-act" data-all-off>All off</button>' +
          '<button type="button" class="sub-tray-close" data-close>close ×</button></div>' +
          '<div class="sub-tray-chips">' + inner + '</div>' +
          '</div>';
      }

      el.innerHTML = '<div class="chip-row">' + mainChips + '</div>' + trayHtml;

      el.querySelectorAll('.chip-group .chip-label').forEach(lbl => {
        lbl.addEventListener('click', ev => {
          ev.stopPropagation();
          const g = lbl.parentElement.dataset.g;
          const cats = [...(catsByGroup[g] || [])];
          const allOn = cats.every(ci => on.has(ci));
          if (allOn) cats.forEach(ci => on.delete(ci));
          else cats.forEach(ci => on.add(ci));
          render();
          onChange();
        });
      });
      el.querySelectorAll('.chip-caret').forEach(c => {
        c.addEventListener('click', ev => {
          ev.stopPropagation();
          const g = c.dataset.caret;
          state.openGroup = state.openGroup === g ? null : g;
          render();
        });
      });
      el.querySelectorAll('.chip-sub').forEach(c => {
        c.addEventListener('click', () => {
          const ci = parseInt(c.dataset.ci, 10);
          if (on.has(ci)) on.delete(ci); else on.add(ci);
          render();
          onChange();
        });
      });
      const close = el.querySelector('[data-close]');
      if (close) close.addEventListener('click', () => { state.openGroup = null; render(); });
      const allOnBtn = el.querySelector('[data-all-on]');
      if (allOnBtn) allOnBtn.addEventListener('click', () => {
        const cats = [...(catsByGroup[state.openGroup] || [])];
        cats.forEach(ci => on.add(ci));
        render(); onChange();
      });
      const allOffBtn = el.querySelector('[data-all-off]');
      if (allOffBtn) allOffBtn.addEventListener('click', () => {
        const cats = [...(catsByGroup[state.openGroup] || [])];
        cats.forEach(ci => on.delete(ci));
        render(); onChange();
      });
    }
    render();
    state.rebuildChips = render;
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
      // showAll is now always true — every place is always shown. There is no
      // "less certain listings" toggle anymore.
      const state = { showAll: true };
      let on;
      function draw() {
        layer.clearLayers();
        // smaller dots first so picks sit on top
        const list = d.places.filter(p => on.has(p.c));
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
      on = buildChips(document.getElementById(opts.chipsId), d, () => { draw(); if (opts.onFilter) opts.onFilter(on, state.showAll); }, state);
      draw();
      // make the shared `on` set reachable for chip re-renders
      state.on = on;
      // home on top of everything
      L.circleMarker(CENTER, { radius: 9, color: '#E24B4A', weight: 3, fillColor: '#2C2A24', fillOpacity: 1 })
        .addTo(map).bindPopup('<div class="pop-name">8 Rivington St</div><div class="pop-sub">Home base</div>');
      if (opts.onReady) opts.onReady(d, on, () => state.showAll);
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
      const rows = state.d.places.filter(p => state.on.has(p.c) &&
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
