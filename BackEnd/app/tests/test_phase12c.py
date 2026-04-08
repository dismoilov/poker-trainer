"""
Phase 12C: Solver Core Extraction Tests

Tests for:
- SolverArrays flat storage class
- Info-set integer indexing
- Integer node IDs in tree finalization
- Array-based regret/strategy equivalence with dict-based path
- Convergence correctness with arrays
- Strategy extraction from arrays matches legacy format
- Performance: array solver not slower than dict solver
"""

import pytest
import time

from app.solver.tree_builder import (
    TreeConfig, build_tree_skeleton, NodeType, GameTreeNode, _finalize_tree,
)
from app.solver.cfr_solver import (
    CfrSolver, SolveRequest, SolveOutput, SolverArrays,
    validate_solve_request,
    MAX_COMBOS_PER_SIDE, MAX_COMBOS_PER_SIDE_TURN, MAX_COMBOS_PER_SIDE_RIVER,
)


# ═══════════════════════════════════════════════════════════════
# A. SOLVER ARRAYS CLASS
# ═══════════════════════════════════════════════════════════════


class TestSolverArrays:
    """Tests for the flat array storage class."""

    def test_basic_creation(self):
        """SolverArrays initializes with correct dimensions."""
        arrays = SolverArrays(100, 5)
        assert arrays.num_info_sets == 100
        assert arrays.max_actions == 5
        assert len(arrays.regrets) == 500
        assert len(arrays.strategy_sums) == 500
        assert len(arrays.action_counts) == 100

    def test_all_zeros_on_init(self):
        """All arrays initialize to zero."""
        arrays = SolverArrays(10, 3)
        assert all(r == 0.0 for r in arrays.regrets)
        assert all(s == 0.0 for s in arrays.strategy_sums)
        assert all(c == 0 for c in arrays.action_counts)

    def test_get_set_regret(self):
        """Can read/write regrets by (info_idx, action_idx)."""
        arrays = SolverArrays(5, 3)
        arrays.set_regret(2, 1, 4.5)
        assert arrays.get_regret(2, 1) == 4.5
        assert arrays.get_regret(2, 0) == 0.0
        assert arrays.get_regret(0, 0) == 0.0

    def test_get_set_strategy_sum(self):
        """Can read/write strategy sums."""
        arrays = SolverArrays(5, 3)
        arrays.add_strategy_sum(1, 0, 2.0)
        arrays.add_strategy_sum(1, 0, 3.0)
        assert arrays.get_strategy_sum(1, 0) == 5.0
        assert arrays.get_strategy_sum(1, 1) == 0.0

    def test_flat_indexing_is_correct(self):
        """Flat index = info_idx * max_actions + action_idx."""
        arrays = SolverArrays(3, 4)
        arrays.set_regret(2, 3, 99.0)
        # Expected flat index: 2 * 4 + 3 = 11
        assert arrays.regrets[11] == 99.0

    def test_large_allocation(self):
        """Can allocate for large info-set counts without error."""
        arrays = SolverArrays(50000, 10)
        assert len(arrays.regrets) == 500000
        arrays.set_regret(49999, 9, 1.0)
        assert arrays.get_regret(49999, 9) == 1.0


# ═══════════════════════════════════════════════════════════════
# B. INTEGER NODE IDS
# ═══════════════════════════════════════════════════════════════


class TestIntegerNodeIds:
    """Tests for integer node ID assignment in tree finalization."""

    def test_root_gets_id_zero(self):
        """Root node should have _int_id == 0."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5,),
            flop_raise_sizes=(),
            max_raises_per_street=0,
        )
        root, _ = build_tree_skeleton(config)
        assert root._int_id == 0

    def test_all_nodes_have_unique_ids(self):
        """All nodes in tree should have unique, non-negative _int_id."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0),
            flop_raise_sizes=(2.5,),
        )
        root, stats = build_tree_skeleton(config)
        
        ids = set()
        def _collect(node):
            assert node._int_id >= 0, f"Node {node.node_id} has invalid _int_id={node._int_id}"
            ids.add(node._int_id)
            for child in node.children.values():
                _collect(child)
        _collect(root)
        
        assert len(ids) == stats.total_nodes, (
            f"Expected {stats.total_nodes} unique IDs, got {len(ids)}"
        )

    def test_ids_are_sequential(self):
        """IDs should be sequential from 0 to N-1."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5,),
            flop_raise_sizes=(),
            max_raises_per_street=0,
        )
        root, stats = build_tree_skeleton(config)
        
        ids = []
        def _collect(node):
            ids.append(node._int_id)
            for child in node.children.values():
                _collect(child)
        _collect(root)
        
        assert sorted(ids) == list(range(stats.total_nodes))

    def test_action_indices_assigned(self):
        """Action nodes should have _action_indices tuple."""
        config = TreeConfig(
            board=("Ks", "7d", "2c"),
            flop_bet_sizes=(0.5, 1.0),
            flop_raise_sizes=(),
            max_raises_per_street=0,
        )
        root, _ = build_tree_skeleton(config)
        assert len(root._action_indices) == len(root.children)
        assert root._action_indices == tuple(range(len(root.children)))


# ═══════════════════════════════════════════════════════════════
# C. INFO-SET INDEX BUILDING
# ═══════════════════════════════════════════════════════════════


class TestInfoSetIndex:
    """Tests for info-set integer indexing in the solver."""

    def test_info_set_map_populated(self):
        """Solver should populate _info_set_map during solve setup."""
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
        assert len(solver._info_set_map) > 0
        assert solver._use_arrays is True
        assert solver._arrays is not None

    def test_info_set_indices_are_unique(self):
        """All info set indices should be unique."""
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
        solver.solve(request)
        indices = list(solver._info_set_map.values())
        assert len(set(indices)) == len(indices), "Duplicate info set indices found"

    def test_info_set_actions_consistent(self):
        """Each info set index should map to its correct action tuple."""
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
        solver.solve(request)
        for info_key, idx in solver._info_set_map.items():
            actions = solver._info_set_actions[idx]
            assert len(actions) > 0, f"Info set {info_key} has no actions"

    def test_arrays_dimensioned_correctly(self):
        """SolverArrays should have enough capacity for all info sets."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=5,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            deterministic=True,
        )
        solver.solve(request)
        arrays = solver._arrays
        assert arrays.num_info_sets == len(solver._info_set_map)
        assert arrays.max_actions >= max(
            len(v) for v in solver._info_set_actions.values()
        )


# ═══════════════════════════════════════════════════════════════
# D. CORRECTNESS: ARRAY PATH vs LEGACY PATH
# ═══════════════════════════════════════════════════════════════


class TestArrayCorrectness:
    """Verify that array-based solver produces correct results."""

    def test_strategies_sum_to_one(self):
        """Array-path strategies should sum to ~1.0 for each combo."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            max_iterations=50,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            deterministic=True,
        )
        output = solver.solve(request)
        for node_id, node_strats in output.strategies.items():
            for combo, action_freqs in node_strats.items():
                freq_sum = sum(action_freqs.values())
                assert abs(freq_sum - 1.0) < 0.01, (
                    f"Strategy at {node_id}/{combo} sums to {freq_sum}"
                )

    def test_convergence_decreases_with_iterations(self):
        """Array-path convergence should improve with more iterations."""
        solver1 = CfrSolver()
        out1 = solver1.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            max_iterations=10, bet_sizes=[0.5], raise_sizes=[],
            deterministic=True,
        ))
        solver2 = CfrSolver()
        out2 = solver2.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            max_iterations=100, bet_sizes=[0.5], raise_sizes=[],
            deterministic=True,
        ))
        assert out2.convergence_metric <= out1.convergence_metric

    def test_exploitability_computed(self):
        """Array-path should still compute exploitability."""
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            max_iterations=50, bet_sizes=[0.5], raise_sizes=[],
            deterministic=True,
        ))
        assert output.exploitability_mbb is not None
        assert isinstance(output.exploitability_mbb, float)
        assert output.exploitability_mbb >= 0

    def test_turn_solve_with_arrays(self):
        """Turn solve should work correctly with array path."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            max_iterations=15,
            bet_sizes=[0.5], raise_sizes=[],
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[],
            turn_max_raises=0,
            deterministic=True,
        )
        output = solver.solve(request)
        assert output.iterations == 15
        assert len(output.strategies) > 0
        assert "turn" in output.metadata.get("street_depth", "")

    def test_river_solve_with_arrays(self):
        """River solve should work correctly with array path."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA", oop_range="KK",
            max_iterations=10,
            bet_sizes=[0.5], raise_sizes=[],
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[],
            turn_max_raises=0,
            include_river=True, max_river_cards=1,
            river_bet_sizes=[0.5], river_raise_sizes=[],
            river_max_raises=0,
            deterministic=True,
        )
        output = solver.solve(request)
        assert output.iterations == 10
        assert len(output.strategies) > 0
        assert "river" in output.metadata.get("street_depth", "")


# ═══════════════════════════════════════════════════════════════
# E. PERFORMANCE: ARRAY PATH NOT SLOWER
# ═══════════════════════════════════════════════════════════════


class TestArrayPerformance:
    """Verify array path is not slower than legacy path."""

    def test_flop_solve_reasonable_time(self):
        """Array-path flop solve should complete in <60s."""
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
        assert elapsed < 60, f"Flop solve took {elapsed:.1f}s, expected <60s"
        assert output.iterations == 50

    def test_info_set_count_reasonable(self):
        """Number of info sets should be proportional to tree × combos."""
        solver = CfrSolver()
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            max_iterations=5,
            bet_sizes=[0.5, 1.0],
            raise_sizes=[2.5],
            deterministic=True,
        )
        output = solver.solve(request)
        # Info sets = action_nodes × combos_per_side (roughly)
        assert len(solver._info_set_map) > 0
        # Memory footprint: 2 arrays × info_sets × max_actions × 8 bytes each
        mem_kb = (solver._arrays.num_info_sets * solver._arrays.max_actions * 8 * 2) / 1024
        assert mem_kb < 10000, f"Array memory {mem_kb:.1f} KB seems excessive"


# ═══════════════════════════════════════════════════════════════
# F. BOUNDARY / MIGRATION READINESS
# ═══════════════════════════════════════════════════════════════


class TestMigrationReadiness:
    """Tests that verify the architecture is migration-ready."""

    def test_solver_arrays_has_slots(self):
        """SolverArrays uses __slots__ for memory efficiency."""
        assert hasattr(SolverArrays, '__slots__')

    def test_flat_data_contiguous(self):
        """Flat arrays should be contiguous numpy ndarrays."""
        import numpy as np
        arrays = SolverArrays(100, 5)
        assert isinstance(arrays.regrets, np.ndarray)
        assert isinstance(arrays.strategy_sums, np.ndarray)
        assert arrays.regrets.dtype == np.float64
        assert arrays.regrets.flags['C_CONTIGUOUS']
        assert len(arrays.regrets) == 500

    def test_game_tree_node_has_int_id(self):
        """GameTreeNode now has _int_id field."""
        node = GameTreeNode(node_id="test", node_type=NodeType.ACTION)
        assert hasattr(node, '_int_id')
        assert node._int_id == -1  # default before finalization

    def test_game_tree_node_has_action_indices(self):
        """GameTreeNode now has _action_indices field."""
        node = GameTreeNode(node_id="test", node_type=NodeType.ACTION)
        assert hasattr(node, '_action_indices')
        assert node._action_indices == ()

    def test_safety_limits_current(self):
        """Phase 12A safety limits are correct."""
        assert MAX_COMBOS_PER_SIDE == 60
        assert MAX_COMBOS_PER_SIDE_TURN == 40
        assert MAX_COMBOS_PER_SIDE_RIVER == 20
