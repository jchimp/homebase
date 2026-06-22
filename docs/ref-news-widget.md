# ref-news-widget.md — News Feed Widget (v1.5)

Add an aggregated RSS/Atom news panel. Configured entirely from the existing
**admin/settings** page. Keep it in-spirit: server-side fetch + cache, no SPA.

## Settings (extend the existing settings model)

```jsonc
"news": {
  "enabled": true,
  "max_items": 15,
  "refresh_minutes": 20,
  "feeds": [ /* defaults below */ ]
}
```

Add to the settings page: an **Enable news widget** toggle, a **Max items**
number, a **Refresh (minutes)** number, and a **Feeds** textarea (one URL per
line). The whole widget shows/hides on the `enabled` toggle.

## Default feeds (seed these)

```
https://isc.sans.edu/rssfeed.xml
https://cisa.kevintel.com/rss.xml
https://www.bleepingcomputer.com/feed/
https://www.theregister.com/security/headlines.atom
https://krebsonsecurity.com/feed/
https://www.schneier.com/feed/atom/
https://selfh.st/rss/
https://www.reddit.com/r/selfhosted/.rss
https://www.reddit.com/r/homelab/.rss
https://www.reddit.com/r/sysadmin/.rss
https://hnrss.org/frontpage
```
(CISA killed their official KEV RSS — `cisa.kevintel.com` is a mirror.)

## Backend (`app/news.py`)

- Use **feedparser**.
- A background task refreshes every `refresh_minutes`: pull all feeds, merge,
  sort by published desc, dedupe by link, trim to `max_items`.
- Cache in memory **and** persist to `data/feed_cache.json` (survives restart,
  serves instantly on boot).
- A slow/dead feed must **never block** page render — fetch with a timeout,
  catch per-feed errors, skip failures.
- Send a polite `User-Agent` header (Reddit/others rate-limit anonymous hits).
- **Sanitize** each entry's title/summary HTML before storing (escape; strip
  tags/scripts). Feed content is untrusted.

## Endpoint

- `GET /api/news` → cached items `[{title, link, source, published}]`.

## Render

- A `news` partial in the layout. Render **server-side at page load** from cache
  (news moves slowly — no live polling needed). Optional: a light JS refresh
  every few minutes hitting `/api/news`.
- No auth gate — public content.

## Export

- Bake the current cached snapshot **inline** into the static export (it's
  non-private and still useful offline). No backend needed in the exported file.

## Notes

- Support pasting many feeds; an OPML import is a nice-to-have, not required.
- `data/feed_cache.json` is runtime state — keep it **out** of `dashboard.json`.
