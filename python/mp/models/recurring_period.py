import calendar
import json
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator

RecurringKind = Literal[
    "monthly_day",
    "monthly_last_day",
    "twice_monthly",
    "every_n_months_day",
    "yearly_month_day",
    "every_n_years_month_day",
    "daily_weekdays",
    "weekly_weekday",
    "biweekly_weekday",
    "every_n_weeks_weekday",
]

WEEKDAY_LABELS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
WEEKDAY_SHORT = ["M", "T", "W", "R", "F", "S", "U"]


class RecurringPeriod(BaseModel):
    kind: RecurringKind
    day: int | None = None
    day_1: int | None = None
    day_2: int | None = None
    month: int | None = None
    interval_months: int | None = None
    interval_years: int | None = None
    interval_weeks: int | None = None
    weekdays: list[int] | None = None
    weekday: int | None = None
    start_date: date | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "RecurringPeriod":
        if self.kind == "monthly_day":
            if self.day is None or not 1 <= self.day <= 31:
                raise ValueError("monthly_day requires day in range 1..31")
        elif self.kind == "monthly_last_day":
            pass
        elif self.kind == "twice_monthly":
            if (
                self.day_1 is None
                or self.day_2 is None
                or not 1 <= self.day_1 <= 31
                or not 1 <= self.day_2 <= 31
                or self.day_1 == self.day_2
            ):
                raise ValueError(
                    "twice_monthly requires distinct day_1/day_2 in range 1..31"
                )
        elif self.kind == "every_n_months_day":
            if self.day is None or not 1 <= self.day <= 31:
                raise ValueError("every_n_months_day requires day in range 1..31")
            if self.interval_months is None or self.interval_months < 1:
                raise ValueError("every_n_months_day requires interval_months >= 1")
            if self.start_date is None:
                raise ValueError("every_n_months_day requires start_date")
        elif self.kind == "yearly_month_day":
            if (
                self.month is None
                or self.day is None
                or not 1 <= self.month <= 12
                or not 1 <= self.day <= 31
            ):
                raise ValueError("yearly_month_day requires month 1..12 and day 1..31")
        elif self.kind == "every_n_years_month_day":
            if (
                self.month is None
                or self.day is None
                or not 1 <= self.month <= 12
                or not 1 <= self.day <= 31
            ):
                raise ValueError(
                    "every_n_years_month_day requires month 1..12 and day 1..31"
                )
            if self.interval_years is None or self.interval_years < 1:
                raise ValueError("every_n_years_month_day requires interval_years >= 1")
            if self.start_date is None:
                raise ValueError("every_n_years_month_day requires start_date")
        elif self.kind == "daily_weekdays":
            if self.weekdays is None or not self.weekdays:
                raise ValueError("daily_weekdays requires at least one weekday")
            if any(day < 0 or day > 6 for day in self.weekdays):
                raise ValueError("daily_weekdays values must be in range 0..6")
        elif self.kind == "weekly_weekday":
            if self.weekday is None or not 0 <= self.weekday <= 6:
                raise ValueError("weekly_weekday requires weekday in range 0..6")
        elif self.kind == "biweekly_weekday":
            if self.weekday is None or not 0 <= self.weekday <= 6:
                raise ValueError("biweekly_weekday requires weekday in range 0..6")
            if self.start_date is None:
                raise ValueError("biweekly_weekday requires start_date")
        elif self.kind == "every_n_weeks_weekday":
            if self.weekday is None or not 0 <= self.weekday <= 6:
                raise ValueError("every_n_weeks_weekday requires weekday in range 0..6")
            if self.interval_weeks is None or self.interval_weeks < 1:
                raise ValueError("every_n_weeks_weekday requires interval_weeks >= 1")
            if self.start_date is None:
                raise ValueError("every_n_weeks_weekday requires start_date")
        return self

    def describe(self) -> str:
        if self.kind == "monthly_day":
            assert self.day is not None
            return f"Monthly on the {ordinal(self.day)}"
        if self.kind == "monthly_last_day":
            return "Monthly on the last day of the month"
        if self.kind == "twice_monthly":
            assert self.day_1 is not None and self.day_2 is not None
            low, high = sorted([self.day_1, self.day_2])
            return f"Twice monthly on the {ordinal(low)} and {ordinal(high)}"
        if self.kind == "every_n_months_day":
            assert self.day is not None and self.interval_months is not None
            return f"Every {self.interval_months} months on the {ordinal(self.day)}"
        if self.kind == "yearly_month_day":
            assert self.month is not None and self.day is not None
            return f"Yearly on {calendar.month_name[self.month]} {ordinal(self.day)}"
        if self.kind == "every_n_years_month_day":
            assert (
                self.month is not None
                and self.day is not None
                and self.interval_years is not None
            )
            return (
                f"Every {self.interval_years} years on "
                f"{calendar.month_name[self.month]} {ordinal(self.day)}"
            )
        if self.kind == "daily_weekdays":
            assert self.weekdays is not None
            symbols = "".join(
                WEEKDAY_SHORT[index] for index in sorted(set(self.weekdays))
            )
            return f"Daily on {symbols}"
        if self.kind == "biweekly_weekday":
            assert self.weekday is not None
            return f"Every 2 weeks on {WEEKDAY_LABELS[self.weekday]}"
        if self.kind == "every_n_weeks_weekday":
            assert self.weekday is not None and self.interval_weeks is not None
            return (
                f"Every {self.interval_weeks} weeks on {WEEKDAY_LABELS[self.weekday]}"
            )
        assert self.weekday is not None
        return f"Weekly on {WEEKDAY_LABELS[self.weekday]}"

    def next_on_or_after(self, candidate: date) -> date:
        if self.kind == "monthly_day":
            assert self.day is not None
            return _next_month_day(candidate, self.day)
        if self.kind == "monthly_last_day":
            return _next_last_day(candidate)
        if self.kind == "twice_monthly":
            assert self.day_1 is not None and self.day_2 is not None
            return _next_twice_monthly(candidate, self.day_1, self.day_2)
        if self.kind == "every_n_months_day":
            assert (
                self.day is not None
                and self.interval_months is not None
                and self.start_date is not None
            )
            return _next_every_n_months_day(
                candidate, self.day, self.interval_months, self.start_date
            )
        if self.kind == "yearly_month_day":
            assert self.month is not None and self.day is not None
            return _next_yearly_month_day(candidate, self.month, self.day)
        if self.kind == "every_n_years_month_day":
            assert (
                self.month is not None
                and self.day is not None
                and self.interval_years is not None
                and self.start_date is not None
            )
            return _next_every_n_years_month_day(
                candidate,
                self.month,
                self.day,
                self.interval_years,
                self.start_date,
            )
        if self.kind == "daily_weekdays":
            assert self.weekdays is not None
            allowed = set(self.weekdays)
            next_day = candidate
            while next_day.weekday() not in allowed:
                next_day += timedelta(days=1)
            return next_day
        if self.kind == "biweekly_weekday":
            assert self.weekday is not None and self.start_date is not None
            return _next_biweekly_weekday(candidate, self.weekday, self.start_date)
        if self.kind == "every_n_weeks_weekday":
            assert (
                self.weekday is not None
                and self.start_date is not None
                and self.interval_weeks is not None
            )
            return _next_every_n_weeks_weekday(
                candidate,
                self.weekday,
                self.start_date,
                self.interval_weeks,
            )
        assert self.weekday is not None
        delta_days = (self.weekday - candidate.weekday()) % 7
        return candidate + timedelta(days=delta_days)

    def delta_from(self, start: date) -> timedelta:
        return self.next_on_or_after(start) - start


def parse_recurring_period(raw: str) -> RecurringPeriod:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Recurring period must be valid JSON") from exc
    try:
        return RecurringPeriod.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Recurring period schema is invalid") from exc


def previous_occurrence_before(
    period: RecurringPeriod, before_value: date
) -> date | None:
    search = before_value - timedelta(days=400)
    current = period.next_on_or_after(search)
    previous: date | None = None
    guard = 0
    while current < before_value and guard < 2000:
        previous = current
        current = period.next_on_or_after(current + timedelta(days=1))
        guard += 1
    return previous


def first_due_after_last_occurrence(
    period: RecurringPeriod,
    *,
    search_start: date,
    last_occurrence: date | None = None,
) -> date:
    next_due = period.next_on_or_after(search_start)
    if last_occurrence is None:
        return next_due
    previous_due = previous_occurrence_before(period, next_due)
    if previous_due is not None and previous_due < last_occurrence < next_due:
        return period.next_on_or_after(next_due + timedelta(days=1))
    return next_due


def ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _month_last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _next_month_day(candidate: date, day: int) -> date:
    month_day = min(day, _month_last_day(candidate.year, candidate.month))
    this_month = candidate.replace(day=month_day)
    if this_month >= candidate:
        return this_month
    year = candidate.year + (1 if candidate.month == 12 else 0)
    month = 1 if candidate.month == 12 else candidate.month + 1
    return date(year, month, min(day, _month_last_day(year, month)))


def _next_last_day(candidate: date) -> date:
    day = _month_last_day(candidate.year, candidate.month)
    this_month = candidate.replace(day=day)
    if this_month >= candidate:
        return this_month
    year = candidate.year + (1 if candidate.month == 12 else 0)
    month = 1 if candidate.month == 12 else candidate.month + 1
    return date(year, month, _month_last_day(year, month))


def _next_twice_monthly(candidate: date, day_1: int, day_2: int) -> date:
    options = sorted([day_1, day_2])
    for option in options:
        day = min(option, _month_last_day(candidate.year, candidate.month))
        possible = candidate.replace(day=day)
        if possible >= candidate:
            return possible
    year = candidate.year + (1 if candidate.month == 12 else 0)
    month = 1 if candidate.month == 12 else candidate.month + 1
    first = min(options[0], _month_last_day(year, month))
    return date(year, month, first)


def _next_yearly_month_day(candidate: date, month: int, day: int) -> date:
    capped_day = min(day, _month_last_day(candidate.year, month))
    possible = date(candidate.year, month, capped_day)
    if possible >= candidate:
        return possible
    next_year = candidate.year + 1
    return date(next_year, month, min(day, _month_last_day(next_year, month)))


def _next_every_n_months_day(
    candidate: date, day: int, interval_months: int, start_date: date
) -> date:
    anchor = date(
        start_date.year,
        start_date.month,
        min(day, _month_last_day(start_date.year, start_date.month)),
    )
    if candidate <= anchor:
        return anchor
    candidate_index = candidate.year * 12 + (candidate.month - 1)
    anchor_index = anchor.year * 12 + (anchor.month - 1)
    elapsed = candidate_index - anchor_index
    steps = max(0, (elapsed + interval_months - 1) // interval_months)
    while True:
        idx = anchor_index + steps * interval_months
        year = idx // 12
        month = (idx % 12) + 1
        possible = date(year, month, min(day, _month_last_day(year, month)))
        if possible >= candidate:
            return possible
        steps += 1


def _next_every_n_years_month_day(
    candidate: date,
    month: int,
    day: int,
    interval_years: int,
    start_date: date,
) -> date:
    anchor_year = start_date.year
    candidate_year = candidate.year
    if candidate_year <= anchor_year:
        year = anchor_year
    else:
        elapsed = candidate_year - anchor_year
        steps = (elapsed + interval_years - 1) // interval_years
        year = anchor_year + steps * interval_years
    for _ in range(6):
        possible = date(year, month, min(day, _month_last_day(year, month)))
        if possible >= candidate:
            return possible
        year += interval_years
    return date(year, month, min(day, _month_last_day(year, month)))


def _next_biweekly_weekday(candidate: date, weekday: int, start_date: date) -> date:
    base = start_date + timedelta(days=(weekday - start_date.weekday()) % 7)
    if candidate <= base:
        return base
    days_since = (candidate - base).days
    periods_since = (days_since + 13) // 14
    return base + timedelta(days=periods_since * 14)


def _next_every_n_weeks_weekday(
    candidate: date, weekday: int, start_date: date, interval_weeks: int
) -> date:
    base = start_date + timedelta(days=(weekday - start_date.weekday()) % 7)
    if candidate <= base:
        return base
    interval_days = max(1, interval_weeks) * 7
    days_since = (candidate - base).days
    periods_since = (days_since + interval_days - 1) // interval_days
    return base + timedelta(days=periods_since * interval_days)
