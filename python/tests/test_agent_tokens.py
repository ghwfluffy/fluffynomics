from __future__ import annotations

import os
import unittest
from dataclasses import dataclass
from typing import Any, cast

from mp.api.agent_tokens import (
    encode_agent_token,
    required_agent_scope,
    user_from_agent_token,
)


@dataclass
class FakeUser:
    identity_provider: str
    external_subject: str


class FakeQuery:
    def __init__(self, users: list[FakeUser]) -> None:
        self.users = users
        self.filters: dict[str, str] = {}

    def filter_by(self, **kwargs: str) -> FakeQuery:
        self.filters = kwargs
        return self

    def first(self) -> FakeUser | None:
        for user in self.users:
            if user.identity_provider == self.filters.get(
                "identity_provider"
            ) and user.external_subject == self.filters.get("external_subject"):
                return user
        return None


class FakeDb:
    def __init__(self, users: list[FakeUser]) -> None:
        self.users = users

    def query(self, _model: Any) -> FakeQuery:
        return FakeQuery(self.users)


class FakeRequest:
    def __init__(self, path: str, method: str) -> None:
        self.url = type("Url", (), {"path": path})()
        self.method = method


class AgentTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_secret = os.environ.get("AGENT_INTEGRATION_TOKEN_SECRET")
        self._original_auth = os.environ.get("AUTH_BASE_URL")
        os.environ["AGENT_INTEGRATION_TOKEN_SECRET"] = "test-agent-secret"
        os.environ["AUTH_BASE_URL"] = "http://auth.example.test/auth"

    def tearDown(self) -> None:
        if self._original_secret is None:
            os.environ.pop("AGENT_INTEGRATION_TOKEN_SECRET", None)
        else:
            os.environ["AGENT_INTEGRATION_TOKEN_SECRET"] = self._original_secret
        if self._original_auth is None:
            os.environ.pop("AUTH_BASE_URL", None)
        else:
            os.environ["AUTH_BASE_URL"] = self._original_auth

    def test_required_scope_resolves_budget_routes(self) -> None:
        cases = [
            ("GET", "/api/accounts", "budget.list_accounts"),
            (
                "GET",
                "/api/accounts/net-worth/history",
                "budget.get_net_worth_history",
            ),
            (
                "GET",
                "/api/accounts/net-worth/forecast",
                "budget.get_net_worth_forecast",
            ),
            ("GET", "/api/accounts/account-1", "budget.get_account"),
            ("PUT", "/api/accounts/account-1/value", "budget.update_account_value"),
            ("GET", "/api/transfers", "budget.list_transfers"),
            ("GET", "/api/contracts", "budget.list_contracts"),
            ("GET", "/api/expenses", "budget.list_expenses"),
            ("GET", "/api/investments", "budget.list_investments"),
            ("GET", "/api/logs", "budget.list_audit_logs"),
        ]
        for method, path, expected_scope in cases:
            self.assertEqual(
                required_agent_scope(cast(Any, FakeRequest(path, method))),
                expected_scope,
            )

    def test_agent_token_maps_to_oauth_user(self) -> None:
        user = FakeUser(
            identity_provider="http://auth.example.test/auth",
            external_subject="central-user-1",
        )
        token = encode_agent_token(
            secret="test-agent-secret",
            subject="central-user-1",
            scope="budget.list_accounts",
        )

        resolved = user_from_agent_token(
            cast(Any, FakeRequest("/api/accounts", "GET")),
            cast(Any, FakeDb([user])),
            token,
        )

        self.assertIs(resolved, user)

    def test_agent_token_rejects_wrong_scope_user_and_app(self) -> None:
        user = FakeUser(
            identity_provider="http://auth.example.test/auth",
            external_subject="central-user-1",
        )
        db = FakeDb([user])
        request = FakeRequest("/api/accounts", "GET")

        wrong_scope = encode_agent_token(
            secret="test-agent-secret",
            subject="central-user-1",
            scope="budget.list_expenses",
        )
        wrong_user = encode_agent_token(
            secret="test-agent-secret",
            subject="other-user",
            scope="budget.list_accounts",
        )
        wrong_app = encode_agent_token(
            secret="test-agent-secret",
            subject="central-user-1",
            scope="budget.list_accounts",
            audience="goals",
        )

        self.assertIsNone(
            user_from_agent_token(cast(Any, request), cast(Any, db), wrong_scope)
        )
        self.assertIsNone(
            user_from_agent_token(cast(Any, request), cast(Any, db), wrong_user)
        )
        self.assertIsNone(
            user_from_agent_token(cast(Any, request), cast(Any, db), wrong_app)
        )


if __name__ == "__main__":
    unittest.main()
