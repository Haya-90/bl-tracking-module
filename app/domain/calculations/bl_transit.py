"""
bl_transit.py — pure freight-tracking math, no DB/I/O, no calls out.

Per the architecture blueprint: "domain/calculations — pure freight math, no
DB/I/O." These functions take plain values in and return plain values out;
they never touch a session, a repository, or an API.
"""

from datetime import datetime, timezone
from typing import Optional

from app.infrastructure.db.models.bl_tracking import BLStatus


def _as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    Normalize to a tz-aware UTC datetime. Some database drivers (notably
    SQLite, used in tests) drop tzinfo on round-trip even for a
    timezone-aware column, so two datetimes that are logically both UTC can
    otherwise arrive as one naive and one aware, which raises a TypeError on
    subtraction. Treat a naive datetime as already being UTC rather than
    fail — never guess a different offset.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_transit_days(
    atd: Optional[datetime], ata: Optional[datetime]
) -> Optional[int]:
    """
    Actual transit time in whole days, once both actual departure and actual
    arrival are known. Returns None if either date is missing (transit isn't
    over, or hasn't started).
    """
    atd = _as_aware_utc(atd)
    ata = _as_aware_utc(ata)
    if atd is None or ata is None:
        return None
    delta = ata - atd
    return max(delta.days, 0)


def compute_transit_label(
    status: BLStatus,
    etd: Optional[datetime],
    eta: Optional[datetime],
    atd: Optional[datetime],
    ata: Optional[datetime],
) -> str:
    """
    A short, human-readable summary of where the shipment stands, derived
    only from stored dates + status — no new data is fetched.
    """
    if status == BLStatus.CANCELLED:
        return "Cancelled"

    if status == BLStatus.DELIVERED:
        days = compute_transit_days(atd, ata)
        return f"Delivered — {days} day(s) in transit" if days is not None else "Delivered"

    if status == BLStatus.ARRIVED:
        return "Arrived — awaiting delivery"

    if status == BLStatus.IN_TRANSIT:
        eta = _as_aware_utc(eta)
        if eta is not None:
            days_left = (eta - datetime.now(timezone.utc)).days
            if days_left > 0:
                return f"In transit — ETA in {days_left} day(s)"
            if days_left == 0:
                return "In transit — arriving today"
            return "In transit — overdue against ETA"
        return "In transit"

    if status == BLStatus.BOOKED:
        etd = _as_aware_utc(etd)
        if etd is not None:
            days_to_departure = (etd - datetime.now(timezone.utc)).days
            if days_to_departure > 0:
                return f"Booked — departs in {days_to_departure} day(s)"
        return "Booked"

    return status.value  # pragma: no cover - defensive fallback


def is_overdue(status: BLStatus, eta: Optional[datetime]) -> bool:
    """True if the shipment is still in transit past its ETA."""
    eta = _as_aware_utc(eta)
    if status != BLStatus.IN_TRANSIT or eta is None:
        return False
    return datetime.now(timezone.utc) > eta
