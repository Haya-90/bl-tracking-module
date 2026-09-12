"""
shipment_tracking_service.py — business logic for ShipsGo live tracking.

Two distinct operations:
- get_tracking_for_bl(bl): read-only, safe to call anytime, never costs a
  credit. Uses the shipsgo_shipment_id already stored on the record.
- register_tracking_for_bl(db, org_id, bl_id): CONSUMES 1 SHIPSGO CREDIT
  (except when ShipsGo recognizes it as a duplicate, which is free per
  their own docs). Fetches the record, calls ShipsGo to create the
  shipment, and PERSISTS the returned shipsgo_shipment_id back onto the
  record via the repository — this id is required for every later lookup.
  Only ever called from an explicit, user-initiated action.
"""

from sqlalchemy.orm import Session

from app.infrastructure.live_tracking import shipsgo_client
from app.repositories.bl_tracking_repository import BLTrackingRepository


class ShipsGoNotConfigured(shipsgo_client.ShipsGoNotConfigured):
    pass


class ShipsGoUnavailable(shipsgo_client.ShipsGoUnavailable):
    pass


class ShipsGoOutOfCredits(shipsgo_client.ShipsGoOutOfCredits):
    pass


class ShipsGoForbidden(shipsgo_client.ShipsGoForbidden):
    pass


class ShipsGoRequestError(shipsgo_client.ShipsGoRequestError):
    pass


def get_tracking_for_bl(bl: dict) -> dict:
    """Read-only. Never registers anything, never costs a credit."""
    if bl["status"] == "booked":
        return {"available": False, "registered": None,
                "reason": "Shipment is still booked — nothing to track until it's moving."}
    if bl["status"] == "cancelled":
        return {"available": False, "registered": None,
                "reason": "Shipment was cancelled — tracking doesn't apply."}

    shipment_id = bl.get("shipsgo_shipment_id")
    if not shipment_id:
        return {"available": False, "registered": False,
                "reason": "Not yet registered with ShipsGo — register it to start "
                          "live tracking (uses 1 of your ShipsGo credits)."}

    mode = "air" if bl["mode"] == "air" else "ocean"
    try:
        detail = shipsgo_client.get_shipment(mode, shipment_id)
        route = shipsgo_client.get_shipment_route(mode, shipment_id)
    except shipsgo_client.ShipsGoNotConfigured as exc:
        raise ShipsGoNotConfigured(str(exc)) from exc
    except shipsgo_client.ShipsGoUnavailable as exc:
        return {"available": False, "registered": True,
                "reason": f"ShipsGo is temporarily unreachable: {exc}"}

    if detail is None:
        return {"available": False, "registered": True,
                "reason": "ShipsGo has no record of this shipment id (it may have "
                          "been deleted on ShipsGo's side)."}

    position = shipsgo_client.extract_current_position(route) or {}
    return {
        "available": True,
        "registered": True,
        "status": detail.get("status"),
        "reference": detail.get("reference"),
        "checked_at": detail.get("checked_at"),
        **position,
        "source": f"ShipsGo ({'air cargo/AWB' if mode == 'air' else 'ocean container/BL'} tracking)",
    }


def register_tracking_for_bl(db: Session, org_id: int, bl_id: int) -> dict:
    """
    CONSUMES 1 SHIPSGO CREDIT (unless ShipsGo recognizes a duplicate, which
    is free per their docs). Only call from a dedicated, explicit action.
    """
    # Local import avoids a circular import (bl_tracking_service imports
    # nothing from here, but both live in the same package).
    from app.domain.services.bl_tracking_api.bl_tracking_service import (
        get_bl, BLNotFoundError,
    )

    bl = get_bl(db, org_id=org_id, bl_id=bl_id)  # raises BLNotFoundError if missing

    mode = "air" if bl["mode"] == "air" else "ocean"
    identifier = bl["flight_number"] if bl["mode"] == "air" else bl["bl_number"]
    if not identifier:
        raise ShipsGoRequestError(
            f"Cannot register: no {'AWB' if bl['mode'] == 'air' else 'BL'} "
            f"number recorded for this shipment."
        )

    try:
        shipment = shipsgo_client.create_shipment(
            mode, reference=bl["bl_number"], identifier=identifier
        )
    except shipsgo_client.ShipsGoNotConfigured as exc:
        raise ShipsGoNotConfigured(str(exc)) from exc
    except shipsgo_client.ShipsGoOutOfCredits as exc:
        raise ShipsGoOutOfCredits(str(exc)) from exc
    except shipsgo_client.ShipsGoForbidden as exc:
        raise ShipsGoForbidden(str(exc)) from exc
    except shipsgo_client.ShipsGoUnavailable as exc:
        raise ShipsGoUnavailable(str(exc)) from exc
    except shipsgo_client.ShipsGoRequestError as exc:
        raise ShipsGoRequestError(str(exc)) from exc

    shipment_id = shipment["id"]

    repo = BLTrackingRepository(db)
    record = repo.get_by_id(bl_id, org_id)
    repo.update(record, shipsgo_shipment_id=shipment_id)

    return {"registered": True, "shipsgo_shipment_id": shipment_id}
