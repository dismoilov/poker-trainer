"""Analytics API routes (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AnalyticsSummary, AnalyticsRow, AnalyticsQuestion, GameDetail
from app.security import get_current_user
from app.models import UserModel
from app.services import analytics as analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    return analytics_service.get_summary(db, user.id)


@router.get("/history", response_model=list[AnalyticsRow])
def get_history(
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    return analytics_service.get_history(db, user.id)


@router.get("/recent", response_model=list[AnalyticsQuestion])
def get_recent(
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    return analytics_service.get_recent(db, user.id)


@router.get("/game/{game_id}", response_model=GameDetail)
def get_game_detail(
    game_id: int,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    detail = analytics_service.get_game_detail(db, game_id, user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="Game not found")
    return detail
