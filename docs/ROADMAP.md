# ROADMAP — Homebase

Phased so each step ends with something runnable. **P0–P2 are v1.** P3–P4 are
post-v1 and optional.

---

## P0 — Static render from data ✓
*Goal: prove the renderer and the look, no editing yet.*

- [x] Project scaffold (FastAPI, Jinja2, Docker, `.env`).
- [x] `store.py`: load/validate `dashboard.json` (Pydantic), atomic save.
- [x] Seed a sample `dashboard.json` (a few apps + bookmark groups).
- [x] `render.py`: build the render-context dict (greeting, date, items).
- [x] `templates/base.html` + `layouts/flame.html` + partials
      (`app_card`, `bookmark_group`).
- [x] One polished theme (`themes/midnight.css`) using CSS variables.
- [x] `GET /` renders the Flame layout from the seed file.

---

## P1 — Auth + CRUD ✓
*Goal: make it editable.*

- [x] `auth.py`: bcrypt creds from `.env`, signed session cookie.
- [x] `cli.py set-password`.
- [x] Login / logout; guard `/admin/*`.
- [x] Admin home + Apps CRUD (name, subtitle, url).
- [x] Bookmarks CRUD (groups + links, with ordering).
- [x] Simple reorder controls (up/down buttons posting to move endpoint).
- [x] HTMX (`/static/js/htmx.min.js`) wired to all admin forms — inline saves,
      delete-without-reload, icon picker streaming results.

---

## P2 — Icons, weather, search, settings, export ✓ *(v1 complete)*
*Goal: the features that make it nice and portable.*

- [x] Settings page: title, theme, layout, visibility, icon_style + color,
      search engine, weather city + units, export path + auto toggle.
- [x] `icons.py`:
  - [x] Iconify search proxy (`/api/icons/search`).
  - [x] Favicon resolution + SVG fetch.
  - [x] **SVG sanitization** (lxml strip: `script`, `on*` attrs, `foreignObject`,
        `use`, `javascript:` URIs) — runs on every inbound SVG before storage.
  - [x] Recolor logic (monotone `?color=` / `currentColor`; CSS-mask fallback).
  - [x] Store resolved icon inline in the item.
- [x] Icon picker UI: search box, live tinted preview grid, favicon button,
      color-logo option, custom upload/paste.
- [x] Weather: Open-Meteo geocode on save; client-side current-conditions fetch;
      `weather` partial with icon mapping from `weather_code`.
- [x] Search: `search` partial with client-side redirect.
- [x] Export: `render(inline=True)`; auto-write on save + `/export/download`
      button; verify the file opens standalone with working weather + search.

---

## P3 — Polish (optional)
- [x] A second theme or two (light + Nord accent variant).
- [x] Drag-to-reorder (SortableJS) replacing position buttons.
- [x] Import/export of `dashboard.json` (backup / restore / repo round-trip).
- [ ] Icon cache to local `data/icons/` + optional self-hosted Iconify pointer.
- [ ] Keyboard focus on the search box; small accessibility pass.

---

## P4 — Stretch (only if wanted)
- [ ] A second **layout** (e.g. single-column or sidebar) — one template file
      against the existing contract.
- [ ] Optional up/down **status dots** per item (server-side ping; its own
      concern — CORS/mixed-content handled in the backend, not the browser).
- [ ] Per-item "visible when logged out" flag for sensitive internal hosts.

---

## Risk notes
- **Highest-touch piece:** the icon picker + consistency engine (P2). Build the
  recolor/mask path early and test it against a *color* logo, a *monotone* glyph,
  and a *raster* favicon — those three cases prove the whole approach.
- **Keep the renderer single-path.** The moment export and live diverge into two
  code paths, the design is broken. Export is just `inline=True`.
- **Resist scope.** Every "wouldn't it be cool if…" goes to P4 or `PRD.md`
  non-goals, not into v1.
