from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mp.db import get_db
from mp.api.auth import get_current_user
from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCreateSchema,
    AccountCryptoPosition,
    AccountSchema,
    AccountStockPosition,
    AccountUpdateSchema,
    CashBillSchema,
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


def _validate_account_type(account_type: str) -> None:
    if account_type not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported account type: {account_type}"
        )


def _validate_type_requirements(
    payload: AccountCreateSchema | AccountUpdateSchema,
) -> None:
    if payload.type is None:
        return

    required_fields_by_type = {
        "checking": [
            "balance_cents",
            "fee_amount_cents",
            "fee_period",
            "routing_number",
        ],
        "savings": [
            "apy_bps",
            "compound_period",
            "balance_cents",
            "fee_amount_cents",
            "fee_period",
            "routing_number",
        ],
        "cash": ["cash_bills"],
        "line_of_credit": [
            "balance_cents",
            "fee_amount_cents",
            "fee_period",
            "apr_bps",
            "compound_period",
            "billing_day",
            "payment_day",
        ],
        "credit_card": [
            "balance_cents",
            "fee_amount_cents",
            "fee_period",
            "apr_bps",
            "billing_day",
            "payment_day",
            "compound_period",
            "expiration_date",
            "cvc",
        ],
        "stocks_account": ["stock_positions"],
        "crypto_exchange": ["usd_balance_cents", "crypto_positions"],
        "crypto_wallet": ["crypto_positions"],
        "retirement": ["balance_cents", "retirement_account_type"],
        "loan": [
            "balance_cents",
            "apr_bps",
            "compound_period",
            "payment_amount_cents",
            "payment_day",
        ],
        "rewards_card": ["balance_cents", "expiration_date"],
    }

    for required_field in required_fields_by_type[payload.type]:
        value = getattr(payload, required_field, None)
        if value is None:
            raise HTTPException(
                status_code=400,
                detail=f"{required_field} is required for type {payload.type}",
            )


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


def _serialize_account(db: Session, account: Account) -> AccountSchema:
    stock_positions, crypto_positions, cash_bills = _hydrate_nested_positions(
        db, account
    )
    return AccountSchema(
        id=account.id,
        user_id=account.user_id,
        account_number=account.account_number,
        name=account.name,
        type=account.type,
        organization=account.organization,
        url=account.url,
        notes=account.notes,
        balance_cents=account.balance_cents,
        fee_amount_cents=account.fee_amount_cents,
        fee_period=account.fee_period,
        routing_number=account.routing_number,
        apy_bps=account.apy_bps,
        compound_period=account.compound_period,
        apr_bps=account.apr_bps,
        billing_day=account.billing_day,
        payment_day=account.payment_day,
        expiration_date=account.expiration_date,
        cvc=account.cvc,
        usd_balance_cents=account.usd_balance_cents,
        retirement_account_type=account.retirement_account_type,
        payment_amount_cents=account.payment_amount_cents,
        date_opened=account.date_opened,
        last_update=account.last_update,
        stock_positions=[
            PositionStockSchema(stock_id=position.stock_id, quantity=position.quantity)
            for position in stock_positions
        ],
        crypto_positions=[
            PositionCryptoSchema(ticker=position.ticker, quantity=position.quantity)
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
        updated_at=account.updated_at,
    )


def _replace_nested_positions(
    db: Session,
    account_id: UUID,
    stock_positions: list | None,
    crypto_positions: list | None,
    cash_bills: list | None,
) -> None:
    if stock_positions is not None:
        db.query(AccountStockPosition).filter_by(account_id=account_id).delete()
        for item in stock_positions:
            db.add(
                AccountStockPosition(
                    account_id=account_id,
                    stock_id=item.stock_id,
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


@router.get("/accounts", response_model=list[AccountSchema])
def get_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountSchema]:
    accounts = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .order_by(Account.created_at.desc())
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


@router.post("/accounts", response_model=AccountSchema)
def create_account(
    payload: AccountCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    _validate_account_type(payload.type)
    _validate_type_requirements(payload)

    account = Account(
        user_id=current_user.id,
        account_number=payload.account_number,
        name=payload.name,
        type=payload.type,
        organization=payload.organization,
        url=payload.url,
        notes=payload.notes,
        balance_cents=payload.balance_cents,
        fee_amount_cents=payload.fee_amount_cents,
        fee_period=payload.fee_period,
        routing_number=payload.routing_number,
        apy_bps=payload.apy_bps,
        compound_period=payload.compound_period,
        apr_bps=payload.apr_bps,
        billing_day=payload.billing_day,
        payment_day=payload.payment_day,
        expiration_date=payload.expiration_date,
        cvc=payload.cvc,
        usd_balance_cents=payload.usd_balance_cents,
        retirement_account_type=payload.retirement_account_type,
        payment_amount_cents=payload.payment_amount_cents,
        date_opened=payload.date_opened,
        last_update=payload.last_update,
    )
    db.add(account)
    db.flush()

    if payload.stock_positions:
        stock_ids = [item.stock_id for item in payload.stock_positions]
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
        account.id,
        payload.stock_positions,
        payload.crypto_positions,
        payload.cash_bills,
    )

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
        expiration_date=data.get("expiration_date", account.expiration_date),
        cvc=data.get("cvc", account.cvc),
        usd_balance_cents=data.get("usd_balance_cents", account.usd_balance_cents),
        retirement_account_type=data.get(
            "retirement_account_type", account.retirement_account_type
        ),
        payment_amount_cents=data.get(
            "payment_amount_cents", account.payment_amount_cents
        ),
        date_opened=data.get("date_opened", account.date_opened),
        last_update=data.get("last_update", account.last_update),
        stock_positions=payload.stock_positions
        if payload.stock_positions is not None
        else [
            PositionStockSchema(stock_id=position.stock_id, quantity=position.quantity)
            for position in existing_stock_positions
        ],
        crypto_positions=payload.crypto_positions
        if payload.crypto_positions is not None
        else [
            PositionCryptoSchema(ticker=position.ticker, quantity=position.quantity)
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
    _validate_type_requirements(merged_payload)

    if payload.stock_positions is not None and payload.stock_positions:
        stock_ids = [item.stock_id for item in payload.stock_positions]
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
        "expiration_date",
        "cvc",
        "usd_balance_cents",
        "retirement_account_type",
        "payment_amount_cents",
        "date_opened",
        "last_update",
    ]:
        if field in data:
            setattr(account, field, data[field])

    account.updated_at = datetime.utcnow()

    _replace_nested_positions(
        db,
        account_id,
        payload.stock_positions,
        payload.crypto_positions,
        payload.cash_bills,
    )

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
