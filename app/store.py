import json
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

DATA_PATH = Path(os.getenv("DATA_PATH", "data/dashboard.json"))

# Seed feeds for the news widget. Users edit these through the settings UI; this
# is only the starting set on first run.
DEFAULT_FEEDS = [
    "https://isc.sans.edu/rssfeed.xml",
    "https://cisa.kevintel.com/rss.xml",
    "https://www.bleepingcomputer.com/feed/",
    "https://www.theregister.com/security/headlines.atom",
    "https://krebsonsecurity.com/feed/",
    "https://www.schneier.com/feed/atom/",
    "https://selfh.st/rss/",
    # Combine subreddits into ONE request — Reddit aggressively rate-limits
    # (429s) multiple separate feed hits from a server, but a single combined
    # feed works and each entry is still tagged with its own subreddit.
    "https://www.reddit.com/r/selfhosted+homelab+sysadmin/.rss",
    "https://hnrss.org/frontpage",
]

# Themes consolidated into hue families with light/dark modes; map the old
# single-mode theme names onto their family so existing data keeps working.
_LEGACY_THEMES = {"midnight": "sage", "light": "sage"}
_KNOWN_THEMES = {"nord", "slate", "sage"}
_LEGACY_LAYOUTS = {"flame": "icons"}


class Icon(BaseModel):
    source: Literal["iconify", "favicon", "logo", "custom"] = "custom"
    ref: str = ""
    mode: Literal["monotone", "color"] = "monotone"
    svg: str = ""


class App(BaseModel):
    id: str
    name: str
    subtitle: str = ""
    url: str
    icon: Icon = Icon()


class AppGroup(BaseModel):
    id: str
    title: str
    items: list[App] = []


class BookmarkLink(BaseModel):
    id: str
    name: str
    url: str
    icon: Icon = Icon()


class BookmarkGroup(BaseModel):
    id: str
    title: str
    links: list[BookmarkLink] = []


class SearchSettings(BaseModel):
    enabled: bool = True
    engine_url: str = "https://duckduckgo.com/?q="
    placeholder: str = "Search the web…"


class WeatherSettings(BaseModel):
    enabled: bool = False
    city: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    units: Literal["fahrenheit", "celsius"] = "fahrenheit"


class ExportSettings(BaseModel):
    auto_on_save: bool = True
    auto_path: str = "/data/export/index.html"


class NewsSettings(BaseModel):
    enabled: bool = False
    columns: Literal[1, 3] = 1
    per_column: int = 6
    refresh_minutes: int = 20
    feeds: list[str] = Field(default_factory=lambda: list(DEFAULT_FEEDS))

    @field_validator("columns", mode="before")
    @classmethod
    def _coerce_columns(cls, v: object) -> int:
        """Only 1 or 3 are supported; anything else falls back to a single column."""
        try:
            return 3 if int(v) == 3 else 1
        except (TypeError, ValueError):
            return 1

    @field_validator("per_column")
    @classmethod
    def _clamp_per_column(cls, v: int) -> int:
        return max(1, min(v, 20))

    @field_validator("refresh_minutes")
    @classmethod
    def _clamp_refresh(cls, v: int) -> int:
        return max(5, min(v, 1440))


class Settings(BaseModel):
    title: str = "Hearth"
    theme: str = "nord"
    mode: Literal["system", "light", "dark"] = "system"
    layout: str = "icons"
    visibility: Literal["public", "private"] = "public"
    icon_style: Literal["monochrome", "color"] = "monochrome"
    accent_override: bool = False
    accent_color: str = "#0067c0"
    show_theme_switcher: bool = False
    search: SearchSettings = SearchSettings()
    weather: WeatherSettings = WeatherSettings()
    export: ExportSettings = ExportSettings()
    news: NewsSettings = NewsSettings()

    @field_validator("theme", mode="before")
    @classmethod
    def _migrate_theme(cls, v: object) -> str:
        """Map legacy theme names onto their new family; fall back to default."""
        if not isinstance(v, str) or not v:
            return "nord"
        v = _LEGACY_THEMES.get(v, v)
        return v if v in _KNOWN_THEMES else "nord"

    @field_validator("layout", mode="before")
    @classmethod
    def _migrate_layout(cls, v: object) -> str:
        """Map legacy layout names onto their new name; fall back to default."""
        if not isinstance(v, str) or not v:
            return "icons"
        return _LEGACY_LAYOUTS.get(v, v)


class Dashboard(BaseModel):
    version: int = 1
    settings: Settings = Settings()
    apps: list[AppGroup] = []
    bookmarks: list[BookmarkGroup] = []


def load_dashboard() -> Dashboard:
    """Load and validate dashboard.json, returning defaults if absent."""
    if not DATA_PATH.exists():
        return Dashboard()
    with DATA_PATH.open(encoding="utf-8") as f:
        return Dashboard.model_validate(json.load(f))


def save_dashboard(dashboard: Dashboard) -> None:
    """Atomically write dashboard to disk (temp file + os.replace)."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(dashboard.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, DATA_PATH)
