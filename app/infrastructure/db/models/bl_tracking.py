"""
BLTracking model — one Bill of Lading / Air Waybill record per shipment,
trackable in either trade direction (import/export) and either mode
(air/sea).

Layer: app/infrastructure/db/models/  (layer 4 — SQLAlchemy ORM, one class
per file, registered in models/__init__.py per the architecture blueprint).
No business logic here — validation and workflow rules live in
domain/services/bl_tracking_api/bl_tracking_service.py.
"""

import enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

# ASSUMPTION: app/core/database.py exposes the shared declarative Base,
# consistent with core/ being "config, DB session, JWT security" per the
# blueprint. Adjust this import once the real core/database.py is available.
from app.core.database import Base


class BLMode(str, enum.Enum):
    AIR = "air"
    SEA = "sea"


class BLDirection(str, enum.Enum):
    IMPORT = "import"
    EXPORT = "export"


class BLStatus(str, enum.Enum):
    BOOKED = "booked"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class BLTracking(Base):
    __tablename__ = "bl_tracking"

    id = Column(Integer, primary_key=True)

    # --- ownership ---------------------------------------------------
    # ASSUMPTION: an `organizations` table with an integer `id` PK exists,
    # matching the blueprint's `list_for_org` repository convention.
    org_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # Optional link back to the inquiry this shipment originated from.
    # ASSUMPTION: an `inquiries` table exists (the blueprint's inquiries_api
    # service implies one).
    inquiry_id = Column(
        Integer,
        ForeignKey("inquiries.id"),
        nullable=True,
        index=True,
    )

    # ASSUMPTION: a `users` table exists for audit trail purposes.
    created_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    # --- document identity --------------------------------------------
    bl_number = Column(String(64), nullable=False, index=True)
    mode = Column(Enum(BLMode, name="bl_mode"), nullable=False)
    direction = Column(Enum(BLDirection, name="bl_direction"), nullable=False)
    status = Column(
        Enum(BLStatus, name="bl_status"),
        nullable=False,
        default=BLStatus.BOOKED,
        server_default=BLStatus.BOOKED.value,
    )

    # --- parties --------------------------------------------------------
    carrier_name = Column(String(128), nullable=False)
    shipper_name = Column(String(256), nullable=False)
    consignee_name = Column(String(256), nullable=False)

    # --- routing ----------------------------------------------------
    origin_location = Column(String(128), nullable=False)
    destination_location = Column(String(128), nullable=False)

    # --- mode-specific fields (nullable; enforced conditionally in the
    # service layer, not the DB, since "should be present" is a soft rule) --
    vessel_name = Column(String(128), nullable=True)       # sea only
    voyage_number = Column(String(64), nullable=True)      # sea only
    container_numbers = Column(Text, nullable=True)        # sea only, CSV
    flight_number = Column(String(32), nullable=True)      # air only

    # --- cargo details ------------------------------------------------
    package_count = Column(Integer, nullable=True)
    gross_weight_kg = Column(Numeric(12, 2), nullable=True)
    volume_cbm = Column(Numeric(12, 3), nullable=True)

    # --- schedule (estimated vs actual) ---------------------------------
    etd = Column(DateTime(timezone=True), nullable=True)
    eta = Column(DateTime(timezone=True), nullable=True)
    atd = Column(DateTime(timezone=True), nullable=True)
    ata = Column(DateTime(timezone=True), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # --- relationships --------------------------------------------------
    # ASSUMPTION: Organization / Inquiry / User models exist with these
    # class names; adjust to match the real model class names.
    organization = relationship("Organization", lazy="joined")
    inquiry = relationship("Inquiry", lazy="joined")
    created_by = relationship("User", lazy="joined")

    __table_args__ = (
        # bl_number is unique per org, not globally (see business rules).
        UniqueConstraint("org_id", "bl_number", name="uq_bl_tracking_org_bl_number"),
        CheckConstraint(
            "(mode != 'sea') OR (flight_number IS NULL)",
            name="ck_bl_tracking_sea_no_flight_number",
        ),
        CheckConstraint(
            "(mode != 'air') OR "
            "(vessel_name IS NULL AND voyage_number IS NULL AND container_numbers IS NULL)",
            name="ck_bl_tracking_air_no_sea_fields",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return (
            f"<BLTracking id={self.id} bl_number={self.bl_number!r} "
            f"mode={self.mode} direction={self.direction} status={self.status}>"
        )
