import os
from urllib.parse import urlparse


def app_base_path() -> str:
    raw = os.getenv("APP_BASE_PATH", "/").strip() or "/"
    base = f"/{raw.lstrip('/')}"
    if not base.endswith("/"):
        base = f"{base}/"
    return base


def app_base_path_no_trailing_slash() -> str:
    base = app_base_path()
    return "" if base == "/" else base.rstrip("/")


def external_api_root_path() -> str:
    return f"{app_base_path_no_trailing_slash()}/api"


def session_cookie_path() -> str:
    return app_base_path()


def public_url_origin() -> str | None:
    public_url = os.getenv("PUBLIC_URL", "").strip()
    if not public_url:
        return None
    parsed = urlparse(public_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
