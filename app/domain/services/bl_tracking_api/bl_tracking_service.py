"""
bl_tracking_service.py — layer 2. Business logic, validation, and workflow
rules for BL Tracking.

Per the architecture blueprint: "Business logic. Plain values + db: Session
in. No fastapi imports, no raw SQL." Accordingly, every function here takes
plain Python values (ints, strs, datetimes, enums) and a `db: Session` — no
Pydantic request models, no FastAPI Request/Response objects. Routes are
responsible for translating HTTP payloads into these plain arguments and
back.

    create_bl()
         ↓
    validate input
         ↓
    apply business rules
         ↓
    perform calculations (transit label, for the return value)
         ↓
    repository.create()
         ↓
    return result
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.domain.calculations.bl_transit import (
    compute_transit_days,
    compute_transit_label,
)
from app.infrastructure.db.models.bl_tracking import (
    BLTracking,
    BLMode,
    BLDirection,
    BLStatus,
)
from app.repositories.bl_tracking_repository import BLTrackingRepository


# --- domain errors (never HTTP-status-coded here; routes translate these
# into the right HTTP response, e.g. 404 / 409 / 422) ----------------------

class BLValidationError(Exception):
    """Raised when input data violates a BL Tracking business rule."""


class BLNotFoundError(Exception):
    """Raised when a BL record doesn't exist for the given org."""


class BLStatusTransitionError(Exception):
    """Raised when a requested status change isn't a legal transition."""


class BLDeleteNotAllowedError(Exception):
    """Raised when a delete is requested on a BL that's already moving."""


_ALLOWED_STATUS_TRANSITIONS = {
    BLStatus.BOOKED: {BLStatus.IN_TRANSIT, BLStatus.CANCELLED},
    BLStatus.IN_TRANSIT: {BLStatus.ARRIVED, BLStatus.CANCELLED},
    BLStatus.ARRIVED: {BLStatus.DELIVERED},
    BLStatus.DELIVERED: set(),
    BLStatus.CANCELLED: set(),
}


def _validate_mode_fields(
    mode: BLMode,
    vessel_name: Optional[str],
    voyage_number: Optional[str],
    container_numbers: Optional[str],
    flight_number: Optional[str],
) -> None:
    """Hard rule: a field belonging to the other mode must not be set."""
    if mode == BLMode.SEA and flight_number:
        raise BLValidationError("flight_number must not be set when mode is 'sea'")
    if mode == BLMode.AIR and (vessel_name or voyage_number or container_numbers):
        raise BLValidationError(
            "vessel_name / voyage_number / container_numbers must not be set "
            "when mode is 'air'"
        )


def _serialize(record: BLTracking) -> dict:
    """Attach the read-only computed transit label to the record's data."""
    return {
        "id": record.id,
        "org_id": record.org_id,
        "inquiry_id": record.inquiry_id,
        "bl_number": record.bl_number,
        "mode": record.mode,
        "direction": record.direction,
        "status": record.status,
        "carrier_name": record.carrier_name,
        "shipper_name": record.shipper_name,
        "consignee_name": record.consignee_name,
        "origin_location": record.origin_location,
        "destination_location": record.destination_location,
        "vessel_name": record.vessel_name,
        "voyage_number": record.voyage_number,
        "container_numbers": record.container_numbers,
        "flight_number": record.flight_number,
        "package_count": record.package_count,
        "gross_weight_kg": record.gross_weight_kg,
        "volume_cbm": record.volume_cbm,
        "etd": record.etd,
        "eta": record.eta,
        "atd": record.atd,
        "ata": record.ata,
        "notes": record.notes,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "transit_days": compute_transit_days(record.atd, record.ata),
        "transit_label": compute_transit_label(
            record.status, record.etd, record.eta, record.atd, record.ata
        ),
    }


# --- operations -------------------------------------------------------

def create_bl(
    db: Session,
    org_id: int,
    bl_number: str,
    mode: BLMode,
    direction: BLDirection,
    carrier_name: str,
    shipper_name: str,
    consignee_name: str,
    origin_location: str,
    destination_location: str,
    inquiry_id: Optional[int] = None,
    created_by_id: Optional[int] = None,
    vessel_name: Optional[str] = None,
    voyage_number: Optional[str] = None,
    container_numbers: Optional[str] = None,
    flight_number: Optional[str] = None,
    package_count: Optional[int] = None,
    gross_weight_kg: Optional[float] = None,
    volume_cbm: Optional[float] = None,
    etd: Optional[datetime] = None,
    eta: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> dict:
    repo = BLTrackingRepository(db)

    _validate_mode_fields(mode, vessel_name, voyage_number, container_numbers, flight_number)

    if repo.get_by_bl_number(bl_number, org_id) is not None:
        raise BLValidationError(
            f"bl_number '{bl_number}' already exists for this organization"
        )

    record = repo.create(
        org_id=org_id,
        inquiry_id=inquiry_id,
        created_by_id=created_by_id,
        bl_number=bl_number,
        mode=mode,
        direction=direction,
        status=BLStatus.BOOKED,
        carrier_name=carrier_name,
        shipper_name=shipper_name,
        consignee_name=consignee_name,
        origin_location=origin_location,
        destination_location=destination_location,
        vessel_name=vessel_name,
        voyage_number=voyage_number,
        container_numbers=container_numbers,
        flight_number=flight_number,
        package_count=package_count,
        gross_weight_kg=gross_weight_kg,
        volume_cbm=volume_cbm,
        etd=etd,
        eta=eta,
        notes=notes,
    )
    return _serialize(record)


def get_bl(db: Session, org_id: int, bl_id: int) -> dict:
    repo = BLTrackingRepository(db)
    record = repo.get_by_id(bl_id, org_id)
    if record is None:
        raise BLNotFoundError(f"BL id {bl_id} not found for this organization")
    return _serialize(record)


def list_bl(
    db: Session,
    org_id: int,
    mode: Optional[BLMode] = None,
    direction: Optional[BLDirection] = None,
    status: Optional[BLStatus] = None,
    carrier_name: Optional[str] = None,
    bl_number: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    repo = BLTrackingRepository(db)
    filters = dict(
        mode=mode,
        direction=direction,
        status=status,
        carrier_name=carrier_name,
        bl_number=bl_number,
        date_from=date_from,
        date_to=date_to,
    )
    offset = max(page - 1, 0) * page_size
    records = repo.list_for_org(org_id, offset=offset, limit=page_size, **filters)
    total = repo.count_for_org(org_id, **filters)
    return {
        "items": [_serialize(r) for r in records],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def update_bl(
    db: Session,
    org_id: int,
    bl_id: int,
    **fields,
) -> dict:
    repo = BLTrackingRepository(db)
    record = repo.get_by_id(bl_id, org_id)
    if record is None:
        raise BLNotFoundError(f"BL id {bl_id} not found for this organization")

    # Re-validate mode-specific fields using the post-update view of the record.
    mode = fields.get("mode", record.mode)
    vessel_name = fields.get("vessel_name", record.vessel_name)
    voyage_number = fields.get("voyage_number", record.voyage_number)
    container_numbers = fields.get("container_numbers", record.container_numbers)
    flight_number = fields.get("flight_number", record.flight_number)
    _validate_mode_fields(mode, vessel_name, voyage_number, container_numbers, flight_number)

    if "bl_number" in fields and fields["bl_number"] != record.bl_number:
        existing = repo.get_by_bl_number(fields["bl_number"], org_id)
        if existing is not None:
            raise BLValidationError(
                f"bl_number '{fields['bl_number']}' already exists for this organization"
            )

    record = repo.update(record, **fields)
    return _serialize(record)


def update_bl_status(
    db: Session,
    org_id: int,
    bl_id: int,
    new_status: BLStatus,
    atd: Optional[datetime] = None,
    ata: Optional[datetime] = None,
) -> dict:
    repo = BLTrackingRepository(db)
    record = repo.get_by_id(bl_id, org_id)
    if record is None:
        raise BLNotFoundError(f"BL id {bl_id} not found for this organization")

    allowed = _ALLOWED_STATUS_TRANSITIONS.get(record.status, set())
    if new_status not in allowed:
        raise BLStatusTransitionError(
            f"cannot transition from '{record.status.value}' to '{new_status.value}'"
        )

    updates: dict = {"status": new_status}

    if new_status == BLStatus.IN_TRANSIT:
        effective_atd = atd or record.atd
        if effective_atd is None:
            raise BLValidationError("atd (actual time of departure) is required to mark in_transit")
        updates["atd"] = effective_atd

    if new_status == BLStatus.ARRIVED:
        effective_ata = ata or record.ata
        if effective_ata is None:
            raise BLValidationError("ata (actual time of arrival) is required to mark arrived")
        updates["ata"] = effective_ata

    record = repo.update(record, **updates)
    return _serialize(record)


def delete_bl(db: Session, org_id: int, bl_id: int) -> None:
    repo = BLTrackingRepository(db)
    record = repo.get_by_id(bl_id, org_id)
    if record is None:
        raise BLNotFoundError(f"BL id {bl_id} not found for this organization")

    if record.status != BLStatus.BOOKED:
        raise BLDeleteNotAllowedError(
            "cannot delete a BL once it has departed (status is no longer 'booked')"
        )

    repo.delete(record)
