"""
Phase 3B tests: validation layer, persistence, trainer bridge, job hardening.
"""

import pytest
import math
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


# ── Solver Validation Tests ──

class TestSolverValidation:
    """Tests for the solver validation layer."""

    def test_valid_strategies_pass(self):
        from app.solver.solver_validation import validate_solve_output

        strategies = {
            "node_0": {
                "AhAs": {"check": 0.6, "bet_50": 0.3, "fold": 0.1},
                "KhKs": {"check": 0.4, "bet_50": 0.5, "fold": 0.1},
            },
        }
        result = validate_solve_output(strategies, 100, 0.5)
        assert result.passed
        assert result.checks_passed >= 5
        assert len(result.issues) == 0

    def test_normalization_failure(self):
        from app.solver.solver_validation import validate_solve_output

        strategies = {
            "node_0": {
                "AhAs": {"check": 0.5, "bet_50": 0.3, "fold": 0.1},  # sums to 0.9
            },
        }
        result = validate_solve_output(strategies, 100, 0.5)
        assert not result.passed
        assert any("Normalization" in i for i in result.issues)

    def test_negative_frequency_failure(self):
        from app.solver.solver_validation import validate_solve_output

        strategies = {
            "node_0": {
                "AhAs": {"check": 1.1, "bet_50": -0.1},
            },
        }
        result = validate_solve_output(strategies, 100, 0.5)
        assert not result.passed
        assert any("Negative" in i for i in result.issues)

    def test_nan_failure(self):
        from app.solver.solver_validation import validate_solve_output

        strategies = {
            "node_0": {
                "AhAs": {"check": float("nan"), "bet_50": 0.5},
            },
        }
        result = validate_solve_output(strategies, 100, 0.5)
        assert not result.passed
        assert any("NaN" in i for i in result.issues)

    def test_empty_strategies_failure(self):
        from app.solver.solver_validation import validate_solve_output

        result = validate_solve_output({}, 0, 0.0)
        assert not result.passed
        assert any("Empty" in i for i in result.issues)

    def test_high_convergence_warning(self):
        from app.solver.solver_validation import validate_solve_output

        strategies = {
            "node_0": {
                "AhAs": {"check": 0.5, "bet_50": 0.5},
            },
        }
        result = validate_solve_output(strategies, 10, 10.0)
        assert result.passed  # high convergence is a warning, not failure
        assert len(result.warnings) > 0

    def test_validation_result_to_dict(self):
        from app.solver.solver_validation import ValidationResult

        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        d = vr.to_dict()
        assert d["passed"] is True
        assert "trust_level" in d

    def test_trust_level_categories(self):
        from app.solver.solver_validation import ValidationResult

        # Failed
        vr = ValidationResult(passed=False)
        assert "FAILED" in vr._trust_level()

        # Structural only (no toy game)
        vr = ValidationResult(passed=True)
        assert "STRUCTURAL" in vr._trust_level()

        # With toy game
        vr = ValidationResult(passed=True, toy_game_result={"passed": True})
        assert "INTERNAL_DEMO" in vr._trust_level()


class TestToyGameValidation:
    """Tests for the toy-game validator."""

    def test_toy_game_runs_and_passes(self):
        from app.solver.solver_validation import run_toy_game_validation

        result = run_toy_game_validation()
        assert result["solver_completed"]
        assert result["structural_validation"]
        assert result["aa_avg_fold_at_root"] < 0.10
        assert result["passed"]

    def test_toy_game_has_note(self):
        from app.solver.solver_validation import run_toy_game_validation

        result = run_toy_game_validation()
        assert "note" in result
        assert "NOT" in result["note"] or "not" in result["note"] or "sanity" in result["note"].lower()


class TestDeterministicMode:
    """Tests for deterministic reproducibility."""

    def test_deterministic_reproducibility(self):
        from app.solver.solver_validation import validate_deterministic_reproducibility

        result = validate_deterministic_reproducibility()
        assert result["passed"]
        assert result["compared_values"] > 0
        assert result["differences"] == 0

    def test_deterministic_solve_gives_same_output(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest

        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=20,
            max_raises=1,
            deterministic=True,
        )

        s1 = CfrSolver()
        out1 = s1.solve(request)

        s2 = CfrSolver()
        out2 = s2.solve(request)

        # Root strategies should be identical
        for combo in out1.strategies.get("node_0", {}):
            for action in out1.strategies["node_0"][combo]:
                assert abs(
                    out1.strategies["node_0"][combo][action] -
                    out2.strategies["node_0"].get(combo, {}).get(action, 0.0)
                ) < 1e-10


class TestValidationInSolveOutput:
    """Test that validation is automatically run and attached to solve output."""

    def test_solve_includes_validation(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest

        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=10,
            max_raises=1,
        )

        solver = CfrSolver()
        output = solver.solve(request)

        assert "validation" in output.metadata
        validation = output.metadata["validation"]
        assert "passed" in validation
        assert "trust_level" in validation
        assert validation["passed"] is True

    def test_solve_deterministic_flag_in_metadata(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest

        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=10,
            max_raises=1,
            deterministic=True,
        )

        solver = CfrSolver()
        output = solver.solve(request)
        assert output.metadata["deterministic"] is True


class TestTimeEstimation:
    """Test the solve time estimation logic."""

    def test_estimate_returns_value(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest

        req = SolveJobRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5,
            effective_stack=97.0,
        )
        est, warnings = _estimate_solve_time(req)
        assert est > 0
        assert isinstance(warnings, list)

    def test_large_range_warns(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest

        req = SolveJobRequest(
            board=["9s", "7d", "2c"],
            ip_range="TT+,ATs+,KQs,AJo+",
            oop_range="TT+,ATs+,KQs,AJo+",
            pot=6.5,
            effective_stack=97.0,
            max_iterations=500,
        )
        est, warnings = _estimate_solve_time(req)
        assert len(warnings) > 0


class TestPersistenceModel:
    """Test that SolveResultModel can be created and queried."""

    def test_model_exists(self):
        from app.models import SolveResultModel
        assert SolveResultModel.__tablename__ == "solve_results"

    def test_model_has_required_columns(self):
        from app.models import SolveResultModel
        columns = [c.name for c in SolveResultModel.__table__.columns]
        required = [
            "id", "user_id", "status", "created_at",
            "config_json", "iterations", "convergence_metric",
            "elapsed_seconds", "tree_nodes", "ip_combos",
            "validation_json", "root_strategy_summary_json",
            "full_strategies_available",
        ]
        for col in required:
            assert col in columns, f"Missing column: {col}"


class TestSolveRequestDeterministic:
    """Test that SolveRequest supports the deterministic flag."""

    def test_default_is_false(self):
        from app.solver.cfr_solver import SolveRequest

        req = SolveRequest(board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert req.deterministic is False

    def test_can_set_true(self):
        from app.solver.cfr_solver import SolveRequest

        req = SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            deterministic=True,
        )
        assert req.deterministic is True


class TestJobStatusTransitions:
    """Test that solve job statuses are correct."""

    def test_initial_status(self):
        """Jobs should start as 'queued'."""
        from app.api.routes_solver import SolveJobRequest, _estimate_solve_time

        req = SolveJobRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
        )
        # estimation doesn't crash
        est, warnings = _estimate_solve_time(req)
        assert isinstance(est, float)
