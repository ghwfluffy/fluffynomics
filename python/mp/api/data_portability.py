import base64
import binascii
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
import yaml

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.db.account_history import compute_user_net_worth_cents
from mp.schema.account import (
    Account,
    AccountTransfer,
    AccountCashDenomination,
    AccountCryptoPosition,
    AccountStockPosition,
    AccountValueHistory,
    DefaultIcon,
    IconAsset,
    NetWorthDailySnapshot,
    Organization,
    Stock,
)
from mp.schema.audit_log import AuditLogEvent
from mp.schema.contract import Contract, ContractPosting
from mp.schema.expense import Expense
from mp.schema.investment import Investment
from mp.schema.user import User

router = APIRouter(prefix="/data", tags=["data"])

PACKAGE_FORMAT = "money-planner-export"
PACKAGE_VERSION = 1
PAYLOAD_SCHEMA_VERSION = 12

# Intentional security-over-speed defaults for export package encryption.
KDF_ALGORITHM = "pbkdf2_sha256"
KDF_ITERATIONS = 1_500_000
KDF_SALT_BYTES = 64

DEFAULT_CONTRACT_EXPIRATION = date(2099, 1, 1)

ICON_TYPE_VALUES = {"Letters", "Gravatar", "Icon"}


class ExportRequestSchema(BaseModel):
    password: str | None = None


class ImportRequestSchema(BaseModel):
    package: Any
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
    imported_investments: int
    imported_history_points: int
    imported_net_worth_snapshots: int
    imported_account_transfers: int
    imported_audit_log_events: int


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


def _parse_bool(value: Any, field: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise HTTPException(status_code=400, detail=f"{field} must be a boolean")


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


def _is_export_envelope(raw: Any) -> bool:
    return (
        isinstance(raw, dict)
        and raw.get("format") == PACKAGE_FORMAT
        and "package_version" in raw
    )


def _is_legacy_payload(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    legacy_keys = {"assets", "contracts", "budget", "bonds"}
    return any(key in raw for key in legacy_keys) and "schema_version" not in raw


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = normalized.strip("-")
    return normalized or "item"


def _parse_optional_iso_date(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError:
        return None


def _dollars_to_cents(raw: Any) -> int:
    if raw is None:
        return 0
    try:
        return int(round(float(raw) * 100))
    except (TypeError, ValueError):
        return 0


def _legacy_account_type(raw: str | None, *, default: str = "checking") -> str:
    value = (raw or "").strip().lower()
    if value in {
        "checking",
        "savings",
        "cash",
        "line_of_credit",
        "credit_card",
        "stocks_account",
        "investment_fund",
        "crypto_exchange",
        "crypto_wallet",
        "retirement",
        "loan",
        "rewards_card",
    }:
        return value
    mapping = {
        "checking account": "checking",
        "savings account": "savings",
        "cash": "cash",
        "credit card": "credit_card",
        "line of credit": "line_of_credit",
        "loan": "loan",
        "investment fund": "investment_fund",
        "retirement": "retirement",
    }
    if value in mapping:
        return mapping[value]
    if "credit" in value and "card" in value:
        return "credit_card"
    if "line" in value and "credit" in value:
        return "line_of_credit"
    if "loan" in value or "mortgage" in value:
        return "loan"
    if "retirement" in value or "ira" in value or "401" in value:
        return "retirement"
    if "stock" in value or "broker" in value or "fund" in value:
        return "stocks_account"
    if "crypto" in value:
        if "wallet" in value:
            return "crypto_wallet"
        return "crypto_exchange"
    return default


def _normalize_legacy_period(raw: Any) -> str:
    return re.sub(r"\s+", " ", str(raw or "").strip().lower())


def _legacy_value_as_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _normalize_retirement_account_type(raw: Any) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "", value.lower())
    mapping = {
        "roth": "roth",
        "rothira": "roth",
        "simple": "simple",
        "simpleira": "simple",
        "401k": "401k",
    }
    return mapping.get(normalized)


def _canonical_org_name(raw: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (raw or "").strip().lower())


def _matches_organization(name: str | None, org: str | None) -> bool:
    left = _canonical_org_name(name)
    right = _canonical_org_name(org)
    if not left or not right:
        return False
    return left in right or right in left


def _legacy_org_alias_match(name: str | None, org: str | None) -> bool:
    canonical_name = _canonical_org_name(name)
    canonical_org = _canonical_org_name(org)
    if not canonical_name or not canonical_org:
        return False
    if canonical_org == "wellsfargo" and re.search(r"\bwf\b", (name or "").lower()):
        return True
    if canonical_org == "citibank" and "citicard" in canonical_name:
        return True
    return False


def _legacy_wallet_alias(raw: str | None) -> str | None:
    canonical = _canonical_org_name(raw)
    if not canonical:
        return None
    if "paypal" in canonical:
        return "paypal"
    if "googlepay" in canonical or canonical.startswith("gpay"):
        return "google_pay"
    return None


def _legacy_org_match_score(name: str | None, org: str | None) -> tuple[int, int, int]:
    canonical_name = _canonical_org_name(name)
    canonical_org = _canonical_org_name(org)
    if not canonical_name or not canonical_org:
        return (0, 0, 0)
    alias_boost = 1 if _legacy_org_alias_match(name, org) else 0
    direct_match = canonical_name in canonical_org or canonical_org in canonical_name
    if not alias_boost and not direct_match:
        return (0, 0, 0)
    return (
        2 if alias_boost else 1,
        min(len(canonical_name), len(canonical_org)),
        len(canonical_org),
    )


def _date_plus_years(base: date, years: int) -> date:
    try:
        return base.replace(year=base.year + years)
    except ValueError:
        # Handle leap day.
        return base.replace(month=2, day=28, year=base.year + years)


def _legacy_next_payment_is_far_future(raw_next_payment: Any, years: int = 30) -> bool:
    next_payment = _parse_optional_iso_date(raw_next_payment)
    if next_payment is None:
        return False
    return next_payment > _date_plus_years(date.today(), years)


def _legacy_extract_date(raw: dict[str, Any], *keys: str) -> date | None:
    for key in keys:
        if key not in raw:
            continue
        parsed = _parse_optional_iso_date(raw.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_far_future_date(value: date | None, years: int = 30) -> bool:
    if value is None:
        return False
    return value > _date_plus_years(date.today(), years)


def _append_note(base: str | None, line: str) -> str:
    rendered = line.strip()
    if not rendered:
        return (base or "").strip()
    root = (base or "").strip()
    if not root:
        return rendered
    return f"{root}\n{rendered}"


def _legacy_notes(
    raw: dict[str, Any],
    *,
    consumed_keys: set[str],
    seed_note: str | None = None,
) -> str | None:
    note = (seed_note or "").strip() or None
    extras: dict[str, Any] = {}
    for key, value in raw.items():
        if key in consumed_keys:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        extras[key] = value
    if extras:
        note = _append_note(
            note,
            f"Legacy extras: {json.dumps(extras, sort_keys=True, ensure_ascii=True)}",
        )
    return note


def _legacy_contract_period(
    raw_period: Any,
    last_payment_date: date | None,
    next_payment_date: date | None,
    unsupported_periods: set[str],
) -> tuple[str | None, int | None]:
    period = _normalize_legacy_period(raw_period)
    reference_date = next_payment_date or last_payment_date
    payment_day = reference_date.day if reference_date is not None else 1
    reference = reference_date or date.today()
    every_n_months_match = re.fullmatch(r"(\d+)\s+months?", period)
    every_n_weeks_match = re.fullmatch(r"(?:every\s+)?(\d+)\s+weeks?", period)
    every_n_years_match = re.fullmatch(r"(\d+)\s+years?", period)
    if period in {"", "month", "1 month", "monthly"}:
        return json.dumps({"kind": "monthly_day", "day": payment_day}), payment_day
    if period in {"half month", "half-month", "semi monthly", "semimonthly"}:
        return json.dumps({"kind": "twice_monthly", "day_1": 15, "day_2": 31}), 15
    if every_n_months_match is not None:
        interval_months = int(every_n_months_match.group(1))
        return (
            json.dumps(
                {
                    "kind": "every_n_months_day",
                    "interval_months": interval_months,
                    "day": payment_day,
                    "start_date": reference.isoformat(),
                }
            ),
            payment_day,
        )
    if period in {"2 weeks", "2 week", "biweekly"}:
        weekday = reference_date.weekday() if reference_date is not None else 0
        start = last_payment_date or next_payment_date
        payload = {
            "kind": "biweekly_weekday",
            "weekday": weekday,
            "start_date": (start or date.today()).isoformat(),
        }
        return json.dumps(payload), None
    if every_n_weeks_match is not None:
        interval_weeks = int(every_n_weeks_match.group(1))
        weekday = reference_date.weekday() if reference_date is not None else 0
        start = last_payment_date or next_payment_date
        if interval_weeks == 1:
            return (
                json.dumps({"kind": "weekly_weekday", "weekday": weekday}),
                None,
            )
        if interval_weeks == 2:
            return (
                json.dumps(
                    {
                        "kind": "biweekly_weekday",
                        "weekday": weekday,
                        "start_date": (start or date.today()).isoformat(),
                    }
                ),
                None,
            )
        return (
            json.dumps(
                {
                    "kind": "every_n_weeks_weekday",
                    "interval_weeks": interval_weeks,
                    "weekday": weekday,
                    "start_date": (start or date.today()).isoformat(),
                }
            ),
            None,
        )
    if period in {"week", "weekly"}:
        weekday = reference_date.weekday() if reference_date is not None else 0
        return json.dumps({"kind": "weekly_weekday", "weekday": weekday}), None
    if period in {"year", "yearly", "1 year"}:
        ref = reference
        return (
            json.dumps(
                {"kind": "yearly_month_day", "month": ref.month, "day": ref.day}
            ),
            payment_day,
        )
    if every_n_years_match is not None:
        interval_years = int(every_n_years_match.group(1))
        return (
            json.dumps(
                {
                    "kind": "every_n_years_month_day",
                    "interval_years": interval_years,
                    "month": reference.month,
                    "day": reference.day,
                    "start_date": reference.isoformat(),
                }
            ),
            payment_day,
        )
    unsupported_periods.add(period or "<empty>")
    return None, payment_day


def _legacy_expense_frequency(
    raw_period: Any, unsupported_periods: set[str]
) -> str | None:
    period = _normalize_legacy_period(raw_period)
    every_n_months_match = re.fullmatch(r"(\d+)\s+months?", period)
    every_n_weeks_match = re.fullmatch(r"(?:every\s+)?(\d+)\s+weeks?", period)
    every_n_years_match = re.fullmatch(r"(\d+)\s+years?", period)
    if period in {"", "month", "1 month", "monthly"}:
        return json.dumps({"kind": "monthly_day", "day": 1})
    if period in {"half month", "half-month", "semi monthly", "semimonthly"}:
        return json.dumps({"kind": "twice_monthly", "day_1": 15, "day_2": 31})
    if every_n_months_match is not None:
        interval_months = int(every_n_months_match.group(1))
        return json.dumps(
            {
                "kind": "every_n_months_day",
                "interval_months": interval_months,
                "day": 1,
                "start_date": "2025-01-01",
            }
        )
    if period in {"2 weeks", "2 week", "biweekly"}:
        return json.dumps(
            {"kind": "biweekly_weekday", "weekday": 0, "start_date": "2025-01-06"}
        )
    if every_n_weeks_match is not None:
        interval_weeks = int(every_n_weeks_match.group(1))
        if interval_weeks == 1:
            return json.dumps({"kind": "weekly_weekday", "weekday": 0})
        if interval_weeks == 2:
            return json.dumps(
                {"kind": "biweekly_weekday", "weekday": 0, "start_date": "2025-01-06"}
            )
        return json.dumps(
            {
                "kind": "every_n_weeks_weekday",
                "interval_weeks": interval_weeks,
                "weekday": 0,
                "start_date": "2025-01-06",
            }
        )
    if period in {"week", "weekly"}:
        return json.dumps({"kind": "weekly_weekday", "weekday": 0})
    if period in {"year", "yearly", "1 year"}:
        return json.dumps({"kind": "yearly_month_day", "month": 1, "day": 1})
    if every_n_years_match is not None:
        interval_years = int(every_n_years_match.group(1))
        return json.dumps(
            {
                "kind": "every_n_years_month_day",
                "interval_years": interval_years,
                "month": 1,
                "day": 1,
                "start_date": "2025-01-01",
            }
        )
    unsupported_periods.add(period or "<empty>")
    return None


def _legacy_account_payload(
    *,
    account_id: str,
    account_number: str,
    name: str,
    account_type: str,
    organization_name: str | None,
    url: str | None,
    notes: str | None,
    rank: int,
    now_iso: str,
    balance_cents: int | None = None,
    fee_amount_cents: int | None = None,
    fee_period: str | None = None,
    routing_number: str | None = None,
    apy_bps: int | None = None,
    compound_period: str | None = None,
    apr_bps: int | None = None,
    billing_day: int | None = None,
    payment_day: int | None = None,
    last_payment_date: date | None = None,
    expiration_date: date | None = None,
    closed: bool = False,
    max_credit_cents: int | None = None,
    rewards_balance_cents: int | None = None,
    icon_id: str | None = None,
    cvc: str | None = None,
    usd_balance_cents: int | None = None,
    retirement_account_type: str | None = None,
    payment_amount_cents: int | None = None,
    stock_positions: list[dict[str, Any]] | None = None,
    crypto_positions: list[dict[str, Any]] | None = None,
    cash_bills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": account_id,
        "account_number": account_number,
        "name": name,
        "type": account_type,
        "organization": organization_name,
        "url": url,
        "notes": notes,
        "balance_cents": balance_cents,
        "fee_amount_cents": fee_amount_cents,
        "fee_period": fee_period,
        "routing_number": routing_number,
        "apy_bps": apy_bps,
        "compound_period": compound_period,
        "apr_bps": apr_bps,
        "billing_day": billing_day,
        "payment_day": payment_day,
        "last_payment_date": last_payment_date.isoformat()
        if last_payment_date
        else None,
        "expiration_date": expiration_date.isoformat() if expiration_date else None,
        "closed": bool(closed),
        "max_credit_cents": max_credit_cents,
        "rewards_balance_cents": rewards_balance_cents,
        "cvc": cvc,
        "usd_balance_cents": usd_balance_cents,
        "retirement_account_type": retirement_account_type,
        "payment_amount_cents": payment_amount_cents,
        "icon_id": icon_id,
        "icon_type": "Icon" if icon_id is not None else "Letters",
        "rank": float(rank),
        "last_update": None,
        "created_at": now_iso,
        "stock_positions": stock_positions or [],
        "crypto_positions": crypto_positions or [],
        "cash_bills": cash_bills or [],
    }


def _coerce_import_package(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Import package text is empty")
        try:
            parsed_json = json.loads(text)
            if isinstance(parsed_json, dict):
                return parsed_json
        except json.JSONDecodeError:
            pass
        try:
            parsed_yaml = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=400, detail="Import package is not valid JSON or YAML"
            ) from exc
        if not isinstance(parsed_yaml, dict):
            raise HTTPException(
                status_code=400, detail="Import package root must be an object"
            )
        return parsed_yaml
    raise HTTPException(
        status_code=400, detail="Import package must be an object or text"
    )


def _convert_legacy_payload_to_latest(
    raw_payload: dict[str, Any], user: User, db: Session
) -> dict[str, Any]:
    default_organizations = (
        db.query(Organization).filter(Organization.is_default.is_(True)).all()
    )
    texas_default_icon = (
        db.query(DefaultIcon).filter(DefaultIcon.key == "texas").first()
    )
    texas_icon_id = (
        str(texas_default_icon.icon_id) if texas_default_icon is not None else None
    )

    def matched_default_org(name: str) -> Organization | None:
        best_org: Organization | None = None
        best_score = (0, 0, 0)
        for org in default_organizations:
            score = _legacy_org_match_score(name, org.name)
            if score > best_score:
                best_score = score
                best_org = org
        return best_org

    def matched_icon_id(name: str, org: Organization | None) -> str | None:
        if org is not None and org.icon_id is not None:
            return str(org.icon_id)
        if texas_icon_id is not None and "texas" in _canonical_org_name(name):
            return texas_icon_id
        return None

    now_iso = datetime.now(tz=timezone.utc).isoformat()
    assets = _required_list(raw_payload.get("assets", []), "legacy.assets")
    payables = _required_list(raw_payload.get("payables", []), "legacy.payables")
    liabilities = _required_list(
        raw_payload.get("liabilities", []), "legacy.liabilities"
    )
    closed_accounts = _required_list(raw_payload.get("closed", []), "legacy.closed")
    funds = _required_list(raw_payload.get("funds", []), "legacy.funds")
    retirement = _required_list(raw_payload.get("retirement", []), "legacy.retirement")
    stock_accounts = _required_list(raw_payload.get("stocks", []), "legacy.stocks")
    crypto_accounts = _required_list(raw_payload.get("crypto", []), "legacy.crypto")
    receivables = _required_list(
        raw_payload.get("receivables", []), "legacy.receivables"
    )
    contracts = _required_list(raw_payload.get("contracts", []), "legacy.contracts")
    expenses = _required_list(raw_payload.get("expenses", []), "legacy.expenses")

    account_id_by_name: dict[str, str] = {}
    stock_id_by_ticker: dict[str, str] = {}
    converted_accounts: list[dict[str, Any]] = []
    converted_stocks: list[dict[str, Any]] = []
    converted_expenses: list[dict[str, Any]] = []
    pending_retirement_contributions: list[tuple[str, int, str | None]] = []

    def reserve_account_id(name: str) -> str:
        account_id = str(uuid4())
        key = name.strip().lower()
        if key and key not in account_id_by_name:
            account_id_by_name[key] = account_id
        return account_id

    account_rank = 1
    stock_rank = 1

    def ensure_stock_id(ticker: str, fallback_name: str, price_cents: int) -> str:
        nonlocal stock_rank
        key = ticker.strip().upper()
        if not key:
            key = f"LEGACY-{stock_rank}"
        existing = stock_id_by_ticker.get(key)
        if existing is not None:
            return existing
        stock_id = str(uuid4())
        stock_id_by_ticker[key] = stock_id
        converted_stocks.append(
            {
                "id": stock_id,
                "name": fallback_name.strip() or key,
                "ticker": key,
                "exchange": None,
                "last_price_cents": price_cents,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )
        stock_rank += 1
        return stock_id

    def append_account(record: dict[str, Any]) -> None:
        nonlocal account_rank
        converted_accounts.append(record)
        account_rank += 1

    for index, raw_asset in enumerate(assets, start=1):
        asset = _required_dict(raw_asset, "legacy.assets[]")
        name = str(asset.get("name") or "").strip() or f"Legacy Account {index}"
        account_id = reserve_account_id(name)
        account_type = _legacy_account_type(
            str(asset.get("type") or ""), default="checking"
        )
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        denominations_raw = asset.get("denominations")
        cash_bills: list[dict[str, Any]] = []
        if isinstance(denominations_raw, dict):
            for denom, qty in denominations_raw.items():
                try:
                    denomination = int(denom)
                    quantity = int(qty)
                except (TypeError, ValueError):
                    continue
                cash_bills.append(
                    {
                        "denomination_cents": denomination * 100,
                        "quantity": max(0, quantity),
                    }
                )
        notes = _legacy_notes(
            asset,
            consumed_keys={
                "name",
                "type",
                "url",
                "balance",
                "notes",
                "apr",
                "denominations",
            },
            seed_note=str(asset.get("notes")).strip()
            if asset.get("notes") is not None
            else None,
        )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-ASSET-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type=account_type,
                organization_name=organization_name,
                url=str(asset.get("url")).strip()
                if asset.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(asset.get("balance")),
                apy_bps=(
                    int(round(float(asset.get("apr", 0)) * 100))
                    if asset.get("apr") is not None
                    else None
                ),
                cash_bills=cash_bills,
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_payable in enumerate(payables, start=1):
        payable = _required_dict(raw_payable, "legacy.payables[]")
        name = str(payable.get("name") or "").strip() or f"Legacy Payable {index}"
        account_id = reserve_account_id(name)
        base_type = _legacy_account_type(
            str(payable.get("type") or ""), default="credit_card"
        )
        if base_type not in {"credit_card", "line_of_credit", "loan"}:
            base_type = "credit_card"
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        payable_balance_cents = _dollars_to_cents(payable.get("balance"))
        notes = _legacy_notes(
            payable,
            consumed_keys={
                "name",
                "type",
                "url",
                "credit",
                "lastPayment",
                "nextPayment",
                "paymentDay",
                "apr",
                "balance",
                "rewards",
                "notes",
            },
            seed_note=str(payable.get("notes")).strip()
            if payable.get("notes") is not None
            else None,
        )
        if payable.get("credit") is not None:
            notes = _append_note(
                notes,
                f"Legacy credit_limit: {_legacy_value_as_text(payable.get('credit'))}",
            )
        if payable.get("rewards") is not None:
            notes = _append_note(
                notes,
                f"Legacy rewards_balance: {_legacy_value_as_text(payable.get('rewards'))}",
            )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-PAYABLE-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type=base_type,
                organization_name=organization_name,
                url=str(payable.get("url")).strip()
                if payable.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=payable_balance_cents,
                apr_bps=(
                    int(round(float(payable.get("apr", 0)) * 100))
                    if payable.get("apr") is not None
                    else None
                ),
                payment_day=_parse_int(
                    payable.get("paymentDay"), "legacy.payables[].paymentDay"
                )
                if payable.get("paymentDay") is not None
                else None,
                last_payment_date=_parse_optional_iso_date(payable.get("lastPayment")),
                closed=(
                    (base_type == "loan" and payable_balance_cents == 0)
                    or _legacy_next_payment_is_far_future(payable.get("nextPayment"))
                ),
                max_credit_cents=_dollars_to_cents(payable.get("credit")),
                rewards_balance_cents=_dollars_to_cents(payable.get("rewards")),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_liability in enumerate(liabilities, start=1):
        liability = _required_dict(raw_liability, "legacy.liabilities[]")
        name = str(liability.get("name") or "").strip() or f"Legacy Liability {index}"
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        liability_balance_cents = _dollars_to_cents(liability.get("balance"))
        notes = _legacy_notes(
            liability,
            consumed_keys={
                "name",
                "url",
                "balance",
                "interestRate",
                "paymentDay",
                "lastPayment",
                "nextPayment",
                "monthlyPayment",
                "notes",
                "NOTES",
            },
            seed_note=(
                str(liability.get("notes")).strip()
                if liability.get("notes") is not None
                else str(liability.get("NOTES")).strip()
                if liability.get("NOTES") is not None
                else None
            ),
        )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-LIABILITY-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type="loan",
                organization_name=organization_name,
                url=str(liability.get("url")).strip()
                if liability.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=liability_balance_cents,
                apr_bps=(
                    int(round(float(liability.get("interestRate", 0)) * 100))
                    if liability.get("interestRate") is not None
                    else None
                ),
                payment_day=_parse_int(
                    liability.get("paymentDay"), "legacy.liabilities[].paymentDay"
                )
                if liability.get("paymentDay") is not None
                else None,
                last_payment_date=_parse_optional_iso_date(
                    liability.get("lastPayment")
                ),
                payment_amount_cents=_dollars_to_cents(liability.get("monthlyPayment")),
                closed=(
                    liability_balance_cents == 0
                    or _legacy_next_payment_is_far_future(liability.get("nextPayment"))
                ),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_fund in enumerate(funds, start=1):
        fund = _required_dict(raw_fund, "legacy.funds[]")
        name = str(fund.get("name") or "").strip() or f"Legacy Fund {index}"
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        notes = _legacy_notes(
            fund,
            consumed_keys={
                "name",
                "type",
                "url",
                "monthlyContribution",
                "balance",
                "notes",
            },
            seed_note=str(fund.get("notes")).strip()
            if fund.get("notes") is not None
            else None,
        )
        if fund.get("monthlyContribution") is not None:
            notes = _append_note(
                notes,
                f"Legacy monthly_contribution: {_legacy_value_as_text(fund.get('monthlyContribution'))}",
            )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-FUND-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type="stocks_account",
                organization_name=organization_name,
                url=str(fund.get("url")).strip()
                if fund.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(fund.get("balance")),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_retirement in enumerate(retirement, start=1):
        item = _required_dict(raw_retirement, "legacy.retirement[]")
        name = str(item.get("name") or "").strip() or f"Legacy Retirement {index}"
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        notes = _legacy_notes(
            item,
            consumed_keys={
                "name",
                "type",
                "symbol",
                "url",
                "balance",
                "monthlyContribution",
                "funds",
                "notes",
            },
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        if item.get("monthlyContribution") is not None:
            notes = _append_note(
                notes,
                f"Legacy monthly_contribution: {_legacy_value_as_text(item.get('monthlyContribution'))}",
            )
            monthly_contribution_cents = _dollars_to_cents(
                item.get("monthlyContribution")
            )
            if monthly_contribution_cents > 0:
                pending_retirement_contributions.append(
                    (name, monthly_contribution_cents, organization_name)
                )
        if item.get("symbol") is not None:
            notes = _append_note(
                notes, f"Legacy symbol: {_legacy_value_as_text(item.get('symbol'))}"
            )
        if item.get("funds") is not None:
            notes = _append_note(
                notes,
                f"Legacy retirement_funds: {_legacy_value_as_text(item.get('funds'))}",
            )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-RETIRE-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type="retirement",
                organization_name=organization_name,
                url=str(item.get("url")).strip()
                if item.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(item.get("balance")),
                retirement_account_type=_normalize_retirement_account_type(
                    item.get("type")
                ),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_stock_account in enumerate(stock_accounts, start=1):
        item = _required_dict(raw_stock_account, "legacy.stocks[]")
        name = (
            str(item.get("broker") or item.get("name") or "").strip()
            or f"Legacy Brokerage {index}"
        )
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        notes = _legacy_notes(
            item,
            consumed_keys={"broker", "name", "balance", "stocks", "notes"},
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        positions: list[dict[str, Any]] = []
        for raw_position in _required_list(
            item.get("stocks", []), "legacy.stocks[].stocks"
        ):
            position = _required_dict(raw_position, "legacy.stocks[].stocks[]")
            ticker = str(position.get("ticker") or "").strip().upper()
            stock_name = (
                str(position.get("stock") or "").strip() or ticker or "Legacy Stock"
            )
            stock_id = ensure_stock_id(
                ticker=ticker,
                fallback_name=stock_name,
                price_cents=_dollars_to_cents(position.get("price")),
            )
            quantity_text = "0"
            try:
                parsed_quantity = _parse_decimal(
                    position.get("shares"), "legacy.stocks[].stocks[].shares"
                )
                quantity_text = _serialize_decimal(parsed_quantity)
            except HTTPException:
                quantity_text = "0"
            positions.append({"stock_id": stock_id, "quantity": quantity_text})
            position_note = _legacy_notes(
                position,
                consumed_keys={"stock", "ticker", "shares", "price"},
                seed_note=None,
            )
            if position_note:
                notes = _append_note(
                    notes,
                    f"Legacy stock '{stock_name}' extras: {position_note}",
                )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-STOCK-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type="stocks_account",
                organization_name=organization_name,
                url=None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(item.get("balance")),
                stock_positions=positions,
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_crypto in enumerate(crypto_accounts, start=1):
        item = _required_dict(raw_crypto, "legacy.crypto[]")
        name = (
            str(item.get("wallet") or item.get("name") or "").strip()
            or f"Legacy Crypto {index}"
        )
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        is_metamask = name.strip().lower() == "metamask"
        account_type = "crypto_wallet" if is_metamask else "crypto_exchange"
        notes = _legacy_notes(
            item,
            consumed_keys={"wallet", "name", "balance", "url", "notes"},
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-CRYPTO-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type=account_type,
                organization_name=organization_name,
                url=str(item.get("url")).strip()
                if item.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                usd_balance_cents=_dollars_to_cents(item.get("balance"))
                if account_type == "crypto_exchange"
                else None,
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_receivable in enumerate(receivables, start=1):
        item = _required_dict(raw_receivable, "legacy.receivables[]")
        name = str(item.get("name") or "").strip() or f"Legacy Receivable {index}"
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        receivable_type = str(item.get("type") or "").strip().lower()
        mapped_receivable_account_type = (
            "rewards_card"
            if receivable_type in {"store credit", "store-credit", "rewards"}
            else "checking"
        )
        notes = _legacy_notes(
            item,
            consumed_keys={"name", "type", "balance", "notes"},
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        if item.get("type") is not None:
            notes = _append_note(
                notes,
                f"Legacy receivable_type: {_legacy_value_as_text(item.get('type'))}",
            )
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-RECV-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type=mapped_receivable_account_type,
                organization_name=organization_name,
                url=None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(item.get("balance")),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    for index, raw_closed in enumerate(closed_accounts, start=1):
        item = _required_dict(raw_closed, "legacy.closed[]")
        name = str(item.get("name") or "").strip() or f"Legacy Closed {index}"
        account_id = reserve_account_id(name)
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        notes = _legacy_notes(
            item,
            consumed_keys={
                "name",
                "type",
                "url",
                "credit",
                "lastPayment",
                "nextPayment",
                "paymentDay",
                "apr",
                "balance",
                "rewards",
                "notes",
            },
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        notes = _append_note(notes, "Legacy status: closed")
        append_account(
            _legacy_account_payload(
                account_id=account_id,
                account_number=f"LEG-CLOSED-{_slugify(name)}-{account_rank:03d}",
                name=name,
                account_type=_legacy_account_type(
                    str(item.get("type") or ""), default="credit_card"
                ),
                organization_name=organization_name,
                url=str(item.get("url")).strip()
                if item.get("url") is not None
                else None,
                notes=notes,
                rank=account_rank,
                now_iso=now_iso,
                balance_cents=_dollars_to_cents(item.get("balance")),
                apr_bps=(
                    int(round(float(item.get("apr", 0)) * 100))
                    if item.get("apr") is not None
                    else None
                ),
                payment_day=_parse_int(
                    item.get("paymentDay"), "legacy.closed[].paymentDay"
                )
                if item.get("paymentDay") is not None
                else None,
                last_payment_date=_parse_optional_iso_date(item.get("lastPayment")),
                closed=True,
                max_credit_cents=_dollars_to_cents(item.get("credit")),
                rewards_balance_cents=_dollars_to_cents(item.get("rewards")),
                icon_id=matched_icon_id(name, matched_org),
            )
        )

    converted_contracts: list[dict[str, Any]] = []
    unsupported_periods: set[str] = set()
    for index, raw_contract in enumerate(contracts, start=1):
        item = _required_dict(raw_contract, "legacy.contracts[]")
        name = str(item.get("name") or "").strip() or f"Legacy Contract {index}"
        amount_cents = _dollars_to_cents(item.get("amount"))
        contract_type = "income" if amount_cents > 0 else "payment"
        payment_account_name = str(item.get("paymentAccount") or "").strip().lower()
        linked_wallet = _legacy_wallet_alias(payment_account_name)
        linked_account_id = (
            None
            if linked_wallet is not None
            else account_id_by_name.get(payment_account_name)
        )
        last_payment_date = _legacy_extract_date(
            item,
            "lastPayment",
            "last_payment_date",
            "lastPaymentDate",
            "last_paid",
            "lastPaid",
        )
        next_payment_date = _legacy_extract_date(
            item,
            "nextPayment",
            "next_payment_date",
            "nextPaymentDate",
        )
        explicit_expiration_date = _legacy_extract_date(
            item,
            "expiration_date",
            "expirationDate",
            "expires",
            "expiry",
            "endDate",
        )
        mark_expired = _is_far_future_date(next_payment_date) or _is_far_future_date(
            explicit_expiration_date
        )
        payment_period, payment_day = _legacy_contract_period(
            item.get("period"),
            last_payment_date,
            next_payment_date,
            unsupported_periods,
        )
        category = (
            str(item.get("category") or item.get("catgory") or "Financial").strip()
            or "Financial"
        )
        matched_org = matched_default_org(name)
        organization_name = matched_org.name if matched_org is not None else name
        matched_contract_icon_id = matched_icon_id(name, matched_org)
        notes = _legacy_notes(
            item,
            consumed_keys={
                "name",
                "details",
                "amount",
                "period",
                "lastPayment",
                "last_payment_date",
                "lastPaymentDate",
                "last_paid",
                "lastPaid",
                "nextPayment",
                "next_payment_date",
                "nextPaymentDate",
                "automatic",
                "category",
                "catgory",
                "expiration_date",
                "expirationDate",
                "expires",
                "expiry",
                "endDate",
                "paymentAccount",
                "url",
                "notes",
            },
            seed_note=str(item.get("details")).strip()
            if item.get("details") is not None
            else str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
        )
        converted_contracts.append(
            {
                "id": str(uuid4()),
                "name": name,
                "type": contract_type,
                "automatic": bool(item.get("automatic", True)),
                "amount_cents": abs(amount_cents),
                "organization": organization_name,
                "icon_id": matched_contract_icon_id,
                "icon_type": "Icon"
                if matched_contract_icon_id is not None
                else "Letters",
                "rank": float(index),
                "linked_account_id": linked_account_id,
                "linked_wallet": linked_wallet,
                "source_account_id": None,
                "last_payment_date": last_payment_date.isoformat()
                if last_payment_date
                else None,
                "payment_period": payment_period,
                "payment_day": payment_day,
                "expiration_date": (
                    (date.today() - timedelta(days=1)).isoformat()
                    if mark_expired
                    else explicit_expiration_date.isoformat()
                    if explicit_expiration_date
                    else None
                ),
                "notes": notes,
                "category": category,
                "url": str(item.get("url")).strip()
                if item.get("url") is not None
                else None,
                "account_number": None,
                "billing_day": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    for index, (account_name, monthly_cents, contribution_org_name) in enumerate(
        pending_retirement_contributions, start=1
    ):
        linked_account_id = account_id_by_name.get(account_name.strip().lower())
        if linked_account_id is None:
            continue
        converted_contracts.append(
            {
                "id": str(uuid4()),
                "name": f"{account_name} Contribution",
                "type": "income",
                "automatic": True,
                "amount_cents": int(monthly_cents),
                "organization": contribution_org_name,
                "icon_id": None,
                "icon_type": "Letters",
                "rank": float(1000 + index),
                "linked_account_id": linked_account_id,
                "linked_wallet": None,
                "source_account_id": None,
                "last_payment_date": None,
                "payment_period": json.dumps({"kind": "monthly_last_day"}),
                "payment_day": None,
                "expiration_date": None,
                "notes": "Imported from legacy retirement monthlyContribution",
                "category": "Retirement",
                "url": None,
                "account_number": None,
                "billing_day": None,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        )

    for index, raw_expense in enumerate(expenses, start=1):
        item = _required_dict(raw_expense, "legacy.expenses[]")
        name = str(item.get("name") or "").strip() or f"Legacy Expense {index}"
        frequency = _legacy_expense_frequency(item.get("period"), unsupported_periods)
        account_name = (
            str(item.get("account") or item.get("paymentAccount") or "").strip().lower()
        )
        linked_account_id = (
            account_id_by_name.get(account_name) if account_name else None
        )
        notes = _legacy_notes(
            item,
            consumed_keys={
                "name",
                "amount",
                "period",
                "enabled",
                "category",
                "account",
                "paymentAccount",
                "notes",
                "details",
            },
            seed_note=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else str(item.get("details")).strip()
            if item.get("details") is not None
            else None,
        )
        converted_expenses.append(
            {
                "id": str(uuid4()),
                "name": name,
                "category": str(item.get("category") or "Legacy").strip() or "Legacy",
                "icon_id": None,
                "icon_type": "Letters",
                "estimated_amount_cents": abs(_dollars_to_cents(item.get("amount"))),
                "linked_account_id": linked_account_id,
                "enabled": bool(item.get("enabled", True)),
                "general_frequency": frequency,
                "last_expensed_date": None,
                "next_expensed_date": None,
                "next_date_is_static": False,
                "created_at": now_iso,
                "updated_at": now_iso,
                "notes": notes,
            }
        )

    if unsupported_periods:
        bad_periods = ", ".join(sorted(unsupported_periods))
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported legacy period strings: "
                f"{bad_periods}. Please clarify how these should recur."
            ),
        )

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "exported_at": now_iso,
        "user_profile": {
            "avatar_icon_id": None,
            "paypal_account_id": None,
            "google_pay_account_id": None,
            "widget_token": None,
            "widget_last_accessed_at": None,
            "widget_last_net_worth_cents": None,
            "last_login_at": None,
            "password_changed_at": None,
            "created_at": user.created_at.isoformat() if user.created_at else now_iso,
            "updated_at": now_iso,
        },
        "icons": [],
        "stocks": converted_stocks,
        "accounts": converted_accounts,
        "contracts": converted_contracts,
        "contract_postings": [],
        "expenses": converted_expenses,
        "investments": [],
        "account_value_history": [],
        "net_worth_daily_snapshot": [],
        "account_transfers": [],
        "audit_log_events": [],
    }


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
    investments = (
        db.query(Investment)
        .filter(Investment.user_id == user_id)
        .order_by(
            Investment.enabled.desc(),
            Investment.next_investment_date.asc().nulls_last(),
            Investment.created_at.asc(),
        )
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
    account_transfers = (
        db.query(AccountTransfer)
        .filter(AccountTransfer.user_id == user_id)
        .order_by(
            AccountTransfer.queued_at.asc(),
            AccountTransfer.id.asc(),
        )
        .all()
    )
    audit_log_events = (
        db.query(AuditLogEvent)
        .filter(AuditLogEvent.user_id == user_id)
        .order_by(AuditLogEvent.occurred_at.asc(), AuditLogEvent.id.asc())
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
        db.query(IconAsset)
        .filter(
            (IconAsset.created_by_user_id == user_id)
            | (IconAsset.id.in_(list(referenced_icon_ids)))
        )
        .order_by(IconAsset.created_at.asc(), IconAsset.id.asc())
        .all()
    )

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "user_profile": {
            "avatar_icon_id": str(user.avatar_icon_id)
            if user.avatar_icon_id is not None
            else None,
            "paypal_account_id": str(user.paypal_account_id)
            if user.paypal_account_id is not None
            else None,
            "google_pay_account_id": str(user.google_pay_account_id)
            if user.google_pay_account_id is not None
            else None,
            "widget_token": user.widget_token,
            "widget_last_accessed_at": _serialize_datetime(
                user.widget_last_accessed_at
            ),
            "widget_last_net_worth_cents": (
                int(user.widget_last_net_worth_cents)
                if user.widget_last_net_worth_cents is not None
                else None
            ),
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
                "closed": bool(account.closed),
                "max_credit_cents": account.max_credit_cents,
                "rewards_balance_cents": account.rewards_balance_cents,
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
                "linked_wallet": contract.linked_wallet,
                "source_account_id": (
                    str(contract.source_account_id)
                    if contract.source_account_id is not None
                    else None
                ),
                "last_payment_date": _serialize_date(contract.last_payment_date),
                "next_payment_date": _serialize_date(contract.next_payment_date),
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
                "notes": expense.notes,
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
        "investments": [
            {
                "id": str(investment.id),
                "source_account_id": str(investment.source_account_id),
                "destination_account_id": str(investment.destination_account_id),
                "amount_cents": int(investment.amount_cents),
                "enabled": bool(investment.enabled),
                "general_frequency": investment.general_frequency,
                "last_invested_date": _serialize_date(investment.last_invested_date),
                "next_investment_date": _serialize_date(
                    investment.next_investment_date
                ),
                "next_date_is_static": bool(investment.next_date_is_static),
                "created_at": _serialize_datetime(investment.created_at),
                "updated_at": _serialize_datetime(investment.updated_at),
            }
            for investment in investments
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
        "account_transfers": [
            {
                "id": str(transfer.id),
                "source_account_id": str(transfer.source_account_id),
                "destination_account_id": str(transfer.destination_account_id),
                "amount_cents": int(transfer.amount_cents),
                "current_balance_cents": int(transfer.current_balance_cents)
                if transfer.current_balance_cents is not None
                else None,
                "pending_balance_cents": int(transfer.pending_balance_cents)
                if transfer.pending_balance_cents is not None
                else None,
                "transfer_kind": str(transfer.transfer_kind or "standard"),
                "instant_deposit": bool(transfer.instant_deposit),
                "queued_at": _serialize_datetime(transfer.queued_at),
                "effective_at": _serialize_datetime(transfer.effective_at),
                "applied_at": _serialize_datetime(transfer.applied_at),
            }
            for transfer in account_transfers
        ],
        "audit_log_events": [
            {
                "id": str(event.id),
                "trigger_type": event.trigger_type,
                "event_type": event.event_type,
                "message": event.message,
                "details": event.details_json or {},
                "occurred_at": _serialize_datetime(event.occurred_at),
            }
            for event in audit_log_events
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


def _upgrade_payload_v3_to_v4(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 4
    accounts = _required_list(upgraded.get("accounts", []), "accounts")
    upgraded_accounts: list[dict[str, Any]] = []
    for raw in accounts:
        account = _required_dict(raw, "accounts[]")
        normalized = dict(account)
        if "closed" not in normalized:
            normalized["closed"] = False
        if "max_credit_cents" not in normalized:
            normalized["max_credit_cents"] = None
        if "rewards_balance_cents" not in normalized:
            normalized["rewards_balance_cents"] = None
        upgraded_accounts.append(normalized)
    upgraded["accounts"] = upgraded_accounts
    return upgraded


def _upgrade_payload_v4_to_v5(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 5
    profile = _required_dict(upgraded.get("user_profile"), "user_profile")
    if "paypal_account_id" not in profile:
        profile["paypal_account_id"] = None
    if "google_pay_account_id" not in profile:
        profile["google_pay_account_id"] = None
    upgraded["user_profile"] = profile
    contracts = _required_list(upgraded.get("contracts", []), "contracts")
    upgraded_contracts: list[dict[str, Any]] = []
    for raw in contracts:
        item = _required_dict(raw, "contracts[]")
        normalized = dict(item)
        if "linked_wallet" not in normalized:
            normalized["linked_wallet"] = None
        upgraded_contracts.append(normalized)
    upgraded["contracts"] = upgraded_contracts
    return upgraded


def _upgrade_payload_v5_to_v6(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 6
    if "queued_credit_card_payments" not in upgraded:
        upgraded["queued_credit_card_payments"] = []
    return upgraded


def _upgrade_payload_v6_to_v7(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 7
    if "account_transfers" not in upgraded:
        upgraded["account_transfers"] = [
            {
                "id": item.get("id"),
                "source_account_id": item.get("source_account_id"),
                "destination_account_id": item.get("credit_card_account_id"),
                "amount_cents": item.get("payment_cents"),
                "current_balance_cents": item.get("current_balance_cents"),
                "pending_balance_cents": item.get("pending_balance_cents"),
                "transfer_kind": "credit_card_payment",
                "instant_deposit": False,
                "queued_at": item.get("queued_at"),
                "effective_at": item.get("effective_at"),
                "applied_at": item.get("applied_at"),
            }
            for item in _required_list(
                upgraded.get("queued_credit_card_payments", []),
                "queued_credit_card_payments",
            )
        ]
    return upgraded


def _upgrade_payload_v7_to_v8(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 8
    upgraded_transfers: list[dict[str, Any]] = []
    for item in _required_list(
        upgraded.get("account_transfers", []), "account_transfers"
    ):
        normalized = dict(_required_dict(item, "account_transfers[]"))
        normalized["instant_deposit"] = bool(normalized.get("instant_deposit", False))
        upgraded_transfers.append(normalized)
    upgraded["account_transfers"] = upgraded_transfers
    return upgraded


def _upgrade_payload_v8_to_v9(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 9
    if "investments" not in upgraded:
        upgraded["investments"] = []
    return upgraded


def _upgrade_payload_v9_to_v10(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 10
    if "audit_log_events" not in upgraded:
        upgraded["audit_log_events"] = []
    return upgraded


def _upgrade_payload_v10_to_v11(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 11
    contracts = _required_list(upgraded.get("contracts", []), "contracts")
    upgraded_contracts: list[dict[str, Any]] = []
    for raw in contracts:
        item = dict(_required_dict(raw, "contracts[]"))
        if "next_payment_date" not in item:
            item["next_payment_date"] = None
        upgraded_contracts.append(item)
    upgraded["contracts"] = upgraded_contracts
    return upgraded


def _upgrade_payload_v11_to_v12(payload: dict[str, Any]) -> dict[str, Any]:
    upgraded = dict(payload)
    upgraded["schema_version"] = 12
    profile = _required_dict(upgraded.get("user_profile"), "user_profile")
    if "widget_token" not in profile:
        profile["widget_token"] = None
    if "widget_last_accessed_at" not in profile:
        profile["widget_last_accessed_at"] = None
    if "widget_last_net_worth_cents" not in profile:
        profile["widget_last_net_worth_cents"] = None
    upgraded["user_profile"] = profile
    return upgraded


PAYLOAD_MIGRATIONS: dict[int, Any] = {
    0: _upgrade_payload_v0_to_v1,
    1: _upgrade_payload_v1_to_v2,
    2: _upgrade_payload_v2_to_v3,
    3: _upgrade_payload_v3_to_v4,
    4: _upgrade_payload_v4_to_v5,
    5: _upgrade_payload_v5_to_v6,
    6: _upgrade_payload_v6_to_v7,
    7: _upgrade_payload_v7_to_v8,
    8: _upgrade_payload_v8_to_v9,
    9: _upgrade_payload_v9_to_v10,
    10: _upgrade_payload_v10_to_v11,
    11: _upgrade_payload_v11_to_v12,
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
    investments = _required_list(payload.get("investments", []), "investments")
    history_points = _required_list(
        payload.get("account_value_history"), "account_value_history"
    )
    net_worth_snapshots = _required_list(
        payload.get("net_worth_daily_snapshot"), "net_worth_daily_snapshot"
    )
    account_transfers = _required_list(
        payload.get("account_transfers", []), "account_transfers"
    )
    audit_log_events = _required_list(
        payload.get("audit_log_events", []), "audit_log_events"
    )

    db.query(Expense).filter(Expense.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Investment).filter(Investment.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(Contract).filter(Contract.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AccountValueHistory).filter(AccountValueHistory.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AccountTransfer).filter(AccountTransfer.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(AuditLogEvent).filter(AuditLogEvent.user_id == user_id).delete(
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
        elif existing.created_by_user_id is None:
            is_default_icon = (
                db.query(DefaultIcon.id)
                .filter(DefaultIcon.icon_id == existing.id)
                .first()
                is not None
            ) or (
                db.query(Organization.id)
                .filter(
                    Organization.icon_id == existing.id,
                    Organization.is_default.is_(True),
                )
                .first()
                is not None
            )
            if not is_default_icon:
                existing.created_by_user_id = user_id
                db.add(existing)
        icon_id_map[old_id] = existing.id
        imported_icons += 1

    def resolve_import_icon_id(raw_icon_id: UUID | None) -> UUID | None:
        if raw_icon_id is None:
            return None
        mapped_icon_id = icon_id_map.get(raw_icon_id)
        if mapped_icon_id is not None:
            return mapped_icon_id
        existing_icon = db.get(IconAsset, raw_icon_id)
        if existing_icon is not None:
            return existing_icon.id
        return None

    raw_avatar_icon_id = _parse_optional_uuid(
        user_profile.get("avatar_icon_id"), "user_profile.avatar_icon_id"
    )
    raw_paypal_account_id = _parse_optional_uuid(
        user_profile.get("paypal_account_id"), "user_profile.paypal_account_id"
    )
    raw_google_pay_account_id = _parse_optional_uuid(
        user_profile.get("google_pay_account_id"),
        "user_profile.google_pay_account_id",
    )
    raw_widget_token = user_profile.get("widget_token")
    if raw_widget_token is not None and not isinstance(raw_widget_token, str):
        raise HTTPException(
            status_code=400,
            detail="user_profile.widget_token must be a string or null",
        )
    user.avatar_icon_id = resolve_import_icon_id(raw_avatar_icon_id)
    user.widget_token = (
        raw_widget_token.strip()
        if isinstance(raw_widget_token, str) and raw_widget_token.strip()
        else None
    )
    user.widget_last_accessed_at = _parse_optional_datetime(
        user_profile.get("widget_last_accessed_at"),
        "user_profile.widget_last_accessed_at",
    )
    user.widget_last_net_worth_cents = (
        _parse_int(
            user_profile.get("widget_last_net_worth_cents"),
            "user_profile.widget_last_net_worth_cents",
        )
        if user_profile.get("widget_last_net_worth_cents") is not None
        else None
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
    user.paypal_account_id = None
    user.google_pay_account_id = None
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
        resolved_icon_id = resolve_import_icon_id(raw_icon_id)
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
            closed=bool(item.get("closed", False)),
            max_credit_cents=_parse_int(
                item.get("max_credit_cents"), "accounts[].max_credit_cents"
            )
            if item.get("max_credit_cents") is not None
            else None,
            rewards_balance_cents=_parse_int(
                item.get("rewards_balance_cents"),
                "accounts[].rewards_balance_cents",
            )
            if item.get("rewards_balance_cents") is not None
            else None,
            cvc=str(item.get("cvc")).strip() if item.get("cvc") is not None else None,
            usd_balance_cents=_parse_int(
                item.get("usd_balance_cents"), "accounts[].usd_balance_cents"
            )
            if item.get("usd_balance_cents") is not None
            else None,
            retirement_account_type=_normalize_retirement_account_type(
                item.get("retirement_account_type")
            ),
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

    user.paypal_account_id = (
        account_id_map.get(raw_paypal_account_id)
        if raw_paypal_account_id is not None
        else None
    )
    user.google_pay_account_id = (
        account_id_map.get(raw_google_pay_account_id)
        if raw_google_pay_account_id is not None
        else None
    )
    db.add(user)

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
        linked_wallet = item.get("linked_wallet")
        if linked_wallet is not None and linked_wallet not in {"paypal", "google_pay"}:
            raise HTTPException(
                status_code=400,
                detail="contracts[].linked_wallet must be paypal or google_pay",
            )
        source_old = _parse_optional_uuid(
            item.get("source_account_id"), "contracts[].source_account_id"
        )
        raw_icon_id = _parse_optional_uuid(item.get("icon_id"), "contracts[].icon_id")
        icon_type = _coerce_icon_type(item.get("icon_type"))
        parsed_contract_last_payment_date = _parse_optional_date(
            item.get("last_payment_date", item.get("lastPayment")),
            "contracts[].last_payment_date",
        )
        parsed_contract_expiration_date = _parse_optional_date(
            item.get("expiration_date", item.get("expirationDate")),
            "contracts[].expiration_date",
        )
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
            icon_id=resolve_import_icon_id(raw_icon_id)
            if icon_type == "Icon" and raw_icon_id is not None
            else None,
            icon_type=icon_type,
            rank=_parse_float(item.get("rank"), "contracts[].rank", default=0.0),
            linked_account_id=account_id_map.get(linked_old)
            if linked_old is not None
            else None,
            linked_wallet=linked_wallet,
            source_account_id=account_id_map.get(source_old)
            if source_old is not None
            else None,
            last_payment_date=parsed_contract_last_payment_date,
            next_payment_date=_parse_optional_date(
                item.get("next_payment_date"), "contracts[].next_payment_date"
            ),
            payment_period=str(item.get("payment_period")).strip()
            if item.get("payment_period") is not None
            else None,
            payment_day=_parse_int(item.get("payment_day"), "contracts[].payment_day")
            if item.get("payment_day") is not None
            else None,
            expiration_date=parsed_contract_expiration_date
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
            notes=str(item.get("notes")).strip()
            if item.get("notes") is not None
            else None,
            icon_id=resolve_import_icon_id(raw_icon_id)
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

    imported_investments = 0
    for raw in investments:
        item = _required_dict(raw, "investments[]")
        old_source_account_id = _parse_uuid(
            item.get("source_account_id"), "investments[].source_account_id"
        )
        old_destination_account_id = _parse_uuid(
            item.get("destination_account_id"),
            "investments[].destination_account_id",
        )
        source_account_id = account_id_map.get(old_source_account_id)
        destination_account_id = account_id_map.get(old_destination_account_id)
        if source_account_id is None or destination_account_id is None:
            raise HTTPException(
                status_code=400,
                detail="investments[] references unknown account",
            )
        db.add(
            Investment(
                id=uuid4(),
                user_id=user_id,
                source_account_id=source_account_id,
                destination_account_id=destination_account_id,
                amount_cents=_parse_int(
                    item.get("amount_cents"), "investments[].amount_cents"
                ),
                enabled=bool(item.get("enabled", True)),
                general_frequency=str(item.get("general_frequency")).strip()
                if item.get("general_frequency") is not None
                else None,
                last_invested_date=_parse_optional_date(
                    item.get("last_invested_date"), "investments[].last_invested_date"
                ),
                next_investment_date=_parse_optional_date(
                    item.get("next_investment_date"),
                    "investments[].next_investment_date",
                ),
                next_date_is_static=bool(item.get("next_date_is_static", False)),
                created_at=_parse_optional_datetime(
                    item.get("created_at"), "investments[].created_at"
                )
                or datetime.now(tz=timezone.utc),
                updated_at=_parse_optional_datetime(
                    item.get("updated_at"), "investments[].updated_at"
                )
                or datetime.now(tz=timezone.utc),
            )
        )
        imported_investments += 1

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
    imported_account_transfers = 0
    imported_audit_log_events = 0
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

    for raw in account_transfers:
        item = _required_dict(raw, "account_transfers[]")
        old_source_account_id = _parse_uuid(
            item.get("source_account_id"),
            "account_transfers[].source_account_id",
        )
        old_destination_account_id = _parse_uuid(
            item.get("destination_account_id"),
            "account_transfers[].destination_account_id",
        )
        source_account_id = account_id_map.get(old_source_account_id)
        destination_account_id = account_id_map.get(old_destination_account_id)
        if source_account_id is None or destination_account_id is None:
            raise HTTPException(
                status_code=400,
                detail="account_transfers[] references unknown account",
            )
        transfer_kind = str(item.get("transfer_kind") or "standard").strip()
        if transfer_kind not in {"standard", "credit_card_payment"}:
            raise HTTPException(
                status_code=400,
                detail="account_transfers[].transfer_kind is invalid",
            )
        instant_deposit = _parse_bool(
            item.get("instant_deposit"),
            "account_transfers[].instant_deposit",
            default=False,
        )
        if transfer_kind != "standard" and instant_deposit:
            raise HTTPException(
                status_code=400,
                detail="account_transfers[].instant_deposit is only valid for standard transfers",
            )
        db.add(
            AccountTransfer(
                id=uuid4(),
                user_id=user_id,
                source_account_id=source_account_id,
                destination_account_id=destination_account_id,
                amount_cents=_parse_int(
                    item.get("amount_cents"),
                    "account_transfers[].amount_cents",
                ),
                current_balance_cents=_parse_int(
                    item.get("current_balance_cents"),
                    "account_transfers[].current_balance_cents",
                )
                if item.get("current_balance_cents") is not None
                else None,
                pending_balance_cents=_parse_int(
                    item.get("pending_balance_cents"),
                    "account_transfers[].pending_balance_cents",
                    default=0,
                )
                if item.get("pending_balance_cents") is not None
                else None,
                transfer_kind=transfer_kind,
                instant_deposit=instant_deposit,
                queued_at=_parse_optional_datetime(
                    item.get("queued_at"),
                    "account_transfers[].queued_at",
                )
                or datetime.now(tz=timezone.utc),
                effective_at=_parse_optional_datetime(
                    item.get("effective_at"),
                    "account_transfers[].effective_at",
                )
                or datetime.now(tz=timezone.utc),
                applied_at=_parse_optional_datetime(
                    item.get("applied_at"),
                    "account_transfers[].applied_at",
                ),
            )
        )
        imported_account_transfers += 1

    for raw in audit_log_events:
        item = _required_dict(raw, "audit_log_events[]")
        trigger_type = str(item.get("trigger_type") or "").strip()
        if trigger_type not in {"user", "cron", "system"}:
            raise HTTPException(
                status_code=400,
                detail="audit_log_events[].trigger_type is invalid",
            )
        details = item.get("details", {})
        if not isinstance(details, dict):
            raise HTTPException(
                status_code=400, detail="audit_log_events[].details must be an object"
            )
        db.add(
            AuditLogEvent(
                id=uuid4(),
                user_id=user_id,
                trigger_type=trigger_type,
                event_type=str(item.get("event_type") or "").strip(),
                message=str(item.get("message") or "").strip(),
                details_json=details,
                occurred_at=_parse_optional_datetime(
                    item.get("occurred_at"), "audit_log_events[].occurred_at"
                )
                or datetime.now(tz=timezone.utc),
            )
        )
        imported_audit_log_events += 1

    return ImportResponseSchema(
        schema_version=PAYLOAD_SCHEMA_VERSION,
        imported_icons=imported_icons,
        imported_stocks=imported_stocks,
        imported_accounts=imported_accounts,
        imported_contracts=imported_contracts,
        imported_contract_postings=imported_contract_postings,
        imported_expenses=imported_expenses,
        imported_investments=imported_investments,
        imported_history_points=imported_history_points,
        imported_net_worth_snapshots=imported_snapshots,
        imported_account_transfers=imported_account_transfers,
        imported_audit_log_events=imported_audit_log_events,
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
    incoming_package = _coerce_import_package(payload.package)
    imported_legacy_payload = False

    if _is_export_envelope(incoming_package):
        raw_data = _extract_payload_from_envelope(incoming_package, normalized_password)
        migrated_data = _migrate_payload_to_latest(raw_data)
    elif _is_legacy_payload(incoming_package):
        imported_legacy_payload = True
        migrated_data = _convert_legacy_payload_to_latest(
            incoming_package, current_user, db
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported import format: expected export package or legacy YAML",
        )

    result = _replace_user_data(db, current_user.id, migrated_data)
    if imported_legacy_payload:
        snapshot_day = date.today()
        snapshot_value_cents = compute_user_net_worth_cents(db, current_user.id)
        stmt = pg_insert(NetWorthDailySnapshot).values(
            user_id=current_user.id,
            snapshot_date=snapshot_day,
            value_cents=snapshot_value_cents,
            updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_net_worth_daily_snapshot_user_day",
            set_={
                "value_cents": snapshot_value_cents,
                "updated_at": datetime.utcnow(),
            },
        )
        db.execute(stmt)
        result.imported_net_worth_snapshots += 1
    db.commit()
    return result
