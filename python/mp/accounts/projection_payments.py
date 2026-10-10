"""Read-only forecast assumption for paying debt from surplus checking cash."""

from datetime import date

from mp.schema.account import AccountSchema

CHECKING_THRESHOLD_CENTS = 1000000
PAYMENT_BATCH_CENTS = 500000
DEBT_TYPES = {"credit_card", "line_of_credit", "loan"}


def apply_projected_surplus_payments(accounts: list[AccountSchema], day: date) -> None:
    """Apply repeated $5k batches while checking exceeds $10k, highest APR first.

    Liability balances store positive amounts owed, despite their negative
    net-worth contribution. Only simulated account schemas are accepted here.
    """
    debts = sorted(
        (
            account
            for account in accounts
            if account.type in DEBT_TYPES
            and not account.closed
            and int(account.balance_cents or 0) > 0
        ),
        key=lambda account: (-max(0, int(account.apr_bps or 0)), str(account.id)),
    )
    checking_accounts = sorted(
        (a for a in accounts if a.type == "checking" and not a.closed),
        key=lambda account: str(account.id),
    )
    for checking in checking_accounts:
        for debt in debts:
            cash = int(checking.balance_cents or 0)
            if cash <= CHECKING_THRESHOLD_CENTS:
                break
            owed = int(debt.balance_cents or 0)
            if owed <= 0:
                continue
            # Collapse consecutive batches for the same debt into one delta.
            # This is equivalent to rechecking the strict threshold after each
            # batch and avoids looping once per $5k for large horizons.
            batches = (
                cash - CHECKING_THRESHOLD_CENTS + PAYMENT_BATCH_CENTS - 1
            ) // PAYMENT_BATCH_CENTS
            payment = min(owed, batches * PAYMENT_BATCH_CENTS)
            checking.balance_cents = cash - payment
            debt.balance_cents = owed - payment
            debt.last_payment_date = day
