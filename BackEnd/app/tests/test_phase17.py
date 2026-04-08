"""
Phase 17: Practical Scaling Validation Tests.

Tests cover:
  1. Street-depth-aware min_iterations (core Phase 17 fix)
  2. Turn/river quality labeling after fix
  3. Preset behavior validation
  4. Safe/borderline/too-heavy boundary classification
  5. Rust path remains active for turn/river
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


# ── 1. Street-Depth-Aware min_iterations ──────────────────────────

class TestStreetDepthMinIterations:
    """Phase 17: Verify min_iterations scales with street depth."""

    def test_flop_min_25(self):
        """Flop solves should have min_iterations=25."""
        d = SolveDifficulty(ip_combos=6, oop_combos=3, matchups=18,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        b = compute_iteration_budget(d, 'standard')
        assert b.min_iterations == 25

    def test_turn_min_50(self):
        """Turn solves should have min_iterations=50."""
        d = SolveDifficulty(ip_combos=15, oop_combos=18, matchups=270,
                            tree_nodes=456, street_depth='flop_plus_turn',
                            turn_cards=3, river_cards=0)
        d.classify()
        b = compute_iteration_budget(d, 'standard')
        assert b.min_iterations == 50

    def test_river_min_75(self):
        """River solves should have min_iterations=75."""
        d = SolveDifficulty(ip_combos=15, oop_combos=18, matchups=270,
                            tree_nodes=1935, street_depth='flop_plus_turn_plus_river',
                            turn_cards=2, river_cards=2)
        d.classify()
        b = compute_iteration_budget(d, 'standard')
        assert b.min_iterations == 75

    def test_turn_min_applies_to_all_presets(self):
        """Turn min_iterations=50 applies to fast/standard/deep."""
        d = SolveDifficulty(ip_combos=15, oop_combos=18, matchups=270,
                            tree_nodes=456, street_depth='flop_plus_turn',
                            turn_cards=3, river_cards=0)
        d.classify()
        for preset in ['fast', 'standard', 'deep']:
            b = compute_iteration_budget(d, preset)
            assert b.min_iterations == 50, f"Turn {preset} min should be 50, got {b.min_iterations}"


# ── 2. Turn/River Quality After Fix ──────────────────────────────

class TestTurnRiverQualityAfterFix:
    """Phase 17: Verify turn/river solves no longer false-converge at 25 iterations."""

    def test_turn_solve_runs_50_iterations(self):
        """A turn solve should run >= 50 iterations, not stop at 25."""
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
        assert result.iterations >= 50, \
            f"Turn solve should run >= 50 iters, got {result.iterations}"

    def test_river_solve_runs_75_iterations(self):
        """A river solve should run >= 75 iterations, not stop at 25."""
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
        req._preset = 'standard'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations >= 75, \
            f"River solve should run >= 75 iters, got {result.iterations}"

    def test_turn_quality_is_good(self):
        """Turn solve should produce good quality at standard preset."""
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
        sq = result.metadata.get('solve_quality', {})
        assert sq.get('quality_class') in ('good', 'acceptable'), \
            f"Turn quality should be good/acceptable, got {sq.get('quality_class')}"


# ── 3. Preset Behavior Validation ────────────────────────────────

class TestPresetBehavior:
    """Phase 17: Verify preset behavior is sensible."""

    def test_fast_runs_fewer_iterations_than_deep(self):
        """Fast preset should target fewer iterations than deep."""
        d = SolveDifficulty(ip_combos=24, oop_combos=29, matchups=655,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        fast = compute_iteration_budget(d, 'fast')
        deep = compute_iteration_budget(d, 'deep')
        assert fast.target_iterations < deep.target_iterations

    def test_fast_has_higher_conv_target(self):
        """Fast preset should have higher (more lenient) convergence target."""
        d = SolveDifficulty(ip_combos=24, oop_combos=29, matchups=655,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        fast = compute_iteration_budget(d, 'fast')
        deep = compute_iteration_budget(d, 'deep')
        assert fast.convergence_target > deep.convergence_target

    def test_deep_has_more_patience(self):
        """Deep preset should have more patience for plateau detection."""
        d = SolveDifficulty(ip_combos=24, oop_combos=29, matchups=655,
                            tree_nodes=57, street_depth='flop_only',
                            turn_cards=0, river_cards=0)
        d.classify()
        fast = compute_iteration_budget(d, 'fast')
        deep = compute_iteration_budget(d, 'deep')
        assert deep.patience > fast.patience


# ── 4. Safe/Borderline/Too-Heavy Boundaries ──────────────────────

class TestBoundaryClassification:
    """Phase 17: Verify workloads near limits are handled correctly."""

    def test_80_combos_is_limit(self):
        """80 combos per side is the max for flop."""
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE
        assert MAX_COMBOS_PER_SIDE == 80

    def test_50_combos_turn_limit(self):
        """50 combos per side is the max for turn."""
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE_TURN
        assert MAX_COMBOS_PER_SIDE_TURN == 50

    def test_30_combos_river_limit(self):
        """30 combos per side is the max for river."""
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE_RIVER
        assert MAX_COMBOS_PER_SIDE_RIVER == 30

    def test_over_limit_raises_error(self):
        """Exceeding combo limit should raise ValueError."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Td", "8s", "3c"],
            ip_range="AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs",
            oop_range="AKo,AQo,AJo,ATo,KQs,KJs,KTs,QJs,QTs,JTs,KQo,KJo,KTo,QJo,QTo,JTo",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = 'standard'
        solver = CfrSolver()
        with pytest.raises(ValueError, match="max allowed is 80"):
            solver.solve(req, progress_callback=lambda info: None)


# ── 5. Rust Path Active for Turn/River ────────────────────────────

class TestRustPathTurnRiver:
    """Phase 17: Verify Rust path is active for turn and river solves."""

    def test_rust_active_for_turn(self):
        """Turn solve should log Rust path."""
        import logging
        log_msgs = []
        handler = logging.Handler()
        handler.emit = lambda r: log_msgs.append(r.getMessage())
        logger = logging.getLogger('app.solver.cfr_solver')
        logger.addHandler(handler)
        try:
            from app.solver.cfr_solver import CfrSolver, SolveRequest
            req = SolveRequest(
                board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=100,
                max_raises=0, deterministic=True,
                include_turn=True, max_turn_cards=2,
                turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
            )
            req._preset = 'fast'
            solver = CfrSolver()
            solver.solve(req, progress_callback=lambda info: None)
            rust_msgs = [m for m in log_msgs if 'Rust CFR' in m or 'using Rust' in m]
            assert len(rust_msgs) > 0, "Turn solve should log Rust path"
        finally:
            logger.removeHandler(handler)


# ── 6. Regression Protection ──────────────────────────────────────

class TestPhase17Regression:
    """Phase 17: Ensure existing functionality is not broken."""

    def test_flop_solve_unchanged(self):
        """Flop solve behavior should be unchanged from Phase 16."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = 'standard'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.strategies is not None
        assert result.stop_reason in ('converged', 'max_iterations', 'plateau')
        sq = result.metadata.get('solve_quality', {})
        assert sq.get('quality_class') in ('good', 'acceptable')

    def test_stop_reason_metadata_present(self):
        """Result should always have stop_reason and quality in metadata."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = 'standard'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert 'stop_reason' in result.metadata
        assert 'solve_quality' in result.metadata
        assert 'difficulty_grade' in result.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
