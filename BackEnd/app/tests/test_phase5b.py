"""Phase 5B tests: Deep Solver-Backed Product Flows.

Tests enriched Explore (solver-nodes, solver-backed), Drill (question, answer),
and Play (compare-to-solver) solver-backed endpoints.

Uses shared conftest fixtures: client, auth_header, db.
"""

import pytest
from datetime import datetime
from app.models import SolveResultModel


# ── Helper: seed a test solve ────────────────────────────────────

def _seed_solve(db, solve_id="test-5b-solve"):
    """Insert a test solve into the DB if not present."""
    existing = db.query(SolveResultModel).filter(SolveResultModel.id == solve_id).first()
    if existing:
        return
    solve = SolveResultModel(
        id=solve_id,
        user_id=1,
        status="done",
        created_at=datetime.utcnow(),
        config_json={
            "board": ["Ah", "Kd", "7c"],
            "ip_range": "AA,KK,QQ",
            "oop_range": "AKs,AKo,QQ",
            "pot": 10,
            "effective_stack": 100,
        },
        root_strategy_summary_json={"check": 0.6, "bet_half": 0.4},
        node_summaries_json={
            "node_0": {"check": 0.6, "bet_half": 0.4},
            "node_1": {"call": 0.7, "fold": 0.3},
        },
        combo_strategies_json={
            "node_0": {
                "AhAs": {"check": 0.3, "bet_half": 0.7},
                "KdKs": {"check": 0.8, "bet_half": 0.2},
                "QhQs": {"check": 0.5, "bet_half": 0.5},
            }
        },
        trust_grade="INTERNAL_DEMO",
        exploitability_mbb=12.5,
        iterations=1000,
        converged=True,
        elapsed_seconds=2.5,
        tree_nodes=8,
        ip_combos=3,
        oop_combos=3,
        matchups=9,
        solved_node_count=2,
    )
    db.merge(solve)
    db.commit()


# ──────────────────────────────────────────────────────────────────
# 1. EXPLORE — solver-nodes endpoint
# ──────────────────────────────────────────────────────────────────

class TestExploreSolverNodes:
    """Tests for GET /api/explore/solver-nodes."""

    def test_solver_nodes_returns_tree(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-nodes?solve_id=test-5b-solve",
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert len(data["nodes"]) > 0
        assert "total_nodes" in data

    def test_solver_nodes_has_data_quality(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-nodes?solve_id=test-5b-solve",
                        headers=auth_header)
        data = r.json()
        for node in data["nodes"]:
            assert "data_quality" in node
            assert node["data_quality"] in ("per_combo", "summary_only", "unavailable")

    def test_solver_nodes_metadata(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-nodes?solve_id=test-5b-solve",
                        headers=auth_header)
        data = r.json()
        assert data["board"] == ["Ah", "Kd", "7c"]
        assert data["trust_grade"] == "INTERNAL_DEMO"
        assert data["exploitability_mbb"] is not None

    def test_solver_nodes_404_for_missing(self, client, auth_header):
        r = client.get("/api/explore/solver-nodes?solve_id=nonexistent-xyz-5b",
                        headers=auth_header)
        assert r.status_code == 404

    def test_solver_nodes_root_has_combo_data(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-nodes?solve_id=test-5b-solve",
                        headers=auth_header)
        data = r.json()
        root = next((n for n in data["nodes"] if n["node_id"] == "node_0"), None)
        assert root is not None
        assert root["data_quality"] == "per_combo"
        assert root["combo_count"] == 3


# ──────────────────────────────────────────────────────────────────
# 2. EXPLORE — enriched solver-backed endpoint
# ──────────────────────────────────────────────────────────────────

class TestExploreSolverBackedEnriched:
    """Tests enriched GET /api/explore/solver-backed."""

    def test_enriched_response_has_metadata(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-backed?solve_id=test-5b-solve&node_id=node_0",
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "board" in data
        assert "iterations" in data
        assert "converged" in data
        assert "data_depth" in data
        assert data["board"] == ["Ah", "Kd", "7c"]

    def test_enriched_has_ranges(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-backed?solve_id=test-5b-solve&node_id=node_0",
                        headers=auth_header)
        data = r.json()
        assert "ip_range" in data
        assert "oop_range" in data

    def test_data_depth_per_combo(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-backed?solve_id=test-5b-solve&node_id=node_0",
                        headers=auth_header)
        data = r.json()
        assert "per-combo" in data["data_depth"]


# ──────────────────────────────────────────────────────────────────
# 3. DRILL — enriched solver drill question + answer
# ──────────────────────────────────────────────────────────────────

class TestDrillSolverDrillEnriched:
    """Tests enriched solver drill endpoints."""

    def test_enriched_question_has_node_label(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-5b-solve"},
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "node_label" in data
        assert "data_depth" in data

    def test_enriched_question_has_effective_stack(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-5b-solve"},
                        headers=auth_header)
        data = r.json()
        assert "effective_stack" in data

    def test_enriched_answer_has_explanation(self, client, auth_header, db):
        _seed_solve(db)
        q = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-5b-solve"},
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
        data = r.json()
        assert "explanation" in data
        assert isinstance(data["explanation"], list)
        assert len(data["explanation"]) > 0
        assert "accuracy_pct" in data
        assert "data_depth_note" in data

    def test_enriched_answer_has_exploitability(self, client, auth_header, db):
        _seed_solve(db)
        q = client.post("/api/drill/solver-drill",
                        json={"solve_id": "test-5b-solve"},
                        headers=auth_header).json()

        r = client.post("/api/drill/solver-drill/answer",
                        json={
                            "solve_id": q["solve_id"],
                            "node_id": q["node_id"],
                            "combo": q["combo"],
                            "chosen_action": q["actions"][0],
                        },
                        headers=auth_header)
        data = r.json()
        assert "exploitability_mbb" in data

    def test_drill_question_no_solve(self, client, auth_header):
        r = client.post("/api/drill/solver-drill",
                        json={"solve_id": "nonexistent-xyz-5b"},
                        headers=auth_header)
        assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────
# 4. PLAY — enriched compare-to-solver
# ──────────────────────────────────────────────────────────────────

class TestPlayCompareEnriched:
    """Tests enriched POST /api/play/compare-to-solver."""

    def test_enriched_has_explanation(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd", "7c"],
                            "hero_hand": ["AhAs"],
                            "pot": 10,
                            "position": "IP",
                        },
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "explanation" in data
        assert data["explanation"] is not None

    def test_enriched_has_data_depth(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd", "7c"],
                            "hero_hand": ["AhAs"],
                            "pot": 10,
                        },
                        headers=auth_header)
        data = r.json()
        assert "data_depth" in data

    def test_enriched_has_iterations(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd", "7c"],
                            "pot": 10,
                        },
                        headers=auth_header)
        data = r.json()
        assert "iterations" in data
        assert "converged" in data

    def test_enriched_has_hero_combo_key(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd", "7c"],
                            "hero_hand": ["AhAs"],
                            "pot": 10,
                        },
                        headers=auth_header)
        data = r.json()
        assert "hero_combo_key" in data

    def test_unsupported_has_explanation(self, client, auth_header):
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["2h", "3d", "4c"],
                            "pot": 10,
                        },
                        headers=auth_header)
        data = r.json()
        assert data["match_quality"] == "unsupported"
        assert "explanation" in data

    def test_unsupported_too_few_cards(self, client, auth_header):
        r = client.post("/api/play/compare-to-solver",
                        json={
                            "board": ["Ah", "Kd"],
                            "pot": 10,
                        },
                        headers=auth_header)
        data = r.json()
        assert data["match_quality"] == "unsupported"


# ──────────────────────────────────────────────────────────────────
# 5. EDGE CASES
# ──────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases for enriched endpoints."""

    def test_solver_backed_summary_only_node(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-backed?solve_id=test-5b-solve&node_id=node_1",
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "aggregate" in data["data_depth"]

    def test_solver_backed_missing_node(self, client, auth_header, db):
        _seed_solve(db)
        r = client.get("/api/explore/solver-backed?solve_id=test-5b-solve&node_id=node_999",
                        headers=auth_header)
        assert r.status_code == 404

    def test_drill_answer_missing_combo(self, client, auth_header, db):
        _seed_solve(db)
        r = client.post("/api/drill/solver-drill/answer",
                        json={
                            "solve_id": "test-5b-solve",
                            "node_id": "node_0",
                            "combo": "XxYy",
                            "chosen_action": "check",
                        },
                        headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["correct"] is False
        assert data["solver_frequencies"] == {}
