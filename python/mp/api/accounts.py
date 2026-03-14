from datetime import date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
from sqlalchemy.orm import Session

from mp.db import get_db
from mp.api.auth import get_current_user
from mp.contracts.engine import run_contract_simulation
from mp.expenses.engine import run_expense_simulation
from mp.icons import digest_icon, generate_algorithmic_icon, normalize_icon_png
from mp.robinhood_statement import parse_robinhood_statement
from mp.recurring_period import parse_recurring_period
from mp.schema.account import (
    Account,
    AccountTransfer,
    AccountTransferCreateSchema,
    AccountTransferSchema,
    AccountTransferUpdateSchema,
    AccountCashDenomination,
    AccountCreateSchema,
    AccountIconType,
    AccountValueHistory,
    AccountValueHistorySchema,
    NetWorthHistoryPointSchema,
    NetWorthForecastPointSchema,
    AccountCryptoPosition,
    DefaultIcon,
    DefaultIconSchema,
    AccountRankUpdateSchema,
    AccountSchema,
    AccountStockPosition,
    AccountUpdateSchema,
    AccountValueUpdateSchema,
    QueueCreditCardPaymentCreateSchema,
    CashBillSchema,
    IconAsset,
    IconListItemSchema,
    IconUploadResponseSchema,
    NetWorthDailySnapshot,
    Organization,
    OrganizationSuggestionSchema,
    PositionCryptoSchema,
    PositionStockSchema,
    QueuedCreditCardPaymentSchema,
    Stock,
    StockCreateSchema,
    StockSchema,
    StockUpdateSchema,
)
from mp.schema.contract import Contract
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
LIABILITY_ACCOUNT_TYPES = {"credit_card", "line_of_credit", "loan"}
TRANSFER_KINDS = {"standard", "credit_card_payment"}


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


def _account_rewards_cents(account: Account) -> int:
    return max(0, int(account.rewards_balance_cents or 0))


def _net_worth_sign_for_account_type(account_type: str) -> int:
    if account_type in {"credit_card", "line_of_credit", "loan"}:
        return -1
    return 1


def _net_worth_contribution_cents(db: Session, account: Account) -> int:
    base_value = _compute_account_value_cents(db, account)
    rewards_value = _account_rewards_cents(account)
    if account.type in {"credit_card", "line_of_credit", "loan"}:
        return (-base_value) + rewards_value
    return base_value + rewards_value


def _record_account_value_history(db: Session, account: Account) -> None:
    db.add(
        AccountValueHistory(
            account_id=account.id,
            user_id=account.user_id,
            value_cents=_compute_account_value_cents(db, account),
        )
    )
    _upsert_daily_net_worth_snapshot(db, account.user_id)


def _compute_user_net_worth_cents(db: Session, user_id: UUID) -> int:
    user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    return int(sum(_net_worth_contribution_cents(db, item) for item in user_accounts))


def _upsert_daily_net_worth_snapshot(db: Session, user_id: UUID) -> None:
    today = datetime.utcnow().date()
    value_cents = _compute_user_net_worth_cents(db, user_id)
    stmt = pg_insert(NetWorthDailySnapshot).values(
        user_id=user_id,
        snapshot_date=today,
        value_cents=value_cents,
        updated_at=datetime.utcnow(),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_net_worth_daily_snapshot_user_day",
        set_={"value_cents": value_cents, "updated_at": datetime.utcnow()},
    )
    db.execute(stmt)


def _account_balance_field(account_type: str) -> str | None:
    if account_type == "crypto_exchange":
        return "usd_balance_cents"
    if account_type in {"cash", "crypto_wallet"}:
        return None
    return "balance_cents"


def _apply_balance_delta(item: AccountSchema, delta_cents: int) -> None:
    field = _account_balance_field(item.type)
    if field is None or not delta_cents:
        return
    current = getattr(item, field) or 0
    setattr(item, field, int(current) + int(delta_cents))


def _first_weekday_of_month(year: int, month: int, weekday: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    current = _first_weekday_of_month(year, month, weekday)
    return current + timedelta(weeks=max(0, nth - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _us_bank_holidays(year: int) -> set[date]:
    return {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday_of_month(year, 1, 0, 3),  # MLK Day
        _nth_weekday_of_month(year, 2, 0, 3),  # Washington's Birthday
        _last_weekday_of_month(year, 5, 0),  # Memorial Day
        _observed_fixed_holiday(year, 6, 19),  # Juneteenth
        _observed_fixed_holiday(year, 7, 4),  # Independence Day
        _nth_weekday_of_month(year, 9, 0, 1),  # Labor Day
        _nth_weekday_of_month(year, 10, 0, 2),  # Columbus Day
        _observed_fixed_holiday(year, 11, 11),  # Veterans Day
        _nth_weekday_of_month(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed_holiday(year, 12, 25),  # Christmas
    }


def _is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in _us_bank_holidays(day.year)


def _next_business_day_noon(reference: datetime) -> datetime:
    current_day = reference.date() + timedelta(days=1)
    while not _is_business_day(current_day):
        current_day += timedelta(days=1)
    return datetime.combine(current_day, time(hour=12, minute=0))


def _is_liability_account_type(account_type: str) -> bool:
    return account_type in LIABILITY_ACCOUNT_TYPES


def _incoming_transfer_delta(account_type: str, amount_cents: int) -> int:
    return -amount_cents if _is_liability_account_type(account_type) else amount_cents


def _outgoing_transfer_delta(account_type: str, amount_cents: int) -> int:
    return amount_cents if _is_liability_account_type(account_type) else -amount_cents


def _apply_transfer_delta_db(account: Account, delta_cents: int) -> bool:
    field = _account_balance_field(account.type)
    if field is None or not delta_cents:
        return False
    current = int(getattr(account, field) or 0)
    setattr(account, field, current + int(delta_cents))
    return True


def _build_transfer_schema(
    transfer: AccountTransfer,
    source_account_name: str,
    destination_account_name: str,
) -> AccountTransferSchema:
    kind = (
        transfer.transfer_kind
        if transfer.transfer_kind in TRANSFER_KINDS
        else "standard"
    )
    return AccountTransferSchema(
        id=transfer.id,
        source_account_id=transfer.source_account_id,
        source_account_name=source_account_name,
        destination_account_id=transfer.destination_account_id,
        destination_account_name=destination_account_name,
        amount_cents=int(transfer.amount_cents or 0),
        transfer_kind=kind,  # type: ignore[arg-type]
        queued_at=transfer.queued_at,
        effective_at=transfer.effective_at,
    )


def _build_queued_payment_schema(
    transfer: AccountTransfer,
    source_account_name: str,
) -> QueuedCreditCardPaymentSchema:
    return QueuedCreditCardPaymentSchema(
        id=transfer.id,
        source_account_id=transfer.source_account_id,
        source_account_name=source_account_name,
        current_balance_cents=int(transfer.current_balance_cents or 0),
        pending_balance_cents=int(transfer.pending_balance_cents or 0),
        payment_cents=int(transfer.amount_cents or 0),
        queued_at=transfer.queued_at,
        effective_at=transfer.effective_at,
    )


def _validate_credit_card_queue_payload(
    db: Session,
    current_user_id: UUID,
    credit_card: Account,
    payload: QueueCreditCardPaymentCreateSchema,
    *,
    allow_zero_payment: bool = False,
) -> tuple[Account, int, int, int]:
    funding_account = (
        db.query(Account)
        .filter(
            Account.id == payload.source_account_id,
            Account.user_id == current_user_id,
        )
        .first()
    )
    if funding_account is None:
        raise HTTPException(status_code=404, detail="Funding account not found")
    if funding_account.id == credit_card.id:
        raise HTTPException(
            status_code=400,
            detail="Funding account must be different from the credit card",
        )
    if bool(funding_account.closed):
        raise HTTPException(
            status_code=400, detail="Cannot use a closed account as the funding source"
        )
    if funding_account.type in {
        "credit_card",
        "line_of_credit",
        "loan",
        "cash",
        "crypto_wallet",
    }:
        raise HTTPException(
            status_code=400,
            detail="Funding account must be a non-liability account with a direct balance",
        )

    current_balance_cents = max(0, int(payload.current_balance_cents or 0))
    pending_balance_cents = max(0, int(payload.pending_balance_cents or 0))
    payment_cents = (
        max(0, int(payload.payment_cents or 0))
        if payload.payment_cents is not None
        else current_balance_cents
    )
    if payment_cents < 0:
        raise HTTPException(status_code=400, detail="payment_cents cannot be negative")
    if payment_cents == 0 and not allow_zero_payment:
        raise HTTPException(
            status_code=400, detail="payment_cents must be greater than 0"
        )
    if payment_cents > current_balance_cents + pending_balance_cents:
        raise HTTPException(
            status_code=400,
            detail="payment_cents cannot exceed current balance plus pending balance",
        )
    return (
        funding_account,
        current_balance_cents,
        pending_balance_cents,
        payment_cents,
    )


def _validate_transfer_accounts(
    db: Session,
    current_user_id: UUID,
    source_account_id: UUID,
    destination_account_id: UUID,
    *,
    require_credit_card_destination: bool = False,
) -> tuple[Account, Account]:
    if source_account_id == destination_account_id:
        raise HTTPException(
            status_code=400, detail="Source and destination accounts must differ"
        )

    accounts = (
        db.query(Account)
        .filter(
            Account.user_id == current_user_id,
            Account.id.in_([source_account_id, destination_account_id]),
        )
        .all()
    )
    accounts_by_id = {account.id: account for account in accounts}
    source_account = accounts_by_id.get(source_account_id)
    destination_account = accounts_by_id.get(destination_account_id)
    if source_account is None or destination_account is None:
        raise HTTPException(status_code=404, detail="Transfer account not found")
    if bool(source_account.closed) or bool(destination_account.closed):
        raise HTTPException(
            status_code=400, detail="Cannot transfer with closed account"
        )
    if _account_balance_field(source_account.type) is None:
        raise HTTPException(
            status_code=400,
            detail="Source account must support direct balance transfers",
        )
    if _account_balance_field(destination_account.type) is None:
        raise HTTPException(
            status_code=400,
            detail="Destination account must support direct balance transfers",
        )
    if require_credit_card_destination and destination_account.type != "credit_card":
        raise HTTPException(
            status_code=400,
            detail="Credit card payment transfers must target a credit card account",
        )
    return source_account, destination_account


def _is_robinhood_account(account: Account) -> bool:
    return (account.organization or "").strip().lower() == "robinhood"


def _get_robinhood_crypto_exchange_account(
    db: Session, user_id: UUID
) -> Account | None:
    matches = (
        db.query(Account)
        .filter(
            Account.user_id == user_id,
            Account.type == "crypto_exchange",
            Account.organization.isnot(None),
        )
        .all()
    )
    robinhood_matches = [
        account for account in matches if _is_robinhood_account(account)
    ]
    if len(robinhood_matches) > 1:
        raise HTTPException(
            status_code=400,
            detail="Multiple Robinhood crypto exchange accounts found",
        )
    return robinhood_matches[0] if robinhood_matches else None


def _settle_due_account_transfers(db: Session, user_id: UUID) -> bool:
    due_transfers = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == user_id,
            AccountTransfer.applied_at.is_(None),
            AccountTransfer.effective_at <= datetime.utcnow(),
        )
        .order_by(AccountTransfer.queued_at.asc())
        .all()
    )
    if not due_transfers:
        return False

    account_ids = {transfer.source_account_id for transfer in due_transfers} | {
        transfer.destination_account_id for transfer in due_transfers
    }
    accounts_by_id = {
        account.id: account
        for account in db.query(Account)
        .filter(Account.user_id == user_id, Account.id.in_(account_ids))
        .all()
    }
    now = datetime.utcnow()
    changed = False
    for transfer in due_transfers:
        source_account = accounts_by_id.get(transfer.source_account_id)
        destination_account = accounts_by_id.get(transfer.destination_account_id)
        amount = int(transfer.amount_cents or 0)
        if source_account is None or destination_account is None or amount <= 0:
            transfer.applied_at = now
            changed = True
            continue
        source_applied = _apply_transfer_delta_db(
            source_account,
            _outgoing_transfer_delta(source_account.type, amount),
        )
        destination_applied = _apply_transfer_delta_db(
            destination_account,
            _incoming_transfer_delta(destination_account.type, amount),
        )
        if not source_applied or not destination_applied:
            transfer.applied_at = now
            changed = True
            continue
        destination_account.last_update = now
        source_account.last_update = now
        transfer.applied_at = now
        _record_account_value_history(db, source_account)
        _record_account_value_history(db, destination_account)
        changed = True
    return changed


def _apply_active_account_transfers(
    db: Session,
    user_id: UUID,
    accounts: list[AccountSchema],
    as_of_date: date | None = None,
) -> list[AccountSchema]:
    transfers = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == user_id,
            AccountTransfer.applied_at.is_(None),
        )
        .order_by(AccountTransfer.queued_at.asc())
        .all()
    )
    if as_of_date is not None:
        transfers = [
            transfer
            for transfer in transfers
            if transfer.queued_at.date() <= as_of_date
        ]
    if not transfers:
        return accounts

    accounts_by_id = {item.id: item for item in accounts}
    referenced_ids = {transfer.source_account_id for transfer in transfers} | {
        transfer.destination_account_id for transfer in transfers
    }
    names_by_id = {item.id: item.name for item in accounts if item.id in referenced_ids}
    if len(names_by_id) < len(referenced_ids):
        for account_id, name in (
            db.query(Account.id, Account.name)
            .filter(Account.user_id == user_id, Account.id.in_(referenced_ids))
            .all()
        ):
            names_by_id[account_id] = name

    for transfer in transfers:
        amount = int(transfer.amount_cents or 0)
        if amount <= 0:
            continue
        source_account = accounts_by_id.get(transfer.source_account_id)
        if source_account is not None:
            _apply_balance_delta(
                source_account,
                _outgoing_transfer_delta(source_account.type, amount),
            )
        destination_account = accounts_by_id.get(transfer.destination_account_id)
        if destination_account is not None:
            _apply_balance_delta(
                destination_account,
                _incoming_transfer_delta(destination_account.type, amount),
            )
            if transfer.transfer_kind == "credit_card_payment":
                destination_account.queued_credit_card_payment = (
                    _build_queued_payment_schema(
                        transfer,
                        names_by_id.get(transfer.source_account_id, "Funding account"),
                    )
                )
    return accounts


def _build_net_worth_points_from_events(
    db: Session, user_id: UUID
) -> list[NetWorthHistoryPointSchema]:
    rows = (
        db.query(AccountValueHistory)
        .filter(AccountValueHistory.user_id == user_id)
        .order_by(AccountValueHistory.recorded_at.asc())
        .all()
    )
    if not rows:
        return []

    account_meta_by_id = {
        account.id: (account.type, int(account.rewards_balance_cents or 0))
        for account in db.query(Account.id, Account.type, Account.rewards_balance_cents)
        .filter(Account.user_id == user_id)
        .all()
    }
    running_total = 0
    last_by_account: dict[UUID, int] = {}
    by_day: dict[date, int] = {}
    for row in rows:
        account_type, rewards_balance_cents = account_meta_by_id.get(
            row.account_id, ("", 0)
        )
        sign = _net_worth_sign_for_account_type(account_type)
        previous = last_by_account.get(row.account_id, 0)
        current = int(row.value_cents or 0)
        reward_delta = 0
        if previous == 0 and row.account_id not in last_by_account:
            reward_delta = max(0, int(rewards_balance_cents or 0))
        running_total += (current - previous) * sign + reward_delta
        last_by_account[row.account_id] = current
        by_day[row.recorded_at.date()] = running_total
    return [
        NetWorthHistoryPointSchema(snapshot_date=day, value_cents=value)
        for day, value in sorted(by_day.items(), key=lambda item: item[0])
    ]


def _forecast_net_worth_points(
    db: Session, user_id: UUID, through_date: date
) -> list[NetWorthForecastPointSchema]:
    today = date.today()
    current = _compute_user_net_worth_cents(db, user_id)
    if through_date <= today:
        return [NetWorthForecastPointSchema(snapshot_date=today, value_cents=current)]

    contract_simulation = run_contract_simulation(
        db, user_id, through_date, apply=False
    )
    expense_simulation = run_expense_simulation(db, user_id, through_date, apply=False)
    contracts = {
        contract.id: contract
        for contract in db.query(Contract).filter(Contract.user_id == user_id).all()
    }
    user = db.get(User, user_id)
    accounts = {
        account.id: (account.type, int(account.rewards_balance_cents or 0))
        for account in db.query(Account.id, Account.type, Account.rewards_balance_cents)
        .filter(Account.user_id == user_id)
        .all()
    }

    def resolve_linked_account_id(contract: Contract) -> UUID | None:
        if contract.linked_account_id is not None:
            return contract.linked_account_id
        if user is None:
            return None
        if contract.linked_wallet == "paypal":
            return user.paypal_account_id
        if contract.linked_wallet == "google_pay":
            return user.google_pay_account_id
        return None

    deltas_by_day: dict[date, int] = {}
    for posting in contract_simulation.postings:
        if posting.status == "skipped":
            continue
        if posting.effective_date <= today:
            continue
        contract = contracts.get(posting.contract_id)
        if contract is None:
            continue
        if contract.type == "transfer":
            amount = int(contract.amount_cents or 0)
            source_type = (
                accounts.get(contract.source_account_id)
                if contract.source_account_id is not None
                else None
            )
            linked_type = (
                accounts.get(resolve_linked_account_id(contract))
                if resolve_linked_account_id(contract) is not None
                else None
            )
            source_sign = (
                _net_worth_sign_for_account_type(source_type[0]) if source_type else 1
            )
            linked_sign = (
                _net_worth_sign_for_account_type(linked_type[0]) if linked_type else 1
            )
            net_delta = (-amount * source_sign) + (amount * linked_sign)
        else:
            linked_type = (
                accounts.get(resolve_linked_account_id(contract))
                if resolve_linked_account_id(contract) is not None
                else None
            )
            linked_sign = (
                _net_worth_sign_for_account_type(linked_type[0]) if linked_type else 1
            )
            net_delta = int(posting.delta_cents) * linked_sign
        deltas_by_day[posting.effective_date] = (
            deltas_by_day.get(posting.effective_date, 0) + net_delta
        )
    for expense_posting in expense_simulation.postings:
        if expense_posting.status == "skipped":
            continue
        if expense_posting.effective_date <= today:
            continue
        account_type = accounts.get(expense_posting.account_id)
        account_sign = (
            _net_worth_sign_for_account_type(account_type[0]) if account_type else 1
        )
        net_delta = int(expense_posting.delta_cents) * account_sign
        deltas_by_day[expense_posting.effective_date] = (
            deltas_by_day.get(expense_posting.effective_date, 0) + net_delta
        )

    points = [NetWorthForecastPointSchema(snapshot_date=today, value_cents=current)]
    running = current
    for snapshot_day in sorted(deltas_by_day):
        running += int(deltas_by_day[snapshot_day])
        points.append(
            NetWorthForecastPointSchema(
                snapshot_date=snapshot_day,
                value_cents=running,
            )
        )
    if points[-1].snapshot_date < through_date:
        points.append(
            NetWorthForecastPointSchema(
                snapshot_date=through_date,
                value_cents=running,
            )
        )
    return points


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
        closed=bool(account.closed),
        max_credit_cents=account.max_credit_cents,
        rewards_balance_cents=account.rewards_balance_cents,
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
    as_of_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountSchema]:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    accounts = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .order_by(Account.rank.desc(), Account.created_at.desc())
        .all()
    )
    serialized = [_serialize_account(db, account) for account in accounts]
    if as_of_date is not None:
        contract_simulation = run_contract_simulation(
            db, current_user.id, as_of_date, apply=False
        )
        expense_simulation = run_expense_simulation(
            db, current_user.id, as_of_date, apply=False
        )
        for item in serialized:
            delta = contract_simulation.account_deltas.get(
                item.id, 0
            ) + expense_simulation.account_deltas.get(item.id, 0)
            if not delta:
                continue
            _apply_balance_delta(item, int(delta))
    return _apply_active_account_transfers(db, current_user.id, serialized, as_of_date)


@router.get("/accounts/{account_id}", response_model=AccountSchema)
def get_account(
    account_id: UUID,
    as_of_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    serialized = _serialize_account(db, account)
    if as_of_date is not None:
        contract_simulation = run_contract_simulation(
            db, current_user.id, as_of_date, apply=False
        )
        expense_simulation = run_expense_simulation(
            db, current_user.id, as_of_date, apply=False
        )
        delta = contract_simulation.account_deltas.get(
            serialized.id, 0
        ) + expense_simulation.account_deltas.get(serialized.id, 0)
        if delta:
            _apply_balance_delta(serialized, int(delta))
    return _apply_active_account_transfers(
        db, current_user.id, [serialized], as_of_date
    )[0]


@router.get(
    "/accounts/net-worth/history", response_model=list[NetWorthHistoryPointSchema]
)
def get_net_worth_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NetWorthHistoryPointSchema]:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    rows = (
        db.query(NetWorthDailySnapshot)
        .filter(NetWorthDailySnapshot.user_id == current_user.id)
        .order_by(NetWorthDailySnapshot.snapshot_date.asc())
        .all()
    )
    if rows:
        return [
            NetWorthHistoryPointSchema(
                value_cents=int(row.value_cents or 0),
                snapshot_date=row.snapshot_date,
            )
            for row in rows
        ]
    return _build_net_worth_points_from_events(db, current_user.id)


@router.get(
    "/accounts/net-worth/forecast", response_model=list[NetWorthForecastPointSchema]
)
def get_net_worth_forecast(
    through_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NetWorthForecastPointSchema]:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    return _forecast_net_worth_points(db, current_user.id, through_date)


@router.get(
    "/accounts/{account_id}/history", response_model=list[AccountValueHistorySchema]
)
def get_account_history(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountValueHistorySchema]:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
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
        closed=bool(payload.closed),
        max_credit_cents=payload.max_credit_cents,
        rewards_balance_cents=payload.rewards_balance_cents,
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
        closed=data.get("closed", account.closed),
        max_credit_cents=data.get("max_credit_cents", account.max_credit_cents),
        rewards_balance_cents=data.get(
            "rewards_balance_cents", account.rewards_balance_cents
        ),
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
        "closed",
        "max_credit_cents",
        "rewards_balance_cents",
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
    _settle_due_account_transfers(db, current_user.id)
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
    if account.type == "credit_card":
        has_active_queue = (
            db.query(AccountTransfer)
            .filter(
                AccountTransfer.user_id == current_user.id,
                AccountTransfer.destination_account_id == account.id,
                AccountTransfer.transfer_kind == "credit_card_payment",
                AccountTransfer.applied_at.is_(None),
            )
            .first()
            is not None
        )
        if has_active_queue and "balance_cents" in data:
            raise HTTPException(
                status_code=409,
                detail="Credit card already has a queued payment awaiting settlement",
            )

    if "balance_cents" in data and account.type != "cash":
        account.balance_cents = data["balance_cents"]
    if "usd_balance_cents" in data:
        account.usd_balance_cents = data["usd_balance_cents"]
    if "rewards_balance_cents" in data:
        account.rewards_balance_cents = max(0, int(data["rewards_balance_cents"] or 0))
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
    return _apply_active_account_transfers(
        db, current_user.id, [_serialize_account(db, account)]
    )[0]


@router.post(
    "/accounts/{account_id}/import-robinhood-statement",
    response_model=AccountSchema,
)
async def import_robinhood_statement(
    account_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    _settle_due_account_transfers(db, current_user.id)
    account = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.type != "stocks_account" or not _is_robinhood_account(account):
        raise HTTPException(
            status_code=400,
            detail="Robinhood statement import is only supported for Robinhood stocks accounts",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Statement file is empty")

    try:
        statement = parse_robinhood_statement(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stock_positions = [
        PositionStockSchema(
            ticker=holding.ticker,
            quantity=holding.quantity,
            last_price_cents=holding.price_cents,
        )
        for holding in statement.stock_holdings
    ]
    _replace_nested_positions(
        db,
        current_user.id,
        account.id,
        stock_positions,
        None,
        None,
    )
    _propagate_stock_prices_for_user(db, current_user.id, stock_positions)
    now = datetime.utcnow()
    if statement.stock_cash_cents is not None:
        account.balance_cents = statement.stock_cash_cents
    account.last_update = now
    _record_account_value_history(db, account)

    if statement.has_crypto_section:
        crypto_account = _get_robinhood_crypto_exchange_account(db, current_user.id)
        if crypto_account is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Robinhood PDF included cryptocurrencies, but no Robinhood "
                    "crypto exchange account was found for this user"
                ),
            )
        crypto_positions = [
            PositionCryptoSchema(
                ticker=holding.ticker,
                quantity=holding.quantity,
                exchange_rate_cents=holding.price_cents,
            )
            for holding in statement.crypto_holdings
        ]
        _replace_nested_positions(
            db,
            current_user.id,
            crypto_account.id,
            None,
            crypto_positions,
            None,
        )
        _propagate_crypto_rates_for_user(db, current_user.id, crypto_positions)
        crypto_account.usd_balance_cents = 0
        crypto_account.last_update = now
        _record_account_value_history(db, crypto_account)

    db.commit()
    db.refresh(account)
    return _apply_active_account_transfers(
        db, current_user.id, [_serialize_account(db, account)]
    )[0]


@router.post(
    "/accounts/{account_id}/queue-credit-card-payment",
    response_model=AccountSchema,
)
def queue_credit_card_payment(
    account_id: UUID,
    payload: QueueCreditCardPaymentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    _settle_due_account_transfers(db, current_user.id)
    credit_card = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if credit_card is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if credit_card.type != "credit_card":
        raise HTTPException(
            status_code=400,
            detail="Queued payments are only supported for credit cards",
        )
    if bool(credit_card.closed):
        raise HTTPException(
            status_code=400, detail="Cannot queue payment for closed account"
        )
    active_existing = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == current_user.id,
            AccountTransfer.destination_account_id == credit_card.id,
            AccountTransfer.transfer_kind == "credit_card_payment",
            AccountTransfer.applied_at.is_(None),
        )
        .first()
    )
    if active_existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Credit card already has a queued payment awaiting settlement",
        )

    (
        funding_account,
        current_balance_cents,
        pending_balance_cents,
        payment_cents,
    ) = _validate_credit_card_queue_payload(
        db,
        current_user.id,
        credit_card,
        payload,
        allow_zero_payment=True,
    )

    credit_card.balance_cents = current_balance_cents + pending_balance_cents
    if payload.rewards_balance_cents is not None:
        credit_card.rewards_balance_cents = max(0, int(payload.rewards_balance_cents))
    credit_card.last_update = datetime.utcnow()
    if payment_cents == 0:
        _record_account_value_history(db, credit_card)
        db.commit()
        db.refresh(credit_card)
        return _apply_active_account_transfers(
            db, current_user.id, [_serialize_account(db, credit_card)]
        )[0]
    queued_at = datetime.utcnow()
    effective_at = _next_business_day_noon(queued_at)
    db.add(
        AccountTransfer(
            user_id=current_user.id,
            source_account_id=funding_account.id,
            destination_account_id=credit_card.id,
            amount_cents=payment_cents,
            current_balance_cents=current_balance_cents,
            pending_balance_cents=pending_balance_cents,
            transfer_kind="credit_card_payment",
            queued_at=queued_at,
            effective_at=effective_at,
        )
    )
    _record_account_value_history(db, credit_card)
    db.commit()
    db.refresh(credit_card)
    return _apply_active_account_transfers(
        db, current_user.id, [_serialize_account(db, credit_card)]
    )[0]


@router.put(
    "/accounts/{account_id}/queue-credit-card-payment",
    response_model=AccountSchema,
)
def update_queued_credit_card_payment(
    account_id: UUID,
    payload: QueueCreditCardPaymentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountSchema:
    _settle_due_account_transfers(db, current_user.id)
    credit_card = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if credit_card is None:
        raise HTTPException(status_code=404, detail="Account not found")
    if credit_card.type != "credit_card":
        raise HTTPException(
            status_code=400,
            detail="Queued payments are only supported for credit cards",
        )
    active_existing = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == current_user.id,
            AccountTransfer.destination_account_id == credit_card.id,
            AccountTransfer.transfer_kind == "credit_card_payment",
            AccountTransfer.applied_at.is_(None),
        )
        .first()
    )
    if active_existing is None:
        raise HTTPException(
            status_code=404,
            detail="No active queued payment found for this credit card",
        )

    (
        funding_account,
        current_balance_cents,
        pending_balance_cents,
        payment_cents,
    ) = _validate_credit_card_queue_payload(
        db,
        current_user.id,
        credit_card,
        payload,
        allow_zero_payment=True,
    )

    now = datetime.utcnow()
    credit_card.balance_cents = current_balance_cents + pending_balance_cents
    if payload.rewards_balance_cents is not None:
        credit_card.rewards_balance_cents = max(0, int(payload.rewards_balance_cents))
    credit_card.last_update = now
    if payment_cents == 0:
        db.delete(active_existing)
        _record_account_value_history(db, credit_card)
        db.commit()
        db.refresh(credit_card)
        return _apply_active_account_transfers(
            db, current_user.id, [_serialize_account(db, credit_card)]
        )[0]
    active_existing.source_account_id = funding_account.id
    active_existing.amount_cents = payment_cents
    active_existing.current_balance_cents = current_balance_cents
    active_existing.pending_balance_cents = pending_balance_cents
    active_existing.queued_at = now
    active_existing.effective_at = _next_business_day_noon(now)
    _record_account_value_history(db, credit_card)
    db.commit()
    db.refresh(credit_card)
    return _apply_active_account_transfers(
        db, current_user.id, [_serialize_account(db, credit_card)]
    )[0]


@router.get("/transfers", response_model=list[AccountTransferSchema])
def list_account_transfers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AccountTransferSchema]:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    transfers = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.user_id == current_user.id,
            AccountTransfer.applied_at.is_(None),
        )
        .order_by(AccountTransfer.effective_at.asc(), AccountTransfer.queued_at.asc())
        .all()
    )
    if not transfers:
        return []
    account_ids = {transfer.source_account_id for transfer in transfers} | {
        transfer.destination_account_id for transfer in transfers
    }
    names_by_id = {
        account.id: account.name
        for account in db.query(Account)
        .filter(Account.user_id == current_user.id, Account.id.in_(account_ids))
        .all()
    }
    return [
        _build_transfer_schema(
            transfer,
            names_by_id.get(transfer.source_account_id, "Unknown account"),
            names_by_id.get(transfer.destination_account_id, "Unknown account"),
        )
        for transfer in transfers
    ]


@router.post("/transfers", response_model=AccountTransferSchema)
def create_account_transfer(
    payload: AccountTransferCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountTransferSchema:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    if int(payload.amount_cents or 0) <= 0:
        raise HTTPException(
            status_code=400, detail="amount_cents must be greater than 0"
        )
    source_account, destination_account = _validate_transfer_accounts(
        db,
        current_user.id,
        payload.source_account_id,
        payload.destination_account_id,
    )
    queued_at = datetime.utcnow()
    transfer = AccountTransfer(
        user_id=current_user.id,
        source_account_id=source_account.id,
        destination_account_id=destination_account.id,
        amount_cents=int(payload.amount_cents),
        transfer_kind="standard",
        queued_at=queued_at,
        effective_at=payload.effective_at or _next_business_day_noon(queued_at),
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return _build_transfer_schema(
        transfer, source_account.name, destination_account.name
    )


@router.put("/transfers/{transfer_id}", response_model=AccountTransferSchema)
def update_account_transfer(
    transfer_id: UUID,
    payload: AccountTransferUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccountTransferSchema:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    transfer = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.id == transfer_id,
            AccountTransfer.user_id == current_user.id,
            AccountTransfer.applied_at.is_(None),
        )
        .first()
    )
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    next_source_id = payload.source_account_id or transfer.source_account_id
    next_destination_id = transfer.destination_account_id
    if (
        transfer.transfer_kind == "standard"
        and payload.destination_account_id is not None
    ):
        next_destination_id = payload.destination_account_id
    amount_cents = int(
        payload.amount_cents
        if payload.amount_cents is not None
        else transfer.amount_cents
    )
    if amount_cents <= 0:
        raise HTTPException(
            status_code=400, detail="amount_cents must be greater than 0"
        )
    source_account, destination_account = _validate_transfer_accounts(
        db,
        current_user.id,
        next_source_id,
        next_destination_id,
        require_credit_card_destination=transfer.transfer_kind == "credit_card_payment",
    )
    transfer.source_account_id = source_account.id
    transfer.destination_account_id = destination_account.id
    transfer.amount_cents = amount_cents
    if payload.effective_at is not None:
        transfer.effective_at = payload.effective_at
    db.commit()
    db.refresh(transfer)
    return _build_transfer_schema(
        transfer, source_account.name, destination_account.name
    )


@router.delete("/transfers/{transfer_id}", status_code=204)
def delete_account_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if _settle_due_account_transfers(db, current_user.id):
        db.commit()
    transfer = (
        db.query(AccountTransfer)
        .filter(
            AccountTransfer.id == transfer_id,
            AccountTransfer.user_id == current_user.id,
            AccountTransfer.applied_at.is_(None),
        )
        .first()
    )
    if transfer is None:
        raise HTTPException(status_code=404, detail="Transfer not found")
    db.delete(transfer)
    db.commit()


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
