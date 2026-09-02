"""
bl_tracking_routes.py — layer 1. HTTP only: reads input, calls the service,
renders output. No SQL, no business rules here (per the architecture
blueprint).

ASSUMPTION: the existing app exposes:
  - `get_db` — a request-scoped Session dependency (core/database.py)
  - `get_current_org_id` / `get_current_user_id` — auth dependencies
    (core/security.py, per the blueprint's "JWT security" responsibility)
  - `error_handlers.py`'s `@handle_route_errors` decorator / equivalent
    exception handling for domain errors

Register this router in main.py alongside the other routers, e.g.:

    from app.api.routes.bl_tracking_routes import router as bl_tracking_router
    app.include_router(bl_tracking_router)
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status

from app.api.routes.bl_tracking_schemas import (
    BLCreateRequest,
    BLUpdateRequest,
    BLStatusUpdateRequest,
    BLResponse,
    BLListResponse,
)
from app.core.database import get_db  # ASSUMPTION
from app.core.security import get_current_org_id, get_current_user_id  # ASSUMPTION
from app.domain.services.bl_tracking_api import (
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

router = APIRouter(prefix="/bl", tags=["bl-tracking"])


@router.post("", response_model=BLResponse, status_code=http_status.HTTP_201_CREATED)
def create_bl_route(
    payload: BLCreateRequest,
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return create_bl(
            db,
            org_id=org_id,
            created_by_id=user_id,
            **payload.dict(),
        )
    except BLValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{bl_id}", response_model=BLResponse)
def get_bl_route(
    bl_id: int,
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
):
    try:
        return get_bl(db, org_id=org_id, bl_id=bl_id)
    except BLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("", response_model=BLListResponse)
def list_bl_route(
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
    mode: Optional[BLMode] = None,
    direction: Optional[BLDirection] = None,
    status: Optional[BLStatus] = None,
    carrier_name: Optional[str] = None,
    bl_number: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return list_bl(
        db,
        org_id=org_id,
        mode=mode,
        direction=direction,
        status=status,
        carrier_name=carrier_name,
        bl_number=bl_number,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.patch("/{bl_id}", response_model=BLResponse)
def update_bl_route(
    bl_id: int,
    payload: BLUpdateRequest,
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
):
    try:
        return update_bl(db, org_id=org_id, bl_id=bl_id, **payload.to_service_kwargs())
    except BLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BLValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/{bl_id}/status", response_model=BLResponse)
def update_bl_status_route(
    bl_id: int,
    payload: BLStatusUpdateRequest,
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
):
    try:
        return update_bl_status(
            db,
            org_id=org_id,
            bl_id=bl_id,
            new_status=payload.status,
            atd=payload.atd,
            ata=payload.ata,
        )
    except BLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BLStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except BLValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.delete("/{bl_id}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_bl_route(
    bl_id: int,
    db=Depends(get_db),
    org_id: int = Depends(get_current_org_id),
):
    try:
        delete_bl(db, org_id=org_id, bl_id=bl_id)
    except BLNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except BLDeleteNotAllowedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
