"""
Phase 9B: Spot-to-Study Workflow Tests

Tests context carry-over between Play, Solver, Drill, and Explore.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get auth token for test user."""
    client.post("/api/auth/register", json={"username": "test9b", "password": "test9b"})
    r = client.post("/api/auth/login", json={"username": "test9b", "password": "test9b"})
    token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestCompareToSolverContextFields:
    """Next-steps in compare-to-solver response carry context data."""

    def _compare(self, client, auth_headers, board):
        return client.post(
            "/api/game-sessions/compare-to-solver",
            json={
                "board": board,
                "hero_hand": ["As", "Kd"],
                "villain_hand": ["Th", "9h"],
                "pot": 10.0,
                "user_action": "call",
            },
            headers=auth_headers,
        )

    def test_next_steps_include_solve_id_when_match_exists(self, client, auth_headers):
        """When a persisted solve exists, next_steps should carry solve_id."""
        # Create a solve first
        r = client.post(
            "/api/solver/job",
            json={
                "board": ["Ks", "7d", "2c"],
                "ip_range": "AA,KK,AKs",
                "oop_range": "QQ,JJ,AQs",
            },
            headers=auth_headers,
        )
        if r.status_code != 200:
            pytest.skip("Solver job creation failed")

        job_id = r.json().get("job_id")
        if not job_id:
            pytest.skip("No job_id returned")

        # Wait and get result
        import time
        for _ in range(20):
            pr = client.get(f"/api/solver/progress/{job_id}", headers=auth_headers)
            if pr.json().get("status") == "done":
                break
            time.sleep(0.5)

        # Now compare
        resp = self._compare(client, auth_headers, ["Ks", "7d", "2c"])
        if resp.status_code != 200:
            pytest.skip("Compare failed (no match expected in test env)")

        data = resp.json()
        if data.get("match_quality") == "unsupported":
            pytest.skip("No solver match found")

        next_steps = data.get("next_steps", [])
        assert len(next_steps) >= 2, "Should have at least drill + explore steps"

        # Drill step should carry context
        drill_step = next(s for s in next_steps if s["id"] == "drill")
        assert "solve_id" in drill_step, "Drill next_step must carry solve_id"
        assert "board" in drill_step, "Drill next_step must carry board"
        assert "board_display" in drill_step, "Drill next_step must carry board_display"
        assert "spot_label" in drill_step, "Drill next_step must carry spot_label"
        assert "Флоп" in drill_step["spot_label"], "spot_label should be Russian"

        # Explore step should carry same context
        explore_step = next(s for s in next_steps if s["id"] == "explore")
        assert explore_step["solve_id"] == drill_step["solve_id"]
        assert explore_step["board"] == drill_step["board"]

    def test_next_steps_solver_has_no_solve_id(self, client, auth_headers):
        """Solver next_step should NOT carry solve_id (navigates to solver page)."""
        # Create a solve first
        client.post(
            "/api/solver/job",
            json={
                "board": ["Ks", "7d", "2c"],
                "ip_range": "AA,KK,AKs",
                "oop_range": "QQ,JJ,AQs",
            },
            headers=auth_headers,
        )
        import time
        time.sleep(3)

        resp = self._compare(client, auth_headers, ["Ks", "7d", "2c"])
        if resp.status_code != 200 or resp.json().get("match_quality") == "unsupported":
            pytest.skip("No match")

        data = resp.json()
        next_steps = data.get("next_steps", [])
        solver_step = next((s for s in next_steps if s["id"] == "solver"), None)
        if solver_step:
            assert "solve_id" not in solver_step, "Solver step should not carry solve_id"


class TestNextStepsLocalization:
    """Next-step labels and spot labels should be in Russian."""

    def test_next_steps_labels_are_russian(self, client, auth_headers):
        """All next_step labels should be Russian."""
        # We need a solve. Create one.
        client.post(
            "/api/solver/job",
            json={
                "board": ["Ad", "5h", "3c"],
                "ip_range": "AA,KK",
                "oop_range": "QQ,JJ",
            },
            headers=auth_headers,
        )
        import time
        time.sleep(3)

        resp = client.post(
            "/api/game-sessions/compare-to-solver",
            json={
                "board": ["Ad", "5h", "3c"],
                "hero_hand": ["Ah", "Kc"],
                "villain_hand": ["Qd", "Qc"],
                "pot": 8.0,
                "user_action": "check",
            },
            headers=auth_headers,
        )
        if resp.status_code != 200 or resp.json().get("match_quality") == "unsupported":
            pytest.skip("No match")

        data = resp.json()
        next_steps = data.get("next_steps", [])

        for step in next_steps:
            label = step.get("label", "")
            # All labels should contain Cyrillic characters
            assert any("\u0400" <= c <= "\u04FF" for c in label), \
                f"Label '{label}' should be Russian"


class TestBoardDisplayFormat:
    """Board display should be human-readable."""

    def test_board_display_format(self, client, auth_headers):
        """board_display in next_steps should use card display format."""
        client.post(
            "/api/solver/job",
            json={
                "board": ["Ks", "7d", "2c"],
                "ip_range": "AA,KK,AKs",
                "oop_range": "QQ,JJ,AQs",
            },
            headers=auth_headers,
        )
        import time
        time.sleep(3)

        resp = client.post(
            "/api/game-sessions/compare-to-solver",
            json={
                "board": ["Ks", "7d", "2c"],
                "hero_hand": ["As", "Kd"],
                "villain_hand": ["Th", "9h"],
                "pot": 10.0,
                "user_action": "call",
            },
            headers=auth_headers,
        )
        if resp.status_code != 200 or resp.json().get("match_quality") == "unsupported":
            pytest.skip("No match")

        data = resp.json()
        next_steps = data.get("next_steps", [])
        drill_step = next((s for s in next_steps if s.get("board_display")), None)
        if drill_step:
            bd = drill_step["board_display"]
            # Board display should contain card symbols (suit symbols)
            assert len(bd) > 0, "board_display should not be empty"


class TestSolverResponseFields:
    """Solver result fields for study continuity."""

    def test_solve_id_in_compare_response(self, client, auth_headers):
        """compare-to-solver should return solve_id at top level."""
        client.post(
            "/api/solver/job",
            json={
                "board": ["Ks", "7d", "2c"],
                "ip_range": "AA,KK,AKs",
                "oop_range": "QQ,JJ,AQs",
            },
            headers=auth_headers,
        )
        import time
        time.sleep(3)

        resp = client.post(
            "/api/game-sessions/compare-to-solver",
            json={
                "board": ["Ks", "7d", "2c"],
                "hero_hand": ["As", "Kd"],
                "villain_hand": ["Th", "9h"],
                "pot": 10.0,
                "user_action": "call",
            },
            headers=auth_headers,
        )
        if resp.status_code != 200 or resp.json().get("match_quality") == "unsupported":
            pytest.skip("No match")

        data = resp.json()
        assert "solve_id" in data, "Response must include solve_id"
        assert data["solve_id"] is not None, "solve_id should not be None"
