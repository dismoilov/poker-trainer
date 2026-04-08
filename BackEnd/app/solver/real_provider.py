"""
Real solver provider — CFR+ based solver implementation.

This provider invokes a genuine CFR+ solver (app.solver.cfr_solver.CfrSolver)
that performs real counterfactual regret minimization.

Phase 10A: Expanded to support richer action abstraction (7 flop bet sizes
including overbets, 2 raise sizes) and stronger turn solving (4 bet sizes,
raise support, up to 15 turn cards).

HONEST SCOPE: Flop + optional turn subgames with small-to-medium ranges.
River is NOT supported.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.solver.base import (
    StrategyProvider,
    ProviderType,
    SolveConfig,
    SolveProgress,
)
from app.solver.cfr_solver import CfrSolver, SolveRequest, SolveOutput
from app.poker_engine.types import StrategyMatrix

logger = logging.getLogger(__name__)


class RealSolverProvider(StrategyProvider):
    """
    Real GTO solver provider using CFR+.

    CURRENT STATUS (Phase 3A): Functional for limited-scope solves.
    - Flop-only subgames
    - Small ranges (~30 combos per side max)
    - Pure Python implementation

    This is a REAL solver that produces genuine equilibrium approximations.
    """

    def __init__(self) -> None:
        self._progress = SolveProgress()
        self._cancelled = False
        self._solver: Optional[CfrSolver] = None

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.REAL_SOLVER

    @property
    def supports_iterative(self) -> bool:
        return True

    def generate_strategy(
        self,
        node_id: str,
        actions: list[dict],
        config: Optional[SolveConfig] = None,
    ) -> StrategyMatrix:
        """
        Generate strategy via real CFR+ solving.

        This runs a full solve and returns the strategy for the requested node.
        For efficiency, results should be cached from a full solve run.

        NOTE: This method solves the ENTIRE game tree, not just one node.
        For large-scale use, call solve_full() once and then extract
        strategies per node from the result.
        """
        if config is None:
            raise ValueError(
                "RealSolverProvider requires a SolveConfig with board, ranges, etc. "
                "Cannot generate strategy without configuration."
            )

        # Convert SolveConfig to SolveRequest
        request = SolveRequest(
            board=config.board,
            ip_range=config.ip_range or "",
            oop_range=config.oop_range or "",
            pot=config.pot,
            effective_stack=config.ip_stack,
            bet_sizes=config.allowed_bet_sizes,
            raise_sizes=config.allowed_raise_sizes,
            max_iterations=config.max_iterations,
        )

        self._solver = CfrSolver()
        output = self._solver.solve(
            request,
            progress_callback=self._on_progress,
            cancel_check=lambda: self._cancelled,
        )

        # Extract strategy for the requested node
        node_strategies = output.strategies.get(node_id, {})

        # Convert to StrategyMatrix format: {hand_label: {action_id: freq}}
        strategy_matrix: StrategyMatrix = {}
        for combo_str, action_freqs in node_strategies.items():
            strategy_matrix[combo_str] = action_freqs

        return strategy_matrix

    def solve_full(self, config: SolveConfig) -> SolveOutput:
        """
        Run a full solve and return the complete output.
        This is the preferred method for solve jobs.

        Phase 10A: Now passes turn-specific abstraction fields.
        """
        request = SolveRequest(
            board=config.board,
            ip_range=config.ip_range or "",
            oop_range=config.oop_range or "",
            pot=config.pot,
            effective_stack=config.ip_stack,
            bet_sizes=config.allowed_bet_sizes,
            raise_sizes=config.allowed_raise_sizes,
            max_iterations=config.max_iterations,
            # Phase 10A: turn abstraction defaults from SolveRequest
        )

        self._solver = CfrSolver()
        return self._solver.solve(
            request,
            progress_callback=self._on_progress,
            cancel_check=lambda: self._cancelled,
        )

    def _on_progress(self, info) -> None:
        """Update progress from solver callback."""
        self._progress = SolveProgress(
            iterations_done=info.iteration,
            total_iterations=info.total_iterations,
            exploitability=info.convergence_metric,
            converged=info.convergence_metric < 0.01,
            cancelled=False,
            message=f"CFR+ iteration {info.iteration}/{info.total_iterations}",
        )

    def get_progress(self) -> SolveProgress:
        return self._progress

    def cancel(self) -> None:
        self._cancelled = True
        self._progress.cancelled = True
        self._progress.message = "Cancelled by user"
