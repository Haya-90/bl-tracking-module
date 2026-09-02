"""
BLTrackingRepository — layer 3. Every db.query() call for BLTracking lives
here, and nowhere else (per the architecture: "One class per model. All
db.query() calls live here. create() flushes, never commits.").

The repository never commits the session — commit is the request-scoped
session dependency's job (per core/database.get_db, per the blueprint's
core/ responsibility). This lets a service compose several repository calls
inside one atomic transaction if it ever needs to.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.infrastructure.db.models.bl_tracking import (
    BLTracking,
    BLMode,
    BLDirection,
    BLStatus,
)


class BLTrackingRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- reads -----------------------------------------------------------

    def get_by_id(self, bl_id: int, org_id: int) -> Optional[BLTracking]:
        return (
            self.db.query(BLTracking)
            .filter(BLTracking.id == bl_id, BLTracking.org_id == org_id)
            .first()
        )

    def get_by_bl_number(self, bl_number: str, org_id: int) -> Optional[BLTracking]:
        return (
            self.db.query(BLTracking)
            .filter(
                BLTracking.bl_number == bl_number,
                BLTracking.org_id == org_id,
            )
            .first()
        )

    def _filtered_query(
        self,
        org_id: int,
        mode: Optional[BLMode] = None,
        direction: Optional[BLDirection] = None,
        status: Optional[BLStatus] = None,
        carrier_name: Optional[str] = None,
        bl_number: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ):
        query = self.db.query(BLTracking).filter(BLTracking.org_id == org_id)

        if mode is not None:
            query = query.filter(BLTracking.mode == mode)
        if direction is not None:
            query = query.filter(BLTracking.direction == direction)
        if status is not None:
            query = query.filter(BLTracking.status == status)
        if carrier_name:
            query = query.filter(BLTracking.carrier_name.ilike(f"%{carrier_name}%"))
        if bl_number:
            query = query.filter(BLTracking.bl_number.ilike(f"%{bl_number}%"))
        if date_from is not None:
            query = query.filter(BLTracking.created_at >= date_from)
        if date_to is not None:
            query = query.filter(BLTracking.created_at <= date_to)

        return query

    def list_for_org(
        self,
        org_id: int,
        offset: int = 0,
        limit: int = 50,
        **filters,
    ) -> list[BLTracking]:
        return (
            self._filtered_query(org_id, **filters)
            .order_by(BLTracking.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_for_org(self, org_id: int, **filters) -> int:
        return self._filtered_query(org_id, **filters).count()

    # --- writes ------------------------------------------------------

    def create(self, **fields) -> BLTracking:
        record = BLTracking(**fields)
        self.db.add(record)
        self.db.flush()  # get record.id populated; caller/session owns commit
        return record

    def update(self, record: BLTracking, **fields) -> BLTracking:
        for key, value in fields.items():
            setattr(record, key, value)
        self.db.flush()
        return record

    def delete(self, record: BLTracking) -> None:
        self.db.delete(record)
        self.db.flush()
