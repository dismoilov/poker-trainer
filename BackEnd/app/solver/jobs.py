"""
Solver job runner — refactored to use the StrategyProvider interface.

HONEST NOTE: In Phase 1, all jobs use the HeuristicProvider.
The job pipeline is now structured so that swapping in a RealSolverProvider
requires only changing the provider selection logic, not the job runner itself.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import JobModel, JobLogModel, NodeModel, SpotModel
from app.solver.base import StrategyProvider, ProviderType
from app.solver.heuristic_provider import HeuristicProvider
from app.services.strategy import save_strategy

logger = logging.getLogger(__name__)


def get_provider_for_job(job_type: str = "solve") -> StrategyProvider:
    """
    Select the appropriate strategy provider for a job.

    Phase 1: Always returns HeuristicProvider.
    Future: Could select RealSolverProvider based on job_type or config.
    """
    # Phase 1: heuristic only
    return HeuristicProvider()


async def run_strategy_generation(job_id: str, spot_id: str) -> None:
    """
    Background task: generate strategy matrices for all nodes in a spot.

    Uses the StrategyProvider interface, so the actual generation method
    is determined by get_provider_for_job().
    """
    logger.info("Starting strategy generation job %s for spot %s", job_id, spot_id)
    db = SessionLocal()
    try:
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()
        _add_log(db, job_id, "Запущено — используется эвристический провайдер")

        provider = get_provider_for_job()
        provider_label = (
            "heuristic frequency tables"
            if provider.provider_type == ProviderType.HEURISTIC
            else "real solver"
        )
        _add_log(db, job_id, f"Провайдер: {provider_label}")

        nodes = db.query(NodeModel).filter(NodeModel.spot_id == spot_id).all()
        total = len(nodes)

        for idx, node in enumerate(nodes):
            await asyncio.sleep(0.3)  # Simulate processing time

            strategy = provider.generate_strategy(node.id, node.actions)
            save_strategy(db, node.id, strategy)

            progress = int((idx + 1) / total * 100)
            job = db.query(JobModel).filter(JobModel.id == job_id).first()
            if job:
                job.progress = progress
                db.commit()
            _add_log(db, job_id, f"Узел {node.id} обработан ({progress}%)")
            logger.info("Job %s: %s done (%d%%)", job_id, node.id, progress)

        # Mark complete
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "done"
            job.progress = 100
            db.commit()
        _add_log(db, job_id, "Готово — эвристические стратегии сгенерированы")

        spot = db.query(SpotModel).filter(SpotModel.id == spot_id).first()
        if spot:
            spot.solved = True
            db.commit()

        logger.info("Job %s completed (provider: %s).", job_id, provider_label)

    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        job = db.query(JobModel).filter(JobModel.id == job_id).first()
        if job:
            job.status = "failed"
            db.commit()
        _add_log(db, job_id, f"Ошибка: {str(e)}")
    finally:
        db.close()


def _add_log(db: Session, job_id: str, message: str) -> None:
    db.add(JobLogModel(job_id=job_id, message=message))
    db.commit()
