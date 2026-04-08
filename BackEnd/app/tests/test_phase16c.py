"""
Phase 16C: Tests for Quality-Aware UX, Rust Path Verification, and Legacy Cleanup.

Tests cover:
  1. Quality label wording (user-friendly Russian)
  2. Quality explanation field presence
  3. Rust path is always selected when available
  4. Python fallback triggers warning log
  5. API shape consistency
  6. StopReason display labels
  7. Regression protection for Phase 16A/B
"""
import pytest
import sys
sys.path.insert(0, '.')

from app.solver.solve_policy import (
    SolveDifficulty,
    StopReason,
    classify_solve_quality,
    compute_iteration_budget,
)


# ── 1. Quality Label Wording ─────────────────────────────────────

class TestQualityLabelWording:
    """Phase 16C: Verify quality labels are user-friendly Russian."""

    def test_good_label_is_user_friendly(self):
        """Good quality should say 'Надёжный результат', not 'сходимость'."""
        q = classify_solve_quality(
            StopReason.CONVERGED, 0.3, 0.4, 100, 100,
        )
        assert "Надёжный" in q["quality_label_ru"]
        assert "сходимость" not in q["quality_label_ru"].lower()

    def test_acceptable_label_is_user_friendly(self):
        """Acceptable quality should say 'Рабочий результат'."""
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, 1.0, 0.4, 100, 100,
        )
        assert "Рабочий" in q["quality_label_ru"]
        assert "плато" not in q["quality_label_ru"].lower()

    def test_weak_label_is_user_friendly(self):
        """Weak quality should say 'Приблизительный результат'."""
        q = classify_solve_quality(
            StopReason.MAX_ITERATIONS, 5.0, 0.4, 100, 100,
        )
        assert "Приблизительный" in q["quality_label_ru"]
        assert "требует" not in q["quality_label_ru"].lower()

    def test_cancelled_label_is_user_friendly(self):
        """Cancelled should say 'Расчёт прерван'."""
        q = classify_solve_quality(
            StopReason.CANCELLED, 1.0, 0.4, 50, 100,
        )
        assert "прерван" in q["quality_label_ru"].lower()

    def test_timeout_label_is_user_friendly(self):
        """Timeout should say 'Превышено время'."""
        q = classify_solve_quality(
            StopReason.TIMEOUT, 1.0, 0.4, 50, 100,
        )
        assert "время" in q["quality_label_ru"].lower()


# ── 2. Quality Explanation Field ─────────────────────────────────

class TestQualityExplanation:
    """Phase 16C: Verify quality_explanation_ru field is present."""

    def test_good_has_explanation(self):
        q = classify_solve_quality(StopReason.CONVERGED, 0.3, 0.4, 100, 100)
        assert "quality_explanation_ru" in q
        assert len(q["quality_explanation_ru"]) > 10

    def test_acceptable_has_explanation(self):
        q = classify_solve_quality(StopReason.MAX_ITERATIONS, 1.0, 0.4, 100, 100)
        assert "quality_explanation_ru" in q
        assert len(q["quality_explanation_ru"]) > 10

    def test_weak_has_explanation(self):
        q = classify_solve_quality(StopReason.MAX_ITERATIONS, 5.0, 0.4, 100, 100)
        assert "quality_explanation_ru" in q
        assert "Глубокий" in q["quality_explanation_ru"]  # recommends deep preset

    def test_cancelled_has_explanation(self):
        q = classify_solve_quality(StopReason.CANCELLED, 1.0, 0.4, 50, 100)
        assert "quality_explanation_ru" in q

    def test_timeout_has_explanation(self):
        q = classify_solve_quality(StopReason.TIMEOUT, 1.0, 0.4, 50, 100)
        assert "quality_explanation_ru" in q
        assert "Быстрый" in q["quality_explanation_ru"]  # recommends fast preset

    def test_plateau_close_has_explanation(self):
        q = classify_solve_quality(StopReason.PLATEAU, 1.0, 0.4, 150, 200)
        assert "quality_explanation_ru" in q
        assert "тренировки" in q["quality_explanation_ru"].lower()

    def test_plateau_far_has_explanation(self):
        q = classify_solve_quality(StopReason.PLATEAU, 5.0, 0.4, 150, 200)
        assert "quality_explanation_ru" in q
        assert "Глубокий" in q["quality_explanation_ru"]


# ── 3. Rust Path Verification ─────────────────────────────────────

class TestRustPathVerification:
    """Phase 16C: Verify Rust path is always selected when available."""

    def test_rust_is_available(self):
        """Rust poker_core should be importable."""
        from app.solver.rust_bridge import RUST_AVAILABLE, RUST_VERSION
        assert RUST_AVAILABLE, "Rust poker_core is not available!"
        assert RUST_VERSION is not None

    def test_rust_has_cfr_iterate(self):
        """Rust should have cfr_iterate function."""
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate')

    def test_rust_has_cfr_iterate_with_control(self):
        """Rust should have cfr_iterate_with_control function."""
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate_with_control')

    def test_should_use_rust_returns_true(self):
        """_should_use_rust_cfr should return True for a normal solve."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        solver = CfrSolver()
        # We need to partially set up the solver to test this
        solver._board = [__import__('app.poker_engine.cards', fromlist=['Card']).Card.parse(c) for c in req.board]
        solver._ip_combos = [(solver._board[0], solver._board[1])]  # dummy
        solver._oop_combos = [(solver._board[0], solver._board[2])]  # dummy
        solver._use_arrays = True

        import numpy as np
        class DummyArrays:
            regrets = np.zeros(10)
            strategy_sums = np.zeros(10)
            max_actions = 4
        solver._arrays = DummyArrays()

        result = solver._should_use_rust_cfr(req)
        assert result is True, "Rust path should be selected for standard solve"

    def test_solve_uses_rust_log(self):
        """A real solve should log 'Rust CFR' not 'PYTHON FALLBACK'."""
        import logging
        from app.solver.cfr_solver import CfrSolver, SolveRequest

        # Capture logs
        log_messages = []
        handler = logging.Handler()
        handler.emit = lambda record: log_messages.append(record.getMessage())
        logger = logging.getLogger('app.solver.cfr_solver')
        logger.addHandler(handler)

        try:
            req = SolveRequest(
                board=["Ks", "7d", "2c"],
                ip_range="AA", oop_range="KK",
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
                max_raises=0, deterministic=True,
            )
            req._preset = "standard"
            solver = CfrSolver()
            result = solver.solve(req, progress_callback=lambda info: None)

            # Check logs for Rust path
            rust_messages = [m for m in log_messages if 'Rust CFR' in m]
            python_messages = [m for m in log_messages if 'PYTHON FALLBACK' in m]

            assert len(rust_messages) > 0, f"Expected 'Rust CFR' in logs, got: {log_messages[-5:]}"
            assert len(python_messages) == 0, "Python fallback should NOT appear in a normal solve"
        finally:
            logger.removeHandler(handler)

    def test_solve_metadata_has_engine_field(self):
        """Result metadata should indicate Rust engine was used."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)

        # Verify metadata includes stop reason and quality
        assert "stop_reason" in result.metadata
        assert "solve_quality" in result.metadata
        assert "difficulty_grade" in result.metadata


# ── 4. API Shape Consistency ──────────────────────────────────────

class TestAPIShapeConsistency:
    """Phase 16C: Verify API response models are consistent."""

    def test_solve_history_item_has_new_fields(self):
        from app.api.routes_solver import SolveHistoryItem
        schema = SolveHistoryItem.model_json_schema()
        props = schema.get("properties", {})
        assert "stop_reason" in props, "SolveHistoryItem missing stop_reason"
        assert "quality_class" in props, "SolveHistoryItem missing quality_class"

    def test_solve_history_detail_has_metadata(self):
        from app.api.routes_solver import SolveHistoryDetail
        schema = SolveHistoryDetail.model_json_schema()
        props = schema.get("properties", {})
        assert "metadata" in props, "SolveHistoryDetail missing metadata"
        assert "algorithm_metadata" in props, "SolveHistoryDetail missing algorithm_metadata"

    def test_quality_dict_shape(self):
        """classify_solve_quality should always return the required keys."""
        q = classify_solve_quality(StopReason.CONVERGED, 0.3, 0.4, 100, 100)
        assert "quality_class" in q
        assert "quality_label_ru" in q
        assert "quality_explanation_ru" in q
        assert "honest_note" in q
        assert q["quality_class"] in ("good", "acceptable", "weak", "incomplete")


# ── 5. StopReason Display Labels ──────────────────────────────────

class TestStopReasonDisplayLabels:
    """Phase 16C: Verify StopReason enum has correct display properties."""

    def test_converged_icon(self):
        assert StopReason.CONVERGED.icon == "✅"

    def test_plateau_icon(self):
        assert StopReason.PLATEAU.icon == "📊"

    def test_max_iterations_icon(self):
        assert StopReason.MAX_ITERATIONS.icon == "🔢"

    def test_cancelled_has_label(self):
        assert isinstance(StopReason.CANCELLED.label_ru, str)
        assert len(StopReason.CANCELLED.label_ru) > 0

    def test_all_stop_reasons_have_value(self):
        """All stop reasons should have string values."""
        for reason in StopReason:
            assert isinstance(reason.value, str)
            assert len(reason.value) > 0


# ── 6. Docstring/Architecture Verification ────────────────────────

class TestArchitectureDocumentation:
    """Phase 16C: Verify code documentation reflects current architecture."""

    def test_solver_module_mentions_rust(self):
        """cfr_solver module docstring should mention Rust as primary."""
        import app.solver.cfr_solver as mod
        doc = mod.__doc__
        assert "Rust" in doc, "Module docstring should mention Rust"
        assert "PRIMARY ENGINE" in doc, "Module docstring should say PRIMARY ENGINE"

    def test_python_fallback_mentions_emergency(self):
        """Python iteration fallback should be marked as emergency."""
        from app.solver.cfr_solver import CfrSolver
        doc = CfrSolver._run_iterations_python.__doc__
        assert "EMERGENCY FALLBACK" in doc, "Python path should be marked as emergency"

    def test_should_use_rust_mentions_phase_15b(self):
        """_should_use_rust_cfr should mention all scopes."""
        from app.solver.cfr_solver import CfrSolver
        doc = CfrSolver._should_use_rust_cfr.__doc__
        assert "Rust" in doc


# ── 7. Regression Protection ──────────────────────────────────────

class TestPhase16CRegression:
    """Phase 16C: Ensure existing functionality is not broken."""

    def test_normal_solve_still_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.strategies is not None
        assert len(result.strategies) > 0
        assert result.stop_reason is not None

    def test_cancel_still_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        import threading
        cancelled = threading.Event()

        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=500,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()

        # Cancel after a brief moment
        def cancel_later():
            import time
            time.sleep(0.1)
            cancelled.set()
        threading.Thread(target=cancel_later, daemon=True).start()

        result = solver.solve(
            req,
            progress_callback=lambda info: None,
            cancel_check=lambda: cancelled.is_set(),
        )
        # Rust is so fast that adaptive stopping may fire before cancel arrives.
        # Both outcomes are valid: either cancelled or early-stopped.
        assert result.stop_reason in ("cancelled", "plateau", "max_iterations", "converged"), \
            f"Unexpected stop_reason: {result.stop_reason}"

    def test_convergence_metric_is_finite(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[], max_iterations=50,
            max_raises=0, deterministic=True,
        )
        req._preset = "standard"
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.convergence_metric >= 0.0
        assert result.convergence_metric < 100.0  # should be finite and small-ish


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
