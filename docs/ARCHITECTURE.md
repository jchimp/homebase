# ARCHITECTURE — Homebase

## 1. Shape of the system

Three layers, one container:

1. **Store** — `dashboard.json` on a mounted volume, the single source of truth.
2. **Renderer** — turns the store into a render-context dict, then into HTML.
   Used both for the live view *and* the export (inline mode). One code path.
3. **Admin layer** — auth + CRUD forms (HTMX-enhanced; no full-page reloads) that mutate the store and trigger export.

```
            ┌──────────────── FastAPI ────────────────┐
browser ──▶ │  / (view)        → render(context, live) │ ──▶ HTML
            │  /admin/* (auth) → forms → store.save()   │
            │  /api/icons/*    → Iconify proxy + favicon│
            │  /admin/export   → render(context, inline)│ ──▶ data/export/index.html
            └───────────────────────────────────────────┘
                         │
                  data/dashboard.json   (atomic write)
```

The two dynamic widgets (weather, search) run **client-side** so they survive in
the exported file with no backend.

## 2. Data model — `dashboard.json`

Single file. `store.py` loads it into memory, validates with Pydantic models, and
saves atomically (write temp + `os.replace`). Icons are stored **inline as
resolved SVG** so the file is fully self-contained.

```jsonc
{
  "version": 1,
  "settings": {
    "title": "Jeremy's Dashboard",
    "theme": "nord",                // hue family -> static/css/themes/nord.css
    "layout": "icons",              // -> templates/layouts/icons.html
    "visibility": "public",         // public | private
    "icon_style": "monochrome",     // monochrome | color
    "search": {
      "enabled": true,
      "engine_url": "https://duckduckgo.com/?q=",
      "placeholder": "Search the web…"
    },
    "weather": {
      "enabled": true,
      "city": "Polson, MT",
      "latitude": 47.6935,          // filled by geocode on save
      "longitude": -114.1631,
      "units": "fahrenheit"         // fahrenheit | celsius
    },
    "export": {
      "auto_on_save": true,
      "auto_path": "/data/export/index.html"
    }
  },
  "apps": [
    {
      "id": "a1b2c3",
      "name": "Plex",
      "subtitle": "plex.example.com",
      "url": "https://plex.example.com",
      "icon": {
        "source": "iconify",        // iconify | favicon | logo | custom
        "ref": "simple-icons:plex", // prefix:name, slug, or url depending on source
        "mode": "monotone",         // monotone | color  (can this icon be recolored?)
        "svg": "<svg …>…</svg>"      // resolved, inlined; raster favicons -> data URI
      }
    }
  ],
  "bookmarks": [
    {
      "id": "g1",
      "title": "Cloud",
      "links": [
        {
          "id": "l1",
          "name": "Google Drive",
          "url": "https://drive.google.com",
          "icon": { "source": "iconify", "ref": "simple-icons:googledrive",
                    "mode": "monotone", "svg": "<svg …>…</svg>" }
        }
      ]
    }
  ]
}
```

Notes:
- `apps` is a flat, ordered grid. `bookmarks` is ordered groups, each with ordered
  links — matching the screenshot's two-section structure.
- **Order = array order.** No `position` field. Reordering rewrites the array. This
  avoids gap/renumber problems and keeps the JSON readable.
- `icon.mode` records whether the stored SVG is monochrome-capable (monotone) or a
  full-color asset; the renderer uses this to decide how to enforce `icon_style`.

## 3. Render-context contract

The **one dict every layout template receives.** Layouts are presentation only;
they may use or ignore any field, but the shape never changes. Adding a field is
backward-compatible; removing one is a breaking change to templates.

```python
{
  "settings": Settings,                # full settings object
  "greeting": "Good afternoon",        # computed from server local time
  "date_str": "Saturday, 21 June 2026",
  "apps": [                            # each item pre-rendered for the template
    {"name": str, "subtitle": str, "url": str, "icon_html": SafeString}
  ],
  "bookmark_groups": [
    {"title": str, "links": [{"name": str, "url": str, "icon_html": SafeString}]}
  ],
  "weather": {"enabled": bool, "lat": float, "lon": float, "units": str},
  "search":  {"enabled": bool, "engine_url": str, "placeholder": str},
  "icon_style": str,
  "theme": str, "layout": str,
  "inline": bool                       # True during export (see §7)
}
```

`icon_html` is produced by `render.py` so templates never deal with raw SVG or
recolor logic — they just drop it in.

## 4. Templating & theming

Jinja inheritance, no extra framework.

- `templates/base.html` — the skeleton, with named blocks: `head`, `header`,
  `apps`, `bookmarks`, `footer`.
- `templates/partials/` — reusable macros: `app_card`, `bookmark_group`,
  `weather`, `search`. Built once, shared by all layouts.
- `templates/layouts/<name>.html` — `{% extends "base.html" %}` and arranges the
  partials. `icons.html` is layout #1. The active layout name comes from settings.
- **Themes** are CSS-variable files in `static/css/themes/` (`nord`, `slate`,
  `sage`). A theme is a *hue family* defining both a light and dark palette via
  the CSS `light-dark()` function plus `color-scheme`. `--icon-color` is
  `var(--accent)`, so icons track the theme accent. Switching a theme swaps the
  stylesheet only.
- **Light/dark mode** is independent of the theme. The admin picks a default in
  Settings — `mode` = `system` | `light` | `dark` — which is baked server-side as
  `data-mode` on `<html>` (omitted for `system`, so `color-scheme: light dark`
  follows the OS). The per-page toggle button overrides it by setting
  `data-mode` on `<html>` (which flips `color-scheme`), persisted per browser in
  `localStorage` (`hearth-mode`); the Settings dropdown's `system` option clears
  that override. The baked `data-mode` also travels into exports. The
  admin `accent_override`/`accent_color` settings inject a `:root` override that
  retints `--accent` (and its derived dim/focus) across either mode.

Adding a layout later = one new template file against the existing contract. No
code, no data migration.

## 5. Icon resolution — the consistency engine

This is the feature that decides whether the board looks clean or like junk. The
guiding rule: **one global style wins, regardless of where an icon came from.**

### 5.1 Sources (picker, in priority order)
1. **Iconify search (primary).** `GET https://api.iconify.design/search?query={q}&limit=64`
   → `{ icons: ["simple-icons:plex", "mdi:server", …], total }`. Spans many sets:
   Simple Icons (brand marks), Tabler / Lucide / Material Symbols (generic glyphs).
   One box searches app names and glyph names alike.
2. **Favicon grab.** Server-side resolve from the link URL (algorithm in §5.4).
3. **Color logo.** selfh.st / dashboard-icons via jsDelivr, by slug, e.g.
   `https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/{slug}.svg`.
4. **Custom.** Paste SVG, image URL, or upload.

### 5.2 Rendering a single Iconify icon (monotone)
`GET https://api.iconify.design/{prefix}/{name}.svg?color=%239ccc65&height=32`
The `color` param recolors `currentColor`. **It only works on monotone icons** —
which is exactly the consistent-glyph case, so this is the happy path.

### 5.3 Enforcing `icon_style` at render time
`render.py` produces `icon_html` per item:

- **`color` mode:** inline the stored SVG as-is (vivid logos, native colors).
- **`monochrome` mode (default):**
  - *Monotone SVG* (Iconify glyphs, Simple Icons): set fills to `currentColor` /
    request with `?color=`, then color via CSS `--icon-color`. Crisp.
  - *Any color SVG or raster favicon:* render through a **CSS mask** so it becomes
    a single solid theme-colored silhouette. This is the universal fallback that
    guarantees uniformity even for assets the `color` param can't touch:

    ```css
    .icon--mono {
      width: var(--icon-size); height: var(--icon-size);
      background-color: var(--icon-color);
      -webkit-mask: var(--icon-src) center / contain no-repeat;
              mask: var(--icon-src) center / contain no-repeat;
    }
    ```
    where `--icon-src` is the inline SVG as a data URI.

Result: pick from any source, the board still reads as one icon set. The picker's
preview already applies this, so selection is WYSIWYG.

### 5.4 Favicon resolution (server-side, `icons.py`)
1. Fetch the page HTML; parse `<link rel="icon" | "shortcut icon" |
   "apple-touch-icon">`; choose the highest-resolution candidate.
2. Fallback to `https://{domain}/favicon.ico`.
3. (Optional, off by default for privacy) fallback to a third-party favicon
   service.
4. Store as a data URI. Flag: raster favicons don't monochrome cleanly — in
   monochrome mode they'll silhouette via the mask; prefer them in color mode.

### 5.5 Storage
On selection, the resolved SVG (or data URI) is stored inline in the item's
`icon.svg`, with `source`, `ref`, and `mode`. Nothing is fetched at view time, so
the live page and the export are local, fast, and offline-capable.

### 5.6 Optional: self-hosted Iconify
The Iconify API ships as a Docker image (`docker run -d -p 3000:3000
iconify/api`). Point `icons.py` at it via an env var to keep icon search/render
fully on your network. Not required for v1; nice for the home-lab privacy story.

### 5.7 SVG sanitization (required before inlining any external SVG)
Any SVG fetched from Iconify, favicon resolution, or user upload **must be
sanitized before being stored** in `dashboard.json`. The attack surface is XSS
via `<script>`, event attributes (`on*`), and `<foreignObject>` embedding HTML.

Sanitization runs in `icons.py` using `lxml`:

1. Parse the fetched bytes with `lxml.etree.fromstring` — reject anything that
   fails to parse as well-formed XML.
2. Walk every element. Remove nodes whose tag is in the blocklist:
   `{script, style, iframe, object, embed, foreignObject, use}` (the last two
   can pull in external resources or embed HTML).
3. Remove all attributes whose lowercased name starts with `on` (event handlers)
   or whose value contains a `javascript:` URI.
4. Re-serialize with `lxml.etree.tostring(el, encoding="unicode")`.

This is applied to **every** SVG path — Iconify responses, fetched favicons, and
custom uploads — before the result touches the data model. Templates output
`icon_html` via `markupsafe.Markup`, which bypasses Jinja auto-escaping; the
sanitization step is what makes that safe.

## 6. Weather & search (client-side)

- **Geocoding (once, on settings save):**
  `GET https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1`
  → store `latitude`/`longitude`.
- **Forecast (client-side, live):**
  `GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}`
  `&current=temperature_2m,relative_humidity_2m,weather_code&temperature_unit={units}`
  Keyless, CORS-enabled → works inside the exported static file.
- **Search:** a tiny JS handler that appends the query to `engine_url` and
  navigates. No backend.

Because both are client-side and keyless, the export needs no server to stay live.

## 7. Export renderer

Export reuses the renderer with `inline=True`:
- CSS: inline the active theme + base styles into a `<style>` block.
- JS: inline the weather + search scripts into a `<script>` block.
- Icons: already inline (stored as SVG/data-URI in the JSON).
- Output: one `index.html`.

Triggers:
- **Auto:** after any successful `store.save()`, if `export.auto_on_save`, write to
  `export.auto_path` (atomic). Your git/Syncthing watcher picks it up.
- **Manual:** `POST /admin/export` and a `GET /export/download` button return the
  same artifact.

The exported file is identical in look to the live view for the selected
layout + theme, and remains functional standalone.

## 8. Auth

- `.env`: `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` (bcrypt via passlib),
  `SESSION_SECRET`.
- `python -m app.cli set-password` prompts and writes the hash.
- Signed session cookie (Starlette `SessionMiddleware` / itsdangerous). Login sets
  it, logout clears it.
- **Deployment posture:** designed for LAN / Tailscale, or behind a reverse proxy
  with an identity provider for internet exposure. Don't expose the bespoke login
  raw to the internet — front it. (Relevant given PCI-adjacent work use.)

## 9. Endpoints

| Method | Path                     | Auth | Purpose                                  |
|-------:|--------------------------|:----:|------------------------------------------|
| GET    | `/`                      |  ~   | Dashboard view (honors `visibility`)     |
| GET    | `/login`                 |  –   | Login form                               |
| POST   | `/login`                 |  –   | Authenticate, set session                |
| POST   | `/logout`                |  ✓   | Clear session                            |
| GET    | `/admin`                 |  ✓   | Admin home                               |
| GET/POST | `/admin/apps`          |  ✓   | List / create app                        |
| POST   | `/admin/apps/{id}`       |  ✓   | Update / delete app                      |
| GET/POST | `/admin/bookmarks`     |  ✓   | List / create group or link              |
| POST   | `/admin/bookmarks/{id}`  |  ✓   | Update / delete group or link            |
| GET/POST | `/admin/settings`      |  ✓   | View / save settings (geocodes city)     |
| GET    | `/api/icons/search?q=`   |  ✓   | Proxy to Iconify search (swappable host) |
| POST   | `/api/icons/resolve`     |  ✓   | Resolve favicon / fetch + recolor SVG    |
| POST   | `/admin/export`          |  ✓   | Render + write export, return file       |
| GET    | `/export/download`       |  ✓   | Download current export                  |
| GET    | `/healthz`               |  –   | Liveness                                 |

`~` = public or login-required per `visibility`. The icon search is proxied (not
hit directly from the browser) so it can be cached and later pointed at a
self-hosted Iconify instance.

## 10. Deployment

```yaml
# docker-compose.yml
services:
  Homebase:
    build: .
    image: Homebase:latest
    ports: ["8080:8080"]
    volumes:
      - ./data:/data          # dashboard.json, icon cache, export/index.html
    env_file: .env
    restart: unless-stopped
```

Single image, one volume. Back up = copy `data/`. The exported `index.html` lives
under the same volume so a host-side sync tool can ship it to a repo or docs dir.

## 11. Security & resilience notes

- Atomic writes on `dashboard.json` (temp + replace) prevent corruption.
- Validate/normalize URLs on input; render external links with
  `rel="noopener noreferrer"`.
- Favicon/SVG fetch is server-side; sanitize fetched SVG (strip scripts/`on*`
  handlers) before inlining.
- Rate-limit `/api/icons/*` lightly; cache Iconify results.
- Keep `SESSION_SECRET` out of the image; supply via `.env`.

## 12. HTMX admin patterns

Admin forms use [htmx](https://htmx.org) loaded from a CDN or local static file.
No build step, no framework — just attributes on existing HTML elements.

**Key patterns:**

- **Inline CRUD:** forms post to the same endpoint via `hx-post`; the server
  returns the updated partial (e.g. the apps list row), which swaps in via
  `hx-swap="outerHTML"` on the target element. No page reload.
- **Delete:** a button with `hx-delete` (or `hx-post` to a `?action=delete` URL
  if the host strips non-standard methods) removes the row via
  `hx-target="closest .item-row" hx-swap="delete"`.
- **Reorder:** up/down buttons post to `/admin/apps/{id}/move?dir=up|down`;
  server rewrites the array and returns the updated list partial.
- **Icon picker:** a search `<input>` with `hx-get="/api/icons/search"
  hx-trigger="input changed delay:300ms"` streams results into a preview grid.
  Each result is a button; clicking it posts to resolve + store the icon and
  swaps the card's icon preview in place.
- **Settings save:** the settings form posts normally (full-page) since it
  triggers geocoding and export — a slight delay is acceptable there.

HTMX is included in `templates/base.html` via a `<script>` tag (either a CDN
link or `/static/js/htmx.min.js` for fully offline operation).
**Only admin templates use HTMX.** The public dashboard view has zero JS
dependencies beyond `hearth.js` (weather fetch + search redirect).
