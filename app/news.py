"""Aggregated RSS/Atom news feed: server-side fetch, cache, and persistence.

The widget renders server-side from an in-memory snapshot that is also persisted
to ``feed_cache.json`` (runtime state — kept out of ``dashboard.json``). A slow or
dead feed never blocks page render: every feed is fetched with a timeout and its
errors are caught and skipped.
"""

import asyncio
import calendar
import html
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import feedparser
import httpx

from .store import DATA_PATH, NewsSettings, load_dashboard

CACHE_PATH = DATA_PATH.parent / "feed_cache.json"
FETCH_TIMEOUT = 10  # seconds, per feed
IDLE_SLEEP = 300  # seconds to sleep when the widget is disabled
# Reddit (and others) throttle generic/browser User-Agents harder and want a
# unique, descriptive one. Keep it specific.
USER_AGENT = "Homebase:dashboard:1.0 (RSS news widget; +https://github.com/homebase)"
# Feeds on the same host are fetched sequentially with this gap so we don't burst
# a single host (the 3 Reddit feeds were hitting reddit.com all at once → 429).
SAME_HOST_DELAY = 1.0  # seconds between requests to the same host
# On a 429 we honor Retry-After, but only retry inline if the wait is short;
# anything longer is left to the next refresh cycle.
RETRY_AFTER_MAX = 5.0  # seconds
CACHE_CAP = 200  # max items retained in the cache pool (curation trims for display)

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r'<img[^>]+?src="([^"]+)"', re.I)

# In-memory snapshot served to the renderer and /api/news.
_CACHE: list[dict] = []


def _sanitize(text: str) -> str:
    """Strip tags and decode entities, returning safe plain text.

    Consumers (Jinja autoescape, JS ``textContent``) escape on render, so the
    stored value is untrusted feed content reduced to a flat string.
    """
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _published_epoch(entry: object) -> int:
    """Best-effort UTC epoch seconds for an entry; 0 if unknown (sorts last)."""
    for key in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, key, None) or (
            entry.get(key) if isinstance(entry, dict) else None
        )
        if struct:
            try:
                return calendar.timegm(struct)
            except (TypeError, ValueError):
                continue
    return 0


def _thumbnail(entry: object) -> str:
    """Best-effort image URL for an entry, or "" if none.

    Tries, in order: media:thumbnail, image media:content, image enclosures,
    then the first <img> in the content/summary HTML. Reddit emits placeholder
    thumbnails like "self"/"default"/"nsfw" — the http check filters those out.
    """
    def get(key: str) -> list:
        val = entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
        return val or []

    for thumb in get("media_thumbnail"):
        url = thumb.get("url", "")
        if url.startswith("http"):
            return url

    for media in get("media_content"):
        url = media.get("url", "")
        is_image = media.get("medium") == "image" or str(media.get("type", "")).startswith("image")
        if url.startswith("http") and is_image:
            return url

    for link in get("links"):
        if (
            link.get("rel") == "enclosure"
            and str(link.get("type", "")).startswith("image")
            and link.get("href", "").startswith("http")
        ):
            return link["href"]

    blobs = [c.get("value", "") for c in get("content")]
    blobs.append(entry.get("summary", "") if isinstance(entry, dict) else getattr(entry, "summary", ""))
    for blob in blobs:
        match = _IMG_RE.search(blob or "")
        if match and match.group(1).startswith("http"):
            return match.group(1)

    return ""


def _entry_source(entry: object, feed_source: str, is_reddit: bool) -> str:
    """Source label for one entry.

    Reddit feeds may combine several subreddits in one request (e.g.
    ``r/selfhosted+homelab+sysadmin/.rss``); each entry is tagged with its own
    subreddit, so we label per-subreddit ("r/homelab"). That keeps curation
    treating each subreddit as a distinct source even from a single fetch.
    """
    if is_reddit:
        tags = entry.get("tags") if isinstance(entry, dict) else getattr(entry, "tags", None)
        if tags:
            tag = tags[0]
            label = tag.get("label") or (f"r/{tag.get('term')}" if tag.get("term") else "")
            if label:
                return _sanitize(label)
    return feed_source


def get_cached_items() -> list[dict]:
    """Return the current in-memory snapshot. Never raises."""
    return list(_CACHE)


def curate(entries: list[dict], columns: int, per_column: int) -> list[list[dict]]:
    """Select and arrange cached items into `columns` balanced, source-mixed columns.

    Selection favours fairness over raw recency: the 2 newest of every feed are
    taken first (round-robin rounds 0 and 1), then older items backfill by recency
    until `columns * per_column` are chosen. The selected list is interleaved by
    source, then sliced into sequential column-sized chunks so each column shows a
    spread of sources rather than one feed clustered together.
    """
    total = columns * per_column

    by_source: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:  # entries arrive newest-first, so groups stay ordered
        by_source[entry["source"]].append(entry)

    # Freshest feed first, so interleaving starts from the most recently updated.
    sources = sorted(by_source, key=lambda s: by_source[s][0]["published"], reverse=True)
    deepest = max((len(items) for items in by_source.values()), default=0)

    selected: list[dict] = []
    for round_idx in range(deepest):
        for source in sources:
            items = by_source[source]
            if round_idx < len(items):
                selected.append(items[round_idx])
                if len(selected) >= total:
                    break
        if len(selected) >= total:
            break

    return [selected[c * per_column : (c + 1) * per_column] for c in range(columns)]


def load_cache_from_disk() -> None:
    """Populate the in-memory cache from disk so we serve instantly on boot."""
    global _CACHE
    try:
        with CACHE_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _CACHE = data
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def _save_cache(items: list[dict]) -> None:
    """Atomically persist the snapshot (temp file + os.replace)."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
    os.replace(tmp, CACHE_PATH)


def _retry_after(resp: httpx.Response) -> float | None:
    """Bounded Retry-After delay for a 429, or None if too long to wait inline."""
    raw = resp.headers.get("Retry-After")
    delay = 2.0
    if raw:
        try:
            delay = float(raw)
        except ValueError:
            delay = 2.0
    return delay if delay <= RETRY_AFTER_MAX else None


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    """GET a feed, retrying once on a 429 with a short, bounded backoff."""
    try:
        resp = await client.get(url, timeout=FETCH_TIMEOUT)
        if resp.status_code == 429:
            delay = _retry_after(resp)
            if delay is None:
                return resp
            await asyncio.sleep(delay)
            resp = await client.get(url, timeout=FETCH_TIMEOUT)
        return resp
    except Exception:
        return None


async def _fetch_feed(client: httpx.AsyncClient, url: str) -> list[dict]:
    """Fetch and parse one feed into normalized items; [] on any error."""
    resp = await _get(client, url)
    if resp is None or resp.status_code != 200:
        return []
    try:
        parsed = feedparser.parse(resp.content)
    except Exception:
        return []

    feed_source = _sanitize(getattr(parsed.feed, "title", "")) or url
    is_reddit = "reddit.com" in urlsplit(url).netloc.lower()
    items = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "")
        title = _sanitize(getattr(entry, "title", ""))
        if not link or not title:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "source": _entry_source(entry, feed_source, is_reddit),
                "published": _published_epoch(entry),
                "thumbnail": _thumbnail(entry),
            }
        )
    return items


async def _fetch_host(client: httpx.AsyncClient, urls: list[str]) -> list[dict]:
    """Fetch all feeds for one host sequentially, spacing requests apart."""
    items: list[dict] = []
    for i, url in enumerate(urls):
        if i:
            await asyncio.sleep(SAME_HOST_DELAY)
        items.extend(await _fetch_feed(client, url))
    return items


async def refresh(settings: NewsSettings) -> list[dict]:
    """Pull all feeds, merge, sort by published desc, dedupe by link, trim.

    Different hosts are fetched concurrently; feeds sharing a host are fetched
    one at a time (so the several Reddit feeds don't burst reddit.com at once).
    Updates the in-memory cache and persists it. Returns the new snapshot.
    """
    global _CACHE
    by_host: dict[str, list[str]] = defaultdict(list)
    for url in settings.feeds:
        by_host[urlsplit(url).netloc.lower()].append(url)

    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        results = await asyncio.gather(
            *(_fetch_host(client, urls) for urls in by_host.values())
        )

    merged: list[dict] = [item for feed_items in results for item in feed_items]
    merged.sort(key=lambda i: i["published"], reverse=True)

    seen: set[str] = set()
    deduped: list[dict] = []
    for item in merged:
        if item["link"] in seen:
            continue
        seen.add(item["link"])
        deduped.append(item)

    snapshot = deduped[:CACHE_CAP]
    _CACHE = snapshot
    try:
        _save_cache(snapshot)
    except OSError:
        pass
    return snapshot


async def refresh_loop() -> None:
    """Background task: refresh on the configured interval while enabled.

    Reads settings fresh each cycle so admin changes take effect on the next
    pass. When the widget is disabled, idles without fetching.
    """
    while True:
        news = load_dashboard().settings.news
        if news.enabled:
            try:
                await refresh(news)
            except Exception:
                pass
            sleep_for = news.refresh_minutes * 60
        else:
            sleep_for = IDLE_SLEEP
        await asyncio.sleep(sleep_for)
