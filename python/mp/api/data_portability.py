import base64
import binascii
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCryptoPosition,
    AccountStockPosition,
    AccountValueHistory,
    IconAsset,
    NetWorthDailySnapshot,
    Stock,
)
from mp.schema.contract import Contract, ContractPosting
from mp.schema.expense import Expense
from mp.schema.user import User

router = APIRouter(prefix="/data", tags=["data"])

PACKAGE_FORMAT = "money-planner-export"
PACKAGE_VERSION = 1
PAYLOAD_SCHEMA_VERSION = 3

# Intentional security-over-speed defaults for export package encryption.
KDF_ALGORITHM = "pbkdf2_sha256"
KDF_ITERATIONS = 1_500_000
KDF_SALT_BYTES = 64

DEFAULT_CONTRACT_EXPIRATION = date(2099, 1, 1)

ICON_TYPE_VALUES = {"Letters", "Gravatar", "Icon"}


class ExportRequestSchema(BaseModel):
    password: str | None = None


class ImportRequestSchema(BaseModel):
    package: dict[str, Any]
    password: str | None = None
    replace_existing: bool = True


class ImportResponseSchema(BaseModel):
    schema_version: int
    imported_icons: int
    imported_stocks: int
    imported_accounts: int
    imported_contracts: int
    imported_contract_postings: int
    imported_expenses: int
    imported_history_points: int
    imported_net_worth_snapshots: int


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _normalize_password(password: str | None) -> str | None:
    if password is None:
        return None
    trimmed = password.strip()
    return trimmed or None


def _derive_fernet_key(password: str, salt: bytes, iterations: int) -> bytes:
    raw_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )
    return base64.urlsafe_b64encode(raw_key)


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_date(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_decimal(value: Decimal) -> str:
    rendered = format(value, "f").rstrip("0").rstrip(".")
    return rendered or "0"


def _coerce_icon_type(raw: Any) -> str:
    if isinstance(raw, str) and raw in ICON_TYPE_VALUES:
        return raw
    return "Icon"


def _parse_uuid(value: Any, field: str) -> UUID:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field} must be a string UUID")
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid UUID for {field}"
        ) from exc


def _parse_optional_uuid(value: Any, field: str) -> UUID | None:
    if value is None:
        return None
    return _parse_uuid(value, field)


def _parse_int(value: Any, field: str, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise HTTPException(status_code=400, detail=f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"{field} must be an integer"
        ) from exc


def _parse_float(value: Any, field: str, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"{field} must be a number"
        ) from exc


def _parse_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=400, detail=f"{field} must be decimal-like"
            ) from exc
    raise HTTPException(status_code=400, detail=f"{field} must be decimal-like")


def _parse_optional_date(value: Any, field: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO date string"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO date string"
        ) from exc


def _parse_optional_datetime(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO datetime string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"{field} must be an ISO datetime string"
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _required_dict(raw: Any, field: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail=f"{field} must be an object")
    return raw


def _required_list(raw: Any, field: str) -> list[Any]:
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail=f"{field} must be an array")
    return raw


def _build_export_payload(db: Session, user_id: UUID) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    stocks = (
        db.query(Stock)
        .filter(Stock.user_id == user_id)
        .order_by(Stock.created_at.asc())
        .all()
    )
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)
        .order_by(Account.rank.desc(), Account.created_at.asc())
        .all()
    )
    contracts = (
        db.query(Contract)
        .filter(Contract.user_id == user_id)
        .order_by(
            Contract.category.asc(), Contract.rank.desc(), Contract.created_at.asc()
        )
        .all()
    )
    contract_postings = (
        db.query(ContractPosting)
        .filter(ContractPosting.user_id == user_id)
        .order_by(
            ContractPosting.effective_date.asc(), ContractPosting.created_at.asc()
        )
        .all()
    )
    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id)
        .order_by(Expense.category.asc(), Expense.name.asc(), Expense.created_at.asc())
        .all()
    )
    history_points = (
        db.query(AccountValueHistory)
        .filter(AccountValueHistory.user_id == user_id)
        .order_by(AccountValueHistory.recorded_at.asc(), AccountValueHistory.id.asc())
        .all()
    )
    net_worth_snapshots = (
        db.query(NetWorthDailySnapshot)
        .filter(NetWorthDailySnapshot.user_id == user_id)
        .order_by(NetWorthDailySnapshot.snapshot_date.asc())
        .all()
    )

    account_ids = [item.id for item in accounts]
    stock_positions = (
        db.query(AccountStockPosition)
        .filter(AccountStockPosition.account_id.in_(account_ids))
        .all()
        if account_ids
        else []
    )
    crypto_positions = (
        db.query(AccountCryptoPosition)
        .filter(AccountCryptoPosition.account_id.in_(account_ids))
        .all()
        if account_ids
        else []
    )
    cash_bills = (
        db.query(AccountCashDenomination)
        .filter(AccountCashDenomination.account_id.in_(account_ids))
        .all()
        if account_ids
        else []
    )

    stock_positions_by_account: dict[UUID, list[dict[str, Any]]] = {}
    for stock_position in stock_positions:
        stock_positions_by_account.setdefault(stock_position.account_id, []).append(
            {
                "stock_id": str(stock_position.stock_id),
                "quantity": _serialize_decimal(stock_position.quantity),
            }
        )

    crypto_positions_by_account: dict[UUID, list[dict[str, Any]]] = {}
    for crypto_position in crypto_positions:
        crypto_positions_by_account.setdefault(crypto_position.account_id, []).append(
            {
                "ticker": crypto_position.ticker,
                "quantity": _serialize_decimal(crypto_position.quantity),
                "exchange_rate_cents": int(crypto_position.exchange_rate_cents),
            }
        )

    cash_bills_by_account: dict[UUID, list[dict[str, Any]]] = {}
    for bill in cash_bills:
        cash_bills_by_account.setdefault(bill.account_id, []).append(
            {
                "denomination_cents": int(bill.denomination_cents),
                "quantity": int(bill.quantity),
            }
        )

    referenced_icon_ids: set[UUID] = set()
    if user.avatar_icon_id is not None:
        referenced_icon_ids.add(user.avatar_icon_id)
    for account in accounts:
        if account.icon_type == "Icon" and account.icon_id is not None:
            referenced_icon_ids.add(account.icon_id)
    for contract in contracts:
        if contract.icon_type == "Icon" and contract.icon_id is not None:
            referenced_icon_ids.add(contract.icon_id)
    for expense in expenses:
        if expense.icon_type == "Icon" and expense.icon_id is not None:
            referenced_icon_ids.add(expense.icon_id)
    icons = (
        db.query(IconAsset).filter(IconAsset.id.in_(list(referenced_icon_ids))).all()
        if referenced_icon_ids
        else []
    )

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "user_profile": {
            "avatar_icon_id": str(user.avatar_icon_id)
            if user.avatar_icon_id is not None
            else None,
            "last_login_at": _serialize_datetime(user.last_login_at),
            "password_changed_at": _serialize_datetime(user.password_changed_at),
            "created_at": _serialize_datetime(user.created_at),
            "updated_at": _serialize_datetime(user.updated_at),
        },
        "icons": [
            {
                "id": str(icon.id),
                "hash": icon.hash,
                "png_data_b64": base64.b64encode(icon.png_data).decode("ascii"),
            }
            for icon in icons
        ],
        "stocks": [
            {
                "id": str(stock.id),
                "name": stock.name,
                "ticker": stock.ticker,
                "exchange": stock.exchange,
                "last_price_cents": int(stock.last_price_cents or 0),
                "created_at": _serialize_datetime(stock.created_at),
                "updated_at": _serialize_datetime(stock.updated_at),
            }
            for stock in stocks
        ],
        "accounts": [
            {
                "id": str(account.id),
                "account_number": account.account_number,
                "name": account.name,
                "type": account.type,
                "organization": account.organization,
                "url": account.url,
                "notes": account.notes,
                "balance_cents": account.balance_cents,
                "fee_amount_cents": account.fee_amount_cents,
                "fee_period": account.fee_period,
                "routing_number": account.routing_number,
                "apy_bps": account.apy_bps,
                "compound_period": account.compound_period,
                "apr_bps": account.apr_bps,
                "billing_day": account.billing_day,
                "payment_day": account.payment_day,
                "last_payment_date": _serialize_date(account.last_payment_date),
                "expiration_date": _serialize_date(account.expiration_date),
                "cvc": account.cvc,
                "usd_balance_cents": account.usd_balance_cents,
                "retirement_account_type": account.retirement_account_type,
                "payment_amount_cents": account.payment_amount_cents,
                "icon_id": str(account.icon_id)
                if account.icon_id is not None
                else None,
                "icon_type": account.icon_type,
                "rank": float(account.rank),
                "last_update": _serialize_datetime(account.last_update),
                "created_at": _serialize_datetime(account.created_at),
                "stock_positions": stock_positions_by_account.get(account.id, []),
                "crypto_positions": crypto_positions_by_account.get(account.id, []),
                "cash_bills": cash_bills_by_account.get(account.id, []),
            }
            for account in accounts
        ],
        "contracts": [
            {
                "id": str(contract.id),
                "name": contract.name,
                "type": contract.type,
                "automatic": bool(contract.automatic),
                "amount_cents": int(contract.amount_cents),
                "organization": contract.organization,
                "icon_id": str(contract.icon_id)
                if contract.icon_id is not None
                else None,
                "icon_type": contract.icon_type,
                "rank": float(contract.rank),
                "linked_account_id": (
                    str(contract.linked_account_id)
                    if contract.linked_account_id is not None
                    else None
                ),
                "source_account_id": (
                    str(contract.source_account_id)
                    if contract.source_account_id is not None
                    else None
                ),
                "last_payment_date": _serialize_date(contract.last_payment_date),
                "payment_period": contract.payment_period,
                "payment_day": contract.payment_day,
                "expiration_date": _serialize_date(contract.expiration_date),
                "notes": contract.notes,
                "category": contract.category,
                "url": contract.url,
                "account_number": contract.account_number,
                "billing_day": contract.billing_day,
                "created_at": _serialize_datetime(contract.created_at),
                "updated_at": _serialize_datetime(contract.updated_at),
            }
            for contract in contracts
        ],
        "contract_postings": [
            {
                "id": str(posting.id),
                "contract_id": str(posting.contract_id),
                "effective_date": _serialize_date(posting.effective_date),
                "delta_cents": int(posting.delta_cents),
                "applied_at": _serialize_datetime(posting.applied_at),
                "created_at": _serialize_datetime(posting.created_at),
            }
            for posting in contract_postings
        ],
        "expenses": [
            {
                "id": str(expense.id),
                "name": expense.name,
                "category": expense.category,
                "icon_id": str(expense.icon_id)
                if expense.icon_id is not None
                else None,
                "icon_type": expense.icon_type,
                "estimated_amount_cents": int(expense.estimated_amount_cents or 0),
                "linked_account_id": (
                    str(expense.linked_account_id)
                    if expense.linked_account_id is not None
                    else None
                ),
                "enabled": bool(expense.enabled),
                "general_frequency": expense.general_frequency,
                "last_expensed_date": _serialize_date(expense.last_expensed_date),
                "next_expensed_date": _serialize_date(expense.next_expensed_date),
                "next_date_is_static": bool(expense.next_date_is_static),
                "created_at": _serialize_datetime(expense.created_at),
                "updated_at": _serialize_datetime(expense.updated_at),
            }
            for expense in expenses
        ],
        "account_value_history": [
            {
                "id": str(point.id),
                "account_id": str(point.account_id),
                "value_cents": int(point.value_cents),
                "recorded_at": _serialize_datetime(point.recorded_at),
            }
            for point in history_points
        ],
        "net_worth_daily_snapshot": [
            {
                "id": str(point.id),
                "snapshot_date": _serialize_date(point.snapshot_date),
                "value_cents": int(point.value_cents),
                "updated_at": _serialize_datetime(point.updated_at),
            }
            for point in net_worth_snapshots
        ],
    }


def _upgrade_payload_v0_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 1
    if "icons" not in upgraded:
        upgraded["icons"] = []
    return upgraded


def _upgrade_payload_v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 2
    if "user_profile" not in upgraded:
        upgraded["user_profile"] = {
            "avatar_icon_id": None,
            "last_login_at": None,
            "password_changed_at": None,
            "created_at": None,
            "updated_at": None,
        }
    if "contract_postings" not in upgraded:
        upgraded["contract_postings"] = []
    return upgraded


def _upgrade_payload_v2_to_v3(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 3
    profile = _required_dict(upgraded.get("user_profile"), "user_profile")
    if "failed_password_attempts" not in profile:
        profile["failed_password_attempts"] = 0
    if "password_lockout_until" not in profile:
        profile["password_lockout_until"] = None
    upgraded["user_profile"] = profile
    return upgraded


PAYLOAD_MIGRATIONS: dict[int, Any] = {
    0: _upgrade_payload_v0_to_v1,
    1: _upgrade_payload_v1_to_v2,
    2: _upgrade_payload_v2_to_v3,
}


def _migrate_payload_to_latest(raw_payload: dict[str, Any]) -> dict[str, Any]:
    schema_version = raw_payload.get("schema_version", 0)
    if not isinstance(schema_version, int):
        raise HTTPException(status_code=400, detail="schema_version must be an integer")
    if schema_version > PAYLOAD_SCHEMA_VERSION:
        raise HTTPException(
            status_code=400,
            detail=(
                "Package schema_version is newer than this server "
                f"({schema_version} > {PAYLOAD_SCHEMA_VERSION})"
            ),
        )

    payload = dict(raw_payload)
    version = schema_version
    while version < PAYLOAD_SCHEMA_VERSION:
        migration = PAYLOAD_MIGRATIONS.get(version)
        if migration is None:
            raise HTTPException(
                status_code=400,
                detail=f"No migration path for schema_version {version}",
            )
        payload = migration(payload)
        version += 1
    return payload


def _envelope_for_export(
    payload: dict[str, Any], password: str | None
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "format": PACKAGE_FORMAT,
        "package_version": PACKAGE_VERSION,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    if password is None:
        envelope["encrypted"] = False
        envelope["payload"] = payload
        return envelope

    salt = hashlib.sha512(uuid4().bytes + uuid4().bytes).digest()
    # Keep the salt intentionally very large to harden offline brute-force attempts.
    salt = salt + hashlib.sha512(salt).digest()
    key = _derive_fernet_key(password, salt, KDF_ITERATIONS)
    token = Fernet(key).encrypt(_json_bytes(payload))
    envelope["encrypted"] = True
    envelope["kdf"] = {
        "algorithm": KDF_ALGORITHM,
        "iterations": KDF_ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
    }
    envelope["cipher"] = "fernet"
    envelope["payload_b64"] = base64.b64encode(token).decode("ascii")
    return envelope


def _extract_payload_from_envelope(
    envelope: dict[str, Any], password: str | None
) -> dict[str, Any]:
    fmt = envelope.get("format")
    if fmt != PACKAGE_FORMAT:
        raise HTTPException(status_code=400, detail="Unsupported package format")
    package_version = envelope.get("package_version")
    if package_version != PACKAGE_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported package version")
    encrypted = envelope.get("encrypted")
    if not isinstance(encrypted, bool):
        raise HTTPException(status_code=400, detail="Package encrypted flag is invalid")

    if not encrypted:
        payload = envelope.get("payload")
        return _required_dict(payload, "payload")

    if password is None:
        raise HTTPException(
            status_code=400,
            detail="This package is encrypted and requires a password",
        )
    kdf = _required_dict(envelope.get("kdf"), "kdf")
    algorithm = kdf.get("algorithm")
    if algorithm != KDF_ALGORITHM:
        raise HTTPException(status_code=400, detail="Unsupported KDF algorithm")
    iterations = _parse_int(kdf.get("iterations"), "kdf.iterations")
    if iterations <= 0:
        raise HTTPException(status_code=400, detail="kdf.iterations must be > 0")
    salt_b64 = kdf.get("salt_b64")
    if not isinstance(salt_b64, str):
        raise HTTPException(
            status_code=400, detail="kdf.salt_b64 must be a base64 string"
        )
    try:
        salt = base64.b64decode(salt_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=400, detail="kdf.salt_b64 is invalid base64"
        ) from exc
    if len(salt) < KDF_SALT_BYTES:
        raise HTTPException(status_code=400, detail="kdf.salt_b64 is too short")

    payload_b64 = envelope.get("payload_b64")
    if not isinstance(payload_b64, str):
        raise HTTPException(
            status_code=400, detail="payload_b64 must be a base64 string"
        )
    try:
        encrypted_payload = base64.b64decode(payload_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=400, detail="payload_b64 is invalid base64"
        ) from exc
    key = _derive_fernet_key(password, salt, iterations)
    try:
        raw = Fernet(key).decrypt(encrypted_payload)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=400, detail="Invalid password or package payload"
        ) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail="Decrypted payload is invalid JSON"
        ) from exc
    return _required_dict(payload, "payload")


def _replace_user_data(
    db: Session, user_id: UUID, payload: dict[str, Any]
) -> ImportResponseSchema:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user_profile = _required_dict(payload.get("user_profile"), "user_profile")
    icons = _required_list(payload.get("icons"), "icons")
    stocks = _required_list(payload.get("stocks"), "stocks")
    accounts = _required_list(payload.get("accounts"), "accounts")
    contracts = _required_list(payload.get("contracts"), "contracts")
    contract_postings = _required_list(
        payload.get("contract_postings", []), "contract_postings"
    )
    expenses = _required_list(payload.get("expenses"), "expenses")
    history_points = _required_list(
        payload.get("account_value_history"), "account_value_history"
    )
    net_worth_snapshots = _required_list(
        payload.get("net_worth_daily_snapshot"), "net_worth_daily_snapshot"
    )

    db.query(Expense).filter(Expense.user_id == user_id).delete(
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
    db.flush()

    icon_id_map: dict[UUID, UUID] = {}
    imported_icons = 0
    for raw in icons:
        item = _required_dict(raw, "icons[]")
        old_id = _parse_uuid(item.get("id"), "icons[].id")
        hash_value = item.get("hash")
        png_data_b64 = item.get("png_data_b64")
        if not isinstance(hash_value, str) or len(hash_value) != 64:
            raise HTTPException(
                status_code=400, detail="icons[].hash must be sha256 hex"
            )
        if not isinstance(png_data_b64, str):
            raise HTTPException(
                status_code=400, detail="icons[].png_data_b64 must be string"
            )
        try:
            png_data = base64.b64decode(png_data_b64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(
                status_code=400, detail="icons[].png_data_b64 is invalid"
            ) from exc
        existing = db.query(IconAsset).filter(IconAsset.hash == hash_value).first()
        if existing is None:
            existing = IconAsset(
                hash=hash_value,
                created_by_user_id=user_id,
                png_data=png_data,
            )
            db.add(existing)
            db.flush()
        icon_id_map[old_id] = existing.id
        imported_icons += 1

    raw_avatar_icon_id = _parse_optional_uuid(
        user_profile.get("avatar_icon_id"), "user_profile.avatar_icon_id"
    )
    user.avatar_icon_id = (
        icon_id_map.get(raw_avatar_icon_id) if raw_avatar_icon_id is not None else None
    )
    user.last_login_at = _parse_optional_datetime(
        user_profile.get("last_login_at"), "user_profile.last_login_at"
    )
    user.password_changed_at = _parse_optional_datetime(
        user_profile.get("password_changed_at"), "user_profile.password_changed_at"
    )
    # Keep lockout counters local-only; do not restore from import payload.
    user.failed_password_attempts = 0
    user.password_lockout_until = None
    user.created_at = (
        _parse_optional_datetime(
            user_profile.get("created_at"), "user_profile.created_at"
        )
        or user.created_at
    )
    user.updated_at = _parse_optional_datetime(
        user_profile.get("updated_at"), "user_profile.updated_at"
    ) or datetime.now(tz=timezone.utc)
    db.add(user)

    stock_id_map: dict[UUID, UUID] = {}
    imported_stocks = 0
    for raw in stocks:
        item = _required_dict(raw, "stocks[]")
        old_id = _parse_uuid(item.get("id"), "stocks[].id")
        stock = Stock(
            id=uuid4(),
            user_id=user_id,
            name=str(item.get("name") or "").strip(),
            ticker=str(item.get("ticker") or "").strip(),
            exchange=str(item.get("exchange")).strip()
            if item.get("exchange") is not None
            else None,
            last_price_cents=_parse_int(
                item.get("last_price_cents"), "stocks[].last_price_cents"
            ),
            created_at=_parse_optional_datetime(
                item.get("created_at"), "stocks[].created_at"
            )
            or datetime.now(tz=timezone.utc),
            updated_at=_parse_optional_datetime(
                item.get("updated_at"), "stocks[].updated_at"
            )
            or datetime.now(tz=timezone.utc),
        )
        if not stock.name:
            raise HTTPException(status_code=400, detail="stocks[].name is required")
        if not stock.ticker:
            raise HTTPException(status_code=400, detail="stocks[].ticker is required")
        db.add(stock)
        stock_id_map[old_id] = stock.id
        imported_stocks += 1
    db.flush()

    account_id_map: dict[UUID, UUID] = {}
    imported_accounts = 0
    for raw in accounts:
        item = _required_dict(raw, "accounts[]")
        old_id = _parse_uuid(item.get("id"), "accounts[].id")
        icon_type = _coerce_icon_type(item.get("icon_type"))
        raw_icon_id = _parse_optional_uuid(item.get("icon_id"), "accounts[].icon_id")
        resolved_icon_id = (
            icon_id_map.get(raw_icon_id) if raw_icon_id is not None else None
        )
        account = Account(
            id=uuid4(),
            user_id=user_id,
            account_number=str(item.get("account_number") or "").strip(),
            name=str(item.get("name") or "").strip(),
            type=str(item.get("type") or "").strip(),
            organization=str(item.get("organization")).strip()
            if item.get("organization") is not None
            else None,
            url=str(item.get("url")).strip() if item.get("url") is not None else None,
            notes=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
            balance_cents=_parse_int(
                item.get("balance_cents"), "accounts[].balance_cents", default=0
            )
            if item.get("balance_cents") is not None
            else None,
            fee_amount_cents=_parse_int(
                item.get("fee_amount_cents"), "accounts[].fee_amount_cents", default=0
            )
            if item.get("fee_amount_cents") is not None
            else None,
            fee_period=str(item.get("fee_period")).strip()
            if item.get("fee_period") is not None
            else None,
            routing_number=str(item.get("routing_number")).strip()
            if item.get("routing_number") is not None
            else None,
            apy_bps=_parse_int(item.get("apy_bps"), "accounts[].apy_bps")
            if item.get("apy_bps") is not None
            else None,
            compound_period=str(item.get("compound_period")).strip()
            if item.get("compound_period") is not None
            else None,
            apr_bps=_parse_int(item.get("apr_bps"), "accounts[].apr_bps")
            if item.get("apr_bps") is not None
            else None,
            billing_day=_parse_int(item.get("billing_day"), "accounts[].billing_day")
            if item.get("billing_day") is not None
            else None,
            payment_day=_parse_int(item.get("payment_day"), "accounts[].payment_day")
            if item.get("payment_day") is not None
            else None,
            last_payment_date=_parse_optional_date(
                item.get("last_payment_date"), "accounts[].last_payment_date"
            ),
            expiration_date=_parse_optional_date(
                item.get("expiration_date"), "accounts[].expiration_date"
            ),
            cvc=str(item.get("cvc")).strip() if item.get("cvc") is not None else None,
            usd_balance_cents=_parse_int(
                item.get("usd_balance_cents"), "accounts[].usd_balance_cents"
            )
            if item.get("usd_balance_cents") is not None
            else None,
            retirement_account_type=str(item.get("retirement_account_type")).strip()
            if item.get("retirement_account_type") is not None
            else None,
            payment_amount_cents=_parse_int(
                item.get("payment_amount_cents"), "accounts[].payment_amount_cents"
            )
            if item.get("payment_amount_cents") is not None
            else None,
            icon_id=resolved_icon_id if icon_type == "Icon" else None,
            icon_type=icon_type,
            rank=_parse_float(item.get("rank"), "accounts[].rank", default=0.0),
            last_update=_parse_optional_datetime(
                item.get("last_update"), "accounts[].last_update"
            ),
            created_at=_parse_optional_datetime(
                item.get("created_at"), "accounts[].created_at"
            )
            or datetime.now(tz=timezone.utc),
        )
        if not account.account_number:
            raise HTTPException(
                status_code=400, detail="accounts[].account_number is required"
            )
        if not account.name:
            raise HTTPException(status_code=400, detail="accounts[].name is required")
        if not account.type:
            raise HTTPException(status_code=400, detail="accounts[].type is required")
        db.add(account)
        account_id_map[old_id] = account.id
        imported_accounts += 1
    db.flush()

    for raw in accounts:
        item = _required_dict(raw, "accounts[]")
        old_account_id = _parse_uuid(item.get("id"), "accounts[].id")
        new_account_id = account_id_map[old_account_id]
        for raw_pos in _required_list(
            item.get("stock_positions", []), "accounts[].stock_positions"
        ):
            pos = _required_dict(raw_pos, "accounts[].stock_positions[]")
            old_stock_id = _parse_uuid(
                pos.get("stock_id"), "accounts[].stock_positions[].stock_id"
            )
            new_stock_id = stock_id_map.get(old_stock_id)
            if new_stock_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="accounts[].stock_positions references unknown stock_id",
                )
            db.add(
                AccountStockPosition(
                    account_id=new_account_id,
                    stock_id=new_stock_id,
                    quantity=_parse_decimal(
                        pos.get("quantity"), "accounts[].stock_positions[].quantity"
                    ),
                )
            )
        for raw_pos in _required_list(
            item.get("crypto_positions", []), "accounts[].crypto_positions"
        ):
            pos = _required_dict(raw_pos, "accounts[].crypto_positions[]")
            ticker = str(pos.get("ticker") or "").strip()
            if not ticker:
                raise HTTPException(
                    status_code=400,
                    detail="accounts[].crypto_positions[].ticker is required",
                )
            db.add(
                AccountCryptoPosition(
                    account_id=new_account_id,
                    ticker=ticker,
                    quantity=_parse_decimal(
                        pos.get("quantity"), "accounts[].crypto_positions[].quantity"
                    ),
                    exchange_rate_cents=_parse_int(
                        pos.get("exchange_rate_cents"),
                        "accounts[].crypto_positions[].exchange_rate_cents",
                    ),
                )
            )
        for raw_bill in _required_list(
            item.get("cash_bills", []), "accounts[].cash_bills"
        ):
            bill = _required_dict(raw_bill, "accounts[].cash_bills[]")
            db.add(
                AccountCashDenomination(
                    account_id=new_account_id,
                    denomination_cents=_parse_int(
                        bill.get("denomination_cents"),
                        "accounts[].cash_bills[].denomination_cents",
                    ),
                    quantity=_parse_int(
                        bill.get("quantity"),
                        "accounts[].cash_bills[].quantity",
                    ),
                )
            )

    imported_contracts = 0
    contract_id_map: dict[UUID, UUID] = {}
    for raw in contracts:
        item = _required_dict(raw, "contracts[]")
        old_contract_id = _parse_uuid(item.get("id"), "contracts[].id")
        linked_old = _parse_optional_uuid(
            item.get("linked_account_id"), "contracts[].linked_account_id"
        )
        source_old = _parse_optional_uuid(
            item.get("source_account_id"), "contracts[].source_account_id"
        )
        raw_icon_id = _parse_optional_uuid(item.get("icon_id"), "contracts[].icon_id")
        icon_type = _coerce_icon_type(item.get("icon_type"))
        contract = Contract(
            id=uuid4(),
            user_id=user_id,
            name=str(item.get("name") or "").strip(),
            type=str(item.get("type") or "").strip(),
            automatic=bool(item.get("automatic", True)),
            amount_cents=_parse_int(
                item.get("amount_cents"), "contracts[].amount_cents"
            ),
            organization=str(item.get("organization")).strip()
            if item.get("organization") is not None
            else None,
            icon_id=icon_id_map.get(raw_icon_id)
            if icon_type == "Icon" and raw_icon_id is not None
            else None,
            icon_type=icon_type,
            rank=_parse_float(item.get("rank"), "contracts[].rank", default=0.0),
            linked_account_id=account_id_map.get(linked_old)
            if linked_old is not None
            else None,
            source_account_id=account_id_map.get(source_old)
            if source_old is not None
            else None,
            last_payment_date=_parse_optional_date(
                item.get("last_payment_date"), "contracts[].last_payment_date"
            ),
            payment_period=str(item.get("payment_period")).strip()
            if item.get("payment_period") is not None
            else None,
            payment_day=_parse_int(item.get("payment_day"), "contracts[].payment_day")
            if item.get("payment_day") is not None
            else None,
            expiration_date=_parse_optional_date(
                item.get("expiration_date"), "contracts[].expiration_date"
            )
            or DEFAULT_CONTRACT_EXPIRATION,
            notes=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
            category=str(item.get("category")).strip()
            if item.get("category") is not None
            else None,
            url=str(item.get("url")).strip() if item.get("url") is not None else None,
            account_number=str(item.get("account_number")).strip()
            if item.get("account_number") is not None
            else None,
            billing_day=_parse_int(item.get("billing_day"), "contracts[].billing_day")
            if item.get("billing_day") is not None
            else None,
            created_at=_parse_optional_datetime(
                item.get("created_at"), "contracts[].created_at"
            )
            or datetime.now(tz=timezone.utc),
            updated_at=_parse_optional_datetime(
                item.get("updated_at"), "contracts[].updated_at"
            )
            or datetime.now(tz=timezone.utc),
        )
        if not contract.name:
            raise HTTPException(status_code=400, detail="contracts[].name is required")
        if not contract.type:
            raise HTTPException(status_code=400, detail="contracts[].type is required")
        db.add(contract)
        contract_id_map[old_contract_id] = contract.id
        imported_contracts += 1

    imported_contract_postings = 0
    for raw in contract_postings:
        item = _required_dict(raw, "contract_postings[]")
        old_contract_id = _parse_uuid(
            item.get("contract_id"), "contract_postings[].contract_id"
        )
        mapped_contract_id = contract_id_map.get(old_contract_id)
        if mapped_contract_id is None:
            raise HTTPException(
                status_code=400,
                detail="contract_postings references unknown contract_id",
            )
        effective_date = _parse_optional_date(
            item.get("effective_date"), "contract_postings[].effective_date"
        )
        if effective_date is None:
            raise HTTPException(
                status_code=400,
                detail="contract_postings[].effective_date is required",
            )
        db.add(
            ContractPosting(
                id=uuid4(),
                contract_id=mapped_contract_id,
                user_id=user_id,
                effective_date=effective_date,
                delta_cents=_parse_int(
                    item.get("delta_cents"), "contract_postings[].delta_cents"
                ),
                applied_at=_parse_optional_datetime(
                    item.get("applied_at"), "contract_postings[].applied_at"
                ),
                created_at=_parse_optional_datetime(
                    item.get("created_at"), "contract_postings[].created_at"
                )
                or datetime.now(tz=timezone.utc),
            )
        )
        imported_contract_postings += 1

    imported_expenses = 0
    for raw in expenses:
        item = _required_dict(raw, "expenses[]")
        linked_old = _parse_optional_uuid(
            item.get("linked_account_id"), "expenses[].linked_account_id"
        )
        raw_icon_id = _parse_optional_uuid(item.get("icon_id"), "expenses[].icon_id")
        icon_type = _coerce_icon_type(item.get("icon_type"))
        expense = Expense(
            id=uuid4(),
            user_id=user_id,
            name=str(item.get("name") or "").strip(),
            category=str(item.get("category") or "").strip(),
            icon_id=icon_id_map.get(raw_icon_id)
            if icon_type == "Icon" and raw_icon_id is not None
            else None,
            icon_type=icon_type,
            estimated_amount_cents=_parse_int(
                item.get("estimated_amount_cents"), "expenses[].estimated_amount_cents"
            ),
            linked_account_id=account_id_map.get(linked_old)
            if linked_old is not None
            else None,
            enabled=bool(item.get("enabled", True)),
            general_frequency=str(item.get("general_frequency")).strip()
            if item.get("general_frequency") is not None
            else None,
            last_expensed_date=_parse_optional_date(
                item.get("last_expensed_date"), "expenses[].last_expensed_date"
            ),
            next_expensed_date=_parse_optional_date(
                item.get("next_expensed_date"), "expenses[].next_expensed_date"
            ),
            next_date_is_static=bool(item.get("next_date_is_static", False)),
            created_at=_parse_optional_datetime(
                item.get("created_at"), "expenses[].created_at"
            )
            or datetime.now(tz=timezone.utc),
            updated_at=_parse_optional_datetime(
                item.get("updated_at"), "expenses[].updated_at"
            )
            or datetime.now(tz=timezone.utc),
        )
        if not expense.name:
            raise HTTPException(status_code=400, detail="expenses[].name is required")
        if not expense.category:
            raise HTTPException(
                status_code=400, detail="expenses[].category is required"
            )
        db.add(expense)
        imported_expenses += 1

    imported_history_points = 0
    for raw in history_points:
        item = _required_dict(raw, "account_value_history[]")
        old_account_id = _parse_uuid(
            item.get("account_id"), "account_value_history[].account_id"
        )
        mapped_account_id = account_id_map.get(old_account_id)
        if mapped_account_id is None:
            raise HTTPException(
                status_code=400,
                detail="account_value_history references unknown account_id",
            )
        db.add(
            AccountValueHistory(
                id=uuid4(),
                account_id=mapped_account_id,
                user_id=user_id,
                value_cents=_parse_int(
                    item.get("value_cents"), "account_value_history[].value_cents"
                ),
                recorded_at=_parse_optional_datetime(
                    item.get("recorded_at"), "account_value_history[].recorded_at"
                )
                or datetime.now(tz=timezone.utc),
            )
        )
        imported_history_points += 1

    imported_snapshots = 0
    for raw in net_worth_snapshots:
        item = _required_dict(raw, "net_worth_daily_snapshot[]")
        snapshot_date = _parse_optional_date(
            item.get("snapshot_date"), "net_worth_daily_snapshot[].snapshot_date"
        )
        if snapshot_date is None:
            raise HTTPException(
                status_code=400,
                detail="net_worth_daily_snapshot[].snapshot_date is required",
            )
        db.add(
            NetWorthDailySnapshot(
                id=uuid4(),
                user_id=user_id,
                snapshot_date=snapshot_date,
                value_cents=_parse_int(
                    item.get("value_cents"), "net_worth_daily_snapshot[].value_cents"
                ),
                updated_at=_parse_optional_datetime(
                    item.get("updated_at"), "net_worth_daily_snapshot[].updated_at"
                )
                or datetime.now(tz=timezone.utc),
            )
        )
        imported_snapshots += 1

    return ImportResponseSchema(
        schema_version=PAYLOAD_SCHEMA_VERSION,
        imported_icons=imported_icons,
        imported_stocks=imported_stocks,
        imported_accounts=imported_accounts,
        imported_contracts=imported_contracts,
        imported_contract_postings=imported_contract_postings,
        imported_expenses=imported_expenses,
        imported_history_points=imported_history_points,
        imported_net_worth_snapshots=imported_snapshots,
    )


@router.post("/export")
def export_data(
    payload: ExportRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    normalized_password = _normalize_password(payload.password)
    export_payload = _build_export_payload(db, current_user.id)
    return _envelope_for_export(export_payload, normalized_password)


@router.post("/import", response_model=ImportResponseSchema)
def import_data(
    payload: ImportRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportResponseSchema:
    if payload.replace_existing is not True:
        raise HTTPException(
            status_code=400,
            detail="Only replace_existing=true is currently supported",
        )

    normalized_password = _normalize_password(payload.password)
    raw_data = _extract_payload_from_envelope(payload.package, normalized_password)
    migrated_data = _migrate_payload_to_latest(raw_data)
    result = _replace_user_data(db, current_user.id, migrated_data)
    db.commit()
    return result
