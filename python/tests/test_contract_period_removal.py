from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from typing import cast

from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "sqlite://")

from mp.api.contracts import _validate_recurring_period  # noqa: E402
from mp.api.data_portability import _upgrade_payload_v12_to_v13  # noqa: E402
from mp.contracts.engine import _parse_period  # noqa: E402
from mp.schema.contract import (  # noqa: E402
    Contract,
    ContractCreateSchema,
    ContractSchema,
    ContractUpdateSchema,
)


class ContractPeriodRemovalTests(unittest.TestCase):
    def test_contract_schemas_do_not_expose_payment_day(self) -> None:
        for schema in (ContractCreateSchema, ContractUpdateSchema, ContractSchema):
            self.assertNotIn("payment_day", schema.model_fields)

    def test_contract_writes_require_structured_periods(self) -> None:
        _validate_recurring_period('{"kind":"monthly_day","day":18}')

        for invalid in (None, "", "monthly", "not-json"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(HTTPException):
                    _validate_recurring_period(invalid)

    def test_scheduler_has_no_payment_day_fallback(self) -> None:
        period = _parse_period(
            cast(
                Contract,
                SimpleNamespace(payment_period='{"kind":"monthly_day","day":18}'),
            )
        )
        self.assertIsNotNone(period)
        self.assertEqual(period.day if period is not None else None, 18)
        self.assertIsNone(
            _parse_period(cast(Contract, SimpleNamespace(payment_period=None)))
        )

    def test_v12_export_upgrade_moves_timing_into_payment_period(self) -> None:
        structured = '{"kind":"weekly_weekday","weekday":4}'
        upgraded = _upgrade_payload_v12_to_v13(
            {
                "schema_version": 12,
                "contracts": [
                    {
                        "id": "missing-period",
                        "payment_period": None,
                        "payment_day": 18,
                    },
                    {
                        "id": "structured",
                        "payment_period": structured,
                        "payment_day": 7,
                    },
                    {
                        "id": "legacy-keyword",
                        "payment_period": "monthly",
                        "payment_day": 22,
                    },
                    {
                        "id": "unrecoverable",
                        "payment_period": None,
                        "payment_day": None,
                    },
                    {
                        "id": "invalid",
                        "payment_period": "not-json",
                        "payment_day": 12,
                    },
                ],
            }
        )

        self.assertEqual(upgraded["schema_version"], 13)
        contracts = {item["id"]: item for item in upgraded["contracts"]}
        self.assertEqual(
            json.loads(contracts["missing-period"]["payment_period"]),
            {"kind": "monthly_day", "day": 18},
        )
        self.assertEqual(contracts["structured"]["payment_period"], structured)
        self.assertEqual(
            json.loads(contracts["legacy-keyword"]["payment_period"]),
            {"kind": "monthly_day", "day": 1},
        )
        self.assertIsNone(contracts["unrecoverable"]["payment_period"])
        self.assertIsNone(contracts["invalid"]["payment_period"])
        self.assertTrue(
            all("payment_day" not in item for item in upgraded["contracts"])
        )


if __name__ == "__main__":
    unittest.main()
