import os
from pathlib import Path

from .render import build_context
from .store import Dashboard


def render_inline(db: Dashboard, jinja_env) -> str:
    """Render the full dashboard as a self-contained HTML string."""
    ctx = build_context(db, inline=True)
    layout = f"layouts/{ctx['layout']}.html"
    return jinja_env.get_template(layout).render(**ctx)


def auto_export(db: Dashboard, jinja_env) -> None:
    """Write inline export to disk if auto_on_save is enabled. Fails silently."""
    if not db.settings.export.auto_on_save:
        return
    path = Path(db.settings.export.auto_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        html = render_inline(db, jinja_env)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass
