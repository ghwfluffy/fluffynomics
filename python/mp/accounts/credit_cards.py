"""Monthly card bookkeeping, shared by persistence and read-only projections."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from mp.db.account_history import record_account_value_history
from mp.db.audit_log import format_cents, record_audit_log
from mp.schema.account import Account, AccountSchema, AccountTransfer
from mp.schema.audit_log import AuditLogTriggerType

FUNDING_TYPES = {"checking", "savings"}


class CreditCardEvent(BaseModel):
    account_id: UUID
    account_name: str
    source_account_id: UUID | None = None
    source_account_name: str | None = None
    effective_date: date
    kind: Literal["payment", "interest"]
    amount_cents: int
    net_worth_delta_cents: int


def monthly_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def previous_due(day: date, payment_day: int) -> date:
    month = day.month - 1 or 12
    year = day.year - (day.month == 1)
    return monthly_day(year, month, payment_day)


@dataclass
class CardState:
    account: Account | AccountSchema
    balance: int
    last_payment: date | None
    processed_through: date


def _covered_payment_date(account: Account | AccountSchema) -> date | None:
    last_payment = account.last_payment_date
    if isinstance(account, AccountSchema) and account.queued_credit_card_payment:
        last_payment = max(
            last_payment or date.min,
            account.queued_credit_card_payment.effective_at.date(),
        )
    return last_payment


def card_states(accounts: list[Account] | list[AccountSchema]) -> dict[UUID, CardState]:
    return {
        item.id: CardState(
            account=item,
            balance=int(item.balance_cents or 0),
            last_payment=_covered_payment_date(item),
            processed_through=item.credit_card_processed_through
            or date.today() - timedelta(days=1),
        )
        for item in accounts
    }


def process_card_day(
    states: dict[UUID, CardState],
    day: date,
    pending_cards: set[UUID] | None = None,
) -> list[CreditCardEvent]:
    events: list[CreditCardEvent] = []
    for state in states.values():
        card = state.account
        if card.type != "credit_card" or day <= state.processed_through:
            continue
        state.processed_through = day
        if card.closed:
            continue
        # Billing interest is posted first if both dates fall on the same day.
        billing_day = int(card.billing_day or 0)
        if (
            1 <= billing_day <= 31
            and day == monthly_day(day.year, day.month, billing_day)
            and state.balance > 0
            and int(card.apr_bps or 0) > 0
        ):
            interest = int(
                (
                    Decimal(state.balance)
                    * Decimal(card.apr_bps or 0)
                    / Decimal(120000)
                ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            )
            if interest:
                state.balance += interest
                events.append(
                    CreditCardEvent(
                        account_id=card.id,
                        account_name=card.name,
                        effective_date=day,
                        kind="interest",
                        amount_cents=interest,
                        net_worth_delta_cents=-interest,
                    )
                )
        payment_day = int(card.payment_day or 0)
        source = (
            states.get(card.default_payment_account_id)
            if card.default_payment_account_id
            else None
        )
        if (
            not 1 <= payment_day <= 31
            or day != monthly_day(day.year, day.month, payment_day)
            or state.balance <= 0
            or int(card.minimum_payment_cents or 0) <= 0
            or source is None
            or source.account.closed
            or source.account.type not in FUNDING_TYPES
            or card.id in (pending_cards or set())
            or (
                state.last_payment is not None
                and state.last_payment > previous_due(day, payment_day)
            )
        ):
            continue
        amount = min(state.balance, int(card.minimum_payment_cents or 0))
        state.balance -= amount
        source.balance -= amount
        state.last_payment = day
        events.append(
            CreditCardEvent(
                account_id=card.id,
                account_name=card.name,
                source_account_id=source.account.id,
                source_account_name=source.account.name,
                effective_date=day,
                kind="payment",
                amount_cents=amount,
                net_worth_delta_cents=0,
            )
        )
    return events


def apply_credit_card_automation(
    db: Session,
    user_id: UUID,
    through_date: date,
    *,
    trigger_type: AuditLogTriggerType = "system",
) -> bool:
    # Re-read under row locks so concurrent scheduler/read requests cannot double-post.
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)
        .order_by(Account.id)
        .with_for_update()
        .populate_existing()
        .all()
    )
    states = card_states(accounts)
    pending_cards = {
        item.destination_account_id
        for item in db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == user_id,
            AccountTransfer.applied_at.is_(None),
            AccountTransfer.transfer_kind == "credit_card_payment",
        )
        .all()
    }
    cards = [s for s in states.values() if s.account.type == "credit_card"]
    if not cards:
        return False
    start = min(s.processed_through for s in cards) + timedelta(days=1)
    changed = start <= through_date
    now = datetime.utcnow()
    day = start
    while day <= through_date:
        events = process_card_day(states, day, pending_cards)
        # Update all balances before recording snapshots, including both transfer sides.
        for state in states.values():
            if (
                state.account.type in FUNDING_TYPES
                or state.account.type == "credit_card"
            ):
                if state.balance != int(state.account.balance_cents or 0):
                    state.account.balance_cents = state.balance
        for event in events:
            card = states[event.account_id].account
            card.last_payment_date = states[event.account_id].last_payment
            card.last_update = now
            touched = [card]
            if event.source_account_id:
                source = states[event.source_account_id].account
                source.last_update = now
                touched.append(source)
                db.add(
                    AccountTransfer(
                        user_id=user_id,
                        source_account_id=source.id,
                        destination_account_id=card.id,
                        amount_cents=event.amount_cents,
                        transfer_kind="credit_card_payment",
                        instant_deposit=False,
                        queued_at=now,
                        effective_at=datetime.combine(day, time.min),
                        applied_at=now,
                    )
                )
            for account in touched:
                assert isinstance(account, Account)
                record_account_value_history(db, account, recorded_at=now)
            record_audit_log(
                db,
                user_id,
                trigger_type=trigger_type,
                event_type=f"credit_card_automatic_{event.kind}",
                message=f"{card.name}: automatic {event.kind} of {format_cents(event.amount_cents)}.",
                details=event.model_dump(mode="json"),
                occurred_at=now,
            )
        day += timedelta(days=1)
    for state in cards:
        state.account.credit_card_processed_through = state.processed_through
    return changed


def project_card_day(accounts: list[AccountSchema], day: date) -> list[CreditCardEvent]:
    states = card_states(accounts)
    events = process_card_day(states, day)
    for state in states.values():
        if state.account.type in FUNDING_TYPES or state.account.type == "credit_card":
            state.account.balance_cents = state.balance
        state.account.last_payment_date = state.last_payment
        state.account.credit_card_processed_through = state.processed_through
    return events
