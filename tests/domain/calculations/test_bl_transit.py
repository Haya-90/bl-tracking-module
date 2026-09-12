"""
Pure-function tests — no DB, no fixtures needed, per the blueprint's test
tree mirroring domain/calculations.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.calculations.bl_transit import (
    compute_transit_days,
    compute_transit_label,
    is_overdue,
)
from app.infrastructure.db.models.bl_tracking import BLStatus


def test_compute_transit_days_returns_none_without_both_dates():
    assert compute_transit_days(None, None) is None
    assert compute_transit_days(datetime.now(timezone.utc), None) is None


def test_compute_transit_days_counts_whole_days():
    atd = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ata = datetime(2026, 1, 15, tzinfo=timezone.utc)
    assert compute_transit_days(atd, ata) == 14


def test_compute_transit_label_cancelled():
    assert compute_transit_label(BLStatus.CANCELLED, None, None, None, None) == "Cancelled"


def test_compute_transit_label_delivered_with_transit_time():
    atd = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ata = datetime(2026, 1, 8, tzinfo=timezone.utc)
    label = compute_transit_label(BLStatus.DELIVERED, None, None, atd, ata)
    assert "Delivered" in label
    assert "7 day" in label


def test_compute_transit_label_booked_shows_days_to_departure():
    etd = datetime.now(timezone.utc) + timedelta(days=3)
    label = compute_transit_label(BLStatus.BOOKED, etd, None, None, None)
    assert "Booked" in label


def test_is_overdue_true_when_past_eta_and_in_transit():
    past_eta = datetime.now(timezone.utc) - timedelta(days=1)
    assert is_overdue(BLStatus.IN_TRANSIT, past_eta) is True


def test_is_overdue_false_when_not_in_transit():
    past_eta = datetime.now(timezone.utc) - timedelta(days=1)
    assert is_overdue(BLStatus.DELIVERED, past_eta) is False


def test_is_overdue_false_without_eta():
    assert is_overdue(BLStatus.IN_TRANSIT, None) is False
