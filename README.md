# Homebase

A tiny, self-hosted start page / dashboard. An **Applications** grid up top and
grouped **Bookmarks** below (modeled on [Flame](https://github.com/pawelmalak/flame)),
plus a weather widget and a web-search box. A single admin logs in to add links and
pick icons through a UI; everyone else just sees a fast, clean page.

Its signature feature: **export the entire dashboard as a single, self-contained
static HTML file** — weather and search included — that works with no server, so it
can be synced to a docs folder or committed to a repo.

![Homebase dashboard](docs/images/homebase-screenshot.png)

## Quick start

### Docker (recommended)

```bash
docker compose up -d
```

Then open <http://localhost:8080>. On first run there is no admin account — visiting
`/login` redirects to `/setup`, where you create the admin username and password in
the browser. Credentials and an auto-generated session secret are written to
`data/auth.json` on the mounted volume.

### Local (dev)

```bash
pip install -r requirements.txt          # or: uv pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Configuration

All environment variables are **optional overrides** — copy `.env.example` to `.env`
only if you need them. By default everything is configured through the admin UI and writen to disk.

| Variable              | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `DATA_PATH`           | Path to `dashboard.json` (default `/data/dashboard.json`).      |
| `ADMIN_USERNAME`      | Override the web-created admin username.                        |
| `ADMIN_PASSWORD_HASH` | Override the web-created bcrypt password hash.                  |
| `SESSION_SECRET`      | Cookie signing secret (auto-generated into `auth.json` if unset).|

When set, these env vars take precedence over the web-created credentials in
`data/auth.json`.

### Resetting the admin password

`set-password` rewrites the stored credentials:

```bash
# local
python -m app.cli set-password

# container
docker compose exec homebase python -m app.cli set-password
```
## Features

- **Applications grid** and grouped **Bookmarks**, edited entirely through the UI
  (drag-to-reorder, inline saves via HTMX).
- **Icon picker with consistency built in** — search Iconify by app or glyph name,
  grab a favicon, or use a full-color brand logo. A global `icon_style`
  (`monochrome` | `color`) is enforced at render time so the whole board reads as one
  set. Icons are stored inline as sanitized SVG, so the JSON is self-contained.
- **Weather** widget configured by city name (geocoded once via Open-Meteo, fetched
  live client-side) and a **search** box pointed at any engine URL — both keyless and
  client-side, so they keep working in the export.
- **Themes** (`nord`, `slate`, `sage`) as CSS-variable files, with independent
  light/dark mode. **Layouts** (`icons`, `detailed`) as single Jinja templates.
- **Static export** to a single `index.html`, auto-written on every save and available
  via a download button.

## Backup

Everything lives under `data/` (the mounted volume): `dashboard.json`, `auth.json`,
and `export/index.html`.
You can also just export a copy of the HTML and call it a day, it's not perfect, but it works.

## Routes

| Path      | Purpose                                          |
|-----------|--------------------------------------------------|
| `/`       | Dashboard view (public or login-required).       |
| `/login`  | Admin login (redirects to `/setup` on first run).|
| `/setup`  | First-run admin account creation.                |
| `/admin`  | Admin panel — apps, bookmarks, settings, export. |
| `/export/download` | Download the standalone HTML export.    |
| `/healthz`| Liveness check.                                  |
