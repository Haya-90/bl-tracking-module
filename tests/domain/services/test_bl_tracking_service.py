"""
Service-layer tests for bl_tracking_service — the most important test file,
since this is where the business rules live.
"""
from datetime import datetime, timezone

import pytest

from app.domain.services.bl_tracking_api.bl_tracking_service import (
    create_bl,
    get_bl,
    list_bl,
    update_bl,
    update_bl_status,
    delete_bl,
    BLValidationError,
    BLNotFoundError,
    BLStatusTransitionError,
    BLDeleteNotAllowedError,
)
from app.infrastructure.db.models.bl_tracking import BLMode, BLDirection, BLStatus

ORG_ID = 1


def _make_sea_bl(db_session, bl_number="MSCU1234567"):
    return create_bl(
        db_session,
        org_id=ORG_ID,
        bl_number=bl_number,
        mode=BLMode.SEA,
        direction=BLDirection.IMPORT,
        carrier_name="MSC",
        shipper_name="Acme Exports",
        consignee_name="Acme Imports",
        origin_location="CNSHA",
        destination_location="PKKHI",
        vessel_name="MSC Anna",
        voyage_number="V123",
    )


def _make_air_bl(db_session, bl_number="020-12345678"):
    return create_bl(
        db_session,
        org_id=ORG_ID,
        bl_number=bl_number,
        mode=BLMode.AIR,
        direction=BLDirection.EXPORT,
        carrier_name="Emirates SkyCargo",
        shipper_name="Acme Exports",
        consignee_name="Acme Imports",
        origin_location="PKKHI",
        destination_location="AEDXB",
        flight_number="EK601",
    )


# --- create: valid input ------------------------------------------------

def test_create_sea_bl_succeeds(db_session):
    result = _make_sea_bl(db_session)
    assert result["status"] == BLStatus.BOOKED
    assert result["mode"] == BLMode.SEA
    assert result["vessel_name"] == "MSC Anna"


def test_create_air_bl_succeeds(db_session):
    result = _make_air_bl(db_session)
    assert result["mode"] == BLMode.AIR
    assert result["flight_number"] == "EK601"


# --- create: invalid input / business rules ------------------------------

def test_create_sea_bl_with_flight_number_rejected(db_session):
    with pytest.raises(BLValidationError):
        create_bl(
            db_session,
            org_id=ORG_ID,
            bl_number="BAD1",
            mode=BLMode.SEA,
            direction=BLDirection.IMPORT,
            carrier_name="MSC",
            shipper_name="A",
            consignee_name="B",
            origin_location="X",
            destination_location="Y",
            flight_number="EK601",  # not allowed for sea
        )


def test_create_air_bl_with_vessel_name_rejected(db_session):
    with pytest.raises(BLValidationError):
        create_bl(
            db_session,
            org_id=ORG_ID,
            bl_number="BAD2",
            mode=BLMode.AIR,
            direction=BLDirection.EXPORT,
            carrier_name="Emirates",
            shipper_name="A",
            consignee_name="B",
            origin_location="X",
            destination_location="Y",
            vessel_name="Should not be here",  # not allowed for air
        )


def test_duplicate_bl_number_within_org_rejected(db_session):
    _make_sea_bl(db_session, bl_number="DUPLICATE1")
    with pytest.raises(BLValidationError):
        _make_sea_bl(db_session, bl_number="DUPLICATE1")


# --- get / not found -------------------------------------------------

def test_get_bl_not_found_raises(db_session):
    with pytest.raises(BLNotFoundError):
        get_bl(db_session, org_id=ORG_ID, bl_id=999999)


def test_get_bl_scoped_to_org(db_session):
    created = _make_sea_bl(db_session)
    with pytest.raises(BLNotFoundError):
        get_bl(db_session, org_id=999, bl_id=created["id"])  # wrong org


# --- list / search --------------------------------------------------

def test_list_bl_filters_by_mode(db_session):
    _make_sea_bl(db_session, bl_number="SEA1")
    _make_air_bl(db_session, bl_number="AIR1")

    result = list_bl(db_session, org_id=ORG_ID, mode=BLMode.AIR)
    assert result["total"] == 1
    assert result["items"][0]["mode"] == BLMode.AIR


# --- status transitions: business rules ----------------------------------

def test_status_transition_booked_to_in_transit_requires_atd(db_session):
    created = _make_sea_bl(db_session)
    with pytest.raises(BLValidationError):
        update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.IN_TRANSIT)


def test_status_transition_booked_to_in_transit_succeeds_with_atd(db_session):
    created = _make_sea_bl(db_session)
    result = update_bl_status(
        db_session,
        org_id=ORG_ID,
        bl_id=created["id"],
        new_status=BLStatus.IN_TRANSIT,
        atd=datetime.now(timezone.utc),
    )
    assert result["status"] == BLStatus.IN_TRANSIT


def test_status_transition_cannot_skip_to_delivered(db_session):
    created = _make_sea_bl(db_session)
    with pytest.raises(BLStatusTransitionError):
        update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.DELIVERED)


def test_status_transition_cannot_cancel_after_arrived(db_session):
    created = _make_sea_bl(db_session)
    now = datetime.now(timezone.utc)
    update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.IN_TRANSIT, atd=now)
    update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.ARRIVED, ata=now)
    with pytest.raises(BLStatusTransitionError):
        update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.CANCELLED)


def test_full_happy_path_booked_to_delivered(db_session):
    created = _make_sea_bl(db_session)
    now = datetime.now(timezone.utc)
    update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.IN_TRANSIT, atd=now)
    update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.ARRIVED, ata=now)
    result = update_bl_status(db_session, org_id=ORG_ID, bl_id=created["id"], new_status=BLStatus.DELIVERED)
    assert result["status"] == BLStatus.DELIVERED


# --- delete: business rule -------------------------------------------

def test_delete_allowed_while_booked(db_session):
    created = _make_sea_bl(db_session)
    delete_bl(db_session, org_id=ORG_ID, bl_id=created["id"])
    with pytest.raises(BLNotFoundError):
        get_bl(db_session, org_id=ORG_ID, bl_id=created["id"])


def test_delete_rejected_once_in_transit(db_session):
    created = _make_sea_bl(db_session)
    update_bl_status(
        db_session,
        org_id=ORG_ID,
        bl_id=created["id"],
        new_status=BLStatus.IN_TRANSIT,
        atd=datetime.now(timezone.utc),
    )
    with pytest.raises(BLDeleteNotAllowedError):
        delete_bl(db_session, org_id=ORG_ID, bl_id=created["id"])


# --- update: re-validates mode fields ------------------------------------

def test_update_rejects_introducing_flight_number_on_sea_bl(db_session):
    created = _make_sea_bl(db_session)
    with pytest.raises(BLValidationError):
        update_bl(db_session, org_id=ORG_ID, bl_id=created["id"], flight_number="EK601")
