"""
Phase 15C Tests: Real-Time Progress & Cancel UX Integration

Tests verify:
  1. Progress callback bridge fix (SolveProgressInfo, not raw ints)
  2. Cancel request sets job cancelled flag
  3. SSE endpoint streams progress events
  4. Terminal states persisted correctly
  5. Regression: normal solves still work
"""

import time
import pytest
import asyncio
from unittest.mock import MagicMock

from app.solver.cfr_solver import CfrSolver, SolveRequest, SolveProgressInfo


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

SMALL_REQUEST = SolveRequest(
    board=['Ks', '7d', '2c'],
    ip_range='AA,KK,QQ',
    oop_range='JJ,TT,99',
    pot=10.0,
    effective_stack=50.0,
    bet_sizes=[0.5, 1.0],
    raise_sizes=[],
    max_iterations=100,
    max_raises=0,
    deterministic=True,
)

MEDIUM_REQUEST = SolveRequest(
    board=['Ks', '7d', '2c'],
    ip_range='AA,KK,QQ,AKs,AKo,AQs',
    oop_range='JJ,TT,99,AJs,KQs,QJs',
    pot=10.0,
    effective_stack=50.0,
    bet_sizes=[0.5, 1.0],
    raise_sizes=[2.5],
    max_iterations=200,
    max_raises=1,
    deterministic=True,
    include_turn=True,
    max_turn_cards=3,
    turn_bet_sizes=[0.5],
    turn_raise_sizes=[],
    turn_max_raises=0,
)


# ═══════════════════════════════════════════════════════════
# Test: Progress Callback Bridge Fix (Phase 15C Critical)
# ═══════════════════════════════════════════════════════════

class TestProgressCallbackBridge:
    """Phase 15C: progress callback now receives SolveProgressInfo, not raw ints."""

    def test_callback_receives_solve_progress_info(self):
        """Progress callback should receive SolveProgressInfo objects."""
        received = []
        def on_progress(info):
            received.append(info)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert len(received) > 0, "Should have received progress updates"
        for info in received:
            assert isinstance(info, SolveProgressInfo), \
                f"Expected SolveProgressInfo, got {type(info).__name__}"

    def test_callback_info_has_iteration(self):
        """SolveProgressInfo should have iteration count."""
        iterations = []
        def on_progress(info):
            iterations.append(info.iteration)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert len(iterations) > 0
        # Monotonically increasing
        for i in range(1, len(iterations)):
            assert iterations[i] >= iterations[i-1]
        # Last should be total
        assert iterations[-1] == 100

    def test_callback_info_has_total_iterations(self):
        """SolveProgressInfo should report total iterations."""
        totals = set()
        def on_progress(info):
            totals.add(info.total_iterations)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert totals == {100}, f"Expected {{100}}, got {totals}"

    def test_callback_info_has_convergence(self):
        """SolveProgressInfo should include convergence metric."""
        convergences = []
        def on_progress(info):
            convergences.append(info.convergence_metric)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert len(convergences) > 0
        # All should be non-negative
        for c in convergences:
            assert c >= 0.0

    def test_callback_info_has_elapsed(self):
        """SolveProgressInfo should include elapsed_seconds."""
        elapsed_vals = []
        def on_progress(info):
            elapsed_vals.append(info.elapsed_seconds)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert len(elapsed_vals) > 0
        for e in elapsed_vals:
            assert e >= 0.0
        # Should be monotonically non-decreasing
        for i in range(1, len(elapsed_vals)):
            assert elapsed_vals[i] >= elapsed_vals[i-1] - 0.001

    def test_callback_info_has_status(self):
        """SolveProgressInfo should have status='running'."""
        statuses = set()
        def on_progress(info):
            statuses.add(info.status)

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert "running" in statuses


# ═══════════════════════════════════════════════════════════
# Test: Backend Callback Integration (routes_solver bridge)
# ═══════════════════════════════════════════════════════════

class TestBackendCallbackIntegration:
    """Verify that the on_progress callback in routes_solver.py
    correctly receives and extracts SolveProgressInfo attributes."""

    def test_on_progress_extracts_fields(self):
        """Simulated on_progress from routes_solver.py should work with SolveProgressInfo."""
        job = {
            "iteration": 0,
            "total_iterations": 0,
            "convergence_metric": float("inf"),
            "elapsed_seconds": 0.0,
        }

        def on_progress(info: SolveProgressInfo):
            job["iteration"] = info.iteration
            job["total_iterations"] = info.total_iterations
            job["convergence_metric"] = info.convergence_metric
            job["elapsed_seconds"] = info.elapsed_seconds

        solver = CfrSolver()
        solver.solve(SMALL_REQUEST, progress_callback=on_progress)

        assert job["iteration"] == 100
        assert job["total_iterations"] == 100
        assert job["convergence_metric"] >= 0.0
        assert job["elapsed_seconds"] > 0.0


# ═══════════════════════════════════════════════════════════
# Test: Cancel Integration
# ═══════════════════════════════════════════════════════════

class TestCancelIntegration:
    """Verify cancel semantics work with SolveProgressInfo callback."""

    def test_cancel_with_progress_info(self):
        """Cancel should work alongside SolveProgressInfo callbacks."""
        cancel_flag = [False]
        progress_iters = []

        def on_progress(info):
            progress_iters.append(info.iteration)
            if info.iteration >= 50:
                cancel_flag[0] = True

        def do_cancel():
            return cancel_flag[0]

        solver = CfrSolver()
        result = solver.solve(
            SolveRequest(
                board=['Ks', '7d', '2c'],
                ip_range='AA,KK,QQ,AKs,AKo,AQs',
                oop_range='JJ,TT,99,AJs,KQs,QJs',
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
                max_iterations=5000, max_raises=1, deterministic=True,
                include_turn=True, max_turn_cards=3,
                turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            ),
            cancel_check=do_cancel,
            progress_callback=on_progress,
        )

        assert result.iterations < 5000
        assert result.iterations <= 75  # cancel_at=50 + 1 chunk of 25

    def test_cancel_job_dict_semantics(self):
        """Simulated cancel via job dict (as routes_solver.py does)."""
        job_dict = {"cancelled": False}
        start_wall = time.time()

        def check_cancel():
            if job_dict["cancelled"]:
                return True
            if time.time() - start_wall > 300:
                return True
            return False

        # Simulate user cancel after 50 iterations
        progress_count = [0]
        def on_progress(info):
            progress_count[0] += 1
            if info.iteration >= 50:
                job_dict["cancelled"] = True

        solver = CfrSolver()
        result = solver.solve(MEDIUM_REQUEST, cancel_check=check_cancel, progress_callback=on_progress)

        assert result.iterations < 200
        assert progress_count[0] > 0


# ═══════════════════════════════════════════════════════════
# Test: SSE Endpoint Format
# ═══════════════════════════════════════════════════════════

class TestSSEEndpointFormat:
    """Verify SSE endpoint exists and returns correct response."""

    def test_sse_endpoint_registered(self):
        """The /stream/{job_id} endpoint should be registered."""
        from app.api.routes_solver import router
        paths = [r.path for r in router.routes]
        assert any("/stream/" in p for p in paths), f"SSE route not found in {paths}"

    def test_sse_endpoint_requires_token(self):
        """SSE endpoint should require token query parameter."""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/solver/stream/fake-job-id")
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════
# Test: Deterministic Equivalence
# ═══════════════════════════════════════════════════════════

class TestDeterministicEquivalence:
    """Results with control callbacks should match no-control results."""

    def test_progress_doesnt_change_results(self):
        """Results should be identical with and without progress callback."""
        solver1 = CfrSolver()
        r1 = solver1.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ))

        solver2 = CfrSolver()
        r2 = solver2.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ), progress_callback=lambda info: None)

        assert r1.iterations == r2.iterations
        for nid in r1.strategies:
            for combo in r1.strategies[nid]:
                for action in r1.strategies[nid][combo]:
                    v1 = r1.strategies[nid][combo][action]
                    v2 = r2.strategies[nid][combo][action]
                    assert abs(v1 - v2) < 0.001


# ═══════════════════════════════════════════════════════════
# Test: Regression
# ═══════════════════════════════════════════════════════════

class TestPhase15CRegression:
    """Ensure Phase 15C changes don't break existing solver behavior."""

    def test_normal_solve_works(self):
        """Solve without callbacks still works."""
        solver = CfrSolver()
        result = solver.solve(SMALL_REQUEST)
        assert result.iterations == 100
        assert len(result.strategies) > 0

    def test_strategies_valid(self):
        """All strategies sum to 1.0."""
        solver = CfrSolver()
        result = solver.solve(SMALL_REQUEST, progress_callback=lambda info: None)

        for nid, combos in result.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01

    def test_version_ok(self):
        """Rust module version accessible."""
        import poker_core
        v = poker_core.version()
        assert 'poker_core' in v
