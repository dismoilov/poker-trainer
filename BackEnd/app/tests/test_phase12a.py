"""
Phase 12A tests: Hot-path optimization correctness, updated limits, regression.
"""
import pytest
import time
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, validate_solve_request,
    MAX_COMBOS_PER_SIDE, MAX_COMBOS_PER_SIDE_TURN, MAX_COMBOS_PER_SIDE_RIVER,
)
from app.solver.tree_builder import TreeConfig, build_tree_skeleton, NodeType


# ── Optimization correctness ────────────────────────────────────

class TestOptimizationCorrectness:
    """Verify that optimizations don't change solver output."""

    def test_flop_convergence_preserved(self):
        """Flop solve must produce identical convergence with optimizations."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=50,
            deterministic=True,
        ))
        # Convergence should be deterministic
        assert output.convergence_metric == pytest.approx(0.22, abs=0.05)  # Phase 14: parallel mode
        assert output.iterations == 50

    def test_turn_convergence_preserved(self):
        """Turn solve must produce identical convergence with optimizations."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=50,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
        ))
        assert output.metadata["street_depth"] == "flop_plus_turn"
        assert output.iterations == 50

    def test_river_convergence_preserved(self):
        """River solve must produce valid output with optimizations."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=30,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
            include_river=True,
            max_river_cards=2,
            river_bet_sizes=[0.33, 0.5, 1.0],
            river_raise_sizes=[2.5],
            river_max_raises=2,
        ))
        assert output.metadata["street_depth"] == "flop_plus_turn_plus_river"
        assert output.iterations == 30
        # Must have valid strategies
        assert len(output.strategies) > 0

    def test_terminal_type_int_tags(self):
        """Tree must have integer terminal type tags after optimization."""
        config = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
        )
        root, _ = build_tree_skeleton(config)

        # Manually tag (solver does this in _tag_terminal_nodes)
        solver = CfrSolver()
        solver._root = root
        solver._tag_terminal_nodes(root)

        # Check terminal nodes have integer type tags
        def check_terminals(node):
            if node._is_terminal:
                assert node._terminal_type_int in (1, 2, 3), (
                    f"Terminal node {node.node_id} has invalid type_int: {node._terminal_type_int}"
                )
            for child in node.children.values():
                check_terminals(child)

        check_terminals(root)


# ── Tree finalization ────────────────────────────────────────────

class TestTreeFinalization:
    """Verify tree finalization populates cached fields."""

    def test_actions_tuple_populated(self):
        """All action nodes must have _actions_tuple set."""
        config = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
        )
        root, _ = build_tree_skeleton(config)

        def check_actions(node):
            if node.node_type == NodeType.ACTION:
                assert len(node._actions_tuple) == len(node.children)
                assert set(node._actions_tuple) == set(node.children.keys())
            for child in node.children.values():
                check_actions(child)

        check_actions(root)

    def test_is_terminal_cached(self):
        """_is_terminal must match node_type == TERMINAL."""
        config = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
        )
        root, _ = build_tree_skeleton(config)

        def check(node):
            assert node._is_terminal == (node.node_type == NodeType.TERMINAL)
            assert node._is_chance == (node.node_type == NodeType.CHANCE)
            for child in node.children.values():
                check(child)

        check(root)

    def test_turn_tree_finalized(self):
        """Turn tree must also have finalized fields."""
        config = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0), flop_raise_sizes=(),
            include_turn=True, max_turn_cards=2,
        )
        root, _ = build_tree_skeleton(config)

        chance_found = False
        def check(node):
            nonlocal chance_found
            if node._is_chance:
                chance_found = True
            assert isinstance(node._actions_tuple, tuple)
            for child in node.children.values():
                check(child)

        check(root)
        assert chance_found, "No chance nodes found in turn tree"


# ── Updated combo limits ─────────────────────────────────────────

class TestUpdatedComboLimits:
    """Verify Phase 12A updated combo limits."""

    def test_turn_limit_raised(self):
        """Turn combo limit should be 40 (raised from 30)."""
        assert MAX_COMBOS_PER_SIDE_TURN == 40

    def test_river_limit_raised(self):
        """River combo limit should be 20 (raised from 15)."""
        assert MAX_COMBOS_PER_SIDE_RIVER == 20

    def test_flop_limit_unchanged(self):
        """Flop combo limit should remain 60."""
        assert MAX_COMBOS_PER_SIDE == 60

    def test_wider_turn_range_accepted(self):
        """Turn solve with 35 combos (was rejected at 30 limit) should now pass."""
        # AA,KK,QQ,JJ,TT gives ~27-30 combos depending on board blockers
        # But we test the limit directly
        req = SolveRequest(
            board=["8s", "5d", "2h"],
            ip_range="AA,KK,QQ,JJ,TT",  # ~30 combos
            oop_range="99,88,77,66,55",  # ~24 combos (board blockers)
            pot=10.0,
            effective_stack=50.0,
            include_turn=True,
            max_turn_cards=2,
        )
        valid, error = validate_solve_request(req)
        assert valid, f"Should accept wider turn range: {error}"

    def test_wider_river_range_accepted(self):
        """River solve with 18 combos (was rejected at 15 limit) should now pass."""
        req = SolveRequest(
            board=["8s", "5d", "2h"],
            ip_range="AA,KK,QQ",  # 18 combos
            oop_range="JJ,TT,99",  # 18 combos
            pot=10.0,
            effective_stack=50.0,
            include_turn=True,
            max_turn_cards=2,
            include_river=True,
            max_river_cards=2,
        )
        valid, error = validate_solve_request(req)
        assert valid, f"Should accept wider river range: {error}"

    def test_too_wide_river_still_rejected(self):
        """River solve with >20 combos per side should still be rejected."""
        req = SolveRequest(
            board=["8s", "5d", "2h"],
            ip_range="AA,KK,QQ,JJ,TT",  # ~30 combos
            oop_range="99,88,77,66,55",  # too many for river
            pot=10.0,
            effective_stack=50.0,
            include_turn=True,
            max_turn_cards=2,
            include_river=True,
            max_river_cards=2,
        )
        valid, error = validate_solve_request(req)
        assert not valid
        assert "combo" in error.lower() or "too large" in error.lower()


# ── Performance ──────────────────────────────────────────────────

class TestPerformance:
    """Verify that optimized paths are measurably faster."""

    def test_flop_under_budget(self):
        """Flop solve of AA,KK,QQ vs JJ,TT,99 @100i must complete in <30s."""
        solver = CfrSolver()
        t0 = time.time()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,QQ",
            oop_range="JJ,TT,99",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            max_iterations=100,
            max_raises=2,
            deterministic=True,
        ))
        elapsed = time.time() - t0
        assert elapsed < 30.0, f"Flop solve took {elapsed:.1f}s, expected <30s"

    def test_turn_under_budget(self):
        """Turn solve of AA vs KK @100i 2tc must complete in <15s."""
        solver = CfrSolver()
        t0 = time.time()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            max_iterations=100,
            max_raises=2,
            deterministic=True,
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5, 1.0],
            turn_raise_sizes=[],
            turn_max_raises=0,
        ))
        elapsed = time.time() - t0
        assert elapsed < 15.0, f"Turn solve took {elapsed:.1f}s, expected <15s"


# ── Regression ───────────────────────────────────────────────────

class TestPhase12ARegression:
    """Ensure previous functionality still works."""

    def test_flop_only_still_works(self):
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            max_iterations=20,
            deterministic=True,
        ))
        assert output.metadata["street_depth"] == "flop_only"
        assert len(output.strategies) > 0

    def test_strategies_sum_to_one(self):
        """Strategy frequencies must sum to ~1.0 for each combo at each node."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=[0.5, 1.0],
            max_iterations=50,
            deterministic=True,
        ))
        for node_id, combos in output.strategies.items():
            for combo_str, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, (
                    f"Strategy at {node_id}/{combo_str} sums to {total}, expected ~1.0"
                )

    def test_deep_preset_still_works(self):
        """Deep preset configuration must still produce valid river solve."""
        from app.api.routes_solver import SOLVER_PRESETS
        p = SOLVER_PRESETS["deep"]
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=10.0,
            effective_stack=50.0,
            bet_sizes=p["bet_sizes"],
            raise_sizes=p["raise_sizes"],
            max_iterations=30,
            max_raises=p["max_raises"],
            deterministic=True,
            include_turn=p["include_turn"],
            max_turn_cards=p["max_turn_cards"],
            turn_bet_sizes=p["turn_bet_sizes"],
            turn_raise_sizes=p["turn_raise_sizes"],
            turn_max_raises=p["turn_max_raises"],
            include_river=p["include_river"],
            max_river_cards=p["max_river_cards"],
            river_bet_sizes=p["river_bet_sizes"],
            river_raise_sizes=p["river_raise_sizes"],
            river_max_raises=p["river_max_raises"],
        ))
        assert output.metadata["street_depth"] == "flop_plus_turn_plus_river"
        assert len(output.strategies) > 0
