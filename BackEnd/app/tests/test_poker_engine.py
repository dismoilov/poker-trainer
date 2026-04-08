"""
Tests for the poker engine — cards, deck, legal actions, state transitions,
hand evaluation, and showdown.
"""

import pytest
from app.poker_engine.cards import Card, parse_cards
from app.poker_engine.deck import Deck
from app.poker_engine.types import Rank, Suit, Street, ActionType, Position, HandCategory
from app.poker_engine.actions import get_legal_actions, PokerAction
from app.poker_engine.state import create_initial_state, GameState
from app.poker_engine.transitions import apply_action
from app.poker_engine.hand_eval import evaluate_5, evaluate_best, HandRank
from app.poker_engine.showdown import determine_winner


# ── Card Tests ──

class TestCard:
    def test_parse_valid(self):
        c = Card.parse("Ah")
        assert c.rank == Rank.ACE
        assert c.suit == Suit.HEARTS

    def test_parse_ten(self):
        c = Card.parse("Ts")
        assert c.rank == Rank.TEN
        assert c.suit == Suit.SPADES

    def test_parse_invalid_rank(self):
        with pytest.raises(ValueError, match="Invalid rank"):
            Card.parse("Xh")

    def test_parse_invalid_suit(self):
        with pytest.raises(ValueError, match="Invalid suit"):
            Card.parse("Ax")

    def test_parse_invalid_length(self):
        with pytest.raises(ValueError, match="must be 2 chars"):
            Card.parse("A")

    def test_str_roundtrip(self):
        for s in ["Ah", "2c", "Td", "Ks"]:
            assert str(Card.parse(s)) == s

    def test_equality(self):
        assert Card.parse("Ah") == Card.parse("Ah")
        assert Card.parse("Ah") != Card.parse("As")

    def test_comparison(self):
        assert Card.parse("Ah") > Card.parse("Kh")
        assert Card.parse("2c") < Card.parse("3c")

    def test_parse_cards(self):
        cards = parse_cards(["Ah", "Ks", "Td"])
        assert len(cards) == 3
        assert cards[0].rank == Rank.ACE


# ── Deck Tests ──

class TestDeck:
    def test_full_deck(self):
        d = Deck()
        assert len(d) == 52

    def test_deal(self):
        d = Deck()
        cards = d.deal(5)
        assert len(cards) == 5
        assert d.remaining == 47

    def test_deal_one(self):
        d = Deck()
        c = d.deal_one()
        assert isinstance(c, Card)
        assert d.remaining == 51

    def test_deal_too_many(self):
        d = Deck()
        with pytest.raises(ValueError, match="Cannot deal"):
            d.deal(53)

    def test_shuffle_deterministic(self):
        d1 = Deck(seed=42)
        d1.shuffle()
        d2 = Deck(seed=42)
        d2.shuffle()
        assert d1.deal(5) == d2.deal(5)

    def test_remove(self):
        d = Deck()
        to_remove = [Card.parse("Ah"), Card.parse("Ks")]
        d.remove(to_remove)
        assert d.remaining == 50

    def test_unique_cards(self):
        d = Deck()
        all_cards = d.deal(52)
        assert len(set(all_cards)) == 52


# ── Legal Action Tests ──

class TestLegalActions:
    def test_no_bet_facing(self):
        """When no bet is facing, player can check and bet."""
        actions = get_legal_actions(pot=10, facing_bet=0, player_stack=100,
                                     min_raise_to=0, can_check=True)
        types = {a.type for a in actions}
        assert ActionType.CHECK in types
        assert ActionType.BET in types
        assert ActionType.FOLD not in types

    def test_facing_bet(self):
        """When facing a bet, player can fold, call, raise, or allin."""
        actions = get_legal_actions(pot=10, facing_bet=5, player_stack=100,
                                     min_raise_to=10, can_check=False)
        types = {a.type for a in actions}
        assert ActionType.FOLD in types
        assert ActionType.CALL in types
        assert ActionType.RAISE in types

    def test_short_stack_call_allin(self):
        """Very short stack can only call all-in."""
        actions = get_legal_actions(pot=20, facing_bet=15, player_stack=10,
                                     min_raise_to=30, can_check=False)
        types = {a.type for a in actions}
        assert ActionType.FOLD in types
        assert ActionType.ALLIN in types
        assert ActionType.CALL not in types  # stack < facing_bet

    def test_empty_stack(self):
        """Player with no stack gets no actions."""
        actions = get_legal_actions(pot=20, facing_bet=0, player_stack=0,
                                     min_raise_to=0, can_check=True)
        assert len(actions) == 0


# ── State Tests ──

class TestGameState:
    def _make_state(self) -> GameState:
        board = parse_cards(["Ks", "7d", "2c"])
        return create_initial_state(
            ip_stack=97.0, oop_stack=97.0, pot=6.5,
            board=board,
            ip_hand=parse_cards(["Ah", "Kh"]),
            oop_hand=parse_cards(["Qd", "Jd"]),
        )

    def test_initial_state(self):
        s = self._make_state()
        assert s.street == Street.FLOP
        assert s.current_player == Position.OOP
        assert s.pot == 6.5
        assert not s.is_terminal
        assert len(s.board) == 3

    def test_effective_stack(self):
        s = self._make_state()
        assert s.effective_stack == 97.0


# ── Transition Tests ──

class TestTransitions:
    def _make_state(self) -> GameState:
        board = parse_cards(["Ks", "7d", "2c"])
        return create_initial_state(
            ip_stack=97.0, oop_stack=97.0, pot=6.5,
            board=board,
            ip_hand=parse_cards(["Ah", "Kh"]),
            oop_hand=parse_cards(["Qd", "Jd"]),
        )

    def test_fold(self):
        s = self._make_state()
        s2 = apply_action(s, PokerAction(ActionType.FOLD))
        assert s2.is_terminal
        assert s2.winner == Position.IP
        assert s2.folded_player == Position.OOP

    def test_check_check_advances_street(self):
        s = self._make_state()
        # OOP checks
        s2 = apply_action(s, PokerAction(ActionType.CHECK))
        assert not s2.is_terminal
        assert s2.current_player == Position.IP
        # IP checks → should advance to turn
        s3 = apply_action(s2, PokerAction(ActionType.CHECK))
        assert s3.street == Street.TURN

    def test_bet_call(self):
        s = self._make_state()
        # OOP bets 3.3
        s2 = apply_action(s, PokerAction(ActionType.BET, amount=3.3))
        assert s2.pot == 6.5 + 3.3
        assert s2.stacks[Position.OOP] == 97.0 - 3.3
        assert s2.current_player == Position.IP
        # IP calls → advance street
        s3 = apply_action(s2, PokerAction(ActionType.CALL, amount=3.3))
        assert s3.street == Street.TURN

    def test_bet_fold(self):
        s = self._make_state()
        s2 = apply_action(s, PokerAction(ActionType.BET, amount=5.0))
        s3 = apply_action(s2, PokerAction(ActionType.FOLD))
        assert s3.is_terminal
        assert s3.winner == Position.OOP

    def test_cannot_act_on_terminal(self):
        s = self._make_state()
        s2 = apply_action(s, PokerAction(ActionType.FOLD))
        with pytest.raises(ValueError, match="terminal"):
            apply_action(s2, PokerAction(ActionType.CHECK))

    def test_river_completes_hand(self):
        """Check through all streets → terminal after river."""
        s = self._make_state()
        # Flop: check-check
        s = apply_action(s, PokerAction(ActionType.CHECK))
        s = apply_action(s, PokerAction(ActionType.CHECK))
        assert s.street == Street.TURN
        # Turn: check-check
        s = apply_action(s, PokerAction(ActionType.CHECK))
        s = apply_action(s, PokerAction(ActionType.CHECK))
        assert s.street == Street.RIVER
        # River: check-check
        s = apply_action(s, PokerAction(ActionType.CHECK))
        s = apply_action(s, PokerAction(ActionType.CHECK))
        assert s.is_terminal

    def test_pot_accounting(self):
        """Verify pot is correct after bet-raise-call."""
        s = self._make_state()
        # OOP bets 5
        s = apply_action(s, PokerAction(ActionType.BET, amount=5.0))
        assert s.pot == 11.5
        # IP raises to 15
        s = apply_action(s, PokerAction(ActionType.RAISE, amount=15.0))
        assert s.pot == 11.5 + 15.0
        # OOP calls: needs to put in 15 - 5 = 10
        s = apply_action(s, PokerAction(ActionType.CALL, amount=10.0))
        assert s.pot == 11.5 + 15.0 + 10.0


# ── Hand Evaluation Tests ──

class TestHandEval:
    def test_high_card(self):
        cards = parse_cards(["Ah", "Kd", "9s", "7c", "3h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.HIGH_CARD

    def test_pair(self):
        cards = parse_cards(["Ah", "Ad", "Ks", "7c", "3h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.PAIR

    def test_two_pair(self):
        cards = parse_cards(["Ah", "Ad", "Ks", "Kc", "3h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.TWO_PAIR

    def test_three_of_a_kind(self):
        cards = parse_cards(["Ah", "Ad", "As", "Kc", "3h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.THREE_OF_A_KIND

    def test_straight(self):
        cards = parse_cards(["5h", "6d", "7s", "8c", "9h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.STRAIGHT

    def test_wheel(self):
        cards = parse_cards(["Ah", "2d", "3s", "4c", "5h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.STRAIGHT
        assert r.kickers == (5,)  # wheel high is 5

    def test_flush(self):
        cards = parse_cards(["Ah", "Kh", "9h", "7h", "3h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.FLUSH

    def test_full_house(self):
        cards = parse_cards(["Ah", "Ad", "As", "Kc", "Kh"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.FULL_HOUSE

    def test_four_of_a_kind(self):
        cards = parse_cards(["Ah", "Ad", "As", "Ac", "Kh"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.FOUR_OF_A_KIND

    def test_straight_flush(self):
        cards = parse_cards(["5h", "6h", "7h", "8h", "9h"])
        r = evaluate_5(cards)
        assert r.category == HandCategory.STRAIGHT_FLUSH

    def test_comparison(self):
        pair = evaluate_5(parse_cards(["Ah", "Ad", "Ks", "7c", "3h"]))
        trips = evaluate_5(parse_cards(["Ah", "Ad", "As", "Kc", "3h"]))
        assert trips > pair

    def test_evaluate_best_7_cards(self):
        cards = parse_cards(["Ah", "Kh", "Qh", "Jh", "Th", "2c", "3d"])
        r = evaluate_best(cards)
        assert r.category == HandCategory.STRAIGHT_FLUSH

    def test_evaluate_best_picks_best(self):
        # Board: Ks 7d 2c | Hand: Ah Kh → pair of Kings
        board = parse_cards(["Ks", "7d", "2c", "8s", "4h"])
        hand = parse_cards(["Ah", "Kh"])
        r = evaluate_best(board + hand)
        assert r.category == HandCategory.PAIR


# ── Showdown Tests ──

class TestShowdown:
    def test_ip_wins(self):
        board = parse_cards(["Ks", "7d", "2c", "8s", "4h"])
        ip = parse_cards(["Ah", "Kh"])  # pair of Kings, A kicker
        oop = parse_cards(["Qd", "Jd"])  # Q high
        result = determine_winner(board, ip, oop, pot=10.0)
        assert result.winner == Position.IP
        assert result.ip_winnings == 10.0
        assert result.oop_winnings == 0.0

    def test_oop_wins(self):
        board = parse_cards(["Qs", "Qd", "2c", "8s", "4h"])
        ip = parse_cards(["Ah", "Kh"])  # pair of Queens, A kicker
        oop = parse_cards(["Qh", "Jd"])  # trips Queens
        result = determine_winner(board, ip, oop, pot=20.0)
        assert result.winner == Position.OOP

    def test_split_pot(self):
        board = parse_cards(["As", "Ks", "Qs", "Js", "Ts"])  # royal straight flush on board
        ip = parse_cards(["2h", "3h"])
        oop = parse_cards(["4d", "5d"])
        result = determine_winner(board, ip, oop, pot=10.0)
        assert result.is_split
        assert result.ip_winnings == 5.0
        assert result.oop_winnings == 5.0
