"""
Game session API routes — live playable poker + solver-prep endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_user
from app.models import UserModel
from app.game_sessions import service
from app.game_sessions.schemas import (
    CreateSessionRequest,
    SessionState,
    TakeActionRequest,
    HandRecord,
)

router = APIRouter(prefix="/api/play", tags=["play"])


@router.post("/session", response_model=SessionState)
def create_session(
    req: CreateSessionRequest,
    db: Session = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Create a new game session and deal the first hand."""
    try:
        return service.create_session(
            db,
            starting_stack=req.startingStack,
            hero_position=req.heroPosition,
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session/{session_id}", response_model=SessionState)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get current state of a game session."""
    try:
        return service.get_session_state(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/action", response_model=SessionState)
def take_action(
    req: TakeActionRequest,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Take an action in the current hand."""
    try:
        return service.take_action(db, req.sessionId, req.actionType, req.amount)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/next-hand/{session_id}", response_model=SessionState)
def next_hand(
    session_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Deal a new hand within the same session."""
    try:
        return service.next_hand(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{session_id}", response_model=list[HandRecord])
def get_history(
    session_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get hand history for a session."""
    try:
        return service.get_hand_history(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Post-hand solver comparison ─────────────────────────────────


class SolverCompareRequest(BaseModel):
    board: list[str]  # 3+ cards
    hero_hand: list[str] = []  # optional
    pot: float = 6.5
    position: str = "IP"  # hero's position
    user_action: str = ""  # optional: the action the user actually took


@router.post("/compare-to-solver")
def compare_to_solver(
    req: SolverCompareRequest,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Compare current hand situation to persisted solver output.

    Searches for a persisted solve matching the board (flop only).
    Returns solver root action frequencies + recommendation summary +
    deviation classification if user_action is provided.

    HONEST NOTE: This only works for scenarios that exactly match
    a persisted solve's board. It is NOT a real-time solver.
    """
    from app.models import SolveResultModel
    from app.services.i18n import (
        generate_recommendation_summary_ru as generate_recommendation_summary,
        classify_deviation_ru as classify_deviation,
        get_quality_label_ru as get_quality_label,
    )

    if len(req.board) < 3:
        return {
            "match_quality": "unsupported",
            "message": "Solver comparison requires at least 3 board cards (flop).",
            "solver_data": None,
        }

    flop = sorted(req.board[:3])

    # Search persisted solves for matching board
    solves = db.query(SolveResultModel).filter(
        SolveResultModel.status == "done",
    ).order_by(SolveResultModel.created_at.desc()).limit(50).all()

    best_match = None
    for solve in solves:
        config = solve.config_json or {}
        solve_board = sorted(config.get("board", [])[:3])
        if solve_board == flop:
            best_match = solve
            break

    if not best_match:
        board_str = " ".join(req.board[:3])
        return {
            "match_quality": "unsupported",
            "message": (
                f"Солвер ещё не рассчитал борд {board_str}."
            ),
            "explanation": (
                "Чтобы сравнить свою игру с солвером, "
                "нужен расчёт именно для этого флопа. "
                "Откройте Солвер и запустите расчёт."
            ),
            "board_for_solver": board_str,
            "solver_data": None,
        }

    # Get root summary
    root_summary = best_match.root_strategy_summary_json or {}
    combo_data = best_match.combo_strategies_json or {}
    root_combos = combo_data.get("node_0", {})

    # If hero hand matches a specific combo, show combo-level data
    hero_combo_data = None
    hero_combo_key = None
    if req.hero_hand and len(req.hero_hand) >= 2:
        hero_key = "".join(req.hero_hand[:2])
        hero_combo_data = root_combos.get(hero_key)
        hero_combo_key = hero_key
        # Try reversed
        if not hero_combo_data:
            hero_key_rev = req.hero_hand[1] + req.hero_hand[0]
            hero_combo_data = root_combos.get(hero_key_rev)
            if hero_combo_data:
                hero_combo_key = hero_key_rev

    config = best_match.config_json or {}

    # Choose the best available frequencies for analysis
    analysis_freqs = hero_combo_data or root_summary

    # Phase 8B: Generate recommendation summary
    recommendation_summary = generate_recommendation_summary(analysis_freqs)

    # Phase 8B: Classify deviation if user_action provided
    deviation = None
    quality_label = None
    if req.user_action and analysis_freqs:
        deviation = classify_deviation(req.user_action, analysis_freqs)
        quality_label = get_quality_label(deviation["label"])

    # Build human-readable explanation
    # Action name localization
    ACTION_RU = {
        "check": "чек", "fold": "пас", "call": "колл",
        "bet": "ставка", "raise": "рейз", "allin": "олл-ин",
    }

    def ru_action(a: str) -> str:
        return ACTION_RU.get(a.lower(), a)

    if hero_combo_data:
        best_action = max(hero_combo_data, key=hero_combo_data.get)
        best_freq = hero_combo_data[best_action]
        sorted_actions = sorted(hero_combo_data.items(), key=lambda x: x[1], reverse=True)
        action_parts = [f"{ru_action(a)} {f*100:.0f}%" for a, f in sorted_actions]
        explanation = (
            f"Для вашей руки ({hero_combo_key}) солвер рекомендует: "
            f"{', '.join(action_parts)}. "
            f"Основное действие — {ru_action(best_action)} ({best_freq*100:.0f}%)."
        )
        data_depth = "частоты для конкретной руки (максимальное качество)"
    elif root_summary:
        best_action = max(root_summary, key=root_summary.get)
        best_freq = root_summary[best_action]
        sorted_actions = sorted(root_summary.items(), key=lambda x: x[1], reverse=True)
        action_parts = [f"{ru_action(a)} {f*100:.0f}%" for a, f in sorted_actions]
        explanation = (
            f"Точных данных для вашей комбинации нет. "
            f"Средняя стратегия солвера: {', '.join(action_parts)}. "
            f"Основное действие — {ru_action(best_action)} ({best_freq*100:.0f}%)."
        )
        data_depth = "средние частоты (вашей комбинации нет в расчёте)"
    else:
        explanation = "Данные солвера найдены, но частоты стратегий недоступны."
        data_depth = "только метаданные"

    # Generate learning takeaway
    learning_takeaway = None
    if analysis_freqs:
        best_a = max(analysis_freqs, key=analysis_freqs.get)
        best_f = analysis_freqs[best_a]
        if best_f >= 0.8:
            learning_takeaway = (
                f"В этой ситуации солвер почти всегда делает {ru_action(best_a)} "
                f"({best_f*100:.0f}%). Это чистое решение."
            )
        elif best_f >= 0.5:
            second_actions = sorted(
                [(a, f) for a, f in analysis_freqs.items() if a != best_a],
                key=lambda x: x[1], reverse=True
            )
            if second_actions:
                learning_takeaway = (
                    f"Солвер предпочитает {ru_action(best_a)} ({best_f*100:.0f}%), "
                    f"но иногда делает {ru_action(second_actions[0][0])} "
                    f"({second_actions[0][1]*100:.0f}%). Важна гибкость."
                )
        else:
            learning_takeaway = (
                f"Здесь нет единственно правильного действия — солвер "
                f"смешивает несколько вариантов. Это нормально."
            )

    street_label = (best_match.street_depth or "flop_only").replace("_", " ")

    # ── Phase 8J: Hand narrative + user action label + next steps ──
    CARD_SUIT_RU = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
    def card_display(c: str) -> str:
        rank = c[0].upper() if c[0] != 'T' else '10'
        suit = CARD_SUIT_RU.get(c[1], c[1]) if len(c) > 1 else ""
        return f"{rank}{suit}"

    board_display = " ".join(card_display(c) for c in req.board[:3])
    hand_narrative = f"Флоп: {board_display} • Банк: {req.pot:.1f}ББ"
    if len(req.board) >= 4:
        hand_narrative = f"Тёрн: {board_display} {card_display(req.board[3])} • Банк: {req.pot:.1f}ББ"
    if len(req.board) >= 5:
        hand_narrative = f"Ривер: {' '.join(card_display(c) for c in req.board)} • Банк: {req.pot:.1f}ББ"
    if req.hero_hand and len(req.hero_hand) >= 2:
        hero_display = " ".join(card_display(c) for c in req.hero_hand[:2])
        hand_narrative += f" • Ваша рука: {hero_display}"

    user_action_ru = ru_action(req.user_action) if req.user_action else None

    # Next-step learning actions
    board_str_for_link = " ".join(req.board[:3])
    board_display = " ".join(card_display(c) for c in req.board[:3])
    spot_label = f"Флоп {board_display}"
    next_steps = [
        {
            "id": "drill",
            "label": "Потренировать этот тип спота",
            "icon": "🎯",
            "route": "/drill",
            "solve_id": best_match.id,
            "board": req.board[:3],
            "board_display": board_display,
            "spot_label": spot_label,
        },
        {
            "id": "explore",
            "label": "Изучить стратегию подробнее",
            "icon": "🔍",
            "route": "/explore",
            "solve_id": best_match.id,
            "board": req.board[:3],
            "board_display": board_display,
            "spot_label": spot_label,
        },
        {
            "id": "solver",
            "label": "Открыть солвер с этим бордом",
            "icon": "🧮",
            "route": f"/solver?board={board_str_for_link}",
        },
    ]

    return {
        "match_quality": "exact_board_match" if hero_combo_data else "board_match_summary_only",
        "solve_id": best_match.id,
        "board": config.get("board", []),
        "ip_range": config.get("ip_range", ""),
        "oop_range": config.get("oop_range", ""),
        "root_summary": root_summary,
        "hero_combo_data": hero_combo_data,
        "hero_combo_key": hero_combo_key,
        "trust_grade": best_match.trust_grade or "",
        "exploitability_mbb": best_match.exploitability_mbb,
        "iterations": best_match.iterations,
        "converged": best_match.converged,
        "scope": f"{street_label}, хедз-ап постфлоп, фиксированные размеры ставок",
        "street_depth": best_match.street_depth or "flop_only",
        "data_depth": data_depth,
        "explanation": explanation,
        "recommendation_summary": recommendation_summary,
        "deviation": deviation,
        "quality_label": quality_label,
        "learning_takeaway": learning_takeaway,
        "hand_narrative": hand_narrative,
        "user_action_ru": user_action_ru,
        "next_steps": next_steps,
        "message": (
            f"Найдено совпадение. Показаны частоты действий солвера. "
            f"Это реальный CFR+ расчёт, ограниченный подигрой: {street_label}."
        ),
        "honest_note": (
            f"Сравнение на основе сохранённого расчёта для совпадающего борда. "
            f"Показаны только корневые частоты. "
            f"Область: {street_label}, хедз-ап, фиксированные ставки."
        ),
    }


# ── Solver-prep endpoints ──────────────────────────────────────


class RangeParseRequest(BaseModel):
    range_str: str


class RangeParseResponse(BaseModel):
    valid: bool
    error: str = ""
    hands: list[str] = []
    count: int = 0
    combos: int = 0
    pct: float = 0.0


@router.post("/range/parse", response_model=RangeParseResponse)
def parse_range_endpoint(
    req: RangeParseRequest,
    _user: UserModel = Depends(get_current_user),
):
    """
    Parse and validate a preflop range string.

    Examples: "AA,KK,QQ", "TT+", "AKs,AQs+", "76s-54s"
    Returns combo count and percentage of all possible starting hands.
    """
    from app.poker_engine.ranges import parse_range, validate_range

    valid, error = validate_range(req.range_str)
    if not valid:
        return RangeParseResponse(valid=False, error=error)

    parsed = parse_range(req.range_str)
    return RangeParseResponse(
        valid=True,
        hands=sorted(parsed.hands),
        count=parsed.count,
        combos=parsed.combos,
        pct=round(parsed.pct, 2),
    )


class TreeInfoRequest(BaseModel):
    board: list[str] = []
    ip_range: str = ""
    oop_range: str = ""
    starting_pot: float = 6.5
    effective_stack: float = 97.0


class TreeInfoResponse(BaseModel):
    total_nodes: int
    action_nodes: int
    terminal_nodes: int
    chance_nodes: int
    max_depth: int
    ip_range_combos: int
    oop_range_combos: int
    message: str = ""


@router.post("/solver/tree-info", response_model=TreeInfoResponse)
def get_tree_info(
    req: TreeInfoRequest,
    _user: UserModel = Depends(get_current_user),
):
    """
    Build a game tree skeleton and return statistics.

    HONEST NOTE: This is a tree-structure scaffold, NOT a solver.
    No equilibrium computation is performed. This shows the shape
    of the game tree that a real solver would traverse.
    """
    from app.solver.tree_builder import TreeConfig, build_tree_skeleton

    config = TreeConfig(
        ip_range_str=req.ip_range,
        oop_range_str=req.oop_range,
        board=tuple(req.board),
        starting_pot=req.starting_pot,
        effective_stack=req.effective_stack,
    )

    _, stats = build_tree_skeleton(config)

    return TreeInfoResponse(
        total_nodes=stats.total_nodes,
        action_nodes=stats.action_nodes,
        terminal_nodes=stats.terminal_nodes,
        chance_nodes=stats.chance_nodes,
        max_depth=stats.max_depth,
        ip_range_combos=stats.ip_range_combos,
        oop_range_combos=stats.oop_range_combos,
        message="SCAFFOLD: Game tree statistics only, no solving performed.",
    )

