from datetime import datetime, timezone
from unittest.mock import patch

from app.domain.services.bl_tracking_api.bl_tracking_service import create_bl, update_bl_status
from app.domain.services.bl_tracking_api.shipment_tracking_service import (
    get_tracking_for_bl,
    register_tracking_for_bl,
)
from app.infrastructure.db.models.bl_tracking import BLMode, BLDirection, BLStatus

ORG_ID = 1


def _make_air_bl(db_session, bl_number="AIR1"):
    return create_bl(
        db_session, org_id=ORG_ID, bl_number=bl_number, mode=BLMode.AIR,
        direction=BLDirection.EXPORT, carrier_name="Emirates", shipper_name="A",
        consignee_name="B", origin_location="X", destination_location="Y",
        flight_number="333-88888888",
    )


def _make_sea_bl(db_session, bl_number="SEA1"):
    return create_bl(
        db_session, org_id=ORG_ID, bl_number=bl_number, mode=BLMode.SEA,
        direction=BLDirection.IMPORT, carrier_name="MSC", shipper_name="A",
        consignee_name="B", origin_location="X", destination_location="Y",
    )


def test_booked_shipment_never_calls_shipsgo(db_session):
    bl = _make_air_bl(db_session)
    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.get_shipment"
    ) as mock_get:
        result = get_tracking_for_bl(bl)
    assert result["available"] is False
    mock_get.assert_not_called()


def test_not_yet_registered_reports_registered_false(db_session):
    bl = _make_air_bl(db_session)
    update_bl_status(db_session, org_id=ORG_ID, bl_id=bl["id"], new_status=BLStatus.IN_TRANSIT,
                      atd=datetime.now(timezone.utc))
    bl = {**bl, "status": "in_transit"}  # reflect the transition for this read
    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.get_shipment"
    ) as mock_get:
        result = get_tracking_for_bl(bl)
    assert result["registered"] is False
    mock_get.assert_not_called()  # no shipsgo_shipment_id stored yet -> no API call at all


def test_register_persists_shipment_id_onto_the_record(db_session):
    bl = _make_sea_bl(db_session)
    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.create_shipment",
        return_value={"id": 42, "reference": bl["bl_number"]},
    ) as mock_create:
        result = register_tracking_for_bl(db_session, org_id=ORG_ID, bl_id=bl["id"])
    mock_create.assert_called_once_with("ocean", reference=bl["bl_number"], identifier=bl["bl_number"])
    assert result["shipsgo_shipment_id"] == 42

    # Re-fetch through the normal service layer and confirm it's really persisted.
    from app.domain.services.bl_tracking_api.bl_tracking_service import get_bl
    refetched = get_bl(db_session, org_id=ORG_ID, bl_id=bl["id"])
    assert refetched["shipsgo_shipment_id"] == 42


def test_register_air_uses_flight_number_as_identifier(db_session):
    bl = _make_air_bl(db_session)
    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.create_shipment",
        return_value={"id": 100, "reference": bl["bl_number"]},
    ) as mock_create:
        register_tracking_for_bl(db_session, org_id=ORG_ID, bl_id=bl["id"])
    mock_create.assert_called_once_with("air", reference=bl["bl_number"], identifier="333-88888888")


def test_get_tracking_uses_stored_shipment_id_after_registration(db_session):
    bl = _make_sea_bl(db_session)
    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.create_shipment",
        return_value={"id": 42, "reference": bl["bl_number"]},
    ):
        register_tracking_for_bl(db_session, org_id=ORG_ID, bl_id=bl["id"])

    from app.domain.services.bl_tracking_api.bl_tracking_service import get_bl
    update_bl_status(db_session, org_id=ORG_ID, bl_id=bl["id"], new_status=BLStatus.IN_TRANSIT,
                      atd=datetime.now(timezone.utc))
    refetched = get_bl(db_session, org_id=ORG_ID, bl_id=bl["id"])

    with patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.get_shipment",
        return_value={"status": "SAILING"},
    ) as mock_get, patch(
        "app.domain.services.bl_tracking_api.shipment_tracking_service.shipsgo_client.get_shipment_route",
        return_value=None,
    ):
        result = get_tracking_for_bl(refetched)
    mock_get.assert_called_once_with("ocean", 42)
    assert result["available"] is True
    assert result["status"] == "SAILING"
