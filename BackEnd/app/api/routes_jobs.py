"""Jobs API routes (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import JobCreateRequest, Job
from app.security import get_current_user
from app.models import UserModel
from app.services import jobs as jobs_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[Job])
def list_jobs(
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    return jobs_service.get_all_jobs(db)


@router.post("/solve", response_model=Job)
async def create_solve_job(
    req: JobCreateRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    try:
        return jobs_service.create_solve_job(db, req.spotId, user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
