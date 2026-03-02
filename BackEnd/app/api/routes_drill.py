"""Drill API routes (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DrillNextRequest, DrillQuestion, DrillAnswerRequest, DrillFeedback
from app.security import get_current_user
from app.models import UserModel
from app.services import drill as drill_service

router = APIRouter(prefix="/api/drill", tags=["drill"])


@router.post("/next", response_model=DrillQuestion)
def get_next_question(
    req: DrillNextRequest,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    try:
        return drill_service.generate_question(db, req.spotId, req.nodeId)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/answer", response_model=DrillFeedback)
def submit_answer(
    req: DrillAnswerRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    try:
        return drill_service.process_answer(
            db, req.nodeId, req.hand, req.actionId, req.questionId, user_id=user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
