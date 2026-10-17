"""Deterministic date handling for TempeSense.

The LLM never writes date numbers. It names a window ("this_weekend", "2026-10-17..2026-10-19");
this module turns that into exact boundaries in Arizona time and into an ArcGIS
TIMESTAMP clause. Arizona does not observe daylight saving time, so a fixed UTC-7 offset
is correct year-round (and avoids needing the tzdata package on Windows).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

AZ_TZ = timezone(timedelta(hours=-7), "MST")

NAMED_SPECS = (
    "today", "tomorrow", "yesterday",
    "this_weekend", "next_weekend",
    "this_week", "next_week", "last_week",
    "this_month", "next_month", "last_month",
    "next_7_days", "next_30_days", "last_7_days", "last_30_days",
)

_ISO_DATE = r"\d{4}-\d{2}-\d{2}"
_EXPLICIT = re.compile(rf"^({_ISO_DATE})(?:\.\.({_ISO_DATE}))?$")


def now_az() -> datetime:
    return datetime.now(AZ_TZ)


def _midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=AZ_TZ)


def _first_of_month(year: int, month: int) -> date:
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1)


def _normalize(spec: str) -> str:
    s = (spec or "").strip()
    if _EXPLICIT.match(s):
        return s
    return re.sub(r"[\s-]+", "_", s.lower())


def resolve_date_window(spec: str, now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Return (start, end) in Arizona time. start is inclusive, end is exclusive."""
    now = (now or now_az()).astimezone(AZ_TZ)
    today = now.date()
    s = _normalize(spec)

    m = _EXPLICIT.match(s)
    if m:
        d1 = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        d2 = datetime.strptime(m.group(2), "%Y-%m-%d").date() if m.group(2) else d1
        if d2 < d1:
            raise ValueError(f"date range ends before it starts: {spec!r}")
        return _midnight(d1), _midnight(d2 + timedelta(days=1))

    if s == "today":
        return _midnight(today), _midnight(today + timedelta(days=1))
    if s == "tomorrow":
        return _midnight(today + timedelta(days=1)), _midnight(today + timedelta(days=2))
    if s == "yesterday":
        return _midnight(today - timedelta(days=1)), _midnight(today)

    weekday = today.weekday()  # Monday=0 ... Sunday=6
    if s in ("this_weekend", "next_weekend"):
        # Mon-Fri -> the coming Saturday; Sat/Sun -> the weekend already under way.
        saturday = today + timedelta(days=5 - weekday) if weekday <= 4 else today - timedelta(days=weekday - 5)
        if s == "next_weekend":
            saturday += timedelta(days=7)
        return _midnight(saturday), _midnight(saturday + timedelta(days=2))

    if s in ("this_week", "next_week", "last_week"):
        monday = today - timedelta(days=weekday)
        monday += timedelta(days={"this_week": 0, "next_week": 7, "last_week": -7}[s])
        return _midnight(monday), _midnight(monday + timedelta(days=7))

    if s in ("this_month", "next_month", "last_month"):
        offset = {"this_month": 0, "next_month": 1, "last_month": -1}[s]
        start = _first_of_month(today.year, today.month + offset)
        end = _first_of_month(start.year, start.month + 1)
        return _midnight(start), _midnight(end)

    if s == "next_7_days":
        return _midnight(today), _midnight(today + timedelta(days=7))
    if s == "next_30_days":
        return _midnight(today), _midnight(today + timedelta(days=30))
    if s == "last_7_days":
        return _midnight(today - timedelta(days=7)), _midnight(today + timedelta(days=1))
    if s == "last_30_days":
        return _midnight(today - timedelta(days=30)), _midnight(today + timedelta(days=1))

    raise ValueError(
        f"unknown date_range {spec!r}; use one of {', '.join(NAMED_SPECS)} "
        "or YYYY-MM-DD or YYYY-MM-DD..YYYY-MM-DD"
    )


def is_valid_date_spec(spec: str) -> bool:
    try:
        resolve_date_window(spec, datetime(2026, 1, 15, tzinfo=AZ_TZ))
        return True
    except ValueError:
        return False


def _utc_literal(dt: datetime) -> str:
    return "TIMESTAMP '" + dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + "'"


def overlap_clause(start_field: str, end_field: str, window: Tuple[datetime, datetime]) -> str:
    """ArcGIS clause: the record's [start_field, end_field] period overlaps the window.

    ArcGIS hosted layers compare TIMESTAMP literals in UTC, so the Arizona boundaries are
    converted to UTC. An end date equal to the window start counts as overlapping.
    """
    start, end = window
    return f"({start_field} < {_utc_literal(end)} AND {end_field} >= {_utc_literal(start)})"
