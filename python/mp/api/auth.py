import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from mp.db import get_db
from mp.sample_data import ensure_example_data_for_user
from mp.schema.user import (
    LoginResponseSchema,
    LoginSchema,
    User,
    UserCreateSchema,
    UserSchema,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = "mp_session"
DEFAULT_SESSION_SECONDS = 24 * 60 * 60
MAX_SESSION_SECONDS = 30 * 24 * 60 * 60
_fernet: Fernet | None = None


def initialize_session_signing_key() -> None:
    global _fernet
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

    user = User(
        username=payload.username,
        password_hash=_hash_password(payload.password),
        example_data=payload.add_example_data,
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
    user = db.query(User).filter_by(username=payload.username).first()
    if user is None or not _verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

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
