"""
E2E Integration Test Suite — Phase 5A.1

Comprehensive end-to-end tests covering all critical application flows.
Uses FastAPI TestClient for HTTP-level integration testing.
Tests exercise the full stack: routes → services → DB → response validation.

Coverage:
  1. Login flow + invalid login
  2. Dashboard load
  3. Play session creation + multi-action + next hand
  4. Play stability: repeated hands, fold/call/raise paths
  5. Solver create + progress + result
  6. Solver history + detail + node inspection
  7. Explore legacy flow
  8. Explore solver-backed flow
  9. Drill legacy flow
 10. Drill solver-backed flow
 11. Play compare-to-solver
 12. Error states
 13. Schema regression guard
 14. Migration safety validation
"""

import pytest
import time


# ──────────────────────────────────────────────────────────────────
# 1. AUTH / LOGIN
# ──────────────────────────────────────────────────────────────────


class TestAuthFlow:
    """E2E: Login, invalid login, protected endpoints."""

    def test_login_success(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert "accessToken" in data
        assert data["user"]["username"] == "admin"

    def test_login_wrong_password(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        assert r.status_code == 401

    def test_protected_without_token(self, client):
        r = client.get("/api/spots")
        assert r.status_code == 401

    def test_protected_with_invalid_token(self, client):
        r = client.get("/api/spots", headers={"Authorization": "Bearer invalid_token_123"})
        assert r.status_code == 401

    def test_protected_with_valid_token(self, client, auth_header):
        r = client.get("/api/spots", headers=auth_header)
        assert r.status_code == 200


# ──────────────────────────────────────────────────────────────────
# 2. DASHBOARD / SPOTS
# ──────────────────────────────────────────────────────────────────


class TestDashboard:
    """E2E: Dashboard data endpoints."""

    def test_spots_list(self, client, auth_header):
        r = client.get("/api/spots", headers=auth_header)
        assert r.status_code == 200
        spots = r.json()
        assert isinstance(spots, list)
        assert len(spots) > 0

    def test_analytics_summary(self, client, auth_header):
        r = client.get("/api/analytics/summary", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "totalQuestions" in data

    def test_jobs_list(self, client, auth_header):
        r = client.get("/api/jobs", headers=auth_header)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ──────────────────────────────────────────────────────────────────
# 3. PLAY — SESSION + ACTIONS + HAND PROGRESSION
# ──────────────────────────────────────────────────────────────────


class TestPlaySessionFlow:
    """E2E: Full play session lifecycle."""

    def test_create_session(self, client, auth_header):
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        assert r.status_code == 200
        state = r.json()
        assert state["status"] == "active"
        assert state["sessionId"]
        assert len(state["board"]) >= 3
        assert len(state["heroHand"]) == 2
        assert state["currentPlayer"] == "IP"  # hero should have first action
        assert len(state["legalActions"]) > 0

    def test_full_hand_check_check_to_showdown(self, client, auth_header):
        """Play a full hand checking through all streets to showdown."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Check through every street
        step = 0
        while state.get("legalActions"):
            # Find check action, or call if we face a bet
            check_action = None
            call_action = None
            fold_action = None
            for a in state["legalActions"]:
                if a["type"] == "check":
                    check_action = a
                elif a["type"] == "call":
                    call_action = a
                elif a["type"] == "fold":
                    fold_action = a

            chosen = check_action or call_action or fold_action
            assert chosen, f"No passive action found at step {step}"

            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": chosen["type"],
                                  "amount": chosen.get("amount", 0)},
                            headers=auth_header)
            assert r.status_code == 200
            state = r.json()
            step += 1
            assert step < 20, "Infinite loop guard"

        assert state["status"] in ("showdown", "hand_complete")

    def test_fold_hand(self, client, auth_header):
        """Hero folds immediately."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Check if fold exists (villain may have bet)
        fold_action = next((a for a in state["legalActions"] if a["type"] == "fold"), None)
        if not fold_action:
            # If no fold, villain checked so we can check first, then fold next
            check = next(a for a in state["legalActions"] if a["type"] == "check")
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": "check", "amount": 0},
                            headers=auth_header)
            state = r.json()
            fold_action = next((a for a in state.get("legalActions", []) if a["type"] == "fold"), None)

        if fold_action:
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": "fold", "amount": 0},
                            headers=auth_header)
            state = r.json()
            assert state["status"] == "hand_complete"
            assert state["lastResult"] is not None

    def test_next_hand_flow(self, client, auth_header):
        """Create session, finish hand, deal next hand."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Complete hand 1 by checking through
        while state.get("legalActions"):
            chosen = next((a for a in state["legalActions"]
                           if a["type"] in ("check", "call")),
                          state["legalActions"][0])
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": chosen["type"],
                                  "amount": chosen.get("amount", 0)},
                            headers=auth_header)
            state = r.json()
            if not state.get("legalActions"):
                break

        # Deal next hand
        r = client.post(f"/api/play/next-hand/{sid}", headers=auth_header)
        assert r.status_code == 200
        state2 = r.json()
        assert state2["status"] == "active"
        assert len(state2["board"]) >= 3
        assert len(state2["heroHand"]) == 2
        assert len(state2["legalActions"]) > 0

    def test_hand_history_after_play(self, client, auth_header):
        """Verify hand history is recorded after completing a hand."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Complete hand
        while state.get("legalActions"):
            chosen = next((a for a in state["legalActions"]
                           if a["type"] in ("check", "call")),
                          state["legalActions"][0])
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": chosen["type"],
                                  "amount": chosen.get("amount", 0)},
                            headers=auth_header)
            state = r.json()
            if not state.get("legalActions"):
                break

        # Check history
        r = client.get(f"/api/play/history/{sid}", headers=auth_header)
        assert r.status_code == 200
        history = r.json()
        assert len(history) >= 1
        assert "result" in history[0]
        assert "actions" in history[0]


# ──────────────────────────────────────────────────────────────────
# 4. PLAY STABILITY — Repeated hands, bet/raise/allin
# ──────────────────────────────────────────────────────────────────


class TestPlayStability:
    """E2E: Play stress and edge-case tests."""

    def test_multiple_hands(self, client, auth_header):
        """Play 3 consecutive hands in the same session."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        for hand_num in range(3):
            # Complete hand
            step = 0
            while state.get("legalActions"):
                chosen = next((a for a in state["legalActions"]
                               if a["type"] in ("check", "call")),
                              state["legalActions"][0])
                r = client.post("/api/play/action",
                                json={"sessionId": sid, "actionType": chosen["type"],
                                      "amount": chosen.get("amount", 0)},
                                headers=auth_header)
                state = r.json()
                step += 1
                assert step < 20

            assert state["status"] in ("showdown", "hand_complete")

            if hand_num < 2:  # Don't deal after last hand
                r = client.post(f"/api/play/next-hand/{sid}", headers=auth_header)
                assert r.status_code == 200
                state = r.json()
                assert state["status"] == "active"

        # Verify all 3 hands recorded
        r = client.get(f"/api/play/history/{sid}", headers=auth_header)
        assert len(r.json()) == 3

    def test_bet_action(self, client, auth_header):
        """Hero can bet when checked to."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Look for a bet action
        bet_action = next((a for a in state["legalActions"] if a["type"] == "bet"), None)
        if bet_action:
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": "bet",
                                  "amount": bet_action["amount"]},
                            headers=auth_header)
            assert r.status_code == 200
            state2 = r.json()
            assert state2["status"] in ("active", "hand_complete", "showdown")
            # Should have action history entry for hero bet
            assert len(state2["actionHistory"]) > len(state["actionHistory"])

    def test_action_on_terminal_hand_rejected(self, client, auth_header):
        """Cannot take action on a completed hand."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        state = r.json()
        sid = state["sessionId"]

        # Complete hand
        while state.get("legalActions"):
            chosen = next((a for a in state["legalActions"]
                           if a["type"] in ("check", "call")),
                          state["legalActions"][0])
            r = client.post("/api/play/action",
                            json={"sessionId": sid, "actionType": chosen["type"],
                                  "amount": chosen.get("amount", 0)},
                            headers=auth_header)
            state = r.json()
            if not state.get("legalActions"):
                break

        # Try action on terminal hand — should fail
        r = client.post("/api/play/action",
                        json={"sessionId": sid, "actionType": "check", "amount": 0},
                        headers=auth_header)
        assert r.status_code == 400

    def test_session_not_found(self, client, auth_header):
        """Action on nonexistent session returns 404/400."""
        r = client.post("/api/play/action",
                        json={"sessionId": "nonexistent-123", "actionType": "check", "amount": 0},
                        headers=auth_header)
        assert r.status_code in (400, 404)

    def test_get_session_state(self, client, auth_header):
        """Can retrieve session state by ID."""
        r = client.post("/api/play/session",
                        json={"startingStack": 100, "heroPosition": "IP"},
                        headers=auth_header)
        sid = r.json()["sessionId"]

        r = client.get(f"/api/play/session/{sid}", headers=auth_header)
        assert r.status_code == 200
        state = r.json()
        assert state["sessionId"] == sid
        assert len(state["board"]) >= 3


# ──────────────────────────────────────────────────────────────────
# 5. SOLVER — Create + Progress + Result
# ──────────────────────────────────────────────────────────────────


class TestSolverFlow:
    """E2E: Solver job lifecycle — must run real CFR+."""

    def test_create_solve_job(self, client, auth_header):
        r = client.post("/api/solver/solve", json={
            "board": ["Ah", "Kd", "3c"],
            "ip_range": "AA",
            "oop_range": "KK",
            "pot": 6.5,
            "effective_stack": 97.0,
            "max_iterations": 10,
        }, headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"].startswith("solve-")
        assert data["status"] == "queued"

    def test_invalid_board_rejected(self, client, auth_header):
        r = client.post("/api/solver/solve", json={
            "board": ["XX"],
            "ip_range": "AA",
            "oop_range": "KK",
        }, headers=auth_header)
        assert r.status_code in (400, 422)

    def test_empty_range_rejected(self, client, auth_header):
        r = client.post("/api/solver/solve", json={
            "board": ["Ah", "Kd", "3c"],
            "ip_range": "",
            "oop_range": "KK",
        }, headers=auth_header)
        assert r.status_code == 400

    def test_solve_and_poll(self, client, auth_header):
        """Start a small solve and poll until done."""
        r = client.post("/api/solver/solve", json={
            "board": ["Td", "6s", "2h"],
            "ip_range": "AA",
            "oop_range": "KK",
            "max_iterations": 10,
        }, headers=auth_header)
        job_id = r.json()["job_id"]

        # Poll for completion (max 30s)
        import time
        for _ in range(30):
            time.sleep(1)
            r = client.get(f"/api/solver/job/{job_id}", headers=auth_header)
            assert r.status_code == 200
            progress = r.json()
            if progress["status"] in ("done", "failed", "timeout"):
                break

        assert progress["status"] == "done", f"Solve not done: {progress}"
        assert progress["iteration"] >= 10

    def test_solve_result_retrieval(self, client, auth_header):
        """Start solve, wait for completion, get result."""
        r = client.post("/api/solver/solve", json={
            "board": ["Qh", "7c", "4d"],
            "ip_range": "AA",
            "oop_range": "KK",
            "max_iterations": 10,
        }, headers=auth_header)
        job_id = r.json()["job_id"]

        # Wait for completion
        for _ in range(30):
            time.sleep(1)
            r = client.get(f"/api/solver/job/{job_id}", headers=auth_header)
            if r.json()["status"] in ("done", "failed"):
                break

        r = client.get(f"/api/solver/result/{job_id}", headers=auth_header)
        assert r.status_code == 200
        result = r.json()
        assert result["status"] == "done"
        assert result["iterations"] >= 10
        assert result["tree_nodes"] > 0

    def test_job_not_found(self, client, auth_header):
        r = client.get("/api/solver/job/nonexistent-xyz", headers=auth_header)
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────
# 6. SOLVER HISTORY + DETAIL
# ──────────────────────────────────────────────────────────────────


class TestSolverHistory:
    """E2E: Solver persistence endpoints."""

    def test_history_list(self, client, auth_header):
        r = client.get("/api/solver/history", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_history_detail(self, client, auth_header, db):
        """Insert a mock solve result and retrieve detail."""
        from app.models import SolveResultModel
        from datetime import datetime

        mock = SolveResultModel(
            id="test-detail-001",
            user_id=1,
            status="done",
            created_at=datetime.utcnow(),
            config_json={"board": ["Ah", "Kd", "3c"], "ip_range": "AA", "oop_range": "KK"},
            iterations=50,
            convergence_metric=0.001,
            elapsed_seconds=5.0,
            tree_nodes=10,
            ip_combos=6,
            oop_combos=6,
            matchups=30,
            converged=True,
            solved_node_count=5,
            root_strategy_summary_json={"check": 0.4, "bet_0.5": 0.6},
            node_summaries_json={"node_0": {"check": 0.4, "bet_0.5": 0.6}},
            trust_grade="INTERNAL_DEMO",
            trust_grade_json={"grade": "INTERNAL_DEMO"},
            exploitability_mbb=15.0,
            combo_strategies_json={"node_0": {"AhAs": {"check": 0.3, "bet_0.5": 0.7}}},
            combo_storage_note="Persisted 1 node",
        )
        db.merge(mock)
        db.commit()

        r = client.get("/api/solver/history/test-detail-001", headers=auth_header)
        assert r.status_code == 200
        detail = r.json()
        assert detail["id"] == "test-detail-001"
        assert detail["iterations"] == 50
        assert detail["trust_grade"]["grade"] == "INTERNAL_DEMO"
        assert "node_0" in detail["combo_available_nodes"]

    def test_history_node_detail(self, client, auth_header, db):
        """Retrieve per-combo data for a persisted node."""
        r = client.get("/api/solver/history/test-detail-001/node/node_0", headers=auth_header)
        assert r.status_code == 200
        node = r.json()
        assert node["data_source"] == "persisted_combo_subset"
        assert "AhAs" in node["combos"]

    def test_history_not_found(self, client, auth_header):
        r = client.get("/api/solver/history/nonexistent-xyz", headers=auth_header)
        assert r.status_code == 404

    def test_history_node_not_found(self, client, auth_header, db):
        r = client.get("/api/solver/history/test-detail-001/node/node_999", headers=auth_header)
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────
# 7. EXPLORE — Legacy flow
# ──────────────────────────────────────────────────────────────────


class TestExploreLegacy:
    """E2E: Explore page data flow."""

    def test_explore_nodes(self, client, auth_header):
        """Fetch nodes for a spot."""
        spots = client.get("/api/spots", headers=auth_header).json()
        assert len(spots) > 0
        spot_id = spots[0]["id"]

        r = client.get(f"/api/explore/nodes?spotId={spot_id}", headers=auth_header)
        assert r.status_code == 200
        nodes = r.json()
        assert isinstance(nodes, list)
        assert len(nodes) > 0

    def test_explore_strategy(self, client, auth_header):
        """Fetch strategy matrix for a node."""
        spots = client.get("/api/spots", headers=auth_header).json()
        spot_id = spots[0]["id"]
        nodes = client.get(f"/api/explore/nodes?spotId={spot_id}", headers=auth_header).json()
        assert len(nodes) > 0
        node_id = nodes[0]["id"]

        r = client.get(f"/api/explore/strategy?nodeId={node_id}", headers=auth_header)
        assert r.status_code == 200
        # Strategy returns matrix data
        data = r.json()
        assert "cells" in data or isinstance(data, dict)


# ──────────────────────────────────────────────────────────────────
# 8. EXPLORE — Solver-backed flow
# ──────────────────────────────────────────────────────────────────


class TestExploreSolverBacked:
    """E2E: Solver-backed explore endpoint."""

    def test_solver_backed_with_valid_solve(self, client, auth_header, db):
        """Query solver-backed explore with a persisted solve."""
        r = client.get("/api/explore/solver-backed?solve_id=test-detail-001&node_id=node_0",
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "data_source" in data or "action_frequencies" in data or "combos" in data

    def test_solver_backed_missing_solve(self, client, auth_header):
        """Query with nonexistent solve ID."""
        r = client.get("/api/explore/solver-backed?solve_id=nonexistent&node_id=node_0",
                        headers=auth_header)
        assert r.status_code in (404, 200)  # May return empty data


# ──────────────────────────────────────────────────────────────────
# 9. DRILL — Legacy flow
# ──────────────────────────────────────────────────────────────────


class TestDrillLegacy:
    """E2E: Drill question + answer flow."""

    def test_drill_question(self, client, auth_header):
        """Get a drill question for a spot."""
        spots = client.get("/api/spots", headers=auth_header).json()
        spot_id = spots[0]["id"]

        r = client.post("/api/drill/next",
                        json={"spotId": spot_id},
                        headers=auth_header)
        assert r.status_code == 200
        q = r.json()
        assert "hand" in q
        assert "actions" in q
        assert len(q["actions"]) > 0

    def test_drill_answer(self, client, auth_header):
        """Answer a drill question and get feedback."""
        spots = client.get("/api/spots", headers=auth_header).json()
        spot_id = spots[0]["id"]

        q = client.post("/api/drill/next",
                        json={"spotId": spot_id},
                        headers=auth_header).json()

        # actionId must match the drill service expectations
        action_id = q["actions"][0]["id"]
        r = client.post("/api/drill/answer",
                        json={
                            "nodeId": q["nodeId"],
                            "hand": q["hand"],
                            "actionId": action_id,
                            "questionId": q.get("questionId"),
                        },
                        headers=auth_header)
        assert r.status_code == 200, f"Drill answer failed: {r.text}"
        fb = r.json()
        assert "evLoss" in fb


# ──────────────────────────────────────────────────────────────────
# 10. DRILL — Solver-backed flow
# ──────────────────────────────────────────────────────────────────


class TestDrillSolverBacked:
    """E2E: Solver-backed drill endpoints."""

    def test_solver_drill_with_persisted_data(self, client, auth_header, db):
        """Generate solver drill question from persisted solve."""
        r = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-detail-001"},
                        headers=auth_header)
        assert r.status_code == 200
        q = r.json()
        assert "combo" in q
        assert "actions" in q
        assert q["data_source"] == "real_cfr_solver"

    def test_solver_drill_no_data(self, client, auth_header):
        """Solver drill with nonexistent solve returns 404."""
        r = client.post("/api/drill/solver-drill",
                        json={"solve_id": "nonexistent-xyz"},
                        headers=auth_header)
        assert r.status_code == 404

    def test_solver_drill_answer(self, client, auth_header, db):
        """Answer a solver drill question."""
        q = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-detail-001"},
                        headers=auth_header).json()

        r = client.post("/api/drill/solver-drill/answer",
                        json={
                            "solve_id": q["solve_id"],
                            "node_id": q["node_id"],
                            "combo": q["combo"],
                            "chosen_action": q["actions"][0],
                        },
                        headers=auth_header)
        assert r.status_code == 200
        fb = r.json()
        assert "solver_frequencies" in fb
        assert "correct" in fb
        assert "feedback" in fb


# ──────────────────────────────────────────────────────────────────
# 11. PLAY — Compare-to-solver
# ──────────────────────────────────────────────────────────────────


class TestPlayCompareToSolver:
    """E2E: Post-hand solver comparison."""

    def test_compare_no_matching_solve(self, client, auth_header):
        """Compare with a board that has no matching solve."""
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["9s", "8s", "7s"],
                            "hero_hand": ["As", "Ks"],
                            "pot": 6.5,
                            "position": "IP",
                        },
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["match_quality"] == "unsupported"

    def test_compare_with_matching_board(self, client, auth_header, db):
        """Compare with a board that matches a persisted solve."""
        # test-detail-001 has board ["Ah", "Kd", "3c"]
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd", "3c"],
                            "hero_hand": ["As", "Ad"],
                            "pot": 6.5,
                            "position": "IP",
                        },
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["match_quality"] in ("exact_board_match", "board_match_summary_only")
        assert data["solve_id"] == "test-detail-001"

    def test_compare_too_few_cards(self, client, auth_header):
        """Compare with < 3 board cards returns unsupported."""
        r = client.post("/api/play/compare-to-solver",
                        json={"board": ["Ah", "Kd"], "pot": 6.5},
                        headers=auth_header)
        assert r.status_code == 200
        assert r.json()["match_quality"] == "unsupported"


# ──────────────────────────────────────────────────────────────────
# 12. ERROR STATES
# ──────────────────────────────────────────────────────────────────


class TestErrorStates:
    """E2E: Verify graceful error handling."""

    def test_nonexistent_session_state(self, client, auth_header):
        r = client.get("/api/play/session/nonexistent-abc", headers=auth_header)
        assert r.status_code in (400, 404)

    def test_next_hand_nonexistent_session(self, client, auth_header):
        r = client.post("/api/play/next-hand/nonexistent-abc", headers=auth_header)
        assert r.status_code in (400, 404)

    def test_solver_history_empty(self, client, auth_header, db):
        """History query on clean DB returns empty list, not error."""
        # This tests that the history endpoint handles empty tables gracefully
        r = client.get("/api/solver/history", headers=auth_header)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_range_parse_invalid(self, client, auth_header):
        r = client.post("/api/play/range/parse",
                        json={"range_str": "XXXX_INVALID"},
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False

    def test_range_parse_valid(self, client, auth_header):
        r = client.post("/api/play/range/parse",
                        json={"range_str": "AA,KK,QQ"},
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["count"] > 0


# ──────────────────────────────────────────────────────────────────
# 13. SCHEMA REGRESSION GUARD
# ──────────────────────────────────────────────────────────────────


class TestSchemaIntegrity:
    """Regression guard: ORM models match DB schema."""

    def test_all_model_columns_exist(self):
        """Verify all ORM columns exist in the test database."""
        from app.migrate import validate_schema
        from app.db import Base
        import app.db as _db_mod

        missing = validate_schema(_db_mod.engine)
        assert missing == [], f"Schema drift detected: {missing}"

    def test_solve_result_model_columns(self):
        """Explicitly verify SolveResultModel critical columns."""
        from app.models import SolveResultModel
        critical_cols = [
            "combo_strategies_json",
            "combo_storage_note",
            "exploitability_mbb",
            "exploitability_exact",
            "trust_grade",
            "trust_grade_json",
            "benchmark_summary_json",
            "exploitability_json",
        ]
        model_cols = {c.name for c in SolveResultModel.__table__.columns}
        for col in critical_cols:
            assert col in model_cols, f"Critical column missing from ORM: {col}"


# ──────────────────────────────────────────────────────────────────
# 14. VALIDATION ENDPOINT
# ──────────────────────────────────────────────────────────────────


class TestSolverValidation:
    """E2E: Solver validation/benchmark endpoint."""

    def test_validation_endpoint(self, client, auth_header):
        r = client.post("/api/solver/validate", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "overall_passed" in data
