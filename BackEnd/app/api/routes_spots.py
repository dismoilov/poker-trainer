"""Spots API routes (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import Spot, SpotCreateRequest
from app.security import get_current_user
from app.models import UserModel
from app.services import spots as spots_service

router = APIRouter(prefix="/api", tags=["spots"])


@router.get("/spots", response_model=list[Spot])
def get_spots(
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    return spots_service.get_all_spots(db)


@router.get("/spots/{spot_id}", response_model=Spot)
def get_spot(
    spot_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    spot = spots_service.get_spot_by_id(db, spot_id)
    if not spot:
        raise HTTPException(status_code=404, detail=f"Spot not found: {spot_id}")
    return spot


@router.post("/spots", response_model=Spot)
def create_spot(
    req: SpotCreateRequest,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    try:
        return spots_service.create_custom_spot(db, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/spots/{spot_id}")
def delete_spot(
    spot_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    try:
        spots_service.delete_spot(db, spot_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
