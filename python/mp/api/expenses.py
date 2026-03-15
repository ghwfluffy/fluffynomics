from datetime import date, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from mp.api.auth import get_current_user
from mp.db import get_db
from mp.db.audit_log import format_cents, record_audit_log
from mp.models.recurring_period import parse_recurring_period
from mp.schema.account import Account, AccountIconType, Organization
from mp.schema.expense import (
    Expense,
    ExpenseCreateSchema,
    ExpenseSchema,
    ExpenseUpdateSchema,
)
from mp.schema.user import User

router = APIRouter()

LEGACY_RECURRING_PERIODS = {"daily", "weekly", "biweekly", "monthly", "yearly"}


def _validate_icon_type(icon_type: str | None) -> None:
    if icon_type is None:
        return
    if icon_type not in {item.value for item in AccountIconType}:
        raise HTTPException(
            status_code=400, detail=f"Unsupported icon_type: {icon_type}"
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
    name: str | None,
    db: Session,
) -> tuple[Literal["Letters", "Gravatar", "Icon"], UUID | None]:
    normalized_type = _coerce_icon_type(icon_type)
    if normalized_type != AccountIconType.ICON.value:
        return normalized_type, None
    if icon_id is not None:
        return normalized_type, icon_id
    if name:
        org = db.query(Organization).filter_by(name=name.strip()).first()
        if org is not None:
            return normalized_type, org.icon_id
    return normalized_type, None


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


def _derive_next_expensed_date(
    last_expensed_date: date | None, general_frequency: str | None
) -> date | None:
    if last_expensed_date is None or general_frequency is None:
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
    return period.next_on_or_after(last_expensed_date + timedelta(days=1))


def _validate_payload(payload: ExpenseCreateSchema) -> None:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not payload.category.strip():
        raise HTTPException(status_code=400, detail="category is required")
    if payload.estimated_amount_cents < 0:
        raise HTTPException(
            status_code=400, detail="estimated_amount_cents must be >= 0"
        )
    if payload.linked_account_id is None:
        raise HTTPException(status_code=400, detail="linked_account_id is required")
    _validate_recurring_period(payload.general_frequency)
    if payload.next_date_is_static and payload.next_expensed_date is None:
        raise HTTPException(
            status_code=400,
            detail="next_expensed_date is required when next_date_is_static=true",
        )


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


def _serialize_expense(expense: Expense) -> ExpenseSchema:
    return ExpenseSchema.model_validate(expense)


def _expense_name(expense: Expense) -> str:
    return expense.name.strip() or "Unnamed expense"


@router.get("/expenses", response_model=list[ExpenseSchema])
def get_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExpenseSchema]:
    rows = (
        db.query(Expense)
        .filter(Expense.user_id == current_user.id)
        .order_by(Expense.category.asc(), Expense.name.asc())
        .all()
    )
    return [_serialize_expense(item) for item in rows]


@router.post("/expenses", response_model=ExpenseSchema)
def create_expense(
    payload: ExpenseCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseSchema:
    _validate_payload(payload)
    _validate_icon_type(payload.icon_type)
    linked_account = _owned_account(db, current_user.id, payload.linked_account_id)
    if linked_account is None:
        raise HTTPException(status_code=400, detail="linked_account_id is required")
    now = datetime.utcnow()
    icon_type, icon_id = _normalize_icon_selection(
        payload.icon_type, payload.icon_id, payload.category, db
    )
    next_date = payload.next_expensed_date
    if not payload.next_date_is_static:
        next_date = _derive_next_expensed_date(
            payload.last_expensed_date, payload.general_frequency
        )

    expense = Expense(
        user_id=current_user.id,
        name=payload.name.strip(),
        category=payload.category.strip(),
        notes=payload.notes.strip() if payload.notes is not None else None,
        icon_id=icon_id,
        icon_type=icon_type,
        estimated_amount_cents=payload.estimated_amount_cents,
        linked_account_id=payload.linked_account_id,
        enabled=payload.enabled,
        general_frequency=payload.general_frequency,
        last_expensed_date=payload.last_expensed_date,
        next_expensed_date=next_date,
        next_date_is_static=payload.next_date_is_static,
        created_at=now,
        updated_at=now,
    )
    db.add(expense)
    record_audit_log(
        db,
        current_user.id,
        trigger_type="user",
        event_type="expense_created",
        message=(
            f"Created expense {_expense_name(expense)} for "
            f"{format_cents(int(expense.estimated_amount_cents or 0))}."
        ),
        details={
            "expense_name": _expense_name(expense),
            "category": expense.category,
            "estimated_amount_cents": int(expense.estimated_amount_cents or 0),
        },
        occurred_at=now,
    )
    db.commit()
    db.refresh(expense)
    return _serialize_expense(expense)


@router.put("/expenses/{expense_id}", response_model=ExpenseSchema)
def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExpenseSchema:
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.user_id == current_user.id)
        .first()
    )
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _serialize_expense(expense)
    if "icon_type" in data:
        _validate_icon_type(data["icon_type"])
    linked_account_id = data.get("linked_account_id", expense.linked_account_id)
    if linked_account_id is None:
        raise HTTPException(status_code=400, detail="linked_account_id is required")

    merged = ExpenseCreateSchema(
        name=data.get("name", expense.name),
        category=data.get("category", expense.category),
        notes=data.get("notes", expense.notes),
        icon_id=data.get("icon_id", expense.icon_id),
        icon_type=data.get("icon_type", expense.icon_type),
        estimated_amount_cents=data.get(
            "estimated_amount_cents", expense.estimated_amount_cents
        ),
        linked_account_id=linked_account_id,
        enabled=data.get("enabled", expense.enabled),
        general_frequency=data.get("general_frequency", expense.general_frequency),
        last_expensed_date=data.get("last_expensed_date", expense.last_expensed_date),
        next_expensed_date=data.get("next_expensed_date", expense.next_expensed_date),
        next_date_is_static=data.get(
            "next_date_is_static", expense.next_date_is_static
        ),
    )
    _validate_payload(merged)
    linked_account = _owned_account(db, current_user.id, merged.linked_account_id)
    if linked_account is None:
        raise HTTPException(status_code=400, detail="linked_account_id is required")
    icon_type, icon_id = _normalize_icon_selection(
        merged.icon_type,
        merged.icon_id,
        merged.category,
        db,
    )
    expense.name = merged.name.strip()
    expense.category = merged.category.strip()
    expense.notes = merged.notes.strip() if merged.notes is not None else None
    expense.icon_type = icon_type
    expense.icon_id = icon_id
    expense.estimated_amount_cents = merged.estimated_amount_cents
    expense.linked_account_id = merged.linked_account_id
    expense.enabled = merged.enabled
    expense.general_frequency = merged.general_frequency
    expense.last_expensed_date = merged.last_expensed_date
    expense.next_date_is_static = merged.next_date_is_static
    if merged.next_date_is_static:
        expense.next_expensed_date = merged.next_expensed_date
    else:
        expense.next_expensed_date = _derive_next_expensed_date(
            merged.last_expensed_date, merged.general_frequency
        )
    expense.updated_at = datetime.utcnow()
    record_audit_log(
        db,
        current_user.id,
        trigger_type="user",
        event_type="expense_updated",
        message=f"Updated expense {_expense_name(expense)}.",
        details={
            "expense_name": _expense_name(expense),
            "category": expense.category,
            "fields": sorted(data.keys()),
        },
        occurred_at=expense.updated_at,
    )
    db.commit()
    db.refresh(expense)
    return _serialize_expense(expense)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(
    expense_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.user_id == current_user.id)
        .first()
    )
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    record_audit_log(
        db,
        current_user.id,
        trigger_type="user",
        event_type="expense_deleted",
        message=f"Deleted expense {_expense_name(expense)}.",
        details={"expense_name": _expense_name(expense), "category": expense.category},
    )
    db.delete(expense)
    db.commit()
