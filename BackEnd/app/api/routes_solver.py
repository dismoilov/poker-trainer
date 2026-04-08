"""
Solver API routes — real CFR+ solve job management with persistence.

These endpoints manage real solver jobs: creating solves,
polling progress, retrieving results, and persisting solve history.

HONEST NOTE: The solver is real but limited to small flop-only subgames.
Full per-combo strategies are in-memory only; only summaries are persisted.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import get_current_user
from app.models import UserModel, SolveResultModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/solver", tags=["solver"])


# ── In-memory solve job storage (for active jobs + full strategies) ──
# Summaries are also persisted to SQLite on completion.

_solve_jobs: dict[str, dict] = {}

# Phase 18: Concurrent solve protection
_solve_lock = threading.Lock()
_active_solve_id: Optional[str] = None  # Currently running solve job ID
MAX_CONCURRENT_SOLVES = 1  # Single-user beta: only 1 active solve at a time

# Wall-clock timeout for any solve
MAX_SOLVE_WALL_SECONDS = 300
# Estimated seconds per (matchup × iteration) — recalibrated Phase 12A
EST_SECONDS_PER_MATCHUP_ITER = 0.000020
# Max estimated seconds before we reject the job outright
MAX_ESTIMATED_SECONDS = 300
# Stale job expiry (seconds)
STALE_JOB_EXPIRY_SECONDS = 1800  # 30 minutes
# Phase 18: stuck "running" job timeout (10 min without progress = stuck)
STUCK_RUNNING_TIMEOUT_SECONDS = 600


# ── Solver Presets ──────────────────────────────────────────────

SOLVER_PRESETS = {
    "fast": {
        "label": "Быстрый",
        "description": "Быстрый расчёт с базовыми размерами ставок. Хорошо для первого знакомства.",
        "icon": "⚡",
        "bet_sizes": [0.5, 1.0],
        "raise_sizes": [],
        "max_iterations": 100,
        "max_raises": 2,
        "include_turn": False,
        "max_turn_cards": 0,
        "turn_bet_sizes": [],
        "turn_raise_sizes": [],
        "turn_max_raises": 0,
        "est_time_range": "2–10 сек.",
        "complexity": "LIGHT",
    },
    "standard": {
        "label": "Стандартный",
        "description": "Сбалансированный расчёт с 4 размерами ставок и рейзами. Подходит для большинства ситуаций.",
        "icon": "⚖️",
        "bet_sizes": [0.33, 0.5, 0.67, 1.0],
        "raise_sizes": [2.5],
        "max_iterations": 200,
        "max_raises": 2,
        "include_turn": False,
        "max_turn_cards": 0,
        "turn_bet_sizes": [],
        "turn_raise_sizes": [],
        "turn_max_raises": 0,
        "est_time_range": "10–30 сек.",
        "complexity": "MODERATE",
    },
    "deep": {
        "label": "Глубокий",
        "description": "Максимальная точность: тёрн + ривер, 3 ставки ривера, 1 рейз. Дольше, но подробнее.",
        "icon": "🔬",
        "bet_sizes": [0.33, 0.5, 0.75, 1.0],
        "raise_sizes": [2.5],
        "max_iterations": 150,
        "max_raises": 2,
        "include_turn": True,
        "max_turn_cards": 2,
        "turn_bet_sizes": [0.5, 1.0],
        "turn_raise_sizes": [],
        "turn_max_raises": 0,
        # Phase 11C: river in deep preset
        "include_river": True,
        "max_river_cards": 2,
        "river_bet_sizes": [0.33, 0.5, 1.0],
        "river_raise_sizes": [2.5],
        "river_max_raises": 2,
        "est_time_range": "30–120 сек.",
        "complexity": "HEAVY",
    },
}


# ── Request/Response models ─────────────────────────────────────

class SolveJobRequest(BaseModel):
    board: list[str] = Field(..., min_length=3, max_length=5, example=["Ks", "7d", "2c"])
    ip_range: str = Field(..., example="AA,KK,AKs")
    oop_range: str = Field(..., example="QQ,JJ,AQs")
    pot: float = Field(default=6.5, ge=1.0, le=500.0)
    effective_stack: float = Field(default=97.0, ge=1.0, le=500.0)
    bet_sizes: list[float] = Field(default=[0.5, 1.0], max_length=8)
    raise_sizes: list[float] = Field(default=[2.5], max_length=4)
    max_iterations: int = Field(default=200, ge=10, le=5000)
    max_raises: int = Field(default=2, ge=1, le=4)
    deterministic: bool = Field(default=False)
    include_turn: bool = Field(default=False)
    max_turn_cards: int = Field(default=5, ge=0, le=49)
    # Phase 10A turn-specific fields
    turn_bet_sizes: list[float] = Field(default=[])
    turn_raise_sizes: list[float] = Field(default=[])
    turn_max_raises: int = Field(default=0, ge=0, le=3)
    # Phase 11A river-specific fields
    include_river: bool = Field(default=False)
    max_river_cards: int = Field(default=4, ge=0, le=10)
    river_bet_sizes: list[float] = Field(default=[])
    river_raise_sizes: list[float] = Field(default=[])
    river_max_raises: int = Field(default=0, ge=0, le=2)
    # Phase 10C preset
    preset: Optional[str] = Field(default=None, description="Preset name: fast, standard, deep")


class SolveJobResponse(BaseModel):
    job_id: str
    status: str
    message: str = ""
    estimated_seconds: float = 0.0
    warnings: list[str] = []
    complexity_grade: str = ""  # LIGHT, MODERATE, HEAVY, REJECTED


class SolveJobProgress(BaseModel):
    job_id: str
    status: str
    iteration: int = 0
    total_iterations: int = 0
    convergence_metric: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    progress_pct: float = 0.0
    error: str = ""
    data_source: str = "in_memory"  # in_memory | persisted_summary


class SolveResultResponse(BaseModel):
    job_id: str
    status: str
    iterations: int = 0
    convergence_metric: float = 0.0
    elapsed_seconds: float = 0.0
    tree_nodes: int = 0
    ip_combos: int = 0
    oop_combos: int = 0
    matchups: int = 0
    converged: bool = False
    node_count: int = 0
    metadata: dict = {}
    validation: dict = {}
    exploitability: dict = {}
    trust_grade: dict = {}
    error: str = ""
    full_strategies_available: bool = False
    data_source: str = "in_memory"  # in_memory | persisted_summary


class NodeStrategyResponse(BaseModel):
    job_id: str
    node_id: str
    player: str = ""
    combos: dict[str, dict[str, float]] = {}
    action_summary: dict[str, float] = {}
    message: str = ""


class SolveHistoryItem(BaseModel):
    id: str
    status: str
    created_at: str
    board: list[str] = []
    ip_range: str = ""
    oop_range: str = ""
    iterations: int = 0
    convergence_metric: float = 0.0
    elapsed_seconds: float = 0.0
    converged: bool = False
    validation_passed: bool = False
    full_strategies_available: bool = False
    exploitability_mbb: float | None = None
    trust_grade: str = ""
    street_depth: str = "flop_only"
    stop_reason: str | None = None       # Phase 16B
    quality_class: str | None = None     # Phase 16B


class SolveHistoryDetail(BaseModel):
    id: str
    status: str
    created_at: str
    config: dict = {}
    iterations: int = 0
    convergence_metric: float = 0.0
    elapsed_seconds: float = 0.0
    tree_nodes: int = 0
    ip_combos: int = 0
    oop_combos: int = 0
    matchups: int = 0
    converged: bool = False
    solved_node_count: int = 0
    algorithm_metadata: dict = {}
    metadata: dict = {}  # Phase 16B: alias for frontend consistency
    validation: dict = {}
    root_strategy_summary: dict = {}
    node_summaries: dict = {}
    full_strategies_available: bool = False
    exploitability: dict | None = None
    trust_grade: dict | None = None
    combo_available_nodes: list[str] = []
    combo_storage_note: str = ""
    error: str = ""
    honest_note: str = (
        "Persisted summary + combo subset. Full per-combo data was available "
        "at solve time; a constrained subset is persisted for product integration. "
        "Solver scope: HU postflop, fixed bet sizes."
    )
    street_depth: str = "flop_only"


# ── Helper: estimate solve time ─────────────────────────────────

def _estimate_solve_time(request: SolveJobRequest) -> tuple[float, list[str]]:
    """Estimate solve time and generate warnings."""
    from app.solver.cfr_solver import (
        expand_range_to_combos, SolveRequest,
        MAX_TREE_NODES_FLOP, MAX_COMBOS_PER_SIDE,
    )
    from app.poker_engine.cards import Card
    from app.solver.tree_builder import TreeConfig, build_tree_skeleton

    warnings = []

    try:
        board_cards = [Card.parse(c) for c in request.board]
        ip_combos = expand_range_to_combos(request.ip_range, board_cards)
        oop_combos = expand_range_to_combos(request.oop_range, board_cards)

        # Count valid matchups
        matchups = 0
        for ic in ip_combos:
            ic_set = {(c.rank.value, c.suit.value) for c in ic}
            for oc in oop_combos:
                oc_set = {(c.rank.value, c.suit.value) for c in oc}
                if not ic_set & oc_set:
                    matchups += 1

        # Build tree to get node count for better estimation
        # Phase 11C: include river in tree build for accurate node count
        config = TreeConfig(
            starting_pot=request.pot,
            effective_stack=request.effective_stack,
            board=tuple(request.board),
            flop_bet_sizes=tuple(request.bet_sizes),
            flop_raise_sizes=tuple(request.raise_sizes),
            max_raises_per_street=request.max_raises,
            include_turn=request.include_turn,
            max_turn_cards=request.max_turn_cards,
            turn_bet_sizes_override=tuple(request.turn_bet_sizes) if request.turn_bet_sizes else (0.5, 1.0),
            turn_raise_sizes_override=tuple(request.turn_raise_sizes) if request.turn_raise_sizes else (),
            turn_max_raises=request.turn_max_raises,
            include_river=request.include_river,
            max_river_cards=request.max_river_cards,
            river_bet_sizes_override=tuple(request.river_bet_sizes) if request.river_bet_sizes else (0.33, 0.5, 1.0),
            river_raise_sizes_override=tuple(request.river_raise_sizes) if request.river_raise_sizes else (2.5,),
            river_max_raises=request.river_max_raises,
        )
        _, stats = build_tree_skeleton(config)

        # Calibrated estimation: matchups × iterations × per-matchup-iter cost
        # The tree already includes turn+river branches, so node count captures
        # the full traversal work. No separate turn/river multipliers needed.
        baseline_nodes = 21.0  # typical small flop-only tree
        node_factor = max(stats.total_nodes / baseline_nodes, 1.0)
        est_seconds = matchups * request.max_iterations * EST_SECONDS_PER_MATCHUP_ITER * node_factor

        # Add equity precomputation time
        if request.include_turn:
            turn_cards = request.max_turn_cards or 5
            equity_precomp = matchups * turn_cards * 0.00005
            est_seconds += equity_precomp
            if request.include_river:
                river_cards = request.max_river_cards or 4
                equity_precomp_river = matchups * turn_cards * river_cards * 0.00005
                est_seconds += equity_precomp_river
                warnings.append(
                    f"Тёрн ({turn_cards} карт) + ривер ({river_cards} карт). "
                    f"Примерное время ~{est_seconds:.0f} сек. "
                    "Ривер: 3 ставки, 1 рейз."
                )
            else:
                warnings.append(
                    f"Тёрн включён ({turn_cards} карт). "
                    f"Примерное время ~{est_seconds:.0f} сек. "
                    "Тёрн-поддержка: ограниченная абстракция."
                )
            if turn_cards > 5:
                warnings.append(
                    f"Using {turn_cards} turn cards. Consider ≤5 for faster results."
                )

        if est_seconds > 120:
            warnings.append(
                f"Estimated solve time: ~{est_seconds:.0f}s ({matchups} matchups × "
                f"{request.max_iterations} iters × {stats.total_nodes} nodes). "
                f"Consider reducing range or iterations."
            )
        elif est_seconds > 30:
            warnings.append(f"Estimated solve time: ~{est_seconds:.0f}s. May take a while.")

        if len(ip_combos) > 30 or len(oop_combos) > 30:
            warnings.append(
                f"Large range: IP={len(ip_combos)} combos, OOP={len(oop_combos)} combos. "
                f"Pure Python solver is slow for large ranges."
            )

        if request.max_iterations > 500:
            warnings.append(
                f"High iteration count ({request.max_iterations}). "
                f"50-200 iterations is usually sufficient for demo purposes."
            )

        return est_seconds, warnings
    except Exception:
        return 0.0, []


# ── Helper: persist job status early (Phase 8A) ──────────────────

def _persist_job_status(job_id: str, job: dict, db: Session, status: str = "running"):
    """Persist job status to SolveResultModel at creation time (before solve completes).
    Uses db.merge() to upsert — safe if record already exists."""
    try:
        config = job.get("request", {})
        record = SolveResultModel(
            id=job_id,
            user_id=job.get("user_id"),
            status=status,
            config_json=config,
        )
        db.merge(record)
        db.commit()
        logger.info("Persisted job %s status=%s to database (early)", job_id, status)
    except Exception as e:
        logger.error("Failed to persist job status %s: %s", job_id, e)
        db.rollback()


def _build_result_from_db(record: SolveResultModel) -> SolveResultResponse:
    """Build a SolveResultResponse from a persisted SolveResultModel.
    Used as fallback when in-memory job data is gone."""
    config = record.config_json or {}
    validation = record.validation_json or {}
    exploit_data = record.exploitability_json or {}
    trust = record.trust_grade_json or {}

    return SolveResultResponse(
        job_id=record.id,
        status=record.status,
        iterations=record.iterations or 0,
        convergence_metric=record.convergence_metric or 0.0,
        elapsed_seconds=record.elapsed_seconds or 0.0,
        tree_nodes=record.tree_nodes or 0,
        ip_combos=record.ip_combos or 0,
        oop_combos=record.oop_combos or 0,
        matchups=record.matchups or 0,
        converged=record.converged or False,
        node_count=record.solved_node_count or 0,
        metadata=record.algorithm_metadata_json or {},
        validation=validation,
        exploitability=exploit_data,
        trust_grade=trust,
        full_strategies_available=False,  # In-memory strategies are gone
        data_source="persisted_summary",
        error=record.error or "",
    )


def _build_progress_from_db(record: SolveResultModel) -> SolveJobProgress:
    """Build a SolveJobProgress from a persisted SolveResultModel.
    Used when in-memory job is gone but DB has the completed record."""
    return SolveJobProgress(
        job_id=record.id,
        status=record.status,
        iteration=record.iterations or 0,
        total_iterations=record.iterations or 0,
        convergence_metric=record.convergence_metric or 0.0,
        elapsed_seconds=record.elapsed_seconds or 0.0,
        estimated_remaining_seconds=0.0,
        progress_pct=100.0 if record.status == "done" else 0.0,
        data_source="persisted_summary",
    )


# ── Helper: persist solve result ─────────────────────────────────

def _persist_solve_result(job_id: str, job: dict, db: Session):
    """Persist solve result summary to SQLite."""
    try:
        result = job.get("result")
        config = job.get("request", {})
        metadata = job.get("metadata", {})
        validation = metadata.get("validation", {})

        # Build root strategy summary (aggregate action freqs, not per-combo)
        root_summary = {}
        node_summaries = {}
        if result:
            for node_id, combos in list(result.strategies.items())[:20]:
                action_totals = {}
                count = len(combos)
                for combo_str, freqs in combos.items():
                    for action, freq in freqs.items():
                        action_totals[action] = action_totals.get(action, 0.0) + freq
                summary = {a: round(t / count, 4) for a, t in action_totals.items()}
                node_summaries[node_id] = summary
                if node_id == "node_0":
                    root_summary = summary

        # Compute trust grade for persistence
        exploit_data = metadata.get("exploitability", {})
        exploit_mbb = exploit_data.get("exploitability_mbb_per_hand") if exploit_data else None
        exploit_exact = exploit_data.get("is_exact_within_abstraction", False)

        from app.solver.solver_validation import ValidationResult, compute_trust_grade
        vr = ValidationResult(
            passed=validation.get("passed", False),
            checks_run=validation.get("checks_run", 0),
            checks_passed=validation.get("checks_passed", 0),
            warnings=validation.get("warnings", []),
        )
        trust = compute_trust_grade(
            vr,
            exploitability_mbb=exploit_mbb if exploit_mbb is not None else float("inf"),
            exploitability_available=exploit_mbb is not None,
            street_depth=metadata.get("street_depth", "flop_only"),
        )

        # Run correctness checks if solver state is available
        correctness_data = None
        correctness_notes_str = None
        try:
            from app.solver.correctness_checks import run_correctness_checks
            correctness_report = run_correctness_checks(include_slow=False)
            correctness_data = correctness_report.to_dict()
            correctness_notes_str = "; ".join(correctness_report.confidence_notes)
            # Update trust grade with correctness confidence
            trust = compute_trust_grade(
                vr,
                exploitability_mbb=exploit_mbb if exploit_mbb is not None else float("inf"),
                exploitability_available=exploit_mbb is not None,
                street_depth=metadata.get("street_depth", "flop_only"),
                correctness_confidence=correctness_report.confidence_level,
                correctness_notes=correctness_report.confidence_notes,
            )
        except Exception as e:
            logger.warning("Correctness checks skipped during persist: %s", e)

        record = SolveResultModel(
            id=job_id,
            user_id=job.get("user_id"),
            status=job["status"],
            completed_at=datetime.utcnow(),
            config_json=config,
            iterations=job.get("iterations", 0),
            convergence_metric=job.get("convergence_metric", 0.0),
            elapsed_seconds=job.get("elapsed_seconds", 0.0),
            tree_nodes=job.get("tree_nodes", 0),
            ip_combos=job.get("ip_combos", 0),
            oop_combos=job.get("oop_combos", 0),
            matchups=job.get("matchups", 0),
            converged=job.get("converged", False),
            solved_node_count=len(result.strategies) if result else 0,
            algorithm_metadata_json={
                k: v for k, v in metadata.items()
                if k not in ("validation", "exploitability")
            },
            validation_json=validation,
            root_strategy_summary_json=root_summary,
            node_summaries_json=node_summaries,
            full_strategies_available=result is not None,
            exploitability_mbb=exploit_mbb,
            exploitability_exact=exploit_exact,
            trust_grade=trust.get("grade", "STRUCTURAL_ONLY"),
            trust_grade_json=trust,
            exploitability_json=exploit_data,
            combo_strategies_json=_extract_combo_subset(result) if result else None,
            combo_storage_note=_combo_storage_note(result) if result else None,
            street_depth=metadata.get("street_depth", "flop_only"),
            turn_cards_explored=metadata.get("turn_cards_explored", 0),
            correctness_json=correctness_data,
            correctness_notes=correctness_notes_str,
            error=job.get("error"),
        )

        db.merge(record)
        db.commit()
        logger.info("Persisted solve result %s to database", job_id)

    except Exception as e:
        logger.error("Failed to persist solve result %s: %s", job_id, e)
        db.rollback()



MAX_PERSISTED_COMBOS = 500
MAX_PERSISTED_NODES = 6  # root + 5 children


def _extract_combo_subset(output) -> dict | None:
    """Extract a constrained subset of per-combo strategies for persistence.
    Stores root + first 5 child nodes, max 500 combo entries total."""
    if not output or not output.strategies:
        return None
    combo_data = {}
    total_combos = 0
    sorted_nodes = sorted(output.strategies.keys())
    for node_id in sorted_nodes[:MAX_PERSISTED_NODES]:
        node_strats = output.strategies[node_id]
        if total_combos + len(node_strats) > MAX_PERSISTED_COMBOS:
            remaining = MAX_PERSISTED_COMBOS - total_combos
            truncated = dict(list(node_strats.items())[:remaining])
            combo_data[node_id] = truncated
            total_combos += len(truncated)
            break
        combo_data[node_id] = node_strats
        total_combos += len(node_strats)
    return combo_data if combo_data else None


def _combo_storage_note(output) -> str:
    """Describe what combo data was persisted."""
    if not output or not output.strategies:
        return "No combo data available."
    total_nodes = len(output.strategies)
    stored_nodes = min(total_nodes, MAX_PERSISTED_NODES)
    return (
        f"Persisted {stored_nodes}/{total_nodes} nodes (max {MAX_PERSISTED_COMBOS} combos). "
        f"Full per-combo data was available at solve time but only a subset is persisted."
    )


# ── Background solve runner ─────────────────────────────────────

async def _run_solve_background(job_id: str, request: SolveJobRequest):
    """Run CFR+ solve in background with timeout guard."""
    from app.solver.cfr_solver import CfrSolver, SolveRequest, SolveProgressInfo

    job = _solve_jobs.get(job_id)
    if not job:
        return

    try:
        job["status"] = "running"
        start_wall = time.time()

        # ── Phase 8A: Persist job at creation (status=running) ──
        from app.db import SessionLocal
        db_early = SessionLocal()
        try:
            _persist_job_status(job_id, job, db_early, status="running")
        finally:
            db_early.close()

        solve_request = SolveRequest(
            board=request.board,
            ip_range=request.ip_range,
            oop_range=request.oop_range,
            pot=request.pot,
            effective_stack=request.effective_stack,
            bet_sizes=request.bet_sizes,
            raise_sizes=request.raise_sizes,
            max_iterations=request.max_iterations,
            max_raises=request.max_raises,
            deterministic=request.deterministic,
            include_turn=request.include_turn,
            max_turn_cards=request.max_turn_cards,
            turn_bet_sizes=request.turn_bet_sizes if request.turn_bet_sizes else [0.33, 0.5, 0.75, 1.0],
            turn_raise_sizes=request.turn_raise_sizes if request.turn_raise_sizes else [2.5],
            turn_max_raises=request.turn_max_raises,
            # Phase 11A+11C: river support (expanded abstraction)
            include_river=request.include_river,
            max_river_cards=request.max_river_cards,
            river_bet_sizes=request.river_bet_sizes if request.river_bet_sizes else [0.33, 0.5, 1.0],
            river_raise_sizes=request.river_raise_sizes if request.river_raise_sizes else [2.5],
            river_max_raises=request.river_max_raises if request.river_max_raises else 2,
        )
        # Phase 16A: tag SolveRequest with preset for adaptive budget
        solve_request._preset = job.get('preset', 'standard')

        solver = CfrSolver()

        def on_progress(info: SolveProgressInfo):
            job["iteration"] = info.iteration
            job["total_iterations"] = info.total_iterations
            job["convergence_metric"] = info.convergence_metric
            job["elapsed_seconds"] = info.elapsed_seconds

        def check_cancel() -> bool:
            # Cancel if explicitly requested OR wall-clock timeout
            if job.get("cancelled", False):
                return True
            if time.time() - start_wall > MAX_SOLVE_WALL_SECONDS:
                job["timeout"] = True
                return True
            return False

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            lambda: solver.solve(solve_request, on_progress, check_cancel),
        )

        # Phase 18: release concurrent solve lock
        global _active_solve_id
        with _solve_lock:
            if _active_solve_id == job_id:
                _active_solve_id = None

        if job.get("timeout"):
            job["status"] = "timeout"
        elif job.get("cancelled"):
            job["status"] = "cancelled"
        else:
            job["status"] = "done"

        job["result"] = output
        job["iterations"] = output.iterations
        job["convergence_metric"] = output.convergence_metric
        job["elapsed_seconds"] = output.elapsed_seconds
        job["tree_nodes"] = output.tree_nodes
        job["ip_combos"] = output.ip_combos
        job["oop_combos"] = output.oop_combos
        job["matchups"] = output.matchups
        job["converged"] = output.converged
        job["metadata"] = output.metadata
        # Phase 16A: record stop reason
        job["stop_reason"] = output.stop_reason

        logger.info("Solve job %s completed: %d iters, convergence=%.6f, stop_reason=%s, status=%s",
                     job_id, output.iterations, output.convergence_metric,
                     output.stop_reason, job["status"])

        # Persist to DB (full result with strategies)
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            _persist_solve_result(job_id, job, db)
        finally:
            db.close()

    except Exception as e:
        logger.error("Solve job %s failed: %s", job_id, e)
        job["status"] = "failed"
        job["error"] = str(e)

        # Persist failed status
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            _persist_solve_result(job_id, job, db)
        finally:
            db.close()


# ── Endpoints ───────────────────────────────────────────────────

def _cleanup_stale_jobs():
    """Remove in-memory jobs older than STALE_JOB_EXPIRY_SECONDS.
    Phase 18: Also recovers stuck 'running' jobs that have been running too long."""
    global _active_solve_id
    now = datetime.utcnow()
    stale_ids = []
    stuck_ids = []
    for jid, jdata in _solve_jobs.items():
        created = jdata.get("created_at", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                age_seconds = (now - created_dt).total_seconds()
                # Phase 18: detect stuck "running" jobs (>10 min old)
                if jdata.get("status") in ("running", "queued") and age_seconds > STUCK_RUNNING_TIMEOUT_SECONDS:
                    stuck_ids.append(jid)
                # Stale completed jobs (>30 min)
                elif (age_seconds > STALE_JOB_EXPIRY_SECONDS
                      and jdata.get("status") in ("done", "failed", "timeout", "cancelled")):
                    stale_ids.append(jid)
            except (ValueError, TypeError):
                pass
    # Mark stuck jobs as failed
    for jid in stuck_ids:
        _solve_jobs[jid]["status"] = "failed"
        _solve_jobs[jid]["error"] = "Солвер зависла. Задача автоматически отменена после 10 минут."
        logger.warning("Recovered stuck job %s (was running > %ds)", jid, STUCK_RUNNING_TIMEOUT_SECONDS)
    # Clean up old completed jobs
    for jid in stale_ids:
        del _solve_jobs[jid]
    if stale_ids or stuck_ids:
        logger.info("Cleanup: %d stale removed, %d stuck recovered", len(stale_ids), len(stuck_ids))
    # Phase 18: release solve lock if active solve is no longer running
    with _solve_lock:
        if _active_solve_id:
            active_job = _solve_jobs.get(_active_solve_id)
            if not active_job or active_job.get("status") not in ("queued", "running"):
                _active_solve_id = None

@router.get("/presets")
def get_solver_presets(_user: UserModel = Depends(get_current_user)):
    """Return available solver presets with descriptions.
    Phase 18: includes turn_preset_note for honest UX messaging."""
    return {
        "presets": {
            k: {
                "label": v["label"],
                "description": v["description"],
                "icon": v["icon"],
                "est_time_range": v["est_time_range"],
                "complexity": v["complexity"],
                "include_turn": v["include_turn"],
                "include_river": v.get("include_river", False),
            }
            for k, v in SOLVER_PRESETS.items()
        },
        "default": "standard",
        # Phase 18: honest turn preset messaging
        "turn_preset_note": (
            "При расчёте тёрна все режимы (Быстрый / Стандартный / Глубокий) "
            "дают одинаковый результат, потому что солвер достигает полной "
            "сходимости за ~50 итераций на ограниченном дереве тёрна. "
            "Выбор режима влияет только на флоп и ривер."
        ),
    }


@router.post("/solve", response_model=SolveJobResponse)
async def create_solve_job(
    req: SolveJobRequest,
    background_tasks: BackgroundTasks,
    _user: UserModel = Depends(get_current_user),
):
    """
    Start a real CFR+ solve job.

    The solve runs in the background. Use GET /job/{id} to poll progress
    and GET /result/{id} to retrieve the completed result.

    Supports preset-driven configuration (fast/standard/deep) or manual.
    """
    from app.solver.cfr_solver import validate_solve_request, SolveRequest

    # Phase 10C: Apply preset overrides (Phase 11C: includes river)
    preset_name = req.preset
    if preset_name and preset_name in SOLVER_PRESETS:
        p = SOLVER_PRESETS[preset_name]
        req.bet_sizes = p["bet_sizes"]
        req.raise_sizes = p["raise_sizes"]
        req.max_iterations = p["max_iterations"]
        req.max_raises = p["max_raises"]
        req.include_turn = p["include_turn"]
        req.max_turn_cards = p["max_turn_cards"]
        req.turn_bet_sizes = p["turn_bet_sizes"]
        req.turn_raise_sizes = p["turn_raise_sizes"]
        req.turn_max_raises = p["turn_max_raises"]
        # Phase 11C: wire preset river fields
        req.include_river = p.get("include_river", False)
        if req.include_river:
            req.max_river_cards = p.get("max_river_cards", 2)
            req.river_bet_sizes = p.get("river_bet_sizes", [0.5, 1.0])
            req.river_raise_sizes = p.get("river_raise_sizes", [])
            req.river_max_raises = p.get("river_max_raises", 0)

    solve_request = SolveRequest(
        board=req.board,
        ip_range=req.ip_range,
        oop_range=req.oop_range,
        pot=req.pot,
        effective_stack=req.effective_stack,
        bet_sizes=req.bet_sizes,
        raise_sizes=req.raise_sizes,
        max_iterations=req.max_iterations,
        max_raises=req.max_raises,
        deterministic=req.deterministic,
        include_turn=req.include_turn,
        max_turn_cards=req.max_turn_cards,
        turn_bet_sizes=req.turn_bet_sizes if req.turn_bet_sizes else [0.33, 0.5, 0.75, 1.0],
        turn_raise_sizes=req.turn_raise_sizes if req.turn_raise_sizes else [2.5],
        turn_max_raises=req.turn_max_raises,
        # Phase 11A+11C: river support (expanded abstraction)
        include_river=req.include_river,
        max_river_cards=req.max_river_cards,
        river_bet_sizes=req.river_bet_sizes if req.river_bet_sizes else [0.33, 0.5, 1.0],
        river_raise_sizes=req.river_raise_sizes if req.river_raise_sizes else [2.5],
        river_max_raises=req.river_max_raises if req.river_max_raises else 2,
    )

    valid, error = validate_solve_request(solve_request)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Time estimation + warnings
    est_seconds, warnings = _estimate_solve_time(req)

    # Complexity grading
    if est_seconds > MAX_ESTIMATED_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Configuration too complex (estimated ~{est_seconds:.0f}s, "
                f"max {MAX_ESTIMATED_SECONDS}s). Reduce range, iterations, or turn cards."
            ),
        )

    complexity_grade = (
        "LIGHT" if est_seconds < 5
        else "MODERATE" if est_seconds < 30
        else "HEAVY"
    )

    # Cleanup stale jobs
    _cleanup_stale_jobs()

    # Phase 18: Concurrent solve protection
    global _active_solve_id
    with _solve_lock:
        if _active_solve_id:
            active_job = _solve_jobs.get(_active_solve_id)
            if active_job and active_job.get("status") in ("queued", "running"):
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Уже выполняется другой расчёт. Дождитесь завершения или отмените "
                        f"текущий расчёт (ID: {_active_solve_id})."
                    ),
                )
            # Previous solve finished, release
            _active_solve_id = None

    job_id = f"solve-{uuid.uuid4().hex[:8]}"
    _solve_jobs[job_id] = {
        "status": "queued",
        "iteration": 0,
        "total_iterations": req.max_iterations,
        "convergence_metric": float("inf"),
        "elapsed_seconds": 0.0,
        "error": "",
        "result": None,
        "cancelled": False,
        "timeout": False,
        "request": req.model_dump(),
        "user_id": _user.id,
        "created_at": datetime.utcnow().isoformat(),
        "estimated_seconds": est_seconds,
        "preset": preset_name or "standard",  # Phase 16A: for adaptive budget
    }

    with _solve_lock:
        _active_solve_id = job_id

    background_tasks.add_task(_run_solve_background, job_id, req)

    return SolveJobResponse(
        job_id=job_id,
        status="queued",
        message=f"Solve job created. Board: {req.board}, IP: {req.ip_range}, OOP: {req.oop_range}",
        estimated_seconds=round(est_seconds, 1),
        warnings=warnings,
        complexity_grade=complexity_grade,
    )


@router.get("/job/{job_id}", response_model=SolveJobProgress)
def get_solve_progress(
    job_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get progress of a solve job. Falls back to DB if not in memory."""
    job = _solve_jobs.get(job_id)
    if not job:
        # Phase 8A: DB fallback — check persisted results
        record = db.query(SolveResultModel).filter(SolveResultModel.id == job_id).first()
        if record:
            return _build_progress_from_db(record)
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}. It may have expired from memory. "
                   f"Check /history for persisted results.",
        )

    iteration = job.get("iteration", 0)
    total = job.get("total_iterations", 0)
    elapsed = job.get("elapsed_seconds", 0.0)

    # Compute ETA
    progress_pct = (iteration / total * 100) if total > 0 else 0.0
    if iteration > 0 and total > 0 and elapsed > 0:
        rate = iteration / elapsed
        eta = (total - iteration) / rate if rate > 0 else 0.0
    else:
        eta = job.get("estimated_seconds", 0.0)

    return SolveJobProgress(
        job_id=job_id,
        status=job["status"],
        iteration=iteration,
        total_iterations=total,
        convergence_metric=job.get("convergence_metric", 0.0),
        elapsed_seconds=round(elapsed, 1),
        estimated_remaining_seconds=round(eta, 1),
        progress_pct=round(progress_pct, 1),
        error=job.get("error", ""),
        data_source="in_memory",
    )


@router.get("/result/{job_id}", response_model=SolveResultResponse)
def get_solve_result(
    job_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """Get the completed result of a solve job. Falls back to DB if not in memory."""
    job = _solve_jobs.get(job_id)
    if not job:
        # Phase 8A: DB fallback — return persisted result
        record = db.query(SolveResultModel).filter(SolveResultModel.id == job_id).first()
        if record:
            return _build_result_from_db(record)
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}. It may have expired from memory. "
                   f"Check /history for persisted results.",
        )

    if job["status"] not in ("done", "timeout", "cancelled"):
        return SolveResultResponse(
            job_id=job_id,
            status=job["status"],
            error=job.get("error", "Not yet complete"),
        )

    result = job.get("result")
    metadata = job.get("metadata", {})
    validation = metadata.get("validation", {})
    exploit_data = metadata.get("exploitability", {})

    # Compute trust grade
    from app.solver.solver_validation import ValidationResult, compute_trust_grade
    vr = ValidationResult(
        passed=validation.get("passed", False),
        checks_run=validation.get("checks_run", 0),
        checks_passed=validation.get("checks_passed", 0),
        warnings=validation.get("warnings", []),
    )
    exploit_mbb = exploit_data.get("exploitability_mbb_per_hand", float("inf"))
    trust = compute_trust_grade(
        vr,
        exploitability_mbb=exploit_mbb,
        exploitability_available=bool(exploit_data),
        street_depth=metadata.get("street_depth", "flop_only"),
    )

    return SolveResultResponse(
        job_id=job_id,
        status=job["status"],
        iterations=job.get("iterations", 0),
        convergence_metric=job.get("convergence_metric", 0.0),
        elapsed_seconds=job.get("elapsed_seconds", 0.0),
        tree_nodes=job.get("tree_nodes", 0),
        ip_combos=job.get("ip_combos", 0),
        oop_combos=job.get("oop_combos", 0),
        matchups=job.get("matchups", 0),
        converged=job.get("converged", False),
        node_count=len(result.strategies) if result else 0,
        metadata=metadata,
        validation=validation,
        exploitability=exploit_data,
        trust_grade=trust,
        full_strategies_available=result is not None,
        data_source="in_memory",
    )


@router.get("/node/{job_id}/{node_id}", response_model=NodeStrategyResponse)
def get_node_strategy(
    job_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Inspect a solved node — view per-combo action frequencies.
    Falls back to persisted combo subset if full strategies are gone.
    """
    job = _solve_jobs.get(job_id)

    # Phase 8A: Try in-memory first
    if job and job["status"] in ("done", "timeout", "cancelled"):
        result = job.get("result")
        if result:
            node_strats = result.strategies.get(node_id, {})
            if node_strats:
                action_totals: dict[str, float] = {}
                combo_count = len(node_strats)
                for combo_str, freqs in node_strats.items():
                    for action, freq in freqs.items():
                        action_totals[action] = action_totals.get(action, 0.0) + freq
                action_summary = {a: round(t / combo_count, 4) for a, t in action_totals.items()}
                return NodeStrategyResponse(
                    job_id=job_id,
                    node_id=node_id,
                    combos=node_strats,
                    action_summary=action_summary,
                    message=f"Strategy for {combo_count} combos at node {node_id} (live in-memory data)",
                )

    # Phase 8A: DB fallback — try persisted combo subset
    record = db.query(SolveResultModel).filter(SolveResultModel.id == job_id).first()
    if record:
        combo_data = record.combo_strategies_json or {}
        node_strats = combo_data.get(node_id, {})
        if node_strats:
            action_totals = {}
            combo_count = len(node_strats)
            for combo_str, freqs in node_strats.items():
                for action, freq in freqs.items():
                    action_totals[action] = action_totals.get(action, 0.0) + freq
            action_summary = {a: round(t / combo_count, 4) for a, t in action_totals.items()}
            return NodeStrategyResponse(
                job_id=job_id,
                node_id=node_id,
                combos=node_strats,
                action_summary=action_summary,
                message=(
                    f"Persisted combo subset for node {node_id} ({combo_count} combos). "
                    f"Full in-memory strategies are no longer available. "
                    f"{record.combo_storage_note or ''}"
                ),
            )

        # Node not in persisted subset — check node summaries
        node_summaries = record.node_summaries_json or {}
        node_summary = node_summaries.get(node_id)
        if node_summary:
            return NodeStrategyResponse(
                job_id=job_id,
                node_id=node_id,
                combos={},
                action_summary=node_summary,
                message=(
                    f"Aggregate action frequencies for node {node_id} (persisted summary). "
                    f"Per-combo data is no longer available."
                ),
            )

        # Node not found anywhere
        available_nodes = list((record.combo_strategies_json or {}).keys())[:10]
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found in persisted data for job {job_id}. "
                   f"Available persisted nodes: {available_nodes}",
        )

    if job and job["status"] not in ("done", "timeout", "cancelled"):
        raise HTTPException(status_code=400, detail="Solve not yet complete")

    raise HTTPException(
        status_code=404,
        detail=f"Job not found: {job_id}. It may have expired from memory. "
               f"Check /history for persisted results.",
    )


@router.post("/cancel/{job_id}")
def cancel_solve_job(
    job_id: str,
    _user: UserModel = Depends(get_current_user),
):
    """Cancel a running solve job."""
    job = _solve_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] not in ("queued", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in status: {job['status']}")

    job["cancelled"] = True
    return {"job_id": job_id, "status": "cancelling", "message": "Cancellation requested"}


@router.get("/stream/{job_id}")
async def stream_solve_progress(
    job_id: str,
    token: str = "",
    db: Session = Depends(get_db),
):
    """
    Phase 15C: SSE endpoint for real-time solve progress.

    Auth: token passed as query parameter (EventSource cannot set headers).

    Streams progress events every 500ms until the job reaches a terminal state
    (done, failed, timeout, cancelled). Each event is a JSON object with:
      - job_id, status, iteration, total_iterations, progress_pct,
        convergence_metric, elapsed_seconds, estimated_remaining_seconds

    Transport: Server-Sent Events (text/event-stream)
    """
    from starlette.responses import StreamingResponse
    from app.security import decode_token

    # Auth via query param (EventSource can't set headers)
    if not token:
        raise HTTPException(status_code=401, detail="Token required")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_id = int(payload["sub"])
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    TERMINAL_STATES = {"done", "failed", "timeout", "cancelled"}
    POLL_INTERVAL = 0.5  # seconds between SSE pushes

    async def event_generator():
        import json as _json

        while True:
            job = _solve_jobs.get(job_id)
            if not job:
                # Job not in memory — check DB
                from app.db import SessionLocal
                db = SessionLocal()
                try:
                    record = db.query(SolveResultModel).filter(
                        SolveResultModel.id == job_id
                    ).first()
                    if record:
                        event_data = {
                            "job_id": job_id,
                            "status": record.status,
                            "iteration": record.iterations or 0,
                            "total_iterations": record.iterations or 0,
                            "progress_pct": 100.0 if record.status == "done" else 0.0,
                            "convergence_metric": record.convergence_metric or 0.0,
                            "elapsed_seconds": record.elapsed_seconds or 0.0,
                            "estimated_remaining_seconds": 0.0,
                        }
                        yield f"event: {record.status}\ndata: {_json.dumps(event_data)}\n\n"
                    else:
                        yield f"event: error\ndata: {_json.dumps({'error': 'Job not found'})}\n\n"
                finally:
                    db.close()
                return

            iteration = job.get("iteration", 0)
            total = job.get("total_iterations", 0)
            elapsed = job.get("elapsed_seconds", 0.0)
            status = job["status"]

            progress_pct = (iteration / total * 100) if total > 0 else 0.0
            if iteration > 0 and total > 0 and elapsed > 0:
                rate = iteration / elapsed
                eta = (total - iteration) / rate if rate > 0 else 0.0
            else:
                eta = job.get("estimated_seconds", 0.0)

            event_data = {
                "job_id": job_id,
                "status": status,
                "iteration": iteration,
                "total_iterations": total,
                "progress_pct": round(progress_pct, 1),
                "convergence_metric": round(job.get("convergence_metric", 0.0), 6),
                "elapsed_seconds": round(elapsed, 1),
                "estimated_remaining_seconds": round(eta, 1),
            }

            event_name = status if status in TERMINAL_STATES else "progress"
            yield f"event: {event_name}\ndata: {_json.dumps(event_data)}\n\n"

            if status in TERMINAL_STATES:
                return

            await asyncio.sleep(POLL_INTERVAL)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs", response_model=list[SolveJobProgress])
def list_solve_jobs(
    _user: UserModel = Depends(get_current_user),
):
    """List all active (in-memory) solve jobs."""
    return [
        SolveJobProgress(
            job_id=job_id,
            status=job["status"],
            iteration=job.get("iteration", 0),
            total_iterations=job.get("total_iterations", 0),
            convergence_metric=job.get("convergence_metric", 0.0),
            elapsed_seconds=job.get("elapsed_seconds", 0.0),
            error=job.get("error", ""),
        )
        for job_id, job in _solve_jobs.items()
    ]


# ── Persistence endpoints ───────────────────────────────────────

@router.get("/history", response_model=list[SolveHistoryItem])
def list_solve_history(
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    List persisted solve results.

    HONEST NOTE: Persisted results contain summaries only,
    not the full per-combo strategy matrix.
    """
    records = db.query(SolveResultModel).order_by(
        SolveResultModel.created_at.desc()
    ).limit(50).all()

    items = []
    for r in records:
        config = r.config_json or {}
        validation = r.validation_json or {}
        algo_meta = r.algorithm_metadata_json or {}
        solve_quality = algo_meta.get("solve_quality", {})
        items.append(SolveHistoryItem(
            id=r.id,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else "",
            board=config.get("board", []),
            ip_range=config.get("ip_range", ""),
            oop_range=config.get("oop_range", ""),
            iterations=r.iterations,
            convergence_metric=r.convergence_metric,
            elapsed_seconds=r.elapsed_seconds,
            converged=r.converged,
            validation_passed=validation.get("passed", False),
            full_strategies_available=r.full_strategies_available and r.id in _solve_jobs,
            exploitability_mbb=r.exploitability_mbb,
            trust_grade=r.trust_grade or "",
            street_depth=r.street_depth or "flop_only",
            stop_reason=algo_meta.get("stop_reason"),
            quality_class=solve_quality.get("quality_class"),
        ))
    return items


@router.get("/history/{solve_id}", response_model=SolveHistoryDetail)
def get_solve_history_detail(
    solve_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Get detailed persisted solve result.

    HONEST NOTE: This returns summary data. Full per-combo strategies
    are only available in-memory via /node/{job_id}/{node_id}.
    """
    r = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Solve result not found: {solve_id}")

    combo_data = r.combo_strategies_json or {}

    return SolveHistoryDetail(
        id=r.id,
        status=r.status,
        created_at=r.created_at.isoformat() if r.created_at else "",
        config=r.config_json or {},
        iterations=r.iterations,
        convergence_metric=r.convergence_metric,
        elapsed_seconds=r.elapsed_seconds,
        tree_nodes=r.tree_nodes,
        ip_combos=r.ip_combos,
        oop_combos=r.oop_combos,
        matchups=r.matchups,
        converged=r.converged,
        solved_node_count=r.solved_node_count,
        algorithm_metadata=r.algorithm_metadata_json or {},
        metadata=r.algorithm_metadata_json or {},  # Phase 16B: alias
        validation=r.validation_json or {},
        root_strategy_summary=r.root_strategy_summary_json or {},
        node_summaries=r.node_summaries_json or {},
        full_strategies_available=r.full_strategies_available and r.id in _solve_jobs,
        exploitability=r.exploitability_json,
        trust_grade=r.trust_grade_json,
        combo_available_nodes=list(combo_data.keys()) if combo_data else [],
        combo_storage_note=r.combo_storage_note or "",
        error=r.error or "",
        street_depth=r.street_depth or "flop_only",
    )


@router.get("/history/{solve_id}/node/{node_id}")
def get_solve_node_detail(
    solve_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    _user: UserModel = Depends(get_current_user),
):
    """
    Get persisted per-combo strategy data for a specific node within a solve.

    Returns combo-level frequencies if persisted, otherwise summary-only.
    """
    r = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if not r:
        raise HTTPException(status_code=404, detail=f"Solve not found: {solve_id}")

    combo_data = r.combo_strategies_json or {}
    node_combos = combo_data.get(node_id)
    node_summary = (r.node_summaries_json or {}).get(node_id)

    if not node_combos and not node_summary:
        raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")

    return {
        "solve_id": solve_id,
        "node_id": node_id,
        "data_source": "persisted_combo_subset" if node_combos else "persisted_summary_only",
        "combos": node_combos or {},
        "combo_count": len(node_combos) if node_combos else 0,
        "summary": node_summary or {},
        "trust_grade": r.trust_grade or "",
        "exploitability_mbb": r.exploitability_mbb,
        "scope": "flop-only, HU postflop, fixed bet sizes",
    }


# ── Validation endpoint ─────────────────────────────────────────

@router.post("/validate")
def run_validation(
    _user: UserModel = Depends(get_current_user),
):
    """
    Run toy-game and deterministic validation checks.

    Returns validation results. This is NOT a proof of correctness,
    but an engineering sanity check.
    """
    from app.solver.solver_validation import (
        run_toy_game_validation,
        validate_deterministic_reproducibility,
    )

    toy_result = run_toy_game_validation()
    det_result = validate_deterministic_reproducibility()

    return {
        "toy_game": toy_result,
        "deterministic": det_result,
        "overall_passed": toy_result.get("passed", False) and det_result.get("passed", False),
        "honest_note": (
            "These are engineering sanity checks, NOT mathematical proof. "
            "They verify the solver doesn't produce obviously wrong output."
        ),
    }


# ── Benchmark endpoint ──────────────────────────────────────────

@router.post("/benchmarks")
def run_benchmarks(
    _user: UserModel = Depends(get_current_user),
):
    """
    Run the benchmark suite — 5 predefined scenarios with expected behavior.

    Each benchmark: solve → compute exploitability → check qualitative behavior.
    Returns pass/warn/fail for each scenario.

    WARNING: This runs 5 real solves and may take 30-120 seconds.
    """
    from app.solver.benchmarks import run_benchmark_suite

    suite_result = run_benchmark_suite()
    return suite_result.to_dict()


@router.get("/benchmarks")
def get_benchmark_info(
    _user: UserModel = Depends(get_current_user),
):
    """Get benchmark suite metadata (without running)."""
    from app.solver.benchmarks import BENCHMARKS

    return {
        "total_benchmarks": len(BENCHMARKS),
        "benchmarks": [
            {
                "name": b["name"],
                "description": b["description"],
                "board": b["board"],
                "ip_range": b["ip_range"],
                "oop_range": b["oop_range"],
                "checks": len(b.get("checks", [])),
            }
            for b in BENCHMARKS
        ],
        "honest_note": (
            "Benchmarks verify qualitative behavior, not exact Nash frequencies. "
            "They are regression checkpoints, not proofs of correctness."
        ),
    }


@router.post("/correctness-check")
def run_correctness_check(
    _user: UserModel = Depends(get_current_user),
):
    """
    Run all solver correctness checks (including slow ones).

    This runs the full correctness check suite: regret sanity, showdown
    equity spot-checks, blocker filtering, board construction, chance-node
    uniformity, exploitability monotonicity, and relabelled symmetry.

    HONEST NOTE: These checks verify properties within the current
    game abstraction. They do NOT prove full NLHE correctness.
    """
    from app.solver.correctness_checks import run_correctness_checks

    report = run_correctness_checks(include_slow=True)
    return report.to_dict()
