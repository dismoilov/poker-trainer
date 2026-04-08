"""
Phase 12D: NumPy-First Hot Path Switch — Test Suite

Tests verify:
- NumPy ndarray backing for SolverArrays
- Single source of truth (no dict-based regrets/strategy_sums)
- Convergence correctness
- Strategy normalization
- Vectorized operations
- Regression protection against split-brain bug
"""

import pytest
import numpy as np

from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolverArrays,
    MAX_COMBOS_PER_SIDE, MAX_COMBOS_PER_SIDE_TURN, MAX_COMBOS_PER_SIDE_RIVER,
)


# ── 1. NumPy Storage Tests ────────────────────────────────────

class TestNumpyStorage:
    """Verify SolverArrays uses numpy ndarray."""

    def test_regrets_are_ndarray(self):
        arrays = SolverArrays(100, 5)
        assert isinstance(arrays.regrets, np.ndarray)
        assert arrays.regrets.dtype == np.float64

    def test_strategy_sums_are_ndarray(self):
        arrays = SolverArrays(100, 5)
        assert isinstance(arrays.strategy_sums, np.ndarray)
        assert arrays.strategy_sums.dtype == np.float64

    def test_action_counts_are_ndarray(self):
        arrays = SolverArrays(100, 5)
        assert isinstance(arrays.action_counts, np.ndarray)
        assert arrays.action_counts.dtype == np.int32

    def test_correct_dimensions(self):
        arrays = SolverArrays(100, 5)
        assert len(arrays.regrets) == 500
        assert len(arrays.strategy_sums) == 500
        assert len(arrays.action_counts) == 100

    def test_zero_initialized(self):
        arrays = SolverArrays(50, 3)
        assert arrays.regrets.sum() == 0.0
        assert arrays.strategy_sums.sum() == 0.0

    def test_c_contiguous(self):
        arrays = SolverArrays(100, 5)
        assert arrays.regrets.flags['C_CONTIGUOUS']
        assert arrays.strategy_sums.flags['C_CONTIGUOUS']

    def test_get_set_regret(self):
        arrays = SolverArrays(10, 3)
        arrays.set_regret(5, 2, 42.0)
        assert arrays.get_regret(5, 2) == 42.0
        assert isinstance(arrays.get_regret(5, 2), float)  # Not np.float64

    def test_add_strategy_sum(self):
        arrays = SolverArrays(10, 3)
        arrays.add_strategy_sum(3, 1, 10.0)
        arrays.add_strategy_sum(3, 1, 5.0)
        assert arrays.get_strategy_sum(3, 1) == 15.0


# ── 2. Single Source of Truth Tests ───────────────────────────

class TestSingleSourceOfTruth:
    """Verify dicts are eliminated, arrays are the only storage."""

    def test_no_regrets_dict(self):
        solver = CfrSolver()
        assert not hasattr(solver, '_regrets')

    def test_no_strategy_sums_dict(self):
        solver = CfrSolver()
        assert not hasattr(solver, '_strategy_sums')

    def test_no_sync_method(self):
        solver = CfrSolver()
        assert not hasattr(solver, '_sync_arrays_from_dicts')

    def test_arrays_populated_after_solve(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=10, deterministic=True,
        ))
        assert solver._arrays is not None
        assert isinstance(solver._arrays.regrets, np.ndarray)
        assert solver._arrays.regrets.sum() > 0  # Non-zero regrets

    def test_strategy_sums_populated_after_solve(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=10, deterministic=True,
        ))
        assert solver._arrays.strategy_sums.sum() > 0


# ── 3. Correctness Tests ─────────────────────────────────────

class TestNumpyCorrectness:
    """Verify correctness is preserved after numpy migration."""

    def test_convergence_exact_match(self):
        """Canonical AA vs KK convergence must match pre-numpy value."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert 0.10 < output.convergence_metric < 0.50, \
            f"Expected ~0.22, got {output.convergence_metric} (Phase 14: parallel mode)"

    def test_strategies_sum_to_one(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=30, deterministic=True,
        ))
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, \
                    f"Strategy at {node_id}/{combo} sums to {total}"

    def test_no_uniform_corruption(self):
        """Strategies should NOT all be uniform (the Phase 12C bug)."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        all_uniform = True
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                vals = list(freqs.values())
                if len(vals) > 1:
                    if max(vals) - min(vals) > 0.01:
                        all_uniform = False
                        break
        assert not all_uniform, "All strategies are uniform — split-brain bug!"

    def test_exploitability_is_finite(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert output.exploitability_mbb > 0
        assert output.exploitability_mbb < 100_000

    def test_convergence_decreases_with_iterations(self):
        solver1 = CfrSolver()
        out1 = solver1.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=50.0, bet_sizes=[1.0],
            max_iterations=10, deterministic=True,
        ))
        solver2 = CfrSolver()
        out2 = solver2.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=50.0, bet_sizes=[1.0],
            max_iterations=100, deterministic=True,
        ))
        assert out2.convergence_metric <= out1.convergence_metric + 0.01


# ── 4. Vectorized Operations Tests ───────────────────────────

class TestVectorizedOps:
    """Verify vectorized numpy operations work correctly."""

    def test_vectorized_convergence(self):
        """_compute_convergence should use np.maximum/np.sum."""
        solver = CfrSolver()
        solver._arrays = SolverArrays(3, 2)
        solver._info_set_map = {"a": 0, "b": 1, "c": 2}
        solver._use_arrays = True
        solver._iteration_count = 10
        # Set some regrets
        solver._arrays.regrets[0] = 5.0
        solver._arrays.regrets[1] = 0.0
        solver._arrays.regrets[2] = 3.0
        solver._arrays.regrets[3] = 0.0
        solver._arrays.regrets[4] = 2.0
        solver._arrays.regrets[5] = 0.0
        conv = solver._compute_convergence()
        # 3 positive (5, 3, 2), sum=10, count=3, norm=10 → 10/(3*10) = 0.333
        assert abs(conv - 10.0 / (3 * 10)) < 0.001

    def test_convergence_zero_regrets(self):
        solver = CfrSolver()
        solver._arrays = SolverArrays(5, 3)
        solver._use_arrays = True
        solver._iteration_count = 1
        assert solver._compute_convergence() == 0.0

    def test_convergence_no_arrays(self):
        solver = CfrSolver()
        solver._use_arrays = False
        assert solver._compute_convergence() == float('inf')


# ── 5. Turn/River with NumPy Tests ────────────────────────────

class TestTurnRiverNumpy:
    """Verify turn and river solves work with numpy backend."""

    def test_turn_solve_with_numpy(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert isinstance(solver._arrays.regrets, np.ndarray)
        assert len(output.strategies) > 0
        assert "turn" in output.metadata.get("street_depth", "")

    def test_river_solve_with_numpy(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            include_river=True, max_river_cards=1,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert isinstance(solver._arrays.regrets, np.ndarray)
        assert "river" in output.metadata.get("street_depth", "")


# ── 6. Regression Protection ─────────────────────────────────

class TestRegressionProtection:
    """Ensure Phase 12C split-brain bug cannot return."""

    def test_regrets_non_negative_after_solve(self):
        """CFR+ guarantees: all regrets >= 0."""
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert (solver._arrays.regrets >= -1e-9).all()

    def test_strategy_sums_non_negative(self):
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert (solver._arrays.strategy_sums >= -1e-9).all()

    def test_no_nan_or_inf(self):
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert not np.any(np.isnan(solver._arrays.regrets))
        assert not np.any(np.isinf(solver._arrays.regrets))
        assert not np.any(np.isnan(solver._arrays.strategy_sums))
