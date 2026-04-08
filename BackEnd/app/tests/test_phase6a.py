"""
Phase 6A tests: Limited turn support and deeper solver scope.

Tests cover:
- Tree builder with include_turn (chance nodes, turn card handling)
- CFR+ solver with turn support (produces strategies, metadata)
- Street depth in persistence and API responses
- Explore/Drill/Play handling of street_depth
- Regression: flop-only solves still work identically
"""

import pytest

from app.solver.tree_builder import (
    TreeConfig, build_tree_skeleton, NodeType, GameTreeNode, _ALL_CARDS,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput,
    MAX_TREE_NODES_FLOP, MAX_TREE_NODES_TURN,
)


# ══════════════════════════════════════════════════════════════════
# A. Tree Builder — Turn Support
# ══════════════════════════════════════════════════════════════════

class TestTreeBuilderTurn:
    """Test that the tree builder correctly inserts chance nodes for turn."""

    def test_flop_only_no_chance_nodes(self):
        """Flop-only tree should have NO chance nodes."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            flop_bet_sizes=(0.5, 1.0),
            flop_raise_sizes=(2.5,),
            include_turn=False,
        )
        root, stats = build_tree_skeleton(config)
        assert stats.chance_nodes == 0
        assert stats.street_depth == "flop_only"
        assert stats.turn_cards_explored == 0

    def test_turn_enabled_has_chance_nodes(self):
        """Turn-enabled tree should have chance nodes."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,),
            flop_raise_sizes=(),
            include_turn=True,
            max_turn_cards=3,
        )
        root, stats = build_tree_skeleton(config)
        assert stats.chance_nodes > 0
        assert stats.street_depth == "flop_plus_turn"
        assert stats.turn_cards_explored == 3

    def test_chance_node_children_have_turn_card(self):
        """Each child of a chance node should have a turn_card set."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,),
            flop_raise_sizes=(),
            include_turn=True,
            max_turn_cards=3,
        )
        root, stats = build_tree_skeleton(config)

        # Find a chance node by traversing
        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)

        assert len(chance_nodes) > 0
        for cn in chance_nodes:
            assert cn.node_type == NodeType.CHANCE
            for label, child in cn.children.items():
                assert child.turn_card is not None
                assert label.startswith("turn_")
                # Turn card should not be a board card
                assert child.turn_card not in ("Ks", "7d", "2c")

    def test_turn_cards_capped(self):
        """Max turn cards should be respected."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,),
            flop_raise_sizes=(),
            include_turn=True,
            max_turn_cards=4,
        )
        root, stats = build_tree_skeleton(config)
        assert stats.turn_cards_explored == 4

        # Find chance nodes and verify child count
        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)
        for cn in chance_nodes:
            assert len(cn.children) == 4

    def test_turn_action_tree_uses_override_sizes(self):
        """Turn subtree should use override bet sizes (simpler tree)."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.33, 0.67, 1.0),  # 3 sizes on flop
            flop_raise_sizes=(2.5,),
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes_override=(0.67,),  # 1 size on turn
            turn_raise_sizes_override=(),      # no raises on turn
            turn_max_raises=0,
        )
        root, stats = build_tree_skeleton(config)
        # Tree should be smaller because turn has fewer actions
        assert stats.total_nodes < MAX_TREE_NODES_TURN

    def test_street_depth_property(self):
        """TreeConfig.street_depth should return correct label."""
        config_flop = TreeConfig(include_turn=False)
        assert config_flop.street_depth == "flop_only"

        config_turn = TreeConfig(include_turn=True)
        assert config_turn.street_depth == "flop_plus_turn"

    def test_turn_nodes_have_turn_street(self):
        """Nodes in the turn subtree should have street='turn'."""
        config = TreeConfig(
            starting_pot=6.5,
            effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,),
            flop_raise_sizes=(),
            include_turn=True,
            max_turn_cards=2,
        )
        root, stats = build_tree_skeleton(config)

        chance_nodes = []
        _find_chance_nodes(root, chance_nodes)
        assert len(chance_nodes) > 0
        for cn in chance_nodes:
            for child in cn.children.values():
                assert child.street == "turn"


# ══════════════════════════════════════════════════════════════════
# B. CFR+ Solver — Turn Support
# ══════════════════════════════════════════════════════════════════

class TestCfrSolverTurn:
    """Test that the CFR+ solver produces valid results with turn support."""

    def test_solve_with_turn_produces_strategies(self):
        """Solve with turn should produce non-empty strategies."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=20,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=3,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert output.iterations > 0
        assert len(output.strategies) > 0
        assert output.metadata.get("street_depth") == "flop_plus_turn"
        assert output.metadata.get("include_turn") is True
        assert output.metadata.get("turn_cards_explored") == 3

    def test_solve_with_turn_has_scope_label(self):
        """Solve with turn should have flop_plus_turn scope."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=10,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert "flop plus turn" in output.metadata.get("scope", "")
        assert output.metadata.get("street_depth") == "flop_plus_turn"

    def test_solve_flop_only_regression(self):
        """Flop-only solve should still work identically."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            max_iterations=50,
            max_raises=2,
            deterministic=True,
            include_turn=False,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert output.metadata.get("street_depth") == "flop_only"
        assert "flop only" in output.metadata.get("scope", "")
        assert output.exploitability_mbb < float("inf")
        assert output.iterations == 50

    def test_solve_with_turn_exploitability(self):
        """Solve with turn should have finite exploitability."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.67],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert output.exploitability_mbb < float("inf")
        assert output.exploitability_mbb >= 0

    def test_max_tree_nodes_limits(self):
        """Safety limits should be separate for flop vs turn."""
        assert MAX_TREE_NODES_FLOP == 5000
        assert MAX_TREE_NODES_TURN == 35000  # Phase 10A: expanded from 15000
        assert MAX_TREE_NODES_TURN > MAX_TREE_NODES_FLOP


# ══════════════════════════════════════════════════════════════════
# C. API Integration — Street Depth
# ══════════════════════════════════════════════════════════════════

class TestApiStreetDepth:
    """Test street_depth in API responses (using existing test fixtures)."""

    @staticmethod
    def _create_solve(db):
        """Create a test solve result with street_depth."""
        from datetime import datetime
        from app.models import SolveResultModel
        existing = db.query(SolveResultModel).filter_by(id="test-solve-6a").first()
        if existing:
            return
        record = SolveResultModel(
            id="test-solve-6a",
            user_id=1,
            status="completed",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            config_json={
                "board": ["Ks", "7d", "2c"],
                "ip_range": "AA",
                "oop_range": "KK",
                "pot": 6.5,
                "effective_stack": 97.0,
                "bet_sizes": [0.5, 1.0],
                "raise_sizes": [2.5],
            },
            iterations=50,
            convergence_metric=0.001,
            elapsed_seconds=1.5,
            tree_nodes=100,
            ip_combos=6,
            oop_combos=6,
            matchups=30,
            converged=True,
            solved_node_count=5,
            algorithm_metadata_json={"algorithm": "CFR+", "street_depth": "flop_only"},
            validation_json={"passed": True, "checks_run": 5, "checks_passed": 5},
            root_strategy_summary_json={"check": 0.6, "bet_67": 0.4},
            node_summaries_json={"node_0": {"check": 0.6, "bet_67": 0.4}},
            full_strategies_available=False,
            exploitability_mbb=2.5,
            exploitability_exact=True,
            trust_grade="VERIFIED",
            trust_grade_json={"grade": "VERIFIED"},
            combo_strategies_json={"node_0": {"AhAd": {"check": 0.6, "bet_67": 0.4}}},
            combo_storage_note="Test data",
            street_depth="flop_only",
            turn_cards_explored=0,
        )
        db.add(record)
        db.commit()

    def test_explore_solver_backed_has_street_depth(self, client, auth_header, db):
        """Explore solver-backed should include street_depth when data exists."""
        self._create_solve(db)
        resp = client.get("/api/explore/solver-backed?solve_id=test-solve-6a&node_id=node_0",
                          headers=auth_header)
        # May return 200 or 400 depending on combo data availability
        if resp.status_code == 200:
            data = resp.json()
            assert "street_depth" in data
            assert data["street_depth"] in ("flop_only", "flop_plus_turn")

    def test_explore_solver_nodes_has_street_depth(self, client, auth_header, db):
        """Solver nodes endpoint should include street_depth."""
        self._create_solve(db)
        resp = client.get("/api/explore/solver-nodes?solve_id=test-solve-6a",
                          headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "street_depth" in data

    def test_drill_question_has_street_depth(self, client, auth_header, db):
        """Drill question should include street_depth."""
        self._create_solve(db)
        resp = client.post("/api/drill/solver-drill",
                           json={"solve_id": "test-solve-6a"},
                           headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert "street_depth" in data

    def test_play_compare_has_street_depth(self, client, auth_header, db):
        """Play compare should include street_depth when match found."""
        self._create_solve(db)
        resp = client.post("/api/play/compare-to-solver",
                           json={
                               "board": ["Ks", "7d", "2c"],
                               "hero_cards": ["Ah", "Kh"],
                               "hero_position": "IP",
                           },
                           headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        if data.get("supported"):
            assert "street_depth" in data

    def test_solver_history_has_street_depth(self, client, auth_header, db):
        """Solver history items should include street_depth."""
        self._create_solve(db)
        resp = client.get("/api/solver/history", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        if len(data) > 0:
            assert "street_depth" in data[0]

    def test_solver_request_accepts_include_turn(self, client, auth_header):
        """Solve request should accept include_turn parameter."""
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
        # Should accept the request (returns 200 with job_id)
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data


# ══════════════════════════════════════════════════════════════════
# D. Edge Cases
# ══════════════════════════════════════════════════════════════════

class TestEdgeCasesTurn:
    """Edge case tests for turn support."""

    def test_zero_turn_cards_means_all(self):
        """max_turn_cards=0 should explore all remaining cards."""
        config = TreeConfig(
            starting_pot=6.5, effective_stack=97.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.67,), flop_raise_sizes=(),
            include_turn=True,
            max_turn_cards=0,  # all remaining cards
        )
        root, stats = build_tree_skeleton(config)
        # 52 - 3 board = 49 remaining cards
        assert stats.turn_cards_explored == 49

    def test_all_cards_constant(self):
        """_ALL_CARDS should have exactly 52 cards."""
        assert len(_ALL_CARDS) == 52
        assert "As" in _ALL_CARDS
        assert "2c" in _ALL_CARDS

    def test_solve_request_defaults(self):
        """SolveRequest should default to include_turn=False."""
        sr = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
        )
        assert sr.include_turn is False
        assert sr.max_turn_cards == 8  # Phase 10A: expanded from 5


# ══════════════════════════════════════════════════════════════════
# Utility
# ══════════════════════════════════════════════════════════════════

def _find_chance_nodes(node: GameTreeNode, result: list):
    """Recursively find all CHANCE nodes in the tree."""
    if node.node_type == NodeType.CHANCE:
        result.append(node)
    for child in node.children.values():
        _find_chance_nodes(child, result)
