from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from mp.db.account_history import record_account_value_history
from mp.models.recurring_period import RecurringPeriod, parse_recurring_period
from mp.schema.account import Account
from mp.schema.expense import Expense

LEGACY_RECURRING = {
    "daily": '{"kind":"daily_weekdays","weekdays":[0,1,2,3,4,5,6]}',
    "weekly": '{"kind":"weekly_weekday","weekday":0}',
    "biweekly": '{"kind":"biweekly_weekday","weekday":0,"start_date":"2025-01-06"}',
    "monthly": '{"kind":"monthly_day","day":1}',
    "yearly": '{"kind":"yearly_month_day","month":1,"day":1}',
}


@dataclass
class SimulatedExpensePosting:
    expense_id: UUID
    account_id: UUID
    effective_date: date
    delta_cents: int
    status: str
    reason: str | None = None


@dataclass
class ExpenseSimulation:
    postings: list[SimulatedExpensePosting]
    account_deltas: dict[UUID, int]


def _parse_period(raw: str | None) -> RecurringPeriod | None:
    value = (raw or "").strip()
    if not value:
        return None
    if value.lower() in LEGACY_RECURRING:
        value = LEGACY_RECURRING[value.lower()]
    try:
        return parse_recurring_period(value)
    except ValueError:
        return None


def _is_liability(account_type: str) -> bool:
    return account_type in {"credit_card", "line_of_credit", "loan"}


def _balance_field(account_type: str) -> str | None:
    if account_type == "crypto_exchange":
        return "usd_balance_cents"
    if account_type == "cash":
        return None
    return "balance_cents"


def _account_delta_for_expense(account_type: str, amount_cents: int) -> int:
    return int(amount_cents) if _is_liability(account_type) else -int(amount_cents)


def _first_due(expense: Expense, period: RecurringPeriod | None) -> date | None:
    if expense.next_expensed_date is not None:
        return expense.next_expensed_date
    if expense.last_expensed_date is None or period is None:
        return None
    return period.next_on_or_after(expense.last_expensed_date + timedelta(days=1))


def _iter_due_dates(
    expense: Expense, up_to: date, period: RecurringPeriod | None
) -> Iterable[date]:
    if not expense.enabled:
        return []
    due = _first_due(expense, period)
    if due is None:
        return []
    items: list[date] = []
    guard = 0
    while due <= up_to and guard < 2000:
        items.append(due)
        if period is None:
            break
        due = period.next_on_or_after(due + timedelta(days=1))
        guard += 1
    return items


def run_expense_simulation(
    db: Session,
    user_id: UUID,
    as_of_date: date,
    *,
    apply: bool,
    lock: bool = False,
) -> ExpenseSimulation:
    if lock:
        acquired = db.execute(
            text("SELECT pg_try_advisory_xact_lock(99422118)")
        ).scalar_one()
        if not acquired:
            return ExpenseSimulation(postings=[], account_deltas={})

    expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
    accounts = {
        a.id: a for a in db.query(Account).filter(Account.user_id == user_id).all()
    }
    postings: list[SimulatedExpensePosting] = []
    account_deltas: dict[UUID, int] = {}
    now = datetime.utcnow()

    for expense in expenses:
        if expense.linked_account_id is None:
            continue
        account = accounts.get(expense.linked_account_id)
        if account is None:
            continue
        if bool(account.closed):
            postings.append(
                SimulatedExpensePosting(
                    expense_id=expense.id,
                    account_id=account.id,
                    effective_date=as_of_date,
                    delta_cents=0,
                    status="skipped",
                    reason="linked account is closed",
                )
            )
            continue
        period = _parse_period(expense.general_frequency)
        due_dates = list(_iter_due_dates(expense, as_of_date, period))
        if not due_dates:
            continue

        field = _balance_field(account.type)
        if field is None:
            postings.append(
                SimulatedExpensePosting(
                    expense_id=expense.id,
                    account_id=account.id,
                    effective_date=due_dates[0],
                    delta_cents=0,
                    status="skipped",
                    reason="unsupported account type",
                )
            )
            continue

        for due_date in due_dates:
            delta = _account_delta_for_expense(
                account.type, int(expense.estimated_amount_cents or 0)
            )
            postings.append(
                SimulatedExpensePosting(
                    expense_id=expense.id,
                    account_id=account.id,
                    effective_date=due_date,
                    delta_cents=delta,
                    status="applied" if apply else "planned",
                )
            )
            account_deltas[account.id] = account_deltas.get(account.id, 0) + delta
            if apply:
                setattr(account, field, int(getattr(account, field) or 0) + delta)
                record_account_value_history(db, account, recorded_at=now)

        if apply:
            last_due = due_dates[-1]
            expense.last_expensed_date = last_due
            if period is None:
                expense.next_expensed_date = None
                expense.next_date_is_static = False
            else:
                expense.next_expensed_date = period.next_on_or_after(
                    last_due + timedelta(days=1)
                )
                expense.next_date_is_static = False
            expense.updated_at = now

    return ExpenseSimulation(postings=postings, account_deltas=account_deltas)
