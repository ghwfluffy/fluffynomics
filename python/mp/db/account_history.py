from datetime import date, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCryptoPosition,
    AccountStockPosition,
    AccountValueHistory,
    NetWorthDailySnapshot,
    Stock,
)


def compute_account_value_cents(db: Session, account: Account) -> int:
    if account.type == "cash":
        denoms = (
            db.query(AccountCashDenomination).filter_by(account_id=account.id).all()
        )
        return int(sum(item.denomination_cents * item.quantity for item in denoms))
    if account.type in {"crypto_wallet", "crypto_exchange"}:
        crypto_positions = (
            db.query(AccountCryptoPosition).filter_by(account_id=account.id).all()
        )
        total = int(
            sum(
                int(round(float(item.quantity) * int(item.exchange_rate_cents or 0)))
                for item in crypto_positions
            )
        )
        if account.type == "crypto_exchange":
            total += int(account.usd_balance_cents or 0)
        return total
    if account.type == "stocks_account":
        stock_positions = (
            db.query(AccountStockPosition).filter_by(account_id=account.id).all()
        )
        stock_ids = [item.stock_id for item in stock_positions]
        prices_by_id = {
            item.id: int(item.last_price_cents or 0)
            for item in db.query(Stock).filter(Stock.id.in_(stock_ids)).all()
        }
        total = int(
            sum(
                int(round(float(item.quantity) * prices_by_id.get(item.stock_id, 0)))
                for item in stock_positions
            )
        )
        return total + int(account.balance_cents or 0)
    return int(account.balance_cents or 0)


def _account_rewards_cents(account: Account) -> int:
    return max(0, int(account.rewards_balance_cents or 0))


def _net_worth_sign_for_account_type(account_type: str) -> int:
    if account_type in {"credit_card", "line_of_credit", "loan"}:
        return -1
    return 1


def compute_user_net_worth_cents(db: Session, user_id: UUID) -> int:
    user_accounts = db.query(Account).filter(Account.user_id == user_id).all()
    return int(
        sum(
            (
                compute_account_value_cents(db, account)
                * _net_worth_sign_for_account_type(account.type)
            )
            + _account_rewards_cents(account)
            for account in user_accounts
        )
    )


def upsert_daily_net_worth_snapshot(
    db: Session,
    user_id: UUID,
    *,
    snapshot_date: date | None = None,
    updated_at: datetime | None = None,
) -> None:
    target_day = snapshot_date or datetime.utcnow().date()
    current_time = updated_at or datetime.utcnow()
    value_cents = compute_user_net_worth_cents(db, user_id)
    stmt = pg_insert(NetWorthDailySnapshot).values(
        user_id=user_id,
        snapshot_date=target_day,
        value_cents=value_cents,
        updated_at=current_time,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_net_worth_daily_snapshot_user_day",
        set_={"value_cents": value_cents, "updated_at": current_time},
    )
    db.execute(stmt)


def record_account_value_history(
    db: Session,
    account: Account,
    *,
    recorded_at: datetime | None = None,
) -> None:
    history = AccountValueHistory(
        account_id=account.id,
        user_id=account.user_id,
        value_cents=compute_account_value_cents(db, account),
    )
    if recorded_at is not None:
        history.recorded_at = recorded_at
    db.add(history)
    upsert_daily_net_worth_snapshot(
        db,
        account.user_id,
        snapshot_date=(recorded_at.date() if recorded_at is not None else None),
        updated_at=recorded_at,
    )
