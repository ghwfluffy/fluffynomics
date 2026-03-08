from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from mp.db.core import SessionLocal
from mp.schema.account import (
    Account,
    AccountCashDenomination,
    AccountCryptoPosition,
    AccountStockPosition,
    AccountValueHistory,
    Organization,
    Stock,
)
from mp.schema.contract import Contract
from mp.schema.user import User


def _ensure_account(db: Session, user: User, name: str, payload: dict) -> Account:
    account = db.query(Account).filter_by(user_id=user.id, name=name).first()
    if account is None:
        max_rank = (
            db.query(Account.rank)
            .filter_by(user_id=user.id)
            .order_by(Account.rank.desc())
            .first()
        )
        next_rank = (max_rank[0] if max_rank else 0) + 1
        account = Account(user_id=user.id, name=name, rank=next_rank, **payload)
        db.add(account)
        db.flush()
    elif account.last_update is None and payload.get("last_update") is not None:
        account.last_update = payload["last_update"]
    if account.icon_id is None and account.organization:
        organization = (
            db.query(Organization).filter_by(name=account.organization).first()
        )
        if organization is not None and organization.icon_id is not None:
            account.icon_id = organization.icon_id
    return account


def _ensure_stock(db: Session, user: User, ticker: str, payload: dict) -> Stock:
    stock = (
        db.query(Stock)
        .filter_by(
            user_id=user.id,
            ticker=ticker,
            exchange=payload.get("exchange"),
        )
        .first()
    )
    if stock is None:
        stock = Stock(user_id=user.id, ticker=ticker, **payload)
        db.add(stock)
        db.flush()
    elif payload.get("last_price_cents") is not None:
        stock.last_price_cents = payload["last_price_cents"]
    return stock


def _ensure_contract(db: Session, user: User, name: str, payload: dict) -> Contract:
    contract = db.query(Contract).filter_by(user_id=user.id, name=name).first()
    if contract is None:
        contract = Contract(user_id=user.id, name=name, **payload)
        db.add(contract)
        db.flush()
    return contract


def _account_value_cents(db: Session, account: Account) -> int:
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
        if not stock_positions:
            return int(account.balance_cents or 0)
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


def _ensure_history_seed(db: Session, user: User, account: Account) -> None:
    existing = db.query(AccountValueHistory).filter_by(account_id=account.id).first()
    if existing is not None:
        return
    base_value = _account_value_cents(db, account)
    if base_value <= 0:
        base_value = int(account.balance_cents or account.usd_balance_cents or 10000)
    seed = sum(ord(ch) for ch in account.name) % 17
    points = 8
    for idx in range(points):
        days_ago = (points - idx) * 21
        drift = (idx - (points // 2)) * 900
        jitter = ((seed * (idx + 3)) % 11 - 5) * 275
        value = max(0, base_value + drift + jitter)
        db.add(
            AccountValueHistory(
                account_id=account.id,
                user_id=user.id,
                value_cents=value,
                recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            )
        )


def ensure_example_data_for_user(db: Session, user: User) -> None:
    if not user.example_data:
        return

    now = datetime.now(timezone.utc)
    fresh = now - timedelta(days=2)
    recent = now - timedelta(days=12)
    aging = now - timedelta(days=45)
    stale = now - timedelta(days=120)

    checking = _ensure_account(
        db,
        user,
        "Household Checking",
        {
            "account_number": "100012341234",
            "type": "checking",
            "organization": "Fluffy Federal",
            "balance_cents": 485000,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "110000000",
            "last_update": fresh,
        },
    )
    _ensure_account(
        db,
        user,
        "Emergency Savings",
        {
            "account_number": "200056781234",
            "type": "savings",
            "organization": "Fluffy Federal",
            "balance_cents": 2250000,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "110000000",
            "apy_bps": 430,
            "compound_period": "monthly",
            "last_update": recent,
        },
    )
    cash = _ensure_account(
        db,
        user,
        "Cash Envelope",
        {
            "account_number": "CASH-0001",
            "type": "cash",
            "organization": "On Hand",
            "last_update": aging,
        },
    )
    _ensure_account(
        db,
        user,
        "Travel Checking",
        {
            "account_number": "100012349999",
            "type": "checking",
            "organization": "Fluffy Federal",
            "balance_cents": 136400,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "110000000",
            "last_update": stale,
        },
    )
    _ensure_account(
        db,
        user,
        "Bills Checking",
        {
            "account_number": "100055551234",
            "type": "checking",
            "organization": "Northline Bank",
            "balance_cents": 242900,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "121000358",
            "last_update": fresh,
        },
    )
    _ensure_account(
        db,
        user,
        "Vacation Savings",
        {
            "account_number": "200099991234",
            "type": "savings",
            "organization": "Fluffy Federal",
            "balance_cents": 485000,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "110000000",
            "apy_bps": 390,
            "compound_period": "monthly",
            "last_update": recent,
        },
    )
    _ensure_account(
        db,
        user,
        "Tax Savings",
        {
            "account_number": "200012349876",
            "type": "savings",
            "organization": "Northline Bank",
            "balance_cents": 318700,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "routing_number": "121000358",
            "apy_bps": 410,
            "compound_period": "monthly",
            "last_update": aging,
        },
    )
    _ensure_account(
        db,
        user,
        "Home Safe Cash",
        {
            "account_number": "CASH-0002",
            "type": "cash",
            "organization": "On Hand",
            "last_update": stale,
        },
    )
    _ensure_account(
        db,
        user,
        "Petty Cash Drawer",
        {
            "account_number": "CASH-0003",
            "type": "cash",
            "organization": "On Hand",
            "last_update": fresh,
        },
    )
    _ensure_account(
        db,
        user,
        "Daily Rewards Card",
        {
            "account_number": "4000123412345678",
            "type": "credit_card",
            "organization": "Nimbus Card",
            "balance_cents": 156700,
            "fee_amount_cents": 0,
            "fee_period": "monthly",
            "apr_bps": 2499,
            "billing_day": 5,
            "payment_day": 25,
            "compound_period": "daily",
            "expiration_date": date(2028, 8, 1),
            "cvc": "123",
            "last_update": recent,
        },
    )
    _ensure_account(
        db,
        user,
        "Home Line of Credit",
        {
            "account_number": "310090001234",
            "type": "line_of_credit",
            "organization": "Northline Bank",
            "balance_cents": 940000,
            "fee_amount_cents": 1500,
            "fee_period": "monthly",
            "apr_bps": 899,
            "compound_period": "daily",
            "billing_day": 3,
            "payment_day": 22,
            "last_update": aging,
        },
    )
    _ensure_account(
        db,
        user,
        "Auto Loan",
        {
            "account_number": "LN-778899",
            "type": "loan",
            "organization": "AutoTrust Finance",
            "balance_cents": 1124000,
            "apr_bps": 525,
            "compound_period": "monthly",
            "payment_amount_cents": 41500,
            "payment_day": 14,
            "last_update": stale,
        },
    )
    _ensure_account(
        db,
        user,
        "Work 401k",
        {
            "account_number": "RET-401K-1",
            "type": "retirement",
            "organization": "Peak Retirement",
            "balance_cents": 8450000,
            "retirement_account_type": "401k",
            "last_update": fresh,
        },
    )
    _ensure_account(
        db,
        user,
        "Travel Rewards",
        {
            "account_number": "RW-10001",
            "type": "rewards_card",
            "organization": "SkyMile Club",
            "balance_cents": 42000,
            "expiration_date": date(2027, 12, 1),
            "last_update": recent,
        },
    )
    stocks_account = _ensure_account(
        db,
        user,
        "Brokerage Main",
        {
            "account_number": "BRK-445566",
            "type": "stocks_account",
            "organization": "Fluffy Brokerage",
            "last_update": aging,
        },
    )
    crypto_exchange = _ensure_account(
        db,
        user,
        "Crypto Exchange Wallet",
        {
            "account_number": "CRX-9988",
            "type": "crypto_exchange",
            "organization": "CatCoin Exchange",
            "usd_balance_cents": 210000,
            "last_update": stale,
        },
    )
    crypto_wallet = _ensure_account(
        db,
        user,
        "Hardware Wallet",
        {
            "account_number": "CW-1122",
            "type": "crypto_wallet",
            "organization": "Self Custody",
            "last_update": fresh,
        },
    )

    spy = _ensure_stock(
        db,
        user,
        "SPY",
        {"name": "SPDR S&P 500 ETF", "exchange": "NYSE", "last_price_cents": 59500},
    )
    msft = _ensure_stock(
        db,
        user,
        "MSFT",
        {"name": "Microsoft Corp.", "exchange": "NASDAQ", "last_price_cents": 42000},
    )

    if (
        db.query(AccountStockPosition)
        .filter_by(account_id=stocks_account.id, stock_id=spy.id)
        .first()
        is None
    ):
        db.add(
            AccountStockPosition(
                account_id=stocks_account.id,
                stock_id=spy.id,
                quantity=Decimal("12.50"),
            )
        )
    if (
        db.query(AccountStockPosition)
        .filter_by(account_id=stocks_account.id, stock_id=msft.id)
        .first()
        is None
    ):
        db.add(
            AccountStockPosition(
                account_id=stocks_account.id,
                stock_id=msft.id,
                quantity=Decimal("8.00"),
            )
        )

    for ticker, qty in [("BTC", Decimal("0.245")), ("ETH", Decimal("1.900"))]:
        if (
            db.query(AccountCryptoPosition)
            .filter_by(account_id=crypto_exchange.id, ticker=ticker)
            .first()
            is None
        ):
            db.add(
                AccountCryptoPosition(
                    account_id=crypto_exchange.id,
                    ticker=ticker,
                    quantity=qty,
                    exchange_rate_cents=8600000 if ticker == "BTC" else 350000,
                )
            )
    if (
        db.query(AccountCryptoPosition)
        .filter_by(account_id=crypto_wallet.id, ticker="BTC")
        .first()
        is None
    ):
        db.add(
            AccountCryptoPosition(
                account_id=crypto_wallet.id,
                ticker="BTC",
                quantity=Decimal("0.750"),
                exchange_rate_cents=8600000,
            )
        )

    for denom, qty_int in [(100, 5), (500, 6), (2000, 3), (10000, 2)]:
        if (
            db.query(AccountCashDenomination)
            .filter_by(account_id=cash.id, denomination_cents=denom)
            .first()
            is None
        ):
            db.add(
                AccountCashDenomination(
                    account_id=cash.id, denomination_cents=denom, quantity=qty_int
                )
            )

    db.execute(
        text(
            """
            INSERT INTO pending_payments (account_id, delta, notes)
            SELECT :account_id, :delta, :notes
            WHERE NOT EXISTS (
                SELECT 1 FROM pending_payments
                WHERE account_id = :account_id AND notes = :notes
            )
            """
        ),
        {
            "account_id": checking.id,
            "delta": -8532,
            "notes": "Example: pending grocery transaction",
        },
    )

    seeded_accounts = (
        db.query(Account)
        .filter(Account.user_id == user.id)
        .order_by(Account.created_at.asc())
        .all()
    )
    for seeded in seeded_accounts:
        _ensure_history_seed(db, user, seeded)
    _ensure_contract(
        db,
        user,
        "Example Paycheck",
        {
            "type": "income",
            "automatic": True,
            "amount_cents": 325000,
            "organization": "Employer Payroll",
            "account_number": "PAY-1001",
            "icon_type": "Letters",
            "rank": 3,
            "linked_account_id": checking.id,
            "source_account_id": None,
            "last_payment_date": date.today() - timedelta(days=14),
            "payment_period": '{"kind":"biweekly_weekday","weekday":4,"start_date":"2025-01-03"}',
            "payment_day": 1,
            "notes": "Seeded sample contract",
            "category": "Work",
        },
    )
    _ensure_contract(
        db,
        user,
        "Example Rent",
        {
            "type": "payment",
            "automatic": True,
            "amount_cents": 165000,
            "organization": "Main Street Apartments",
            "icon_type": "Letters",
            "rank": 2,
            "linked_account_id": checking.id,
            "source_account_id": None,
            "last_payment_date": date.today().replace(day=1),
            "payment_period": '{"kind":"monthly_day","day":1}',
            "payment_day": 1,
            "notes": "Seeded housing payment",
            "category": "Living",
            "url": "https://rent.example.com",
            "account_number": "RENT-001",
            "billing_day": 25,
        },
    )
    _ensure_contract(
        db,
        user,
        "Example Transfer to Savings",
        {
            "type": "transfer",
            "automatic": True,
            "amount_cents": 50000,
            "organization": "Internal Transfer",
            "account_number": "XFER-2002",
            "icon_type": "Letters",
            "rank": 1,
            "linked_account_id": checking.id,
            "source_account_id": cash.id,
            "last_payment_date": date.today() - timedelta(days=30),
            "payment_period": '{"kind":"monthly_day","day":1}',
            "payment_day": 1,
            "notes": "Seeded savings transfer",
            "category": "Financial",
        },
    )


def ensure_example_data_for_opted_in_users() -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter_by(example_data=True).all()
        for user in users:
            ensure_example_data_for_user(db, user)
        db.commit()
    finally:
        db.close()
