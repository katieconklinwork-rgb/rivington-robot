// Rivington Robot: top-of-page briefing — weather, sunset, trash and a mood line.
// Weather + sunset come from Open-Meteo (free, no key). Trash is computed from
// a schedule, because NYC DSNY has no public per-address live feed. Subway
// status has no reliable key-free API from a static page, so the briefing just
// names the house lines and links out to the live MTA page.
(function () {
  const LAT = 40.72203, LNG = -73.99198, TZ = 'America/New_York';

  // Typical Manhattan CB3 (Lower East Side) residential schedule.
  // 0=Sun … 6=Sat. Collection happens in the AM; residents set out after 6pm
  // the night before. Numbers below are COLLECTION days.
  const REFUSE_DAYS = [1, 3, 5];       // Mon, Wed, Fri
  const RECYCLING_DAYS = [4];           // Thursday (paper + metal/glass/plastic)
  const DAY_NAMES = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];

  function nowInNY() {
    const now = new Date();
    const p = {};
    new Intl.DateTimeFormat('en-US', { timeZone: TZ, weekday: 'short', hour: 'numeric', hour12: false })
      .formatToParts(now).forEach(x => p[x.type] = x.value);
    const map = { Sun:0, Mon:1, Tue:2, Wed:3, Thu:4, Fri:5, Sat:6 };
    return { dow: map[p.weekday], hour: parseInt(p.hour, 10) };
  }
  function nextDayIn(days, startDow) {
    for (let i = 0; i < 7; i++) { const d = (startDow + i) % 7; if (days.includes(d)) return { d, in: i }; }
    return null;
  }
  function fmtTimeIso(iso) {
    const p = {};
    new Intl.DateTimeFormat('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit', hour12: true })
      .formatToParts(new Date(iso)).forEach(x => p[x.type] = x.value);
    return p.hour + ':' + p.minute + p.dayPeriod.toLowerCase();
  }

  function setTrash(mainEl, subEl) {
    const { dow, hour } = nowInNY();
    const tomorrow = (dow + 1) % 7;
    const refuseTomorrow = REFUSE_DAYS.includes(tomorrow);
    const recyclingTomorrow = RECYCLING_DAYS.includes(tomorrow);

    if (refuseTomorrow || recyclingTomorrow) {
      const kind = recyclingTomorrow && !refuseTomorrow ? 'recycling' : 'trash';
      if (hour >= 18) { mainEl.textContent = kind + ' out now'; subEl.textContent = 'collected tomorrow AM'; }
      else            { mainEl.textContent = kind + ' out tonight'; subEl.textContent = 'put out after 6pm'; }
      return;
    }

    // Nothing goes out tonight — show when the next put-out night is.
    // "Night N" means the evening of day N, so collection is on day N+1.
    const nextRefuseCollect = nextDayIn(REFUSE_DAYS, (dow + 1) % 7);
    const nextRecyCollect   = nextDayIn(RECYCLING_DAYS, (dow + 1) % 7);
    const refuseNightOffset = (nextRefuseCollect.in + 0); // nights from today, where 0 = tonight
    const recyNightOffset   = nextRecyCollect ? nextRecyCollect.in + 0 : 999;
    const next = refuseNightOffset <= recyNightOffset
      ? { kind: 'trash', nights: refuseNightOffset, dayIdx: nextRefuseCollect.d }
      : { kind: 'recycling', nights: recyNightOffset, dayIdx: nextRecyCollect.d };

    const nightLabel =
      next.nights === 0 ? 'tonight after 6pm'
      : next.nights === 1 ? 'tomorrow night'
      : DAY_NAMES[(dow + next.nights) % 7] + ' night';
    mainEl.textContent = 'no pickup tonight';
    subEl.textContent = 'next ' + next.kind + ' out ' + nightLabel;
  }

  // Open-Meteo weather codes — kept small and friendly.
  const WX = {
    0:['Clear','☀️'], 1:['Mostly clear','🌤️'], 2:['Partly cloudy','⛅'], 3:['Cloudy','☁️'],
    45:['Fog','🌫️'], 48:['Freezing fog','🌫️'],
    51:['Light drizzle','🌦️'], 53:['Drizzle','🌦️'], 55:['Heavy drizzle','🌧️'],
    61:['Light rain','🌦️'], 63:['Rain','🌧️'], 65:['Heavy rain','🌧️'],
    66:['Freezing rain','🌧️'], 67:['Freezing rain','🌧️'],
    71:['Light snow','🌨️'], 73:['Snow','🌨️'], 75:['Heavy snow','❄️'], 77:['Snow grains','🌨️'],
    80:['Showers','🌦️'], 81:['Showers','🌧️'], 82:['Heavy showers','⛈️'],
    85:['Snow showers','🌨️'], 86:['Heavy snow','❄️'],
    95:['Thunderstorms','⛈️'], 96:['Thunderstorms','⛈️'], 99:['Thunderstorms','⛈️']
  };
  function initApartment() {
    const trashM = document.getElementById('ap-trash');
    const trashS = document.getElementById('ap-trash-sub');
    if (trashM && trashS) setTrash(trashM, trashS);
  }

  function init() {
    const tempEl   = document.getElementById('b-temp');
    const feelsEl  = document.getElementById('b-feels');
    const iconEl   = document.getElementById('b-wx-icon');
    const sunsetEl = document.getElementById('b-sunset');
    const sunsubEl = document.getElementById('b-sunset-sub');

    const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + LAT + '&longitude=' + LNG
      + '&current=temperature_2m,weather_code,apparent_temperature,is_day'
      + '&daily=sunrise,sunset,temperature_2m_max,temperature_2m_min,precipitation_probability_max'
      + '&temperature_unit=fahrenheit&timezone=America%2FNew_York&forecast_days=1';

    fetch(url).then(r => { if (!r.ok) throw new Error('weather ' + r.status); return r.json(); })
      .then(d => {
        const t = Math.round(d.current.temperature_2m);
        const feels = Math.round(d.current.apparent_temperature);
        const code = d.current.weather_code;
        const [desc, icon] = WX[code] || ['', '🌡️'];
        if (iconEl) iconEl.textContent = icon;
        if (tempEl) tempEl.textContent = t + '°';
        const bits = [];
        if (desc) bits.push(desc);
        if (Math.abs(feels - t) >= 3) bits.push('feels ' + feels + '°');
        const pop = d.daily.precipitation_probability_max && d.daily.precipitation_probability_max[0];
        if (pop >= 40) bits.push(pop + '% rain');
        const hi = Math.round(d.daily.temperature_2m_max[0]);
        const lo = Math.round(d.daily.temperature_2m_min[0]);
        bits.push('H' + hi + '° L' + lo + '°');
        if (feelsEl) feelsEl.textContent = bits.join(' · ');

        if (sunsetEl) sunsetEl.textContent = fmtTimeIso(d.daily.sunset[0]);
        if (sunsubEl) {
          const setMs = new Date(d.daily.sunset[0]).getTime();
          const diffMin = Math.round((setMs - Date.now()) / 60000);
          if (diffMin > 0 && diffMin < 60 * 6) {
            sunsubEl.textContent = 'in ' + (diffMin < 60 ? diffMin + ' min' : Math.round(diffMin / 60) + ' hr');
          } else if (diffMin < 0) {
            sunsubEl.textContent = 'already down';
          } else {
            sunsubEl.textContent = 'sunset';
          }
        }
      })
      .catch(() => {
        if (feelsEl) feelsEl.textContent = 'weather offline';
      });
  }

  window.RobotBriefing = { init, initApartment };
})();
