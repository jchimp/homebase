const hearth = (() => {
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
    localStorage.setItem('hearth-mode', mode);
    updateModeIcon(mode);
  }

  function toggleMode() {
    applyMode(currentMode() === 'dark' ? 'light' : 'dark');
  }

  // Settings dropdown: 'system' clears the per-browser override (back to OS).
  function setMode(mode) {
    if (mode === 'system') {
      document.documentElement.removeAttribute('data-mode');
      localStorage.removeItem('hearth-mode');
      updateModeIcon(currentMode());
    } else {
      applyMode(mode);
    }
  }

  // Live preview for the Settings theme dropdown; persists per browser.
  function applyTheme(theme) {
    const link = document.getElementById('theme-css');
    if (link) link.href = `/static/css/themes/${theme}.css`;
    localStorage.setItem('hearth-theme', theme);
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
    initMode();
  });

  return { search, toggleMode, setMode, applyTheme };
})();
