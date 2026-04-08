"""
Tests for the solver abstraction layer — provider interface, heuristic, and real scaffold.
"""

import pytest
from app.solver.base import StrategyProvider, ProviderType, SolveConfig
from app.solver.heuristic_provider import HeuristicProvider, get_default_provider
from app.solver.real_provider import RealSolverProvider


# ── Heuristic Provider Tests ──

class TestHeuristicProvider:
    def test_provider_type(self):
        p = HeuristicProvider()
        assert p.provider_type == ProviderType.HEURISTIC

    def test_not_iterative(self):
        p = HeuristicProvider()
        assert p.supports_iterative is False

    def test_generate_strategy_returns_matrix(self):
        p = HeuristicProvider()
        actions = [
            {"id": "check", "label": "Check", "type": "check"},
            {"id": "bet33", "label": "Bet 33%", "type": "bet", "size": 33},
            {"id": "bet75", "label": "Bet 75%", "type": "bet", "size": 75},
        ]
        matrix = p.generate_strategy("test-node-1", actions)
        assert isinstance(matrix, dict)
        assert len(matrix) == 169  # 13x13 hand matrix
        # Each hand should have frequencies for all actions
        for hand, freqs in matrix.items():
            assert len(freqs) == 3
            total = sum(freqs.values())
            assert abs(total - 1.0) < 0.01  # normalized

    def test_deterministic_output(self):
        """Same inputs → same output (deterministic jitter)."""
        p = HeuristicProvider()
        actions = [
            {"id": "check", "label": "Check", "type": "check"},
            {"id": "bet33", "label": "Bet 33%", "type": "bet", "size": 33},
        ]
        m1 = p.generate_strategy("node-x", actions)
        m2 = p.generate_strategy("node-x", actions)
        assert m1 == m2

    def test_default_provider_singleton(self):
        p1 = get_default_provider()
        p2 = get_default_provider()
        assert p1 is p2

    def test_generate_with_config(self):
        p = HeuristicProvider()
        config = SolveConfig(board=["Ks", "7d", "2c"])
        actions = [
            {"id": "fold", "label": "Fold", "type": "fold"},
            {"id": "call", "label": "Call", "type": "call"},
            {"id": "raise", "label": "Raise", "type": "raise"},
        ]
        matrix = p.generate_strategy("test-node-2", actions, config=config)
        assert len(matrix) == 169


# ── Real Provider Tests ──

class TestRealSolverProvider:
    def test_provider_type(self):
        p = RealSolverProvider()
        assert p.provider_type == ProviderType.REAL_SOLVER

    def test_is_iterative(self):
        p = RealSolverProvider()
        assert p.supports_iterative is True

    def test_generate_requires_config(self):
        """Real solver requires SolveConfig (no longer a scaffold)."""
        p = RealSolverProvider()
        with pytest.raises(ValueError, match="requires a SolveConfig"):
            p.generate_strategy("node", [{"id": "check"}])

    def test_cancel(self):
        p = RealSolverProvider()
        p.cancel()
        progress = p.get_progress()
        assert progress.cancelled is True

    def test_progress_default(self):
        p = RealSolverProvider()
        progress = p.get_progress()
        assert progress.iterations_done == 0
        assert not progress.converged


# ── Interface Compliance Tests ──

class TestInterfaceCompliance:
    """Verify both providers implement the StrategyProvider interface."""

    @pytest.mark.parametrize("provider_cls", [HeuristicProvider, RealSolverProvider])
    def test_is_strategy_provider(self, provider_cls):
        p = provider_cls()
        assert isinstance(p, StrategyProvider)

    @pytest.mark.parametrize("provider_cls", [HeuristicProvider, RealSolverProvider])
    def test_has_provider_type(self, provider_cls):
        p = provider_cls()
        assert isinstance(p.provider_type, ProviderType)

    @pytest.mark.parametrize("provider_cls", [HeuristicProvider, RealSolverProvider])
    def test_has_supports_iterative(self, provider_cls):
        p = provider_cls()
        assert isinstance(p.supports_iterative, bool)
