from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Request
from sqlalchemy.orm import Session

from mp.config import agent_integration_token_secret, central_auth_base_url
from mp.schema.user import User

TOKEN_PREFIX = "agent-v1"
ISSUER = "ghwiz-agent"
AUDIENCE = "budget"


@dataclass(frozen=True)
class AgentTokenClaims:
    subject: str
    scope: str
    expires_at: int
    audience: str


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str, secret: str) -> str:
    return _b64encode(
        hmac.new(
            secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256
        ).digest()
    )


def encode_agent_token(
    *,
    secret: str,
    subject: str,
    scope: str,
    audience: str = AUDIENCE,
    expires_at: int | None = None,
) -> str:
    payload = {
        "iss": ISSUER,
        "aud": audience,
        "sub": subject,
        "scope": scope,
        "iat": int(time.time()),
        "exp": expires_at if expires_at is not None else int(time.time()) + 300,
    }
    encoded_payload = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{TOKEN_PREFIX}.{encoded_payload}.{_sign(encoded_payload, secret)}"


def decode_agent_token(
    token: str, *, secret: str, audience: str = AUDIENCE
) -> AgentTokenClaims | None:
    prefix, separator, rest = token.partition(".")
    payload, separator_two, signature = rest.partition(".")
    if (
        prefix != TOKEN_PREFIX
        or separator != "."
        or separator_two != "."
        or not payload
        or not signature
    ):
        return None
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return None
    try:
        claims = json.loads(_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if claims.get("iss") != ISSUER or claims.get("aud") != audience:
        return None
    subject = claims.get("sub")
    scope = claims.get("scope")
    expires_at = claims.get("exp")
    if (
        not isinstance(subject, str)
        or not isinstance(scope, str)
        or not isinstance(expires_at, int)
    ):
        return None
    if expires_at <= int(time.time()):
        return None
    return AgentTokenClaims(
        subject=subject, scope=scope, expires_at=expires_at, audience=audience
    )


def required_agent_scope(request: Request) -> str | None:
    path = request.url.path
    if path.startswith("/api/"):
        path = path[4:]
    path = path.rstrip("/") or "/"
    method = request.method.upper()
    segments = [segment for segment in path.split("/") if segment]

    if segments == ["accounts"] and method == "GET":
        return "budget.list_accounts"
    if segments[:3] == ["accounts", "net-worth", "history"] and method == "GET":
        return "budget.get_net_worth_history"
    if segments[:3] == ["accounts", "net-worth", "forecast"] and method == "GET":
        return "budget.get_net_worth_forecast"
    if len(segments) == 2 and segments[0] == "accounts" and method == "GET":
        return "budget.get_account"
    if (
        len(segments) == 3
        and segments[0] == "accounts"
        and segments[2] == "value"
        and method == "PUT"
    ):
        return "budget.update_account_value"
    if segments == ["transfers"] and method == "GET":
        return "budget.list_transfers"
    if segments == ["contracts"] and method == "GET":
        return "budget.list_contracts"
    if segments == ["contracts"] and method == "POST":
        return "budget.create_contract"
    if len(segments) == 2 and segments[0] == "contracts" and method == "PUT":
        return "budget.update_contract"
    if len(segments) == 2 and segments[0] == "contracts" and method == "DELETE":
        return "budget.delete_contract"
    if segments == ["expenses"] and method == "GET":
        return "budget.list_expenses"
    if segments == ["expenses"] and method == "POST":
        return "budget.create_expense"
    if len(segments) == 2 and segments[0] == "expenses" and method == "PUT":
        return "budget.update_expense"
    if len(segments) == 2 and segments[0] == "expenses" and method == "DELETE":
        return "budget.delete_expense"
    if segments == ["investments"] and method == "GET":
        return "budget.list_investments"
    if segments == ["logs"] and method == "GET":
        return "budget.list_audit_logs"
    return None


def user_from_agent_token(request: Request, db: Session, token: str) -> User | None:
    secret = agent_integration_token_secret()
    required_scope = required_agent_scope(request)
    if not secret or required_scope is None:
        return None
    claims = decode_agent_token(token, secret=secret, audience=AUDIENCE)
    if claims is None or claims.scope != required_scope:
        return None
    return (
        db.query(User)
        .filter_by(
            identity_provider=central_auth_base_url(), external_subject=claims.subject
        )
        .first()
    )
