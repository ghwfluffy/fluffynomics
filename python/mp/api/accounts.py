from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from mp.db import get_db
from mp.api.auth import get_current_user
from mp.icons import digest_icon, generate_algorithmic_icon, normalize_icon_png
from mp.recurring_period import parse_recurring_period
from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCreateSchema,
    AccountIconType,
    AccountValueHistory,
    AccountValueHistorySchema,
    AccountCryptoPosition,
    DefaultIcon,
    DefaultIconSchema,
    AccountRankUpdateSchema,
    AccountSchema,
    AccountStockPosition,
    AccountUpdateSchema,
    AccountValueUpdateSchema,
    CashBillSchema,
    IconAsset,
    IconListItemSchema,
    IconUploadResponseSchema,
    Organization,
    OrganizationSuggestionSchema,
    PositionCryptoSchema,
    PositionStockSchema,
    Stock,
    StockCreateSchema,
    StockSchema,
    StockUpdateSchema,
)
from mp.schema.user import User

router = APIRouter()

ACCOUNT_TYPES = {
    "checking",
    "savings",
    "cash",
    "line_of_credit",
    "credit_card",
    "stocks_account",
    "crypto_exchange",
    "crypto_wallet",
    "retirement",
    "loan",
    "rewards_card",
}

LEGACY_RECURRING_PERIODS = {"daily", "weekly", "biweekly", "monthly", "yearly"}


def _validate_account_type(account_type: str) -> None:
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported account type: {account_type}"
        )


def _validate_required_identity_fields(
    name: str | None, organization: str | None
) -> None:
    if name is None or not name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if organization is None or not organization.strip():
        raise HTTPException(status_code=400, detail="organization is required")


def _validate_account_number(account_number: str | None) -> None:
    if account_number is None or not account_number.strip():
        raise HTTPException(status_code=400, detail="account_number is required")


def _validate_type_requirements(
    payload: AccountCreateSchema | AccountUpdateSchema,
) -> None:
    # Type-specific fields are intentionally optional. We only enforce
    # account identity fields + a valid account type.
    return


def _validate_icon_type(icon_type: str | None) -> None:
    if icon_type is None:
        return
    if icon_type not in {item.value for item in AccountIconType}:
        raise HTTPException(
            status_code=400, detail=f"Unsupported icon_type: {icon_type}"
        )


def _validate_recurring_period(raw: str | None) -> None:
    if raw is None:
        return
    normalized = raw.strip()
    if not normalized:
        return
    if normalized.lower() in LEGACY_RECURRING_PERIODS:
        # Backward compatibility for older seeded/example rows.
        return
    try:
        parse_recurring_period(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_last_payment_date(value: date | None) -> None:
    if value is None:
        return
    if value > date.today():
        raise HTTPException(
            status_code=400, detail="last_payment_date cannot be in the future"
        )


def _coerce_icon_type(icon_type: str | None) -> Literal["Letters", "Gravatar", "Icon"]:
    if icon_type == AccountIconType.LETTERS.value:
        return AccountIconType.LETTERS.value
    if icon_type == AccountIconType.GRAVATAR.value:
        return AccountIconType.GRAVATAR.value
    return AccountIconType.ICON.value


def _normalize_icon_selection(
    icon_type: str | None,
    icon_id: UUID | None,
    organization: str | None,
    db: Session,
) -> tuple[Literal["Letters", "Gravatar", "Icon"], UUID | None]:
    normalized_type = _coerce_icon_type(icon_type)
    if normalized_type != AccountIconType.ICON.value:
        return normalized_type, None
    if icon_id is not None:
        return normalized_type, icon_id
    if organization:
        org = db.query(Organization).filter_by(name=organization.strip()).first()
        if org is not None:
            return normalized_type, org.icon_id
    return normalized_type, None


def _hydrate_nested_positions(db: Session, account: Account) -> tuple[list, list, list]:
    stock_positions = (
        db.query(AccountStockPosition).filter_by(account_id=account.id).all()
    )
    crypto_positions = (
        db.query(AccountCryptoPosition).filter_by(account_id=account.id).all()
    )
    cash_bills = (
        db.query(AccountCashDenomination).filter_by(account_id=account.id).all()
    )
    return stock_positions, crypto_positions, cash_bills


def _compute_account_value_cents(db: Session, account: Account) -> int:
    stock_positions, crypto_positions, cash_bills = _hydrate_nested_positions(
        db, account
    )
    if account.type == "cash":
        return int(
            sum(
                int(position.denomination_cents) * int(position.quantity)
                for position in cash_bills
            )
        )
    if account.type in {"crypto_wallet", "crypto_exchange"}:
        crypto_total = sum(
            int(round(float(position.quantity) * int(position.exchange_rate_cents)))
            for position in crypto_positions
        )
        if account.type == "crypto_exchange":
            return int(account.usd_balance_cents or 0) + int(crypto_total)
        return int(crypto_total)
    if account.type == "stocks_account":
        stock_ids = [position.stock_id for position in stock_positions]
        prices_by_id: dict[UUID, int] = {}
        if stock_ids:
            for stock in db.query(Stock).filter(Stock.id.in_(stock_ids)).all():
                prices_by_id[stock.id] = int(stock.last_price_cents or 0)
        stock_total = sum(
            int(
                round(float(position.quantity) * prices_by_id.get(position.stock_id, 0))
            )
            for position in stock_positions
        )
        return int(account.balance_cents or 0) + int(stock_total)
    return int(account.balance_cents or 0)


def _record_account_value_history(db: Session, account: Account) -> None:
    db.add(
        AccountValueHistory(
            account_id=account.id,
            user_id=account.user_id,
            value_cents=_compute_account_value_cents(db, account),
        )
    )


def _serialize_account(db: Session, account: Account) -> AccountSchema:
    stock_positions, crypto_positions, cash_bills = _hydrate_nested_positions(
        db, account
    )
    stock_ids = [position.stock_id for position in stock_positions]
    stocks_by_id: dict[UUID, Stock] = {}
    if stock_ids:
        for db_stock in db.query(Stock).filter(Stock.id.in_(stock_ids)).all():
            stocks_by_id[db_stock.id] = db_stock
    derived_cash_balance = None
    if account.type == "cash":
        derived_cash_balance = sum(
            position.denomination_cents * position.quantity for position in cash_bills
        )
    serialized_stock_positions: list[PositionStockSchema] = []
    for position in stock_positions:
        mapped_stock = stocks_by_id.get(position.stock_id)
        serialized_stock_positions.append(
            PositionStockSchema(
                stock_id=position.stock_id,
                ticker=mapped_stock.ticker if mapped_stock is not None else None,
                exchange=mapped_stock.exchange if mapped_stock is not None else None,
                last_price_cents=(
                    mapped_stock.last_price_cents if mapped_stock is not None else None
                ),
                quantity=position.quantity,
            )
        )

    return AccountSchema(
        id=account.id,
        user_id=account.user_id,
        rank=account.rank,
        account_number=account.account_number,
        name=account.name,
        type=account.type,
        organization=account.organization,
        url=account.url,
        notes=account.notes,
        balance_cents=derived_cash_balance
        if derived_cash_balance is not None
        else account.balance_cents,
        fee_amount_cents=account.fee_amount_cents,
        fee_period=account.fee_period,
        routing_number=account.routing_number,
        apy_bps=account.apy_bps,
        compound_period=account.compound_period,
        apr_bps=account.apr_bps,
        billing_day=account.billing_day,
        payment_day=account.payment_day,
        last_payment_date=account.last_payment_date,
        expiration_date=account.expiration_date,
        cvc=account.cvc,
        usd_balance_cents=account.usd_balance_cents,
        retirement_account_type=account.retirement_account_type,
        payment_amount_cents=account.payment_amount_cents,
        icon_id=account.icon_id,
        icon_type=_coerce_icon_type(account.icon_type),
        last_update=account.last_update,
        stock_positions=serialized_stock_positions,
        crypto_positions=[
            PositionCryptoSchema(
                ticker=position.ticker,
                quantity=position.quantity,
                exchange_rate_cents=position.exchange_rate_cents,
            )
            for position in crypto_positions
        ],
        cash_bills=[
            CashBillSchema(
                denomination_cents=position.denomination_cents,
                quantity=position.quantity,
            )
            for position in cash_bills
        ],
        created_at=account.created_at,
    )


def _replace_nested_positions(
    db: Session,
    user_id: UUID,
    account_id: UUID,
    stock_positions: list | None,
    crypto_positions: list | None,
    cash_bills: list | None,
) -> None:
    if stock_positions is not None:
        db.query(AccountStockPosition).filter_by(account_id=account_id).delete()
        for item in stock_positions:
            stock_id = item.stock_id
            if stock_id is None:
                ticker = (item.ticker or "").strip().upper()
                if not ticker:
                    continue
                stock = (
                    db.query(Stock)
                    .filter(Stock.user_id == user_id, Stock.ticker == ticker)
                    .first()
                )
                if stock is None:
                    stock = Stock(
                        user_id=user_id,
                        name=ticker,
                        ticker=ticker,
                        exchange=item.exchange,
                        last_price_cents=max(0, int(item.last_price_cents or 0)),
                    )
                    db.add(stock)
                    db.flush()
                elif item.last_price_cents is not None:
                    stock.last_price_cents = max(0, int(item.last_price_cents))
                stock_id = stock.id
            elif item.last_price_cents is not None:
                stock = (
                    db.query(Stock)
                    .filter(Stock.id == stock_id, Stock.user_id == user_id)
                    .first()
                )
                if stock is not None:
                    stock.last_price_cents = max(0, int(item.last_price_cents))
            db.add(
                AccountStockPosition(
                    account_id=account_id,
                    stock_id=stock_id,
                    quantity=item.quantity,
                )
            )

    if crypto_positions is not None:
        db.query(AccountCryptoPosition).filter_by(account_id=account_id).delete()
        for item in crypto_positions:
            db.add(
                AccountCryptoPosition(
                    account_id=account_id,
                    ticker=item.ticker.upper(),
                    quantity=item.quantity,
                    exchange_rate_cents=item.exchange_rate_cents or 0,
                )
            )

    if cash_bills is not None:
        db.query(AccountCashDenomination).filter_by(account_id=account_id).delete()
        for item in cash_bills:
            db.add(
                AccountCashDenomination(
                    account_id=account_id,
                    denomination_cents=item.denomination_cents,
                    quantity=item.quantity,
                )
            )


def _propagate_crypto_rates_for_user(
    db: Session, user_id: UUID, crypto_positions: list[PositionCryptoSchema]
) -> None:
    if not crypto_positions:
        return
    by_ticker: dict[str, int] = {}
    for item in crypto_positions:
        ticker = item.ticker.strip().upper()
        if not ticker:
            continue
        by_ticker[ticker] = max(0, int(item.exchange_rate_cents or 0))

    if not by_ticker:
        return

    account_ids_subquery = db.query(Account.id).filter(Account.user_id == user_id)
    for ticker, rate in by_ticker.items():
        (
            db.query(AccountCryptoPosition)
            .filter(
                AccountCryptoPosition.account_id.in_(account_ids_subquery),
                AccountCryptoPosition.ticker == ticker,
            )
            .update({"exchange_rate_cents": rate}, synchronize_session=False)
        )


def _propagate_stock_prices_for_user(
    db: Session, user_id: UUID, stock_positions: list[PositionStockSchema]
) -> None:
    if not stock_positions:
        return
    by_ticker: dict[str, int] = {}
    for item in stock_positions:
        if item.last_price_cents is None:
            continue
        ticker = (item.ticker or "").strip().upper()
        if not ticker and item.stock_id is not None:
            stock = (
                db.query(Stock)
                .filter(Stock.id == item.stock_id, Stock.user_id == user_id)
                .first()
            )
            ticker = stock.ticker if stock is not None else ""
        if not ticker:
            continue
        by_ticker[ticker] = max(0, int(item.last_price_cents))
    for ticker, price in by_ticker.items():
        (
            db.query(Stock)
            .filter(Stock.user_id == user_id, Stock.ticker == ticker)
            .update(
                {"last_price_cents": price, "updated_at": datetime.utcnow()},
                synchronize_session=False,
            )
        )


@router.get("/accounts", response_model=list[AccountSchema])
def get_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountSchema]:
    accounts = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .order_by(Account.rank.desc(), Account.created_at.desc())
        .all()
    )
    return [_serialize_account(db, account) for account in accounts]


@router.get("/accounts/{account_id}", response_model=AccountSchema)
def get_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return _serialize_account(db, account)


@router.get(
    "/accounts/{account_id}/history", response_model=list[AccountValueHistorySchema]
)
def get_account_history(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountValueHistorySchema]:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    rows = (
        db.query(AccountValueHistory)
        .filter(
            AccountValueHistory.account_id == account_id,
            AccountValueHistory.user_id == current_user.id,
        )
        .order_by(AccountValueHistory.recorded_at.asc())
        .all()
    )
    return [
        AccountValueHistorySchema(
            value_cents=row.value_cents, recorded_at=row.recorded_at
        )
        for row in rows
    ]


@router.post("/accounts", response_model=AccountSchema)
def create_account(
    payload: AccountCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    _validate_account_type(payload.type)
    _validate_account_number(payload.account_number)
    _validate_required_identity_fields(payload.name, payload.organization)
    _validate_icon_type(payload.icon_type)
    _validate_recurring_period(payload.fee_period)
    _validate_last_payment_date(payload.last_payment_date)
    _validate_type_requirements(payload)

    max_rank = (
        db.query(func.max(Account.rank))
        .filter(Account.user_id == current_user.id)
        .scalar()
    )
    icon_type, effective_icon_id = _normalize_icon_selection(
        payload.icon_type,
        payload.icon_id,
        payload.organization,
        db,
    )

    account = Account(
        user_id=current_user.id,
        rank=(max_rank or 0) + 1,
        account_number=payload.account_number.strip(),
        name=payload.name.strip(),
        type=payload.type,
        organization=payload.organization.strip() if payload.organization else None,
        url=payload.url,
        notes=payload.notes,
        balance_cents=None if payload.type == "cash" else payload.balance_cents,
        fee_amount_cents=payload.fee_amount_cents,
        fee_period=payload.fee_period,
        routing_number=payload.routing_number,
        apy_bps=payload.apy_bps,
        compound_period=payload.compound_period,
        apr_bps=payload.apr_bps,
        billing_day=payload.billing_day,
        payment_day=payload.payment_day,
        last_payment_date=payload.last_payment_date,
        expiration_date=payload.expiration_date,
        cvc=payload.cvc,
        usd_balance_cents=payload.usd_balance_cents,
        retirement_account_type=payload.retirement_account_type,
        payment_amount_cents=payload.payment_amount_cents,
        icon_id=effective_icon_id,
        icon_type=icon_type,
        created_at=datetime.utcnow(),
        last_update=datetime.utcnow(),
    )
    db.add(account)
    db.flush()

    if payload.stock_positions:
        stock_ids = [item.stock_id for item in payload.stock_positions if item.stock_id]
        if stock_ids:
            owned_count = (
                db.query(Stock)
                .filter(Stock.user_id == current_user.id, Stock.id.in_(stock_ids))
                .count()
            )
            if owned_count != len(set(stock_ids)):
                raise HTTPException(
                    status_code=400, detail="Stock position contains unknown stock"
                )

    _replace_nested_positions(
        db,
        current_user.id,
        account.id,
        payload.stock_positions,
        payload.crypto_positions,
        payload.cash_bills,
    )
    if payload.stock_positions:
        _propagate_stock_prices_for_user(db, current_user.id, payload.stock_positions)
    if payload.crypto_positions:
        _propagate_crypto_rates_for_user(db, current_user.id, payload.crypto_positions)
    _record_account_value_history(db, account)

    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.put("/accounts/{account_id}/rank", response_model=AccountSchema)
def set_account_rank(
    account_id: UUID,
    payload: AccountRankUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    account.rank = payload.rank
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.put("/accounts/{account_id}", response_model=AccountSchema)
def update_account(
    account_id: UUID,
    payload: AccountUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    data = payload.model_dump(exclude_unset=True)
    account_type = data.get("type", account.type)
    _validate_account_type(account_type)
    if "icon_type" in data:
        _validate_icon_type(data["icon_type"])
    if "account_number" in data:
        _validate_account_number(data["account_number"])
    if "fee_period" in data:
        _validate_recurring_period(data["fee_period"])
    if "last_payment_date" in data:
        _validate_last_payment_date(data["last_payment_date"])
    if "name" in data or "organization" in data:
        _validate_required_identity_fields(
            data.get("name", account.name),
            data.get("organization", account.organization),
        )

    existing_stock_positions, existing_crypto_positions, existing_cash_bills = (
        _hydrate_nested_positions(db, account)
    )
    merged_payload = AccountCreateSchema(
        account_number=data.get("account_number", account.account_number),
        name=data.get("name", account.name),
        type=account_type,
        organization=data.get("organization", account.organization),
        url=data.get("url", account.url),
        notes=data.get("notes", account.notes),
        balance_cents=data.get("balance_cents", account.balance_cents),
        fee_amount_cents=data.get("fee_amount_cents", account.fee_amount_cents),
        fee_period=data.get("fee_period", account.fee_period),
        routing_number=data.get("routing_number", account.routing_number),
        apy_bps=data.get("apy_bps", account.apy_bps),
        compound_period=data.get("compound_period", account.compound_period),
        apr_bps=data.get("apr_bps", account.apr_bps),
        billing_day=data.get("billing_day", account.billing_day),
        payment_day=data.get("payment_day", account.payment_day),
        last_payment_date=data.get("last_payment_date", account.last_payment_date),
        expiration_date=data.get("expiration_date", account.expiration_date),
        cvc=data.get("cvc", account.cvc),
        usd_balance_cents=data.get("usd_balance_cents", account.usd_balance_cents),
        retirement_account_type=data.get(
            "retirement_account_type", account.retirement_account_type
        ),
        payment_amount_cents=data.get(
            "payment_amount_cents", account.payment_amount_cents
        ),
        icon_id=data.get("icon_id", account.icon_id),
        icon_type=data.get("icon_type", account.icon_type),
        stock_positions=payload.stock_positions
        if payload.stock_positions is not None
        else [
            PositionStockSchema(
                stock_id=position.stock_id,
                quantity=position.quantity,
            )
            for position in existing_stock_positions
        ],
        crypto_positions=payload.crypto_positions
        if payload.crypto_positions is not None
        else [
            PositionCryptoSchema(
                ticker=position.ticker,
                quantity=position.quantity,
                exchange_rate_cents=position.exchange_rate_cents,
            )
            for position in existing_crypto_positions
        ],
        cash_bills=payload.cash_bills
        if payload.cash_bills is not None
        else [
            CashBillSchema(
                denomination_cents=position.denomination_cents,
                quantity=position.quantity,
            )
            for position in existing_cash_bills
        ],
    )
    normalized_icon_type, normalized_icon_id = _normalize_icon_selection(
        merged_payload.icon_type,
        merged_payload.icon_id,
        merged_payload.organization,
        db,
    )
    merged_payload.icon_type = normalized_icon_type
    merged_payload.icon_id = normalized_icon_id
    _validate_type_requirements(merged_payload)
    _validate_last_payment_date(merged_payload.last_payment_date)

    if payload.stock_positions is not None and payload.stock_positions:
        stock_ids = [item.stock_id for item in payload.stock_positions if item.stock_id]
        if stock_ids:
            owned_count = (
                db.query(Stock)
                .filter(Stock.user_id == current_user.id, Stock.id.in_(stock_ids))
                .count()
            )
            if owned_count != len(set(stock_ids)):
                raise HTTPException(
                    status_code=400, detail="Stock position contains unknown stock"
                )

    for field in [
        "account_number",
        "name",
        "type",
        "organization",
        "url",
        "notes",
        "balance_cents",
        "fee_amount_cents",
        "fee_period",
        "routing_number",
        "apy_bps",
        "compound_period",
        "apr_bps",
        "billing_day",
        "payment_day",
        "last_payment_date",
        "expiration_date",
        "cvc",
        "usd_balance_cents",
        "retirement_account_type",
        "payment_amount_cents",
        "icon_id",
        "icon_type",
    ]:
        if field in data:
            value = data[field]
            if field in {"account_number", "name", "organization"} and isinstance(
                value, str
            ):
                value = value.strip()
            setattr(account, field, value)

    if account.type == "cash":
        account.balance_cents = None

    account.icon_type = merged_payload.icon_type
    account.icon_id = merged_payload.icon_id

    _replace_nested_positions(
        db,
        current_user.id,
        account_id,
        payload.stock_positions,
        payload.crypto_positions,
        payload.cash_bills,
    )
    if payload.stock_positions:
        _propagate_stock_prices_for_user(db, current_user.id, payload.stock_positions)
    if payload.crypto_positions:
        _propagate_crypto_rates_for_user(db, current_user.id, payload.crypto_positions)
    _record_account_value_history(db, account)

    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.post("/icons", response_model=IconUploadResponseSchema)
async def upload_icon(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IconUploadResponseSchema:
    _ = current_user
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Icon file is empty")
    try:
        png_data = normalize_icon_png(raw)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="Invalid image file") from exc
    icon_hash = digest_icon(png_data)
    existing = db.query(IconAsset).filter_by(hash=icon_hash).first()
    if existing is not None:
        return IconUploadResponseSchema(id=existing.id, hash=existing.hash)

    icon = IconAsset(
        hash=icon_hash, png_data=png_data, created_by_user_id=current_user.id
    )
    db.add(icon)
    db.commit()
    db.refresh(icon)
    return IconUploadResponseSchema(id=icon.id, hash=icon.hash)


@router.get("/icons/lettered/{organization_name}")
def get_lettered_icon(
    organization_name: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    _ = current_user
    seed = organization_name.strip() or "Organization"
    png_data = generate_algorithmic_icon(variant="initials", organization_name=seed)
    return Response(content=png_data, media_type="image/png")


@router.get("/icons/gravatar/{organization_name}")
def get_gravatar_style_icon(
    organization_name: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    _ = current_user
    seed = organization_name.strip() or "Organization"
    png_data = generate_algorithmic_icon(variant="identicon", organization_name=seed)
    return Response(content=png_data, media_type="image/png")


@router.get("/icons", response_model=list[IconListItemSchema])
def list_icons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IconListItemSchema]:
    generic_rows = (
        db.query(DefaultIcon.icon_id)
        .filter(DefaultIcon.icon_id.isnot(None))
        .order_by(DefaultIcon.label.asc())
        .all()
    )
    generic_icon_ids = [row[0] for row in generic_rows]
    generic_icon_id_set = set(generic_icon_ids)

    org_rows = (
        db.query(Organization.icon_id)
        .filter(Organization.is_default.is_(True), Organization.icon_id.isnot(None))
        .order_by(Organization.name.asc())
        .all()
    )
    org_icon_ids = [row[0] for row in org_rows if row[0] not in generic_icon_id_set]
    org_icon_id_set = set(org_icon_ids)

    custom_rows = (
        db.query(IconAsset.id)
        .filter(IconAsset.created_by_user_id == current_user.id)
        .order_by(IconAsset.created_at.desc())
        .all()
    )
    custom_icon_ids = [
        row[0]
        for row in custom_rows
        if row[0] not in generic_icon_id_set and row[0] not in org_icon_id_set
    ]

    ordered_icon_ids: list[UUID] = []
    seen: set[UUID] = set()
    for icon_id in [*generic_icon_ids, *org_icon_ids, *custom_icon_ids]:
        if icon_id in seen:
            continue
        seen.add(icon_id)
        ordered_icon_ids.append(icon_id)

    if not ordered_icon_ids:
        return []

    icons = db.query(IconAsset).filter(IconAsset.id.in_(ordered_icon_ids)).all()
    by_id = {icon.id: icon for icon in icons}
    all_default_icon_ids = generic_icon_id_set | org_icon_id_set
    ordered_icons = [by_id[icon_id] for icon_id in ordered_icon_ids if icon_id in by_id]

    return [
        IconListItemSchema(
            id=icon.id,
            hash=icon.hash,
            is_default=icon.id in all_default_icon_ids,
            created_by_me=icon.created_by_user_id == current_user.id,
        )
        for icon in ordered_icons
    ]


@router.get("/default-icons", response_model=list[DefaultIconSchema])
def list_default_icons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DefaultIconSchema]:
    _ = current_user
    rows = db.query(DefaultIcon).order_by(DefaultIcon.label.asc()).all()
    return [
        DefaultIconSchema(key=row.key, label=row.label, icon_id=row.icon_id)
        for row in rows
    ]


@router.get("/icons/{icon_id}")
def get_icon(
    icon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    icon = db.get(IconAsset, icon_id)
    if icon is None:
        raise HTTPException(status_code=404, detail="Icon not found")
    is_default_org_icon = (
        db.query(Organization.id)
        .filter(Organization.icon_id == icon_id, Organization.is_default.is_(True))
        .first()
        is not None
    )
    is_default_generic_icon = (
        db.query(DefaultIcon.id).filter(DefaultIcon.icon_id == icon_id).first()
        is not None
    )
    is_owned = icon.created_by_user_id == current_user.id
    is_referenced_by_user = (
        db.query(Account.id)
        .filter(Account.user_id == current_user.id, Account.icon_id == icon_id)
        .first()
        is not None
    )
    if not (
        is_default_org_icon
        or is_default_generic_icon
        or is_owned
        or is_referenced_by_user
    ):
        raise HTTPException(status_code=404, detail="Icon not found")
    return Response(content=icon.png_data, media_type="image/png")


@router.delete("/icons/{icon_id}", status_code=204)
def delete_icon(
    icon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    icon = db.get(IconAsset, icon_id)
    if icon is None or icon.created_by_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Icon not found")
    db.delete(icon)
    db.commit()
    return None


@router.get("/organizations", response_model=list[OrganizationSuggestionSchema])
def list_organizations(
    query: str = Query(default="", max_length=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrganizationSuggestionSchema]:
    needle = query.strip().lower()
    default_rows = db.query(Organization).order_by(Organization.name.asc()).all()
    suggestions: dict[str, OrganizationSuggestionSchema] = {}

    for row in default_rows:
        if needle and needle not in row.name.lower():
            continue
        suggestions[row.name.lower()] = OrganizationSuggestionSchema(
            name=row.name,
            url=row.url,
            icon_id=row.icon_id,
            is_default=row.is_default,
        )

    account_rows = (
        db.query(Account.organization, Account.url, Account.icon_id, Account.created_at)
        .filter(Account.user_id == current_user.id, Account.organization.isnot(None))
        .order_by(Account.created_at.desc())
        .all()
    )
    for organization, account_url, icon_id, _ in account_rows:
        if organization is None:
            continue
        name = organization.strip()
        if not name:
            continue
        if needle and needle not in name.lower():
            continue
        key = name.lower()
        if key in suggestions:
            if suggestions[key].icon_id is None and icon_id is not None:
                suggestions[key].icon_id = icon_id
            if not suggestions[key].url and account_url:
                suggestions[key].url = account_url
            continue
        suggestions[key] = OrganizationSuggestionSchema(
            name=name,
            url=account_url,
            icon_id=icon_id,
            is_default=False,
        )

    return sorted(suggestions.values(), key=lambda item: item.name.lower())


@router.put("/accounts/{account_id}/value", response_model=AccountSchema)
def update_account_value(
    account_id: UUID,
    payload: AccountValueUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No value updates provided")

    if "balance_cents" in data and account.type != "cash":
        account.balance_cents = data["balance_cents"]
    if "usd_balance_cents" in data:
        account.usd_balance_cents = data["usd_balance_cents"]
    if "last_payment_date" in data:
        _validate_last_payment_date(data["last_payment_date"])
        account.last_payment_date = data["last_payment_date"]
    if "expiration_date" in data:
        account.expiration_date = data["expiration_date"]

    _replace_nested_positions(
        db,
        current_user.id,
        account_id,
        payload.stock_positions,
        payload.crypto_positions,
        payload.cash_bills,
    )
    if payload.stock_positions:
        _propagate_stock_prices_for_user(db, current_user.id, payload.stock_positions)
    if payload.crypto_positions:
        _propagate_crypto_rates_for_user(db, current_user.id, payload.crypto_positions)
    account.last_update = datetime.utcnow()
    _record_account_value_history(db, account)
    db.commit()
    db.refresh(account)
    return _serialize_account(db, account)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return None


@router.get("/stocks", response_model=list[StockSchema])
def get_stocks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Stock]:
    return (
        db.query(Stock)
        .filter(Stock.user_id == current_user.id)
        .order_by(Stock.ticker.asc())
        .all()
    )


@router.post("/stocks", response_model=StockSchema)
def create_stock(
    payload: StockCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Stock:
    stock = Stock(
        user_id=current_user.id,
        name=payload.name,
        ticker=payload.ticker.upper(),
        exchange=payload.exchange,
        last_price_cents=max(0, payload.last_price_cents),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.put("/stocks/{stock_id}", response_model=StockSchema)
def update_stock(
    stock_id: UUID,
    payload: StockUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Stock:
    stock = (
        db.query(Stock)
        .filter(Stock.id == stock_id, Stock.user_id == current_user.id)
        .first()
    )
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        stock.name = data["name"]
    if "ticker" in data:
        stock.ticker = data["ticker"].upper()
    if "exchange" in data:
        stock.exchange = data["exchange"]
    if "last_price_cents" in data and data["last_price_cents"] is not None:
        new_price = max(0, int(data["last_price_cents"]))
        target_ticker = (data.get("ticker") or stock.ticker).upper()
        (
            db.query(Stock)
            .filter(Stock.user_id == current_user.id, Stock.ticker == target_ticker)
            .update(
                {
                    "last_price_cents": new_price,
                    "updated_at": datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        stock.last_price_cents = new_price
    stock.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/stocks/{stock_id}", status_code=204)
def delete_stock(
    stock_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stock = (
        db.query(Stock)
        .filter(Stock.id == stock_id, Stock.user_id == current_user.id)
        .first()
    )
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    in_use = db.query(AccountStockPosition).filter_by(stock_id=stock_id).first()
    if in_use is not None:
        raise HTTPException(
            status_code=400, detail="Stock is referenced by account positions"
        )

    db.delete(stock)
    db.commit()
    return None
