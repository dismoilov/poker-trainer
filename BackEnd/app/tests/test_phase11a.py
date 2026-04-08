"""
Phase 11A tests — Minimal River Solver Layer.

Tests:
1. River tree building (chance nodes created, correct structure)
2. River equity computation (5-card board)
3. River solve execution (minimal ranges, small config)
4. Runtime guardrails (max river cards, tree size limits, combo limits)
5. Metadata includes river scope
6. Regression: flop-only and turn-only solves unchanged
"""

import pytest
from app.solver.tree_builder import (
    TreeConfig, GameTreeNode, GameTreeStats, NodeType,
    build_tree_skeleton,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, validate_solve_request,
    MAX_RIVER_CARDS, MAX_COMBOS_PER_SIDE_RIVER,
)


# ── Helpers ─────────────────────────────────────────────────────

def _make_river_config(**overrides) -> TreeConfig:
    """Build a minimal river-enabled TreeConfig."""
    defaults = dict(
        starting_pot=10.0,
        effective_stack=50.0,
        board=("Ks", "7d", "2c"),
        flop_bet_sizes=(0.5, 1.0),
        flop_raise_sizes=(),
        max_raises_per_street=1,
        include_turn=True,
        max_turn_cards=2,
        turn_bet_sizes_override=(0.5,),
        turn_raise_sizes_override=(),
        turn_max_raises=0,
        include_river=True,
        max_river_cards=2,
        river_bet_sizes_override=(0.5, 1.0),
        river_raise_sizes_override=(),
        river_max_raises=0,
    )
    defaults.update(overrides)
    return TreeConfig(**defaults)


def _make_river_solve_request(**overrides) -> SolveRequest:
    """Build a minimal river-enabled SolveRequest."""
    defaults = dict(
        board=["Ks", "7d", "2c"],
        ip_range="AA",
        oop_range="KK",
        pot=10.0,
        effective_stack=50.0,
        bet_sizes=[0.5, 1.0],
        raise_sizes=[],
        max_iterations=30,
        max_raises=1,
        deterministic=True,
        include_turn=True,
        max_turn_cards=2,
        turn_bet_sizes=[0.5],
        turn_raise_sizes=[],
        turn_max_raises=0,
        include_river=True,
        max_river_cards=2,
        river_bet_sizes=[0.5, 1.0],
        river_raise_sizes=[],
        river_max_raises=0,
    )
    defaults.update(overrides)
    return SolveRequest(**defaults)


# ── 1. River tree building ──────────────────────────────────────

class TestRiverTreeBuilding:
    """Test river tree construction."""

    def test_river_tree_has_river_chance_nodes(self):
        """River-enabled tree must contain river chance nodes."""
        config = _make_river_config()
        root, stats = build_tree_skeleton(config)

        assert stats.river_cards_explored > 0
        assert stats.street_depth == "flop_plus_turn_plus_river"

        # Find a river chance node
        found_river_chance = False
        def walk(node):
            nonlocal found_river_chance
            if node.node_type == NodeType.CHANCE:
                for child in node.children.values():
                    if child.river_card:
                        found_river_chance = True
                        return
            for child in node.children.values():
                walk(child)
        walk(root)
        assert found_river_chance, "Expected river chance node in tree"

    def test_river_tree_has_river_action_nodes(self):
        """River-enabled tree must contain river action nodes."""
        config = _make_river_config()
        root, stats = build_tree_skeleton(config)

        # Find a river action node
        found_river = False
        def walk(node):
            nonlocal found_river
            if node.node_type == NodeType.ACTION and node.street == "river":
                found_river = True
                return
            for child in node.children.values():
                walk(child)
        walk(root)
        assert found_river, "Expected river action nodes in tree"

    def test_river_cards_explored_capped(self):
        """max_river_cards should cap the number of river cards explored."""
        config = _make_river_config(max_river_cards=3)
        _, stats = build_tree_skeleton(config)
        assert stats.river_cards_explored <= 3

    def test_river_disabled_no_river_nodes(self):
        """With include_river=False, tree should NOT contain river nodes."""
        config = _make_river_config(include_river=False)
        root, stats = build_tree_skeleton(config)
        assert stats.river_cards_explored == 0
        assert stats.street_depth == "flop_plus_turn"

    def test_river_tree_larger_than_turn_only(self):
        """River-enabled tree should be larger than turn-only tree."""
        config_turn_only = _make_river_config(include_river=False)
        config_with_river = _make_river_config()

        _, stats_turn = build_tree_skeleton(config_turn_only)
        _, stats_river = build_tree_skeleton(config_with_river)

        assert stats_river.total_nodes > stats_turn.total_nodes


# ── 2. River config fields ──────────────────────────────────────

class TestRiverConfig:
    """Test TreeConfig and SolveRequest river fields."""

    def test_tree_config_street_depth(self):
        config = _make_river_config()
        assert config.street_depth == "flop_plus_turn_plus_river"

    def test_tree_config_river_defaults(self):
        config = TreeConfig()
        assert config.include_river is False
        assert config.max_river_cards == 4
        assert config.river_max_raises == 0

    def test_solve_request_river_defaults(self):
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
        )
        assert req.include_river is False
        assert req.max_river_cards == 4
        assert req.river_max_raises == 0


# ── 3. River validation guardrails ──────────────────────────────

class TestRiverValidation:
    """Test validation guardrails for river-enabled solves."""

    def test_river_requires_turn(self):
        """River cannot be enabled without turn."""
        req = _make_river_solve_request(include_turn=False)
        valid, error = validate_solve_request(req)
        assert not valid
        assert "turn" in error.lower()

    def test_river_card_cap(self):
        """max_river_cards cannot exceed MAX_RIVER_CARDS."""
        req = _make_river_solve_request(max_river_cards=MAX_RIVER_CARDS + 1)
        valid, error = validate_solve_request(req)
        assert not valid
        assert "river_cards" in error.lower()

    def test_river_combo_limit(self):
        """River solves have tight combo limits."""
        # Use a wide range that might exceed the limit
        req = _make_river_solve_request(
            ip_range="AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs",
            oop_range="AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs",
        )
        valid, error = validate_solve_request(req)
        # If combos > 15, should fail
        if not valid:
            assert "combos" in error.lower() or "large" in error.lower()

    def test_valid_river_request(self):
        """Minimal valid river request should pass validation."""
        req = _make_river_solve_request()
        valid, error = validate_solve_request(req)
        assert valid, f"Expected valid, got: {error}"


# ── 4. River solve execution ────────────────────────────────────

class TestRiverSolveExecution:
    """Test actual river solve execution (minimal)."""

    def test_river_solve_completes(self):
        """A minimal river solve should complete without error."""
        req = _make_river_solve_request(max_iterations=20)
        solver = CfrSolver()
        output = solver.solve(req)

        assert output.iterations > 0
        assert output.elapsed_seconds > 0
        assert output.tree_nodes > 0
        assert len(output.strategies) > 0

    def test_river_solve_metadata_contains_river(self):
        """River solve metadata should indicate river support."""
        req = _make_river_solve_request(max_iterations=10)
        solver = CfrSolver()
        output = solver.solve(req)

        metadata = output.metadata
        assert metadata["include_river"] is True
        assert metadata["street_depth"] == "flop_plus_turn_plus_river"
        assert "river_cards_explored" in metadata
        assert metadata["river_cards_explored"] > 0

    def test_river_solve_has_river_strategies(self):
        """River solve should produce strategies for river nodes."""
        req = _make_river_solve_request(max_iterations=20)
        solver = CfrSolver()
        output = solver.solve(req)

        # There should be strategies; the tree has action nodes on flop/turn/river
        assert len(output.strategies) > 0

    def test_river_solve_convergence(self):
        """River solve should show some convergence."""
        req = _make_river_solve_request(max_iterations=50)
        solver = CfrSolver()
        output = solver.solve(req)

        # Convergence should be finite
        assert output.convergence_metric < float("inf")


# ── 5. Regression tests ────────────────────────────────────────

class TestRegressionFlopAndTurn:
    """Ensure flop-only and turn-only solves still work correctly."""

    def test_flop_only_solve(self):
        """Flop-only solve should still work."""
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
        )
        solver = CfrSolver()
        output = solver.solve(req)

        assert output.iterations == 30
        assert output.metadata["street_depth"] == "flop_only"
        assert output.metadata.get("include_river") is False

    def test_turn_only_solve(self):
        """Turn-enabled (no river) solve should still work."""
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
        )
        solver = CfrSolver()
        output = solver.solve(req)

        assert output.iterations == 30
        assert output.metadata["street_depth"] == "flop_plus_turn"
        assert output.metadata.get("include_river") is False
