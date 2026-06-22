import json
import os
import secrets
from typing import Any

import bcrypt
from fastapi import Request
from fastapi.responses import RedirectResponse

from .store import DATA_PATH

AUTH_PATH = DATA_PATH.parent / "auth.json"

_PLACEHOLDER_SECRETS = {"", "change-me-in-production", "change-me-to-a-long-random-string"}


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_auth(request: Request) -> RedirectResponse | None:
    """Return a redirect to /login if the session is not authenticated."""
    if not request.session.get("authenticated"):
        return RedirectResponse("/login", status_code=303)
    return None


# ── Credential store (data/auth.json) ──────────────────────────────────
#
# Credentials resolve env-var-first, then this file, so existing .env/CLI
# installs keep working while a fresh install can be configured in the browser.


def load_credentials() -> dict[str, Any]:
    """Load data/auth.json, returning {} if absent or unreadable."""
    if not AUTH_PATH.exists():
        return {}
    try:
        with AUTH_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_credentials(data: dict[str, Any]) -> None:
    """Atomically write data/auth.json with restrictive permissions."""
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTH_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, AUTH_PATH)
    try:
        os.chmod(AUTH_PATH, 0o600)
    except OSError:
        pass  # best-effort; not supported on all platforms (e.g. Windows)


def get_admin_username() -> str:
    """Admin username: env override, then auth.json, then 'admin'."""
    env = os.getenv("ADMIN_USERNAME", "").strip()
    if env:
        return env
    return str(load_credentials().get("username") or "admin")


def get_admin_hash() -> str:
    """Admin password hash: env override, then auth.json."""
    env = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    if env:
        return env
    return str(load_credentials().get("password_hash") or "")


def is_configured() -> bool:
    """True once an admin password hash exists from any source."""
    return bool(get_admin_hash())


def set_admin_credentials(username: str, password: str) -> None:
    """Hash and persist admin credentials to auth.json, preserving the secret."""
    creds = load_credentials()
    creds["username"] = username
    creds["password_hash"] = get_password_hash(password)
    save_credentials(creds)


def get_session_secret() -> str:
    """Session secret: env override, then auth.json, else generate and persist."""
    env = os.getenv("SESSION_SECRET", "").strip()
    if env and env not in _PLACEHOLDER_SECRETS:
        return env
    creds = load_credentials()
    secret = creds.get("session_secret")
    if secret:
        return str(secret)
    secret = secrets.token_urlsafe(32)
    creds["session_secret"] = secret
    save_credentials(creds)
    return secret
