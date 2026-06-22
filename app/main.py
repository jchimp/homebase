from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .admin import router as admin_router
from .api import router as api_router
from .auth import (
    get_admin_hash,
    get_admin_username,
    get_session_secret,
    is_configured,
    set_admin_credentials,
    verify_password,
)
from .export import render_inline
from .render import build_context
from .store import load_dashboard

load_dotenv()

app = FastAPI(title="Homebase")
app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(admin_router)
app.include_router(api_router)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard_view(request: Request) -> HTMLResponse:
    db = load_dashboard()
    ctx = build_context(db)
    layout = f"layouts/{ctx['layout']}.html"
    return templates.TemplateResponse(request=request, name=layout, context=ctx)


@app.get("/export/download")
async def export_download(request: Request) -> Response:
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    db = load_dashboard()
    html = render_inline(db, templates.env)
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": 'attachment; filename="homebase.html"'},
    )


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if is_configured():
        return RedirectResponse("/login", status_code=303)
    theme = load_dashboard().settings.theme
    return templates.TemplateResponse(request=request, name="admin/setup.html", context={"theme": theme})


@app.post("/setup", response_model=None)
async def setup_submit(request: Request):
    if is_configured():
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    confirm = str(form.get("confirm", ""))

    error = None
    if not username:
        error = "Username is required."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm:
        error = "Passwords do not match."

    if error:
        return templates.TemplateResponse(
            request=request,
            name="admin/setup.html",
            context={"error": error, "username": username, "theme": load_dashboard().settings.theme},
            status_code=400,
        )

    set_admin_credentials(username, password)
    request.session["authenticated"] = True
    return RedirectResponse("/admin", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if not is_configured():
        return RedirectResponse("/setup", status_code=303)
    if request.session.get("authenticated"):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request=request, name="admin/login.html", context={})


@app.post("/login", response_model=None)
async def login_submit(request: Request):
    if not is_configured():
        return RedirectResponse("/setup", status_code=303)
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    expected_user = get_admin_username()
    password_hash = get_admin_hash()
    if username == expected_user and password_hash and verify_password(password, password_hash):
        request.session["authenticated"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"error": "Invalid credentials"},
        status_code=401,
    )


@app.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
