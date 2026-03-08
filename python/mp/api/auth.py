import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from mp.db import get_db
from mp.sample_data import ensure_example_data_for_user
from mp.schema.account import Account, DefaultIcon, IconAsset, Organization
from mp.schema.contract import Contract
from mp.schema.expense import Expense
from mp.schema.user import (
    LoginResponseSchema,
    LoginSchema,
    ProfileUpdateSchema,
    User,
    UserCreateSchema,
    UserSchema,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = "mp_session"
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


def _seconds_until_unlock(user: User, now: datetime) -> int:
    lockout_until = user.password_lockout_until
    if lockout_until is None:
        return 0
    remaining = (lockout_until - now).total_seconds()
    return max(0, int(remaining + 0.999))


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
    existing = db.query(User).filter_by(username=payload.username).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Username already exists")

    now = datetime.now(tz=timezone.utc)
    existing_user_count = db.query(User).count()
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
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        max_age=session_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return LoginResponseSchema(
        user=UserSchema.model_validate(user),
        session_token=cookie_value,
    )


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
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
