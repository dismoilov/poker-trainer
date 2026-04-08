"""
Phase 2 engine tests: multi-street transitions, board advancement,
pot/stack accounting, and tree builder.
"""

import pytest
from app.poker_engine.cards import Card
from app.poker_engine.deck import Deck
from app.poker_engine.state import GameState, create_initial_state
from app.poker_engine.transitions import apply_action
from app.poker_engine.actions import get_legal_actions, PokerAction
from app.poker_engine.types import ActionType, Position, Street
from app.poker_engine.hand_eval import evaluate_best, HandRank


class TestMultiStreetTransitions:
    """Test that betting across multiple streets works correctly."""

    def _make_state(self, street=Street.FLOP) -> GameState:
        deck = Deck()
        deck.shuffle()
        return create_initial_state(
            ip_stack=97.0, oop_stack=97.0, pot=6.5,
            board=deck.deal(3), ip_hand=deck.deal(2),
            oop_hand=deck.deal(2), street=street,
        )

    def test_check_check_advances_to_turn(self):
        state = self._make_state()
        assert state.street == Street.FLOP

        # OOP checks
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))
        # IP checks
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))

        assert state.street == Street.TURN
        assert not state.is_terminal
        assert state.current_player == Position.OOP

    def test_check_check_turn_advances_to_river(self):
        state = self._make_state(Street.TURN)
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))

        assert state.street == Street.RIVER
        assert not state.is_terminal

    def test_check_check_river_is_showdown(self):
        state = self._make_state(Street.RIVER)
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))
        state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))

        assert state.is_terminal
        assert state.is_showdown

    def test_full_three_street_check_through(self):
        """Check through all three streets → showdown."""
        state = self._make_state()

        for _ in range(3):  # flop, turn, river
            state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))
            state = apply_action(state, PokerAction(type=ActionType.CHECK, amount=0))

        assert state.is_terminal
        assert state.is_showdown

    def test_bet_call_advances_street(self):
        state = self._make_state()
        # OOP bets
        state = apply_action(state, PokerAction(type=ActionType.BET, amount=4.0))
        # IP calls
        state = apply_action(state, PokerAction(type=ActionType.CALL, amount=4.0))

        assert state.street == Street.TURN
        assert state.pot == 14.5  # 6.5 + 4 + 4
        assert not state.is_terminal


class TestPotStackAccounting:
    """Verify pot and stack math across actions."""

    def _make_state(self) -> GameState:
        deck = Deck()
        deck.shuffle()
        return create_initial_state(
            ip_stack=97.0, oop_stack=97.0, pot=6.5,
            board=deck.deal(3), ip_hand=deck.deal(2),
            oop_hand=deck.deal(2), street=Street.FLOP,
        )

    def test_bet_increases_pot(self):
        state = self._make_state()
        state = apply_action(state, PokerAction(type=ActionType.BET, amount=5.0))
        assert state.pot == 11.5  # 6.5 + 5
        assert state.stacks[Position.OOP] == 92.0  # 97 - 5

    def test_bet_call_pot_correct(self):
        state = self._make_state()
        state = apply_action(state, PokerAction(type=ActionType.BET, amount=5.0))
        state = apply_action(state, PokerAction(type=ActionType.CALL, amount=5.0))
        assert state.pot == 16.5  # 6.5 + 5 + 5
        assert state.stacks[Position.OOP] == 92.0
        assert state.stacks[Position.IP] == 92.0

    def test_fold_preserves_pot(self):
        state = self._make_state()
        state = apply_action(state, PokerAction(type=ActionType.BET, amount=5.0))
        state = apply_action(state, PokerAction(type=ActionType.FOLD, amount=0))
        assert state.pot == 11.5
        assert state.is_terminal
        assert state.winner == Position.OOP

    def test_stacks_sum_with_pot(self):
        """Total chips should always equal starting total."""
        state = self._make_state()
        total_start = state.stacks[Position.IP] + state.stacks[Position.OOP] + state.pot

        # Bet + Call
        state = apply_action(state, PokerAction(type=ActionType.BET, amount=5.0))
        state = apply_action(state, PokerAction(type=ActionType.CALL, amount=5.0))

        total_now = state.stacks[Position.IP] + state.stacks[Position.OOP] + state.pot
        assert abs(total_start - total_now) < 0.01


class TestVillainPolicy:
    """Test heuristic villain action selection."""

    def test_choose_returns_valid_action(self):
        from app.game_sessions.villain_policy import choose_villain_action
        from app.poker_engine.cards import Card
        from app.poker_engine.types import Rank, Suit

        hand = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.SPADES)]
        board = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.DIAMONDS),
            Card(Rank.TWO, Suit.CLUBS),
        ]
        legal = [
            PokerAction(type=ActionType.CHECK, amount=0),
            PokerAction(type=ActionType.BET, amount=4.0),
        ]
        action = choose_villain_action(legal, hand, board, pot=6.5, facing_bet=0)
        assert action in legal

    def test_monster_hand_prefers_aggression(self):
        """With a monster hand, villain should bet/raise more than fold."""
        from app.game_sessions.villain_policy import choose_villain_action
        from app.poker_engine.cards import Card
        from app.poker_engine.types import Rank, Suit

        hand = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.SPADES)]
        board = [
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.TWO, Suit.CLUBS),
        ]
        legal = [
            PokerAction(type=ActionType.CHECK, amount=0),
            PokerAction(type=ActionType.BET, amount=4.0),
            PokerAction(type=ActionType.BET, amount=6.5),
        ]

        # Run many times; with quads, should heavily prefer betting
        import collections
        results = collections.Counter()
        for _ in range(200):
            action = choose_villain_action(legal, hand, board, pot=6.5, facing_bet=0)
            results[action.type.value] += 1

        # With quads (tier 5), aggressive should dominate
        assert results.get("bet", 0) > results.get("check", 0) * 0.5

    def test_weak_hand_folds_to_big_bet(self):
        """With air, villain should fold more when facing a big bet."""
        from app.game_sessions.villain_policy import choose_villain_action
        from app.poker_engine.cards import Card
        from app.poker_engine.types import Rank, Suit

        hand = [Card(Rank.TWO, Suit.HEARTS), Card(Rank.THREE, Suit.SPADES)]
        board = [
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.QUEEN, Suit.DIAMONDS),
            Card(Rank.JACK, Suit.CLUBS),
        ]
        legal = [
            PokerAction(type=ActionType.FOLD, amount=0),
            PokerAction(type=ActionType.CALL, amount=10.0),
        ]

        import collections
        results = collections.Counter()
        for _ in range(200):
            action = choose_villain_action(legal, hand, board, pot=6.5, facing_bet=10.0)
            results[action.type.value] += 1

        # With 2-3 on KQJ (air, tier 0), fold should be common
        assert results.get("fold", 0) > results.get("call", 0)


class TestTreeBuilder:
    """Test game tree scaffold builder."""

    def test_basic_tree(self):
        from app.solver.tree_builder import TreeConfig, build_tree_skeleton

        config = TreeConfig(starting_pot=6.5, effective_stack=97.0)
        root, stats = build_tree_skeleton(config)

        assert stats.total_nodes > 0
        assert stats.action_nodes > 0
        assert stats.terminal_nodes > 0
        assert stats.max_depth > 0
        assert root.node_id == "node_0"
        assert root.player == "OOP"

    def test_tree_with_ranges(self):
        from app.solver.tree_builder import TreeConfig, build_tree_skeleton

        config = TreeConfig(
            ip_range_str="AA,KK,QQ,AKs",
            oop_range_str="TT+,AQs+",
            starting_pot=6.5,
            effective_stack=97.0,
        )
        _, stats = build_tree_skeleton(config)

        assert stats.ip_range_combos > 0
        assert stats.oop_range_combos > 0
        assert stats.total_nodes > 10

    def test_tree_node_types(self):
        from app.solver.tree_builder import TreeConfig, build_tree_skeleton, NodeType

        config = TreeConfig(starting_pot=6.5, effective_stack=50.0)
        root, stats = build_tree_skeleton(config)

        assert root.node_type == NodeType.ACTION
        # Should have terminal children (fold nodes, showdown nodes)
        has_terminal = any(
            c.node_type == NodeType.TERMINAL
            for c in root.children.values()
        ) or stats.terminal_nodes > 0
        assert has_terminal
