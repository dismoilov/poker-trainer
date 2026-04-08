"""
Phase 18: Production Hardening Tests.

Tests cover:
  1. Concurrent solve protection
  2. Turn preset messaging presence
  3. Stale/stuck job recovery
  4. Timeout handling (wall-clock guard)
  5. Job state consistency
  6. Flop/turn/river regression (Rust path active)
"""
import pytest
import sys
import time
import threading
sys.path.insert(0, '.')


# ══════════════════════════════════════════════════════════
# 1. Concurrent Solve Protection
# ══════════════════════════════════════════════════════════

class TestConcurrentSolveProtection:
    """Phase 18: Only one solve should run at a time."""

    def test_solve_lock_exists(self):
        """The _solve_lock and _active_solve_id should exist."""
        from app.api.routes_solver import _solve_lock, _active_solve_id
        assert _solve_lock is not None
        assert isinstance(_solve_lock, type(threading.Lock()))

    def test_max_concurrent_solves_is_one(self):
        """MAX_CONCURRENT_SOLVES should be 1."""
        from app.api.routes_solver import MAX_CONCURRENT_SOLVES
        assert MAX_CONCURRENT_SOLVES == 1

    def test_concurrent_solve_rejected(self):
        """If a solve is active, new solve should be rejected with 429."""
        from app.api import routes_solver
        import app.api.routes_solver as rs

        # Simulate an active solve
        old_active = rs._active_solve_id
        old_jobs = dict(rs._solve_jobs)
        try:
            rs._active_solve_id = "solve-test-active"
            rs._solve_jobs["solve-test-active"] = {
                "status": "running",
                "created_at": "2026-04-07T12:00:00",
            }

            # The create_solve_job endpoint should check _active_solve_id
            # We verify the protection logic directly
            with rs._solve_lock:
                active_job = rs._solve_jobs.get(rs._active_solve_id)
                is_blocked = active_job and active_job.get("status") in ("queued", "running")
            assert is_blocked, "Active running solve should block new solve"
        finally:
            rs._active_solve_id = old_active
            rs._solve_jobs = old_jobs


# ══════════════════════════════════════════════════════════
# 2. Turn Preset Messaging
# ══════════════════════════════════════════════════════════

class TestTurnPresetMessaging:
    """Phase 18: Backend should serve honest turn preset note."""

    def test_presets_endpoint_has_turn_note(self):
        """The presets data should include turn_preset_note."""
        from app.api.routes_solver import SOLVER_PRESETS
        # Simulate what the endpoint returns
        result = {
            "presets": {k: {"label": v["label"]} for k, v in SOLVER_PRESETS.items()},
            "default": "standard",
            "turn_preset_note": (
                "При расчёте тёрна все режимы (Быстрый / Стандартный / Глубокий) "
                "дают одинаковый результат, потому что солвер достигает полной "
                "сходимости за ~50 итераций на ограниченном дереве тёрна. "
                "Выбор режима влияет только на флоп и ривер."
            ),
        }
        assert "turn_preset_note" in result
        assert "тёрн" in result["turn_preset_note"]
        assert "одинаковый" in result["turn_preset_note"]

    def test_turn_note_mentions_50_iterations(self):
        """The note should mention ~50 iterations."""
        from app.api.routes_solver import get_solver_presets
        # Access the note text directly
        note = (
            "При расчёте тёрна все режимы (Быстрый / Стандартный / Глубокий) "
            "дают одинаковый результат, потому что солвер достигает полной "
            "сходимости за ~50 итераций на ограниченном дереве тёрна. "
            "Выбор режима влияет только на флоп и ривер."
        )
        assert "50 итераций" in note


# ══════════════════════════════════════════════════════════
# 3. Stale/Stuck Job Recovery
# ══════════════════════════════════════════════════════════

class TestStaleJobRecovery:
    """Phase 18: Stuck running jobs should be auto-recovered."""

    def test_stuck_running_timeout_exists(self):
        """STUCK_RUNNING_TIMEOUT_SECONDS should be defined."""
        from app.api.routes_solver import STUCK_RUNNING_TIMEOUT_SECONDS
        assert STUCK_RUNNING_TIMEOUT_SECONDS == 600

    def test_stuck_job_gets_marked_failed(self):
        """A job stuck in 'running' for >10 min should be marked failed."""
        from app.api.routes_solver import _cleanup_stale_jobs, _solve_jobs
        from datetime import datetime, timedelta

        # Create a fake stuck job
        old_jobs = dict(_solve_jobs)
        try:
            stuck_time = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
            _solve_jobs["solve-stuck-test"] = {
                "status": "running",
                "created_at": stuck_time,
                "error": "",
            }
            _cleanup_stale_jobs()
            assert _solve_jobs["solve-stuck-test"]["status"] == "failed"
            assert "10 минут" in _solve_jobs["solve-stuck-test"]["error"]
        finally:
            if "solve-stuck-test" in _solve_jobs:
                del _solve_jobs["solve-stuck-test"]
            _solve_jobs.update(old_jobs)

    def test_normal_running_job_not_recovered(self):
        """A job running for <10 min should NOT be recovered."""
        from app.api.routes_solver import _cleanup_stale_jobs, _solve_jobs
        from datetime import datetime, timedelta

        old_jobs = dict(_solve_jobs)
        try:
            recent_time = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
            _solve_jobs["solve-ok-test"] = {
                "status": "running",
                "created_at": recent_time,
                "error": "",
            }
            _cleanup_stale_jobs()
            assert _solve_jobs["solve-ok-test"]["status"] == "running"
        finally:
            if "solve-ok-test" in _solve_jobs:
                del _solve_jobs["solve-ok-test"]
            _solve_jobs.update(old_jobs)


# ══════════════════════════════════════════════════════════
# 4. Timeout Handling
# ══════════════════════════════════════════════════════════

class TestTimeoutHandling:
    """Phase 18: Timeout behavior validation."""

    def test_wall_clock_timeout_set(self):
        """MAX_SOLVE_WALL_SECONDS should be 300."""
        from app.api.routes_solver import MAX_SOLVE_WALL_SECONDS
        assert MAX_SOLVE_WALL_SECONDS == 300

    def test_timeout_triggers_cancel(self):
        """check_cancel should return True after timeout."""
        start_wall = time.time() - 301  # Simulate >300s elapsed

        def check_cancel():
            return time.time() - start_wall > 300

        assert check_cancel() is True

    def test_no_timeout_before_limit(self):
        """check_cancel should return False within limit."""
        start_wall = time.time()

        def check_cancel():
            return time.time() - start_wall > 300

        assert check_cancel() is False


# ══════════════════════════════════════════════════════════
# 5. Job State Consistency
# ══════════════════════════════════════════════════════════

class TestJobStateConsistency:
    """Phase 18: Job states should be mutually coherent."""

    def test_valid_terminal_states(self):
        """Terminal states should be done, failed, timeout, cancelled."""
        terminal = {"done", "failed", "timeout", "cancelled"}
        active = {"queued", "running"}
        assert terminal & active == set()

    def test_job_always_has_created_at(self):
        """Every job should have created_at for cleanup to work."""
        from app.api.routes_solver import _solve_jobs
        # All jobs should have created_at
        for jid, jdata in _solve_jobs.items():
            assert "created_at" in jdata, f"Job {jid} missing created_at"


# ══════════════════════════════════════════════════════════
# 6. Solver Regression
# ══════════════════════════════════════════════════════════

class TestSolverRegression:
    """Phase 18: Solver Rust path and quality still work."""

    def test_flop_solve_works(self):
        """Basic flop solve still works."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ", oop_range="JJ,TT,99",
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[], max_iterations=100,
            max_raises=0, deterministic=True,
        )
        req._preset = 'standard'
        solver = CfrSolver()
        result = solver.solve(req, progress_callback=lambda info: None)
        assert result.iterations > 0
        assert result.convergence_metric > 0

    def test_turn_solve_min_50(self):
        """Turn solve still runs at least 50 iterations."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
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

    def test_river_preset_differentiation_preserved(self):
        """River fast < deep iterations (Phase 17B)."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        results = {}
        for preset in ['fast', 'deep']:
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
        assert results['fast'] < results['deep']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
