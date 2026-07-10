"""Deterministic analysis clock used to prevent look-ahead leakage."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?(?!\d)")


def normalize_analysis_date(value: str | date | datetime | None) -> date:
    if value is None:
        return datetime.now().astimezone().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("analysis date must use YYYY-MM-DD") from exc


def current_analysis_date() -> date:
    """Return the automatic date anchor for a current research run."""
    return datetime.now().astimezone().date()


def coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def dates_in_text(text: str, as_of: date) -> list[date]:
    dates: list[date] = []
    for match in DATE_PATTERN.finditer(text or ""):
        try:
            parsed = date(*(int(part) for part in match.groups()))
        except ValueError:
            continue
        if parsed <= as_of:
            dates.append(parsed)
    return dates


def period_end(period: str) -> date | None:
    text = period or ""
    year_match = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
    if not year_match:
        return None
    year = int(year_match.group(1))
    quarter_match = re.search(r"(?:Q|第)([1-4])(?:季度)?", text, re.IGNORECASE)
    if quarter_match:
        quarter = int(quarter_match.group(1))
        month_day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        month, day = month_day[quarter]
        return date(year, month, day)
    if any(token in text.lower() for token in ("h1", "半年", "中报")):
        return date(year, 6, 30)
    return date(year, 12, 31)


def temporal_contract(analysis_date: date) -> str:
    return f"""
## Binding Current-Research Contract

- Run date: {analysis_date.isoformat()}.
- Evidence may be historical; do not discard it merely because it is old.
- A future-dated observation cannot be treated as an event that already occurred.
- A forecast is a forecast, not an observed fact, regardless of publication date.
- Unknown publication dates cannot support a current-price or latest-period claim.
- Every time-sensitive claim must state its observation date and evidence ID.
""".strip()
