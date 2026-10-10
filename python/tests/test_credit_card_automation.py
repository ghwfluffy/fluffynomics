from __future__ import annotations

import os
import unittest
from datetime import date
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi import HTTPException  # noqa: E402
from mp.accounts.credit_cards import card_states, process_card_day, project_card_day  # noqa: E402
from mp.api.accounts import _validate_card_automation  # noqa: E402
from mp.api.data_portability import _upgrade_payload_v13_to_v14  # noqa: E402
from mp.schema.account import AccountCreateSchema, AccountSchema  # noqa: E402


def account(account_type: str, balance: int, **settings: object) -> AccountSchema:
    return AccountSchema.model_validate(
        {
            "rank": 0,
            "id": uuid4(),
            "user_id": uuid4(),
            "account_number": "test",
            "name": "Test " + account_type,
            "type": account_type,
            "organization": "Test",
            "balance_cents": balance,
            "created_at": "2026-01-01T00:00:00",
            "credit_card_processed_through": "2026-01-01",
            **settings,
        }
    )


class CreditCardAutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = account("checking", 100000)
        self.card = account(
            "credit_card",
            10000,
            minimum_payment_cents=3000,
            default_payment_account_id=self.source.id,
            payment_day=25,
            billing_day=5,
            apr_bps=2400,
        )
        self.accounts = [self.source, self.card]

    def test_minimum_payment_debits_source_and_preserves_net_worth(self) -> None:
        events = project_card_day(self.accounts, date(2026, 1, 25))
        self.assertEqual(self.card.balance_cents, 7000)
        self.assertEqual(self.source.balance_cents, 97000)
        self.assertEqual(self.card.last_payment_date, date(2026, 1, 25))
        self.assertEqual(events[0].net_worth_delta_cents, 0)

    def test_payment_is_capped_and_paid_off_cards_stop(self) -> None:
        self.card.balance_cents = 1700
        events = project_card_day(self.accounts, date(2026, 1, 25))
        self.assertEqual(events[0].amount_cents, 1700)
        self.assertEqual(self.card.balance_cents, 0)
        self.assertEqual(project_card_day(self.accounts, date(2026, 2, 25)), [])

    def test_a_payment_after_prior_due_date_covers_this_cycle(self) -> None:
        self.card.last_payment_date = date(2026, 1, 20)
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 25)), [])
        self.assertEqual(self.source.balance_cents, 100000)

    def test_prior_due_date_payment_does_not_skip_next_month(self) -> None:
        self.card.last_payment_date = date(2025, 12, 25)
        self.assertEqual(len(project_card_day(self.accounts, date(2026, 1, 25))), 1)
        self.assertEqual(len(project_card_day(self.accounts, date(2026, 2, 25))), 1)

    def test_billing_interest_compounds_and_rounds_to_cents(self) -> None:
        project_card_day(self.accounts, date(2026, 1, 5))
        self.assertEqual(self.card.balance_cents, 10200)
        events = project_card_day(self.accounts, date(2026, 2, 5))
        self.assertEqual(self.card.balance_cents, 10404)
        self.assertEqual(events[0].net_worth_delta_cents, -204)

    def test_interest_before_payment_when_days_match(self) -> None:
        self.card.billing_day = 25
        events = project_card_day(self.accounts, date(2026, 1, 25))
        self.assertEqual([event.kind for event in events], ["interest", "payment"])
        self.assertEqual(self.card.balance_cents, 7200)

    def test_repeated_processing_is_idempotent(self) -> None:
        project_card_day(self.accounts, date(2026, 1, 5))
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 5)), [])
        project_card_day(self.accounts, date(2026, 1, 25))
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 25)), [])
        self.assertEqual(self.source.balance_cents, 97000)

    def test_month_end_and_leap_day_clamping(self) -> None:
        self.card.payment_day = 31
        self.assertEqual(len(project_card_day(self.accounts, date(2026, 2, 28))), 1)
        self.assertEqual(len(project_card_day(self.accounts, date(2026, 3, 31))), 1)
        self.card.credit_card_processed_through = date(2028, 2, 1)
        self.card.last_payment_date = None
        self.assertEqual(len(project_card_day(self.accounts, date(2028, 2, 29))), 1)

    def test_closed_missing_and_invalid_funding_accounts_skip_payment(self) -> None:
        self.source.closed = True
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 25)), [])
        self.card.credit_card_processed_through = date(2026, 1, 1)
        self.source.closed = False
        self.card.default_payment_account_id = uuid4()
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 25)), [])
        self.card.credit_card_processed_through = date(2026, 1, 1)
        self.card.default_payment_account_id = self.source.id
        self.source.type = "credit_card"
        self.assertEqual(project_card_day(self.accounts, date(2026, 1, 25)), [])

    def test_pending_manual_card_payment_suppresses_automatic_payment(self) -> None:
        states = card_states(self.accounts)
        self.assertEqual(
            process_card_day(states, date(2026, 1, 25), {self.card.id}), []
        )
        self.assertEqual(states[self.source.id].balance, 100000)

    def test_zero_credit_balance_and_closed_cards_do_not_accrue_interest(self) -> None:
        for balance, closed in [(0, False), (-100, False), (10000, True)]:
            self.card.balance_cents = balance
            self.card.closed = closed
            self.card.credit_card_processed_through = date(2026, 1, 1)
            self.assertEqual(project_card_day(self.accounts, date(2026, 1, 5)), [])

    def test_projection_does_not_mutate_original_accounts(self) -> None:
        projected = [item.model_copy(deep=True) for item in self.accounts]
        project_card_day(projected, date(2026, 1, 25))
        self.assertEqual(self.card.balance_cents, 10000)
        self.assertEqual(self.source.balance_cents, 100000)

    def test_old_exports_upgrade_with_automation_disabled(self) -> None:
        upgraded = _upgrade_payload_v13_to_v14(
            {"schema_version": 13, "accounts": [{"id": "old"}]}
        )
        self.assertEqual(upgraded["schema_version"], 14)
        self.assertIsNone(upgraded["accounts"][0]["minimum_payment_cents"])
        self.assertIsNone(upgraded["accounts"][0]["default_payment_account_id"])

    def test_positive_minimum_requires_day_and_source(self) -> None:
        from unittest.mock import MagicMock

        payload = AccountCreateSchema(
            account_number="test",
            name="test",
            organization="test",
            type="credit_card",
            minimum_payment_cents=100,
        )
        with self.assertRaises(HTTPException):
            _validate_card_automation(MagicMock(), uuid4(), payload)

    def test_foreign_funding_account_is_rejected(self) -> None:
        from unittest.mock import MagicMock

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        payload = AccountCreateSchema(
            account_number="test",
            name="test",
            organization="test",
            type="credit_card",
            minimum_payment_cents=100,
            payment_day=25,
            default_payment_account_id=uuid4(),
        )
        with self.assertRaises(HTTPException):
            _validate_card_automation(db, uuid4(), payload)


if __name__ == "__main__":
    unittest.main()
