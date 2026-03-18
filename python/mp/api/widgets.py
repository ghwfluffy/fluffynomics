import io
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from mp.api.accounts import (
    _apply_active_account_transfers,
    _apply_projected_account_yield_to_datetime,
    _serialize_account,
    _serialized_user_net_worth_cents,
    _settle_due_account_transfers,
)
from mp.db import get_db
from mp.db.audit_log import format_cents
from mp.models.recurring_period import (
    RecurringPeriod,
    parse_recurring_period,
    previous_occurrence_before,
)
from mp.schema.account import Account
from mp.schema.contract import Contract
from mp.schema.expense import Expense
from mp.schema.user import User

router = APIRouter(prefix="/widgets", tags=["widgets"])

WIDGET_WIDTH = 351
WIDGET_HEIGHT = 485
WIDGET_TEXT_COLOR = (0, 0, 0, 255)
WIDGET_POSITIVE_COLOR = (0, 255, 0, 255)
WIDGET_NEGATIVE_COLOR = (255, 0, 0, 255)
WIDGET_CHANGE_POSITIVE_COLOR = (19, 167, 0, 255)
WIDGET_CHANGE_NEGATIVE_COLOR = (204, 0, 0, 255)
WIDGET_TEXT_SHADOW = (255, 255, 255, 170)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CAT_IMAGE_PATH = _REPO_ROOT / "static" / "cat.png"
_FONT_PATH = _REPO_ROOT / "static" / "DejaVuSans.ttf"


@lru_cache(maxsize=1)
def _load_cat_image() -> Image.Image:
    with Image.open(_CAT_IMAGE_PATH) as image:
        return image.convert("RGBA")


@lru_cache(maxsize=32)
def _load_font(
    size: int, *, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [_FONT_PATH] if bold else [_FONT_PATH]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_width: int,
    start_size: int,
    min_size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(start_size, min_size - 1, -1):
        font = _load_font(size, bold=bold)
        bounds = draw.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] <= max_width:
            return font
    return _load_font(min_size, bold=bold)


def _prorated_cycle_fraction(
    reference_time: datetime, previous: datetime, next_value: datetime
) -> float:
    span_seconds = (next_value - previous).total_seconds()
    if span_seconds <= 0:
        return 0.0
    elapsed_seconds = (reference_time - previous).total_seconds()
    return max(0.0, min(1.0, elapsed_seconds / span_seconds))


def _naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _normalized_period(
    raw: str | None, *, fallback_day: int | None, reference_day: date
) -> tuple[str | None, RecurringPeriod | None]:
    normalized = (raw or "").strip()
    if not normalized:
        if fallback_day is None:
            return None, None
        return "monthly_day", RecurringPeriod(
            kind="monthly_day", day=max(1, min(31, fallback_day))
        )
    lowered = normalized.lower()
    if lowered == "daily":
        return "daily", None
    if lowered == "weekly":
        return "weekly_weekday", RecurringPeriod(
            kind="weekly_weekday", weekday=reference_day.weekday()
        )
    if lowered == "biweekly":
        return "biweekly_weekday", RecurringPeriod(
            kind="biweekly_weekday",
            weekday=reference_day.weekday(),
            start_date=reference_day,
        )
    if lowered == "monthly":
        day = fallback_day or reference_day.day
        return "monthly_day", RecurringPeriod(
            kind="monthly_day", day=max(1, min(31, day))
        )
    if lowered == "yearly":
        day = fallback_day or reference_day.day
        return "yearly_month_day", RecurringPeriod(
            kind="yearly_month_day",
            month=reference_day.month,
            day=max(1, min(31, day)),
        )
    try:
        period = parse_recurring_period(normalized)
    except ValueError:
        return None, None
    return period.kind, period


def _contract_is_active_for_summary(
    contract: Contract, reference_time: datetime
) -> bool:
    expiration = contract.expiration_date
    return expiration is None or expiration >= reference_time.date()


def _expense_is_active_for_summary(expense: Expense) -> bool:
    return bool(expense.enabled)


def _fee_is_active_for_summary(account: Account) -> bool:
    return (
        not bool(account.closed)
        and abs(int(account.fee_amount_cents or 0)) > 0
        and bool((account.fee_period or "").strip())
    )


def _contract_prorated_contribution_cents(
    contract: Contract, reference_time: datetime
) -> float:
    reference_time = _naive_utc(reference_time)
    if not _contract_is_active_for_summary(contract, reference_time):
        return 0.0
    if contract.type == "transfer":
        return 0.0
    kind, period = _normalized_period(
        contract.payment_period,
        fallback_day=contract.payment_day or 1,
        reference_day=reference_time.date(),
    )
    if kind is None:
        return 0.0
    if kind == "daily":
        day_start = datetime.combine(reference_time.date(), time.min)
        next_value = day_start + timedelta(days=1)
        fraction = _prorated_cycle_fraction(reference_time, day_start, next_value)
        signed_amount = (
            abs(int(contract.amount_cents or 0))
            if contract.type == "income"
            else -abs(int(contract.amount_cents or 0))
        )
        return signed_amount * fraction
    assert period is not None
    next_due = period.next_on_or_after(reference_time.date())
    previous_due = previous_occurrence_before(period, next_due)
    if (
        previous_due is not None
        and contract.last_payment_date is not None
        and previous_due < contract.last_payment_date < next_due
    ):
        next_due = period.next_on_or_after(next_due + timedelta(days=1))
        previous_due = contract.last_payment_date
    if contract.expiration_date is not None and contract.expiration_date < next_due:
        return 0.0
    if period.start_date is not None:
        first_due = period.next_on_or_after(period.start_date)
        if reference_time.date() < first_due:
            return 0.0
    if previous_due is None or previous_due >= next_due:
        previous_due = previous_occurrence_before(period, next_due)
    if previous_due is None or previous_due >= next_due:
        return 0.0
    fraction = _prorated_cycle_fraction(
        reference_time,
        datetime.combine(previous_due, time.min),
        datetime.combine(next_due, time.min),
    )
    signed_amount = (
        abs(int(contract.amount_cents or 0))
        if contract.type == "income"
        else -abs(int(contract.amount_cents or 0))
    )
    return signed_amount * fraction


def _expense_prorated_contribution_cents(
    expense: Expense, reference_time: datetime
) -> float:
    reference_time = _naive_utc(reference_time)
    if not _expense_is_active_for_summary(expense) or bool(expense.next_date_is_static):
        return 0.0
    next_due = expense.next_expensed_date
    if next_due is None:
        return 0.0
    previous_due = expense.last_expensed_date
    if previous_due is None or previous_due >= next_due:
        kind, period = _normalized_period(
            expense.general_frequency,
            fallback_day=next_due.day,
            reference_day=next_due,
        )
        if kind is None:
            return 0.0
        if kind == "daily":
            previous_due = next_due - timedelta(days=1)
        else:
            assert period is not None
            previous_due = previous_occurrence_before(period, next_due)
    if previous_due is None or previous_due >= next_due:
        return 0.0
    fraction = _prorated_cycle_fraction(
        reference_time,
        datetime.combine(previous_due, time.min),
        datetime.combine(next_due, time.min),
    )
    return -abs(int(expense.estimated_amount_cents or 0)) * fraction


def _fee_prorated_contribution_cents(
    account: Account, reference_time: datetime
) -> float:
    reference_time = _naive_utc(reference_time)
    fee_amount_cents = abs(int(account.fee_amount_cents or 0))
    if fee_amount_cents <= 0 or not _fee_is_active_for_summary(account):
        return 0.0
    kind, period = _normalized_period(
        account.fee_period,
        fallback_day=reference_time.day,
        reference_day=reference_time.date(),
    )
    if kind is None:
        return 0.0
    if kind == "daily":
        day_start = datetime.combine(reference_time.date(), time.min)
        next_value = day_start + timedelta(days=1)
        fraction = _prorated_cycle_fraction(reference_time, day_start, next_value)
        return -(fee_amount_cents * fraction)
    assert period is not None
    if period.start_date is not None:
        first_due = period.next_on_or_after(period.start_date)
        if reference_time.date() < first_due:
            return 0.0
    next_due = period.next_on_or_after(reference_time.date())
    previous_due = previous_occurrence_before(period, next_due)
    if previous_due is None or previous_due >= next_due:
        return 0.0
    fraction = _prorated_cycle_fraction(
        reference_time,
        datetime.combine(previous_due, time.min),
        datetime.combine(next_due, time.min),
    )
    return -(fee_amount_cents * fraction)


def _load_projected_accounts(db: Session, user_id, reference_time: datetime) -> list:
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)
        .order_by(Account.rank.desc(), Account.created_at.desc())
        .all()
    )
    projected = [_serialize_account(db, account) for account in accounts]
    projected = _apply_active_account_transfers(db, user_id, projected, None)
    _apply_projected_account_yield_to_datetime(projected, _naive_utc(reference_time))
    return projected


def _compute_prorated_net_worth_cents(
    db: Session, user_id, reference_time: datetime
) -> int:
    projected_accounts = _load_projected_accounts(db, user_id, reference_time)
    base_net_worth = _serialized_user_net_worth_cents(projected_accounts)
    contracts = db.query(Contract).filter(Contract.user_id == user_id).all()
    expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
    accounts = db.query(Account).filter(Account.user_id == user_id).all()

    manual_contract_adjustment = sum(
        _contract_prorated_contribution_cents(contract, reference_time)
        for contract in contracts
        if not bool(contract.automatic)
    )
    expense_adjustment = sum(
        _expense_prorated_contribution_cents(expense, reference_time)
        for expense in expenses
    )
    fee_adjustment = sum(
        _fee_prorated_contribution_cents(account, reference_time)
        for account in accounts
    )
    current_net_worth = round(
        base_net_worth
        + manual_contract_adjustment
        + expense_adjustment
        + fee_adjustment
    )
    automatic_contract_adjustment = sum(
        _contract_prorated_contribution_cents(contract, reference_time)
        for contract in contracts
        if bool(contract.automatic)
    )
    return round(current_net_worth + automatic_contract_adjustment)


def _change_color(delta_cents: int) -> tuple[int, int, int, int]:
    if delta_cents > 0:
        return WIDGET_POSITIVE_COLOR
    if delta_cents < 0:
        return WIDGET_NEGATIVE_COLOR
    return WIDGET_TEXT_COLOR


def _change_amount_color(delta_cents: int) -> tuple[int, int, int, int]:
    if delta_cents > 0:
        return WIDGET_CHANGE_POSITIVE_COLOR
    if delta_cents < 0:
        return WIDGET_CHANGE_NEGATIVE_COLOR
    return WIDGET_TEXT_COLOR


def _format_elapsed_label(elapsed_seconds: int) -> str:
    seconds = max(0, int(elapsed_seconds))
    if seconds < 300:
        suffix = "" if seconds == 1 else "s"
        return f"{seconds} Second{suffix}"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    hour_suffix = "" if hours == 1 else "s"
    minute_suffix = "" if minutes == 1 else "s"
    return f"{hours} Hour{hour_suffix}, {minutes} Minute{minute_suffix}"


def _format_change_amount(delta_cents: int) -> str:
    absolute = abs(int(delta_cents or 0)) / 100
    if delta_cents > 0:
        return f"+{absolute:,.2f}"
    if delta_cents < 0:
        return f"-{absolute:,.2f}"
    return f"{absolute:,.2f}"


def _draw_right_aligned_text(
    draw: ImageDraw.ImageDraw,
    right_edge: int,
    top: int,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill,
) -> None:
    text_bounds = draw.textbbox((0, 0), text, font=font)
    text_width = text_bounds[2] - text_bounds[0]
    x = right_edge - text_width
    y = top
    draw.text((x + 2, y + 2), text, font=font, fill=WIDGET_TEXT_SHADOW)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_background(image: Image.Image) -> None:
    width, height = image.size
    base_draw = ImageDraw.Draw(image)
    top_color = (234, 229, 216)
    bottom_color = (214, 223, 232)
    for y in range(height):
        ratio = y / max(1, height - 1)
        row = tuple(
            int(top_color[i] + (bottom_color[i] - top_color[i]) * ratio)
            for i in range(3)
        )
        base_draw.line((0, y, width, y), fill=(*row, 255))

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.ellipse(
        (-70, -30, 190, 180),
        fill=(255, 228, 163, 95),
    )
    overlay_draw.ellipse(
        (155, -40, 380, 165),
        fill=(193, 238, 198, 85),
    )
    overlay_draw.rounded_rectangle(
        (14, 10, 337, 165),
        radius=28,
        fill=(255, 255, 255, 118),
    )
    overlay_draw.pieslice(
        (-40, 360, 160, 560),
        start=230,
        end=360,
        fill=(255, 215, 110, 48),
    )
    overlay_draw.pieslice(
        (240, 310, 410, 520),
        start=180,
        end=320,
        fill=(128, 221, 142, 40),
    )
    image.alpha_composite(overlay)


def _prepare_cat_image() -> Image.Image:
    cat_image = _load_cat_image().copy()
    remapped: list[tuple[int, int, int, int]] = []
    for r, g, b, a in list(cat_image.getdata()):
        if a == 0:
            remapped.append((r, g, b, a))
            continue
        min_channel = min(r, g, b)
        max_channel = max(r, g, b)
        # Knock out the baked-in white background while preserving the cat's
        # cream fur and coin highlights.
        if min_channel >= 246 and max_channel - min_channel <= 10:
            remapped.append((r, g, b, 0))
        elif min_channel >= 236 and max_channel - min_channel <= 12:
            remapped.append((r, g, b, int(a * 0.2)))
        else:
            remapped.append((r, g, b, a))
    cat_image.putdata(remapped)
    alpha_bbox = cat_image.getchannel("A").getbbox()
    if alpha_bbox is not None:
        cat_image = cat_image.crop(alpha_bbox)
    return cat_image


def _render_widget_png(
    *,
    net_worth_cents: int,
    delta_cents: int,
    elapsed_seconds: int,
) -> bytes:
    image = Image.new("RGBA", (WIDGET_WIDTH, WIDGET_HEIGHT), (255, 255, 255, 255))
    _draw_background(image)
    draw = ImageDraw.Draw(image)

    value_text = format_cents(net_worth_cents)
    change_text = _format_change_amount(delta_cents)
    elapsed_text = _format_elapsed_label(elapsed_seconds)

    value_font = _fit_font(
        draw,
        value_text,
        max_width=316,
        start_size=50,
        min_size=42,
        bold=False,
    )
    change_font = _fit_font(
        draw,
        change_text,
        max_width=136,
        start_size=36,
        min_size=28,
        bold=False,
    )
    elapsed_font = _fit_font(
        draw,
        elapsed_text,
        max_width=296,
        start_size=34,
        min_size=26,
        bold=False,
    )

    _draw_right_aligned_text(
        draw,
        333,
        13,
        value_text,
        font=value_font,
        fill=_change_color(delta_cents),
    )
    _draw_right_aligned_text(
        draw,
        333,
        78,
        change_text,
        font=change_font,
        fill=_change_amount_color(delta_cents),
    )
    _draw_right_aligned_text(
        draw,
        333,
        123,
        elapsed_text,
        font=elapsed_font,
        fill=WIDGET_TEXT_COLOR,
    )

    cat_image = _prepare_cat_image()
    cat_image = cat_image.resize((290, 290), Image.Resampling.LANCZOS)
    cat_x = 29
    cat_y = 173
    image.alpha_composite(cat_image, (cat_x, cat_y))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get("/net-worth.png")
def get_net_worth_widget_png(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Response:
    user = db.query(User).filter(User.widget_token == token.strip()).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Widget not found")
    if _settle_due_account_transfers(db, user.id):
        db.commit()

    now = datetime.now(tz=timezone.utc)
    current_net_worth_cents = _compute_prorated_net_worth_cents(db, user.id, now)
    previous_net_worth_cents = user.widget_last_net_worth_cents
    previous_accessed_at = user.widget_last_accessed_at
    delta_cents = (
        current_net_worth_cents - int(previous_net_worth_cents)
        if previous_net_worth_cents is not None
        else 0
    )
    elapsed_seconds = (
        int(max(0.0, (now - previous_accessed_at).total_seconds()))
        if previous_accessed_at is not None
        else 0
    )
    png_data = _render_widget_png(
        net_worth_cents=current_net_worth_cents,
        delta_cents=delta_cents,
        elapsed_seconds=elapsed_seconds,
    )

    user.widget_last_accessed_at = now
    user.widget_last_net_worth_cents = current_net_worth_cents
    db.add(user)
    db.commit()

    return Response(
        content=png_data,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )
