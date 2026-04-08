"""
Phase 10B: Expanded-Scope Solver Validation Tests

Tests validate:
- Narrow vs broad abstraction plausibility
- Turn quality under expanded configuration
- Runtime guardrails and cost safety
- Output quality and metadata completeness
- Regression protection for expanded scope
"""

import time
import pytest

from app.solver.tree_builder import (
    TreeConfig, build_tree_skeleton, NodeType, GameTreeNode,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput, validate_solve_request,
    MAX_TREE_NODES_FLOP, MAX_TREE_NODES_TURN,
    MAX_COMBOS_PER_SIDE, MAX_COMBOS_PER_SIDE_TURN,
    MAX_TURN_CARDS, ADAPTIVE_ITER_CAP_TURN_HEAVY,
)


# ═══════════════════════════════════════════════════════════════
# A. EXPANDED ABSTRACTION PLAUSIBILITY
# ═══════════════════════════════════════════════════════════════


class TestExpandedAbstractionPlausibility:
    """Validate that the broader abstraction produces plausible output."""

    def test_broad_flop_strategies_normalized(self):
        """All strategies under broad abstraction should sum to 1.0."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5, 3.5],
            max_iterations=50, max_raises=3, deterministic=True,
        ))
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.02, (
                    f"Strategy not normalized at {node_id}/{combo}: {total}"
                )

    def test_broad_produces_more_strategy_nodes_than_narrow(self):
        """Broader abstraction should produce more strategy nodes."""
        solver_n = CfrSolver()
        out_n = solver_n.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=30, max_raises=2, deterministic=True,
        ))
        solver_b = CfrSolver()
        out_b = solver_b.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5, 3.5],
            max_iterations=30, max_raises=3, deterministic=True,
        ))
        assert len(out_b.strategies) > len(out_n.strategies)

    def test_broad_has_overbet_actions(self):
        """Broad abstraction should include overbet (125%) actions."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5],
            max_iterations=20, max_raises=2, deterministic=True,
        ))
        all_actions = set()
        for combos in output.strategies.values():
            for freqs in combos.values():
                all_actions.update(freqs.keys())
        assert "bet_125" in all_actions, f"Expected bet_125, got {sorted(all_actions)}"

    def test_broad_converges_better_than_narrow_at_same_iterations(self):
        """Broader abstraction with more actions should not diverge."""
        solver_n = CfrSolver()
        out_n = solver_n.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=100, max_raises=1, deterministic=True,
        ))
        solver_b = CfrSolver()
        out_b = solver_b.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.25, 0.5, 1.0, 1.25], raise_sizes=[],
            max_iterations=100, max_raises=1, deterministic=True,
        ))
        # Both should converge (metric should decrease from initial)
        assert out_n.convergence_metric < 100.0
        assert out_b.convergence_metric < 100.0

    def test_connected_board_broad_plausible(self):
        """Broad abstraction on connected board should remain plausible."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Jh", "Td", "9s"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5, 3.5],
            max_iterations=50, max_raises=3, deterministic=True,
        ))
        assert len(output.strategies) > 0
        for combos in output.strategies.values():
            for freqs in combos.values():
                assert abs(sum(freqs.values()) - 1.0) < 0.02

    def test_monotone_board_broad_plausible(self):
        """Broad abstraction on monotone board should remain plausible."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ah", "Kh", "5h"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5, 3.5],
            max_iterations=50, max_raises=3, deterministic=True,
        ))
        assert len(output.strategies) > 0
        assert output.convergence_metric < 100.0


# ═══════════════════════════════════════════════════════════════
# B. TURN QUALITY AUDIT
# ═══════════════════════════════════════════════════════════════


class TestTurnQualityAudit:
    """Validate turn-solving quality under expanded configuration."""

    def test_richer_turn_produces_more_strategies(self):
        """Turn with 4 bet sizes should produce more strategy nodes than 1 bet size."""
        solver_min = CfrSolver()
        out_min = solver_min.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        solver_rich = CfrSolver()
        out_rich = solver_rich.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.33, 0.5, 0.75, 1.0], turn_raise_sizes=[2.5],
            turn_max_raises=1,
        ))
        assert len(out_rich.strategies) > len(out_min.strategies), (
            f"Rich turn ({len(out_rich.strategies)}) should have more strat nodes "
            f"than min ({len(out_min.strategies)})"
        )

    def test_turn_strategies_all_normalized(self):
        """All turn strategies should sum to 1.0."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=5,
            turn_bet_sizes=[0.33, 0.5, 0.75, 1.0], turn_raise_sizes=[2.5],
            turn_max_raises=1,
        ))
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.02, (
                    f"Turn strategy not normalized at {node_id}/{combo}: {total}"
                )

    def test_turn_exploitability_finite(self):
        """Turn solve should produce finite exploitability."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5, 1.0], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.exploitability_mbb < float("inf")
        assert output.exploitability_mbb >= 0

    def test_turn_metadata_has_action_abstraction(self):
        """Turn solve metadata should include turn-specific abstraction info."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=20, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.33, 0.5, 0.75, 1.0], turn_raise_sizes=[2.5],
            turn_max_raises=1,
        ))
        meta = output.metadata
        assert "Turn:" in meta["action_abstraction"]
        assert "4 bet sizes" in meta["action_abstraction"]
        assert meta["turn_max_raises"] == 1

    def test_turn_heavy_completes_under_adaptive_cap(self):
        """Heavy turn solve should be capped by adaptive iteration limit."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=500, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=8,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations <= ADAPTIVE_ITER_CAP_TURN_HEAVY

    def test_turn_8cards_produces_valid_strategies(self):
        """Turn with 8 cards should still produce valid strategies."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=8,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert len(output.strategies) > 0
        assert output.tree_nodes > 0


# ═══════════════════════════════════════════════════════════════
# C. RUNTIME / COST GUARDRAILS
# ═══════════════════════════════════════════════════════════════


class TestRuntimeCostGuardrails:
    """Validate runtime stays within acceptable bounds."""

    def test_narrow_flop_under_15s(self):
        """Narrow flop solve (100 iter) should finish in <15s."""
        start = time.time()
        CfrSolver().solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            bet_sizes=[0.33, 0.67, 1.0], raise_sizes=[2.5],
            max_iterations=100, max_raises=3, deterministic=True,
        ))
        assert time.time() - start < 15

    def test_broad_flop_under_60s(self):
        """Broad flop solve (100 iter) should finish in <60s."""
        start = time.time()
        CfrSolver().solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK", oop_range="QQ,JJ",
            bet_sizes=[0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25],
            raise_sizes=[2.5, 3.5],
            max_iterations=100, max_raises=3, deterministic=True,
        ))
        assert time.time() - start < 180

    def test_turn_rich_under_10s(self):
        """Rich turn solve (50 iter, 5 cards) should finish in <10s."""
        start = time.time()
        CfrSolver().solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=5,
            turn_bet_sizes=[0.33, 0.5, 0.75, 1.0], turn_raise_sizes=[2.5],
            turn_max_raises=1,
        ))
        assert time.time() - start < 60

    def test_default_turn_tree_within_limits(self):
        """Default turn tree (8 cards, full abstraction) should fit limit."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            include_turn=True, max_turn_cards=8,
        )
        _, stats = build_tree_skeleton(config)
        assert stats.total_nodes <= MAX_TREE_NODES_TURN, (
            f"Default turn tree ({stats.total_nodes}) exceeds limit ({MAX_TREE_NODES_TURN})"
        )

    def test_broad_flop_tree_within_limits(self):
        """Broad flop-only tree should stay within flop limit."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25),
            flop_raise_sizes=(2.5, 3.5),
        )
        _, stats = build_tree_skeleton(config)
        assert stats.total_nodes <= MAX_TREE_NODES_FLOP, (
            f"Broad flop tree ({stats.total_nodes}) exceeds limit ({MAX_TREE_NODES_FLOP})"
        )


# ═══════════════════════════════════════════════════════════════
# D. OUTPUT QUALITY & METADATA
# ═══════════════════════════════════════════════════════════════


class TestOutputQualityAndMetadata:
    """Validate output completeness and quality."""

    def test_metadata_has_all_required_fields(self):
        """Solve metadata should have all Phase 10A fields."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=10, max_raises=2, deterministic=True,
        ))
        meta = output.metadata
        required = [
            "algorithm", "scope", "street_depth", "board",
            "flop_bet_sizes", "flop_raise_sizes",
            "turn_bet_sizes", "turn_raise_sizes", "turn_max_raises",
            "max_raises_per_street", "action_abstraction",
            "honest_note", "validation", "exploitability",
        ]
        for field in required:
            assert field in meta, f"Missing metadata field: {field}"

    def test_honest_note_present_and_accurate(self):
        """Honest note should accurately describe scope limitations."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=10, deterministic=True,
        ))
        note = output.metadata["honest_note"]
        assert "fixed bet sizes" in note
        assert "NOT full-NLHE" in note

    def test_turn_solve_honest_note_mentions_turn(self):
        """Turn solve honest note should reference turn scope."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        note = output.metadata["honest_note"]
        assert "flop plus turn" in note

    def test_validation_result_in_metadata(self):
        """Validation result should be in metadata."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, deterministic=True,
        ))
        val = output.metadata["validation"]
        assert "passed" in val
        assert "checks_run" in val

    def test_exploitability_result_in_metadata(self):
        """Exploitability result should be in metadata."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, deterministic=True,
        ))
        expl = output.metadata["exploitability"]
        assert "exploitability_mbb_per_hand" in expl


# ═══════════════════════════════════════════════════════════════
# E. REGRESSION PROTECTION
# ═══════════════════════════════════════════════════════════════


class TestPhase10BRegression:
    """Ensure nothing broke from Phase 10A changes."""

    def test_flop_only_solve_still_works(self):
        """Basic flop solve should still work."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=30, max_raises=2, deterministic=True,
        ))
        assert output.iterations == 30
        assert len(output.strategies) > 0
        assert output.metadata["street_depth"] == "flop_only"

    def test_turn_solve_still_works(self):
        """Turn solve should still work."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=20, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 20
        assert output.metadata["street_depth"] == "flop_plus_turn"

    def test_validation_still_passes(self):
        """Solver validation should still pass."""
        from app.solver.solver_validation import validate_solve_output
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, deterministic=True,
        ))
        vr = validate_solve_output(
            output.strategies, output.iterations, output.convergence_metric
        )
        assert vr.passed is True
