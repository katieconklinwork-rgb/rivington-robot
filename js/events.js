// Rivington Robot: events list, social calendar and weekly roundup.
// Data: data/events.json and data/roundup.json, rebuilt every Sunday by
// .github/workflows/weekly-refresh.yml. Past events are hidden in the browser,
// so a missed week never shows something that already happened.
(function () {
  const DAYS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : null; }
  function getJson(path) {
    return fetch(path, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); });
  }

  // Times are stored with their New York offset, so Date parses them correctly.
  function nyParts(d) {
    const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
    const o = {}; f.formatToParts(d).forEach(p => { o[p.type] = p.value; });
    return o;
  }
  function timeLabel(d) {
    const p = nyParts(d);
    if (p.hour === '12' && p.minute === '00' && p.dayPeriod === 'AM') return 'All day';
    return p.hour + (p.minute === '00' ? '' : ':' + p.minute) + p.dayPeriod.toLowerCase();
  }
  function dayKey(d) { const p = nyParts(d); return p.weekday + ' ' + p.month + ' ' + p.day; }

  function upcoming(data) {
    const now = Date.now() - 3 * 3600 * 1000;
    return (data.events || []).map(e => Object.assign({}, e, { s: new Date(e.start), e2: e.end ? new Date(e.end) : null }))
      .filter(e => !isNaN(e.s) && (e.e2 || e.s).getTime() > now)
      .sort((a, b) => a.s - b.s);
  }

  function stamp(d) { return d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, ''); }
  function endOf(e) { return e.e2 || new Date(e.s.getTime() + 2 * 3600 * 1000); }
  function googleUrl(e) {
    const q = new URLSearchParams({ action: 'TEMPLATE', text: e.name, dates: stamp(e.s) + '/' + stamp(endOf(e)),
      location: [e.venue, e.address].filter(Boolean).join(', '), details: safeUrl(e.url) || '' });
    return 'https://calendar.google.com/calendar/render?' + q.toString();
  }
  function icsHref(e) {
    const t = s => String(s || '').replace(/[\\,;]/g, m => '\\' + m).replace(/\n/g, ' ');
    const body = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Rivington Robot//EN', 'BEGIN:VEVENT',
      'UID:' + stamp(e.s) + '-' + encodeURIComponent(e.name).slice(0, 40) + '@rivington-robot',
      'DTSTAMP:' + stamp(new Date()), 'DTSTART:' + stamp(e.s), 'DTEND:' + stamp(endOf(e)),
      'SUMMARY:' + t(e.name), 'LOCATION:' + t([e.venue, e.address].filter(Boolean).join(', ')),
      'URL:' + t(safeUrl(e.url) || ''), 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
    return 'data:text/calendar;charset=utf-8,' + encodeURIComponent(body);
  }

  function eventRow(e, withButtons) {
    const p = nyParts(e.s);
    const meta = [timeLabel(e.s), e.venue, e.near].filter(Boolean).map(esc).join(' · ');
    const url = safeUrl(e.url);
    let html = '<div class="event"><div class="event-date"><div class="day">' + esc(p.day) + '</div><span class="mon">' + esc(p.weekday.toUpperCase()) + '</span></div>' +
      '<div class="event-body"><div class="event-name">' + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(e.name) + '</a>' : esc(e.name)) + '</div>' +
      '<div class="event-meta">' + meta + '</div>';
    if (withButtons) {
      html += '<div class="event-add"><a href="' + esc(googleUrl(e)) + '" target="_blank" rel="noopener">Google Calendar</a>' +
        '<a href="' + esc(icsHref(e)) + '" download="event.ics">Apple / other</a></div>';
    }
    return html + '</div></div>';
  }

  function emptyNote(el, text) { el.innerHTML = '<p class="event-empty">' + esc(text) + '</p>'; }

  // Home page: the next few events.
  function initList(opts) {
    const el = document.getElementById(opts.listId);
    const note = opts.noteId && document.getElementById(opts.noteId);
    if (!el) return;
    getJson('data/events.json').then(d => {
      const ev = upcoming(d).slice(0, opts.limit || 6);
      if (!ev.length) return emptyNote(el, 'Nothing listed for the next few days yet. New events land every Sunday.');
      el.innerHTML = ev.map(e => eventRow(e, false)).join('');
      if (note) note.textContent = 'Updated every Sunday from local venues and NYC Parks.';
    }).catch(() => emptyNote(el, "Couldn't load events just now."));
  }

  // Home page: a one-week calendar grouped by day, with ticket links baked in
  // and "Add to calendar" buttons on every event. Shows a card per day so
  // empty days still show up and the layout reads like a week at a glance.
  function initWeek(opts) {
    const el = document.getElementById(opts.listId);
    if (!el) return;
    const days = opts.days || 7;
    const perDay = opts.perDay || 4;
    getJson('data/events.json').then(d => {
      const ev = upcoming(d);
      // Build an ordered list of the next N day buckets starting from today NY time.
      const today = new Date();
      const todayKey = dayKey(today);
      // find index of today's bucket among events; build date list by walking days forward
      const buckets = [];
      for (let i = 0; i < days; i++) {
        const dt = new Date(today.getTime() + i * 86400000);
        const k = dayKey(dt);
        const parts = nyParts(dt);
        buckets.push({
          key: k,
          dayNum: parts.day,
          weekday: parts.weekday,
          month: parts.month,
          events: []
        });
      }
      ev.forEach(e => {
        const k = dayKey(e.s);
        const b = buckets.find(x => x.key === k);
        if (b) b.events.push(e);
      });
      if (!buckets.some(b => b.events.length)) {
        return emptyNote(el, 'Nothing listed for the next week yet. New events land every Sunday.');
      }
      el.innerHTML = buckets.map(b => {
        const isToday = b.key === todayKey;
        const head = '<div class="wk-head"><div class="wk-dow">' + esc(b.weekday.toUpperCase()) + (isToday ? ' · TODAY' : '') + '</div>' +
          '<div class="wk-date">' + esc(b.month) + ' ' + esc(b.dayNum) + '</div></div>';
        if (!b.events.length) return '<div class="wk-day wk-empty">' + head + '<div class="wk-none">Nothing listed</div></div>';
        const shown = b.events.slice(0, perDay);
        const extra = b.events.length - shown.length;
        const list = shown.map(e => weekEventRow(e)).join('');
        const more = extra > 0 ? '<a class="wk-more" href="calendar.html">+ ' + extra + ' more this day →</a>' : '';
        return '<div class="wk-day">' + head + '<div class="wk-events">' + list + '</div>' + more + '</div>';
      }).join('');
    }).catch(() => emptyNote(el, "Couldn't load events just now."));
  }

  function weekEventRow(e) {
    const url = safeUrl(e.url);
    const t = timeLabel(e.s);
    const meta = [e.venue, e.near].filter(Boolean).map(esc).join(' · ');
    const title = url
      ? '<a href="' + esc(url) + '" target="_blank" rel="noopener" class="wk-name">' + esc(e.name) + '</a>'
      : '<span class="wk-name">' + esc(e.name) + '</span>';
    const links = [];
    if (url) links.push('<a href="' + esc(url) + '" target="_blank" rel="noopener" class="wk-tix">Tickets &amp; info →</a>');
    links.push('<a href="' + esc(googleUrl(e)) + '" target="_blank" rel="noopener" class="wk-cal">+ Google Cal</a>');
    links.push('<a href="' + esc(icsHref(e)) + '" download="event.ics" class="wk-cal">+ Apple</a>');
    return '<div class="wk-ev"><div class="wk-time">' + esc(t) + '</div>' +
      '<div class="wk-body">' + title +
      (meta ? '<div class="wk-meta">' + meta + '</div>' : '') +
      '<div class="wk-links">' + links.join('') + '</div>' +
      '</div></div>';
  }

  // Calendar page: everything coming up, grouped by day, with Add to calendar.
  function initCalendar(opts) {
    const el = document.getElementById(opts.listId);
    if (!el) return;
    getJson('data/events.json').then(d => {
      const ev = upcoming(d);
      if (!ev.length) return emptyNote(el, 'Nothing listed yet. New events land every Sunday.');
      let html = '', last = '';
      ev.forEach(e => {
        const k = dayKey(e.s);
        if (k !== last) { html += '<h3 class="cal-day">' + esc(k) + '</h3>'; last = k; }
        html += eventRow(e, true);
      });
      el.innerHTML = '<div class="event-list">' + html + '</div>';
    }).catch(() => emptyNote(el, "Couldn't load events just now."));
  }

  // Roundup page: the latest Sunday edition.
  function initRoundup(opts) {
    const el = document.getElementById(opts.bodyId);
    if (!el) return;
    getJson('data/roundup.json').then(r => {
      const d = new Date(r.edition + 'T12:00:00');
      const parts = ['<p class="roundup-date">Edition of ' + esc(DAYS[d.getDay()].charAt(0) + DAYS[d.getDay()].slice(1).toLowerCase()) + ' ' + esc(MONTHS[d.getMonth()]) + ' ' + d.getDate() + '</p>'];
      const place = p => '<li><b>' + esc(p.n) + '</b>' + (p.k ? ' · ' + esc(String(p.k).replace(/_/g, ' ')) : '') + (p.a ? ' · ' + esc(p.a) : '') + (p.m ? ' · ' + p.m + ' min walk' : '') + '</li>';
      parts.push('<h3 class="cal-day">New on the map</h3>' + (r.new && r.new.length ? '<ul class="roundup-list">' + r.new.map(place).join('') + '</ul>' + (r.new_count > r.new.length ? '<p class="event-empty">and ' + (r.new_count - r.new.length) + ' more</p>' : '') : '<p class="event-empty">Nothing new this week.</p>'));
      if (r.gone && r.gone.length) parts.push('<h3 class="cal-day">No longer listed</h3><ul class="roundup-list">' + r.gone.map(place).join('') + '</ul>');
      const ev = upcoming({ events: r.events || [] });
      parts.push('<h3 class="cal-day">This week</h3>' + (ev.length ? '<div class="event-list">' + ev.map(e => eventRow(e, true)).join('') + '</div>' : '<p class="event-empty">No events listed this week.</p>'));
      el.innerHTML = parts.join('');
    }).catch(() => { /* no edition yet: the page keeps its "first edition" note */ });
  }

  // Calendar page: a horizontal 7-column weekly-plan grid. Looks like a
  // printable weekly planner — title on top, 7 day columns with events as
  // little sticky notes stacked inside each column.
  function initPlanner(opts) {
    const host = document.getElementById(opts.listId);
    if (!host) return;
    const days = opts.days || 7;
    const perDay = opts.perDay || 50;
    getJson('data/events.json').then(d => {
      const ev = upcoming(d);
      const today = new Date();
      const todayKey = dayKey(today);
      const buckets = [];
      for (let i = 0; i < days; i++) {
        const dt = new Date(today.getTime() + i * 86400000);
        const k = dayKey(dt);
        const parts = nyParts(dt);
        buckets.push({
          key: k, slug: 'd' + i,
          dayNum: parts.day, weekday: parts.weekday, month: parts.month,
          isToday: k === todayKey, events: []
        });
      }
      ev.forEach(e => {
        const k = dayKey(e.s);
        const b = buckets.find(x => x.key === k);
        if (b) b.events.push(e);
      });

      const cols = buckets.map(b => {
        const cls = ['plan-col'];
        if (b.isToday) cls.push('today');
        const head = '<div class="plan-col-head">' +
          '<div class="plan-col-dow">' + esc(b.weekday.toLowerCase()) + '</div>' +
          '<div class="plan-col-date">' + esc(b.month) + ' ' + esc(b.dayNum) + '</div>' +
          (b.isToday ? '<div class="plan-col-today-tag">TODAY</div>' : '') +
          '</div>';
        const evs = b.events.slice(0, perDay).map(e => planEvent(e)).join('')
          || '<div class="plan-col-empty">—</div>';
        return '<div class="' + cls.join(' ') + '">' + head +
          '<div class="plan-col-events">' + evs + '</div></div>';
      }).join('');

      host.innerHTML = '<div class="weekly-plan">' +
        '<h2 class="weekly-plan-title">weekly plan</h2>' +
        '<div class="weekly-plan-wrap"><div class="weekly-plan-grid">' + cols + '</div></div>' +
        '</div>';
    }).catch(() => emptyNote(host, "Couldn't load events just now."));
  }

  function planEvent(e) {
    const url = safeUrl(e.url);
    const t = timeLabel(e.s);
    const name = url
      ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(e.name) + '</a>'
      : esc(e.name);
    const venue = e.venue ? '<div class="plan-ev-venue">' + esc(e.venue) + '</div>' : '';
    const links = [];
    if (url) links.push('<a class="plan-ev-tix" href="' + esc(url) + '" target="_blank" rel="noopener">Tix</a>');
    links.push('<a href="' + esc(googleUrl(e)) + '" target="_blank" rel="noopener">+ Google</a>');
    links.push('<a href="' + esc(icsHref(e)) + '" download="event.ics">+ Apple</a>');
    return '<div class="plan-ev">' +
      '<div class="plan-ev-time">' + esc(t) + '</div>' +
      '<div class="plan-ev-name">' + name + '</div>' +
      venue +
      '<div class="plan-ev-links">' + links.join('') + '</div>' +
      '</div>';
  }

  window.RobotEvents = { initList, initWeek, initCalendar, initPlanner, initRoundup };
})();
