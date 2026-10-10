from __future__ import annotations

import os
import unittest
from datetime import date
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "sqlite://")

from mp.accounts.credit_cards import project_card_day  # noqa: E402
from mp.accounts.projection_payments import apply_projected_surplus_payments  # noqa: E402
from mp.api.accounts import _serialized_user_net_worth_cents  # noqa: E402
from mp.schema.account import AccountSchema  # noqa: E402

DAY = date(2026, 10, 11)


def account(kind: str, cents: int, **kwargs: object) -> AccountSchema:
    return AccountSchema.model_validate(
        {
            "id": uuid4(),
            "user_id": uuid4(),
            "rank": 0,
            "account_number": "test",
            "name": kind,
            "type": kind,
            "organization": "test",
            "balance_cents": cents,
            "created_at": "2026-10-10T00:00:00",
            **kwargs,
        }
    )


class ProjectionSurplusPaymentTests(unittest.TestCase):
    def test_strict_threshold_and_full_batch(self) -> None:
        checking = account("checking", 1000000)
        debt = account("credit_card", 2000000, apr_bps=2900)
        apply_projected_surplus_payments([checking, debt], DAY)
        self.assertEqual(debt.balance_cents, 2000000)
        checking.balance_cents = 1000001
        before = _serialized_user_net_worth_cents([checking, debt])
        apply_projected_surplus_payments([checking, debt], DAY)
        self.assertEqual(checking.balance_cents, 500001)
        self.assertEqual(debt.balance_cents, 1500000)
        self.assertEqual(_serialized_user_net_worth_cents([checking, debt]), before)

    def test_highest_apr_and_payoff_cap_then_next_debt(self) -> None:
        checking = account("checking", 1400000)
        lower = account("loan", 700000, apr_bps=1200)
        higher = account("line_of_credit", 200000, apr_bps=2400)
        apply_projected_surplus_payments([lower, checking, higher], DAY)
        self.assertEqual(higher.balance_cents, 0)
        self.assertEqual(lower.balance_cents, 200000)
        self.assertEqual(checking.balance_cents, 700000)
        self.assertEqual(higher.last_payment_date, DAY)

    def test_repeated_batches_stop_at_threshold(self) -> None:
        checking = account("checking", 2500000)
        debt = account("credit_card", 10000000)
        apply_projected_surplus_payments([checking, debt], DAY)
        self.assertEqual(checking.balance_cents, 1000000)
        self.assertEqual(debt.balance_cents, 8500000)
        apply_projected_surplus_payments([checking, debt], DAY)
        self.assertEqual(debt.balance_cents, 8500000)
        checking.balance_cents = int(checking.balance_cents or 0) + 1
        apply_projected_surplus_payments([checking, debt], DAY)
        self.assertEqual(checking.balance_cents, 500001)

    def test_no_eligible_debt_keeps_surplus_cash(self) -> None:
        checking = account("checking", 2000000)
        paid = account("loan", 0)
        credit = account("credit_card", -10000)
        closed = account("loan", 1000000, apr_bps=9999, closed=True)
        asset = account("savings", -100000)
        apply_projected_surplus_payments([checking, paid, credit, closed, asset], DAY)
        self.assertEqual(checking.balance_cents, 2000000)
        self.assertEqual(closed.balance_cents, 1000000)

    def test_multiple_checking_accounts_and_ineligible_funding(self) -> None:
        a = account("checking", 1100000)
        b = account("checking", 1200000)
        savings = account("savings", 9000000)
        closed = account("checking", 9000000, closed=True)
        debt = account("loan", 700000)
        apply_projected_surplus_payments([a, b, savings, closed, debt], DAY)
        self.assertEqual(debt.balance_cents, 0)
        self.assertEqual(int(a.balance_cents or 0) + int(b.balance_cents or 0), 1600000)
        self.assertEqual(savings.balance_cents, 9000000)
        self.assertEqual(closed.balance_cents, 9000000)

    def test_equal_and_missing_apr_have_stable_priority(self) -> None:
        checking = account("checking", 1100000)
        first = account("loan", 500000, id=UUID(int=1), apr_bps=None)
        second = account("credit_card", 500000, id=UUID(int=2), apr_bps=0)
        apply_projected_surplus_payments([second, checking, first], DAY)
        self.assertEqual(first.balance_cents, 0)
        self.assertEqual(second.balance_cents, 500000)

    def test_extra_card_payment_covers_upcoming_monthly_payment(self) -> None:
        checking = account("checking", 1100000)
        card = account(
            "credit_card",
            700000,
            apr_bps=2400,
            payment_day=15,
            minimum_payment_cents=30000,
            default_payment_account_id=checking.id,
            last_payment_date=date(2026, 9, 15),
        )
        apply_projected_surplus_payments([checking, card], DAY)
        self.assertEqual(card.balance_cents, 200000)
        self.assertEqual(project_card_day([checking, card], date(2026, 10, 15)), [])
        self.assertEqual(checking.balance_cents, 600000)


if __name__ == "__main__":
    unittest.main()
