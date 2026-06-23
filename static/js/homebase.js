const homebase = (() => {
  function search(e) {
    e.preventDefault();
    const input = document.getElementById('search-input');
    const q = input?.value.trim();
    const engine = input?.dataset.engine;
    if (q && engine) window.location.href = engine + encodeURIComponent(q);
  }

  const WMO = {
    0:  ['Clear sky',           '☀️'],
    1:  ['Mainly clear',        '🌤️'],
    2:  ['Partly cloudy',       '⛅'],
    3:  ['Overcast',            '☁️'],
    45: ['Fog',                 '🌫️'],
    48: ['Icy fog',             '🌫️'],
    51: ['Light drizzle',       '🌦️'],
    53: ['Drizzle',             '🌦️'],
    55: ['Heavy drizzle',       '🌧️'],
    61: ['Slight rain',         '🌧️'],
    63: ['Rain',                '🌧️'],
    65: ['Heavy rain',          '🌧️'],
    71: ['Slight snow',         '❄️'],
    73: ['Snow',                '❄️'],
    75: ['Heavy snow',          '❄️'],
    77: ['Snow grains',         '🌨️'],
    80: ['Showers',             '🌦️'],
    81: ['Rain showers',        '🌧️'],
    82: ['Violent showers',     '⛈️'],
    85: ['Snow showers',        '🌨️'],
    86: ['Heavy snow showers',  '🌨️'],
    95: ['Thunderstorm',        '⛈️'],
    96: ['Thunderstorm w/ hail','⛈️'],
    99: ['Thunderstorm w/ hail','⛈️'],
  };

  function loadWeather() {
    const w = document.getElementById('weather-widget');
    if (!w) return;
    const { lat, lon, units } = w.dataset;
    if (!lat || !lon) return;

    const url = `https://api.open-meteo.com/v1/forecast`
      + `?latitude=${lat}&longitude=${lon}`
      + `&current=temperature_2m,weather_code`
      + `&temperature_unit=${units}`
      + `&forecast_days=1`;

    fetch(url)
      .then(r => r.json())
      .then(d => {
        const cur = d.current;
        const [desc, icon] = WMO[cur.weather_code] ?? ['Unknown', '🌡️'];
        const unit = units === 'fahrenheit' ? '°F' : '°C';
        document.getElementById('weather-icon').textContent = icon;
        document.getElementById('weather-temp').textContent =
          Math.round(cur.temperature_2m) + unit;
        document.getElementById('weather-desc').textContent = desc;
      })
      .catch(() => {
        const el = document.getElementById('weather-desc');
        if (el) el.textContent = 'unavailable';
      });
  }

  // ── News ──────────────────────────────────────────────

  function relativeTime(tsSeconds) {
    if (!tsSeconds) return '';
    const secs = Math.floor(Date.now() / 1000) - tsSeconds;
    if (secs < 60) return 'just now';
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  function paintNewsTimes(root) {
    (root || document).querySelectorAll('.news__time[data-ts]').forEach(el => {
      el.textContent = relativeTime(parseInt(el.dataset.ts, 10));
    });
  }

  function buildNewsItem(item) {
    const li = document.createElement('li');
    li.className = 'news__item';

    if (item.thumbnail) {
      const img = document.createElement('img');
      img.className = 'news__thumb';
      img.src = item.thumbnail;
      img.alt = '';
      img.loading = 'lazy';
      img.referrerPolicy = 'no-referrer';
      li.append(img);
    }

    const body = document.createElement('div');
    body.className = 'news__body';

    const a = document.createElement('a');
    a.className = 'news__title';
    a.href = item.link;
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = item.title;

    const meta = document.createElement('span');
    meta.className = 'news__meta';
    const time = document.createElement('span');
    time.className = 'news__time';
    time.dataset.ts = item.published;
    time.textContent = relativeTime(item.published);
    meta.append(`${item.source} · `, time);

    body.append(a, meta);
    li.append(body);
    return li;
  }

  function buildColumn(items) {
    const ul = document.createElement('ul');
    ul.className = 'news__list';
    ul.append(...items.map(buildNewsItem));
    return ul;
  }

  function initNews() {
    const container = document.getElementById('news-columns');
    if (!container) return;
    paintNewsTimes(container);

    const refreshMs = parseInt(container.dataset.refresh, 10);
    if (!refreshMs) return; // export snapshot: no polling

    setInterval(() => {
      fetch('/api/news')
        .then(r => r.json())
        .then(cols => {
          if (!Array.isArray(cols) || !cols.some(c => c.length)) return;
          container.replaceChildren(...cols.map(buildColumn));
        })
        .catch(() => {});
    }, refreshMs);
  }

  // ── Light/dark mode ───────────────────────────────────
  // Theme (hue family) is a server setting; light vs dark is a per-browser
  // mode that defaults to the OS preference until the user toggles it.

  function currentMode() {
    const forced = document.documentElement.getAttribute('data-mode');
    if (forced === 'light' || forced === 'dark') return forced;
    return window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark' : 'light';
  }

  function updateModeIcon(mode) {
    const icon = document.getElementById('theme-toggle-icon');
    if (icon) icon.textContent = mode === 'dark' ? '🌙' : '☀️';
  }

  function applyMode(mode) {
    document.documentElement.setAttribute('data-mode', mode);
    localStorage.setItem('homebase-mode', mode);
    updateModeIcon(mode);
    syncPanel();
  }

  function toggleMode() {
    applyMode(currentMode() === 'dark' ? 'light' : 'dark');
  }

  // Settings dropdown: 'system' clears the per-browser override (back to OS).
  function setMode(mode) {
    if (mode === 'system') {
      document.documentElement.removeAttribute('data-mode');
      localStorage.removeItem('homebase-mode');
      updateModeIcon(currentMode());
      syncPanel();
    } else {
      applyMode(mode);
    }
  }

  // ── Theme (hue family) ────────────────────────────────
  // Mirrors the KNOWN list in base.html's pre-paint bootstrap.
  const THEMES = ['nord', 'slate', 'sage'];

  // Live preview for the Settings theme dropdown and the Appearance panel;
  // persists per browser.
  function applyTheme(theme) {
    const link = document.getElementById('theme-css');
    if (link) link.href = `/static/css/themes/${theme}.css`;
    localStorage.setItem('homebase-theme', theme);
  }

  function currentTheme() {
    const stored = localStorage.getItem('homebase-theme');
    if (THEMES.includes(stored)) return stored;
    // Fall back to whatever the server rendered into the stylesheet href.
    const link = document.getElementById('theme-css');
    const match = link && link.getAttribute('href').match(/themes\/([^/]+)\.css/);
    return (match && THEMES.includes(match[1])) ? match[1] : THEMES[0];
  }

  function selectTheme(theme) {
    applyTheme(theme);
    syncPanel();
  }

  // ── Accent (client-side override) ─────────────────────
  // Retints --accent and its two derived vars into #accent-client, mirroring
  // accent_override_css() in app/render.py. Persists per browser; "Default"
  // clears it and falls back to the server/theme accent.

  function accentRule(hex) {
    const h = hex.replace('#', '');
    if (h.length !== 6) return '';
    const r = parseInt(h.slice(0, 2), 16),
          g = parseInt(h.slice(2, 4), 16),
          b = parseInt(h.slice(4, 6), 16);
    return `:root{--accent:#${h};--accent-dim:rgba(${r},${g},${b},0.12);`
         + `--border-focus:rgba(${r},${g},${b},0.5);}`;
  }

  function selectAccent(hex) {
    localStorage.setItem('homebase-accent', hex);
    const el = document.getElementById('accent-client');
    if (el) el.textContent = accentRule(hex);
    syncPanel();
  }

  function clearAccent() {
    localStorage.removeItem('homebase-accent');
    const el = document.getElementById('accent-client');
    if (el) el.textContent = '';
    syncPanel();
  }

  // ── Appearance panel ──────────────────────────────────

  function syncPanel() {
    const panel = document.getElementById('appearance-panel');
    if (!panel) return;
    const mode = localStorage.getItem('homebase-mode') || 'system';
    panel.querySelectorAll('#mode-seg button').forEach((b) =>
      b.classList.toggle('is-active', b.dataset.mode === mode));
    const theme = currentTheme();
    panel.querySelectorAll('.theme-list__item').forEach((b) =>
      b.classList.toggle('is-active', b.dataset.theme === theme));
    const accent = (localStorage.getItem('homebase-accent') || '').toLowerCase();
    panel.querySelectorAll('.accent-swatch[data-accent]').forEach((b) =>
      b.classList.toggle('is-active', b.dataset.accent.toLowerCase() === accent));
    const custom = document.getElementById('accent-custom');
    if (custom && accent) custom.value = accent;
  }

  function closePanel() {
    const panel = document.getElementById('appearance-panel');
    const btn = document.getElementById('appearance-btn');
    if (panel) panel.hidden = true;
    if (btn) btn.setAttribute('aria-expanded', 'false');
    document.removeEventListener('click', onDocClick, true);
    document.removeEventListener('keydown', onKeydown);
  }

  function onDocClick(e) {
    if (!e.target.closest('.appearance')) closePanel();
  }

  function onKeydown(e) {
    if (e.key === 'Escape') closePanel();
  }

  function togglePanel() {
    const panel = document.getElementById('appearance-panel');
    const btn = document.getElementById('appearance-btn');
    if (!panel) return;
    if (panel.hidden) {
      syncPanel();
      panel.hidden = false;
      if (btn) btn.setAttribute('aria-expanded', 'true');
      // Defer so this opening click doesn't immediately close the panel.
      setTimeout(() => {
        document.addEventListener('click', onDocClick, true);
        document.addEventListener('keydown', onKeydown);
      }, 0);
    } else {
      closePanel();
    }
  }

  function initMode() {
    updateModeIcon(currentMode());
    // Keep the icon in sync with the OS when the user hasn't overridden.
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!document.documentElement.getAttribute('data-mode')) {
        updateModeIcon(currentMode());
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadWeather();
    initNews();
    initMode();
  });

  return {
    search, toggleMode, setMode, applyTheme,
    togglePanel, selectTheme, selectAccent, clearAccent,
  };
})();
