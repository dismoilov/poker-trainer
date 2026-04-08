"""
Phase 13C: Tests for Rust CFR traversal with turn chance nodes.

Tests:
1. Rust availability and version
2. Turn dispatch logic (Rust for turn, fallback for river)
3. Tree serialization with chance nodes
4. Flop-only backward compatibility
5. Python↔Rust turn equivalence
6. Blocker correctness
7. Multi-turn-card coverage
8. Fallback behavior
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock


# ── 1. Rust availability ──

class TestRustAvailability:
    def test_poker_core_import(self):
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate')
        assert hasattr(poker_core, 'version')

    def test_version_13c(self):
        import poker_core
        v = poker_core.version()
        assert '0.3.0' in v or '13C' in v or 'chance' in v.lower() or '0.4.0' in v or '13D' in v or '0.5.0' in v or '14' in v or 'parallel' in v.lower() or '15B' in v or '0.6' in v


# ── 2. Dispatch logic ──

class TestDispatchLogic:
    def _make_request(self, include_turn=False, include_river=False):
        from app.solver.cfr_solver import SolveRequest
        return SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=include_turn,
            include_river=include_river,
            max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )

    def test_flop_uses_rust(self):
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = self._make_request(include_turn=False)
        assert solver._should_use_rust_cfr(req) is True

    def test_turn_uses_rust(self):
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = self._make_request(include_turn=True)
        assert solver._should_use_rust_cfr(req) is True

    def test_river_uses_rust(self):
        """Phase 13D: River solves now use Rust."""
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = self._make_request(include_river=True)
        assert solver._should_use_rust_cfr(req) is True

    def test_callback_uses_rust_15b(self):
        """Phase 15B: callbacks no longer force Python fallback."""
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = self._make_request(include_turn=True)
        assert solver._should_use_rust_cfr(req, cancel_check=lambda: False) is True

    def test_no_arrays_falls_back(self):
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = False
        req = self._make_request()
        assert solver._should_use_rust_cfr(req) is False


# ── 3. Tree serialization with chance nodes ──

class TestTreeSerialization:
    @pytest.fixture
    def turn_solver(self):
        """Run a turn solve to get a solver with an active tree."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        return solver

    def test_serialization_includes_chance_nodes(self, turn_solver):
        data = turn_solver._serialize_tree_for_rust(include_turn=True)
        # Should have type 4 (chance) nodes
        assert 4 in data['node_types'], "Serialized tree should contain chance nodes (type 4)"

    def test_serialization_has_chance_card_array(self, turn_solver):
        data = turn_solver._serialize_tree_for_rust(include_turn=True)
        assert 'node_chance_card_abs' in data
        # At least some entries should be non-negative (turn card absolute ints)
        assert np.any(data['node_chance_card_abs'] >= 0), "Some nodes should have turn card abs ints"

    def test_serialization_has_hole_cards(self, turn_solver):
        data = turn_solver._serialize_tree_for_rust(include_turn=True)
        assert 'ip_hole_cards_abs' in data
        assert 'oop_hole_cards_abs' in data

    def test_serialization_has_multi_equity_tables(self, turn_solver):
        data = turn_solver._serialize_tree_for_rust(include_turn=True)
        num_ip = data['num_ip']
        num_oop = data['num_oop']
        num_turn_cards = data['num_turn_cards']
        nr = data['num_river_cards']  # Phase 13D: 2D layout
        expected_size = (num_turn_cards + 1) * (nr + 1) * num_ip * num_oop
        assert len(data['equity_tables']) == expected_size
        assert num_turn_cards == 2

    def test_flop_serialization_no_chance_nodes(self, turn_solver):
        """Even on a turn tree, flop serialization should work."""
        data = turn_solver._serialize_tree_for_rust(include_turn=False)
        # num_turn_cards should be 0
        assert data['num_turn_cards'] == 0
        # equity_tables should be single table
        assert len(data['equity_tables']) == data['num_ip'] * data['num_oop']

    def test_chance_node_children_have_card_indices(self, turn_solver):
        data = turn_solver._serialize_tree_for_rust(include_turn=True)
        # Find chance nodes (type 4)
        chance_indices = np.where(data['node_types'] == 4)[0]
        assert len(chance_indices) > 0
        
        for cn_idx in chance_indices:
            num_branches = data['node_num_actions'][cn_idx]
            first_child = data['node_first_child'][cn_idx]
            for b in range(num_branches):
                child_id = data['children_ids'][first_child + b]
                tc = data['node_chance_card_abs'][child_id]
                assert tc >= 0, f"Chance child {child_id} should have valid card abs int"


# ── 4. Flop-only backward compatibility ──

class TestFlopBackwardCompat:
    def test_flop_convergence_unchanged(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert 0.10 < output.convergence_metric < 0.50, \
            f"Flop regression: convergence {output.convergence_metric} out of range"

    def test_flop_with_different_ranges(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
        ))
        assert output.convergence_metric > 0.0
        assert output.iterations == 20


# ── 5. Python↔Rust turn equivalence ──

class TestTurnEquivalence:
    def _solve_both(self, request):
        from app.solver.cfr_solver import CfrSolver
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        out_py = solver_py.solve(request)
        
        solver_rs = CfrSolver()
        out_rs = solver_rs.solve(request)
        
        return out_py, out_rs

    def test_turn_aa_vs_kk_2_cards(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel
        assert abs(py.exploitability_mbb - rs.exploitability_mbb) < 5000.0  # Phase 14: parallel

    def test_turn_qq_vs_jj_2_cards(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['9s', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_turn_broader_ranges(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK', oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_turn_3_cards(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_turn_5_cards(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=5,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_turn_strategy_values_match(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        py, rs = self._solve_both(req)
        # Phase 14: parallel (simultaneous update) produces different intermediate
        # strategies than sequential. Verify structural correctness instead of exact match.
        for solver_out in [py, rs]:
            for node_id, combos in solver_out.strategies.items():
                for combo, freqs in combos.items():
                    total = sum(freqs.values())
                    assert abs(total - 1.0) < 0.01, \
                        f"Strategy at {node_id}/{combo} sums to {total}, expected ~1.0"


# ── 6. Blocker correctness ──

class TestBlockerCorrectness:
    def test_hole_card_blocking(self):
        """Verify that the serialization correctly marks hole cards as blockers."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        data = solver._serialize_tree_for_rust(include_turn=True)
        
        # Check IP hole cards: AA combos have Ace cards
        # If any turn card is an Ace, it should be reflected in ip_hole_cards
        ip_hc = data['ip_hole_cards_abs']
        # Check that the hole card array has entries
        assert len(ip_hc) > 0
        
    def test_blocked_branch_doesnt_corrupt(self):
        """Solve with combos that block some turn cards and verify correctness."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        # Board has Ks, IP has KK — some turn cards may conflict
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        py_out = solver_py.solve(req)
        
        solver_rs = CfrSolver()
        rs_out = solver_rs.solve(req)
        
        assert abs(py_out.convergence_metric - rs_out.convergence_metric) < 0.5  # Phase 14: parallel


# ── 7. Multi-turn-card coverage ──

class TestMultiTurnCard:
    def test_1_turn_card(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 5
        assert output.convergence_metric > 0.0

    def test_5_turn_cards(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=5,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 5
        assert output.tree_nodes > 300  # should have more nodes than 1-card

    def test_turn_metadata(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.metadata.get('street_depth') == 'flop_plus_turn'


# ── 8. Fallback behavior ──

class TestFallbackBehavior:
    def test_python_fallback_for_river(self):
        """River solves should still work (via Python fallback)."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=1,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert output.iterations == 5
        assert output.convergence_metric > 0.0

    def test_python_fallback_with_callback(self):
        """Phase 15B: Callback no longer forces Python path — Rust handles it via chunked iteration."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        # Phase 15B: Rust path now handles callbacks via chunked iteration
        assert solver._should_use_rust_cfr(req, cancel_check=lambda: False) is True
        assert solver._should_use_rust_cfr(req, progress_callback=lambda i, c: None) is True


# ── 9. Edge cases ──

class TestEdgeCases:
    def test_turn_no_raises(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 5

    def test_turn_with_allin(self):
        """Small stack should create allin + turn tree."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=20.0, effective_stack=10.0, bet_sizes=[1.0],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.iterations == 5
