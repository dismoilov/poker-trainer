"""
Phase 4B tests: solver productization, deeper persistence, and real integration.
"""
import json
import pytest
from datetime import datetime
from app.models import SolveResultModel


@pytest.fixture
def persisted_solve(db, auth_header):
    """Create a persisted solve with combo data for testing."""
    combo_data = {
        "node_0": {
            "AhAs": {"check": 0.3, "bet_half": 0.7},
            "KhKs": {"check": 0.5, "bet_half": 0.5},
            "QhQs": {"check": 0.8, "bet_half": 0.2},
        },
        "node_1": {
            "AhAs": {"fold": 0.0, "call": 1.0},
            "KhKs": {"fold": 0.3, "call": 0.7},
        },
    }
    record = SolveResultModel(
        id="test-solve-4b",
        user_id=1,
        status="done",
        completed_at=datetime.utcnow(),
        config_json={
            "board": ["Ks", "7d", "2c"],
            "ip_range": "AA,KK,QQ",
            "oop_range": "JJ,TT,99",
            "pot": 6.5,
            "effective_stack": 97.0,
        },
        iterations=100,
        convergence_metric=0.01,
        elapsed_seconds=5.0,
        tree_nodes=30,
        ip_combos=3,
        oop_combos=3,
        matchups=9,
        converged=True,
        solved_node_count=2,
        algorithm_metadata_json={"algorithm": "cfr_plus"},
        validation_json={"passed": True, "checks_run": 5, "checks_passed": 5, "warnings": []},
        root_strategy_summary_json={"check": 0.533, "bet_half": 0.467},
        node_summaries_json={
            "node_0": {"check": 0.533, "bet_half": 0.467},
            "node_1": {"fold": 0.15, "call": 0.85},
        },
        full_strategies_available=True,
        exploitability_mbb=25.0,
        exploitability_exact=True,
        trust_grade="INTERNAL_DEMO",
        trust_grade_json={"grade": "INTERNAL_DEMO", "explanation": "test"},
        exploitability_json={
            "exploitability_mbb_per_hand": 25.0,
            "quality_label": "ROUGH",
            "is_exact_within_abstraction": True,
        },
        combo_strategies_json=combo_data,
        combo_storage_note="Persisted 2/2 nodes (max 500 combos).",
    )
    db.merge(record)
    db.commit()
    yield record


# ── Persistence tests ──────────────────────────────────────────


class TestComboSubsetPersistence:
    def test_combo_data_persisted(self, persisted_solve, db):
        r = db.query(SolveResultModel).filter(SolveResultModel.id == "test-solve-4b").first()
        assert r is not None
        assert r.combo_strategies_json is not None
        assert "node_0" in r.combo_strategies_json
        assert "AhAs" in r.combo_strategies_json["node_0"]
        assert r.combo_storage_note is not None

    def test_combo_subset_has_node_structure(self, persisted_solve, db):
        r = db.query(SolveResultModel).filter(SolveResultModel.id == "test-solve-4b").first()
        data = r.combo_strategies_json
        assert len(data) == 2
        assert set(data.keys()) == {"node_0", "node_1"}


# ── Solver history detail tests ────────────────────────────────


class TestSolverHistoryDetail:
    def test_history_detail_returns_combo_nodes(self, client, auth_header, persisted_solve):
        r = client.get("/api/solver/history/test-solve-4b", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "combo_available_nodes" in data
        assert "node_0" in data["combo_available_nodes"]
        assert "combo_storage_note" in data
        assert data["exploitability"] is not None
        assert data["trust_grade"] is not None

    def test_history_node_detail_returns_combos(self, client, auth_header, persisted_solve):
        r = client.get("/api/solver/history/test-solve-4b/node/node_0", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["data_source"] == "persisted_combo_subset"
        assert data["combo_count"] == 3
        assert "AhAs" in data["combos"]
        assert data["trust_grade"] == "INTERNAL_DEMO"

    def test_history_node_detail_404_for_missing(self, client, auth_header, persisted_solve):
        r = client.get("/api/solver/history/test-solve-4b/node/nonexistent", headers=auth_header)
        assert r.status_code == 404


# ── Explore solver-backed tests ────────────────────────────────


class TestExploreSolverBacked:
    def test_solver_backed_returns_strategy(self, client, auth_header, persisted_solve):
        r = client.get(
            "/api/explore/solver-backed?solve_id=test-solve-4b&node_id=node_0",
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["data_source"] == "persisted_combo_subset"
        assert data["combo_count"] == 3
        assert data["trust_grade"] == "INTERNAL_DEMO"
        assert "scope" in data
        assert "honest_note" in data

    def test_solver_backed_not_found(self, client, auth_header, persisted_solve):
        r = client.get(
            "/api/explore/solver-backed?solve_id=nonexistent&node_id=node_0",
            headers=auth_header,
        )
        assert r.status_code == 404


# ── Drill solver-backed tests ──────────────────────────────────


class TestDrillSolverBacked:
    def test_solver_drill_question(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/drill/solver-drill",
            json={"solve_id": "test-solve-4b"},
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert "combo" in data
        assert "actions" in data
        assert data["data_source"] == "real_cfr_solver"
        assert data["trust_grade"] == "INTERNAL_DEMO"

    def test_solver_drill_answer(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/drill/solver-drill/answer",
            json={
                "solve_id": "test-solve-4b",
                "node_id": "node_0",
                "combo": "AhAs",
                "chosen_action": "bet_half",
            },
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["correct"] is True
        assert data["best_action"] == "bet_half"
        assert data["solver_frequencies"]["bet_half"] == 0.7

    def test_solver_drill_wrong_answer(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/drill/solver-drill/answer",
            json={
                "solve_id": "test-solve-4b",
                "node_id": "node_0",
                "combo": "AhAs",
                "chosen_action": "check",
            },
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["correct"] is False
        assert data["acceptable"] is True  # 30% >= 20% threshold


# ── Play post-hand compare tests ──────────────────────────────


class TestPlayCompareToSolver:
    def test_compare_matching_board(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/play/compare-to-solver",
            json={
                "board": ["Ks", "7d", "2c"],
                "hero_hand": ["AhAs"],
                "pot": 6.5,
                "position": "IP",
            },
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["match_quality"] in ("exact_board_match", "board_match_summary_only")
        assert data["trust_grade"] == "INTERNAL_DEMO"
        assert data["root_summary"]["check"] == 0.533

    def test_compare_unmatched_board(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/play/compare-to-solver",
            json={
                "board": ["Ah", "Kh", "Qh"],
                "hero_hand": [],
                "pot": 6.5,
                "position": "IP",
            },
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["match_quality"] == "unsupported"

    def test_compare_too_few_cards(self, client, auth_header):
        r = client.post(
            "/api/play/compare-to-solver",
            json={"board": ["Ks", "7d"], "hero_hand": [], "pot": 6.5, "position": "IP"},
            headers=auth_header,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["match_quality"] == "unsupported"


# ── Unsupported scenario handling ──────────────────────────────


class TestUnsupportedScenarios:
    def test_solver_backed_wrong_solve(self, client, auth_header):
        r = client.get(
            "/api/explore/solver-backed?solve_id=does-not-exist&node_id=node_0",
            headers=auth_header,
        )
        assert r.status_code == 404

    def test_solver_drill_no_solves(self, client, auth_header):
        r = client.post(
            "/api/drill/solver-drill",
            json={"solve_id": "does-not-exist"},
            headers=auth_header,
        )
        assert r.status_code == 404


# ── Trust/scope metadata propagation ──────────────────────────


class TestTrustMetadataPropagation:
    def test_history_has_trust_grade(self, client, auth_header, persisted_solve):
        r = client.get("/api/solver/history", headers=auth_header)
        assert r.status_code == 200
        items = r.json()
        found = [i for i in items if i["id"] == "test-solve-4b"]
        assert len(found) == 1
        assert found[0]["trust_grade"] == "INTERNAL_DEMO"
        assert found[0]["exploitability_mbb"] == 25.0

    def test_explore_solver_backed_has_scope(self, client, auth_header, persisted_solve):
        r = client.get(
            "/api/explore/solver-backed?solve_id=test-solve-4b&node_id=node_0",
            headers=auth_header,
        )
        data = r.json()
        assert "scope" in data
        assert "flop" in data["scope"].lower()

    def test_play_compare_has_scope(self, client, auth_header, persisted_solve):
        r = client.post(
            "/api/play/compare-to-solver",
            json={"board": ["Ks", "7d", "2c"], "hero_hand": [], "pot": 6.5, "position": "IP"},
            headers=auth_header,
        )
        data = r.json()
        assert "scope" in data
        assert "flop" in data["scope"].lower()
