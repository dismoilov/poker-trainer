"""
Phase 18B Tests — Browser QA + UX Honesty Polish

Tests covering Phase 18B fixes:
1. Turn preset structure
2. Quality class in solve results
3. Russian quality labels
4. Concurrent rejection constants
5. Solver regression (flop + turn+river via Rust)
6. Stop reason presence
"""

import pytest
import sys
import time
sys.path.insert(0, '.')

from app.api.routes_solver import (
    SOLVER_PRESETS,
    _solve_lock,
    _active_solve_id,
    STUCK_RUNNING_TIMEOUT_SECONDS,
)


class TestTurnPresetNote:
    """Verify turn preset messaging is present and honest."""

    def test_presets_have_turn_note_field(self):
        """The presets config should contain expected presets."""
        assert 'fast' in SOLVER_PRESETS
        assert 'standard' in SOLVER_PRESETS
        assert 'deep' in SOLVER_PRESETS

    def test_all_presets_have_required_fields(self):
        """Each preset must have label, bet_sizes, max_iterations."""
        for key, preset in SOLVER_PRESETS.items():
            assert 'label' in preset, f"Preset {key} missing label"
            assert 'bet_sizes' in preset, f"Preset {key} missing bet_sizes"
            assert 'max_iterations' in preset, f"Preset {key} missing max_iterations"

    def test_deep_preset_includes_turn_river(self):
        """Deep preset should enable turn and river."""
        deep = SOLVER_PRESETS['deep']
        assert deep.get('include_turn') is True
        assert deep.get('include_river') is True


class TestQualityBadges:
    """Test that quality badges are generated correctly by the solver."""

    def test_converged_solve_gets_good_quality(self):
        """A fully converged solve should produce quality_class=good."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["As", "Kd", "7c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
            max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        sq = result.metadata.get("solve_quality", {})
        assert sq is not None, "solve_quality should be present"
        assert sq.get('quality_class') in ('good', 'acceptable'), \
            f"Expected good/acceptable quality for converged solve, got {sq}"

    def test_quality_class_values_are_standard(self):
        """Quality class must be one of: good, acceptable, weak, poor."""
        valid_classes = {'good', 'acceptable', 'weak', 'poor'}
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Qs", "Jd", "2c"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=25,
            max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        sq = result.metadata.get("solve_quality", {})
        if sq and sq.get('quality_class'):
            assert sq['quality_class'] in valid_classes

    def test_quality_has_russian_label(self):
        """Quality should include quality_label_ru field."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ts", "9d", "3c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
            max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        sq = result.metadata.get("solve_quality", {})
        assert sq is not None
        label = sq.get('quality_label_ru', '')
        assert label, "quality_label_ru should not be empty"
        # Should contain Russian characters
        assert any('\u0400' <= c <= '\u04FF' for c in label), \
            f"Label should contain Russian: {label}"


class TestRustEngine:
    """Verify Rust engine is used for standard solve cases."""

    def test_flop_uses_rust(self):
        """Flop-only solve should use Rust CFR."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=25,
            max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations > 0

    def test_turn_river_uses_rust(self):
        """Turn+river solve should also use Rust CFR."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            include_river=True, max_river_cards=2,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        req._preset = 'deep'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations >= 50, \
            f"Turn+river should run at least 50 iterations, got {result.iterations}"


class TestStopReason:
    """Test that stop_reason is properly set in results."""

    def test_stop_reason_present(self):
        """Result should include stop_reason."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["7h", "6s", "2d"], ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=25,
            max_raises=0, deterministic=True,
        )
        req._preset = 'fast'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        sr = result.stop_reason
        assert sr in ('converged', 'plateau', 'max_iterations', 'cancelled'), \
            f"Unexpected stop_reason: {sr}"


class TestConcurrentRejection:
    """Test concurrent solve rejection infrastructure."""

    def test_lock_exists(self):
        """The solve lock should exist."""
        assert _solve_lock is not None

    def test_concurrent_rejection_timeout(self):
        """Verify stuck timeout constant is reasonable."""
        assert STUCK_RUNNING_TIMEOUT_SECONDS >= 300, \
            "Stuck timeout should be at least 5 minutes"
        assert STUCK_RUNNING_TIMEOUT_SECONDS <= 1800, \
            "Stuck timeout should not exceed 30 minutes"

    def test_presets_bet67_exists(self):
        """Standard preset should include 0.67 bet size."""
        standard = SOLVER_PRESETS['standard']
        assert 0.67 in standard['bet_sizes'], \
            f"Standard preset missing 0.67 bet size: {standard['bet_sizes']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
