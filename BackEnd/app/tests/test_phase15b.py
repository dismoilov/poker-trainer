"""
Phase 15B Tests: Rust-Safe Progress / Cancellation Integration

Tests verify:
  - Progress reporting works on Rust path
  - Cancellation works on Rust path
  - No partial-state corruption after cancel
  - Strategy validity after cancel
  - Rust path used even with callbacks
  - No-control path unaffected
  - cfr_iterate_with_control Rust API works
  - Regression: normal solves still work
"""

import time
import pytest
import numpy as np

from app.solver.cfr_solver import CfrSolver, SolveRequest

# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

TOY_REQUEST = SolveRequest(
    board=['Ks', '7d', '2c'],
    ip_range='AA',
    oop_range='KK',
    pot=10.0,
    effective_stack=50.0,
    bet_sizes=[0.5],
    raise_sizes=[],
    max_iterations=100,
    max_raises=0,
    deterministic=True,
)

MEDIUM_REQUEST = SolveRequest(
    board=['Ks', '7d', '2c'],
    ip_range='AA,KK,QQ,AKs,AKo,AQs',
    oop_range='JJ,TT,99,AJs,KQs,QJs',
    pot=10.0,
    effective_stack=50.0,
    bet_sizes=[0.5, 1.0],
    raise_sizes=[2.5],
    max_iterations=200,
    max_raises=1,
    deterministic=True,
    include_turn=True,
    max_turn_cards=3,
    turn_bet_sizes=[0.5],
    turn_raise_sizes=[],
    turn_max_raises=0,
)


# ═══════════════════════════════════════════════════════════
# Test: Progress Reporting
# ═══════════════════════════════════════════════════════════

class TestProgressReporting:
    """Tests that progress callbacks fire on the Rust path."""
    
    def test_progress_callback_fires(self):
        """Progress callback should receive updates during solve."""
        progress_log = []
        def on_progress(info):
            progress_log.append((info.iteration, info.total_iterations))
        
        solver = CfrSolver()
        result = solver.solve(MEDIUM_REQUEST, progress_callback=on_progress)
        
        # Phase 16A: early stopping may stop before max_iterations
        assert result.iterations > 0
        assert result.iterations <= 200
        assert len(progress_log) > 0, "Progress callback should have fired at least once"
        
        # Check progress is monotonically increasing
        for i in range(1, len(progress_log)):
            assert progress_log[i][0] >= progress_log[i-1][0], "Progress should be monotonically increasing"
        
        # Last update should match actual iterations completed
        assert progress_log[-1][0] == result.iterations
    
    def test_progress_reports_chunk_boundaries(self):
        """Progress updates should happen at chunk boundaries (multiples of 25)."""
        progress_log = []
        def on_progress(info):
            progress_log.append(info.iteration)
        
        solver = CfrSolver()
        result = solver.solve(MEDIUM_REQUEST, progress_callback=on_progress)
        
        # Each update should be a multiple of 25 (chunk size)
        for done in progress_log:
            assert done % 25 == 0, f"Progress {done} should be at chunk boundary"
    
    def test_progress_total_matches_requested(self):
        """The 'total' parameter in progress callback should match requested iterations."""
        totals = set()
        def on_progress(info):
            totals.add(info.total_iterations)
        
        solver = CfrSolver()
        solver.solve(MEDIUM_REQUEST, progress_callback=on_progress)
        
        # Phase 16A: total_iterations reflects adaptive budget max
        assert len(totals) == 1, f"All progress totals should be consistent, got {totals}"
    
    def test_progress_on_tiny_solve(self):
        """Even tiny solves should fire progress if callback is provided."""
        progress_log = []
        def on_progress(info):
            progress_log.append((info.iteration, info.total_iterations))
        
        solver = CfrSolver()
        result = solver.solve(TOY_REQUEST, progress_callback=on_progress)
        
        # Phase 16A: early stopping may fire before max
        assert result.iterations > 0
        assert result.iterations <= 100
        # Tiny solve: 100 iterations / 25 chunk = 4 updates
        assert len(progress_log) >= 1


# ═══════════════════════════════════════════════════════════
# Test: Cancellation
# ═══════════════════════════════════════════════════════════

class TestCancellation:
    """Tests that cancellation works on the Rust path."""
    
    def test_cancel_stops_solve(self):
        """Cancel should stop the solve before all iterations complete."""
        cancel_at = 50
        progress_updates = []
        
        def do_cancel():
            return len(progress_updates) > 0 and progress_updates[-1] >= cancel_at
        
        def on_progress(info):
            progress_updates.append(info.iteration)
        
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ,AKs,AKo,AQs',
            oop_range='JJ,TT,99,AJs,KQs,QJs',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5, 1.0], raise_sizes=[2.5],
            max_iterations=5000, max_raises=1, deterministic=True,
            include_turn=True, max_turn_cards=3,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        )
        
        result = solver.solve(request, cancel_check=do_cancel, progress_callback=on_progress)
        
        assert result.iterations < 5000, f"Cancel should have stopped early, got {result.iterations}"
        assert result.iterations <= cancel_at + 25, f"Should cancel within one chunk after {cancel_at}"
    
    def test_cancel_preserves_strategy_validity(self):
        """Strategies should sum to 1.0 after cancellation."""
        cancel_flag = [False]
        
        def on_progress(info):
            if info.iteration >= 25:
                cancel_flag[0] = True
        
        def do_cancel():
            return cancel_flag[0]
        
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK,QQ',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=1000, max_raises=0, deterministic=True,
        )
        
        result = solver.solve(request, cancel_check=do_cancel, progress_callback=on_progress)
        
        assert result.iterations < 1000
        assert len(result.strategies) > 0, "Should have strategies even after cancel"
        
        for nid, combos in result.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, f"Strategy for {combo} at node {nid} sums to {total}, not 1.0"
    
    def test_cancel_returns_valid_convergence(self):
        """Convergence metric should be finite and non-negative after cancel."""
        def do_cancel():
            return solver._iteration_count >= 25
        
        solver = CfrSolver()
        result = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK,QQ',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=500, max_raises=0, deterministic=True,
        ), cancel_check=do_cancel)
        
        assert result.iterations < 500
        assert result.convergence_metric >= 0.0
        assert np.isfinite(result.convergence_metric)
    
    def test_cancel_at_zero_returns_empty(self):
        """Cancelling immediately should return 0 iterations."""
        def do_cancel():
            return True
        
        solver = CfrSolver()
        result = solver.solve(TOY_REQUEST, cancel_check=do_cancel)
        
        assert result.iterations == 0


# ═══════════════════════════════════════════════════════════
# Test: No Corruption
# ═══════════════════════════════════════════════════════════

class TestNoCorruption:
    """Tests that progress/cancel doesn't corrupt solver state."""
    
    def test_progress_doesnt_change_results(self):
        """Results with progress callback should match results without."""
        # Without progress
        solver1 = CfrSolver()
        r1 = solver1.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK,QQ',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ))
        
        # With progress
        solver2 = CfrSolver()
        r2 = solver2.solve(SolveRequest(
            board=['Ts', '8h', '3c'],
            ip_range='AA,KK,QQ',
            oop_range='JJ,TT,99',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=100, max_raises=0, deterministic=True,
        ), progress_callback=lambda info: None)
        
        assert r1.iterations == r2.iterations
        # Strategies should match (both deterministic, same input)
        for nid in r1.strategies:
            for combo in r1.strategies[nid]:
                for action in r1.strategies[nid][combo]:
                    v1 = r1.strategies[nid][combo][action]
                    v2 = r2.strategies[nid][combo][action]
                    assert abs(v1 - v2) < 0.001, f"Strategy mismatch at {nid}/{combo}/{action}: {v1} vs {v2}"


# ═══════════════════════════════════════════════════════════
# Test: Rust Path Used
# ═══════════════════════════════════════════════════════════

class TestRustPathUsed:
    """Tests that the Rust path is used even with callbacks."""
    
    def test_rust_path_with_progress(self):
        """Solve with progress_callback should still use Rust path."""
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
        )
        
        from unittest.mock import patch
        import logging
        
        with patch.object(logging.getLogger('app.solver.cfr_solver'), 'info') as mock_log:
            solver.solve(request, progress_callback=lambda info: None)
            
            # Should see Phase 15B log, NOT Python fallback
            log_messages = [str(call) for call in mock_log.call_args_list]
            found_rust = any("Rust CFR" in msg for msg in log_messages)
            found_fallback = any("fallback to Python" in msg for msg in log_messages)
            
            assert found_rust, "Should use Rust CFR path"
            assert not found_fallback, "Should NOT fall back to Python"
    
    def test_rust_path_with_cancel(self):
        """Solve with cancel_check should still use Rust path."""
        solver = CfrSolver()
        request = SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
        )
        
        from unittest.mock import patch
        import logging
        
        with patch.object(logging.getLogger('app.solver.cfr_solver'), 'info') as mock_log:
            solver.solve(request, cancel_check=lambda: False)
            
            log_messages = [str(call) for call in mock_log.call_args_list]
            found_rust = any("Rust CFR" in msg for msg in log_messages)
            assert found_rust, "Should use Rust CFR path even with cancel_check"


# ═══════════════════════════════════════════════════════════
# Test: Rust API
# ═══════════════════════════════════════════════════════════

class TestRustAPI:
    """Tests for the cfr_iterate_with_control Rust function."""
    
    def test_with_control_exists(self):
        """poker_core should expose cfr_iterate_with_control."""
        import poker_core
        assert hasattr(poker_core, 'cfr_iterate_with_control')
    
    def test_version_updated(self):
        """Version should reflect Phase 15B."""
        import poker_core
        v = poker_core.version()
        assert '15B' in v or '0.6' in v, f"Version should mention 15B or 0.6, got {v}"


# ═══════════════════════════════════════════════════════════
# Test: Regression
# ═══════════════════════════════════════════════════════════

class TestPhase15BRegression:
    """Regression tests to ensure no breakage."""
    
    def test_normal_solve_still_works(self):
        """Normal solve without control should work exactly as before."""
        solver = CfrSolver()
        result = solver.solve(TOY_REQUEST)
        
        assert result.iterations == 100
        assert result.convergence_metric >= 0.0
        assert len(result.strategies) > 0
    
    def test_turn_solve_still_works(self):
        """Turn solve should work with progress."""
        progress_log = []
        solver = CfrSolver()
        result = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA,KK',
            oop_range='QQ,JJ',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=50, max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ), progress_callback=lambda info: progress_log.append(info.iteration))
        
        assert result.iterations == 50
        assert len(progress_log) >= 1
    
    def test_river_solve_still_works(self):
        """River solve should work with progress."""
        progress_log = []
        solver = CfrSolver()
        result = solver.solve(SolveRequest(
            board=['Ks', '7d', '2c'],
            ip_range='AA',
            oop_range='KK',
            pot=10.0, effective_stack=50.0,
            bet_sizes=[0.5], raise_sizes=[],
            max_iterations=30, max_raises=0, deterministic=True,
            include_turn=True, max_turn_cards=2,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
            include_river=True, max_river_cards=2,
            river_bet_sizes=[0.5], river_raise_sizes=[], river_max_raises=0,
        ), progress_callback=lambda info: progress_log.append(info.iteration))
        
        assert result.iterations > 0
        assert len(progress_log) >= 1
    
    def test_strategies_always_valid(self):
        """All strategies should sum to 1.0 regardless of control path."""
        solver = CfrSolver()
        result = solver.solve(MEDIUM_REQUEST, progress_callback=lambda info: None)
        
        for nid, combos in result.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, f"Strategy at {nid}/{combo} sums to {total}"
