from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .icons import fetch_icon_svg, iconify_search, resolve_favicon

router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="templates")


@router.get("/icons/search", response_class=HTMLResponse)
async def api_icon_search(request: Request, q: str = "") -> HTMLResponse:
    if not q.strip():
        return HTMLResponse("")
    try:
        icons = await iconify_search(q.strip())
    except Exception:
        return HTMLResponse('<p class="icon-results__err">Search unavailable</p>')
    return templates.TemplateResponse(
        request=request,
        name="admin/partials/icon_results.html",
        context={"icons": icons},
    )


@router.get("/icons/resolve")
async def api_icon_resolve(ref: str, mode: str = "monotone") -> JSONResponse:
    try:
        svg = await fetch_icon_svg(ref)
    except Exception:
        svg = ""
    return JSONResponse({"svg": svg, "source": "iconify", "ref": ref, "mode": mode})


@router.get("/icons/favicon")
async def api_icon_favicon(url: str) -> JSONResponse:
    try:
        svg = await resolve_favicon(url)
    except Exception:
        svg = ""
    return JSONResponse({"svg": svg, "source": "favicon", "ref": url, "mode": "color"})
