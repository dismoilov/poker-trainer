"""
Phase 15A: Practical Range Expansion Tests.

Tests:
1. Expanded caps allow realistic ranges
2. Larger-range solves produce valid strategies
3. Guardrails still reject too-heavy configs
4. Broadway + pair combos work correctly
5. Turn/river with expanded ranges
6. Regression protection for existing scenarios
"""
import pytest
import time
import numpy as np


# ── 1. Cap values are correct after Phase 15A ──

class TestPhase15ACaps:
    """Verify safety limits were raised correctly."""
    
    def test_flop_combo_cap_is_80(self):
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE
        assert MAX_COMBOS_PER_SIDE == 80

    def test_turn_combo_cap_is_50(self):
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE_TURN
        assert MAX_COMBOS_PER_SIDE_TURN == 50

    def test_river_combo_cap_is_30(self):
        from app.solver.cfr_solver import MAX_COMBOS_PER_SIDE_RIVER
        assert MAX_COMBOS_PER_SIDE_RIVER == 30

    def test_total_matchups_cap_is_5000(self):
        from app.solver.cfr_solver import MAX_TOTAL_MATCHUPS
        assert MAX_TOTAL_MATCHUPS == 5000


# ── 2. Realistic range solves work ──

class TestRealisticRangeSolves:
    """Verify realistic ranges produce valid outputs."""
    
    def test_broadway_suited_vs_pairs_flop(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AKs,AQs,AJs,KQs',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
        ))
        assert output.ip_combos > 10
        assert output.oop_combos > 10
        assert output.convergence_metric > 0
        for nid, combos in output.strategies.items():
            for combo, freqs in combos.items():
                assert abs(sum(freqs.values()) - 1.0) < 0.01
    
    def test_realistic_IP_vs_OOP_flop(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs,AKo,AQs',
            oop_range='JJ,TT,99,AJs,KQs,QJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ))
        assert output.ip_combos >= 25
        assert output.oop_combos >= 25
        assert output.convergence_metric > 0
        assert output.convergence_metric < 50
    
    def test_wide_flop_63_combos(self):
        """63-combo IP range — was rejected before Phase 15A (cap was 60)."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK,QQ,JJ,TT,AKs,AKo,AQs,AQo,AJs',
            oop_range='99,88,77,ATs,KQs,KQo,QJs,JTs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
        ))
        assert output.ip_combos >= 60  # was blocked at 60 cap
        assert output.matchups > 2000
        # Strategies valid
        for nid, combos in output.strategies.items():
            for combo, freqs in combos.items():
                assert abs(sum(freqs.values()) - 1.0) < 0.01

    def test_broadway_mixed_vs_pairs_flop(self):
        """Mixed suited/offsuit broadways."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AKs,AKo,AQs,KQs',
            oop_range='JJ,TT,99,88',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ))
        assert output.ip_combos >= 15
        assert output.convergence_metric > 0


# ── 3. Expanded turn/river ranges ──

class TestExpandedTurnRiver:
    """Verify expanded turn/river caps work."""
    
    def test_turn_realistic_ranges_3tc(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs,AKo,AQs',
            oop_range='JJ,TT,99,AJs,KQs,QJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.ip_combos >= 25
        assert output.oop_combos >= 25
        assert output.convergence_metric > 0
        assert output.tree_nodes > 100

    def test_turn_with_47_combos(self):
        """47-combo IP range on turn — was blocked at 40 cap."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK,QQ,JJ,TT,AKs,AKo,AQs',
            oop_range='99,88,77,ATs,KQs,KQo,QJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert output.ip_combos >= 45  # was blocked at 40 cap
        assert output.convergence_metric > 0

    def test_river_with_expanded_ranges(self):
        """River with 18+ combos — was blocked at 20 cap, now 30."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs',
            oop_range='JJ,TT,AJs,KQs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            include_river=True, max_river_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ))
        assert output.ip_combos >= 15
        assert output.oop_combos >= 15
        assert output.convergence_metric > 0


# ── 4. Guardrails still reject too-heavy configs ──

class TestGuardrailsStillWork:
    """Over-limit configs must still be rejected."""
    
    def test_flop_over_80_combos_rejected(self):
        """Very wide range (100+ combos) should be rejected on flop."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        with pytest.raises(ValueError, match="range"):
            solver.solve(SolveRequest(
                board=['Ts', '8h', '3c'],
                ip_range='AA,KK,QQ,JJ,TT,99,88,AKs,AKo,AQs,AQo,AJs,AJo,ATs,KQs,KQo',
                oop_range='77,66,55,44,ATs,A9s,A8s,KJs,KTs,QJs,QTs,JTs,T9s,98s',
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5], raise_sizes=[],
                max_iterations=50, max_raises=0,
            ))
    
    def test_turn_over_50_combos_rejected(self):
        """Wide range on turn (>50 combos) should be rejected."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        with pytest.raises(ValueError, match="range"):
            solver.solve(SolveRequest(
                board=['Ts', '8h', '3c'],
                ip_range='AA,KK,QQ,JJ,TT,AKs,AKo,AQs,AQo,AJs',  # 63 combos > 50
                oop_range='99,88,77,ATs,KQs,KQo,QJs,JTs',
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5], raise_sizes=[],
                max_iterations=50, max_raises=0,
                include_turn=True, max_turn_cards=3,
                turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            ))
    
    def test_river_over_30_combos_rejected(self):
        """Wide range on river (>30 combos) should be rejected."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        with pytest.raises(ValueError, match="range"):
            solver.solve(SolveRequest(
                board=['Ts', '8h', '3c'],
                ip_range='AA,KK,QQ,JJ,TT,AKs,AKo,AQs',  # 47 combos > 30
                oop_range='99,88,77,ATs,KQs,KQo,QJs',
                pot=10.0, effective_stack=50.0,
                bet_sizes=[0.5], raise_sizes=[],
                max_iterations=30, max_raises=0,
                include_turn=True, max_turn_cards=2,
                include_river=True, max_river_cards=1,
                turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
                river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
            ))


# ── 5. Regression protection ──

class TestPhase15ARegression:
    """Existing scenarios must not break."""
    
    def test_toy_AA_vs_KK_still_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'], ip_range='AA', oop_range='KK',
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert output.convergence_metric > 0
        assert output.convergence_metric < 1.0
    
    def test_serial_rust_is_default(self):
        """Verify dispatch still uses serial Rust."""
        from app.solver.cfr_solver import CfrSolver
        import inspect
        source = inspect.getsource(CfrSolver._run_iterations_rust)
        assert 'use_parallel = False' in source
    
    def test_strategies_always_valid(self):
        """All strategies must sum to 1.0 for any solved scenario."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs',
            oop_range='JJ,TT,99,AJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ))
        for nid, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, \
                    f"Strategy at {nid}/{combo} sums to {total}"

    def test_convergence_finite(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AKs,AQs,AJs',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
        ))
        assert not np.isnan(output.convergence_metric)
        assert not np.isinf(output.convergence_metric)
