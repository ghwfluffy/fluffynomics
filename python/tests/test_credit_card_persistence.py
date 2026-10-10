"""Run against a disposable database via CREDIT_CARD_TEST_DATABASE_URL."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from typing import ClassVar

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text, Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from mp.accounts.credit_cards import apply_credit_card_automation  # noqa: E402
from mp.api.accounts import (  # noqa: E402
    get_credit_card_events,
    get_accounts,
    get_account,
    _settle_due_account_transfers,
    update_account,
)  # noqa: E402
from mp.api.data_portability import _build_export_payload, _replace_user_data  # noqa: E402
from mp.schema.account import (  # noqa: E402
    Account,
    AccountTransfer,
    AccountValueHistory,
    AccountUpdateSchema,
    NetWorthDailySnapshot,
)  # noqa: E402
from mp.schema.audit_log import AuditLogEvent  # noqa: E402
from mp.schema.base import Base  # noqa: E402
from mp.schema.user import User  # noqa: E402

TEST_URL = os.environ.get("CREDIT_CARD_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_URL, "Requires disposable CREDIT_CARD_TEST_DATABASE_URL")
class CreditCardPersistenceTests(unittest.TestCase):
    engine: ClassVar[Engine]

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(TEST_URL)
        Base.metadata.create_all(cls.engine)

    def setUp(self) -> None:
        self.db = Session(self.engine)
        self.user = User(id=uuid4(), username=str(uuid4()), password_hash="test-only")
        self.db.add(self.user)
        self.db.flush()
        self.source = Account(
            id=uuid4(),
            user_id=self.user.id,
            account_number="test",
            name="Funding",
            type="checking",
            organization="test",
            balance_cents=100000,
        )
        self.card = Account(
            id=uuid4(),
            user_id=self.user.id,
            account_number="test",
            name="Card",
            type="credit_card",
            organization="test",
            balance_cents=10000,
            minimum_payment_cents=3000,
            payment_day=date.today().day,
            billing_day=date.today().day,
            apr_bps=2400,
            credit_card_processed_through=date.today() - timedelta(days=1),
        )
        self.db.add_all([self.source, self.card])
        self.db.flush()
        self.card.default_payment_account_id = self.source.id
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_posts_once_with_transfer_audit_history_and_snapshot(self) -> None:
        self.assertTrue(
            apply_credit_card_automation(self.db, self.user.id, date.today())
        )
        self.db.commit()
        self.assertFalse(
            apply_credit_card_automation(self.db, self.user.id, date.today())
        )
        self.db.commit()
        self.db.refresh(self.card)
        self.db.refresh(self.source)
        self.assertEqual(self.card.balance_cents, 7200)
        self.assertEqual(self.source.balance_cents, 97000)
        transfers = self.db.query(AccountTransfer).filter_by(user_id=self.user.id).all()
        self.assertEqual(len(transfers), 1)
        self.assertIsNotNone(transfers[0].applied_at)
        self.assertEqual(
            self.db.query(AuditLogEvent).filter_by(user_id=self.user.id).count(), 2
        )
        self.assertEqual(
            self.db.query(AccountValueHistory).filter_by(user_id=self.user.id).count(),
            3,
        )
        snapshot = (
            self.db.query(NetWorthDailySnapshot).filter_by(user_id=self.user.id).one()
        )
        self.assertEqual(snapshot.value_cents, 89800)
        events = get_credit_card_events(date.today(), date.today(), self.db, self.user)
        self.assertEqual({item.kind for item in events}, {"payment", "interest"})

    def test_export_import_remaps_source_and_history_without_reposting(self) -> None:
        apply_credit_card_automation(self.db, self.user.id, date.today())
        self.db.commit()
        payload = _build_export_payload(self.db, self.user.id)
        original_id = self.card.id
        self.assertEqual(payload["schema_version"], 14)
        _replace_user_data(self.db, self.user.id, payload)
        self.db.commit()
        card = (
            self.db.query(Account)
            .filter_by(user_id=self.user.id, type="credit_card")
            .one()
        )
        source = (
            self.db.query(Account)
            .filter_by(user_id=self.user.id, type="checking")
            .one()
        )
        self.assertNotEqual(card.id, original_id)
        self.assertEqual(card.default_payment_account_id, source.id)
        self.assertEqual(card.minimum_payment_cents, 3000)
        self.assertFalse(
            apply_credit_card_automation(self.db, self.user.id, date.today())
        )
        events = get_credit_card_events(date.today(), date.today(), self.db, self.user)
        self.assertTrue(all(event.account_id == card.id for event in events))
        payment = next(event for event in events if event.kind == "payment")
        self.assertEqual(payment.source_account_id, source.id)

    def test_concurrent_apply_does_not_duplicate(self) -> None:
        user_id = self.user.id

        def apply() -> None:
            with Session(self.engine) as db:
                apply_credit_card_automation(db, user_id, date.today())
                db.commit()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: apply(), range(2)))
        self.assertEqual(
            self.db.query(AccountTransfer).filter_by(user_id=user_id).count(), 1
        )
        self.db.refresh(self.source)
        self.assertEqual(self.source.balance_cents, 97000)

    def test_manual_settlement_records_payment_and_suppresses_autopayment(self) -> None:
        self.card.apr_bps = 0
        self.db.add(
            AccountTransfer(
                user_id=self.user.id,
                source_account_id=self.source.id,
                destination_account_id=self.card.id,
                amount_cents=4000,
                transfer_kind="credit_card_payment",
                instant_deposit=False,
                queued_at=datetime.utcnow() - timedelta(days=1),
                effective_at=datetime.utcnow() - timedelta(seconds=1),
            )
        )
        self.db.commit()
        self.assertTrue(_settle_due_account_transfers(self.db, self.user.id))
        self.db.commit()
        self.db.refresh(self.card)
        self.db.refresh(self.source)
        self.assertEqual(self.card.last_payment_date, date.today())
        self.assertEqual(self.card.balance_cents, 6000)
        self.assertEqual(self.source.balance_cents, 96000)
        self.assertEqual(
            self.db.query(AccountTransfer).filter_by(user_id=self.user.id).count(), 1
        )

    def test_future_account_list_and_single_card_agree(self) -> None:
        through = date.today() + timedelta(days=65)
        items = get_accounts(through, self.db, self.user)
        card = get_account(self.card.id, through, self.db, self.user)
        projected = next(item for item in items if item.id == self.card.id)
        self.assertEqual(card.balance_cents, projected.balance_cents)
        self.db.refresh(self.card)
        self.assertEqual(
            self.card.balance_cents, 7200
        )  # only today's posting was persisted

    def test_setting_changes_do_not_repost_today(self) -> None:
        apply_credit_card_automation(self.db, self.user.id, date.today())
        self.db.commit()
        update_account(
            self.card.id, AccountUpdateSchema(apr_bps=3000), self.db, self.user
        )
        self.assertFalse(
            apply_credit_card_automation(self.db, self.user.id, date.today())
        )
        self.db.refresh(self.card)
        self.assertEqual(self.card.balance_cents, 7200)
        self.assertEqual(
            self.db.query(AccountTransfer).filter_by(user_id=self.user.id).count(), 1
        )

    def test_migration_starts_existing_cards_without_historical_charges(self) -> None:
        # Dedicated test schema: simulate the previous accounts table, then apply SQL.
        with self.engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA card_migration_test"))
            conn.execute(text("SET LOCAL search_path TO card_migration_test"))
            conn.execute(
                text(
                    "CREATE TABLE accounts(id UUID PRIMARY KEY, balance_cents INTEGER)"
                )
            )
            conn.execute(
                text("INSERT INTO accounts VALUES (:id, 10000)"), {"id": uuid4()}
            )
            sql = (
                Path(__file__).parents[1]
                / "mp/db/migrations/0045_credit_card_automation.sql"
            ).read_text()
            conn.execute(text(sql))
            row = conn.execute(
                text(
                    "SELECT balance_cents, minimum_payment_cents, credit_card_processed_through FROM accounts"
                )
            ).one()
            self.assertEqual(row.balance_cents, 10000)
            self.assertIsNone(row.minimum_payment_cents)
            self.assertEqual(
                row.credit_card_processed_through, date.today() - timedelta(days=1)
            )
            conn.execute(text("DROP SCHEMA card_migration_test CASCADE"))


if __name__ == "__main__":
    unittest.main()
