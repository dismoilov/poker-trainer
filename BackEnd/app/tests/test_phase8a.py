"""
Phase 8A tests — Persistent Job Infrastructure, Session Recovery, Runtime Robustness.

Tests cover:
- Solver job persistence at creation (early DB write)
- Solver result DB fallback when in-memory data is gone
- Progress endpoint DB fallback
- Node strategy persisted combo fallback
- data_source field correctness
- Play session recovery: stateRecovered flag
- Hand history survives state loss
- Stale in-memory session cleanup
- Better error messages for missing jobs
"""

import pytest
from datetime import datetime
from unittest.mock import patch
from app.models import SolveResultModel
from app.game_sessions.schemas import SessionState


# ── Solver Job Persistence ──


class TestSolverJobPersistence:
    """Test that solver jobs are persisted to DB at creation and on completion."""

    def test_result_endpoint_db_fallback(self, client, auth_header, db):
        """GET /result/{id} should return persisted data when not in memory."""
        # Insert a completed solve result directly into DB
        record = SolveResultModel(
            id="test-persist-001",
            status="done",
            config_json={"board": ["As", "Kh", "3d"], "ip_range": "AA", "oop_range": "KK"},
            iterations=50,
            convergence_metric=0.001,
            elapsed_seconds=2.5,
            tree_nodes=21,
            ip_combos=6,
            oop_combos=6,
            matchups=36,
            converged=True,
            solved_node_count=10,
            validation_json={"passed": True, "checks_run": 6, "checks_passed": 6},
            exploitability_json={"exploitability_mbb_per_hand": 15.0},
            trust_grade="APPROXIMATE",
            trust_grade_json={"grade": "APPROXIMATE"},
            combo_strategies_json={"node_0": {"AsAh": {"check": 0.6, "bet_50": 0.4}}},
            combo_storage_note="Persisted 1/10 nodes",
        )
        db.merge(record)
        db.commit()

        # Ensure NOT in _solve_jobs
        from app.api.routes_solver import _solve_jobs
        _solve_jobs.pop("test-persist-001", None)

        r = client.get("/api/solver/result/test-persist-001", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "done"
        assert data["data_source"] == "persisted_summary"
        assert data["iterations"] == 50
        assert data["convergence_metric"] == 0.001
        assert data["full_strategies_available"] is False

    def test_progress_endpoint_db_fallback(self, client, auth_header, db):
        """GET /job/{id} should return persisted data when not in memory."""
        record = SolveResultModel(
            id="test-persist-002",
            status="done",
            iterations=100,
            convergence_metric=0.0005,
            elapsed_seconds=5.0,
        )
        db.merge(record)
        db.commit()

        from app.api.routes_solver import _solve_jobs
        _solve_jobs.pop("test-persist-002", None)

        r = client.get("/api/solver/job/test-persist-002", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "done"
        assert data["data_source"] == "persisted_summary"
        assert data["iteration"] == 100
        assert data["progress_pct"] == 100.0

    def test_node_strategy_db_fallback(self, client, auth_header, db):
        """GET /node/{id}/{node} should return persisted combo subset."""
        record = SolveResultModel(
            id="test-persist-003",
            status="done",
            combo_strategies_json={
                "node_0": {"AsAh": {"check": 0.6, "bet_50": 0.4}},
                "node_1": {"KsKh": {"check": 0.3, "bet_50": 0.7}},
            },
            combo_storage_note="Persisted 2/10 nodes",
            node_summaries_json={
                "node_0": {"check": 0.6, "bet_50": 0.4},
                "node_1": {"check": 0.3, "bet_50": 0.7},
                "node_5": {"check": 0.5, "bet_50": 0.5},
            },
        )
        db.merge(record)
        db.commit()

        from app.api.routes_solver import _solve_jobs
        _solve_jobs.pop("test-persist-003", None)

        # Should return persisted combo data
        r = client.get("/api/solver/node/test-persist-003/node_0", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "AsAh" in data["combos"]
        assert "persisted" in data["message"].lower() or "Persisted" in data["message"]

    def test_node_strategy_summary_fallback(self, client, auth_header, db):
        """When combo data unavailable, fallback to aggregate summary."""
        record = SolveResultModel(
            id="test-persist-004",
            status="done",
            combo_strategies_json={"node_0": {"AsAh": {"check": 0.6, "bet_50": 0.4}}},
            node_summaries_json={
                "node_0": {"check": 0.6, "bet_50": 0.4},
                "node_5": {"check": 0.5, "bet_50": 0.5},
            },
        )
        db.merge(record)
        db.commit()

        from app.api.routes_solver import _solve_jobs
        _solve_jobs.pop("test-persist-004", None)

        # node_5 is only in summaries, not in combo data
        r = client.get("/api/solver/node/test-persist-004/node_5", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["combos"] == {}  # No per-combo data
        assert data["action_summary"]["check"] == 0.5
        assert "summary" in data["message"].lower() or "Aggregate" in data["message"]

    def test_missing_job_error_message(self, client, auth_header):
        """Missing job should give helpful error (not cryptic 404)."""
        from app.api.routes_solver import _solve_jobs
        _solve_jobs.pop("nonexistent-xyz", None)

        r = client.get("/api/solver/result/nonexistent-xyz", headers=auth_header)
        assert r.status_code == 404
        assert "expired" in r.json()["detail"].lower() or "history" in r.json()["detail"].lower()

    def test_in_memory_result_has_data_source(self, client, auth_header):
        """In-memory result should have data_source=in_memory."""
        from app.api.routes_solver import _solve_jobs
        _solve_jobs["test-inmem-001"] = {
            "status": "done",
            "iteration": 50,
            "total_iterations": 50,
            "convergence_metric": 0.001,
            "elapsed_seconds": 2.0,
            "tree_nodes": 21,
            "ip_combos": 6,
            "oop_combos": 6,
            "matchups": 36,
            "converged": True,
            "result": type("FakeResult", (), {"strategies": {"node_0": {"AsAh": {"check": 0.5}}}})(),
            "metadata": {"validation": {"passed": True, "checks_run": 1, "checks_passed": 1}},
        }

        r = client.get("/api/solver/result/test-inmem-001", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["data_source"] == "in_memory"

        # Cleanup
        _solve_jobs.pop("test-inmem-001", None)


# ── Play Session Recovery ──


class TestPlaySessionRecovery:
    """Test play session recovery behavior."""

    def test_new_session_not_recovered(self, client, auth_header):
        """Fresh session should NOT have stateRecovered flag."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["stateRecovered"] is False
        assert data["recoveryNote"] is None

    def test_recovery_after_state_loss(self, client, auth_header):
        """Session should report stateRecovered after in-memory state is cleared."""
        # Create session
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        assert r.status_code == 200
        sid = r.json()["sessionId"]

        # Clear in-memory state (simulating server restart)
        from app.game_sessions.service import _active_games, _active_decks
        _active_games.pop(sid, None)
        _active_decks.pop(sid, None)

        # Re-fetch session — should trigger recovery
        r = client.get(f"/api/play/session/{sid}", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["stateRecovered"] is True
        assert data["recoveryNote"] is not None
        assert "потеряно" in data["recoveryNote"].lower()  # Russian recovery note

    def test_hand_history_survives_state_loss(self, client, auth_header):
        """Completed hand history should persist through state loss."""
        # Create session and play a hand to completion
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        assert r.status_code == 200
        sid = r.json()["sessionId"]

        # Take actions until hand completes (fold)
        r = client.post("/api/play/action",
                        json={"sessionId": sid, "actionType": "fold", "amount": 0},
                        headers=auth_header)
        assert r.status_code == 200

        # Get next hand to complete the first hand's recording
        r = client.post(f"/api/play/next-hand/{sid}", headers=auth_header)
        assert r.status_code == 200

        # Check history before state loss
        r = client.get(f"/api/play/history/{sid}", headers=auth_header)
        assert r.status_code == 200
        history_before = r.json()
        assert len(history_before) >= 1

        # Clear in-memory state
        from app.game_sessions.service import _active_games, _active_decks
        _active_games.pop(sid, None)
        _active_decks.pop(sid, None)

        # History should still be available (persisted in DB)
        r = client.get(f"/api/play/history/{sid}", headers=auth_header)
        assert r.status_code == 200
        history_after = r.json()
        assert len(history_after) == len(history_before)
        assert history_after[0]["result"] in ("hero_win", "villain_win", "split", "fold")


# ── Stale Cleanup ──


class TestStaleCleanup:
    """Test stale in-memory session cleanup."""

    def test_cleanup_respects_cap(self):
        from app.game_sessions.service import (
            _active_games, _active_decks, cleanup_stale_in_memory,
        )
        from app.poker_engine.state import GameState

        # Save state
        saved_games = dict(_active_games)
        saved_decks = dict(_active_decks)
        _active_games.clear()
        _active_decks.clear()

        try:
            # Add 5 fake sessions
            for i in range(5):
                _active_games[f"test-session-{i}"] = None  # type: ignore
            assert len(_active_games) == 5

            # Cleanup with cap=3 should remove 2
            cleanup_stale_in_memory(max_sessions=3)
            assert len(_active_games) == 3

            # Should have removed the first two
            assert "test-session-0" not in _active_games
            assert "test-session-1" not in _active_games
            assert "test-session-4" in _active_games
        finally:
            _active_games.clear()
            _active_games.update(saved_games)
            _active_decks.clear()
            _active_decks.update(saved_decks)

    def test_cleanup_noop_under_cap(self):
        from app.game_sessions.service import (
            _active_games, cleanup_stale_in_memory,
        )

        saved = dict(_active_games)
        _active_games.clear()
        try:
            _active_games["test-only-one"] = None  # type: ignore
            cleanup_stale_in_memory(max_sessions=50)
            assert "test-only-one" in _active_games
        finally:
            _active_games.clear()
            _active_games.update(saved)


# ── Solver Job Stale Cleanup Integration ──


class TestSolverJobStaleCleanup:

    def test_stale_solver_job_cleanup(self):
        """Stale done jobs should be cleaned."""
        from app.api.routes_solver import _solve_jobs, _cleanup_stale_jobs, STALE_JOB_EXPIRY_SECONDS
        from datetime import timedelta

        old_time = (datetime.utcnow() - timedelta(seconds=STALE_JOB_EXPIRY_SECONDS + 60)).isoformat()
        _solve_jobs["test-stale-8a"] = {"status": "done", "created_at": old_time}
        _solve_jobs["test-fresh-8a"] = {"status": "done", "created_at": datetime.utcnow().isoformat()}

        _cleanup_stale_jobs()

        assert "test-stale-8a" not in _solve_jobs
        assert "test-fresh-8a" in _solve_jobs
        _solve_jobs.pop("test-fresh-8a", None)


# ── Data Source Field Compliance ──


class TestDataSourceField:
    """Verify data_source field is set correctly throughout."""

    def test_progress_model_has_data_source(self):
        from app.api.routes_solver import SolveJobProgress
        p = SolveJobProgress(
            job_id="test", status="done",
            iteration=50, total_iterations=50,
            convergence_metric=0.001, elapsed_seconds=2.0,
            data_source="in_memory",
        )
        assert p.data_source == "in_memory"

    def test_result_model_has_data_source(self):
        from app.api.routes_solver import SolveResultResponse
        r = SolveResultResponse(
            job_id="test", status="done",
            data_source="persisted_summary",
        )
        assert r.data_source == "persisted_summary"

    def test_build_result_from_db_sets_persisted(self, db):
        from app.api.routes_solver import _build_result_from_db
        record = SolveResultModel(
            id="test-build-001",
            status="done",
            iterations=50,
        )
        db.merge(record)
        db.commit()

        result = _build_result_from_db(record)
        assert result.data_source == "persisted_summary"
        assert result.full_strategies_available is False

    def test_build_progress_from_db_sets_persisted(self, db):
        from app.api.routes_solver import _build_progress_from_db
        record = SolveResultModel(
            id="test-build-002",
            status="done",
            iterations=100,
        )
        db.merge(record)
        db.commit()

        result = _build_progress_from_db(record)
        assert result.data_source == "persisted_summary"
        assert result.progress_pct == 100.0
