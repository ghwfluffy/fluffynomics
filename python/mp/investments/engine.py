from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from mp.db.account_history import record_account_value_history
from mp.db.audit_log import format_cents, record_audit_log
from mp.models.recurring_period import RecurringPeriod, parse_recurring_period
from mp.schema.account import Account
from mp.schema.audit_log import AuditLogTriggerType
from mp.schema.investment import Investment

LEGACY_RECURRING = {
    "daily": '{"kind":"daily_weekdays","weekdays":[0,1,2,3,4,5,6]}',
    "weekly": '{"kind":"weekly_weekday","weekday":0}',
    "biweekly": '{"kind":"biweekly_weekday","weekday":0,"start_date":"2025-01-06"}',
    "monthly": '{"kind":"monthly_day","day":1}',
    "yearly": '{"kind":"yearly_month_day","month":1,"day":1}',
}

ALLOWED_DESTINATION_TYPES = {
    "savings",
    "stocks_account",
    "crypto_exchange",
    "retirement",
    "investment_fund",
}


@dataclass
class SimulatedInvestmentPosting:
    investment_id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    effective_date: date
    amount_cents: int
    status: str
    reason: str | None = None


@dataclass
class InvestmentSimulation:
    postings: list[SimulatedInvestmentPosting]
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


def _balance_field(account_type: str) -> str | None:
    if account_type == "crypto_exchange":
        return "usd_balance_cents"
    if account_type in {"cash", "crypto_wallet"}:
        return None
    return "balance_cents"


def _account_name(account: Account) -> str:
    return account.name.strip() or "Unnamed account"


def _first_due(investment: Investment, period: RecurringPeriod | None) -> date | None:
    if investment.next_investment_date is not None:
        return investment.next_investment_date
    if investment.last_invested_date is None or period is None:
        return None
    return period.next_on_or_after(investment.last_invested_date + timedelta(days=1))


def _iter_due_dates(
    investment: Investment, up_to: date, period: RecurringPeriod | None
) -> Iterable[date]:
    if not investment.enabled:
        return []
    due = _first_due(investment, period)
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


def run_investment_simulation(
    db: Session,
    user_id: UUID,
    as_of_date: date,
    *,
    apply: bool,
    lock: bool = False,
    trigger_type: AuditLogTriggerType = "system",
) -> InvestmentSimulation:
    if lock:
        acquired = db.execute(
            text("SELECT pg_try_advisory_xact_lock(99422119)")
        ).scalar_one()
        if not acquired:
            return InvestmentSimulation(postings=[], account_deltas={})

    investments = db.query(Investment).filter(Investment.user_id == user_id).all()
    accounts = {
        account.id: account
        for account in db.query(Account).filter(Account.user_id == user_id).all()
    }
    postings: list[SimulatedInvestmentPosting] = []
    account_deltas: dict[UUID, int] = {}
    now = datetime.utcnow()

    for investment in investments:
        source = accounts.get(investment.source_account_id)
        destination = accounts.get(investment.destination_account_id)
        if source is None or destination is None:
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=investment.source_account_id,
                    destination_account_id=investment.destination_account_id,
                    effective_date=as_of_date,
                    amount_cents=0,
                    status="skipped",
                    reason="linked account not found",
                )
            )
            continue
        if bool(source.closed) or bool(destination.closed):
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    effective_date=as_of_date,
                    amount_cents=0,
                    status="skipped",
                    reason="source or destination account is closed",
                )
            )
            continue
        if source.type != "checking":
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    effective_date=as_of_date,
                    amount_cents=0,
                    status="skipped",
                    reason="source account must be checking",
                )
            )
            continue
        if destination.type not in ALLOWED_DESTINATION_TYPES:
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    effective_date=as_of_date,
                    amount_cents=0,
                    status="skipped",
                    reason="destination account type is unsupported",
                )
            )
            continue

        source_field = _balance_field(source.type)
        destination_field = _balance_field(destination.type)
        if source_field is None or destination_field is None:
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    effective_date=as_of_date,
                    amount_cents=0,
                    status="skipped",
                    reason="unsupported account type",
                )
            )
            continue

        period = _parse_period(investment.general_frequency)
        due_dates = list(_iter_due_dates(investment, as_of_date, period))
        if not due_dates:
            continue

        amount_cents = max(0, int(investment.amount_cents or 0))
        for due_date in due_dates:
            postings.append(
                SimulatedInvestmentPosting(
                    investment_id=investment.id,
                    source_account_id=source.id,
                    destination_account_id=destination.id,
                    effective_date=due_date,
                    amount_cents=amount_cents,
                    status="applied" if apply else "planned",
                )
            )
            account_deltas[source.id] = account_deltas.get(source.id, 0) - amount_cents
            account_deltas[destination.id] = (
                account_deltas.get(destination.id, 0) + amount_cents
            )
            if apply:
                setattr(
                    source,
                    source_field,
                    int(getattr(source, source_field) or 0) - amount_cents,
                )
                setattr(
                    destination,
                    destination_field,
                    int(getattr(destination, destination_field) or 0) + amount_cents,
                )
                source.last_update = now
                destination.last_update = now
                record_account_value_history(db, source, recorded_at=now)
                record_account_value_history(db, destination, recorded_at=now)
                record_audit_log(
                    db,
                    user_id,
                    trigger_type=trigger_type,
                    event_type="recurring_investment_applied",
                    message=(
                        f"Recurring investment moved {format_cents(amount_cents)} from "
                        f"{_account_name(source)} to {_account_name(destination)}."
                    ),
                    details={
                        "source_account_name": _account_name(source),
                        "destination_account_name": _account_name(destination),
                        "amount_cents": amount_cents,
                        "effective_date": due_date.isoformat(),
                    },
                    occurred_at=now,
                )

        if apply:
            last_due = due_dates[-1]
            investment.last_invested_date = last_due
            if period is None:
                investment.next_investment_date = None
                investment.next_date_is_static = False
            else:
                investment.next_investment_date = period.next_on_or_after(
                    last_due + timedelta(days=1)
                )
                investment.next_date_is_static = False
            investment.updated_at = now

    return InvestmentSimulation(postings=postings, account_deltas=account_deltas)
