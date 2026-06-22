# CLAUDE.md — Homebase

> **Homebase** — a self-hosted start page / dashboard.

This file orients any developer or AI assistant working in this repo. Read it
first, then `PRD.md` for *what* we're building, `ARCHITECTURE.md` for *how*, and
`ROADMAP.md` for *in what order*.

---

## What this is

A small, single-admin self-hosted dashboard / start page. It displays a fixed
layout — an **Applications** grid up top and grouped **Bookmarks** below
(modeled on the Flame dashboard) — plus a weather widget and a web-search box.
The admin logs in to add links and pick icons through a UI; everyone else just
sees a fast, clean page.

Its signature feature: **export the entire dashboard as a single, self-contained
static HTML file** that works standalone (weather and search included), so it can
be synced to a local docs folder or committed to a repo.

## Core philosophy (the reason this app exists)

The whole point is to be the dashboard that *isn't* a chore. Existing tools were
rejected for being either too heavy (Homarr/Dashy) or driven by hand-edited YAML
that you edit-and-rebuild (Flame/Homepage/Homer). Homebase is deliberately tiny.

**Non-negotiables — do not violate these without an explicit decision:**

- **One user.** No multi-user, no roles, no SSO. A single admin with a password.
- **No hand-edited config files as the workflow.** Data lives in one JSON file
  that the *UI* owns. Users never open it to make changes.
- **The render is static.** The dashboard view is plain HTML + a little vanilla
  JS. No SPA, no client framework, no hydration. It must load instantly.
- **The live page and the export are the same renderer.** Never build a second
  code path for export. Export = render the current view with everything inlined.
- **No feature creep.** No widget marketplace, no service integrations, no
  Docker auto-discovery, no multiple pages. If a feature isn't in `PRD.md`, it's
  out until we put it there.

## Stack

- **Backend:** Python, FastAPI, Jinja2. Single Docker container.
- **Data:** one `dashboard.json` file (see `ARCHITECTURE.md`). No database, no ORM.
- **Frontend:** server-rendered Jinja templates + CSS custom properties +
  vanilla JS for the three dynamic bits (icon picker, weather fetch, search).
- **Auth:** single admin; bcrypt password hash + signed session cookie. Creds in
  `.env`.
- **External services (all keyless):** Iconify API (icon search/render),
  Open-Meteo (weather + geocoding), jsDelivr CDNs (selfh.st / dashboard-icons logos).

## Repo layout (target)

```
app/
  main.py            # FastAPI app, routes
  auth.py            # login/session
  store.py           # load/save dashboard.json (atomic writes)
  icons.py           # icon search proxy, favicon resolution, recolor
  weather.py         # Open-Meteo geocoding
  render.py          # build render-context, render live OR inline-export
  cli.py             # `set-password`, etc.
  templates/
    base.html        # skeleton with named blocks
    layouts/
      icons.html     # layout #1 (default)
    partials/
      app_card.html
      bookmark_group.html
      weather.html
      search.html
    admin/           # admin UI templates
  static/
    css/themes/      # one CSS-variables file per theme
    js/
data/
  dashboard.json     # single source of truth (mounted volume)
  icons/             # optional local icon cache
  export/index.html  # auto-written export target
.env                 # admin creds + session secret
Dockerfile
docker-compose.yml
```

## Key conventions

- **`dashboard.json` is the single source of truth.** All reads/writes go
  through `store.py`, which writes atomically (temp file + rename).
- **Icons are stored inline as resolved SVG** inside each item. This keeps the
  JSON self-contained and makes export trivial. (See icon flow in `ARCHITECTURE.md`.)
- **Every layout template receives the identical render-context dict.** Layout is
  pure presentation; the data model knows nothing about layout. Adding a layout =
  adding one template file, never a data migration.
- **Theme = a CSS-variables file.** Icon consistency is enforced at render time
  via the global `icon_style` setting (monochrome | color).

## Running

```bash
# dev
uv pip install -r requirements.txt   # or pip
uvicorn app.main:app --reload

# docker
docker compose up -d
```

On **first run** there is no admin account: visiting `/login` redirects to `/setup`,
where you create the admin username + password through the browser. Credentials and an
auto-generated session secret are stored in `data/auth.json` (on the data volume).
`python -m app.cli set-password` is now a **reset** that rewrites those credentials
(use `docker compose exec homebase python -m app.cli set-password` for a container).
Setting `ADMIN_PASSWORD_HASH` / `ADMIN_USERNAME` / `SESSION_SECRET` in the environment
still overrides the file.

Dashboard at `/`, login at `/login`, admin at `/admin`, first-run setup at `/setup`.

## Where to put things

- New endpoint → `app/main.py` (+ helper module if non-trivial).
- New icon source → `app/icons.py` (keep the picker UI source-agnostic).
- New layout → `templates/layouts/<name>.html` + register the name; no other code.
- New theme → `static/css/themes/<name>.css` using the documented variables.
