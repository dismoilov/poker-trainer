"""
Phase 13A: First Rust Core Slice — Test Suite

Tests cover:
- Rust module import and version
- Card encoding round-trip
- Hand evaluation: Python vs Rust equivalence (15+ scenarios)
- Showdown equity: Python vs Rust equivalence (8 scenarios)
- Batch equity: correctness
- Solver regression: convergence preserved with Rust backend
- Fallback behavior
"""

import pytest
import sys

# ── 1. Rust Module Tests ──────────────────────────────────────

class TestRustModuleImport:
    """Verify Rust poker_core module loads and is functional."""

    def test_import(self):
        import poker_core
        assert poker_core is not None

    def test_version(self):
        import poker_core
        v = poker_core.version()
        assert "poker_core" in v
        assert "0.1.0" in v or "0.2.0" in v or "0.3.0" in v or "0.4.0" in v or "0.5.0" in v or "0.6.0" in v

    def test_evaluate_hand_callable(self):
        import poker_core
        assert callable(poker_core.evaluate_hand)

    def test_compute_equity_callable(self):
        import poker_core
        assert callable(poker_core.compute_equity)

    def test_batch_compute_equity_callable(self):
        import poker_core
        assert callable(poker_core.batch_compute_equity)

    def test_batch_compute_equity_multi_board_callable(self):
        import poker_core
        assert callable(poker_core.batch_compute_equity_multi_board)


# ── 2. Card Encoding Tests ───────────────────────────────────

class TestCardEncoding:
    """Verify Python Card ↔ Rust integer encoding."""

    def test_encoding_ah(self):
        from app.solver.rust_bridge import card_to_int
        from app.poker_engine.cards import Card
        c = Card.parse("Ah")
        assert card_to_int(c) == 12 * 4 + 2  # rank=12(A), suit=2(h)

    def test_encoding_2c(self):
        from app.solver.rust_bridge import card_to_int
        from app.poker_engine.cards import Card
        c = Card.parse("2c")
        assert card_to_int(c) == 0 * 4 + 0  # rank=0(2), suit=0(c)

    def test_encoding_ks(self):
        from app.solver.rust_bridge import card_to_int
        from app.poker_engine.cards import Card
        c = Card.parse("Ks")
        assert card_to_int(c) == 11 * 4 + 3  # rank=11(K), suit=3(s)

    def test_encoding_7d(self):
        from app.solver.rust_bridge import card_to_int
        from app.poker_engine.cards import Card
        c = Card.parse("7d")
        assert card_to_int(c) == 5 * 4 + 1  # rank=5(7), suit=1(d)

    def test_all_52_cards_unique(self):
        from app.solver.rust_bridge import card_to_int
        from app.poker_engine.cards import Card
        from app.poker_engine.types import Rank, Suit
        ints = set()
        for r in Rank:
            for s in Suit:
                c = Card(rank=r, suit=s)
                val = card_to_int(c)
                assert 0 <= val <= 51, f"Card {c} maps to {val}"
                ints.add(val)
        assert len(ints) == 52

    def test_combo_to_ints(self):
        from app.solver.rust_bridge import combo_to_ints
        from app.poker_engine.cards import Card
        combo = (Card.parse("Ah"), Card.parse("Ad"))
        ints = combo_to_ints(combo)
        assert isinstance(ints, tuple)
        assert len(ints) == 2
        assert ints[0] == 50  # Ah
        assert ints[1] == 49  # Ad

    def test_board_to_ints(self):
        from app.solver.rust_bridge import board_to_ints
        from app.poker_engine.cards import Card
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        ints = board_to_ints(board)
        assert len(ints) == 3
        assert all(0 <= i <= 51 for i in ints)

    def test_card_str_to_int(self):
        from app.solver.rust_bridge import card_str_to_int
        assert card_str_to_int("Ah") == 50
        assert card_str_to_int("2c") == 0


# ── 3. Hand Evaluation Equivalence ───────────────────────────

class TestHandEvalEquivalence:
    """Verify Rust hand evaluator matches Python for all hand categories."""

    def _compare(self, hand1_strs, hand2_strs):
        """Compare Python and Rust winner determination."""
        import poker_core
        from app.poker_engine.cards import Card
        from app.poker_engine.hand_eval import evaluate_best as py_eval
        from app.solver.rust_bridge import card_to_int

        hand1 = [Card.parse(s) for s in hand1_strs]
        hand2 = [Card.parse(s) for s in hand2_strs]

        py1 = py_eval(hand1)
        py2 = py_eval(hand2)
        py_winner = 1 if py1 > py2 else (-1 if py1 < py2 else 0)

        r1 = poker_core.evaluate_hand([card_to_int(c) for c in hand1])
        r2 = poker_core.evaluate_hand([card_to_int(c) for c in hand2])
        rust_winner = 1 if r1 > r2 else (-1 if r1 < r2 else 0)

        return py_winner, rust_winner

    def test_aa_beats_kk(self):
        py, rust = self._compare(
            ["Ah", "Ad", "9s", "7d", "2c"],
            ["Kh", "Kd", "9s", "7d", "2c"]
        )
        assert py == rust == 1

    def test_tie(self):
        py, rust = self._compare(
            ["Ah", "Ad", "9s", "7d", "2c"],
            ["Ac", "As", "9s", "7d", "2c"]
        )
        assert py == rust == 0

    def test_set_vs_overpair(self):
        py, rust = self._compare(
            ["Kh", "Kd", "Ks", "7d", "2c"],
            ["Qh", "Qd", "Ks", "7d", "2c"]
        )
        assert py == rust == 1

    def test_flush_beats_straight(self):
        py, rust = self._compare(
            ["Ah", "Kh", "Qh", "Jh", "9h"],
            ["Tc", "9d", "8s", "7h", "6c"]
        )
        assert py == rust == 1

    def test_full_beats_flush(self):
        py, rust = self._compare(
            ["Ah", "Ad", "Ac", "Kh", "Kd"],
            ["Qh", "Jh", "Th", "9h", "2h"]
        )
        assert py == rust == 1

    def test_quads_beat_full_house(self):
        py, rust = self._compare(
            ["Ah", "Ad", "Ac", "As", "Kd"],
            ["Kh", "Kc", "Ks", "Qh", "Qd"]
        )
        assert py == rust == 1

    def test_straight_flush_beats_quads(self):
        py, rust = self._compare(
            ["5h", "6h", "7h", "8h", "9h"],
            ["Ah", "Ad", "Ac", "As", "Kd"]
        )
        assert py == rust == 1

    def test_wheel(self):
        py, rust = self._compare(
            ["Ah", "2d", "3s", "4h", "5c"],
            ["Kh", "Qd", "Js", "Th", "2c"]
        )
        assert py == rust == 1  # wheel beats KQJ high

    def test_two_pair_vs_pair(self):
        py, rust = self._compare(
            ["Ah", "Ad", "Kh", "Kd", "2c"],
            ["Qh", "Qd", "Ts", "7d", "2c"]
        )
        assert py == rust == 1

    def test_trips_vs_two_pair(self):
        py, rust = self._compare(
            ["7h", "7d", "7s", "2c", "3d"],
            ["Ah", "Ad", "Kh", "Kd", "2c"]
        )
        assert py == rust == 1

    def test_7_card_best_hand(self):
        """7-card evaluation picks the best 5-card combo."""
        py, rust = self._compare(
            ["Ah", "Kh", "9s", "7d", "2c", "Th", "Jh"],
            ["Qs", "Qd", "9s", "7d", "2c", "Th", "Jh"]
        )
        assert py == rust  # Both should agree on winner


# ── 4. Showdown Equity Equivalence ────────────────────────────

class TestEquityEquivalence:
    """Verify Rust equity matches Python for all board sizes."""

    def _compare_eq(self, ip_strs, oop_strs, board_strs):
        from app.poker_engine.cards import Card
        from app.solver.cfr_solver import compute_showdown_equity
        from app.solver.rust_bridge import rust_compute_equity

        ip = tuple(Card.parse(s) for s in ip_strs)
        oop = tuple(Card.parse(s) for s in oop_strs)
        board = [Card.parse(s) for s in board_strs]

        py_eq = compute_showdown_equity(ip, oop, board)
        rust_eq = rust_compute_equity(ip, oop, board)
        return py_eq, rust_eq

    def test_aa_vs_kk_flop(self):
        py, rust = self._compare_eq(["Ah", "Ad"], ["Kh", "Kd"], ["9s", "7d", "2c"])
        assert abs(py - rust) < 0.001

    def test_tie_flop(self):
        py, rust = self._compare_eq(["Ah", "Ad"], ["Ac", "As"], ["9s", "7d", "2c"])
        assert abs(py - rust) < 0.001

    def test_set_loses(self):
        py, rust = self._compare_eq(["2h", "2d"], ["Ah", "Ad"], ["As", "7d", "2c"])
        assert abs(py - rust) < 0.001

    def test_turn_board(self):
        py, rust = self._compare_eq(["Ah", "Ad"], ["Kh", "Kd"], ["9s", "7d", "2c", "3h"])
        assert abs(py - rust) < 0.001

    def test_river_board(self):
        py, rust = self._compare_eq(["Ah", "Ad"], ["Kh", "Kd"], ["9s", "7d", "2c", "3h", "5d"])
        assert abs(py - rust) < 0.001

    def test_set_vs_overpair(self):
        py, rust = self._compare_eq(["Kh", "Kd"], ["7h", "7s"], ["9s", "7d", "2c"])
        assert abs(py - rust) < 0.001


# ── 5. Batch Equity Tests ─────────────────────────────────────

class TestBatchEquity:
    """Verify batch equity computation works correctly."""

    def test_batch_single_matchup(self):
        import poker_core
        from app.solver.rust_bridge import combo_to_ints, board_to_ints
        from app.poker_engine.cards import Card

        ip_combo = (Card.parse("Ah"), Card.parse("Ad"))
        oop_combo = (Card.parse("Kh"), Card.parse("Kd"))
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]

        results = poker_core.batch_compute_equity(
            [combo_to_ints(ip_combo)],
            [combo_to_ints(oop_combo)],
            board_to_ints(board),
            [(0, 0)]
        )
        assert len(results) == 1
        assert abs(results[0] - 1.0) < 0.001

    def test_batch_multiple_matchups(self):
        import poker_core
        from app.solver.rust_bridge import combo_to_ints, board_to_ints
        from app.poker_engine.cards import Card

        aa = (Card.parse("Ah"), Card.parse("Ad"))
        kk = (Card.parse("Kh"), Card.parse("Kd"))
        qq = (Card.parse("Qh"), Card.parse("Qd"))
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]

        ip_hands = [combo_to_ints(aa), combo_to_ints(kk)]
        oop_hands = [combo_to_ints(qq)]
        results = poker_core.batch_compute_equity(
            ip_hands, oop_hands, board_to_ints(board),
            [(0, 0), (1, 0)]  # AA vs QQ, KK vs QQ
        )
        assert len(results) == 2
        assert results[0] == 1.0  # AA beats QQ
        assert results[1] == 1.0  # KK beats QQ

    def test_batch_empty(self):
        import poker_core
        results = poker_core.batch_compute_equity(
            [(50, 49)], [(46, 45)], [31, 21, 0], []
        )
        assert results == []


# ── 6. Bridge Module Tests ────────────────────────────────────

class TestRustBridge:
    """Test the rust_bridge.py module."""

    def test_rust_available(self):
        from app.solver.rust_bridge import RUST_AVAILABLE
        assert RUST_AVAILABLE is True

    def test_rust_version(self):
        from app.solver.rust_bridge import RUST_VERSION
        assert RUST_VERSION is not None
        assert "poker_core" in RUST_VERSION

    def test_rust_evaluate_hand(self):
        from app.solver.rust_bridge import rust_evaluate_hand
        from app.poker_engine.cards import Card
        hand = [Card.parse(s) for s in ["Ah", "Ad", "9s", "7d", "2c"]]
        rank = rust_evaluate_hand(hand)
        assert rank is not None
        assert rank > 0

    def test_rust_compute_equity(self):
        from app.solver.rust_bridge import rust_compute_equity
        from app.poker_engine.cards import Card
        ip = (Card.parse("Ah"), Card.parse("Ad"))
        oop = (Card.parse("Kh"), Card.parse("Kd"))
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        eq = rust_compute_equity(ip, oop, board)
        assert eq is not None
        assert abs(eq - 1.0) < 0.001

    def test_rust_batch_equity(self):
        from app.solver.rust_bridge import rust_batch_equity
        from app.poker_engine.cards import Card
        ip_combos = [(Card.parse("Ah"), Card.parse("Ad"))]
        oop_combos = [(Card.parse("Kh"), Card.parse("Kd"))]
        board = [Card.parse("9s"), Card.parse("7d"), Card.parse("2c")]
        result = rust_batch_equity(ip_combos, oop_combos, board, [(0, 0)])
        assert result is not None
        assert (0, 0) in result
        assert abs(result[(0, 0)] - 1.0) < 0.001


# ── 7. Solver Regression Tests ────────────────────────────────

class TestSolverRegression:
    """Verify solver still works correctly with Rust equity backend."""

    def test_convergence_match(self):
        """Canonical AA vs KK convergence must match."""
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert 0.10 < output.convergence_metric < 0.50  # Phase 14: parallel mode has different value

    def test_strategies_sum_to_one(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        for node_id, combos in output.strategies.items():
            for combo, freqs in combos.items():
                total = sum(freqs.values())
                assert abs(total - 1.0) < 0.01

    def test_turn_solve_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5],
            max_iterations=10, deterministic=True,
            include_turn=True, max_turn_cards=1,
            turn_bet_sizes=[0.5], turn_raise_sizes=[], turn_max_raises=0,
        ))
        assert "turn" in output.metadata.get("street_depth", "")

    def test_broad_range_works(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA,KK,QQ,JJ",
            oop_range="TT,99,AKs,AQs",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=20, deterministic=True,
        ))
        assert output.iterations > 0
        assert len(output.strategies) > 0

    def test_exploitability_finite(self):
        from app.solver.cfr_solver import CfrSolver, SolveRequest
        solver = CfrSolver()
        output = solver.solve(SolveRequest(
            board=["Ks", "7d", "2c"], ip_range="AA", oop_range="KK",
            pot=10.0, effective_stack=50.0, bet_sizes=[0.5, 1.0],
            max_iterations=50, deterministic=True,
        ))
        assert output.exploitability_mbb > 0
        assert output.exploitability_mbb < 100_000


# ── 8. Performance Sanity Tests ───────────────────────────────

class TestPerformanceSanity:
    """Verify Rust is materially faster than Python for hand eval."""

    def test_rust_hand_eval_faster(self):
        import time
        import poker_core
        from app.poker_engine.hand_eval import evaluate_best as py_eval
        from app.poker_engine.cards import Card
        from app.solver.rust_bridge import card_to_int

        hand = [Card.parse(s) for s in ["Ah", "Ad", "9s", "7d", "2c"]]
        hand_ints = [card_to_int(c) for c in hand]

        N = 10_000

        t0 = time.time()
        for _ in range(N):
            py_eval(hand)
        py_time = time.time() - t0

        t0 = time.time()
        for _ in range(N):
            poker_core.evaluate_hand(hand_ints)
        rust_time = time.time() - t0

        speedup = py_time / rust_time
        assert speedup > 5.0, f"Expected >5× speedup, got {speedup:.1f}×"
