import json
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

DATA_PATH = Path(os.getenv("DATA_PATH", "data/dashboard.json"))

# Themes consolidated into hue families with light/dark modes; map the old
# single-mode theme names onto their family so existing data keeps working.
_LEGACY_THEMES = {"midnight": "sage", "light": "sage"}
_KNOWN_THEMES = {"nord", "slate", "sage"}


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


class Settings(BaseModel):
    title: str = "Hearth"
    theme: str = "nord"
    mode: Literal["system", "light", "dark"] = "system"
    layout: str = "flame"
    visibility: Literal["public", "private"] = "public"
    icon_style: Literal["monochrome", "color"] = "monochrome"
    accent_override: bool = False
    accent_color: str = "#0067c0"
    search: SearchSettings = SearchSettings()
    weather: WeatherSettings = WeatherSettings()
    export: ExportSettings = ExportSettings()

    @field_validator("theme", mode="before")
    @classmethod
    def _migrate_theme(cls, v: object) -> str:
        """Map legacy theme names onto their new family; fall back to default."""
        if not isinstance(v, str) or not v:
            return "nord"
        v = _LEGACY_THEMES.get(v, v)
        return v if v in _KNOWN_THEMES else "nord"


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
