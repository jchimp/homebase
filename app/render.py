import base64
from datetime import datetime
from pathlib import Path
from typing import Any

from markupsafe import Markup

from .news import curate, get_cached_items
from .store import Dashboard, Icon


def _icon_html(icon: Icon, icon_style: str, name: str = "") -> Markup:
    if not icon.svg:
        letter = (name[:1] or "?").upper()
        return Markup(f'<span class="icon-placeholder">{letter}</span>')

    if icon_style == "color":
        return Markup(f'<span class="icon icon--color">{icon.svg}</span>')

    if icon.mode == "monotone":
        return Markup(f'<span class="icon icon--mono">{icon.svg}</span>')

    # color SVG forced monochrome: CSS mask collapses it to a flat silhouette
    encoded = base64.b64encode(icon.svg.encode()).decode()
    data_uri = f"url('data:image/svg+xml;base64,{encoded}')"
    return Markup(
        f'<span class="icon icon--mask" style="--icon-src: {data_uri};"></span>'
    )


def accent_override_css(color: str) -> str:
    """Build a :root override that retints --accent and its derived variants.

    Returns an empty string if the color isn't a valid #rrggbb hex, so a bad
    value silently falls back to the theme's own accent rather than breaking CSS.
    """
    hex_str = color.lstrip("#")
    if len(hex_str) != 6:
        return ""
    try:
        r, g, b = (int(hex_str[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return ""
    return (
        f":root{{"
        f"--accent:#{hex_str};"
        f"--accent-dim:rgba({r},{g},{b},0.12);"
        f"--border-focus:rgba({r},{g},{b},0.5);"
        f"}}"
    )


def _short_url(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").rstrip("/")


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    if hour < 21:
        return "Good evening"
    return "Good night"


def _load_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def build_context(dashboard: Dashboard, inline: bool = False) -> dict[str, Any]:
    """Build the render-context dict consumed by every layout template."""
    s = dashboard.settings
    now = datetime.now()

    app_groups = [
        {
            "title": group.title,
            "apps": [
                {
                    "name": app.name,
                    "hint": app.subtitle or _short_url(app.url),
                    "url": app.url,
                    "icon_html": _icon_html(app.icon, s.icon_style, app.name),
                }
                for app in group.items
            ],
        }
        for group in dashboard.apps
    ]

    bookmark_groups = [
        {
            "title": group.title,
            "links": [
                {
                    "name": link.name,
                    "url": link.url,
                    "icon_html": _icon_html(link.icon, s.icon_style, link.name),
                }
                for link in group.links
            ],
        }
        for group in dashboard.bookmarks
    ]

    ctx: dict[str, Any] = {
        "settings": s,
        "greeting": _greeting(),
        "date_str": now.strftime("%A, %d %B %Y"),
        "app_groups": app_groups,
        "bookmark_groups": bookmark_groups,
        "weather": {
            "enabled": s.weather.enabled,
            "lat": s.weather.latitude,
            "lon": s.weather.longitude,
            "units": s.weather.units,
        },
        "search": {
            "enabled": s.search.enabled,
            "engine_url": s.search.engine_url,
            "placeholder": s.search.placeholder,
        },
        "news": {
            "enabled": s.news.enabled,
            "columns": s.news.columns,
            "columns_data": (
                curate(get_cached_items(), s.news.columns, s.news.per_column)
                if s.news.enabled
                else []
            ),
            # Live page polls; the export (inline) baked snapshot stays static.
            "refresh_ms": 0 if inline else s.news.refresh_minutes * 60 * 1000,
        },
        "icon_style": s.icon_style,
        "accent_css": accent_override_css(s.accent_color) if s.accent_override else "",
        "theme": s.theme,
        "mode": s.mode,
        "layout": s.layout,
        "inline": inline,
    }

    if inline:
        ctx["_theme_css"] = _load_file(f"static/css/themes/{s.theme}.css")
        ctx["_base_css"] = _load_file("static/css/base.css")
        ctx["_homebase_js"] = _load_file("static/js/homebase.js")

    return ctx
