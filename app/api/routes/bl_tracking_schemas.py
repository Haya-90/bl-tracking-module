"""
Pydantic schemas for the BL Tracking HTTP layer only. These live under
api/routes/ (not in the service) because the blueprint's service layer must
stay framework/DTO-agnostic ("Plain values + db... no fastapi imports").
Routes translate between these schemas and the plain-value service calls.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.infrastructure.db.models.bl_tracking import BLMode, BLDirection, BLStatus


class BLCreateRequest(BaseModel):
    bl_number: str = Field(..., max_length=64)
    mode: BLMode
    direction: BLDirection
    carrier_name: str = Field(..., max_length=128)
    shipper_name: str = Field(..., max_length=256)
    consignee_name: str = Field(..., max_length=256)
    origin_location: str = Field(..., max_length=128)
    destination_location: str = Field(..., max_length=128)
    inquiry_id: Optional[int] = None
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    container_numbers: Optional[str] = None
    flight_number: Optional[str] = None
    package_count: Optional[int] = None
    gross_weight_kg: Optional[float] = None
    volume_cbm: Optional[float] = None
    etd: Optional[datetime] = None
    eta: Optional[datetime] = None
    notes: Optional[str] = None


class BLUpdateRequest(BaseModel):
    """All fields optional — a PATCH only sends what's changing."""

    bl_number: Optional[str] = None
    mode: Optional[BLMode] = None
    direction: Optional[BLDirection] = None
    carrier_name: Optional[str] = None
    shipper_name: Optional[str] = None
    consignee_name: Optional[str] = None
    origin_location: Optional[str] = None
    destination_location: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    container_numbers: Optional[str] = None
    flight_number: Optional[str] = None
    package_count: Optional[int] = None
    gross_weight_kg: Optional[float] = None
    volume_cbm: Optional[float] = None
    etd: Optional[datetime] = None
    eta: Optional[datetime] = None
    notes: Optional[str] = None

    def to_service_kwargs(self) -> dict:
        """Only the fields the caller actually set — for partial updates."""
        return self.dict(exclude_unset=True)


class BLStatusUpdateRequest(BaseModel):
    status: BLStatus
    atd: Optional[datetime] = None
    ata: Optional[datetime] = None


class BLResponse(BaseModel):
    id: int
    org_id: int
    inquiry_id: Optional[int]
    bl_number: str
    mode: BLMode
    direction: BLDirection
    status: BLStatus
    carrier_name: str
    shipper_name: str
    consignee_name: str
    origin_location: str
    destination_location: str
    vessel_name: Optional[str]
    voyage_number: Optional[str]
    container_numbers: Optional[str]
    flight_number: Optional[str]
    package_count: Optional[int]
    gross_weight_kg: Optional[float]
    volume_cbm: Optional[float]
    etd: Optional[datetime]
    eta: Optional[datetime]
    atd: Optional[datetime]
    ata: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    transit_days: Optional[int]
    transit_label: str

    class Config:
        orm_mode = True


class BLListResponse(BaseModel):
    items: list[BLResponse]
    page: int
    page_size: int
    total: int
