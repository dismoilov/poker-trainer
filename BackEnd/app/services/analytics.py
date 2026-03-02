"""Analytics service — summary, history, recent, game detail (per-user)."""

from datetime import datetime, timedelta
import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import DrillAnswerModel, NodeModel
from app.schemas import AnalyticsSummary, AnalyticsRow, AnalyticsQuestion, GameDetail
from app.services.strategy import get_or_create_strategy
from app.services.explanations import generate_explanation
from app.services.gto_data import get_hand_tier


def get_summary(db: Session, user_id: int) -> AnalyticsSummary:
    base = db.query(DrillAnswerModel).filter(DrillAnswerModel.user_id == user_id)
    total_q = base.count()
    avg_ev = db.query(func.avg(DrillAnswerModel.ev_loss)).filter(
        DrillAnswerModel.user_id == user_id
    ).scalar() or 0.0
    avg_acc = db.query(func.avg(DrillAnswerModel.accuracy)).filter(
        DrillAnswerModel.user_id == user_id
    ).scalar() or 0.0

    total_sessions = _count_sessions(db, user_id)

    return AnalyticsSummary(
        totalSessions=total_sessions,
        totalQuestions=total_q,
        avgEvLoss=round(float(avg_ev), 2),
        accuracy=round(float(avg_acc), 2),
    )


def _count_sessions(db: Session, user_id: int) -> int:
    timestamps = (
        db.query(DrillAnswerModel.created_at)
        .filter(DrillAnswerModel.user_id == user_id)
        .order_by(DrillAnswerModel.created_at)
        .all()
    )
    if not timestamps:
        return 0
    sessions = 1
    prev = timestamps[0][0]
    for (ts,) in timestamps[1:]:
        if ts and prev and (ts - prev).total_seconds() > 1800:
            sessions += 1
        prev = ts
    return sessions


def get_history(db: Session, user_id: int) -> list[AnalyticsRow]:
    cutoff = datetime.utcnow() - timedelta(days=90)
    rows = (
        db.query(
            func.date(DrillAnswerModel.created_at).label("day"),
            func.avg(DrillAnswerModel.ev_loss).label("avg_ev"),
            func.avg(DrillAnswerModel.accuracy).label("avg_acc"),
            func.count(DrillAnswerModel.id).label("cnt"),
        )
        .filter(
            DrillAnswerModel.user_id == user_id,
            DrillAnswerModel.created_at >= cutoff,
        )
        .group_by(func.date(DrillAnswerModel.created_at))
        .order_by(func.date(DrillAnswerModel.created_at))
        .all()
    )
    return [
        AnalyticsRow(
            date=str(r.day),
            evLoss=round(float(r.avg_ev), 2),
            accuracy=round(float(r.avg_acc), 2),
            questions=int(r.cnt),
        )
        for r in rows
    ]


def get_recent(db: Session, user_id: int) -> list[AnalyticsQuestion]:
    rows = (
        db.query(DrillAnswerModel)
        .filter(DrillAnswerModel.user_id == user_id)
        .order_by(DrillAnswerModel.created_at.desc())
        .limit(50)
        .all()
    )
    results = []
    for r in rows:
        # Get node for position and line description
        node = db.query(NodeModel).filter(NodeModel.id == r.node_id).first()

        results.append(AnalyticsQuestion(
            id=str(r.id),
            spotName=r.spot_name or "",
            spotId=r.spot_id,
            nodeId=r.node_id,
            board=r.board or [],
            hand=r.hand,
            position=node.player if node else "",
            chosenAction=r.chosen_action,
            correctAction=r.correct_action,
            evLoss=round(r.ev_loss, 2),
            accuracy=round(r.accuracy, 2),
            lineDescription=node.line_description if node else "",
            date=r.created_at.isoformat() if r.created_at else "",
        ))
    return results


def get_game_detail(db: Session, game_id: int, user_id: int) -> GameDetail | None:
    """Get full detail for a single drill answer, including regenerated explanations."""
    r = (
        db.query(DrillAnswerModel)
        .filter(DrillAnswerModel.id == game_id, DrillAnswerModel.user_id == user_id)
        .first()
    )
    if not r:
        return None

    node = db.query(NodeModel).filter(NodeModel.id == r.node_id).first()

    # Get strategy frequencies for this hand
    frequencies: dict[str, float] = {}
    if node:
        strategy = get_or_create_strategy(db, r.node_id, node.actions)
        frequencies = strategy.get(r.hand, {})

    # Get spot format for explanation
    from app.models import SpotModel
    spot = db.query(SpotModel).filter(SpotModel.id == r.spot_id).first()
    pot_type = spot.format if spot else "SRP"

    # Generate explanations
    explanation = generate_explanation(
        hand=r.hand,
        board=r.board or [],
        chosen_action=r.chosen_action,
        correct_action=r.correct_action,
        frequencies=frequencies,
        position=node.player if node else "",
        line_description=node.line_description if node else "",
        pot_type=pot_type,
    )

    return GameDetail(
        id=str(r.id),
        spotName=r.spot_name or "",
        spotId=r.spot_id,
        nodeId=r.node_id,
        board=r.board or [],
        hand=r.hand,
        position=node.player if node else "",
        chosenAction=r.chosen_action,
        correctAction=r.correct_action,
        evLoss=round(r.ev_loss, 2),
        accuracy=round(r.accuracy, 2),
        lineDescription=node.line_description if node else "",
        date=r.created_at.isoformat() if r.created_at else "",
        frequencies=frequencies,
        explanation=explanation,
    )
