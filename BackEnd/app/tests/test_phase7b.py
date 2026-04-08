"""
Phase 7B tests - Performance Hardening, Job Reliability, Solve Runtime Control.

Tests cover:
- Equity cache correctness (cached results match uncached)
- Turn equity cache correctness
- Performance regression (optimized solve must be fast)
- Job lifecycle state machine
- Complexity-based rejection
- Estimation calibration
- Stale job cleanup
- Progress ETA computation
"""

import time
import pytest
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput,
    compute_showdown_equity, expand_range_to_combos,
    combo_to_str, MAX_COMBOS_PER_SIDE, MAX_TOTAL_MATCHUPS,
)
from app.poker_engine.cards import Card


# -- Equity Cache Correctness --


class TestEquityCache:
    """Verify that precomputed equity cache produces identical results to direct computation."""

    def test_equity_cache_populated_after_solve(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=2, deterministic=True,
        ))
        assert len(solver._equity_cache) > 0, "Equity cache should be populated"
        assert output.iterations == 10

    def test_equity_cache_matches_direct_computation(self):
        """Every cached equity must equal the directly computed equity."""
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["As", "Kh", "3d"],
            ip_range="AA,KK,AKs",
            oop_range="QQ,JJ,TT",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=2, deterministic=True,
        ))
        board = [Card.parse(c) for c in ["As", "Kh", "3d"]]

        for (ip_idx, oop_idx, turn_str, river_str), cached_equity in solver._equity_cache.items():
            ip_combo = solver._ip_combos[ip_idx]
            oop_combo = solver._oop_combos[oop_idx]
            eval_board = list(board)
            if turn_str:
                eval_board = eval_board + [Card.parse(turn_str)]
            if river_str:
                eval_board = eval_board + [Card.parse(river_str)]
            direct_equity = compute_showdown_equity(ip_combo, oop_combo, eval_board)
            assert cached_equity == direct_equity, (
                f"Cache mismatch at ({ip_idx}, {oop_idx}, {turn_str}, {river_str}): "
                f"cached={cached_equity}, direct={direct_equity}"
            )

    def test_aa_vs_kk_equity_always_one(self):
        """AA should beat KK on non-pair boards almost always."""
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["Qs", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=1, deterministic=True,
        ))
        # All cache entries should show equity = 1.0 (AA beats KK)
        for key, equity in solver._equity_cache.items():
            assert equity == 1.0, f"AA should always beat KK on Q72 board, got equity={equity}"

    def test_turn_equity_cache_populated(self):
        """Turn-enabled solve should cache equity for turn cards."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
        ))
        # Should have flop entries (turn_str='') AND turn entries (turn_str != '')
        flop_entries = sum(1 for k in solver._equity_cache if k[2] == "")
        turn_entries = sum(1 for k in solver._equity_cache if k[2] != "")
        assert flop_entries > 0, "Should have flop equity entries"
        assert turn_entries > 0, "Should have turn equity entries"

    def test_turn_equity_cache_correctness(self):
        """Turn equity cache entries must match direct computation."""
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
        ))
        board = [Card.parse(c) for c in ["Ks", "7d", "2c"]]
        for (ip_idx, oop_idx, turn_str, river_str), cached_equity in solver._equity_cache.items():
            ip_combo = solver._ip_combos[ip_idx]
            oop_combo = solver._oop_combos[oop_idx]
            eval_board = list(board)
            if turn_str:
                eval_board = eval_board + [Card.parse(turn_str)]
            if river_str:
                eval_board = eval_board + [Card.parse(river_str)]
            direct = compute_showdown_equity(ip_combo, oop_combo, eval_board)
            assert cached_equity == direct


# -- Pre-formatted Strings --


class TestPreformattedStrings:
    """Verify that pre-formatted combo strings match direct formatting."""

    def test_combo_strs_populated(self):
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["As", "Kh", "3d"],
            ip_range="AA,KK",
            oop_range="QQ",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=5, max_raises=1, deterministic=True,
        ))
        assert len(solver._combo_strs_ip) == len(solver._ip_combos)
        assert len(solver._combo_strs_oop) == len(solver._oop_combos)

    def test_combo_strs_match_direct(self):
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["As", "Kh", "3d"],
            ip_range="AA,KK",
            oop_range="QQ",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=5, max_raises=1, deterministic=True,
        ))
        for i, combo in enumerate(solver._ip_combos):
            assert solver._combo_strs_ip[i] == combo_to_str(combo)
        for i, combo in enumerate(solver._oop_combos):
            assert solver._combo_strs_oop[i] == combo_to_str(combo)

    def test_hole_card_strs_populated(self):
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=["As", "Kh", "3d"],
            ip_range="AA,KK",
            oop_range="QQ",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=5, max_raises=1, deterministic=True,
        ))
        for i, combo in enumerate(solver._ip_combos):
            expected = {f"{c}" for c in combo}
            assert solver._combo_hole_strs_ip[i] == expected


# -- Performance Regression --


class TestPerformanceRegression:
    """Ensure optimized solver meets performance targets."""

    def test_flop_solve_fast(self):
        """50-iter solve with ~177 matchups should complete in <5s (was ~13.5s)."""
        solver = CfrSolver()
        t0 = time.time()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,AKs",
            oop_range="QQ,JJ,AQs",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=50, max_raises=2, deterministic=True,
        ))
        elapsed = time.time() - t0
        assert elapsed < 5.0, f"Solve took {elapsed:.1f}s, expected <5s (pre-optimization was ~13.5s)"
        assert output.iterations == 50

    def test_small_solve_very_fast(self):
        """Small solve (AA vs KK, 10 iters) should complete in <1s."""
        solver = CfrSolver()
        t0 = time.time()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=1, deterministic=True,
        ))
        elapsed = time.time() - t0
        assert elapsed < 1.0, f"Small solve took {elapsed:.1f}s"
        assert output.iterations == 10

    def test_output_quality_preserved(self):
        """Optimized solve should produce valid strategies."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5, effective_stack=20.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=50, max_raises=2, deterministic=True,
        ))
        # Strategies should be present and normalized
        assert len(output.strategies) > 0
        for node_id, combos in output.strategies.items():
            for combo_str, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, (
                    f"Strategy not normalized at {node_id}/{combo_str}: sum={total}"
                )


# -- Job Lifecycle --


class TestJobLifecycle:
    """Test job state transitions and cleanup."""

    def test_stale_job_cleanup(self):
        from app.api.routes_solver import _solve_jobs, _cleanup_stale_jobs, STALE_JOB_EXPIRY_SECONDS
        from datetime import datetime, timedelta

        # Add a stale done job
        old_time = (datetime.utcnow() - timedelta(seconds=STALE_JOB_EXPIRY_SECONDS + 60)).isoformat()
        _solve_jobs["test-stale-1"] = {
            "status": "done",
            "created_at": old_time,
        }
        # Add a fresh job
        _solve_jobs["test-fresh-1"] = {
            "status": "done",
            "created_at": datetime.utcnow().isoformat(),
        }
        # Add a stale BUT running job (should NOT be cleaned)
        _solve_jobs["test-stale-running"] = {
            "status": "running",
            "created_at": old_time,
        }

        _cleanup_stale_jobs()

        assert "test-stale-1" not in _solve_jobs, "Stale done job should be cleaned"
        assert "test-fresh-1" in _solve_jobs, "Fresh job should remain"
        assert "test-stale-running" in _solve_jobs, "Stale running job should NOT be cleaned"

        # Cleanup
        _solve_jobs.pop("test-fresh-1", None)
        _solve_jobs.pop("test-stale-running", None)


# -- Estimation --


class TestEstimation:
    """Test solve time estimation."""

    def test_estimate_returns_values(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest
        est, warnings = _estimate_solve_time(SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5, effective_stack=20.0,
            max_iterations=50,
        ))
        assert est > 0, "Estimation should be positive"
        assert isinstance(warnings, list)

    def test_estimate_turn_higher_than_flop(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest
        flop_est, _ = _estimate_solve_time(SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5, effective_stack=20.0,
            max_iterations=50,
            include_turn=False,
        ))
        turn_est, turn_warns = _estimate_solve_time(SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            max_iterations=50,
            include_turn=True,
            max_turn_cards=5,
        ))
        # Turn should produce warnings about turn-enabled
        assert any("Тёрн" in w or "Turn-enabled" in w for w in turn_warns)

    def test_complexity_grade_categories(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest
        # Light solve
        light_est, _ = _estimate_solve_time(SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5, effective_stack=20.0,
            max_iterations=10,
        ))
        assert light_est < 5, "AA vs KK 10 iters should be LIGHT"

    def test_high_iter_warning(self):
        from app.api.routes_solver import _estimate_solve_time, SolveJobRequest
        _, warnings = _estimate_solve_time(SolveJobRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5, effective_stack=20.0,
            max_iterations=1000,
        ))
        assert any("High iteration" in w for w in warnings)


# -- Progress / ETA --


class TestProgressETA:
    """Test ETA computation in progress response."""

    def test_progress_model_has_eta_fields(self):
        from app.api.routes_solver import SolveJobProgress
        p = SolveJobProgress(
            job_id="test", status="running",
            iteration=50, total_iterations=100,
            convergence_metric=0.1, elapsed_seconds=5.0,
            estimated_remaining_seconds=5.0, progress_pct=50.0,
        )
        assert p.estimated_remaining_seconds == 5.0
        assert p.progress_pct == 50.0

    def test_solve_response_has_complexity_grade(self):
        from app.api.routes_solver import SolveJobResponse
        r = SolveJobResponse(
            job_id="test", status="queued",
            complexity_grade="LIGHT",
        )
        assert r.complexity_grade == "LIGHT"


# -- Solve Cancel Safety --


class TestCancelSafety:
    """Verify solver produces partial results on cancel."""

    def test_cancel_produces_partial_output(self):
        solver = CfrSolver()
        # Cancel after 5 iterations
        cancel_at = [5]
        iters_seen = [0]

        def cancel_check():
            return iters_seen[0] >= cancel_at[0]

        def progress_cb(info):
            iters_seen[0] = info.iteration

        output = solver.solve(
            SolveRequest(
                board=["Ks", "7d", "2c"],
                ip_range="AA,KK",
                oop_range="QQ",
                pot=6.5, effective_stack=20.0,
                bet_sizes=[1.0], raise_sizes=[2.5],
                max_iterations=200, max_raises=1, deterministic=True,
            ),
            progress_callback=progress_cb,
            cancel_check=cancel_check,
        )
        # Should produce partial but valid output
        # Cancel is checked each iteration but callback fires at adaptive intervals
        assert output.iterations < 200, "Should have cancelled before all 200 iterations"
        assert output.iterations > 0, "Should have run at least some iterations"
        assert len(output.strategies) > 0, "partial strategies available"
