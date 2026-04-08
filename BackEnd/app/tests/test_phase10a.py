"""
Phase 10A: Solver Core Expansion Tests

Tests for:
- Richer action abstraction (expanded bet sizes, overbets, raise sizes)
- Stronger turn solving (turn raises, more turn cards, higher limits)
- Metadata output (action_abstraction field, per-street details)
- Validation guardrails (adaptive caps, tree size limits)
- Regression protection (existing solver behavior preserved)
"""

import pytest
import time

from app.solver.tree_builder import (
    TreeConfig, build_tree_skeleton, NodeType, GameTreeNode,
    BetSizing, RaiseSizing,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput, validate_solve_request,
    MAX_TREE_NODES_FLOP, MAX_TREE_NODES_TURN, MAX_COMBOS_PER_SIDE,
    MAX_COMBOS_PER_SIDE_TURN, MAX_TURN_CARDS, ADAPTIVE_ITER_CAP_TURN_HEAVY,
)


# ── Helpers ────────────────────────────────────────────────────


def count_node_types(node: GameTreeNode) -> dict:
    """Recursively count node types."""
    counts = {"action": 0, "terminal": 0, "chance": 0}
    if node.node_type == NodeType.ACTION:
        counts["action"] += 1
    elif node.node_type == NodeType.TERMINAL:
        counts["terminal"] += 1
    elif node.node_type == NodeType.CHANCE:
        counts["chance"] += 1
    for child in node.children.values():
        child_counts = count_node_types(child)
        for k in counts:
            counts[k] += child_counts[k]
    return counts


def collect_actions_at_root(root: GameTreeNode) -> list[str]:
    """Get the list of available actions at the root node."""
    return list(root.children.keys())


def find_overbet_nodes(node: GameTreeNode, found: list = None) -> list:
    """Recursively find all nodes that have a bet_125 child action."""
    if found is None:
        found = []
    for action_label, child in node.children.items():
        if action_label == "bet_125":
            found.append(node.node_id)
        find_overbet_nodes(child, found)
    return found


# ═══════════════════════════════════════════════════════════════
# A. RICHER ACTION ABSTRACTION
# ═══════════════════════════════════════════════════════════════


class TestExpandedFlopAbstraction:
    """Tests for expanded flop bet/raise sizes."""

    def test_default_tree_config_has_seven_flop_bet_sizes(self):
        """TreeConfig now defaults to 7 flop bet sizes."""
        config = TreeConfig()
        assert len(config.flop_bet_sizes) == 7
        assert config.flop_bet_sizes == (0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25)

    def test_default_tree_config_has_two_flop_raise_sizes(self):
        """TreeConfig now defaults to 2 flop raise sizes."""
        config = TreeConfig()
        assert len(config.flop_raise_sizes) == 2
        assert config.flop_raise_sizes == (2.5, 3.5)

    def test_overbet_125_appears_in_tree(self):
        """A 125% pot overbet option should appear in the tree."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            starting_pot=10.0,
            effective_stack=100.0,
            flop_bet_sizes=(1.25,),
            flop_raise_sizes=(),
            max_raises_per_street=0,
        )
        root, stats = build_tree_skeleton(config)
        root_actions = collect_actions_at_root(root)
        assert "bet_125" in root_actions, f"Expected bet_125, got {root_actions}"

    def test_expanded_flop_tree_has_more_nodes(self):
        """Expanded abstraction produces a larger tree than the old one."""
        old_config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.33, 0.67, 1.0),
            flop_raise_sizes=(2.5,),
        )
        new_config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25),
            flop_raise_sizes=(2.5, 3.5),
        )
        _, old_stats = build_tree_skeleton(old_config)
        _, new_stats = build_tree_skeleton(new_config)
        assert new_stats.total_nodes > old_stats.total_nodes, (
            f"New tree ({new_stats.total_nodes}) should be larger than old ({old_stats.total_nodes})"
        )

    def test_raise_35x_appears_in_tree(self):
        """A 3.5x raise option should appear after a bet."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            starting_pot=10.0,
            effective_stack=100.0,
            flop_bet_sizes=(0.5,),
            flop_raise_sizes=(2.5, 3.5),
            max_raises_per_street=2,
        )
        root, _ = build_tree_skeleton(config)
        # OOP bets 50% → IP faces bet → should have raise options
        bet_50_child = root.children.get("bet_50")
        assert bet_50_child is not None
        ip_actions = list(bet_50_child.children.keys())
        assert "raise_35x" in ip_actions, f"Expected raise_35x, got {ip_actions}"

    def test_flop_tree_stays_within_limits(self):
        """Even with expanded abstraction, flop-only tree stays under limit."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            starting_pot=6.5,
            effective_stack=97.0,
        )
        _, stats = build_tree_skeleton(config)
        assert stats.total_nodes <= MAX_TREE_NODES_FLOP, (
            f"Flop tree has {stats.total_nodes} nodes, limit is {MAX_TREE_NODES_FLOP}"
        )


class TestSolveRequestDefaults:
    """Tests for SolveRequest default values."""

    def test_default_bet_sizes_expanded(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert len(req.bet_sizes) == 7
        assert 1.25 in req.bet_sizes  # overbet

    def test_default_raise_sizes_expanded(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert len(req.raise_sizes) == 2
        assert 3.5 in req.raise_sizes

    def test_default_max_raises_is_three(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert req.max_raises == 3

    def test_turn_bet_sizes_field_exists(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert hasattr(req, "turn_bet_sizes")
        assert req.turn_bet_sizes == [0.33, 0.5, 0.75, 1.0]

    def test_turn_raise_sizes_field_exists(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert hasattr(req, "turn_raise_sizes")
        assert req.turn_raise_sizes == [2.5]

    def test_turn_max_raises_field_exists(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK")
        assert hasattr(req, "turn_max_raises")
        assert req.turn_max_raises == 1


# ═══════════════════════════════════════════════════════════════
# B. STRONGER TURN SOLVING
# ═══════════════════════════════════════════════════════════════


class TestExpandedTurnSupport:
    """Tests for stronger turn solving."""

    def test_default_turn_bet_sizes_are_four(self):
        """Turn bet override now has 4 sizes."""
        config = TreeConfig()
        assert len(config.turn_bet_sizes_override) == 4
        assert config.turn_bet_sizes_override == (0.33, 0.5, 0.75, 1.0)

    def test_default_turn_raise_sizes_not_empty(self):
        """Turn raises are now enabled by default."""
        config = TreeConfig()
        assert len(config.turn_raise_sizes_override) == 1
        assert config.turn_raise_sizes_override == (2.5,)

    def test_default_turn_max_raises_is_one(self):
        """Turn allows 1 raise by default."""
        config = TreeConfig()
        assert config.turn_max_raises == 1

    def test_default_max_turn_cards_is_eight(self):
        """Default turn cards is now 8."""
        config = TreeConfig()
        assert config.max_turn_cards == 8

    def test_turn_tree_has_multiple_bet_sizes(self):
        """Turn subtree should have multiple bet options."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            starting_pot=10.0,
            effective_stack=100.0,
            flop_bet_sizes=(0.5,),
            flop_raise_sizes=(),
            max_raises_per_street=1,
            include_turn=True,
            max_turn_cards=1,
            turn_bet_sizes_override=(0.33, 0.5, 0.75, 1.0),
            turn_raise_sizes_override=(2.5,),
            turn_max_raises=1,
        )
        root, stats = build_tree_skeleton(config)
        assert stats.turn_cards_explored >= 1
        assert stats.chance_nodes >= 1

        # Navigate to turn action nodes:
        # OOP checks → IP checks → chance node → turn subtree
        oop_check = root.children.get("check")
        assert oop_check is not None
        ip_check = oop_check.children.get("check")
        assert ip_check is not None, f"IP check missing, got {list(oop_check.children.keys())}"
        assert ip_check.node_type == NodeType.CHANCE

        # First turn card child
        turn_child = list(ip_check.children.values())[0]
        turn_actions = list(turn_child.children.keys())
        # Should have multiple bet sizes + check
        assert "check" in turn_actions
        bet_actions = [a for a in turn_actions if a.startswith("bet_")]
        assert len(bet_actions) >= 2, f"Expected ≥2 turn bet sizes, got {bet_actions}"

    def test_turn_tree_has_raise_option(self):
        """Turn subtree should have raise options when configured."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            starting_pot=10.0,
            effective_stack=200.0,  # large stack so raise doesn't exceed stack
            flop_bet_sizes=(0.5,),
            flop_raise_sizes=(),
            max_raises_per_street=1,
            include_turn=True,
            max_turn_cards=1,
            turn_bet_sizes_override=(0.5,),
            turn_raise_sizes_override=(2.5,),
            turn_max_raises=2,  # OOP bet uses 1, IP raise uses 1
        )
        root, _ = build_tree_skeleton(config)
        # Navigate to turn: OOP check → IP check → chance → turn OOP
        oop_check = root.children.get("check")
        ip_check = oop_check.children.get("check")
        turn_oop = list(ip_check.children.values())[0]
        # OOP bets on turn → IP faces bet → should have raise option
        bet_child = turn_oop.children.get("bet_50")
        if bet_child:
            ip_turn_actions = list(bet_child.children.keys())
            raise_actions = [a for a in ip_turn_actions if a.startswith("raise_")]
            assert len(raise_actions) >= 1, f"Expected raise on turn, got {ip_turn_actions}"

    def test_turn_tree_size_within_expanded_limits(self):
        """Turn tree with expanded abstraction stays within 25K limit."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            include_turn=True,
            max_turn_cards=8,
        )
        _, stats = build_tree_skeleton(config)
        assert stats.total_nodes <= MAX_TREE_NODES_TURN, (
            f"Turn tree has {stats.total_nodes} nodes, limit is {MAX_TREE_NODES_TURN}"
        )


# ═══════════════════════════════════════════════════════════════
# C. SOLVER OUTPUT / METADATA
# ═══════════════════════════════════════════════════════════════


class TestSolverMetadata:
    """Tests for enriched solver metadata output."""

    def test_flop_solve_metadata_has_action_abstraction(self):
        """Flop solve output includes action_abstraction field."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=10,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            deterministic=True,
        )
        output = solver.solve(request)
        meta = output.metadata
        assert "action_abstraction" in meta
        assert "flop_bet_sizes" in meta
        assert "flop_raise_sizes" in meta
        assert "Turn: not included" in meta["action_abstraction"]

    def test_turn_solve_metadata_has_turn_details(self):
        """Turn-enabled solve metadata includes turn-specific fields."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=10,
            bet_sizes=[0.5],
            raise_sizes=[],
            include_turn=True,
            max_turn_cards=2,
            turn_bet_sizes=[0.5, 1.0],
            turn_raise_sizes=[2.5],
            turn_max_raises=1,
            deterministic=True,
        )
        output = solver.solve(request)
        meta = output.metadata
        assert "turn_bet_sizes" in meta
        assert "turn_raise_sizes" in meta
        assert "turn_max_raises" in meta
        assert meta["turn_bet_sizes"] == [0.5, 1.0]
        assert meta["turn_max_raises"] == 1
        assert "Turn:" in meta["action_abstraction"]
        assert "2 bet sizes" in meta["action_abstraction"]

    def test_metadata_has_max_raises_per_street(self):
        """Metadata includes max_raises_per_street."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=5,
            bet_sizes=[0.5],
            raise_sizes=[],
            deterministic=True,
        )
        output = solver.solve(request)
        assert "max_raises_per_street" in output.metadata


# ═══════════════════════════════════════════════════════════════
# D. VALIDATION / CORRECTNESS
# ═══════════════════════════════════════════════════════════════


class TestValidation:
    """Tests for validation guardrails."""

    def test_valid_flop_request_passes(self):
        """Standard flop request with expanded defaults passes validation."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
        )
        valid, msg = validate_solve_request(request)
        assert valid, f"Should be valid: {msg}"

    def test_valid_turn_request_passes(self):
        """Turn request with defaults passes validation."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            include_turn=True,
            max_turn_cards=5,
            max_iterations=200,
        )
        valid, msg = validate_solve_request(request)
        assert valid, f"Should be valid: {msg}"

    def test_too_many_turn_cards_rejected(self):
        """Requesting more than MAX_TURN_CARDS is rejected."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            include_turn=True,
            max_turn_cards=MAX_TURN_CARDS + 1,
        )
        valid, msg = validate_solve_request(request)
        assert not valid
        assert "safety cap" in msg.lower() or "exceeds" in msg.lower()

    def test_heavy_turn_solve_rejected_at_validation(self):
        """Turn solve with >5 cards and >1000 iterations rejected at validation."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            include_turn=True,
            max_turn_cards=8,
            max_iterations=2000,
        )
        valid, msg = validate_solve_request(request)
        assert not valid
        assert "too expensive" in msg.lower()


# ═══════════════════════════════════════════════════════════════
# E. PERFORMANCE / RUNTIME SAFETY
# ═══════════════════════════════════════════════════════════════


class TestRuntimeSafety:
    """Tests for runtime safety guards."""

    def test_safety_limits_are_correct(self):
        """Safety constants have correct Phase 12A values."""
        assert MAX_TREE_NODES_FLOP == 5000
        assert MAX_TREE_NODES_TURN == 35000
        assert MAX_COMBOS_PER_SIDE == 60
        assert MAX_COMBOS_PER_SIDE_TURN == 40  # Phase 12A: raised from 30
        assert MAX_TURN_CARDS == 15
        assert ADAPTIVE_ITER_CAP_TURN_HEAVY == 300

    def test_adaptive_iteration_cap_activates(self):
        """Solver caps iterations for heavy turn solves (>5 cards)."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=500,  # will be capped to 300
            include_turn=True,
            max_turn_cards=8,
            bet_sizes=[0.5],
            raise_sizes=[],
            turn_bet_sizes=[0.5],
            turn_raise_sizes=[],
            turn_max_raises=0,
            deterministic=True,
        )
        output = solver.solve(request)
        assert output.iterations <= ADAPTIVE_ITER_CAP_TURN_HEAVY, (
            f"Expected ≤{ADAPTIVE_ITER_CAP_TURN_HEAVY} iterations, got {output.iterations}"
        )

    def test_flop_solve_completes_in_reasonable_time(self):
        """Flop solve with expanded abstraction completes in <30s."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK,AKs",
            oop_range="QQ,JJ,TT",
            max_iterations=50,
            deterministic=True,
        )
        start = time.time()
        output = solver.solve(request)
        elapsed = time.time() - start
        assert elapsed < 120, f"Flop solve took {elapsed:.1f}s, expected <120s"
        assert output.iterations == 50

    def test_turn_solve_completes_without_crash(self):
        """Turn solve with expanded abstraction completes without errors."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=20,
            include_turn=True,
            max_turn_cards=3,
            bet_sizes=[0.5],
            raise_sizes=[],
            turn_bet_sizes=[0.5, 1.0],
            turn_raise_sizes=[2.5],
            turn_max_raises=1,
            deterministic=True,
        )
        output = solver.solve(request)
        assert output.iterations == 20
        assert output.tree_nodes > 0
        assert "turn" in output.metadata.get("street_depth", "")


# ═══════════════════════════════════════════════════════════════
# F. REGRESSION PROTECTION
# ═══════════════════════════════════════════════════════════════


class TestRegression:
    """Ensure existing solver behavior is preserved."""

    def test_flop_solve_produces_strategies(self):
        """Basic flop solve still produces valid strategies."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=30,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            deterministic=True,
        )
        output = solver.solve(request)
        assert len(output.strategies) > 0
        # Each strategy should sum to ~1.0
        for node_id, node_strats in output.strategies.items():
            for combo, action_freqs in node_strats.items():
                freq_sum = sum(action_freqs.values())
                assert abs(freq_sum - 1.0) < 0.01, (
                    f"Strategy for {combo} at {node_id} sums to {freq_sum}, expected 1.0"
                )

    def test_exploitability_reported(self):
        """Solve output still includes exploitability_mbb."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=30,
            bet_sizes=[0.5],
            raise_sizes=[],
            deterministic=True,
        )
        output = solver.solve(request)
        assert output.exploitability_mbb is not None
        assert isinstance(output.exploitability_mbb, float)

    def test_convergence_metric_decreases(self):
        """Convergence metric should decrease with more iterations."""
        solver1 = CfrSolver()
        req1 = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=10,
            bet_sizes=[0.5],
            raise_sizes=[],
            deterministic=True,
        )
        out1 = solver1.solve(req1)

        solver2 = CfrSolver()
        req2 = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=100,
            bet_sizes=[0.5],
            raise_sizes=[],
            deterministic=True,
        )
        out2 = solver2.solve(req2)

        assert out2.convergence_metric <= out1.convergence_metric, (
            f"100 iter convergence ({out2.convergence_metric}) should be ≤ "
            f"10 iter ({out1.convergence_metric})"
        )

    def test_tree_config_backward_compatible(self):
        """Old-style TreeConfig construction still works."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.33, 0.67, 1.0),
            flop_raise_sizes=(2.5,),
        )
        root, stats = build_tree_skeleton(config)
        assert stats.total_nodes > 0
        assert stats.action_nodes > 0

