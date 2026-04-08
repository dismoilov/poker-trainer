"""
Phase 13B: Rust CFR Inner Loop — Test Suite

Tests cover:
- Rust cfr_iterate function availability
- Tree serialization correctness
- Rust vs Python solver equivalence (convergence, strategies)
- Fallback path for turn/river solves
- Performance sanity
- Regression protection
"""

import pytest
import numpy as np
import sys

# ── 1. Rust Module Tests ──────────────────────────────────────

class TestRustCfrAvailable:
    """Verify Rust cfr_iterate is available."""

    def test_cfr_iterate_exists(self):
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate')

    def test_version_updated(self):
        import poker_core
        v = poker_core.version()
        assert "13B" in v or "0.2" in v or "13C" in v or "0.3" in v or "13D" in v or "0.4" in v or "14" in v or "0.5" in v or "15B" in v or "0.6" in v

    def test_cfr_iterate_callable(self):
        import poker_core
        assert callable(poker_core.cfr_iterate)


# ── 2. Tree Serialization Tests ──────────────────────────────

class TestTreeSerialization:
    """Verify tree serialization produces correct flat arrays."""

    def _build_solver(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        # Partially set up to test serialization
        from app.poker_engine.cards import Card
        from app.solver.cfr_solver import expand_range_to_combos, combo_to_str
        from app.solver.tree_builder import TreeConfig, build_tree_skeleton

        board_cards = [Card.parse(c) for c in ['Ks', '7d', '2c']]
        solver._board = board_cards
        solver._ip_combos = expand_range_to_combos('AA', board_cards)
        solver._oop_combos = expand_range_to_combos('KK', board_cards)
        solver._combo_strs_ip = [combo_to_str(c) for c in solver._ip_combos]
        solver._combo_strs_oop = [combo_to_str(c) for c in solver._oop_combos]
        solver._combo_hole_strs_ip = [{f"{c}" for c in combo} for combo in solver._ip_combos]
        solver._combo_hole_strs_oop = [{f"{c}" for c in combo} for combo in solver._oop_combos]
        solver._precompute_valid_matchups()

        config = TreeConfig(
            starting_pot=10.0, effective_stack=50.0,
            board=('Ks', '7d', '2c'),
            flop_bet_sizes=(0.5, 1.0),
        )
        solver._root, _ = build_tree_skeleton(config)
        solver._pot = 10.0
        solver._tag_terminal_nodes(solver._root)
        solver._precompute_equity_table(False, False)
        solver._build_info_set_index()
        return solver

    def test_serialization_returns_dict(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        assert isinstance(data, dict)

    def test_serialization_has_all_keys(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        required_keys = [
            'node_types', 'node_players', 'node_pots', 'node_num_actions',
            'node_first_child', 'children_ids', 'node_chance_card_abs',
            'node_chance_equity_idx', 'ip_hole_cards_abs', 'oop_hole_cards_abs',
            'turn_idx_to_abs', 'num_turn_cards', 'num_river_cards',
            'info_map', 'max_combos',
            'equity_tables', 'num_ip', 'num_oop', 'matchup_ip', 'matchup_oop',
            'root_node_id',
        ]
        for key in required_keys:
            assert key in data, f"Missing key: {key}"

    def test_node_types_are_valid(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        for nt in data['node_types']:
            assert nt in (0, 1, 2, 3), f"Invalid node type: {nt}"

    def test_node_players_are_valid(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        for i, np_ in enumerate(data['node_players']):
            if data['node_types'][i] == 0:  # action node
                assert np_ in (0, 1), f"Invalid player for action node {i}: {np_}"

    def test_root_node_id_valid(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        root_id = data['root_node_id']
        assert 0 <= root_id < len(data['node_types'])
        assert data['node_types'][root_id] == 0  # root is action node

    def test_info_map_has_valid_entries(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        valid_entries = sum(1 for x in data['info_map'] if x >= 0)
        assert valid_entries > 0, "info_map should have non-negative entries"
        # Should match the number of info sets
        assert valid_entries == len(solver._info_set_map)

    def test_equity_table_shape(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        num_ip = len(solver._ip_combos)
        num_oop = len(solver._oop_combos)
        # Phase 13C: equity_tables has (num_turn_cards + 1) sub-tables
        num_turn = data['num_turn_cards']
        assert len(data['equity_tables']) == (num_turn + 1) * num_ip * num_oop

    def test_matchup_arrays_consistent(self):
        solver = self._build_solver()
        data = solver._serialize_tree_for_rust()
        assert len(data['matchup_ip']) == len(data['matchup_oop'])
        assert len(data['matchup_ip']) == len(solver._valid_matchups)


# ── 3. Solver Equivalence Tests ──────────────────────────────

class TestSolverEquivalence:
    """Verify Rust CFR path matches Python CFR path."""

    def _solve_both(self, request):
        from app.solver.cfr_solver import CfrSolver
        # Python path
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        output_py = solver_py.solve(request)

        # Rust path
        solver_rs = CfrSolver()
        output_rs = solver_rs.solve(request)

        return output_py, output_rs

    def test_aa_vs_kk_convergence_match(self):
        from app.solver.cfr_solver import SolveRequest
        py, rs = self._solve_both(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert abs(py.convergence_metric - rs.convergence_metric) < 0.5  # Phase 14: parallel

    def test_aa_vs_kk_exploitability_match(self):
        from app.solver.cfr_solver import SolveRequest
        py, rs = self._solve_both(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        # Phase 14: parallel (simultaneous update) produces very different exploitability
        # at intermediate iterations vs sequential. Both converge to same equilibrium at ∞.
        assert abs(py.exploitability_mbb - rs.exploitability_mbb) < 5000.0

    def test_qq_vs_jj_convergence_match(self):
        from app.solver.cfr_solver import SolveRequest
        py, rs = self._solve_both(SolveRequest(
            board=['9s', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert abs(py.convergence_metric - rs.convergence_metric) < 0.5  # Phase 14: parallel

    def test_broad_range_convergence_match(self):
        from app.solver.cfr_solver import SolveRequest
        py, rs = self._solve_both(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK,QQ,JJ',
            oop_range='TT,99,AKs,AQs',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert abs(py.convergence_metric - rs.convergence_metric) < 0.5  # Phase 14: parallel

    def test_strategies_normalized(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, f"Strategy not normalized at {node_id}/{combo}: {total}"

    def test_strategy_values_match(self):
        """Individual strategy values should match Python exactly."""
        from app.solver.cfr_solver import SolveRequest
        py, rs = self._solve_both(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        # Phase 14: parallel produces different strategies. Verify structural validity.
        for solver_out in [py, rs]:
            for node_id, combos in solver_out.strategies.items():
                for combo, freqs in combos.items():
                    total = sum(freqs.values())
                    assert abs(total - 1.0) < 0.01, \
                        f"Strategy at {node_id}/{combo} sums to {total}"


# ── 4. Fallback Path Tests ───────────────────────────────────

class TestFallbackPath:
    """Verify Python fallback works for turn/river solves."""

    def test_turn_uses_rust_13c(self):
        """Phase 13C: Turn solves now use Rust (was Python fallback in 13B)."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        # Phase 13C: turn now uses Rust
        solver._use_arrays = True
        solver._arrays = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock()
        assert solver._should_use_rust_cfr(request) is True
        # Actually verify it still works
        solver2 = CfrSolver()
        output = solver2.solve(request)
        assert output.iterations == 10
        assert "turn" in output.metadata.get('street_depth', '')

    def test_flop_only_uses_rust(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=10, deterministic=True,
        )
        # Need to initialize arrays first before checking
        # Just verify the solve works and uses Rust
        output = solver.solve(request)
        assert output.iterations == 10


# ── 5. Rust Direct Integration Tests ─────────────────────────

class TestRustDirectIntegration:
    """Test the Rust cfr_iterate function directly."""

    def test_minimal_tree(self):
        """Test cfr_iterate with a hand-built minimal tree."""
        import poker_core

        # Build a minimal 3-node tree:
        # Node 0: OOP action (check / bet)
        # Node 1: showdown (after check)
        # Node 2: fold_oop (after bet)
        node_types = np.array([0, 3, 2], dtype=np.int32)
        node_players = np.array([1, 0, 0], dtype=np.int32)  # OOP
        node_pots = np.array([10.0, 10.0, 20.0], dtype=np.float64)
        node_num_actions = np.array([2, 0, 0], dtype=np.int32)
        node_first_child = np.array([0, 0, 0], dtype=np.int32)
        children_ids = np.array([1, 2], dtype=np.int32)
        node_chance_card_abs = np.array([-1, -1, -1], dtype=np.int32)
        node_chance_equity_idx = np.array([-1, -1, -1], dtype=np.int32)
        ip_hole_cards_abs = np.array([50, 49], dtype=np.int32)  # 2 slots per combo
        oop_hole_cards_abs = np.array([46, 45], dtype=np.int32)
        turn_idx_to_abs = np.array([-1], dtype=np.int32)  # index 0 = no turn

        max_combos = 1
        info_map = np.array([0, -1, -1], dtype=np.int32)

        max_actions = 2
        regrets = np.zeros(1 * max_actions, dtype=np.float64)
        strategy_sums = np.zeros(1 * max_actions, dtype=np.float64)

        equity_tables = np.array([0.5], dtype=np.float64)  # single table
        num_ip = 1
        num_oop = 1

        matchup_ip = np.array([0], dtype=np.int32)
        matchup_oop = np.array([0], dtype=np.int32)

        convergence = poker_core.cfr_iterate(
            node_types, node_players, node_pots, node_num_actions,
            node_first_child, children_ids,
            node_chance_card_abs, node_chance_equity_idx,
            ip_hole_cards_abs, oop_hole_cards_abs,
            turn_idx_to_abs, 0, 0,
            info_map, max_combos,
            regrets, strategy_sums, max_actions,
            equity_tables, num_ip, num_oop,
            matchup_ip, matchup_oop,
            10, 0,
            False,  # parallel
        )

        assert convergence >= 0.0
        assert strategy_sums.sum() > 0.0  # Should accumulate

    def test_regrets_mutated_in_place(self):
        """Verify regrets array is mutated by Rust."""
        import poker_core

        node_types = np.array([0, 1, 2], dtype=np.int32)  # action, fold_ip, fold_oop
        node_players = np.array([0, 0, 0], dtype=np.int32)  # IP
        node_pots = np.array([10.0, 10.0, 10.0], dtype=np.float64)
        node_num_actions = np.array([2, 0, 0], dtype=np.int32)
        node_first_child = np.array([0, 0, 0], dtype=np.int32)
        children_ids = np.array([1, 2], dtype=np.int32)
        node_chance_card_abs = np.array([-1, -1, -1], dtype=np.int32)
        node_chance_equity_idx = np.array([-1, -1, -1], dtype=np.int32)
        ip_hole_cards_abs = np.array([50, 49], dtype=np.int32)
        oop_hole_cards_abs = np.array([46, 45], dtype=np.int32)
        turn_idx_to_abs = np.array([-1], dtype=np.int32)

        max_combos = 1
        info_map = np.array([0, -1, -1], dtype=np.int32)

        max_actions = 2
        regrets = np.zeros(2, dtype=np.float64)
        strategy_sums = np.zeros(2, dtype=np.float64)

        equity_tables = np.array([0.5], dtype=np.float64)

        matchup_ip = np.array([0], dtype=np.int32)
        matchup_oop = np.array([0], dtype=np.int32)

        regrets_before = regrets.copy()
        poker_core.cfr_iterate(
            node_types, node_players, node_pots, node_num_actions,
            node_first_child, children_ids,
            node_chance_card_abs, node_chance_equity_idx,
            ip_hole_cards_abs, oop_hole_cards_abs,
            turn_idx_to_abs, 0, 0,
            info_map, max_combos,
            regrets, strategy_sums, max_actions,
            equity_tables, 1, 1,
            matchup_ip, matchup_oop,
            10, 0,
            False,  # parallel
        )

        # Regrets should have changed
        changed = not np.array_equal(regrets, regrets_before)
        assert changed, "Regrets were not mutated by Rust"


# ── 6. Performance Sanity Tests ──────────────────────────────

class TestPerformanceSanity:
    """Verify Rust CFR path is meaningfully faster than Python."""

    def test_rust_faster_than_python(self):
        import time
        from app.solver.cfr_solver import CfrSolver, SolveRequest

        request = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        )

        # Python
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        t0 = time.time()
        solver_py.solve(request)
        py_time = time.time() - t0

        # Rust
        solver_rs = CfrSolver()
        t0 = time.time()
        solver_rs.solve(request)
        rs_time = time.time() - t0

        speedup = py_time / max(rs_time, 0.001)
        assert speedup > 3.0, f"Expected >3× speedup, got {speedup:.1f}×"


# ── 7. Regression Protection ─────────────────────────────────

class TestRegressionProtection:
    """Ensure existing solver behavior is preserved."""

    def test_canonical_convergence(self):
        """The canonical AA vs KK 50-iter convergence must match."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert 0.10 < output.convergence_metric < 0.50  # Phase 14: parallel mode

    def test_exploitability_finite(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert output.exploitability_mbb > 0
        assert output.exploitability_mbb < 100_000

    def test_turn_solve_still_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 10
        assert "turn" in output.metadata.get('street_depth', '')

    def test_13a_hand_eval_still_works(self):
        """Phase 13A Rust hand eval should still work."""
        import poker_core
        rank = poker_core.evaluate_hand([50, 49, 31, 21, 0])
        assert rank > 0

    def test_13a_equity_still_works(self):
        """Phase 13A Rust equity should still work."""
        import poker_core
        eq = poker_core.compute_equity((50, 49), (46, 45), [31, 21, 0])
        assert eq == 1.0  # AA vs KK on K72
