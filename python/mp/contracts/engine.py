from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from mp.recurring_period import RecurringPeriod, parse_recurring_period
from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCryptoPosition,
    AccountStockPosition,
    Stock,
)
from mp.schema.contract import Contract, ContractPosting


LEGACY_RECURRENCE = {
    "daily": '{"kind":"daily_weekdays","weekdays":[0,1,2,3,4,5,6]}',
    "weekly": '{"kind":"weekly_weekday","weekday":0}',
    "biweekly": '{"kind":"biweekly_weekday","weekday":0,"start_date":"2025-01-06"}',
    "monthly": '{"kind":"monthly_day","day":1}',
    "yearly": '{"kind":"yearly_month_day","month":1,"day":1}',
}


@dataclass
class SimulatedPosting:
    contract_id: UUID
    effective_date: date
    delta_cents: int
    status: str
    reason: str | None = None


@dataclass
class ContractSimulation:
    postings: list[SimulatedPosting]
    account_deltas: dict[UUID, int]
    projected_last_payment: dict[UUID, date]


def _as_date(raw: date | str | None) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(raw[:10])


def _parse_period(contract: Contract) -> RecurringPeriod | None:
    raw = (contract.payment_period or "").strip()
    if not raw and contract.payment_day:
        raw = f'{{"kind":"monthly_day","day":{int(contract.payment_day)}}}'
    if raw.lower() in LEGACY_RECURRENCE:
        raw = LEGACY_RECURRENCE[raw.lower()]
    if not raw:
        return None
    try:
        return parse_recurring_period(raw)
    except ValueError:
        return None


def _previous_occurrence(period: RecurringPeriod, before_value: date) -> date | None:
    # Generic backwards lookup across period types.
    search = before_value - timedelta(days=400)
    current = period.next_on_or_after(search)
    previous: date | None = None
    guard = 0
    while current < before_value and guard < 2000:
        previous = current
        current = period.next_on_or_after(current + timedelta(days=1))
        guard += 1
    return previous


def _first_due_after_last_payment(contract: Contract, period: RecurringPeriod) -> date:
    baseline = contract.last_payment_date or contract.created_at.date()
    next_due = period.next_on_or_after(baseline + timedelta(days=1))
    if contract.last_payment_date is None:
        return next_due
    previous_due = _previous_occurrence(period, next_due)
    if (
        previous_due is not None
        and previous_due < contract.last_payment_date < next_due
    ):
        # Early payment: skip the already-covered upcoming cycle.
        return period.next_on_or_after(next_due + timedelta(days=1))
    return next_due


def _iter_due_dates(contract: Contract, up_to: date) -> Iterable[date]:
    period = _parse_period(contract)
    if period is None:
        return []
    expiry = contract.expiration_date or date(2099, 1, 1)
    end_date = min(expiry, up_to)
    if end_date < (contract.last_payment_date or contract.created_at.date()):
        return []
    due = _first_due_after_last_payment(contract, period)
    items: list[date] = []
    guard = 0
    while due <= end_date and guard < 4000:
        items.append(due)
        due = period.next_on_or_after(due + timedelta(days=1))
        guard += 1
    return items


def _balance_field(account: Account) -> str | None:
    if account.type == "crypto_exchange":
        return "usd_balance_cents"
    if account.type == "cash":
        return None
    return "balance_cents"


def _delta_for_contract(contract: Contract) -> int:
    amount = int(contract.amount_cents or 0)
    if contract.type == "income":
        return amount
    return -amount


def _compute_account_value_cents(db: Session, account: Account) -> int:
    if account.type == "cash":
        denoms = (
            db.query(AccountCashDenomination).filter_by(account_id=account.id).all()
        )
        return int(sum(d.denomination_cents * d.quantity for d in denoms))
    if account.type in {"crypto_wallet", "crypto_exchange"}:
        crypto_positions = (
            db.query(AccountCryptoPosition).filter_by(account_id=account.id).all()
        )
        total = int(
            sum(
                int(round(float(p.quantity) * int(p.exchange_rate_cents or 0)))
                for p in crypto_positions
            )
        )
        if account.type == "crypto_exchange":
            total += int(account.usd_balance_cents or 0)
        return total
    if account.type == "stocks_account":
        stock_positions = (
            db.query(AccountStockPosition).filter_by(account_id=account.id).all()
        )
        stock_ids = [p.stock_id for p in stock_positions]
        prices = {
            s.id: int(s.last_price_cents or 0)
            for s in db.query(Stock).filter(Stock.id.in_(stock_ids)).all()
        }
        total = int(
            sum(
                int(round(float(p.quantity) * prices.get(p.stock_id, 0)))
                for p in stock_positions
            )
        )
        return total + int(account.balance_cents or 0)
    return int(account.balance_cents or 0)


def run_contract_simulation(
    db: Session,
    user_id: UUID,
    as_of_date: date,
    *,
    apply: bool,
    lock: bool = False,
) -> ContractSimulation:
    if lock:
        acquired = db.execute(
            text("SELECT pg_try_advisory_xact_lock(99422117)")
        ).scalar_one()
        if not acquired:
            return ContractSimulation(
                postings=[], account_deltas={}, projected_last_payment={}
            )

    contracts = (
        db.query(Contract)
        .filter(Contract.user_id == user_id, Contract.automatic.is_(True))
        .all()
    )
    accounts = {
        a.id: a for a in db.query(Account).filter(Account.user_id == user_id).all()
    }
    postings: list[SimulatedPosting] = []
    account_deltas: dict[UUID, int] = {}
    projected_last_payment: dict[UUID, date] = {}
    now = datetime.utcnow()

    for contract in contracts:
        linked = accounts.get(contract.linked_account_id)
        source = (
            accounts.get(contract.source_account_id)
            if contract.source_account_id
            else None
        )
        if linked is None:
            postings.append(
                SimulatedPosting(
                    contract_id=contract.id,
                    effective_date=as_of_date,
                    delta_cents=0,
                    status="skipped",
                    reason="linked account not found",
                )
            )
            continue
        due_dates = list(_iter_due_dates(contract, as_of_date))
        for due_date in due_dates:
            delta = _delta_for_contract(contract)
            if contract.type == "transfer":
                if source is None:
                    postings.append(
                        SimulatedPosting(
                            contract_id=contract.id,
                            effective_date=due_date,
                            delta_cents=0,
                            status="skipped",
                            reason="missing source account",
                        )
                    )
                    continue
                source_field = _balance_field(source)
                linked_field = _balance_field(linked)
                if source_field is None or linked_field is None:
                    postings.append(
                        SimulatedPosting(
                            contract_id=contract.id,
                            effective_date=due_date,
                            delta_cents=0,
                            status="skipped",
                            reason="unsupported account type for transfer",
                        )
                    )
                    continue
            else:
                field = _balance_field(linked)
                if field is None:
                    postings.append(
                        SimulatedPosting(
                            contract_id=contract.id,
                            effective_date=due_date,
                            delta_cents=0,
                            status="skipped",
                            reason="unsupported account type",
                        )
                    )
                    continue

            existing = (
                db.query(ContractPosting)
                .filter_by(contract_id=contract.id, effective_date=due_date)
                .first()
            )
            if existing is not None:
                projected_last_payment[contract.id] = max(
                    projected_last_payment.get(contract.id, due_date), due_date
                )
                continue

            postings.append(
                SimulatedPosting(
                    contract_id=contract.id,
                    effective_date=due_date,
                    delta_cents=delta,
                    status="applied" if apply else "planned",
                )
            )
            projected_last_payment[contract.id] = max(
                projected_last_payment.get(contract.id, due_date), due_date
            )

            if contract.type == "transfer":
                assert source is not None
                account_deltas[source.id] = account_deltas.get(source.id, 0) - int(
                    contract.amount_cents or 0
                )
                account_deltas[linked.id] = account_deltas.get(linked.id, 0) + int(
                    contract.amount_cents or 0
                )
                if apply:
                    source_field = _balance_field(source)
                    linked_field = _balance_field(linked)
                    assert source_field is not None and linked_field is not None
                    setattr(
                        source,
                        source_field,
                        int(getattr(source, source_field) or 0)
                        - int(contract.amount_cents or 0),
                    )
                    setattr(
                        linked,
                        linked_field,
                        int(getattr(linked, linked_field) or 0)
                        + int(contract.amount_cents or 0),
                    )
            else:
                field = _balance_field(linked)
                assert field is not None
                account_deltas[linked.id] = account_deltas.get(linked.id, 0) + delta
                if apply:
                    setattr(
                        linked,
                        field,
                        int(getattr(linked, field) or 0) + delta,
                    )

            if apply:
                db.add(
                    ContractPosting(
                        contract_id=contract.id,
                        user_id=user_id,
                        effective_date=due_date,
                        delta_cents=delta,
                        applied_at=now,
                    )
                )

        if apply and contract.id in projected_last_payment:
            contract.last_payment_date = projected_last_payment[contract.id]
            contract.updated_at = now

    return ContractSimulation(
        postings=postings,
        account_deltas=account_deltas,
        projected_last_payment=projected_last_payment,
    )
