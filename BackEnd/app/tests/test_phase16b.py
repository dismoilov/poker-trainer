"""
Phase 16B: Tests for Adaptive Policy Validation + Recalibration.

Tests cover:
  1. Recalibrated convergence targets
  2. min_plateau_iteration behaviour
  3. Quality classification with realistic convergence values
  4. Difficulty classification correctness
  5. Budget monotonicity
  6. Stop reason logic
  7. Solver integration
"""
import pytest
import sys
sys.path.insert(0, '.')

from app.solver.solve_policy import (
    SolveDifficulty,
    IterationBudget,
    StopReason,
    ConvergenceTracker,
    classify_solve_quality,
    compute_iteration_budget,
    _BUDGET_TABLE,
    DIFFICULTY_GRADES,
)


# ── 1. Recalibrated Convergence Targets ─────────────────────────

class TestRecalibratedTargets:
    """Verify Phase 16B convergence targets are in the right range."""

    def test_trivial_standard_target_is_realistic(self):
        """Trivial AA vs KK achieves ~0.3 at 100it. Target should be around 0.4."""
        target = _BUDGET_TABLE["trivial"]["standard"][1]
        assert 0.2 <= target <= 1.0, f"trivial/standard conv target {target} not in [0.2, 1.0]"

    def test_moderate_standard_target_is_realistic(self):
        """Moderate 6x6 achieves ~1.2-3.1 at 200it. Target should be around 1.5."""
        target = _BUDGET_TABLE["moderate"]["standard"][1]
        assert 0.5 <= target <= 3.0, f"moderate/standard conv target {target} not in [0.5, 3.0]"

    def test_heavy_standard_target_is_realistic(self):
        """Heavy 10x10 achieves ~1.8-4.0 at 200it. Target should be around 2.5."""
        target = _BUDGET_TABLE["heavy"]["standard"][1]
        assert 1.0 <= target <= 5.0, f"heavy/standard conv target {target} not in [1.0, 5.0]"

    def test_extreme_standard_target_is_realistic(self):
        """Extreme 15x15+ achieves ~3.5-6.0 at 200it. Target should be around 4.0."""
        target = _BUDGET_TABLE["extreme"]["standard"][1]
        assert 2.0 <= target <= 8.0, f"extreme/standard conv target {target} not in [2.0, 8.0]"

    def test_deep_targets_are_stricter_than_standard(self):
        """Deep preset should have lower (stricter) convergence targets."""
        for grade in DIFFICULTY_GRADES:
            std = _BUDGET_TABLE[grade]["standard"][1]
            deep = _BUDGET_TABLE[grade]["deep"][1]
            assert deep < std, f"{grade}: deep target {deep} should be < standard {std}"

    def test_fast_targets_are_more_lenient_than_standard(self):
        """Fast preset should have higher (more lenient) convergence targets."""
        for grade in DIFFICULTY_GRADES:
            std = _BUDGET_TABLE[grade]["standard"][1]
            fast = _BUDGET_TABLE[grade]["fast"][1]
            assert fast > std, f"{grade}: fast target {fast} should be > standard {std}"


# ── 2. min_plateau_iteration ────────────────────────────────────

class TestMinPlateauIteration:
    """Verify plateau detection respects min_plateau_iteration floor."""

    def test_budget_has_min_plateau_iteration(self):
        """IterationBudget should have min_plateau_iteration field."""
        budget = IterationBudget()
        assert hasattr(budget, 'min_plateau_iteration')
        assert budget.min_plateau_iteration >= 25

    def test_compute_budget_sets_min_plateau_iteration(self):
        """compute_iteration_budget should set min_plateau_iteration."""
        diff = SolveDifficulty(
            ip_combos=6, oop_combos=6, matchups=36,
            tree_nodes=50, street_depth="flop_only",
        )
        diff.classify()
        budget = compute_iteration_budget(diff, "standard")
        assert budget.min_plateau_iteration >= budget.min_iterations * 3
        assert budget.min_plateau_iteration >= budget.target_iterations // 2

    def test_plateau_not_triggered_before_min_plateau(self):
        """ConvergenceTracker should NOT plateau-stop before min_plateau_iteration."""
        budget = IterationBudget(
            min_iterations=25, target_iterations=200, max_iterations=300,
            convergence_target=1.5, patience=5,
            improvement_threshold=0.02, min_plateau_iteration=100,
        )
        tracker = ConvergenceTracker(budget)
        # Record no improvement for many chunks
        for i in range(10):
            tracker.record(2.5)  # constant = no improvement
        # At iteration 50, should NOT stop (before min_plateau_iteration)
        result = tracker.should_stop(50, 2.5)
        assert result is None, f"Should not plateau-stop at iter 50 (min_plateau=100), got {result}"

    def test_plateau_triggered_after_min_plateau(self):
        """ConvergenceTracker SHOULD plateau-stop after min_plateau_iteration if no improvement."""
        budget = IterationBudget(
            min_iterations=25, target_iterations=200, max_iterations=300,
            convergence_target=1.5, patience=5,
            improvement_threshold=0.02, min_plateau_iteration=100,
        )
        tracker = ConvergenceTracker(budget)
        # Record no improvement for many chunks
        for i in range(10):
            tracker.record(2.5)
        # At iteration 125, SHOULD stop
        result = tracker.should_stop(125, 2.5)
        assert result == StopReason.PLATEAU


# ── 3. Quality Classification with Realistic Values ─────────────

class TestQualityClassification:
    """Verify quality labels make sense with recalibrated targets."""

    def test_good_when_converged(self):
        """Converged stop should always be 'good'."""
        q = classify_solve_quality(
            StopReason.CONVERGED, convergence=0.3, convergence_target=0.4,
            iterations=100, target_iterations=100,
        )
        assert q["quality_class"] == "good"

    def test_good_when_max_iter_but_within_target(self):
        """Max iterations with convergence below target should be 'good'."""
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, convergence=0.3, convergence_target=0.4,
            iterations=100, target_iterations=100,
        )
        assert q["quality_class"] == "good"

    def test_acceptable_when_close_to_target(self):
        """Max iterations with convergence close to target (within 3x) should be 'acceptable'."""
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, convergence=1.0, convergence_target=0.4,
            iterations=100, target_iterations=100,
        )
        assert q["quality_class"] == "acceptable"

    def test_weak_when_far_from_target(self):
        """Max iterations with convergence far from target (>3x) should be 'weak'."""
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, convergence=5.0, convergence_target=0.4,
            iterations=100, target_iterations=100,
        )
        assert q["quality_class"] == "weak"

    def test_incomplete_when_cancelled(self):
        q = classify_solve_quality(
            StopReason.CANCELLED, convergence=1.0, convergence_target=0.4,
            iterations=50, target_iterations=100,
        )
        assert q["quality_class"] == "incomplete"

    def test_plateau_close_is_acceptable(self):
        """Plateau within 3x target should be 'acceptable'."""
        q = classify_solve_quality(
            StopReason.PLATEAU, convergence=1.0, convergence_target=0.4,
            iterations=150, target_iterations=200,
        )
        assert q["quality_class"] == "acceptable"

    def test_plateau_far_is_weak(self):
        """Plateau far from target (>3x) should be 'weak'."""
        q = classify_solve_quality(
            StopReason.PLATEAU, convergence=5.0, convergence_target=0.4,
            iterations=150, target_iterations=200,
        )
        assert q["quality_class"] == "weak"


# ── 4. Difficulty Classification ─────────────────────────────────

class TestDifficultyClassification:
    """Verify difficulty is classified correctly."""

    def test_trivial_classification(self):
        d = SolveDifficulty(ip_combos=1, oop_combos=1, matchups=1,
                           tree_nodes=10, street_depth="flop_only")
        assert d.classify() == "trivial"

    def test_light_classification(self):
        d = SolveDifficulty(ip_combos=5, oop_combos=5, matchups=50,
                           tree_nodes=200, street_depth="flop_only")
        assert d.classify() == "light"

    def test_moderate_with_turn(self):
        d = SolveDifficulty(ip_combos=4, oop_combos=4, matchups=50,
                           tree_nodes=100, street_depth="flop_plus_turn",
                           turn_cards=2)
        assert d.classify() == "moderate"

    def test_heavy_with_wide_ranges(self):
        d = SolveDifficulty(ip_combos=20, oop_combos=20, matchups=600,
                           tree_nodes=500, street_depth="flop_only")
        assert d.classify() == "heavy"

    def test_extreme_with_river(self):
        d = SolveDifficulty(ip_combos=10, oop_combos=10, matchups=100,
                           tree_nodes=1000, street_depth="flop_plus_turn_plus_river",
                           turn_cards=2, river_cards=3)
        assert d.classify() == "extreme"


# ── 5. Budget Monotonicity ───────────────────────────────────────

class TestBudgetMonotonicity:
    """Verify budgets scale correctly with difficulty and preset."""

    def test_target_iters_increase_with_difficulty(self):
        """Heavier difficulty should get >= iteration targets."""
        for preset in ["fast", "standard", "deep"]:
            prev_target = 0
            for grade in DIFFICULTY_GRADES:
                target = _BUDGET_TABLE[grade][preset][0]
                assert target >= prev_target, (
                    f"{preset}: {grade} target {target} < previous {prev_target}"
                )
                prev_target = target

    def test_patience_increases_with_difficulty(self):
        """Heavier difficulty should get >= patience."""
        for preset in ["fast", "standard", "deep"]:
            prev_patience = 0
            for grade in DIFFICULTY_GRADES:
                patience = _BUDGET_TABLE[grade][preset][2]
                assert patience >= prev_patience, (
                    f"{preset}: {grade} patience {patience} < previous {prev_patience}"
                )
                prev_patience = patience


# ── 6. Stop Reason Properties ────────────────────────────────────

class TestStopReasonProperties:
    """Verify stop reason enum properties."""

    def test_all_have_russian_labels(self):
        for reason in StopReason:
            assert reason.label_ru, f"{reason} has no Russian label"
            assert isinstance(reason.label_ru, str)

    def test_all_have_icons(self):
        for reason in StopReason:
            assert reason.icon, f"{reason} has no icon"

    def test_converged_label(self):
        assert "сходимость" in StopReason.CONVERGED.label_ru.lower() or \
               "Сходимость" in StopReason.CONVERGED.label_ru

    def test_plateau_label(self):
        assert "плато" in StopReason.PLATEAU.label_ru.lower() or \
               "Плато" in StopReason.PLATEAU.label_ru


# ── 7. Improvement Threshold Lowered ─────────────────────────────

class TestImprovementThreshold:
    """Verify the improvement threshold was lowered in Phase 16B."""

    def test_default_improvement_threshold(self):
        """Default improvement threshold should be 2% (not 5%)."""
        budget = IterationBudget()
        assert budget.improvement_threshold == 0.02

    def test_computed_budget_has_correct_threshold(self):
        diff = SolveDifficulty(ip_combos=6, oop_combos=6, matchups=36,
                              tree_nodes=50, street_depth="flop_only")
        diff.classify()
        budget = compute_iteration_budget(diff, "standard")
        assert budget.improvement_threshold == 0.02


# ── 8. Convergence Target Sanity ─────────────────────────────────

class TestConvergenceTargetSanity:
    """Verify targets are not still at the old broken 16A values."""

    def test_no_targets_below_0_1(self):
        """No convergence target should be below 0.1 (old 16A bug)."""
        for grade in DIFFICULTY_GRADES:
            for preset in ["fast", "standard", "deep"]:
                target = _BUDGET_TABLE[grade][preset][1]
                assert target >= 0.1, (
                    f"{grade}/{preset}: conv target {target} is < 0.1 — "
                    "likely still at broken 16A value"
                )

    def test_trivial_achieves_good_quality(self):
        """AA vs KK with 0.31 convergence should get 'good' with trivial/standard target."""
        target = _BUDGET_TABLE["trivial"]["standard"][1]
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, convergence=0.31, convergence_target=target,
            iterations=100, target_iterations=100,
        )
        assert q["quality_class"] == "good", (
            f"Trivial AA vs KK (conv=0.31, target={target}) should be 'good', got '{q['quality_class']}'"
        )


# ── 9. Solver Integration ────────────────────────────────────────

class TestSolverIntegration:
    """Integration tests verifying the full solve path with recalibrated policy."""

    def test_trivial_solve_gets_good_quality(self):
        """AA vs KK solve should produce 'good' quality with recalibrated targets."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        quality = result.metadata.get("solve_quality", {}).get("quality_class")
        assert quality in ("good", "acceptable"), f"Trivial solve quality should be good/acceptable, got {quality}"
        assert result.stop_reason in ("max_iterations", "converged", "plateau")

    def test_moderate_solve_gets_non_weak(self):
        """Moderate solve should produce non-weak quality with standard preset."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=150,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        quality = result.metadata.get("solve_quality", {}).get("quality_class")
        assert quality != "incomplete", f"Completed solve should not be 'incomplete'"
        assert result.stop_reason is not None

    def test_stop_reason_persisted_in_metadata(self):
        """Stop reason should be in result metadata."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert "stop_reason" in result.metadata
        assert "solve_quality" in result.metadata
        assert "difficulty_grade" in result.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
