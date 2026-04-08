"""
Phase 7A tests: Solver correctness hardening, reference benchmarks,
deeper correctness checks, trust refinement, and persistence.

Tests cover:
- Correctness check runner behavior
- Individual correctness check categories
- Benchmark suite expansion (14 scenarios)
- Trust grade refinement with correctness confidence
- Correctness persistence in SolveResultModel
- API correctness endpoint
- Exploitability monotonicity
- Zero-sum verification
- Showdown equity spot-checks
- Blocker filtering
- Strategy normalization
"""

import pytest
import math

# ── 1. Correctness Check Module Tests ─────────────────────────

class TestRegretSanity:
    """Test CFR+ regret floor property verification."""

    def test_regret_floor_check_passes_on_valid_solver(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import check_regret_sanity

        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=10, max_raises=1, deterministic=True,
        ))
        result = check_regret_sanity(solver)
        assert result.passed, f"Regret floor failed: {result.actual}"
        assert result.category == "regret"

    def test_regret_no_nan_inf(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import check_regret_no_nan_inf

        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=10, max_raises=1, deterministic=True,
        ))
        result = check_regret_no_nan_inf(solver)
        assert result.passed, f"NaN/Inf found: {result.actual}"


class TestZeroSum:
    """Test zero-sum property verification."""

    def test_zero_sum_passes(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import check_zero_sum

        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=50, max_raises=1, deterministic=True,
        ))
        result = check_zero_sum(solver, output)
        assert result.passed, f"Zero-sum violated: {result.actual}"
        assert result.category == "zero_sum"


class TestBRConsistency:
    """Test best-response consistency."""

    def test_br_weakly_dominates_strategy(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import check_br_consistency

        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=50, max_raises=1, deterministic=True,
        ))
        result = check_br_consistency(solver, output)
        assert result.passed, f"BR consistency failed: {result.actual}"


class TestShowdownEquity:
    """Test showdown equity spot-check correctness."""

    def test_equity_spot_checks_pass(self):
        from app.solver.correctness_checks import check_showdown_equity
        result = check_showdown_equity()
        assert result.passed, f"Equity spot-check failed: {result.actual}"

    def test_aa_beats_kk_on_low_board(self):
        from app.poker_engine.cards import Card
        from app.solver.cfr_solver import compute_showdown_equity
        ip = (Card.parse("Ah"), Card.parse("Ad"))
        oop = (Card.parse("Kh"), Card.parse("Kd"))
        board = [Card.parse(c) for c in ["9s", "7d", "2c"]]
        equity = compute_showdown_equity(ip, oop, board)
        assert equity > 0.99, f"AA should beat KK, got equity={equity}"

    def test_same_hand_gets_half(self):
        from app.poker_engine.cards import Card
        from app.solver.cfr_solver import compute_showdown_equity
        ip = (Card.parse("Ah"), Card.parse("Ad"))
        oop = (Card.parse("Ac"), Card.parse("As"))
        board = [Card.parse(c) for c in ["9s", "7d", "2c"]]
        equity = compute_showdown_equity(ip, oop, board)
        assert abs(equity - 0.5) < 0.01, f"AA vs AA should be 0.5, got {equity}"


class TestBlockerFiltering:
    """Test blocker filtering in turn trees."""

    def test_no_board_cards_as_turn_cards(self):
        from app.solver.correctness_checks import check_blocker_filtering
        result = check_blocker_filtering()
        assert result.passed, f"Blocker filtering failed: {result.actual}"


class TestChanceNodeUniformity:
    """Test chance-node structure."""

    def test_chance_nodes_have_valid_children(self):
        from app.solver.correctness_checks import check_chance_node_uniformity
        result = check_chance_node_uniformity()
        assert result.passed, f"Chance node issue: {result.actual}"


class TestStrategyAccumulation:
    """Test strategy accumulation sanity."""

    def test_strategy_sums_nonnegative(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import check_strategy_accumulation

        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=10, max_raises=1, deterministic=True,
        ))
        result = check_strategy_accumulation(solver)
        assert result.passed, f"Strategy accumulation issue: {result.actual}"


class TestExploitabilityMonotonicity:
    """Test exploitability trend check."""

    def test_monotonicity_check_passes(self):
        from app.solver.correctness_checks import check_exploitability_monotonicity
        result = check_exploitability_monotonicity()
        assert result.passed, f"Monotonicity issue: {result.actual}"
        assert "iter" in result.actual.lower()


class TestBoardConstruction:
    """Test board construction at turn nodes."""

    def test_turn_solve_has_multiple_strategy_nodes(self):
        from app.solver.correctness_checks import check_board_construction
        result = check_board_construction()
        assert result.passed, f"Board construction issue: {result.actual}"


class TestRelabelledSymmetry:
    """Test relabelled symmetry check."""

    def test_dominant_hand_stays_aggressive_across_positions(self):
        from app.solver.correctness_checks import check_relabelled_symmetry
        result = check_relabelled_symmetry()
        assert result.passed, f"Symmetry issue: {result.actual}"


# ── 2. Correctness Report Runner ─────────────────────────────

class TestCorrectnessReport:
    """Test the main correctness check runner."""

    def test_runner_returns_report(self):
        from app.solver.correctness_checks import run_correctness_checks
        report = run_correctness_checks(include_slow=False)
        assert report.total_checks > 0
        assert report.confidence_level in (
            "LOW", "PARTIAL", "STRUCTURAL_PLUS", "BENCHMARK_BACKED", "UNKNOWN"
        )
        assert len(report.confidence_notes) > 0

    def test_runner_with_solver_state(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        from app.solver.correctness_checks import run_correctness_checks

        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["9s", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=6.5, effective_stack=20.0, bet_sizes=[1.0], raise_sizes=[],
            max_iterations=20, max_raises=1, deterministic=True,
        ))
        report = run_correctness_checks(solver=solver, output=output, include_slow=False)
        assert report.total_checks >= 5  # regret + nan + strat_accum + zero_sum + br
        assert report.checks_passed >= 5

    def test_confidence_level_is_structural_plus_without_slow(self):
        from app.solver.correctness_checks import run_correctness_checks
        report = run_correctness_checks(include_slow=False)
        if report.passed:
            assert report.confidence_level == "STRUCTURAL_PLUS"

    def test_full_suite_passes(self):
        """Full suite including slow checks — this is the key integration test."""
        from app.solver.correctness_checks import run_correctness_checks
        report = run_correctness_checks(include_slow=True)
        assert report.passed, (
            f"Full correctness suite failed: "
            f"{[c.name for c in report.checks if not c.passed]}"
        )
        assert report.confidence_level == "BENCHMARK_BACKED"

    def test_report_to_dict_structure(self):
        from app.solver.correctness_checks import run_correctness_checks
        report = run_correctness_checks(include_slow=False)
        d = report.to_dict()
        assert "passed" in d
        assert "total_checks" in d
        assert "checks_passed" in d
        assert "confidence_level" in d
        assert "confidence_notes" in d
        assert "checks" in d
        assert isinstance(d["checks"], list)


# ── 3. Benchmark Suite Expansion ──────────────────────────────

class TestExpandedBenchmarks:
    """Test the expanded benchmark suite."""

    def test_benchmark_count_is_14(self):
        from app.solver.benchmarks import BENCHMARKS
        assert len(BENCHMARKS) == 14, f"Expected 14 benchmarks, got {len(BENCHMARKS)}"

    def test_turn_aware_benchmark_exists(self):
        from app.solver.benchmarks import BENCHMARKS
        turn_benches = [b for b in BENCHMARKS if b.get("include_turn")]
        assert len(turn_benches) >= 3, f"Expected ≥3 turn benchmarks, got {len(turn_benches)}"

    def test_run_single_flop_benchmark(self):
        from app.solver.benchmarks import _run_single_benchmark, BENCHMARKS
        # Run the simplest benchmark (AA vs KK domination)
        result = _run_single_benchmark(BENCHMARKS[0])
        assert result.status in ("pass", "warn", "fail", "error"), f"Bad status: {result.status}"
        assert result.name == "AA vs KK Domination"
        assert result.iterations > 0

    def test_zero_sum_benchmark(self):
        from app.solver.benchmarks import _run_single_benchmark, BENCHMARKS
        zs = next(b for b in BENCHMARKS if b["name"] == "Zero-Sum Check")
        result = _run_single_benchmark(zs)
        assert result.status == "pass", f"Zero-sum benchmark failed: {[c.actual for c in result.checks]}"

    def test_coverage_benchmark(self):
        from app.solver.benchmarks import _run_single_benchmark, BENCHMARKS
        cov = next(b for b in BENCHMARKS if b["name"] == "Board Coverage Multi-Range")
        result = _run_single_benchmark(cov)
        assert result.status == "pass", f"Coverage benchmark failed: {[c.actual for c in result.checks]}"

    def test_turn_normalization_benchmark(self):
        from app.solver.benchmarks import _run_single_benchmark, BENCHMARKS
        tn = next(b for b in BENCHMARKS if b["name"] == "Turn Normalization")
        result = _run_single_benchmark(tn)
        assert result.status == "pass", f"Turn normalization failed: {[c.actual for c in result.checks]}"


# ── 4. Trust Grade Refinement ─────────────────────────────────

class TestTrustGradeRefinement:
    """Test trust grade with correctness confidence."""

    def test_trust_grade_includes_correctness_confidence(self):
        from app.solver.solver_validation import ValidationResult, compute_trust_grade
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=5.0, exploitability_available=True,
            correctness_confidence="BENCHMARK_BACKED",
            correctness_notes=["All checks passed"],
        )
        assert "correctness_confidence" in grade
        assert grade["correctness_confidence"] == "BENCHMARK_BACKED"
        assert "correctness_notes" in grade
        assert len(grade["correctness_notes"]) > 0

    def test_trust_grade_without_correctness(self):
        from app.solver.solver_validation import ValidationResult, compute_trust_grade
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=5.0, exploitability_available=True,
        )
        assert grade["correctness_confidence"] == "UNKNOWN"
        assert grade["correctness_notes"] == []

    def test_trust_grade_turn_with_correctness(self):
        from app.solver.solver_validation import ValidationResult, compute_trust_grade
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=3.0, exploitability_available=True,
            street_depth="flop_plus_turn",
            correctness_confidence="STRUCTURAL_PLUS",
        )
        assert grade["grade"] == "INTERNAL_DEMO"  # turn capped
        assert grade["correctness_confidence"] == "STRUCTURAL_PLUS"


# ── 5. Persistence Tests ─────────────────────────────────────

class TestCorrectnessPersistence:
    """Test that correctness data is persisted correctly."""

    def test_model_has_correctness_columns(self):
        from app.models import SolveResultModel
        assert hasattr(SolveResultModel, 'correctness_json')
        assert hasattr(SolveResultModel, 'correctness_notes')

    def test_correctness_json_nullable(self):
        from app.models import SolveResultModel
        col = SolveResultModel.__table__.columns['correctness_json']
        assert col.nullable is True

    def test_correctness_notes_nullable(self):
        from app.models import SolveResultModel
        col = SolveResultModel.__table__.columns['correctness_notes']
        assert col.nullable is True


# ── 6. Regression Protection ─────────────────────────────────

class TestRegressionProtection:
    """Ensure Phase 7A changes don't break existing functionality."""

    def test_benchmark_result_to_dict(self):
        from app.solver.benchmarks import BenchmarkResult
        r = BenchmarkResult(name="test", description="test desc")
        d = r.to_dict()
        assert "name" in d
        assert "status" in d
        assert d["status"] == "not_run"

    def test_correctness_check_result_to_dict(self):
        from app.solver.correctness_checks import CheckResult
        c = CheckResult(
            name="test", passed=True,
            description="desc", actual="ok", expected="ok",
            category="test_cat",
        )
        d = c.to_dict()
        assert d["name"] == "test"
        assert d["passed"] is True
        assert d["category"] == "test_cat"

    def test_solver_still_produces_valid_output(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK",
            oop_range="QQ,JJ", pot=6.5, effective_stack=20.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=20,
            max_raises=1, deterministic=True,
        ))
        assert output.iterations > 0
        assert len(output.strategies) > 0
        assert output.exploitability_mbb < 30000  # sanity: not insane for wider range at low iters
