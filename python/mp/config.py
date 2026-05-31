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
    configured = os.getenv("SESSION_COOKIE_PATH", "").strip()
    if configured:
        return configured if configured.endswith("/") else f"{configured}/"
    return app_base_path()


def auth_mode() -> str:
    return os.getenv("AUTH_MODE", "local").strip().lower() or "local"


def central_auth_base_url() -> str:
    raw = os.getenv("AUTH_BASE_URL", "http://localhost:8090/auth").strip().rstrip("/")
    if raw.startswith(("http://", "https://")):
        return raw
    origin = public_url_origin()
    if origin and raw.startswith("/"):
        return f"{origin}{raw}"
    return raw


def oauth_server_base_url() -> str:
    raw = os.getenv("OAUTH_SERVER_BASE_URL", "").strip().rstrip("/")
    if raw:
        return raw
    return central_auth_base_url()


def oauth_client_id() -> str:
    return os.getenv("OAUTH_CLIENT_ID", "money-planner")


def oauth_scope() -> str:
    return os.getenv("OAUTH_SCOPE", "openid profile")


def oauth_redirect_uri() -> str:
    origin = public_url_origin() or "http://localhost:8081"
    return f"{origin}{external_api_root_path()}/auth/oauth/callback"


def public_url_origin() -> str | None:
    public_url = os.getenv("PUBLIC_URL", "").strip()
    if not public_url:
        return None
    parsed = urlparse(public_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"
