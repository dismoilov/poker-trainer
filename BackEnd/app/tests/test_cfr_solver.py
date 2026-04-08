"""
Tests for the real CFR+ solver engine.

These verify that the solver produces genuine, mathematically valid results.
"""

import pytest
from app.solver.cfr_solver import (
    CfrSolver,
    SolveRequest,
    SolveOutput,
    expand_range_to_combos,
    combo_to_str,
    compute_showdown_equity,
    validate_solve_request,
    MAX_TREE_NODES_FLOP,
    MAX_COMBOS_PER_SIDE,
)
from app.poker_engine.cards import Card


# ── Combo expansion tests ──────────────────────────────────────

class TestComboExpansion:
    """Tests for expanding range notation into concrete card combos."""

    def test_pair_expansion(self):
        """AA should expand to 6 combos (C(4,2))."""
        board = [Card.parse("Ks"), Card.parse("7d"), Card.parse("2c")]
        combos = expand_range_to_combos("AA", board)
        assert len(combos) == 6  # No board blockers

    def test_pair_with_blocker(self):
        """KK with a K on the board should have fewer combos."""
        board = [Card.parse("Ks"), Card.parse("7d"), Card.parse("2c")]
        combos = expand_range_to_combos("KK", board)
        assert len(combos) == 3  # Only 3 remaining K's → C(3,2) = 3

    def test_suited_expansion(self):
        """AKs should expand to 4 suited combos."""
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        combos = expand_range_to_combos("AKs", board)
        assert len(combos) == 4  # 4 suits

    def test_suited_with_blocker(self):
        """AKs with As on the board should have 3 combos."""
        board = [Card.parse("As"), Card.parse("7d"), Card.parse("2c")]
        combos = expand_range_to_combos("AKs", board)
        assert len(combos) == 3  # spade suit blocked

    def test_offsuit_expansion(self):
        """AKo should expand to 12 offsuit combos."""
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        combos = expand_range_to_combos("AKo", board)
        assert len(combos) == 12

    def test_range_combo_no_overlap(self):
        """No combo should contain board cards."""
        board = [Card.parse("Ks"), Card.parse("Qd"), Card.parse("2c")]
        combos = expand_range_to_combos("KK,QQ", board)
        board_cards_set = {(c.rank.value, c.suit.value) for c in board}
        for c1, c2 in combos:
            assert (c1.rank.value, c1.suit.value) not in board_cards_set
            assert (c2.rank.value, c2.suit.value) not in board_cards_set

    def test_combo_to_str(self):
        c1 = Card.parse("Ah")
        c2 = Card.parse("Kh")
        assert combo_to_str((c1, c2)) == "AhKh"


# ── Showdown equity tests ─────────────────────────────────────

class TestShowdownEquity:
    """Tests for showdown equity computation."""

    def test_better_hand_wins(self):
        """AA vs KK on a neutral board → AA wins."""
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        ip = (Card.parse("Ah"), Card.parse("Ad"))
        oop = (Card.parse("Kh"), Card.parse("Kd"))
        eq = compute_showdown_equity(ip, oop, board)
        assert eq == 1.0

    def test_worse_hand_loses(self):
        """KK vs AA → KK loses (equity = 0)."""
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        ip = (Card.parse("Kh"), Card.parse("Kd"))
        oop = (Card.parse("Ah"), Card.parse("Ad"))
        eq = compute_showdown_equity(ip, oop, board)
        assert eq == 0.0

    def test_tie(self):
        """Same hand rank → tie (equity = 0.5)."""
        board = [Card.parse("As"), Card.parse("Ks"), Card.parse("Qs"),
                 Card.parse("Js"), Card.parse("Ts")]
        ip = (Card.parse("2h"), Card.parse("3h"))
        oop = (Card.parse("2d"), Card.parse("3d"))
        eq = compute_showdown_equity(ip, oop, board)
        assert eq == 0.5


# ── Regret matching tests ─────────────────────────────────────

class TestRegretMatching:
    """Tests for CFR+ regret-matching correctness."""

    def test_uniform_with_no_regrets(self):
        solver = CfrSolver()
        strategy = solver._get_current_strategy("test_key", ("fold", "call", "raise"))
        assert abs(strategy["fold"] - 1/3) < 0.001
        assert abs(strategy["call"] - 1/3) < 0.001
        assert abs(strategy["raise"] - 1/3) < 0.001

    def test_positive_regrets_weight(self):
        """Phase 12D: Uses array backend."""
        from app.solver.cfr_solver import SolverArrays
        solver = CfrSolver()
        solver._arrays = SolverArrays(1, 3)
        solver._info_set_map = {"test": 0}
        solver._info_set_actions = {0: ("fold", "call", "raise")}
        solver._arrays.regrets[0] = 0.0   # fold
        solver._arrays.regrets[1] = 10.0  # call
        solver._arrays.regrets[2] = 0.0   # raise
        strategy = solver._get_current_strategy("test", ("fold", "call", "raise"))
        assert strategy["call"] == 1.0
        assert strategy["fold"] == 0.0
        assert strategy["raise"] == 0.0

    def test_mixed_regrets(self):
        """Phase 12D: Uses array backend."""
        from app.solver.cfr_solver import SolverArrays
        solver = CfrSolver()
        solver._arrays = SolverArrays(1, 2)
        solver._info_set_map = {"test": 0}
        solver._info_set_actions = {0: ("fold", "call")}
        solver._arrays.regrets[0] = 2.0  # fold
        solver._arrays.regrets[1] = 8.0  # call
        strategy = solver._get_current_strategy("test", ("fold", "call"))
        assert abs(strategy["fold"] - 0.2) < 0.001
        assert abs(strategy["call"] - 0.8) < 0.001

    def test_strategy_sums_to_one(self):
        """Phase 12D: Uses array backend."""
        from app.solver.cfr_solver import SolverArrays
        solver = CfrSolver()
        solver._arrays = SolverArrays(1, 3)
        solver._info_set_map = {"test": 0}
        solver._info_set_actions = {0: ("a", "b", "c")}
        solver._arrays.regrets[0] = 3.0
        solver._arrays.regrets[1] = 5.0
        solver._arrays.regrets[2] = 2.0
        strategy = solver._get_current_strategy("test", ("a", "b", "c"))
        total = sum(strategy.values())
        assert abs(total - 1.0) < 0.0001


# ── Average strategy tests ────────────────────────────────────

class TestAverageStrategy:
    """Tests for strategy accumulation and averaging."""

    def test_accumulate_and_average(self):
        """Phase 12D: Uses array backend."""
        from app.solver.cfr_solver import SolverArrays
        solver = CfrSolver()
        solver._arrays = SolverArrays(1, 2)
        solver._info_set_map = {"k": 0}
        solver._info_set_actions = {0: ("fold", "call")}
        solver._use_arrays = True
        # Accumulate two strategy samples
        solver._accumulate_strategy("k", {"fold": 0.5, "call": 0.5}, 1.0)
        solver._accumulate_strategy("k", {"fold": 0.0, "call": 1.0}, 1.0)
        avg = solver._get_average_strategy("k", ["fold", "call"])
        assert abs(avg["fold"] - 0.25) < 0.001
        assert abs(avg["call"] - 0.75) < 0.001

    def test_weighted_accumulation(self):
        """Phase 12D: Uses array backend."""
        from app.solver.cfr_solver import SolverArrays
        solver = CfrSolver()
        solver._arrays = SolverArrays(1, 2)
        solver._info_set_map = {"k": 0}
        solver._info_set_actions = {0: ("a", "b")}
        solver._use_arrays = True
        solver._accumulate_strategy("k", {"a": 1.0, "b": 0.0}, 3.0)
        solver._accumulate_strategy("k", {"a": 0.0, "b": 1.0}, 1.0)
        avg = solver._get_average_strategy("k", ["a", "b"])
        assert abs(avg["a"] - 0.75) < 0.001
        assert abs(avg["b"] - 0.25) < 0.001


# ── Full solve tests ──────────────────────────────────────────

class TestRealSolve:
    """Tests that the full solve pipeline works correctly."""

    def test_tiny_solve_completes(self):
        """A micro solve with 2 hands per side should complete."""
        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[2.5],
            max_iterations=20,
            max_raises=1,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert isinstance(output, SolveOutput)
        assert output.iterations == 20
        assert output.tree_nodes > 0
        assert output.ip_combos > 0
        assert output.oop_combos > 0
        assert output.matchups > 0
        assert output.elapsed_seconds >= 0
        assert len(output.strategies) > 0
        assert output.metadata["algorithm"] == "CFR+ (Tammelin 2014)"

    def test_strategies_are_valid_probabilities(self):
        """All strategies should be valid probability distributions."""
        request = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ,JJ",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[0.5],
            raise_sizes=[],
            max_iterations=30,
            max_raises=1,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        for node_id, combos in output.strategies.items():
            for combo_str, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01, (
                    f"Strategy at node={node_id}, combo={combo_str} "
                    f"sums to {total}, not 1.0"
                )
                for action, freq in freqs.items():
                    assert freq >= -0.001, (
                        f"Negative freq at {node_id}/{combo_str}/{action}: {freq}"
                    )

    def test_convergence_decreases(self):
        """Convergence metric should generally decrease with more iterations."""
        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=10,
            max_raises=1,
        )
        solver1 = CfrSolver()
        out1 = solver1.solve(request)

        request2 = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=100,
            max_raises=1,
        )
        solver2 = CfrSolver()
        out2 = solver2.solve(request2)

        # More iterations should lead to same or better convergence
        assert out2.convergence_metric <= out1.convergence_metric + 0.01

    def test_progress_callback(self):
        """Progress callback should be called during solving."""
        progress_calls = []

        def on_progress(info):
            progress_calls.append(info.iteration)

        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=20,
            max_raises=1,
        )
        solver = CfrSolver()
        solver.solve(request, progress_callback=on_progress)

        assert len(progress_calls) > 0
        assert 20 in progress_calls  # Should report on last iteration

    def test_cancellation(self):
        """Solve should stop early when cancel is requested."""
        cancel_at = [15]

        def check_cancel():
            return cancel_at[0] <= 0

        def on_progress(info):
            cancel_at[0] -= 1

        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=1000,
            max_raises=1,
        )
        solver = CfrSolver()
        output = solver.solve(request, on_progress, check_cancel)
        assert output.iterations < 1000


# ── Validation tests ──────────────────────────────────────────

class TestValidation:
    """Tests for solve request validation."""

    def test_valid_request(self):
        req = SolveRequest(
            board=["Ks", "7d", "2c"],
            ip_range="AA,KK",
            oop_range="QQ",
            max_iterations=50,
        )
        valid, error = validate_solve_request(req)
        assert valid
        assert error == ""

    def test_too_few_board_cards(self):
        req = SolveRequest(board=["Ks", "7d"], ip_range="AA", oop_range="KK")
        valid, error = validate_solve_request(req)
        assert not valid
        assert "3 board cards" in error.lower() or "at least" in error.lower()

    def test_invalid_range(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="XZ$", oop_range="KK")
        valid, error = validate_solve_request(req)
        assert not valid

    def test_duplicate_board_cards(self):
        req = SolveRequest(board=["Ks", "Ks", "2c"], ip_range="AA", oop_range="KK")
        valid, error = validate_solve_request(req)
        assert not valid
        assert "duplicate" in error.lower()

    def test_empty_range(self):
        req = SolveRequest(board=["Ks", "7d", "2c"], ip_range="", oop_range="KK")
        valid, error = validate_solve_request(req)
        assert not valid


# ── Provider integration tests ────────────────────────────────

class TestProviderIntegration:
    """Tests that the real solver provider works via the provider interface."""

    def test_real_provider_type(self):
        from app.solver.real_provider import RealSolverProvider
        from app.solver.base import ProviderType
        provider = RealSolverProvider()
        assert provider.provider_type == ProviderType.REAL_SOLVER
        assert provider.supports_iterative is True

    def test_real_provider_no_longer_raises(self):
        """The real provider should NOT raise NotImplementedError anymore."""
        from app.solver.real_provider import RealSolverProvider
        from app.solver.base import SolveConfig
        provider = RealSolverProvider()
        config = SolveConfig(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            ip_stack=97.0,
            oop_stack=97.0,
            allowed_bet_sizes=[1.0],
            allowed_raise_sizes=[],
            max_iterations=10,
        )
        # This should NOT raise NotImplementedError
        strategy = provider.generate_strategy("node_0", [], config)
        assert isinstance(strategy, dict)

    def test_heuristic_provider_still_works(self):
        """Existing heuristic provider should remain functional."""
        from app.solver.heuristic_provider import HeuristicProvider
        from app.solver.base import ProviderType
        provider = HeuristicProvider()
        assert provider.provider_type == ProviderType.HEURISTIC
        strategy = provider.generate_strategy("test_node", [
            {"id": "check", "label": "Check", "type": "check"},
            {"id": "bet_50", "label": "Bet 50%", "type": "bet"},
        ])
        assert isinstance(strategy, dict)
        assert len(strategy) > 0


# ── Solve output structure tests ──────────────────────────────

class TestSolveOutputStructure:
    """Tests for the shape and metadata of solve outputs."""

    def test_metadata_fields(self):
        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            pot=6.5,
            effective_stack=97.0,
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=10,
            max_raises=1,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert "algorithm" in output.metadata
        assert "scope" in output.metadata
        assert "honest_note" in output.metadata
        assert "board" in output.metadata
        assert output.metadata["algorithm"] == "CFR+ (Tammelin 2014)"
        assert "flop" in output.metadata["scope"].lower()

    def test_output_has_all_fields(self):
        request = SolveRequest(
            board=["9s", "7d", "2c"],
            ip_range="AA",
            oop_range="KK",
            bet_sizes=[1.0],
            raise_sizes=[],
            max_iterations=5,
            max_raises=1,
        )
        solver = CfrSolver()
        output = solver.solve(request)

        assert output.iterations > 0
        assert output.tree_nodes > 0
        assert output.ip_combos > 0
        assert output.oop_combos > 0
        assert output.matchups > 0
        assert output.elapsed_seconds >= 0
        assert isinstance(output.convergence_metric, float)
        assert isinstance(output.converged, bool)
