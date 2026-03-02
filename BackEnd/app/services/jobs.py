"""Jobs service — create and manage solve jobs with background tasks."""

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import JobModel, JobLogModel, NodeModel, SpotModel
from app.schemas import Job
from app.services.strategy import generate_strategy, save_strategy

logger = logging.getLogger(__name__)


def _to_schema(m: JobModel, db: Session) -> Job:
    logs = (
        db.query(JobLogModel.message)
        .filter(JobLogModel.job_id == m.id)
        .order_by(JobLogModel.ts)
        .all()
    )
    return Job(
        id=m.id,
        type=m.type,
        spotId=m.spot_id,
        spotName=m.spot_name,
        status=m.status,
        progress=m.progress,
        createdAt=m.created_at.isoformat() if m.created_at else "",
        log=[row[0] for row in logs],
    )


def _add_log(db: Session, job_id: str, message: str):
    db.add(JobLogModel(job_id=job_id, message=message))
    db.commit()


def get_all_jobs(db: Session) -> list[Job]:
    rows = db.query(JobModel).order_by(JobModel.created_at.desc()).all()
    return [_to_schema(r, db) for r in rows]


def create_solve_job(db: Session, spot_id: str, user_id: int | None = None) -> Job:
    spot = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
    if not spot:
        raise ValueError(f"Spot not found: {spot_id}")

    job = JobModel(
        id=f"job-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        type="solve",
        spot_id=spot_id,
        spot_name=spot.name,
        status="pending",
        progress=0,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    _add_log(db, job.id, "В очереди")

    # Launch background task (graceful fallback for sync test context)
    try:
        asyncio.ensure_future(_run_solve(job.id, spot_id))
    except RuntimeError:
        # No running loop (e.g. in sync tests) — skip background task
        logger.warning("No running event loop, skipping background solve for job %s", job.id)

    return _to_schema(job, db)


async def _run_solve(job_id: str, spot_id: str):
    logger.info("Starting solve job %s for spot %s", job_id, spot_id)
    db = SessionLocal()
    try:
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()
        _add_log(db, job_id, "Запущено")

        nodes = db.query(NodeModel).filter(NodeModel.spot_id == spot_id).all()
        total = len(nodes)

        for idx, node in enumerate(nodes):
            await asyncio.sleep(0.5)
            strategy = generate_strategy(node.id, node.actions)
            save_strategy(db, node.id, strategy)

            progress = int((idx + 1) / total * 100)
            job = db.query(JobModel).filter(JobModel.id == job_id).first()
            if job:
                job.progress = progress
                db.commit()
            _add_log(db, job_id, f"Узел {node.id} обработан ({progress}%)")
            logger.info("Job %s: %s done (%d%%)", job_id, node.id, progress)

        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "done"
            job.progress = 100
            db.commit()
        _add_log(db, job_id, "Готово")

        spot = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
        if spot:
            spot.solved = True
            db.commit()

        logger.info("Job %s completed.", job_id)

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "failed"
            db.commit()
        _add_log(db, job_id, f"Ошибка: {str(e)}")
    finally:
        db.close()
