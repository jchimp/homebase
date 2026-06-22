import json
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from . import news
from .auth import check_auth
from .export import auto_export
from .icons import sanitize_svg
from .render import accent_override_css
from .store import Dashboard, App, AppGroup, BookmarkGroup, BookmarkLink, Icon, load_dashboard, save_dashboard

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


def _new_id(prefix: str = "item") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _tpl(name: str, request: Request, ctx: dict) -> HTMLResponse:
    db = ctx.get("db") or load_dashboard()
    ctx.setdefault("db", db)
    s = db.settings
    ctx.setdefault(
        "accent_css", accent_override_css(s.accent_color) if s.accent_override else ""
    )
    return templates.TemplateResponse(request=request, name=name, context=ctx)


def _apps_section(request: Request, editing: dict | None = None) -> HTMLResponse:
    db = load_dashboard()
    return _tpl("admin/partials/apps_section.html", request, {"db": db, "editing": editing})


def _bm_section(request: Request, editing: dict | None = None) -> HTMLResponse:
    db = load_dashboard()
    return _tpl("admin/partials/bookmarks_section.html", request, {"db": db, "editing": editing})


def _icon_from_form(
    source: str, ref: str, mode: str, svg: str
) -> Icon:
    clean = sanitize_svg(svg) if svg.strip() else ""
    return Icon(source=source or "custom", ref=ref, mode=mode or "monotone", svg=clean)


def _do_auto_export(db) -> None:
    try:
        auto_export(db, templates.env)
    except Exception:
        pass


# ── Root redirect ─────────────────────────────────────────

@router.get("/", include_in_schema=False)
async def admin_root() -> RedirectResponse:
    return RedirectResponse("/admin/apps", status_code=303)


# ── Apps ─────────────────────────────────────────────────

@router.get("/apps", response_class=HTMLResponse)
async def admin_apps(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    return _tpl("admin/apps.html", request, {"db": db, "editing": None, "active": "apps"})


@router.get("/apps/section", response_class=HTMLResponse)
async def admin_apps_section(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _apps_section(request)


# App groups

@router.post("/apps/groups", response_class=HTMLResponse)
async def admin_apps_add_group(request: Request, title: str = Form(...)) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    db.apps.append(AppGroup(id=_new_id("grp"), title=title.strip()))
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.get("/apps/groups/{gid}/edit", response_class=HTMLResponse)
async def admin_apps_edit_group_form(request: Request, gid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _apps_section(request, editing={"type": "group", "id": gid})


@router.put("/apps/groups/{gid}", response_class=HTMLResponse)
async def admin_apps_save_group(
    request: Request, gid: str, title: str = Form(...)
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            g.title = title.strip()
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.delete("/apps/groups/{gid}", response_class=HTMLResponse)
async def admin_apps_delete_group(request: Request, gid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    db.apps = [g for g in db.apps if g.id != gid]
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.post("/apps/groups/{gid}/move", response_class=HTMLResponse)
async def admin_apps_move_group(
    request: Request, gid: str, dir: str = "up"
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    idx = next((i for i, g in enumerate(db.apps) if g.id == gid), None)
    if idx is not None:
        if dir == "up" and idx > 0:
            db.apps[idx - 1], db.apps[idx] = db.apps[idx], db.apps[idx - 1]
        elif dir == "down" and idx < len(db.apps) - 1:
            db.apps[idx + 1], db.apps[idx] = db.apps[idx], db.apps[idx + 1]
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


# App items

@router.post("/apps/groups/{gid}/items", response_class=HTMLResponse)
async def admin_apps_add_item(
    request: Request,
    gid: str,
    name: str = Form(...),
    url: str = Form(...),
    subtitle: str = Form(""),
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            g.items.append(App(
                id=_new_id("app"), name=name.strip(),
                url=url.strip(), subtitle=subtitle.strip(),
            ))
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.get("/apps/groups/{gid}/items/{iid}/edit", response_class=HTMLResponse)
async def admin_apps_edit_item_form(request: Request, gid: str, iid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _apps_section(request, editing={"type": "item", "gid": gid, "iid": iid})


@router.put("/apps/groups/{gid}/items/{iid}", response_class=HTMLResponse)
async def admin_apps_save_item(
    request: Request,
    gid: str,
    iid: str,
    name: str = Form(...),
    url: str = Form(...),
    subtitle: str = Form(""),
    icon_source: str = Form("custom"),
    icon_ref: str = Form(""),
    icon_mode: str = Form("monotone"),
    icon_svg: str = Form(""),
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            for item in g.items:
                if item.id == iid:
                    item.name = name.strip()
                    item.url = url.strip()
                    item.subtitle = subtitle.strip()
                    item.icon = _icon_from_form(icon_source, icon_ref, icon_mode, icon_svg)
                    break
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.delete("/apps/groups/{gid}/items/{iid}", response_class=HTMLResponse)
async def admin_apps_delete_item(request: Request, gid: str, iid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            g.items = [item for item in g.items if item.id != iid]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


@router.post("/apps/groups/{gid}/items/{iid}/move", response_class=HTMLResponse)
async def admin_apps_move_item(
    request: Request, gid: str, iid: str, dir: str = "up"
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            idx = next((i for i, item in enumerate(g.items) if item.id == iid), None)
            if idx is not None:
                if dir == "up" and idx > 0:
                    g.items[idx - 1], g.items[idx] = g.items[idx], g.items[idx - 1]
                elif dir == "down" and idx < len(g.items) - 1:
                    g.items[idx + 1], g.items[idx] = g.items[idx], g.items[idx + 1]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _apps_section(request)


# ── Bookmarks ─────────────────────────────────────────────

@router.get("/bookmarks", response_class=HTMLResponse)
async def admin_bookmarks(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    return _tpl("admin/bookmarks.html", request, {"db": db, "editing": None, "active": "bookmarks"})


@router.get("/bookmarks/section", response_class=HTMLResponse)
async def admin_bm_section(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _bm_section(request)


# Groups

@router.post("/bookmarks/groups", response_class=HTMLResponse)
async def admin_bm_add_group(request: Request, title: str = Form(...)) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    db.bookmarks.append(BookmarkGroup(id=_new_id("grp"), title=title.strip()))
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.get("/bookmarks/groups/{gid}/edit", response_class=HTMLResponse)
async def admin_bm_edit_group_form(request: Request, gid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _bm_section(request, editing={"type": "group", "id": gid})


@router.put("/bookmarks/groups/{gid}", response_class=HTMLResponse)
async def admin_bm_save_group(
    request: Request, gid: str, title: str = Form(...)
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            g.title = title.strip()
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.delete("/bookmarks/groups/{gid}", response_class=HTMLResponse)
async def admin_bm_delete_group(request: Request, gid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    db.bookmarks = [g for g in db.bookmarks if g.id != gid]
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.post("/bookmarks/groups/{gid}/move", response_class=HTMLResponse)
async def admin_bm_move_group(
    request: Request, gid: str, dir: str = "up"
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    idx = next((i for i, g in enumerate(db.bookmarks) if g.id == gid), None)
    if idx is not None:
        if dir == "up" and idx > 0:
            db.bookmarks[idx - 1], db.bookmarks[idx] = db.bookmarks[idx], db.bookmarks[idx - 1]
        elif dir == "down" and idx < len(db.bookmarks) - 1:
            db.bookmarks[idx + 1], db.bookmarks[idx] = db.bookmarks[idx], db.bookmarks[idx + 1]
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


# Links

@router.post("/bookmarks/groups/{gid}/links", response_class=HTMLResponse)
async def admin_bm_add_link(
    request: Request,
    gid: str,
    name: str = Form(...),
    url: str = Form(...),
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            g.links.append(BookmarkLink(id=_new_id("lnk"), name=name.strip(), url=url.strip()))
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.get("/bookmarks/groups/{gid}/links/{lid}/edit", response_class=HTMLResponse)
async def admin_bm_edit_link_form(request: Request, gid: str, lid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    return _bm_section(request, editing={"type": "link", "gid": gid, "lid": lid})


@router.put("/bookmarks/groups/{gid}/links/{lid}", response_class=HTMLResponse)
async def admin_bm_save_link(
    request: Request,
    gid: str,
    lid: str,
    name: str = Form(...),
    url: str = Form(...),
    icon_source: str = Form("custom"),
    icon_ref: str = Form(""),
    icon_mode: str = Form("monotone"),
    icon_svg: str = Form(""),
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            for lnk in g.links:
                if lnk.id == lid:
                    lnk.name = name.strip()
                    lnk.url = url.strip()
                    lnk.icon = _icon_from_form(icon_source, icon_ref, icon_mode, icon_svg)
                    break
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.delete("/bookmarks/groups/{gid}/links/{lid}", response_class=HTMLResponse)
async def admin_bm_delete_link(request: Request, gid: str, lid: str) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            g.links = [lnk for lnk in g.links if lnk.id != lid]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


@router.post("/bookmarks/groups/{gid}/links/{lid}/move", response_class=HTMLResponse)
async def admin_bm_move_link(
    request: Request, gid: str, lid: str, dir: str = "up"
) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            idx = next((i for i, lnk in enumerate(g.links) if lnk.id == lid), None)
            if idx is not None:
                if dir == "up" and idx > 0:
                    g.links[idx - 1], g.links[idx] = g.links[idx], g.links[idx - 1]
                elif dir == "down" and idx < len(g.links) - 1:
                    g.links[idx + 1], g.links[idx] = g.links[idx], g.links[idx + 1]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return _bm_section(request)


# ── Reorder (drag-and-drop) ───────────────────────────────

@router.post("/apps/groups/reorder")
async def admin_apps_reorder_groups(
    request: Request,
    order: Annotated[list[str], Body()],
) -> Response:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    id_map = {g.id: g for g in db.apps}
    db.apps = [id_map[i] for i in order if i in id_map]
    save_dashboard(db)
    _do_auto_export(db)
    return Response(status_code=204)


@router.post("/apps/groups/{gid}/items/reorder")
async def admin_apps_reorder_items(
    request: Request,
    gid: str,
    order: Annotated[list[str], Body()],
) -> Response:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.apps:
        if g.id == gid:
            id_map = {i.id: i for i in g.items}
            g.items = [id_map[i] for i in order if i in id_map]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return Response(status_code=204)


@router.post("/bookmarks/groups/reorder")
async def admin_bm_reorder_groups(
    request: Request,
    order: Annotated[list[str], Body()],
) -> Response:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    id_map = {g.id: g for g in db.bookmarks}
    db.bookmarks = [id_map[i] for i in order if i in id_map]
    save_dashboard(db)
    _do_auto_export(db)
    return Response(status_code=204)


@router.post("/bookmarks/groups/{gid}/links/reorder")
async def admin_bm_reorder_links(
    request: Request,
    gid: str,
    order: Annotated[list[str], Body()],
) -> Response:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    for g in db.bookmarks:
        if g.id == gid:
            id_map = {lnk.id: lnk for lnk in g.links}
            g.links = [id_map[i] for i in order if i in id_map]
            break
    save_dashboard(db)
    _do_auto_export(db)
    return Response(status_code=204)


# ── Data import / export ──────────────────────────────────

@router.get("/data/export")
async def admin_data_export(request: Request) -> Response:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    return Response(
        content=db.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="dashboard.json"'},
    )


@router.post("/data/import", response_model=None)
async def admin_data_import(
    request: Request,
    file: UploadFile = File(...),
) -> RedirectResponse:
    if redir := check_auth(request):
        return redir
    try:
        content = await file.read()
        data = json.loads(content)
        db = Dashboard.model_validate(data)
        save_dashboard(db)
        _do_auto_export(db)
        request.session["flash"] = "Dashboard imported successfully."
    except Exception as exc:
        request.session["flash_err"] = f"Import failed: {exc}"
    return RedirectResponse("/admin/export", status_code=303)


# ── Export page ───────────────────────────────────────────

@router.get("/export", response_class=HTMLResponse)
async def admin_export(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    flash = request.session.pop("flash", None)
    flash_err = request.session.pop("flash_err", None)
    return _tpl("admin/export.html", request, {
        "active": "export",
        "flash": flash,
        "flash_err": flash_err,
    })


# ── Settings ──────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request) -> HTMLResponse:
    if redir := check_auth(request):
        return redir
    db = load_dashboard()
    flash = request.session.pop("flash", None)
    geo_warn = request.session.pop("geo_warn", None)
    return _tpl("admin/settings.html", request, {
        "db": db,
        "active": "settings",
        "flash": flash,
        "geo_warn": geo_warn,
    })


@router.post("/settings", response_model=None)
async def admin_settings_save(request: Request) -> RedirectResponse:
    if redir := check_auth(request):
        return redir
    form = await request.form()

    def get(key: str, default: str = "") -> str:
        return str(form.get(key, default)).strip()

    def flag(key: str) -> bool:
        return key in form

    def _to_int(value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    db = load_dashboard()
    s = db.settings
    s.title = get("title", "Homebase") or "Homebase"
    s.theme = get("theme", "nord")
    mode = get("mode", "system")
    s.mode = mode if mode in ("system", "light", "dark") else "system"
    s.layout = get("layout", "icons")
    s.visibility = get("visibility", "public")
    s.icon_style = get("icon_style", "monochrome")
    s.accent_override = flag("accent_override")
    s.accent_color = get("accent_color", "#0067c0") or "#0067c0"
    s.show_theme_switcher = flag("show_theme_switcher")
    s.search.enabled = flag("search_enabled")
    s.search.engine_url = get("search_engine_url") or "https://duckduckgo.com/?q="
    s.search.placeholder = get("search_placeholder") or "Search the web…"
    s.weather.enabled = flag("weather_enabled")
    s.weather.units = get("weather_units", "fahrenheit")
    s.export.auto_on_save = flag("export_auto_on_save")
    s.export.auto_path = get("export_auto_path") or "/data/export/index.html"
    s.news.enabled = flag("news_enabled")
    s.news.columns = _to_int(get("news_columns"), 1)
    s.news.per_column = _to_int(get("news_per_column"), 6)
    s.news.refresh_minutes = _to_int(get("news_refresh_minutes"), 20)
    s.news.feeds = [u.strip() for u in get("news_feeds").splitlines() if u.strip()]

    new_city = get("weather_city")
    if new_city != s.weather.city or (new_city and s.weather.latitude is None):
        s.weather.city = new_city
        if new_city:
            try:
                from .weather import geocode_city
                coords = await geocode_city(new_city)
                if coords:
                    s.weather.latitude, s.weather.longitude = coords
                else:
                    s.weather.latitude = s.weather.longitude = None
                    request.session["geo_warn"] = f"City '{new_city}' not found — weather disabled."
            except Exception:
                request.session["geo_warn"] = "Geocoding unavailable — check your connection."
        else:
            s.weather.latitude = s.weather.longitude = None

    save_dashboard(db)
    # Refresh news now so the widget (and the auto-export) reflect the saved
    # feeds immediately, rather than waiting for the background loop's next tick.
    if s.news.enabled and s.news.feeds:
        try:
            await news.refresh(s.news)
        except Exception:
            pass
    _do_auto_export(db)
    request.session["flash"] = "Settings saved."
    return RedirectResponse("/admin/settings", status_code=303)
