from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import re

import pdfplumber

LAST4_RE = re.compile(r"\.\.\.(?P<last4>\d{4})")
AMOUNT_RE = re.compile(r"\$(?P<amount>\d[\d,]*\.\d{2})")


@dataclass(frozen=True)
class WellsFargoAccountBalance:
    name: str
    last4: str
    balance_cents: int
    balance_kind: str


def _parse_money_to_cents(raw: str, field: str) -> int:
    try:
        value = Decimal(raw.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid Wells Fargo {field}: {raw}") from exc
    cents = (value * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def _is_upperish(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    uppercase = sum(1 for char in letters if char.isupper())
    return uppercase / len(letters) >= 0.7


def _clean_name(text: str) -> str:
    return " ".join(part for part in text.replace("…", " ").split() if part).strip()


def _is_name_fragment(text: str) -> bool:
    cleaned = _clean_name(text)
    if not cleaned or "..." in cleaned or "$" in cleaned:
        return False
    if cleaned in {
        "Cash Accounts",
        "Credit",
        "Security Tools",
        "Planning & Tools",
        "Customize",
        "Account Summary",
    }:
        return False
    if cleaned.startswith("https://") or cleaned.startswith("3/"):
        return False
    return _is_upperish(cleaned)


def parse_wells_fargo_statement(raw_pdf: bytes) -> list[WellsFargoAccountBalance]:
    if not raw_pdf:
        raise ValueError("Wells Fargo statement file is empty")

    with pdfplumber.open(BytesIO(raw_pdf)) as pdf:
        lines = [
            raw_line.strip()
            for page in pdf.pages
            for raw_line in (page.extract_text() or "").splitlines()
            if raw_line.strip()
        ]
    normalized_text = " ".join(lines)
    if "Account Summary - Wells Fargo" not in normalized_text:
        raise ValueError("Could not find a Wells Fargo account summary in that PDF")

    results: dict[str, WellsFargoAccountBalance] = {}
    for index, line in enumerate(lines):
        last4_match = LAST4_RE.search(line)
        if last4_match is None:
            continue
        last4 = last4_match.group("last4")

        label = None
        for probe in [line, *lines[max(0, index - 3) : index]]:
            if "Available balance" in probe:
                label = "available"
                break
            if "Outstanding balance" in probe:
                label = "outstanding"
                break
        if label is None:
            continue

        amount_line_index = None
        amount_match = None
        for back_index in range(index - 1, max(-1, index - 8), -1):
            candidate = lines[back_index]
            match = AMOUNT_RE.search(candidate)
            if match is None:
                continue
            amount_line_index = back_index
            amount_match = match
            break
        if amount_line_index is None or amount_match is None:
            continue

        name_parts: list[str] = []
        amount_line = lines[amount_line_index]
        amount_prefix = _clean_name(amount_line.split("$", 1)[0])
        if amount_prefix and _is_name_fragment(amount_prefix):
            name_parts.append(amount_prefix)

        for back_index in range(
            amount_line_index - 1, max(-1, amount_line_index - 3), -1
        ):
            candidate = _clean_name(lines[back_index])
            if not _is_name_fragment(candidate):
                if name_parts:
                    break
                continue
            name_parts.insert(0, candidate)

        for extra_line in lines[amount_line_index + 1 : index]:
            piece = extra_line
            if "Available balance" in piece:
                piece = piece.split("Available balance", 1)[0]
            if "Outstanding balance" in piece:
                piece = piece.split("Outstanding balance", 1)[0]
            piece = _clean_name(piece)
            if not _is_name_fragment(piece):
                continue
            if piece not in name_parts:
                name_parts.append(piece)

        name = " ".join(part for part in name_parts if part).strip()
        if not name:
            continue
        results[last4] = WellsFargoAccountBalance(
            name=name,
            last4=last4,
            balance_cents=_parse_money_to_cents(
                amount_match.group("amount"), "balance"
            ),
            balance_kind=label,
        )

    if not results:
        raise ValueError(
            "Could not find account numbers and balances in that Wells Fargo PDF."
        )

    return list(results.values())
