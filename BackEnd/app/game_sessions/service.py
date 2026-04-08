"""
Game session service — manages live heads-up postflop poker sessions.

This service bridges the poker engine (pure logic) with persistence
and the API layer. It manages session lifecycle, villain AI (heuristic
hand-strength policy — NOT GTO), and hand history recording.

Phase 2 improvements:
- Villain uses heuristic hand-strength policy instead of random
- Multi-street card dealing (turn/river) fixed with proper hooks
- Improved pot/stack accounting
- Explicit status transitions
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import replace as dc_replace
from typing import Optional

from sqlalchemy.orm import Session as DbSession

from app.game_sessions.models import GameSessionModel, HandRecordModel
from app.game_sessions.schemas import (
    SessionState, LegalAction, ActionEntry, HandRecord,
)
from app.game_sessions.villain_policy import choose_villain_action
from app.poker_engine.cards import Card, parse_cards
from app.poker_engine.deck import Deck
from app.poker_engine.actions import get_legal_actions, PokerAction
from app.poker_engine.state import GameState, create_initial_state
from app.poker_engine.transitions import apply_action
from app.poker_engine.showdown import determine_winner
from app.poker_engine.types import ActionType, Position, Street

logger = logging.getLogger(__name__)

# In-memory store for active game states (session_id → GameState)
# ── PERSISTENCE BOUNDARY (Phase 8A) ──
# These dicts hold EPHEMERAL live state. On server restart:
#   - _active_games, _active_decks, _session_street_tracker are LOST
#   - GameSessionModel (stacks, hands_played) is PERSISTED in SQLite
#   - HandRecordModel (completed hand history) is PERSISTED in SQLite
# When live state is lost, get_session_state() re-deals a new hand
# and sets stateRecovered=True with a recoveryNote.
_active_games: dict[str, GameState] = {}
_active_decks: dict[str, Deck] = {}
_session_street_tracker: dict[str, str] = {}  # session_id → last dealt street

# Cleanup threshold: sessions older than this with no in-memory state
STALE_SESSION_HOURS = 24


def cleanup_stale_in_memory(max_sessions: int = 50):
    """Remove oldest in-memory game states if we exceed max_sessions.
    Preserves persisted session metadata in DB — only cleans ephemeral state."""
    if len(_active_games) <= max_sessions:
        return
    # Sort by insertion order (dict preserves insertion order in Python 3.7+)
    # Remove oldest entries first
    to_remove = list(_active_games.keys())[: len(_active_games) - max_sessions]
    for sid in to_remove:
        _active_games.pop(sid, None)
        _active_decks.pop(sid, None)
        _session_street_tracker.pop(sid, None)
    logger.info("Cleaned up %d stale in-memory sessions (cap=%d)", len(to_remove), max_sessions)


def _pos_to_str(pos: Position) -> str:
    return pos.value


def _str_to_pos(s: str) -> Position:
    return Position(s)


def _action_type_from_str(s: str) -> ActionType:
    return ActionType(s)


def _cards_to_strs(cards: Optional[list[Card]]) -> list[str]:
    if not cards:
        return []
    return [str(c) for c in cards]


def _build_legal_actions(state: GameState) -> list[LegalAction]:
    """Generate legal actions for the current player."""
    player = state.current_player
    stack = state.stacks[player]
    can_check = state.facing_bet == 0
    min_raise_to = state.facing_bet + max(state.last_raise_size, 1.0)

    actions = get_legal_actions(
        pot=state.pot,
        facing_bet=state.facing_bet,
        player_stack=stack,
        min_raise_to=min_raise_to,
        can_check=can_check,
    )

    result = []
    for a in actions:
        label = a.type.value.capitalize()
        if a.amount > 0:
            label = f"{label} {a.amount:.1f}bb"
        result.append(LegalAction(type=a.type.value, amount=a.amount, label=label))
    return result


# Hand rank localization — matches HandCategory enum names AND English display names
_RANK_RU = {
    # Enum .name values (HandCategory)
    "HIGH_CARD": "Старшая карта",
    "PAIR": "Пара",
    "ONE_PAIR": "Пара",
    "TWO_PAIR": "Две пары",
    "THREE_OF_A_KIND": "Тройка",
    "STRAIGHT": "Стрит",
    "FLUSH": "Флеш",
    "FULL_HOUSE": "Фулл-хаус",
    "FOUR_OF_A_KIND": "Каре",
    "STRAIGHT_FLUSH": "Стрит-флеш",
    "ROYAL_FLUSH": "Роял-флеш",
    # English display names from HAND_NAMES in hand_eval.py
    "High Card": "Старшая карта",
    "Pair": "Пара",
    "Two Pair": "Две пары",
    "Three of a Kind": "Тройка",
    "Straight": "Стрит",
    "Flush": "Флеш",
    "Full House": "Фулл-хаус",
    "Four of a Kind": "Каре",
    "Straight Flush": "Стрит-флеш",
}

def _ru_rank(rank_name: str) -> str:
    """Localize hand rank name to Russian."""
    return _RANK_RU.get(rank_name, rank_name)


def _state_to_response(
    session_id: str,
    state: GameState,
    session: GameSessionModel,
    last_result: Optional[str] = None,
    winning_summary: Optional[str] = None,
    state_recovered: bool = False,
    recovery_note: Optional[str] = None,
) -> SessionState:
    """Convert engine GameState to API response."""
    status = "active"
    villain_hand: list[str] = []

    if state.is_terminal:
        if state.is_showdown:
            status = "showdown"
            villain_hand = _cards_to_strs(state.hands.get(Position.OOP))
        else:
            status = "hand_complete"

    legal_actions = _build_legal_actions(state) if not state.is_terminal else []

    action_history = []
    for rec in state.action_history:
        action_history.append(ActionEntry(
            player=_pos_to_str(rec.player),
            type=rec.action_type.value,
            amount=rec.amount,
            street=rec.street.value,
        ))

    return SessionState(
        sessionId=session_id,
        status=status,
        handsPlayed=session.hands_played,
        heroStack=state.stacks[Position.IP],
        villainStack=state.stacks[Position.OOP],
        pot=state.pot,
        board=_cards_to_strs(state.board),
        heroHand=_cards_to_strs(state.hands.get(Position.IP)),
        villainHand=villain_hand,
        street=state.street.value,
        currentPlayer=_pos_to_str(state.current_player),
        legalActions=legal_actions,
        actionHistory=action_history,
        lastResult=last_result,
        winningSummary=winning_summary,
        stateRecovered=state_recovered,
        recoveryNote=recovery_note,
    )


def create_session(
    db: DbSession, starting_stack: float = 100.0, hero_position: str = "IP",
    user_id: Optional[int] = None,
) -> SessionState:
    """Create a new game session and deal the first hand."""
    session_id = f"session-{uuid.uuid4().hex[:8]}"

    session = GameSessionModel(
        id=session_id,
        user_id=user_id,
        hero_position=hero_position,
        villain_position="OOP" if hero_position == "IP" else "IP",
        starting_stack=starting_stack,
        hero_stack=starting_stack,
        villain_stack=starting_stack,
        hands_played=0,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Deal first hand
    state = _deal_hand(session_id, starting_stack, starting_stack)

    # If villain acts first (OOP in postflop), auto-act with heuristic
    while not state.is_terminal and state.current_player == Position.OOP:
        state = _villain_auto_act(state)
        _active_games[session_id] = state

    # Deal cards if street advanced during villain auto-action
    if not state.is_terminal:
        state = _maybe_deal_street_cards(session_id, state)
        _active_games[session_id] = state

    return _state_to_response(session_id, state, session)


def _deal_hand(session_id: str, ip_stack: float, oop_stack: float) -> GameState:
    """Deal a new postflop hand: shuffle, deal hole cards and flop."""
    deck = Deck()
    deck.shuffle()

    ip_hand = deck.deal(2)
    oop_hand = deck.deal(2)
    board = deck.deal(3)  # Deal flop

    pot = 6.5  # Standard SRP pot

    state = create_initial_state(
        ip_stack=ip_stack,
        oop_stack=oop_stack,
        pot=pot,
        board=board,
        ip_hand=ip_hand,
        oop_hand=oop_hand,
        street=Street.FLOP,
    )

    _active_games[session_id] = state
    _active_decks[session_id] = deck
    return state


def get_session_state(db: DbSession, session_id: str) -> SessionState:
    """Get the current state of a session."""
    session = db.query(GameSessionModel).filter(GameSessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    state = _active_games.get(session_id)
    state_recovered = False
    recovery_note = None

    if not state:
        # Phase 8A: Explicit recovery with flag instead of silent re-deal
        state = _deal_hand(session_id, session.hero_stack, session.villain_stack)
        state_recovered = True
        recovery_note = (
            "Состояние игры было потеряно (перезагрузка сервера). "
            "Новая раздача с вашим текущим стеком. "
            f"Ваши {session.hands_played} завершённых раздач сохранены в истории."
        )
        logger.warning(
            "Session %s state recovered: re-dealt with stacks %.1f/%.1f, %d hands preserved",
            session_id, session.hero_stack, session.villain_stack, session.hands_played,
        )

    return _state_to_response(
        session_id, state, session,
        state_recovered=state_recovered,
        recovery_note=recovery_note,
    )


def take_action(
    db: DbSession, session_id: str, action_type: str, amount: float = 0.0,
) -> SessionState:
    """
    Player takes an action. If it's villain's turn after, villain auto-acts.
    Returns the updated state.
    """
    session = db.query(GameSessionModel).filter(GameSessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    state = _active_games.get(session_id)
    if not state:
        raise ValueError(f"No active game state for session {session_id}")

    if state.is_terminal:
        raise ValueError("Hand is already complete")

    # Apply hero's action
    action = PokerAction(type=_action_type_from_str(action_type), amount=amount)
    state = apply_action(state, action)
    _active_games[session_id] = state

    # If it's now villain's turn and the hand isn't over, auto-act for villain
    while not state.is_terminal and state.current_player == Position.OOP:
        state = _villain_auto_act(state)
        _active_games[session_id] = state

    # Handle street advancement — deal new cards if needed
    if not state.is_terminal:
        state = _maybe_deal_street_cards(session_id, state)
        _active_games[session_id] = state

    # Handle terminal state
    last_result = None
    winning_summary = None
    if state.is_terminal:
        last_result, winning_summary = _resolve_hand(db, session_id, session, state)

    return _state_to_response(session_id, state, session, last_result, winning_summary)


def _villain_auto_act(state: GameState) -> GameState:
    """
    Villain acts using heuristic hand-strength policy.

    Phase 2: uses board texture + hand strength to weight action selection.
    HONEST LABEL: This is a scripted heuristic, NOT GTO or equilibrium play.
    """
    legal = get_legal_actions(
        pot=state.pot,
        facing_bet=state.facing_bet,
        player_stack=state.stacks[Position.OOP],
        min_raise_to=state.facing_bet + max(state.last_raise_size, 1.0),
        can_check=state.facing_bet == 0,
    )
    if not legal:
        return state

    villain_hand = state.hands.get(Position.OOP, [])
    if villain_hand and len(state.board) >= 3:
        chosen = choose_villain_action(
            legal_actions=legal,
            villain_hand=villain_hand,
            board=state.board,
            pot=state.pot,
            facing_bet=state.facing_bet,
        )
    else:
        # Fallback: random if no hand info (shouldn't happen in normal play)
        import random
        chosen = random.choice(legal)

    logger.debug("Villain (heuristic) chose %s %.1f", chosen.type.value, chosen.amount)
    return apply_action(state, chosen)


def _maybe_deal_street_cards(session_id: str, state: GameState) -> GameState:
    """
    Deal turn/river cards if the street has advanced.
    Phase 2: tracks last dealt street to avoid double-dealing.
    """
    deck = _active_decks.get(session_id)
    if not deck:
        return state

    expected_board_size = {
        Street.FLOP: 3,
        Street.TURN: 4,
        Street.RIVER: 5,
    }

    needed = expected_board_size.get(state.street, len(state.board))
    last_street = _session_street_tracker.get(session_id, Street.FLOP.value)

    if len(state.board) < needed:
        cards_to_deal = needed - len(state.board)
        new_cards = deck.deal(cards_to_deal)
        state = dc_replace(state, board=state.board + new_cards)
        _session_street_tracker[session_id] = state.street.value
        logger.info(
            "Dealt %d card(s) for %s: %s",
            cards_to_deal, state.street.value,
            ' '.join(str(c) for c in new_cards),
        )

    return state


def _resolve_hand(
    db: DbSession, session_id: str, session: GameSessionModel, state: GameState,
) -> tuple[str, str]:
    """Resolve a completed hand: determine winner, update stacks, record hand."""
    hero_won = 0.0
    villain_won = 0.0
    result = ""
    winning_summary = ""

    if state.folded_player is not None:
        winner = state.winner
        if winner == Position.IP:
            hero_won = state.pot
            result = "hero_win"
            winning_summary = f"Оппонент сбросил. Вы выиграли {state.pot:.1f}ББ"
        else:
            villain_won = state.pot
            result = "villain_win"
            winning_summary = f"Вы сбросили. Оппонент забрал {state.pot:.1f}ББ"
    else:
        # Showdown
        ip_hand = state.hands.get(Position.IP)
        oop_hand = state.hands.get(Position.OOP)
        board = state.board

        # Need 5 board cards for showdown; deal remaining if needed
        deck = _active_decks.get(session_id)
        while len(board) < 5 and deck:
            board = board + deck.deal(1)

        if ip_hand and oop_hand and len(board) >= 5:
            showdown = determine_winner(board, ip_hand, oop_hand, state.pot)
            hero_won = showdown.ip_winnings
            villain_won = showdown.oop_winnings
            if showdown.is_split:
                result = "split"
                winning_summary = f"Ничья: {state.pot:.1f}ББ. {_ru_rank(showdown.ip_rank.name)}"
            elif showdown.winner == Position.IP:
                result = "hero_win"
                winning_summary = f"Вы выиграли {state.pot:.1f}ББ — {_ru_rank(showdown.ip_rank.name)}"
            else:
                result = "villain_win"
                winning_summary = f"Оппонент выиграл {state.pot:.1f}ББ — {_ru_rank(showdown.oop_rank.name)}"
        else:
            result = "error"
            winning_summary = "Не удалось определить победителя"

    # Update session stacks — correct accounting:
    # New stack = stack at start of hand (already reduced by pot contrib) + winnings
    ip_invested = session.hero_stack - state.stacks[Position.IP]
    oop_invested = session.villain_stack - state.stacks[Position.OOP]
    session.hero_stack = state.stacks[Position.IP] + hero_won
    session.villain_stack = state.stacks[Position.OOP] + villain_won
    session.hands_played += 1
    session.status = "active"  # ready for next hand
    db.commit()

    logger.info(
        "Hand %d resolved: result=%s hero_stack=%.1f villain_stack=%.1f",
        session.hands_played, result, session.hero_stack, session.villain_stack,
    )

    # Record hand
    action_entries = [
        {
            "player": _pos_to_str(rec.player),
            "type": rec.action_type.value,
            "amount": rec.amount,
            "street": rec.street.value,
        }
        for rec in state.action_history
    ]

    hand_record = HandRecordModel(
        id=f"hand-{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        hand_number=session.hands_played,
        board=_cards_to_strs(state.board),
        hero_hand=_cards_to_strs(state.hands.get(Position.IP)),
        villain_hand=_cards_to_strs(state.hands.get(Position.OOP)),
        pot=state.pot,
        hero_won=hero_won,
        villain_won=villain_won,
        result=result,
        actions_json=action_entries,
    )
    db.add(hand_record)
    db.commit()

    return result, winning_summary


def next_hand(db: DbSession, session_id: str) -> SessionState:
    """Deal a new hand within the same session."""
    session = db.query(GameSessionModel).filter(GameSessionModel.id == session_id).first()
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    # Check for busted player
    if session.hero_stack <= 0 or session.villain_stack <= 0:
        session.status = "finished"
        db.commit()
        # Return last known state or a finished state
        state = _active_games.get(session_id)
        if not state:
            state = _deal_hand(session_id, max(session.hero_stack, 0.1), max(session.villain_stack, 0.1))
        return _state_to_response(session_id, state, session)

    # Reset street tracker for new hand
    _session_street_tracker[session_id] = Street.FLOP.value

    state = _deal_hand(session_id, session.hero_stack, session.villain_stack)

    # If villain acts first (OOP), auto-act with heuristic
    while not state.is_terminal and state.current_player == Position.OOP:
        state = _villain_auto_act(state)
        _active_games[session_id] = state

    # Deal cards if street advanced during villain auto-action
    if not state.is_terminal:
        state = _maybe_deal_street_cards(session_id, state)
        _active_games[session_id] = state

    return _state_to_response(session_id, state, session)


def get_hand_history(db: DbSession, session_id: str) -> list[HandRecord]:
    """Get all hand records for a session."""
    rows = (
        db.query(HandRecordModel)
        .filter(HandRecordModel.session_id == session_id)
        .order_by(HandRecordModel.hand_number)
        .all()
    )
    result = []
    for r in rows:
        actions = [
            ActionEntry(
                player=a["player"], type=a["type"],
                amount=a["amount"], street=a["street"],
            )
            for a in (r.actions_json or [])
        ]
        result.append(HandRecord(
            id=r.id,
            handNumber=r.hand_number,
            board=r.board or [],
            heroHand=r.hero_hand or [],
            villainHand=r.villain_hand or [],
            pot=r.pot,
            heroWon=r.hero_won,
            villainWon=r.villain_won,
            result=r.result,
            actions=actions,
        ))
    return result
