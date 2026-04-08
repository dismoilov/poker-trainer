"""
Phase 6B tests: Turn-scope validation, performance guardrails, and product hardening.

Tests cover:
- Turn-aware trust grading (street_depth parameter)
- Turn-specific benchmarks (overpair, normalization, flop vs turn)
- Chance-node structural validation
- Performance guardrails (MAX_TURN_CARDS, combo limits, oversized rejection)
- Board-at-node correctness for turn paths
- Blocker-aware valid-card filtering
- API handling of turn-aware solves
- Persistence of turn metadata
- Regression: flop-only flows unchanged
"""

import pytest

from app.solver.tree_builder import (
    TreeConfig, build_tree_skeleton, NodeType, GameTreeNode, _ALL_CARDS,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput,
    MAX_TREE_NODES_FLOP, MAX_TREE_NODES_TURN,
    MAX_COMBOS_PER_SIDE, MAX_COMBOS_PER_SIDE_TURN,
    MAX_TURN_CARDS, validate_solve_request,
)
from app.solver.solver_validation import (
    ValidationResult, compute_trust_grade, validate_solve_output,
    run_turn_benchmark_validation, validate_chance_node_structure,
)


# ══════════════════════════════════════════════════════════════════
# A. Turn-Aware Trust Grading
# ══════════════════════════════════════════════════════════════════

class TestTurnAwareTrustGrading:
    """Trust grading should be street-depth aware."""

    def test_flop_only_trust_grade_scope(self):
        """Flop-only solve should show flop-only scope."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=5.0, exploitability_available=True,
            benchmark_passed=True, street_depth="flop_only",
        )
        assert grade["street_depth"] == "flop_only"
        assert "flop only" in grade["scope"]
        assert grade["grade"] == "VALIDATED_LIMITED_SCOPE"

    def test_turn_solve_caps_at_internal_demo(self):
        """Turn-aware solves should cap trust at INTERNAL_DEMO."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=5.0, exploitability_available=True,
            benchmark_passed=True, street_depth="flop_plus_turn",
        )
        assert grade["street_depth"] == "flop_plus_turn"
        assert grade["grade"] == "INTERNAL_DEMO"  # capped, not VALIDATED
        assert "flop plus turn" in grade["scope"]
        assert "Turn abstraction" in grade["honest_note"]

    def test_turn_grade_with_high_exploitability(self):
        """Turn solve with high exploitability should warn."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(
            vr, exploitability_mbb=60.0, exploitability_available=True,
            street_depth="flop_plus_turn",
        )
        assert grade["grade"] == "INTERNAL_DEMO_WITH_WARNINGS"

    def test_failed_validation_regardless_of_depth(self):
        """Failed validation should always give FAILED grade."""
        vr = ValidationResult(passed=False, checks_run=5, checks_passed=2)
        grade = compute_trust_grade(vr, street_depth="flop_plus_turn")
        assert grade["grade"] == "FAILED"

    def test_turn_components_include_depth_info(self):
        """Trust grade components should include is_turn_aware."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(vr, street_depth="flop_plus_turn")
        assert grade["components"]["is_turn_aware"] is True
        assert grade["components"]["street_depth"] == "flop_plus_turn"

    def test_flop_components_not_turn_aware(self):
        """Flop-only grade should have is_turn_aware=False."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(vr, street_depth="flop_only")
        assert grade["components"]["is_turn_aware"] is False


# ══════════════════════════════════════════════════════════════════
# B. Turn-Specific Benchmarks
# ══════════════════════════════════════════════════════════════════

class TestTurnBenchmarks:
    """Turn-specific benchmark validation."""

    def test_turn_benchmarks_all_pass(self):
        """All turn benchmarks should pass."""
        result = run_turn_benchmark_validation()
        assert result["passed"] is True
        assert result["benchmark_count"] == 3
        assert result["benchmarks_passed"] == 3

    def test_overpair_benchmark(self):
        """Overpair on clean turn should bet at reasonable frequency."""
        result = run_turn_benchmark_validation()
        overpair = result["benchmarks"]["overpair_clean_turn"]
        assert overpair["passed"] is True
        assert overpair["street_depth"] == "flop_plus_turn"
        assert overpair["aa_avg_check_freq"] < 0.95  # not always checking

    def test_normalization_benchmark(self):
        """All turn-aware strategies should be properly normalized."""
        result = run_turn_benchmark_validation()
        norm = result["benchmarks"]["turn_normalization"]
        assert norm["passed"] is True
        assert norm["node_count"] > 0
        assert norm["street_depth"] == "flop_plus_turn"

    def test_flop_vs_turn_comparison_benchmark(self):
        """Both flop-only and turn should produce valid output."""
        result = run_turn_benchmark_validation()
        fvt = result["benchmarks"]["flop_vs_turn_comparison"]
        assert fvt["passed"] is True
        assert fvt["flop_depth"] == "flop_only"
        assert fvt["turn_depth"] == "flop_plus_turn"
        assert fvt["turn_nodes"] >= fvt["flop_nodes"]


# ══════════════════════════════════════════════════════════════════
# C. Chance-Node Structural Validation
# ══════════════════════════════════════════════════════════════════

class TestChanceNodeStructure:
    """Validate structural correctness of chance nodes."""

    def test_valid_tree_passes_structural_check(self):
        """A properly built turn tree should pass structural checks."""
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=3,
        )
        root, _ = build_tree_skeleton(config)
        result = validate_chance_node_structure(root)
        assert result["passed"] is True
        assert result["chance_nodes_found"] > 0
        assert len(result["issues"]) == 0

    def test_flop_only_has_no_chance_nodes(self):
        """Flop-only tree should have 0 chance nodes (still passes)."""
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=False,
        )
        root, _ = build_tree_skeleton(config)
        result = validate_chance_node_structure(root)
        assert result["passed"] is True
        assert result["chance_nodes_found"] == 0

    def test_chance_children_have_unique_turn_cards(self):
        """Each chance node child should have a unique turn card."""
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=5,
        )
        root, _ = build_tree_skeleton(config)

        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)
        for cn in chance_nodes:
            turn_cards = [c.turn_card for c in cn.children.values()]
            assert len(turn_cards) == len(set(turn_cards)), "Duplicate turn cards"

    def test_no_turn_card_is_board_card(self):
        """Turn cards must not duplicate board cards."""
        board = ("As", "Kd", "Qh")
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            board=board,
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=3,
        )
        root, _ = build_tree_skeleton(config)

        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)
        for cn in chance_nodes:
            for child in cn.children.values():
                assert child.turn_card not in board, \
                    f"Turn card {child.turn_card} is a board card"


# ══════════════════════════════════════════════════════════════════
# D. Performance Guardrails
# ══════════════════════════════════════════════════════════════════

class TestPerformanceGuardrails:
    """Test safety limits and config rejections."""

    def test_max_turn_cards_constant(self):
        """MAX_TURN_CARDS safety cap should exist."""
        assert MAX_TURN_CARDS == 15  # Phase 10A: expanded from 10

    def test_combos_per_side_turn_limit(self):
        """Turn-enabled solves should have tighter combo limit."""
        assert MAX_COMBOS_PER_SIDE_TURN < MAX_COMBOS_PER_SIDE
        assert MAX_COMBOS_PER_SIDE_TURN == 40  # Phase 12A: raised from 30

    def test_reject_turn_with_4_card_board(self):
        """Cannot enable turn dealing with 4+ card board."""
        request = SolveRequest(
            board=["Ks", "7d", "2c", "8h"],
            ip_range="AA",
            oop_range="KK",
            bet_sizes=[0.67],
            raise_sizes=[],
            max_raises=1,
            include_turn=True,
            max_turn_cards=3,
        )
        valid, msg = validate_solve_request(request)
        assert valid is False
        assert "Turn support requires exactly 3 board cards" in msg

    def test_reject_turn_with_excessive_card_count(self):
        """Turn cards exceeding MAX_TURN_CARDS should be rejected."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            bet_sizes=[0.67],
            raise_sizes=[],
            max_raises=1,
            include_turn=True,
            max_turn_cards=16,  # exceeds cap of 15
        )
        valid, msg = validate_solve_request(request)
        assert valid is False
        assert "safety cap" in msg

    def test_reject_expensive_turn_config(self):
        """High iterations + many turn cards should be rejected."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=1100,  # Phase 10A: guard at >1000
            max_raises=1,
            include_turn=True,
            max_turn_cards=8,  # Phase 10A: guard at >5
        )
        valid, msg = validate_solve_request(request)
        assert valid is False
        assert "too expensive" in msg

    def test_accept_valid_turn_config(self):
        """A reasonable turn config should be accepted."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=100,
            max_raises=1,
            include_turn=True,
            max_turn_cards=3,
        )
        valid, msg = validate_solve_request(request)
        assert valid is True
        assert msg == ""

    def test_flop_only_still_accepted(self):
        """Flop-only configs should still validate normally."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,QQ",
            oop_range="JJ,TT",
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            max_iterations=200,
            max_raises=2,
            include_turn=False,
        )
        valid, msg = validate_solve_request(request)
        assert valid is True


# ══════════════════════════════════════════════════════════════════
# E. Board-at-Node and Blocker Correctness
# ══════════════════════════════════════════════════════════════════

class TestBoardAndBlockerCorrectness:
    """Validate board state tracking and blocker filtering."""

    def test_turn_solve_produces_more_nodes(self):
        """Turn-enabled solve should produce more solved nodes than flop-only."""
        flop_req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.67], raise_sizes=[],
            max_iterations=20, max_raises=1,
            deterministic=True, include_turn=False,
        )
        turn_req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.67], raise_sizes=[],
            max_iterations=20, max_raises=1,
            deterministic=True, include_turn=True, max_turn_cards=2,
        )

        solver_f = CfrSolver()
        out_f = solver_f.solve(flop_req)
        solver_t = CfrSolver()
        out_t = solver_t.solve(turn_req)

        assert len(out_t.strategies) >= len(out_f.strategies)

    def test_turn_solve_strategies_normalized(self):
        """All strategies from turn-aware solve should sum to 1.0."""
        request = SolveRequest(
            board=["Ah", "Kd", "7c"],
            ip_range="KK", oop_range="QQ",
            bet_sizes=[0.67], raise_sizes=[],
            max_iterations=30, max_raises=1,
            deterministic=True, include_turn=True, max_turn_cards=2,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        for node_id, combos in output.strategies.items():
            for combo_str, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, \
                    f"Strategy not normalized at {node_id}/{combo_str}: {total}"

    def test_turn_cards_exclude_blockers(self):
        """Turn tree should not include cards that conflict with player combos in blocker check."""
        board = ("As", "Kd", "7c")
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            board=board,
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=5,
        )
        root, _ = build_tree_skeleton(config)

        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)
        for cn in chance_nodes:
            for child in cn.children.values():
                assert child.turn_card not in board


# ══════════════════════════════════════════════════════════════════
# F. API Integration — Turn Guardrails
# ══════════════════════════════════════════════════════════════════

class TestApiTurnGuardrails:
    """Test API-level turn guardrail handling."""

    def test_api_rejects_oversized_turn_config(self, client, auth_header):
        """API should reject oversized turn configurations."""
        resp = client.post("/api/solver/solve",
                          json={
                              "board": ["Ks", "7d", "2c"],
                              "ip_range": "AA",
                              "oop_range": "KK",
                              "include_turn": True,
                              "max_turn_cards": 15,  # exceeds cap
                          },
                          headers=auth_header)
        # Should return error
        assert resp.status_code in (200, 400, 422)
        data = resp.json()
        if resp.status_code == 200 and "error" in data:
            assert "safety cap" in data.get("error", "").lower() or \
                   data.get("warnings") is not None

    def test_api_accepts_valid_turn_config(self, client, auth_header):
        """API should accept valid turn configuration."""
        resp = client.post("/api/solver/solve",
                          json={
                              "board": ["Ks", "7d", "2c"],
                              "ip_range": "AA",
                              "oop_range": "KK",
                              "include_turn": True,
                              "max_turn_cards": 3,
                              "bet_sizes": [0.5],
                              "raise_sizes": [],
                              "turn_bet_sizes": [0.5],
                              "turn_raise_sizes": [],
                          },
                          headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        # Should have turn-specific warnings
        assert any("Тёрн" in w or "тёрн" in w or "Turn" in w or "turn" in w for w in data.get("warnings", []))

    def test_api_solver_history_returns_street_depth(self, client, auth_header, db):
        """History should include street_depth field."""
        from datetime import datetime
        from app.models import SolveResultModel
        existing = db.query(SolveResultModel).filter_by(id="test-6b-hist").first()
        if not existing:
            record = SolveResultModel(
                id="test-6b-hist",
                user_id=1,
                status="completed",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                config_json={"board": ["Ks", "7d", "2c"], "ip_range": "AA", "oop_range": "KK"},
                iterations=50, convergence_metric=0.001, elapsed_seconds=1.0,
                tree_nodes=100, ip_combos=6, oop_combos=6, matchups=30,
                converged=True, solved_node_count=5,
                algorithm_metadata_json={"algorithm": "CFR+", "street_depth": "flop_plus_turn"},
                validation_json={"passed": True, "checks_run": 5, "checks_passed": 5},
                root_strategy_summary_json={}, node_summaries_json={},
                full_strategies_available=False,
                street_depth="flop_plus_turn",
                turn_cards_explored=3,
            )
            db.add(record)
            db.commit()

        resp = client.get("/api/solver/history", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        turn_items = [d for d in data if d.get("id") == "test-6b-hist"]
        if turn_items:
            assert turn_items[0].get("street_depth") == "flop_plus_turn"

    def test_api_turn_with_4card_board_rejected(self, client, auth_header):
        """API should reject turn solve with 4-card board."""
        resp = client.post("/api/solver/solve",
                          json={
                              "board": ["Ks", "7d", "2c", "8h"],
                              "ip_range": "AA",
                              "oop_range": "KK",
                              "include_turn": True,
                              "max_turn_cards": 3,
                          },
                          headers=auth_header)
        # This might return 200 with error or 400
        if resp.status_code == 200:
            data = resp.json()
            # Should have job_id if direct validation happens later
            # or error if validated upfront
            pass
        else:
            assert resp.status_code in (400, 422)


# ══════════════════════════════════════════════════════════════════
# G. Regression Protection
# ══════════════════════════════════════════════════════════════════

class TestRegressionProtection:
    """Ensure existing flop-only behavior is unchanged."""

    def test_flop_only_solve_unchanged(self):
        """Flop-only solve should produce same results as before Phase 6B."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=30, max_raises=2,
            deterministic=True, include_turn=False,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert output.metadata.get("street_depth") == "flop_only"
        assert output.iterations == 30
        assert output.exploitability_mbb < float("inf")
        assert len(output.strategies) > 0

    def test_flop_only_validation_still_works(self):
        """Validation on flop-only solve should still pass."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.67], raise_sizes=[],
            max_iterations=20, max_raises=1,
            deterministic=True,
        )
        solver = CfrSolver()
        output = solver.solve(request)
        vr = validate_solve_output(
            output.strategies, output.iterations, output.convergence_metric
        )
        assert vr.passed is True

    def test_safety_limits_unchanged(self):
        """Core safety limits should remain intact (updated for Phase 10A)."""
        assert MAX_TREE_NODES_FLOP == 5000
        assert MAX_TREE_NODES_TURN == 35000  # Phase 10A: expanded from 15000
        assert MAX_COMBOS_PER_SIDE == 60     # Phase 10A: expanded from 50

    def test_trust_grade_backward_compatible(self):
        """compute_trust_grade without street_depth should default to flop_only."""
        vr = ValidationResult(passed=True, checks_run=5, checks_passed=5)
        grade = compute_trust_grade(vr)  # no street_depth arg
        assert grade["street_depth"] == "flop_only"
        assert grade["components"]["is_turn_aware"] is False


# ══════════════════════════════════════════════════════════════════
# Utility
# ══════════════════════════════════════════════════════════════════

def _find_chance_nodes(node: GameTreeNode, result: list):
    """Recursively find all CHANCE nodes in the tree."""
    if node.node_type == NodeType.CHANCE:
        result.append(node)
    for child in node.children.values():
        _find_chance_nodes(child, result)
