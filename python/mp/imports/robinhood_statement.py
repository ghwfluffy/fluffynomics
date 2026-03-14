from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import re

import pdfplumber

LEGACY_SECURITY_LINE_RE = re.compile(
    r"^(?P<ticker>[A-Z][A-Z0-9.\-]+)\s+\S+\s+"
    r"(?P<qty>\d[\d,]*(?:\.\d+)?)\s+\$(?P<price>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$(?P<market>\d[\d,]*(?:\.\d+)?)\b"
)
DASHBOARD_POSITION_LINE_RE = re.compile(
    r"^(?P<name>.+?)\s*(?P<ticker>[A-Z][A-Z0-9.\-]+)\s+"
    r"(?P<qty>\d[\d,]*(?:\.\d+)?)\s+\$(?P<price>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$(?P<average>\d[\d,]*(?:\.\d+)?)\s+\$(?P<return>\d[\d,]*(?:\.\d+)?)\s+"
    r"\$(?P<equity>\d[\d,]*(?:\.\d+)?)(?:\s+\$(?P<trailing>\d[\d,]*(?:\.\d+)?))?$"
)
BROKERAGE_CASH_RE = re.compile(
    r"Brokerage Cash Balance\s+\$(?P<cash>\d[\d,]*(?:\.\d+)?)"
)
INDIVIDUAL_CASH_RE = re.compile(
    r"Individual cash\s+\d[\d,]*(?:\.\d+)?%\s+\$(?P<cash>\d[\d,]*(?:\.\d+)?)"
)


@dataclass(frozen=True)
class RobinhoodHolding:
    ticker: str
    quantity: Decimal
    market_value_cents: int
    price_cents: int


@dataclass(frozen=True)
class RobinhoodStatementData:
    stock_holdings: list[RobinhoodHolding]
    crypto_holdings: list[RobinhoodHolding]
    stock_cash_cents: int | None
    has_crypto_section: bool


def _parse_decimal(raw: str, field: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Robinhood {field}: {raw}") from exc


def _parse_money_to_cents(raw: str, field: str) -> int:
    value = _parse_decimal(raw, field)
    cents = (value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _append_holding(
    aggregates: dict[str, dict[str, Decimal | int]],
    *,
    ticker: str,
    quantity: Decimal,
    market_value_cents: int,
) -> None:
    aggregate = aggregates.setdefault(
        ticker,
        {"quantity": Decimal("0"), "market_value_cents": 0},
    )
    aggregate["quantity"] = Decimal(aggregate["quantity"]) + quantity
    aggregate["market_value_cents"] = (
        int(aggregate["market_value_cents"]) + market_value_cents
    )


def _finalize_holdings(
    aggregates: dict[str, dict[str, Decimal | int]],
) -> list[RobinhoodHolding]:
    holdings: list[RobinhoodHolding] = []
    for ticker, aggregate in sorted(aggregates.items()):
        quantity = Decimal(aggregate["quantity"])
        market_value_cents = int(aggregate["market_value_cents"])
        if quantity <= 0 or market_value_cents < 0:
            continue
        price_cents = int(
            (Decimal(market_value_cents) / quantity).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        holdings.append(
            RobinhoodHolding(
                ticker=ticker,
                quantity=quantity,
                market_value_cents=market_value_cents,
                price_cents=max(0, price_cents),
            )
        )
    return holdings


def parse_robinhood_statement(raw_pdf: bytes) -> RobinhoodStatementData:
    if not raw_pdf:
        raise ValueError("Robinhood statement file is empty")

    stock_aggregates: dict[str, dict[str, Decimal | int]] = {}
    crypto_aggregates: dict[str, dict[str, Decimal | int]] = {}
    stock_cash_cents: int | None = None
    has_crypto_section = False
    dashboard_section: str | None = None

    with pdfplumber.open(BytesIO(raw_pdf)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text:
                continue

            if stock_cash_cents is None:
                for pattern in (BROKERAGE_CASH_RE, INDIVIDUAL_CASH_RE):
                    match = pattern.search(text)
                    if match is not None:
                        stock_cash_cents = _parse_money_to_cents(
                            match.group("cash"), "cash balance"
                        )
                        break

            if "Cryptocurrencies" in text:
                has_crypto_section = True

            current_section = dashboard_section
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                if line == "Stocks":
                    current_section = "stocks"
                    continue
                if line == "Cryptocurrencies":
                    current_section = "crypto"
                    has_crypto_section = True
                    continue
                if line in {
                    "Options",
                    "Margin investing",
                    "Enable Margin Investing",
                    "Dividend reinvestment",
                    "High-Yield Cash program",
                    "Executed Trades Pending Settlement",
                    "Account Activity",
                    "Stock Lending - Loaned Securities",
                }:
                    current_section = None
                    continue
                if line.startswith("Name") and "Symbol" in line:
                    continue

                dashboard_match = DASHBOARD_POSITION_LINE_RE.match(line)
                if dashboard_match is not None and current_section in {
                    "stocks",
                    "crypto",
                }:
                    quantity = _parse_decimal(dashboard_match.group("qty"), "quantity")
                    market_value_cents = _parse_money_to_cents(
                        dashboard_match.group("equity"), "equity"
                    )
                    target = (
                        stock_aggregates
                        if current_section == "stocks"
                        else crypto_aggregates
                    )
                    _append_holding(
                        target,
                        ticker=dashboard_match.group("ticker").strip().upper(),
                        quantity=quantity,
                        market_value_cents=market_value_cents,
                    )
                    continue

                if current_section is None and (
                    "Portfolio Summary" not in text
                    or (
                        "Securities Held in Account" not in text
                        and "Loaned Securities" not in text
                    )
                ):
                    continue

                legacy_match = LEGACY_SECURITY_LINE_RE.match(line)
                if legacy_match is None:
                    continue
                _append_holding(
                    stock_aggregates,
                    ticker=legacy_match.group("ticker").strip().upper(),
                    quantity=_parse_decimal(legacy_match.group("qty"), "quantity"),
                    market_value_cents=_parse_money_to_cents(
                        legacy_match.group("market"), "market value"
                    ),
                )
            dashboard_section = current_section

    stock_holdings = _finalize_holdings(stock_aggregates)
    crypto_holdings = _finalize_holdings(crypto_aggregates)

    if not stock_holdings and not crypto_holdings:
        raise ValueError(
            "Could not find Robinhood holdings in that PDF. Upload a Robinhood account PDF with positions."
        )

    return RobinhoodStatementData(
        stock_holdings=stock_holdings,
        crypto_holdings=crypto_holdings,
        stock_cash_cents=stock_cash_cents,
        has_crypto_section=has_crypto_section,
    )
