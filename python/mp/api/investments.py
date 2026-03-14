from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.models.recurring_period import parse_recurring_period
from mp.schema.account import Account
from mp.schema.investment import (
    Investment,
    InvestmentCreateSchema,
    InvestmentSchema,
    InvestmentUpdateSchema,
)
from mp.schema.user import User

router = APIRouter()

LEGACY_RECURRING_PERIODS = {"daily", "weekly", "biweekly", "monthly", "yearly"}
SOURCE_ACCOUNT_TYPES = {"checking"}
DESTINATION_ACCOUNT_TYPES = {
    "savings",
    "stocks_account",
    "crypto_exchange",
    "retirement",
    "investment_fund",
}


def _validate_recurring_period(raw: str | None) -> None:
    if raw is None:
        return
    normalized = raw.strip()
    if not normalized:
        return
    if normalized.lower() in LEGACY_RECURRING_PERIODS:
        return
    try:
        parse_recurring_period(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _derive_next_investment_date(
    last_invested_date: date | None, general_frequency: str | None
) -> date | None:
    if last_invested_date is None or general_frequency is None:
        return None
    normalized = general_frequency.strip()
    if not normalized:
        return None
    if normalized.lower() in LEGACY_RECURRING_PERIODS:
        legacy_map = {
            "daily": '{"kind":"daily_weekdays","weekdays":[0,1,2,3,4,5,6]}',
            "weekly": '{"kind":"weekly_weekday","weekday":0}',
            "biweekly": '{"kind":"biweekly_weekday","weekday":0,"start_date":"2025-01-06"}',
            "monthly": '{"kind":"monthly_day","day":1}',
            "yearly": '{"kind":"yearly_month_day","month":1,"day":1}',
        }
        normalized = legacy_map[normalized.lower()]
    try:
        period = parse_recurring_period(normalized)
    except ValueError:
        return None
    return period.next_on_or_after(last_invested_date + timedelta(days=1))


def _owned_account(
    db: Session, user_id: UUID, account_id: UUID | None
) -> Account | None:
    if account_id is None:
        return None
    return (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == user_id)
        .first()
    )


def _validate_payload(
    payload: InvestmentCreateSchema,
    source_account: Account | None,
    destination_account: Account | None,
) -> None:
    if payload.amount_cents < 0:
        raise HTTPException(status_code=400, detail="amount_cents must be >= 0")
    if source_account is None:
        raise HTTPException(status_code=400, detail="source_account_id is required")
    if destination_account is None:
        raise HTTPException(
            status_code=400, detail="destination_account_id is required"
        )
    if source_account.id == destination_account.id:
        raise HTTPException(
            status_code=400,
            detail="source_account_id must be different from destination_account_id",
        )
    if source_account.type not in SOURCE_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400, detail="source_account_id must be a checking account"
        )
    if destination_account.type not in DESTINATION_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "destination_account_id must be a savings, stocks, crypto exchange, "
                "retirement, or investment fund account"
            ),
        )
    _validate_recurring_period(payload.general_frequency)
    if payload.next_date_is_static and payload.next_investment_date is None:
        raise HTTPException(
            status_code=400,
            detail="next_investment_date is required when next_date_is_static=true",
        )


def _serialize_investment(investment: Investment) -> InvestmentSchema:
    return InvestmentSchema.model_validate(investment)


@router.get("/investments", response_model=list[InvestmentSchema])
def get_investments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InvestmentSchema]:
    rows = (
        db.query(Investment)
        .filter(Investment.user_id == current_user.id)
        .order_by(
            Investment.enabled.desc(),
            Investment.next_investment_date.asc().nulls_last(),
            Investment.created_at.asc(),
        )
        .all()
    )
    return [_serialize_investment(row) for row in rows]


@router.post("/investments", response_model=InvestmentSchema)
def create_investment(
    payload: InvestmentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvestmentSchema:
    source_account = _owned_account(db, current_user.id, payload.source_account_id)
    destination_account = _owned_account(
        db, current_user.id, payload.destination_account_id
    )
    _validate_payload(payload, source_account, destination_account)
    now = datetime.utcnow()
    next_date = payload.next_investment_date
    if not payload.next_date_is_static:
        next_date = _derive_next_investment_date(
            payload.last_invested_date, payload.general_frequency
        )
    investment = Investment(
        user_id=current_user.id,
        source_account_id=payload.source_account_id,
        destination_account_id=payload.destination_account_id,
        amount_cents=payload.amount_cents,
        enabled=payload.enabled,
        general_frequency=payload.general_frequency,
        last_invested_date=payload.last_invested_date,
        next_investment_date=next_date,
        next_date_is_static=payload.next_date_is_static,
        created_at=now,
        updated_at=now,
    )
    db.add(investment)
    db.commit()
    db.refresh(investment)
    return _serialize_investment(investment)


@router.put("/investments/{investment_id}", response_model=InvestmentSchema)
def update_investment(
    investment_id: UUID,
    payload: InvestmentUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvestmentSchema:
    investment = (
        db.query(Investment)
        .filter(Investment.id == investment_id, Investment.user_id == current_user.id)
        .first()
    )
    if investment is None:
        raise HTTPException(status_code=404, detail="Investment not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _serialize_investment(investment)

    source_account = _owned_account(
        db, current_user.id, data.get("source_account_id", investment.source_account_id)
    )
    destination_account = _owned_account(
        db,
        current_user.id,
        data.get("destination_account_id", investment.destination_account_id),
    )
    merged = InvestmentCreateSchema(
        source_account_id=data.get("source_account_id", investment.source_account_id),
        destination_account_id=data.get(
            "destination_account_id", investment.destination_account_id
        ),
        amount_cents=data.get("amount_cents", investment.amount_cents),
        enabled=data.get("enabled", investment.enabled),
        general_frequency=data.get("general_frequency", investment.general_frequency),
        last_invested_date=data.get(
            "last_invested_date", investment.last_invested_date
        ),
        next_investment_date=data.get(
            "next_investment_date", investment.next_investment_date
        ),
        next_date_is_static=data.get(
            "next_date_is_static", investment.next_date_is_static
        ),
    )
    _validate_payload(merged, source_account, destination_account)

    for field in [
        "source_account_id",
        "destination_account_id",
        "amount_cents",
        "enabled",
        "general_frequency",
        "last_invested_date",
        "next_investment_date",
        "next_date_is_static",
    ]:
        if field in data:
            setattr(investment, field, data[field])

    if not investment.next_date_is_static:
        investment.next_investment_date = _derive_next_investment_date(
            investment.last_invested_date, investment.general_frequency
        )
    investment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(investment)
    return _serialize_investment(investment)


@router.delete("/investments/{investment_id}", status_code=204)
def delete_investment(
    investment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    investment = (
        db.query(Investment)
        .filter(Investment.id == investment_id, Investment.user_id == current_user.id)
        .first()
    )
    if investment is None:
        raise HTTPException(status_code=404, detail="Investment not found")
    db.delete(investment)
    db.commit()
