"""Drill API routes (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


# ── Solver-backed drill ─────────────────────────────────────────


class SolverDrillRequest(BaseModel):
    solve_id: str | None = None


class SolverDrillAnswerReq(BaseModel):
    solve_id: str
    node_id: str
    combo: str
    chosen_action: str


@router.post("/solver-drill")
def solver_drill_question(
    req: SolverDrillRequest,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Generate a drill question from real solver data.

    Picks a random combo from a persisted solve and asks "what action?".
    HONEST NOTE: Uses real CFR+ output, limited to flop-only HU postflop.
    """
    import random
    from app.models import SolveResultModel

    if req.solve_id:
        solve = db.query(SolveResultModel).filter(
            SolveResultModel.id == req.solve_id
        ).first()
    else:
        solve = db.query(SolveResultModel).filter(
            SolveResultModel.status == "done",
            SolveResultModel.combo_strategies_json.isnot(None),
        ).order_by(SolveResultModel.created_at.desc()).first()

    if not solve:
        raise HTTPException(status_code=404, detail="No persisted solves with combo data")

    combo_data = solve.combo_strategies_json or {}
    if not combo_data:
        raise HTTPException(status_code=404, detail="Solve has no persisted combo data")

    node_id = random.choice(list(combo_data.keys()))
    node_strats = combo_data[node_id]
    if not node_strats:
        raise HTTPException(status_code=404, detail="No combos in node")

    combo_str = random.choice(list(node_strats.keys()))
    freqs = node_strats[combo_str]
    config = solve.config_json or {}

    # Determine best action for context
    best_action = max(freqs, key=freqs.get) if freqs else ""
    node_summaries = solve.node_summaries_json or {}
    node_summary = node_summaries.get(node_id) or (
        solve.root_strategy_summary_json if node_id == "node_0" else {}
    )

    return {
        "solve_id": solve.id,
        "node_id": node_id,
        "combo": combo_str,
        "board": config.get("board", []),
        "actions": list(freqs.keys()),
        "ip_range": config.get("ip_range", ""),
        "oop_range": config.get("oop_range", ""),
        "pot": config.get("pot", 0),
        "effective_stack": config.get("effective_stack", 0),
        "trust_grade": solve.trust_grade or "",
        "exploitability_mbb": solve.exploitability_mbb,
        "scope": f"{(solve.street_depth or 'flop_only').replace('_', ' ')}, HU postflop, fixed bet sizes",
        "street_depth": solve.street_depth or "flop_only",
        "data_source": "real_cfr_solver",
        "node_label": f"Root" if node_id == "node_0" else node_id.replace("node_", "Node "),
        "data_depth": "per-combo frequencies from persisted CFR+ solve",
        "iterations": solve.iterations,
        "converged": solve.converged,
    }


@router.post("/solver-drill/answer")
def solver_drill_answer(
    req: SolverDrillAnswerReq,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Grade a solver drill answer against real solver frequencies.
    Returns enriched feedback with explanation and accuracy.
    """
    from app.models import SolveResultModel
    from app.services.i18n import (
        generate_recommendation_summary_ru as generate_recommendation_summary,
        classify_deviation_ru as classify_deviation,
        get_quality_label_ru as get_quality_label,
        drill_feedback_ru,
    )

    solve = db.query(SolveResultModel).filter(
        SolveResultModel.id == req.solve_id
    ).first()

    if not solve:
        return {"correct": False, "message": "Solve not found", "solver_frequencies": {}}

    combo_data = solve.combo_strategies_json or {}
    node_combos = combo_data.get(req.node_id, {})
    freqs = node_combos.get(req.combo, {})

    if not freqs:
        return {"correct": False, "message": "Combo not found", "solver_frequencies": {}}

    best_action = max(freqs, key=freqs.get)
    chosen_freq = freqs.get(req.chosen_action, 0.0)
    best_freq = freqs[best_action]
    is_correct = req.chosen_action == best_action
    is_acceptable = chosen_freq >= 0.2

    # Compute accuracy: how close to optimal
    accuracy_pct = round(chosen_freq / best_freq * 100, 1) if best_freq > 0 else 0.0

    # Phase 8B: Recommendation summary + deviation classification
    recommendation_summary = generate_recommendation_summary(freqs)
    deviation = classify_deviation(req.chosen_action, freqs)
    quality_label = get_quality_label(deviation["label"])

    # Build structured explanation
    explanation_parts = []
    if is_correct:
        explanation_parts.append(
            f"Correct! The solver plays {best_action} at {best_freq*100:.0f}% frequency."
        )
    elif is_acceptable:
        explanation_parts.append(
            f"Acceptable. Your action ({req.chosen_action}) has {chosen_freq*100:.0f}% solver frequency — "
            f"a mixed strategy. The primary action is {best_action} at {best_freq*100:.0f}%."
        )
    else:
        explanation_parts.append(
            f"Incorrect. The solver strongly prefers {best_action} ({best_freq*100:.0f}%). "
            f"Your choice ({req.chosen_action}) has only {chosen_freq*100:.0f}% frequency."
        )

    # Add breakdown of all actions
    sorted_freqs = sorted(freqs.items(), key=lambda x: x[1], reverse=True)
    breakdown = ", ".join(f"{a}: {f*100:.0f}%" for a, f in sorted_freqs)
    explanation_parts.append(f"Full solver frequencies: {breakdown}.")

    config = solve.config_json or {}

    return {
        "correct": is_correct,
        "acceptable": is_acceptable,
        "chosen_action": req.chosen_action,
        "chosen_frequency": round(chosen_freq, 4),
        "best_action": best_action,
        "best_frequency": round(best_freq, 4),
        "accuracy_pct": accuracy_pct,
        "solver_frequencies": {a: round(f, 4) for a, f in freqs.items()},
        "trust_grade": solve.trust_grade or "",
        "exploitability_mbb": solve.exploitability_mbb,
        "scope": f"{(solve.street_depth or 'flop_only').replace('_', ' ')}, HU postflop, fixed bet sizes",
        "street_depth": solve.street_depth or "flop_only",
        "explanation": explanation_parts,
        "recommendation_summary": recommendation_summary,
        "deviation": deviation,
        "quality_label": quality_label,
        "data_depth_note": (
            "This feedback is based on per-combo solver frequencies "
            "from a persisted CFR+ solve subset. "
            f"Board: {' '.join(config.get('board', []))}."
        ),
        "feedback": (
            f"{quality_label['emoji']} {quality_label['text']}. "
            f"Solver plays {best_action} at {freqs[best_action]*100:.0f}%. "
            f"Your action ({req.chosen_action}) has {chosen_freq*100:.0f}% solver frequency."
        ),
    }
