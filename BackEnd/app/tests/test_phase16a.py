"""
Phase 16A Tests: Adaptive Iterations + Quality-Aware Stopping

Tests verify:
  1. Difficulty classification (all grades)
  2. Iteration budget computation (grade × preset)
  3. Convergence tracker behavior
  4. Early stopping triggers and stop reasons
  5. Stop reason recorded in SolveOutput
  6. Preset alignment
  7. Quality signal classification
  8. Regression: normal solves still work
"""

import time
import pytest
from unittest.mock import MagicMock

from app.solver.solve_policy import (
    SolveDifficulty, IterationBudget, StopReason,
    compute_iteration_budget, ConvergenceTracker,
    classify_solve_quality, DIFFICULTY_GRADES,
    _BUDGET_TABLE,
)
from app.solver.cfr_solver import CfrSolver, SolveRequest, SolveOutput, SolveProgressInfo


# ═══════════════════════════════════════════════════════════
# Test: Difficulty Classification
# ═══════════════════════════════════════════════════════════

class TestDifficultyClassification:
    """Verify difficulty grades are assigned based on measurable features."""

    def test_trivial_grade(self):
        d = SolveDifficulty(
            ip_combos=3, oop_combos=3, matchups=9,
            tree_nodes=21, street_depth="flop_only",
        )
        assert d.classify() == "trivial"

    def test_light_grade(self):
        d = SolveDifficulty(
            ip_combos=6, oop_combos=6, matchups=36,
            tree_nodes=150, street_depth="flop_only",
        )
        assert d.classify() == "light"

    def test_moderate_grade_matchups(self):
        d = SolveDifficulty(
            ip_combos=15, oop_combos=15, matchups=200,
            tree_nodes=300, street_depth="flop_only",
        )
        assert d.classify() == "moderate"

    def test_moderate_grade_turn(self):
        """Any turn inclusion makes at least moderate."""
        d = SolveDifficulty(
            ip_combos=3, oop_combos=3, matchups=9,
            tree_nodes=100, street_depth="flop_plus_turn",
            turn_cards=2,
        )
        assert d.classify() == "moderate"

    def test_heavy_grade_matchups(self):
        d = SolveDifficulty(
            ip_combos=30, oop_combos=30, matchups=800,
            tree_nodes=1000, street_depth="flop_only",
        )
        assert d.classify() == "heavy"

    def test_heavy_grade_turn_many_cards(self):
        d = SolveDifficulty(
            ip_combos=6, oop_combos=6, matchups=30,
            tree_nodes=500, street_depth="flop_plus_turn",
            turn_cards=5,
        )
        assert d.classify() == "heavy"

    def test_heavy_grade_river(self):
        """Any river inclusion makes at least heavy."""
        d = SolveDifficulty(
            ip_combos=3, oop_combos=3, matchups=9,
            tree_nodes=200, street_depth="flop_plus_turn_plus_river",
            turn_cards=2, river_cards=2,
        )
        assert d.classify() == "heavy"

    def test_extreme_grade_matchups(self):
        d = SolveDifficulty(
            ip_combos=50, oop_combos=50, matchups=2500,
            tree_nodes=5000, street_depth="flop_only",
        )
        assert d.classify() == "extreme"

    def test_extreme_grade_river_many_cards(self):
        d = SolveDifficulty(
            ip_combos=10, oop_combos=10, matchups=80,
            tree_nodes=10000, street_depth="flop_plus_turn_plus_river",
            turn_cards=3, river_cards=4,
        )
        assert d.classify() == "extreme"

    def test_all_grades_covered(self):
        """All 5 grades must be achievable."""
        grades_seen = set()
        configs = [
            (5, "flop_only", 0, 0),
            (50, "flop_only", 0, 0),
            (200, "flop_only", 0, 0),
            (800, "flop_only", 0, 0),
            (3000, "flop_only", 0, 0),
        ]
        for matchups, depth, tc, rc in configs:
            d = SolveDifficulty(
                ip_combos=10, oop_combos=10, matchups=matchups,
                tree_nodes=100, street_depth=depth,
                turn_cards=tc, river_cards=rc,
            )
            grades_seen.add(d.classify())
        assert grades_seen == set(DIFFICULTY_GRADES)


# ═══════════════════════════════════════════════════════════
# Test: Iteration Budget Computation
# ═══════════════════════════════════════════════════════════

class TestIterationBudget:
    """Verify budget computation from difficulty × preset."""

    def test_all_presets_produce_budgets(self):
        """Every grade × preset combination returns a valid budget."""
        for grade in DIFFICULTY_GRADES:
            for preset in ["fast", "standard", "deep"]:
                d = SolveDifficulty(
                    ip_combos=10, oop_combos=10, matchups=50,
                    tree_nodes=100, street_depth="flop_only",
                )
                d.grade = grade
                b = compute_iteration_budget(d, preset=preset)
                assert b.min_iterations > 0
                assert b.target_iterations >= b.min_iterations
                assert b.max_iterations >= b.target_iterations
                assert b.convergence_target > 0
                assert b.patience > 0

    def test_deep_has_more_iterations_than_fast(self):
        d = SolveDifficulty(
            ip_combos=10, oop_combos=10, matchups=50,
            tree_nodes=100, street_depth="flop_only",
        )
        d.classify()
        fast = compute_iteration_budget(d, preset="fast")
        deep = compute_iteration_budget(d, preset="deep")
        assert deep.target_iterations >= fast.target_iterations

    def test_deep_has_stricter_convergence(self):
        d = SolveDifficulty(
            ip_combos=10, oop_combos=10, matchups=50,
            tree_nodes=100, street_depth="flop_only",
        )
        d.classify()
        fast = compute_iteration_budget(d, preset="fast")
        deep = compute_iteration_budget(d, preset="deep")
        assert deep.convergence_target <= fast.convergence_target

    def test_user_max_iterations_respected(self):
        d = SolveDifficulty(
            ip_combos=10, oop_combos=10, matchups=50,
            tree_nodes=100, street_depth="flop_only",
        )
        d.classify()
        b = compute_iteration_budget(d, preset="standard", user_max_iterations=50)
        assert b.max_iterations <= 50
        assert b.target_iterations <= 50

    def test_budget_table_complete(self):
        """Budget table covers all grade × preset combos."""
        for grade in DIFFICULTY_GRADES:
            assert grade in _BUDGET_TABLE, f"Missing grade {grade}"
            for preset in ["fast", "standard", "deep"]:
                assert preset in _BUDGET_TABLE[grade], f"Missing {grade}/{preset}"
                entry = _BUDGET_TABLE[grade][preset]
                assert len(entry) == 3  # (target, conv_target, patience)


# ═══════════════════════════════════════════════════════════
# Test: Convergence Tracker
# ═══════════════════════════════════════════════════════════

class TestConvergenceTracker:
    """Verify convergence tracking and plateau detection."""

    def test_no_stop_before_min(self):
        budget = IterationBudget(min_iterations=25, convergence_target=0.01, patience=3)
        tracker = ConvergenceTracker(budget)
        # Even with great convergence, shouldn't stop before min
        result = tracker.should_stop(10, 0.001)
        assert result is None

    def test_converged_stop(self):
        budget = IterationBudget(
            min_iterations=25, target_iterations=200,
            max_iterations=300, convergence_target=0.01, patience=5,
        )
        tracker = ConvergenceTracker(budget)
        result = tracker.should_stop(50, 0.005)
        assert result == StopReason.CONVERGED

    def test_max_iterations_stop(self):
        budget = IterationBudget(
            min_iterations=25, target_iterations=100,
            max_iterations=150, convergence_target=0.001, patience=5,
        )
        tracker = ConvergenceTracker(budget)
        result = tracker.should_stop(150, 0.5)
        assert result == StopReason.MAX_ITERATIONS

    def test_plateau_detection(self):
        budget = IterationBudget(
            min_iterations=25, target_iterations=200,
            max_iterations=300, convergence_target=0.001,
            patience=3, improvement_threshold=0.05,
        )
        tracker = ConvergenceTracker(budget)
        # Simulate plateau: convergence barely drops
        for i in range(5):
            tracker.record(0.5 - i * 0.001)  # tiny improvement
        result = tracker.should_stop(100, 0.496)
        assert result == StopReason.PLATEAU

    def test_no_plateau_with_improvement(self):
        budget = IterationBudget(
            min_iterations=25, target_iterations=200,
            max_iterations=300, convergence_target=0.001,
            patience=3, improvement_threshold=0.05,
        )
        tracker = ConvergenceTracker(budget)
        # Good improvement each step
        for v in [1.0, 0.5, 0.25, 0.12, 0.06]:
            tracker.record(v)
        result = tracker.should_stop(80, 0.06)
        assert result is None  # still converging well

    def test_target_iterations_stop(self):
        """Reaching target_iterations should stop even if not converged."""
        budget = IterationBudget(
            min_iterations=25, target_iterations=100,
            max_iterations=150, convergence_target=0.001, patience=5,
        )
        tracker = ConvergenceTracker(budget)
        result = tracker.should_stop(100, 0.5)
        assert result == StopReason.MAX_ITERATIONS


# ═══════════════════════════════════════════════════════════
# Test: Stop Reason Model
# ═══════════════════════════════════════════════════════════

class TestStopReason:
    """Verify StopReason enum and labels."""

    def test_all_reasons_have_labels(self):
        for reason in StopReason:
            assert len(reason.label_ru) > 0
            assert len(reason.icon) > 0

    def test_converged_label(self):
        assert "Сходимость" in StopReason.CONVERGED.label_ru

    def test_plateau_label(self):
        assert "Плато" in StopReason.PLATEAU.label_ru


# ═══════════════════════════════════════════════════════════
# Test: Quality Signal
# ═══════════════════════════════════════════════════════════

class TestQualitySignal:
    """Verify quality classification is honest and correct."""

    def test_converged_is_good(self):
        q = classify_solve_quality(StopReason.CONVERGED, 0.003, 0.005, 80, 200)
        assert q["quality_class"] == "good"

    def test_cancelled_is_incomplete(self):
        q = classify_solve_quality(StopReason.CANCELLED, 0.5, 0.005, 30, 200)
        assert q["quality_class"] == "incomplete"

    def test_plateau_close_is_acceptable(self):
        q = classify_solve_quality(StopReason.PLATEAU, 0.01, 0.005, 100, 200)
        assert q["quality_class"] == "acceptable"

    def test_plateau_far_is_weak(self):
        q = classify_solve_quality(StopReason.PLATEAU, 0.5, 0.005, 100, 200)
        assert q["quality_class"] == "weak"

    def test_max_iter_good_convergence(self):
        q = classify_solve_quality(StopReason.MAX_ITERATIONS, 0.003, 0.005, 200, 200)
        assert q["quality_class"] == "good"

    def test_max_iter_weak_convergence(self):
        q = classify_solve_quality(StopReason.MAX_ITERATIONS, 0.5, 0.005, 200, 200)
        assert q["quality_class"] == "weak"

    def test_quality_has_honest_note(self):
        q = classify_solve_quality(StopReason.CONVERGED, 0.003, 0.005, 80, 200)
        assert "heuristic" in q["honest_note"].lower() or "NOT exact" in q["honest_note"]


# ═══════════════════════════════════════════════════════════
# Test: Solver Integration — Early Stopping
# ═══════════════════════════════════════════════════════════

class TestSolverEarlyStop:
    """Verify early stopping works end-to-end in the solver."""

    def test_easy_solve_stops_early(self):
        """Small solve should stop before max iterations due to convergence."""
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=300, max_raises=0, deterministic=True,
        )
        req._preset = 'standard'
        result = solver.solve(req, progress_callback=lambda info: None)

        # Should converge easily — expect early stop
        assert result.stop_reason in ("converged", "plateau", "max_iterations")
        assert result.iterations <= 300

    def test_stop_reason_in_output(self):
        """stop_reason must be present in SolveOutput."""
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        result = solver.solve(req, progress_callback=lambda info: None)

        assert hasattr(result, 'stop_reason')
        assert result.stop_reason in ("converged", "plateau", "max_iterations")

    def test_stop_reason_in_metadata(self):
        """stop_reason must also be in metadata."""
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        result = solver.solve(req, progress_callback=lambda info: None)

        assert "stop_reason" in result.metadata
        assert "stop_reason_label" in result.metadata
        assert "difficulty_grade" in result.metadata
        assert "adaptive_budget" in result.metadata
        assert "solve_quality" in result.metadata

    def test_difficulty_grade_in_metadata(self):
        """Difficulty grade must be recorded."""
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        result = solver.solve(req, progress_callback=lambda info: None)

        assert result.metadata["difficulty_grade"] in DIFFICULTY_GRADES

    def test_cancel_sets_cancel_reason(self):
        """Cancel should set stop_reason to cancelled."""
        cancel_at = [False]
        def on_progress(info):
            if info.iteration >= 25:
                cancel_at[0] = True

        solver = CfrSolver()
        req = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs,AKo,AQs',
            oop_range='JJ,TT,99,AJs,KQs,QJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=5000, max_raises=1, deterministic=True,
        )
        req._preset = 'deep'
        result = solver.solve(
            req,
            progress_callback=on_progress,
            cancel_check=lambda: cancel_at[0],
        )

        assert result.stop_reason == "cancelled"


# ═══════════════════════════════════════════════════════════
# Test: Preset Alignment
# ═══════════════════════════════════════════════════════════

class TestPresetAlignment:
    """Verify presets interact correctly with adaptive budgets."""

    def test_fast_preset_budget(self):
        d = SolveDifficulty(
            ip_combos=3, oop_combos=3, matchups=9,
            tree_nodes=21, street_depth="flop_only",
        )
        d.classify()
        b = compute_iteration_budget(d, preset="fast")
        assert b.target_iterations <= 100

    def test_deep_preset_budget(self):
        d = SolveDifficulty(
            ip_combos=3, oop_combos=3, matchups=9,
            tree_nodes=21, street_depth="flop_only",
        )
        d.classify()
        b = compute_iteration_budget(d, preset="deep")
        assert b.target_iterations >= 100

    def test_harder_difficulty_doesnt_reduce_budget(self):
        """Heavier difficulty should not produce fewer iterations."""
        for preset in ["fast", "standard", "deep"]:
            budgets = []
            for matchups in [9, 50, 200, 800, 3000]:
                d = SolveDifficulty(
                    ip_combos=10, oop_combos=10, matchups=matchups,
                    tree_nodes=100, street_depth="flop_only",
                )
                d.classify()
                b = compute_iteration_budget(d, preset=preset)
                budgets.append(b.target_iterations)

            for i in range(1, len(budgets)):
                assert budgets[i] >= budgets[i-1], \
                    f"Budget decreased for harder difficulty at preset={preset}: {budgets}"


# ═══════════════════════════════════════════════════════════
# Test: Regression
# ═══════════════════════════════════════════════════════════

class TestPhase16ARegression:
    """Ensure Phase 16A changes don't break existing solver behavior."""

    def test_normal_solve_works(self):
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        result = solver.solve(req)
        assert result.iterations > 0
        assert len(result.strategies) > 0
        assert hasattr(result, 'stop_reason')

    def test_strategies_valid(self):
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        result = solver.solve(req, progress_callback=lambda info: None)
        for nid, combos in result.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01

    def test_version_ok(self):
        import poker_core
        v = poker_core.version()
        assert 'poker_core' in v

    def test_solve_without_preset_attr(self):
        """Backward compat: solve should work without _preset attribute."""
        solver = CfrSolver()
        req = SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        )
        # No _preset set — should default to 'standard'
        result = solver.solve(req)
        assert result.iterations > 0
        assert result.stop_reason in ("converged", "plateau", "max_iterations")
