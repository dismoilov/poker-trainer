"""
Phase 17B: Convergence Target Recalibration Tests.

Tests cover:
  1. River preset differentiation
  2. Turn preset equivalence (honest behavior)
  3. Street-depth-aware convergence targets
  4. No regression to false convergence
  5. Quality labeling after recalibration
  6. Regression protection
"""
import pytest
import sys
sys.path.insert(0, '.')

from app.solver.solve_policy import (
    SolveDifficulty,
    StopReason,
    classify_solve_quality,
    compute_iteration_budget,
    IterationBudget,
)


# ══════════════════════════════════════════════════════════
# 1. River Preset Differentiation
# ══════════════════════════════════════════════════════════

class TestRiverPresetDifferentiation:
    """Phase 17B: River presets should produce different convergence targets."""

    def _river_difficulty(self):
        d = SolveDifficulty(ip_combos=15, oop_combos=18, matchups=270,
                            tree_nodes=1935, street_depth='flop_plus_turn_plus_river',
                            turn_cards=2, river_cards=2)
        d.classify()
        return d

    def test_river_fast_generous_target(self):
        """River fast should have generous convergence target (0.50)."""
        d = self._river_difficulty()
        b = compute_iteration_budget(d, 'fast')
        assert b.convergence_target == 0.50

    def test_river_standard_moderate_target(self):
        """River standard should have moderate convergence target (0.10)."""
        d = self._river_difficulty()
        b = compute_iteration_budget(d, 'standard')
        assert b.convergence_target == 0.10

    def test_river_deep_tight_target(self):
        """River deep should have tight convergence target (0.05)."""
        d = self._river_difficulty()
        b = compute_iteration_budget(d, 'deep')
        assert b.convergence_target == 0.05

    def test_river_fast_fewer_than_standard(self):
        """River fast should have lower or equal target iterations than standard."""
        d = self._river_difficulty()
        fast = compute_iteration_budget(d, 'fast')
        std = compute_iteration_budget(d, 'standard')
        assert fast.target_iterations <= std.target_iterations

    def test_river_standard_fewer_than_deep(self):
        """River standard should have fewer target iterations than deep."""
        d = self._river_difficulty()
        std = compute_iteration_budget(d, 'standard')
        deep = compute_iteration_budget(d, 'deep')
        assert std.target_iterations < deep.target_iterations

    def test_river_deep_more_patience(self):
        """River deep should have >= patience than standard."""
        d = self._river_difficulty()
        std = compute_iteration_budget(d, 'standard')
        deep = compute_iteration_budget(d, 'deep')
        assert deep.patience >= std.patience


# ══════════════════════════════════════════════════════════
# 2. Turn Preset Equivalence (Honest)
# ══════════════════════════════════════════════════════════

class TestTurnPresetEquivalence:
    """Phase 17B: Turn presets are equivalent because convergence genuinely stabilizes at 50i."""

    def _turn_difficulty(self):
        d = SolveDifficulty(ip_combos=15, oop_combos=18, matchups=270,
                            tree_nodes=456, street_depth='flop_plus_turn',
                            turn_cards=3, river_cards=0)
        d.classify()
        return d

    def test_turn_min_50_for_all_presets(self):
        """All turn presets should have min_iterations=50."""
        d = self._turn_difficulty()
        for preset in ['fast', 'standard', 'deep']:
            b = compute_iteration_budget(d, preset)
            assert b.min_iterations == 50, f"Turn {preset}: min should be 50"

    def test_turn_solve_identical_across_presets(self):
        """Turn solves should produce same iterations/convergence regardless of preset."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        results = {}
        for preset in ['fast', 'standard', 'deep']:
            req = SolveRequest(
                board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=500,
                max_raises=0, deterministic=True,
                include_turn=True, max_turn_cards=3,
                turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
            )
            req._preset = preset
            solver = CfrSolver()
            result = solver.solve(req, progress_callback=lambda info: None)
            results[preset] = (result.iterations, result.convergence_metric)

        # All presets should produce same iterations
        iters = [results[p][0] for p in ['fast', 'standard', 'deep']]
        assert iters[0] == iters[1] == iters[2], \
            f"Turn presets should be identical, got: fast={iters[0]}, std={iters[1]}, deep={iters[2]}"


# ══════════════════════════════════════════════════════════
# 3. River Solve Differentiation (Live)
# ══════════════════════════════════════════════════════════

class TestRiverSolveDifferentiation:
    """Phase 17B: River fast vs deep should produce different iteration counts."""

    def test_river_fast_vs_standard_different_iters(self):
        """River fast should run fewer iterations than standard."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        results = {}
        for preset in ['fast', 'standard']:
            req = SolveRequest(
                board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=500,
                max_raises=0, deterministic=True,
                include_turn=True, max_turn_cards=2,
                turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
                include_river=True, max_river_cards=2,
                river_bet_sizes=[0.5, 1.0], river_raise_sizes=[], river_max_raises=0,
            )
            req._preset = preset
            solver = CfrSolver()
            result = solver.solve(req, progress_callback=lambda info: None)
            results[preset] = result.iterations

        assert results['fast'] < results['standard'], \
            f"River fast ({results['fast']}i) should run fewer iters than standard ({results['standard']}i)"

    def test_river_standard_vs_deep_different_iters(self):
        """River standard should run fewer iterations than deep."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        results = {}
        for preset in ['standard', 'deep']:
            req = SolveRequest(
                board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=500,
                max_raises=0, deterministic=True,
                include_turn=True, max_turn_cards=2,
                turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
                include_river=True, max_river_cards=2,
                river_bet_sizes=[0.5, 1.0], river_raise_sizes=[], river_max_raises=0,
            )
            req._preset = preset
            solver = CfrSolver()
            result = solver.solve(req, progress_callback=lambda info: None)
            results[preset] = result.iterations

        assert results['standard'] < results['deep'], \
            f"River standard ({results['standard']}i) should run fewer iters than deep ({results['deep']}i)"


# ══════════════════════════════════════════════════════════
# 4. No False Convergence Regression
# ══════════════════════════════════════════════════════════

class TestNoFalseConvergence:
    """Phase 17B: Turn/river should NOT converge at 25 iterations."""

    def test_turn_min_50(self):
        """Turn solves should run at least 50 iterations."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=200,
            max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
        )
        req._preset = 'standard'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations >= 50

    def test_river_min_75(self):
        """River solves should run at least 75 iterations."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=200,
            max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
            include_river=True, max_river_cards=2,
            river_bet_sizes=[0.5, 1.0], river_raise_sizes=[], river_max_raises=0,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations >= 75


# ══════════════════════════════════════════════════════════
# 5. Flop Regression
# ══════════════════════════════════════════════════════════

class TestFlopRegression:
    """Phase 17B: Flop behavior should be unchanged."""

    def test_flop_min_25(self):
        """Flop min_iterations should be 25."""
        d = SolveDifficulty(ip_combos=6, oop_combos=3, matchups=18,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        b = compute_iteration_budget(d, 'standard')
        assert b.min_iterations == 25

    def test_flop_presets_unchanged(self):
        """Flop preset targets should use the original budget table."""
        d = SolveDifficulty(ip_combos=24, oop_combos=29, matchups=655,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        fast = compute_iteration_budget(d, 'fast')
        deep = compute_iteration_budget(d, 'deep')
        assert fast.target_iterations == 100  # heavy/fast
        assert deep.target_iterations == 350  # heavy/deep


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
