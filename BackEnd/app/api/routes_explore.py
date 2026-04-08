"""Explore API routes — nodes, strategy, and hand detail (auth-protected)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import TreeNode, HandDetail
from app.security import get_current_user
from app.models import UserModel
from app.services import nodes as nodes_service
from app.services.strategy import get_or_create_strategy
from app.services.gto_data import get_hand_tier, hand_connects_with_board, BOARD_TEXTURES
from app.services.explanations import generate_explanation

router = APIRouter(prefix="/api/explore", tags=["explore"])

TIER_LABELS = {
    1: "Premium (Top 3%)",
    2: "Strong (Top 8%)",
    3: "Good (Top 15%)",
    4: "Playable (Top 25%)",
    5: "Marginal (Top 35%)",
    6: "Speculative (Top 45%)",
    7: "Weak (Top 55%)",
    8: "Trash (Bottom 45%)",
}


@router.get("/nodes", response_model=list[TreeNode])
def get_nodes(
    spotId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    return nodes_service.get_nodes_by_spot(db, spotId)


@router.get("/node", response_model=TreeNode)
def get_node(
    spotId: str = Query(...),
    nodeId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")
    return node


@router.get("/strategy")
def get_strategy(
    nodeId: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")
    actions = [a.model_dump() for a in node.actions]
    return get_or_create_strategy(db, nodeId, actions)


@router.get("/hand-detail", response_model=HandDetail)
def get_hand_detail(
    nodeId: str = Query(...),
    hand: str = Query(...),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get detailed strategy breakdown for a specific hand in a node."""
    node = nodes_service.get_node_by_id(db, nodeId)
    if not node:
        raise HTTPException(status_code=404, detail=f"Node not found: {nodeId}")

    actions = [a.model_dump() for a in node.actions]
    strategy = get_or_create_strategy(db, nodeId, actions)
    frequencies = strategy.get(hand, {})

    tier = get_hand_tier(hand)
    tier_label = TIER_LABELS.get(tier, f"Tier {tier}")

    # Use a sample board for connection analysis
    import random
    sample_board = random.choice(BOARD_TEXTURES)["board"]
    connection = hand_connects_with_board(hand, sample_board)

    # Find correct action
    correct_action = max(frequencies, key=frequencies.get) if frequencies else ""

    # Get spot format
    from app.models import SpotModel
    spot = db.query(SpotModel).filter(SpotModel.id == node.spotId).first()
    pot_type = spot.format if spot else "SRP"

    explanation = generate_explanation(
        hand=hand,
        board=sample_board,
        chosen_action=correct_action,
        correct_action=correct_action,
        frequencies=frequencies,
        position=node.player,
        line_description=node.lineDescription,
        pot_type=pot_type,
    )

    # Phase 8B: Recommendation summary + node context
    from app.services.i18n import (
        generate_recommendation_summary_ru as generate_recommendation_summary,
        generate_node_context_ru as generate_node_context,
    )
    recommendation_summary = generate_recommendation_summary(frequencies)
    node_context = generate_node_context(
        player=node.player,
        street=node.street or "flop",
        line_description=node.lineDescription or "",
        pot_size=node.pot or 0.0,
        stack_size=spot.stack if spot else 100.0,
    )

    return HandDetail(
        hand=hand,
        tier=tier,
        tierLabel=tier_label,
        frequencies=frequencies,
        connection=connection,
        explanation=explanation,
        recommendation_summary=recommendation_summary,
        node_context=node_context,
        data_source_label="Heuristic GTO Data",
    )


@router.get("/solver-compare")
def compare_heuristic_vs_solver(
    solve_id: str = Query(..., description="ID of a completed solve result"),
    node_id: str = Query(default="node_0", description="Node to compare (default: root)"),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Compare heuristic strategy vs real-solved strategy at a given node.

    Returns both strategies side-by-side with clear labeling.
    This is a LIMITED but REAL bridge from solver results into the trainer.

    HONEST NOTE:
    - Heuristic strategy is a 169-hand matrix (AA, AKs, AKo, ... 22)
    - Solver strategy is per-combo (AhAs, AhAd, etc.) at fewer combos
    - They are NOT directly comparable cell-by-cell
    - This shows the aggregate action frequencies for educational comparison
    """
    from app.models import SolveResultModel
    from app.api.routes_solver import _solve_jobs

    # Get persisted solve result
    solve = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if not solve:
        raise HTTPException(status_code=404, detail=f"Solve result not found: {solve_id}")

    if solve.status not in ("done", "timeout", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Solve not complete (status: {solve.status})")

    # Get solver root strategy summary (from persisted summaries)
    node_summaries = solve.node_summaries_json or {}
    solver_summary = node_summaries.get(node_id, {})

    if not solver_summary and solve.root_strategy_summary_json and node_id == "node_0":
        solver_summary = solve.root_strategy_summary_json

    # Also check in-memory for full data
    full_combo_data = None
    job = _solve_jobs.get(solve_id)
    if job and job.get("result"):
        result = job["result"]
        node_strats = result.strategies.get(node_id, {})
        if node_strats:
            full_combo_data = node_strats
            # Recompute summary from full data
            action_totals = {}
            count = len(node_strats)
            for combo_str, freqs in node_strats.items():
                for action, freq in freqs.items():
                    action_totals[action] = action_totals.get(action, 0.0) + freq
            solver_summary = {a: round(t / count, 4) for a, t in action_totals.items()}

    if not solver_summary:
        raise HTTPException(
            status_code=404,
            detail=f"No solver strategy found for node '{node_id}' in solve '{solve_id}'"
        )

    # Generate heuristic strategy for comparison
    # Use the same actions that the solver had
    heuristic_actions = [
        {"id": action, "label": action.replace("_", " ").title(), "type": "bet"}
        for action in solver_summary.keys()
    ]

    from app.services.strategy import generate_strategy
    heuristic_matrix = generate_strategy("compare-" + node_id, heuristic_actions)

    # Compute heuristic aggregate
    heuristic_totals = {}
    for hand, freqs in heuristic_matrix.items():
        for action, freq in freqs.items():
            heuristic_totals[action] = heuristic_totals.get(action, 0.0) + freq
    heuristic_summary = {
        a: round(t / len(heuristic_matrix), 4) for a, t in heuristic_totals.items()
    }

    return {
        "solve_id": solve_id,
        "node_id": node_id,
        "solver_strategy": {
            "label": "Real CFR+ Solver",
            "summary": solver_summary,
            "scope": "flop-only subgame, per-concrete-combo",
            "trust_level": "demo — limited but real equilibrium approximation",
            "full_combo_available": full_combo_data is not None,
            "combo_count": len(full_combo_data) if full_combo_data else 0,
        },
        "heuristic_strategy": {
            "label": "Heuristic (Tier-Based Lookup)",
            "summary": heuristic_summary,
            "scope": "169-hand categories, all streets",
            "trust_level": "approximation — NOT a real solver",
        },
        "comparison_note": (
            "These strategies are computed differently and are not directly comparable. "
            "The solver uses real CFR+ on concrete combos for a specific board; "
            "the heuristic uses hand-tier lookup tables with board-texture adjustments."
        ),
        "config": solve.config_json,
    }


@router.get("/solver-backed")
def get_solver_backed_strategy(
    solve_id: str = Query(..., description="ID of a completed solve result"),
    node_id: str = Query(default="node_0", description="Node to retrieve"),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Get solver-backed strategy for display in Explore mode.

    Returns per-combo frequencies from persisted solver data if available,
    otherwise returns summary. Always includes trust grade and scope.

    HONEST NOTE: This is real solver data, but limited to
    flop-only, HU postflop, fixed bet sizes. Not full NLHE.
    """
    from app.models import SolveResultModel

    solve = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if not solve:
        raise HTTPException(status_code=404, detail=f"Solve not found: {solve_id}")

    if solve.status != "done":
        raise HTTPException(status_code=400, detail=f"Solve not complete: {solve.status}")

    # Try combo data first, then summary
    combo_data = solve.combo_strategies_json or {}
    node_combos = combo_data.get(node_id)
    node_summary = (solve.node_summaries_json or {}).get(node_id)

    if node_id == "node_0" and not node_summary:
        node_summary = solve.root_strategy_summary_json

    if not node_combos and not node_summary:
        raise HTTPException(status_code=404, detail=f"No data for node: {node_id}")

    # Build action frequency matrix for display
    data_source = "persisted_combo_subset" if node_combos else "persisted_summary_only"

    config = solve.config_json or {}

    return {
        "solve_id": solve_id,
        "node_id": node_id,
        "data_source": data_source,
        "combos": node_combos or {},
        "combo_count": len(node_combos) if node_combos else 0,
        "summary": node_summary or _summarize_combos(node_combos) if node_combos else (node_summary or {}),
        "available_nodes": list(combo_data.keys()),
        "all_summary_nodes": list((solve.node_summaries_json or {}).keys()),
        "config": config,
        "board": config.get("board", []),
        "ip_range": config.get("ip_range", ""),
        "oop_range": config.get("oop_range", ""),
        "iterations": solve.iterations,
        "converged": solve.converged,
        "elapsed_seconds": solve.elapsed_seconds,
        "trust_grade": solve.trust_grade or "",
        "exploitability_mbb": solve.exploitability_mbb,
        "street_depth": solve.street_depth or "flop_only",
        "scope": f"{(solve.street_depth or 'flop_only').replace('_', ' ')}, HU postflop, fixed bet sizes",
        "data_depth": (
            "per-combo frequencies" if node_combos
            else "aggregate action frequencies only"
        ),
        "honest_note": (
            f"Real CFR+ solver output. Limited to {(solve.street_depth or 'flop_only').replace('_', ' ')} subgames "
            "with fixed bet sizes. NOT full NLHE equilibrium."
        ),
    }


@router.get("/solver-nodes")
def get_solver_node_tree(
    solve_id: str = Query(..., description="ID of a completed solve result"),
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Get browsable node tree from a persisted solve.

    Returns all nodes with data availability indicators so the frontend
    can show which nodes have per-combo data vs summary-only vs unavailable.
    """
    from app.models import SolveResultModel

    solve = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if not solve:
        raise HTTPException(status_code=404, detail=f"Solve not found: {solve_id}")

    combo_data = solve.combo_strategies_json or {}
    node_summaries = solve.node_summaries_json or {}
    config = solve.config_json or {}

    # Build node list with data availability
    all_node_ids = sorted(set(list(combo_data.keys()) + list(node_summaries.keys())))

    # Add root if it has root_strategy_summary but isn't in node_summaries
    if "node_0" not in all_node_ids and solve.root_strategy_summary_json:
        all_node_ids.insert(0, "node_0")

    nodes = []
    for nid in all_node_ids:
        has_combos = nid in combo_data
        has_summary = nid in node_summaries or (nid == "node_0" and solve.root_strategy_summary_json)
        summary = node_summaries.get(nid) or (
            solve.root_strategy_summary_json if nid == "node_0" else None
        )

        # Derive action labels from summary keys
        actions = list(summary.keys()) if summary else []

        # Derive depth from node ID pattern (node_0 = depth 0, node_1 = depth 1, etc.)
        depth = 0
        if nid != "node_0":
            parts = nid.replace("node_", "").split("_")
            depth = len(parts)

        nodes.append({
            "node_id": nid,
            "has_combo_data": has_combos,
            "has_summary": has_summary,
            "combo_count": len(combo_data.get(nid, {})),
            "actions": actions,
            "depth": depth,
            "data_quality": (
                "per_combo" if has_combos
                else "summary_only" if has_summary
                else "unavailable"
            ),
        })

    return {
        "solve_id": solve_id,
        "board": config.get("board", []),
        "ip_range": config.get("ip_range", ""),
        "oop_range": config.get("oop_range", ""),
        "iterations": solve.iterations,
        "converged": solve.converged,
        "elapsed_seconds": solve.elapsed_seconds,
        "trust_grade": solve.trust_grade or "",
        "exploitability_mbb": solve.exploitability_mbb,
        "total_nodes": len(nodes),
        "nodes": nodes,
        "street_depth": solve.street_depth or "flop_only",
        "scope": f"{(solve.street_depth or 'flop_only').replace('_', ' ')}, HU postflop, fixed bet sizes",
    }


def _summarize_combos(combos: dict) -> dict:
    """Summarize combo-level data into action frequencies."""
    if not combos:
        return {}
    action_totals = {}
    for freqs in combos.values():
        for action, freq in freqs.items():
            action_totals[action] = action_totals.get(action, 0.0) + freq
    count = len(combos)
    return {a: round(t / count, 4) for a, t in action_totals.items()}

