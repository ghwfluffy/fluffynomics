import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from mp.config import (
    app_base_path_no_trailing_slash,
    auth_mode,
    central_auth_base_url,
    oauth_client_id,
    oauth_redirect_uri,
    oauth_scope,
    oauth_server_base_url,
    session_cookie_path,
)
from mp.api.agent_tokens import TOKEN_PREFIX as AGENT_TOKEN_PREFIX
from mp.api.agent_tokens import user_from_agent_token
from mp.db import get_db
from mp.db.sample_data import ensure_example_data_for_user
from mp.schema.account import Account, DefaultIcon, IconAsset, Organization
from mp.schema.account import AccountValueHistory, NetWorthDailySnapshot, Stock
from mp.schema.contract import Contract, ContractPosting
from mp.schema.expense import Expense
from mp.schema.registration_code import RegistrationCode
from mp.schema.user import (
    DeleteAccountSchema,
    LoginResponseSchema,
    LoginSchema,
    ProfileUpdateSchema,
    User,
    UserCreateSchema,
    UserSchema,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "mp_session")
OAUTH_STATE_COOKIE_NAME = os.getenv("OAUTH_STATE_COOKIE_NAME", "mp_oauth_state")
DEFAULT_SESSION_SECONDS = 24 * 60 * 60
MAX_SESSION_SECONDS = 30 * 24 * 60 * 60
_fernet: Fernet | None = None
logger = logging.getLogger(__name__)
MAX_BAD_PASSWORD_ATTEMPTS = 10
PASSWORD_LOCKOUT_SECONDS = 30


def initialize_session_signing_key() -> None:
    global _fernet
    configured_secret = os.getenv("SESSION_KEY", "")
    if configured_secret:
        if configured_secret == "changeme":
            logger.warning(
                "SESSION_KEY is set to the default 'changeme'. "
                "Use a strong secret outside local development."
            )
        digest = hashlib.sha256(configured_secret.encode("utf-8")).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(digest))
        return
    _fernet = Fernet(Fernet.generate_key())


def _get_fernet() -> Fernet:
    if _fernet is None:
        raise RuntimeError("Session key was not initialized")
    return _fernet


def _hash_password(
    password: str, salt: str | None = None, iterations: int = 480000
) -> str:
    effective_salt = salt or base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8")
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        effective_salt.encode("utf-8"),
        iterations,
    )
    digest_b64 = base64.urlsafe_b64encode(digest).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${effective_salt}${digest_b64}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, expected = password_hash.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    iterations = int(iterations_raw)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    digest_b64 = base64.urlsafe_b64encode(digest).decode("utf-8")
    return hmac.compare_digest(digest_b64, expected)


def _create_session_cookie(user_id: UUID, session_seconds: int) -> str:
    expiry = datetime.now(tz=timezone.utc) + timedelta(seconds=session_seconds)
    payload = json.dumps(
        {"user_id": str(user_id), "expires_at": expiry.isoformat()},
        separators=(",", ":"),
    )
    return _get_fernet().encrypt(payload.encode("utf-8")).decode("utf-8")


def _set_session_cookie(
    response: Response, cookie_value: str, session_seconds: int
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        max_age=session_seconds,
        httponly=True,
        path=session_cookie_path(),
        samesite="lax",
        secure=False,
    )


def _require_local_auth_mode() -> None:
    if auth_mode() == "oauth":
        raise HTTPException(
            status_code=409,
            detail="Local authentication is disabled while AUTH_MODE=oauth",
        )


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_challenge(verifier: str) -> str:
    return _base64url(hashlib.sha256(verifier.encode("ascii")).digest())


def _safe_next_path(value: str | None) -> str:
    if value is None:
        return "/app"
    stripped = value.strip()
    if not stripped.startswith("/") or stripped.startswith("//"):
        return "/app"
    return stripped


def _oauth_error_redirect(reason: str) -> RedirectResponse:
    return RedirectResponse(
        f"{app_base_path_no_trailing_slash()}/?{urlencode({'oauth_error': reason})}",
        status_code=302,
    )


def _encode_oauth_state(payload: dict[str, str]) -> str:
    return (
        _get_fernet()
        .encrypt(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        .decode("utf-8")
    )


def _decode_oauth_state(cookie_value: str | None) -> dict[str, str] | None:
    if not cookie_value:
        return None
    try:
        payload = json.loads(
            _get_fernet().decrypt(cookie_value.encode("utf-8")).decode("utf-8")
        )
    except (InvalidToken, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in payload.items()
    ):
        return None
    return payload


def _exchange_oauth_code(code: str, verifier: str) -> dict[str, object]:
    token_response = httpx.post(
        f"{oauth_server_base_url()}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client_id(),
            "code": code,
            "redirect_uri": oauth_redirect_uri(),
            "code_verifier": verifier,
        },
        timeout=10,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not isinstance(access_token, str):
        raise ValueError("OAuth token response did not include an access token")
    userinfo_response = httpx.get(
        f"{oauth_server_base_url()}/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    userinfo_response.raise_for_status()
    userinfo = userinfo_response.json()
    if not isinstance(userinfo, dict):
        raise ValueError("OAuth userinfo response was invalid")
    return userinfo


def _oauth_text(userinfo: dict[str, object], key: str) -> str:
    value = userinfo.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"OAuth userinfo missing {key}")
    return value.strip()


def _unique_oauth_username(db: Session, username: str) -> str:
    base = username[:80] or "oauth-user"
    candidate = base
    suffix = 1
    while db.query(User.id).filter(User.username == candidate).first() is not None:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _find_or_create_oauth_user(db: Session, userinfo: dict[str, object]) -> User:
    subject = _oauth_text(userinfo, "sub")
    username = _oauth_text(userinfo, "preferred_username")
    provider = central_auth_base_url()
    user = (
        db.query(User)
        .filter_by(identity_provider=provider, external_subject=subject)
        .first()
    )
    if user is None:
        user = (
            db.query(User)
            .filter(
                User.username == username,
                User.identity_provider.is_(None),
                User.external_subject.is_(None),
            )
            .first()
        )
        if user is None:
            now = datetime.now(tz=timezone.utc)
            user = User(
                username=_unique_oauth_username(db, username),
                password_hash=_hash_password(secrets.token_urlsafe(32)),
                example_data=False,
                password_changed_at=now,
                is_admin=bool(userinfo.get("is_admin")),
                created_at=now,
                updated_at=now,
            )
            db.add(user)
        user.identity_provider = provider
        user.external_subject = subject
    picture = userinfo.get("picture")
    user.central_avatar_url = (
        picture if isinstance(picture, str) and picture.strip() else None
    )
    user.is_admin = bool(userinfo.get("is_admin"))
    user.last_login_at = datetime.now(tz=timezone.utc)
    user.updated_at = user.last_login_at
    db.add(user)
    db.flush()
    return user


def _is_icon_selectable_for_user(db: Session, user_id: UUID, icon_id: UUID) -> bool:
    is_default_org_icon = (
        db.query(Organization.id)
        .filter(Organization.icon_id == icon_id, Organization.is_default.is_(True))
        .first()
        is not None
    )
    if is_default_org_icon:
        return True
    is_default_generic_icon = (
        db.query(DefaultIcon.id).filter(DefaultIcon.icon_id == icon_id).first()
        is not None
    )
    if is_default_generic_icon:
        return True
    owned = (
        db.query(IconAsset)
        .filter(IconAsset.id == icon_id, IconAsset.created_by_user_id == user_id)
        .first()
    )
    if owned is not None:
        return True
    is_referenced_by_user = (
        (
            db.query(Account.id)
            .filter(Account.user_id == user_id, Account.icon_id == icon_id)
            .first()
            is not None
        )
        or (
            db.query(Contract.id)
            .filter(Contract.user_id == user_id, Contract.icon_id == icon_id)
            .first()
            is not None
        )
        or (
            db.query(Expense.id)
            .filter(Expense.user_id == user_id, Expense.icon_id == icon_id)
            .first()
            is not None
        )
    )
    return is_referenced_by_user


def _is_password_locked(user: User, now: datetime) -> bool:
    lockout_until = user.password_lockout_until
    return lockout_until is not None and lockout_until > now


def _validate_owned_wallet_account(
    db: Session, user_id: UUID, account_id: UUID | None, field: str
) -> None:
    if account_id is None:
        return
    exists = (
        db.query(Account.id)
        .filter(Account.id == account_id, Account.user_id == user_id)
        .first()
    )
    if exists is None:
        raise HTTPException(status_code=400, detail=f"{field} is not an owned account")


def _seconds_until_unlock(user: User, now: datetime) -> int:
    lockout_until = user.password_lockout_until
    if lockout_until is None:
        return 0
    remaining = (lockout_until - now).total_seconds()
    return max(0, int(remaining + 0.999))


def _generate_widget_token(db: Session) -> str:
    for _ in range(10):
        candidate = secrets.token_urlsafe(24)
        exists = db.query(User.id).filter(User.widget_token == candidate).first()
        if exists is None:
            return candidate
    raise RuntimeError("Unable to generate a unique widget token")


def _record_failed_password_attempt(user: User, now: datetime) -> None:
    attempts = int(user.failed_password_attempts or 0) + 1
    user.failed_password_attempts = attempts
    if attempts >= MAX_BAD_PASSWORD_ATTEMPTS:
        user.password_lockout_until = now + timedelta(seconds=PASSWORD_LOCKOUT_SECONDS)


def _reset_password_attempt_state(user: User) -> None:
    user.failed_password_attempts = 0
    user.password_lockout_until = None


def _parse_session_token(raw_token: str | None) -> UUID:
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        decrypted = _get_fernet().decrypt(raw_token.encode("utf-8")).decode("utf-8")
        payload = json.loads(decrypted)
        user_id = UUID(payload["user_id"])
        expires_at = datetime.fromisoformat(payload["expires_at"])
    except (InvalidToken, ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    if expires_at <= datetime.now(tz=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    return user_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth_header = request.headers.get("authorization")
    token: str | None = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token.startswith(f"{AGENT_TOKEN_PREFIX}."):
            user = user_from_agent_token(request, db, token)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid agent token",
                )
            return user
    if token is None:
        token = request.cookies.get(SESSION_COOKIE_NAME)

    user_id = _parse_session_token(token)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    return user


@router.post("/register", response_model=UserSchema)
def register(payload: UserCreateSchema, db: Session = Depends(get_db)) -> User:
    _require_local_auth_mode()
    existing = db.query(User).filter_by(username=payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already exists")

    now = datetime.now(tz=timezone.utc)
    existing_user_count = db.query(User).count()
    if existing_user_count > 0:
        raw_code = (payload.registration_code or "").strip().upper()
        if not raw_code:
            raise HTTPException(status_code=400, detail="registration_code is required")
        registration_code = (
            db.query(RegistrationCode).filter(RegistrationCode.code == raw_code).first()
        )
        if registration_code is None:
            raise HTTPException(status_code=400, detail="registration_code is invalid")
        if (
            registration_code.expires_at is not None
            and registration_code.expires_at <= now
        ):
            raise HTTPException(status_code=400, detail="registration_code is expired")

    user = User(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        example_data=payload.add_example_data,
        password_changed_at=now,
        is_admin=existing_user_count == 0,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()
    if payload.add_example_data:
        ensure_example_data_for_user(db, user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponseSchema)
def login(
    payload: LoginSchema, response: Response, db: Session = Depends(get_db)
) -> LoginResponseSchema:
    _require_local_auth_mode()
    now = datetime.now(tz=timezone.utc)
    user = db.query(User).filter_by(username=payload.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if _is_password_locked(user, now):
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many failed password attempts. "
                f"Try again in {_seconds_until_unlock(user, now)} seconds."
            ),
        )
    if not _verify_password(payload.password, user.password_hash):
        _record_failed_password_attempt(user, now)
        user.updated_at = now
        db.add(user)
        db.commit()
        if _is_password_locked(user, now):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many failed password attempts. "
                    f"Try again in {PASSWORD_LOCKOUT_SECONDS} seconds."
                ),
            )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    _reset_password_attempt_state(user)
    user.last_login_at = now
    user.updated_at = now
    db.commit()
    db.refresh(user)

    session_seconds = payload.session_seconds or DEFAULT_SESSION_SECONDS
    session_seconds = max(1, min(session_seconds, MAX_SESSION_SECONDS))
    cookie_value = _create_session_cookie(user.id, session_seconds)
    _set_session_cookie(response, cookie_value, session_seconds)
    return LoginResponseSchema(
        user=UserSchema.model_validate(user),
        session_token=cookie_value,
    )


@router.get("/oauth/login")
def oauth_login(
    next_path: str = Query(default="/app", alias="next"),
) -> RedirectResponse:
    if auth_mode() != "oauth":
        raise HTTPException(status_code=404, detail="OAuth mode is not enabled")
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(32)
    safe_next = _safe_next_path(next_path)
    response = RedirectResponse(
        f"{central_auth_base_url()}/oauth/authorize?"
        + urlencode(
            {
                "response_type": "code",
                "client_id": oauth_client_id(),
                "redirect_uri": oauth_redirect_uri(),
                "scope": oauth_scope(),
                "state": state,
                "code_challenge": _pkce_challenge(verifier),
                "code_challenge_method": "S256",
            }
        ),
        status_code=302,
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE_NAME,
        value=_encode_oauth_state(
            {"state": state, "verifier": verifier, "next": safe_next}
        ),
        max_age=300,
        httponly=True,
        path=session_cookie_path(),
        samesite="lax",
        secure=False,
    )
    return response


@router.get("/oauth/callback")
def oauth_callback(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if auth_mode() != "oauth":
        raise HTTPException(status_code=404, detail="OAuth mode is not enabled")
    state_payload = _decode_oauth_state(request.cookies.get(OAUTH_STATE_COOKIE_NAME))
    if state_payload is None or state_payload.get("state") != state:
        redirect = _oauth_error_redirect("oauth_state")
        redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=session_cookie_path())
        return redirect
    verifier = state_payload.get("verifier")
    if verifier is None:
        redirect = _oauth_error_redirect("oauth_state")
        redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=session_cookie_path())
        return redirect
    try:
        userinfo = _exchange_oauth_code(code, verifier)
        user = _find_or_create_oauth_user(db, userinfo)
        db.commit()
    except (httpx.HTTPError, ValueError):
        db.rollback()
        redirect = _oauth_error_redirect("oauth_failed")
        redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=session_cookie_path())
        return redirect

    session_seconds = DEFAULT_SESSION_SECONDS
    cookie_value = _create_session_cookie(user.id, session_seconds)
    redirect_path = f"{app_base_path_no_trailing_slash()}{_safe_next_path(state_payload.get('next'))}"
    redirect = RedirectResponse(redirect_path, status_code=302)
    _set_session_cookie(redirect, cookie_value, session_seconds)
    redirect.delete_cookie(OAUTH_STATE_COOKIE_NAME, path=session_cookie_path())
    return redirect


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path=session_cookie_path())
    return None


@router.get("/me", response_model=UserSchema)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/profile", response_model=UserSchema)
def update_profile(
    payload: ProfileUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    now = datetime.now(tz=timezone.utc)
    changed = False
    data = payload.model_dump(exclude_unset=True)
    if auth_mode() == "oauth" and (
        "avatar_icon_id" in data or "new_password" in data or "current_password" in data
    ):
        raise HTTPException(
            status_code=409,
            detail="Profile image and password changes are handled by the configured auth site",
        )

    if "avatar_icon_id" in data:
        avatar_icon_id = payload.avatar_icon_id
        if avatar_icon_id is not None and not _is_icon_selectable_for_user(
            db, current_user.id, avatar_icon_id
        ):
            raise HTTPException(
                status_code=400, detail="avatar_icon_id is not selectable"
            )
        current_user.avatar_icon_id = avatar_icon_id
        changed = True

    if "paypal_account_id" in data:
        _validate_owned_wallet_account(
            db, current_user.id, payload.paypal_account_id, "paypal_account_id"
        )
        current_user.paypal_account_id = payload.paypal_account_id
        changed = True

    if "google_pay_account_id" in data:
        _validate_owned_wallet_account(
            db, current_user.id, payload.google_pay_account_id, "google_pay_account_id"
        )
        current_user.google_pay_account_id = payload.google_pay_account_id
        changed = True

    if "new_password" in data:
        if _is_password_locked(current_user, now):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many failed password attempts. "
                    f"Try again in {_seconds_until_unlock(current_user, now)} seconds."
                ),
            )
        if payload.new_password is None or not payload.new_password.strip():
            raise HTTPException(status_code=400, detail="new_password cannot be empty")
        if not payload.current_password:
            raise HTTPException(
                status_code=400,
                detail="current_password is required when changing password",
            )
        if not _verify_password(payload.current_password, current_user.password_hash):
            _record_failed_password_attempt(current_user, now)
            current_user.updated_at = now
            db.add(current_user)
            db.commit()
            if _is_password_locked(current_user, now):
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Too many failed password attempts. "
                        f"Try again in {PASSWORD_LOCKOUT_SECONDS} seconds."
                    ),
                )
            raise HTTPException(status_code=400, detail="current_password is invalid")
        _reset_password_attempt_state(current_user)
        current_user.password_hash = _hash_password(payload.new_password)
        current_user.password_changed_at = now
        changed = True
    elif "current_password" in data:
        raise HTTPException(
            status_code=400,
            detail="new_password is required when current_password is provided",
        )

    if changed:
        current_user.updated_at = now
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return current_user


@router.post("/widget-url/regenerate", response_model=UserSchema)
def regenerate_widget_url(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    now = datetime.now(tz=timezone.utc)
    current_user.widget_token = _generate_widget_token(db)
    current_user.widget_last_accessed_at = None
    current_user.widget_last_net_worth_cents = None
    current_user.updated_at = now
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/delete-account", status_code=204)
def delete_account(
    payload: DeleteAccountSchema,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if auth_mode() == "oauth":
        raise HTTPException(
            status_code=409,
            detail="Account deletion is handled by the configured auth site",
        )
    now = datetime.now(tz=timezone.utc)
    if _is_password_locked(current_user, now):
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many failed password attempts. "
                f"Try again in {_seconds_until_unlock(current_user, now)} seconds."
            ),
        )
    if not _verify_password(payload.current_password, current_user.password_hash):
        _record_failed_password_attempt(current_user, now)
        current_user.updated_at = now
        db.add(current_user)
        db.commit()
        if _is_password_locked(current_user, now):
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many failed password attempts. "
                    f"Try again in {PASSWORD_LOCKOUT_SECONDS} seconds."
                ),
            )
        raise HTTPException(status_code=400, detail="current_password is invalid")

    _reset_password_attempt_state(current_user)
    db.add(current_user)
    db.flush()

    user_id = current_user.id
    db.query(RegistrationCode).filter(
        RegistrationCode.created_by_user_id == user_id
    ).delete(synchronize_session=False)
    db.query(Expense).filter(Expense.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(ContractPosting).filter(ContractPosting.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Contract).filter(Contract.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AccountValueHistory).filter(AccountValueHistory.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(NetWorthDailySnapshot).filter(
        NetWorthDailySnapshot.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(Account).filter(Account.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Stock).filter(Stock.user_id == user_id).delete(synchronize_session=False)
    db.delete(current_user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path=session_cookie_path())
    return None
