# PRD — Homebase

## 1. Problem

Self-hosted dashboards today force a bad trade: the polished ones (Homarr, Dashy)
are heavy and do far more than needed, while the lean ones (Flame, Homepage,
Homer) lean on hand-edited YAML config that you edit and rebuild. The author
wants a *fast, frictionless* start page for a home lab and a small business:
log in, add a link, get a nice icon, done. Plus the ability to take the whole
thing with them as a portable file.

## 2. Goals

- A single, clean, modern dashboard page: **Applications** grid + grouped
  **Bookmarks** + weather + search, modeled on the Flame layout.
- Add/edit links entirely through a UI. No config-file editing in normal use.
- Icon selection that's easy *and* produces a visually consistent board.
- A weather widget configured by city name on the admin panel.
- A search box configured to any search engine on the admin panel.
- **Export the dashboard as one self-contained static HTML file**, written to a
  known server path on every save *and* available via a download button.
- Swappable themes now; swappable layouts later — without touching data.

## 3. Non-goals (explicitly out)

- Multi-user, roles, permissions, SSO.
- Hand-edited YAML/config workflow.
- Service integrations / live stats on tiles / Docker auto-discovery.
- Multiple dashboard pages / tabs.
- A drag-and-drop visual canvas or resizable tiles.
- Any client-side framework (React/Vue/Svelte) or build step for the view.

## 4. User

One **admin**. Logs in via a corner link, edits everything, logs out. Optionally
the dashboard is public to view (logged-out visitors see it) or private
(login required to view). Default: public to view, login to edit.

## 5. Features & acceptance criteria

### 5.1 Dashboard view
- Renders greeting (time-aware), date, weather (top-right), Applications grid,
  Bookmarks groups — from `dashboard.json`.
- Loads as static HTML; no framework; first paint is immediate.
- Respects the `visibility` setting (public vs login-required).
- **Done when:** the page matches the Flame layout's information structure and
  renders entirely from the JSON file.

### 5.2 Admin auth
- Corner login link → password form → session.
- Single admin; username + bcrypt hash + session secret from `.env`.
- `set-password` CLI generates the hash.
- **Done when:** unauthenticated users cannot reach `/admin/*`, and a valid login
  grants an editing session.

### 5.3 Applications (CRUD)
- Add/edit/delete an app: name, subtitle (e.g. host/URL shown under the name),
  URL, icon. Reorder via simple position controls.
- **Done when:** apps created in the UI appear in the grid in the chosen order.

### 5.4 Bookmarks (CRUD)
- Bookmarks are organized into named **groups** (Cloud, Media, etc., per the
  screenshot). Add/edit/delete groups and the links within them, with ordering.
- **Done when:** grouped bookmarks render like the screenshot's lower section.

### 5.5 Icon selection — *consistency is a first-class requirement*
The point isn't "let me pick any icon"; it's "produce a clean board with a
consistent icon theme." The picker offers, in priority order:

1. **Search by name** (primary): one box, queries the Iconify API, which spans
   many icon sets (Simple Icons for app/brand marks, Tabler/Lucide/Material for
   generic glyphs). Search by **app name** ("plex", "nextcloud") or **glyph
   name** ("server", "lock", "cloud").
2. **Live preview grid**: each match is rendered at the dashboard's tile size and
   **already tinted to the current icon style**, so what you preview is what the
   board will look like. You can't accidentally pick something off-theme without
   seeing it.
3. **Grab favicon**: one click resolves the link's favicon server-side
   (convenience; best used in color mode).
4. **App logo (color)**: optional full-color brand logo from selfh.st /
   dashboard-icons, for when you *want* the colorful look.
5. **Custom**: paste SVG, an image URL, or upload a file.

**Global consistency control:** an `icon_style` setting — `monochrome` (default,
the Flame look: every icon recolored to one theme accent regardless of source)
or `color`. Monochrome is enforced at render time so the *whole board* matches.

- **Done when:** an admin can find an icon by typing a name, preview it tinted to
  the theme, save it, and the resulting board reads as one consistent icon set.

### 5.6 Weather widget
- Configured by **city name** in admin (e.g. "Polson, MT"). The app geocodes it
  once via Open-Meteo and stores coordinates. Units selectable (°F/°C).
- The widget fetches current conditions **client-side** from Open-Meteo (keyless).
- **Done when:** entering a city shows live current temperature + conditions, and
  it keeps working in the exported static file.

### 5.7 Search widget
- A text box that submits to a configurable engine URL set in admin
  (e.g. DuckDuckGo, Google, a self-hosted SearXNG). Purely client-side redirect.
- **Done when:** typing a query and submitting opens the configured engine.

### 5.8 Settings (admin panel)
Page title, search engine URL + placeholder, weather city + units, `icon_style` +
icon color, theme, layout, visibility, and export path / auto-export toggle.

### 5.9 Static export
- On every save, render the current dashboard with **everything inlined** (CSS,
  JS, icon SVGs) to a single `index.html` at the configured server path.
- A **Download** button produces the same file on demand.
- The exported file is fully functional standalone: weather fetches live
  (keyless, CORS-friendly), search redirects, icons are inline.
- **Done when:** the exported file opens directly in a browser with no server and
  looks and behaves like the live dashboard.

### 5.10 Theming & layout
- **Theme** = a CSS-variables file; switching themes never changes structure.
- **Layout** = a Jinja template consuming the shared render-context; `flame` ships
  first. Additional layouts can be added later as single template files.
- **Done when:** changing the theme restyles the board, and the architecture
  supports dropping in a second layout without a data change.

## 6. v1 definition of done

Phases P0–P2 in `ROADMAP.md`: a logged-in admin can build the board (apps +
bookmarks + icons), set weather/search/title, view it publicly, and export a
working standalone HTML file. Theming and a clean default look included; extra
layouts and any health-check features are explicitly post-v1.
