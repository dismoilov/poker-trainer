"""
Tests for game session service — session lifecycle, actions, hand completion.

These are unit tests that exercise the game session service directly,
bypassing the API layer. They use the poker engine for real game state
management.
"""

import pytest
from unittest.mock import MagicMock
from app.game_sessions.service import (
    _deal_hand, _build_legal_actions, _villain_auto_act,
    _active_games,
)
from app.poker_engine.types import Position, ActionType, Street
from app.poker_engine.actions import PokerAction
from app.poker_engine.transitions import apply_action


class TestDealHand:
    def test_deals_valid_hand(self):
        session_id = "test-session-1"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        assert state.street == Street.FLOP
        assert len(state.board) == 3
        assert state.hands[Position.IP] is not None
        assert len(state.hands[Position.IP]) == 2
        assert state.hands[Position.OOP] is not None
        assert len(state.hands[Position.OOP]) == 2
        assert state.pot == 6.5
        assert state.current_player == Position.OOP
        # Clean up
        _active_games.pop(session_id, None)

    def test_no_card_conflicts(self):
        """Board and hole cards should all be unique."""
        session_id = "test-session-2"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        all_cards = state.board + state.hands[Position.IP] + state.hands[Position.OOP]
        assert len(set(all_cards)) == 7  # 3 board + 2 + 2, all unique
        _active_games.pop(session_id, None)


class TestBuildLegalActions:
    def test_legal_actions_at_start(self):
        session_id = "test-session-3"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        actions = _build_legal_actions(state)
        types = {a.type for a in actions}
        assert "check" in types  # OOP can check
        assert "fold" not in types  # No bet to face
        _active_games.pop(session_id, None)


class TestVillainAutoAct:
    def test_villain_makes_legal_action(self):
        session_id = "test-session-4"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        new_state = _villain_auto_act(state)
        assert len(new_state.action_history) == 1
        assert new_state.action_history[0].player == Position.OOP
        _active_games.pop(session_id, None)


class TestHandCompletion:
    def test_fold_ends_hand(self):
        session_id = "test-session-5"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        # OOP folds
        state = apply_action(state, PokerAction(ActionType.FOLD))
        assert state.is_terminal
        assert state.winner == Position.IP
        _active_games.pop(session_id, None)

    def test_check_down_to_showdown(self):
        """Check all streets → terminal after river."""
        session_id = "test-session-6"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        # Flop
        state = apply_action(state, PokerAction(ActionType.CHECK))
        state = apply_action(state, PokerAction(ActionType.CHECK))
        # Turn
        state = apply_action(state, PokerAction(ActionType.CHECK))
        state = apply_action(state, PokerAction(ActionType.CHECK))
        # River
        state = apply_action(state, PokerAction(ActionType.CHECK))
        state = apply_action(state, PokerAction(ActionType.CHECK))
        assert state.is_terminal
        assert state.is_showdown
        _active_games.pop(session_id, None)

    def test_stacks_decrease_on_bet(self):
        session_id = "test-session-7"
        state = _deal_hand(session_id, ip_stack=100.0, oop_stack=100.0)
        initial_oop_stack = state.stacks[Position.OOP]
        bet_amount = 5.0
        state = apply_action(state, PokerAction(ActionType.BET, amount=bet_amount))
        assert state.stacks[Position.OOP] == initial_oop_stack - bet_amount
        assert state.pot == 6.5 + bet_amount
        _active_games.pop(session_id, None)
