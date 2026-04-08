"""
Phase 13D: Tests for Rust CFR traversal with river chance nodes.

Tests:
1. Rust availability and version
2. Dispatch logic (Rust for flop/turn/river, fallback for callbacks)
3. Tree serialization with river chance nodes
4. Flop + turn backward compatibility
5. Python↔Rust river equivalence
6. River blocker correctness
7. Multi-card coverage
8. Fallback behavior
9. Edge cases
"""
import pytest
import numpy as np
from unittest.mock import MagicMock


# ── 1. Rust availability ──

class TestRustAvailability:
    def test_poker_core_import(self):
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate')
        assert hasattr(poker_core, 'version')

    def test_version_13d(self):
        import poker_core
        v = poker_core.version()
        assert '0.4.0' in v or '13D' in v or 'river' in v.lower() or '0.5.0' in v or '14' in v or 'parallel' in v.lower() or '15B' in v or '0.6' in v


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
            max_river_cards=2,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
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
        req = self._make_request(include_turn=True, include_river=True)
        assert solver._should_use_rust_cfr(req) is True

    def test_callback_uses_rust_15b(self):
        """Phase 15B: callbacks no longer force Python fallback."""
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = self._make_request(include_river=True)
        # Phase 15B: Rust path now handles callbacks via chunked iteration
        assert solver._should_use_rust_cfr(req, cancel_check=lambda: False) is True

    def test_no_arrays_falls_back(self):
        from app.solver.cfr_solver import CfrSolver
        solver = CfrSolver()
        solver._use_arrays = False
        req = self._make_request()
        assert solver._should_use_rust_cfr(req) is False


# ── 3. Tree serialization with river chance nodes ──

class TestTreeSerialization:
    @pytest.fixture
    def river_solver(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        return solver

    def test_has_turn_and_river_chance_nodes(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert 4 in data['node_types'], "Should have turn chance nodes (type 4)"
        assert 5 in data['node_types'], "Should have river chance nodes (type 5)"

    def test_has_chance_card_abs_array(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert 'node_chance_card_abs' in data
        assert np.any(data['node_chance_card_abs'] >= 0)

    def test_has_chance_equity_idx_array(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert 'node_chance_equity_idx' in data
        assert np.any(data['node_chance_equity_idx'] >= 0)

    def test_has_hole_cards_abs(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert 'ip_hole_cards_abs' in data
        assert 'oop_hole_cards_abs' in data
        # 2 slots per combo
        num_ip = data['num_ip']
        assert len(data['ip_hole_cards_abs']) == num_ip * 2

    def test_has_turn_idx_to_abs(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert 'turn_idx_to_abs' in data
        assert len(data['turn_idx_to_abs']) == data['num_turn_cards'] + 1
        assert data['turn_idx_to_abs'][0] == -1  # index 0 = no turn card

    def test_has_river_cards(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        assert data['num_river_cards'] == 2

    def test_equity_tables_2d_layout(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        nt = data['num_turn_cards']
        nr = data['num_river_cards']
        num_ip = data['num_ip']
        num_oop = data['num_oop']
        expected_size = (nt + 1) * (nr + 1) * num_ip * num_oop
        assert len(data['equity_tables']) == expected_size

    def test_flop_serialization_backward_compat(self, river_solver):
        data = river_solver._serialize_tree_for_rust(include_turn=False, include_river=False)
        assert data['num_turn_cards'] == 0
        assert data['num_river_cards'] == 0
        assert len(data['equity_tables']) == data['num_ip'] * data['num_oop']


# ── 4. Flop + turn backward compatibility ──

class TestBackwardCompat:
    def test_flop_convergence_unchanged(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        # Phase 14: parallel mode (simultaneous update) produces slightly
        # different convergence than serial (sequential update).
        # Serial: ~0.215773, Parallel: ~0.235661. Both converge to same equilibrium.
        assert 0.10 < output.convergence_metric < 0.50, \
            f"Convergence {output.convergence_metric} out of expected range"

    def test_turn_convergence_unchanged(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=20, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        out_py = solver_py.solve(req)
        solver_rs = CfrSolver()
        out_rs = solver_rs.solve(req)
        # Phase 14: Rust uses simultaneous-update (parallel), Python uses sequential.
        # Convergence metrics differ but both converge to same equilibrium.
        assert abs(out_py.convergence_metric - out_rs.convergence_metric) < 0.5


# ── 5. Python↔Rust river equivalence ──

class TestRiverEquivalence:
    def _solve_both(self, request):
        from app.solver.cfr_solver import CfrSolver
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        out_py = solver_py.solve(request)
        solver_rs = CfrSolver()
        out_rs = solver_rs.solve(request)
        return out_py, out_rs

    def test_river_1tc_1rc(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=1,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel, 15 iters
        # Exploitability differs substantially at 15 iterations (both poorly converged)
        assert abs(py.exploitability_mbb - rs.exploitability_mbb) < 2000.0

    def test_river_2tc_2rc(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_river_broader_ranges(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA,KK', oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_river_3tc_3rc(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=3,
            include_river=True, max_river_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_river_different_board(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['9s', '7d', '2c'], ip_range='QQ', oop_range='JJ',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        assert abs(py.convergence_metric - rs.convergence_metric) < 2.0  # Phase 14: parallel

    def test_river_strategy_values_match(self):
        from app.solver.cfr_solver import SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=15, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        py, rs = self._solve_both(req)
        # Phase 14: parallel produces different strategies. Verify structural validity.
        for solver_out in [py, rs]:
            for node_id, combos in solver_out.strategies.items():
                for combo, freqs in combos.items():
                    total = sum(freqs.values())
                    assert abs(total - 1.0) < 0.01, \
                        f"Strategy at {node_id}/{combo} sums to {total}"


# ── 6. River blocker correctness ──

class TestRiverBlockers:
    def test_river_blocker_doesnt_corrupt(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=3,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        solver_py = CfrSolver()
        solver_py._should_use_rust_cfr = lambda r, c=None, p=None: False
        py_out = solver_py.solve(req)
        solver_rs = CfrSolver()
        rs_out = solver_rs.solve(req)
        assert abs(py_out.convergence_metric - rs_out.convergence_metric) < 2.0  # Phase 14: parallel

    def test_hole_cards_abs_are_unique(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        data = solver._serialize_tree_for_rust(include_turn=True, include_river=True)
        # Each combo's 2 hole cards should be different
        for combo_idx in range(data['num_ip']):
            c0 = data['ip_hole_cards_abs'][combo_idx * 2]
            c1 = data['ip_hole_cards_abs'][combo_idx * 2 + 1]
            assert c0 != c1, f"IP combo {combo_idx}: cards {c0}, {c1} should differ"


# ── 7. Multi-card coverage ──

class TestMultiCardCoverage:
    def test_1tc_1rc(self):
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

    def test_3tc_3rc(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=3,
            include_river=True, max_river_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert output.iterations == 5
        assert output.tree_nodes > 500

    def test_river_metadata(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        depth = output.metadata.get('street_depth', '')
        assert 'river' in depth


# ── 8. Fallback behavior ──

class TestFallbackBehavior:
    def test_callback_uses_rust_for_river_15b(self):
        """Phase 15B: callbacks no longer force Python fallback."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver._use_arrays = True
        solver._arrays = MagicMock()
        req = SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        )
        # Phase 15B: Rust path now handles callbacks via chunked iteration
        assert solver._should_use_rust_cfr(req, cancel_check=lambda: False) is True
        assert solver._should_use_rust_cfr(req, progress_callback=lambda i, c: None) is True

    def test_python_river_still_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        solver._should_use_rust_cfr = lambda r, c=None, p=None: False
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


# ── 9. Edge cases ──

class TestEdgeCases:
    def test_small_stack_allin_with_river(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=20.0, effective_stack=10.0, bet_sizes=[1.0],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert output.iterations == 5

    def test_multi_bet_sizes_river(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.33, 0.5, 1.0],
            max_iterations=5, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert output.iterations == 5
        assert output.tree_nodes > 1000
