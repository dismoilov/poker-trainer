"""
State transitions: apply an action to a GameState, producing a new GameState.

Handles:
- Fold → terminal state
- Check → pass action, possibly advance street
- Call → match bet, possibly advance street
- Bet/Raise → increase pot, set facing_bet for opponent
- All-in → put all chips in
- Street advancement (flop→turn→river→showdown)
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from app.poker_engine.actions import PokerAction
from app.poker_engine.state import GameState, ActionRecord
from app.poker_engine.types import ActionType, Position, Street


_NEXT_STREET: dict[Street, Optional[Street]] = {
    Street.PREFLOP: Street.FLOP,
    Street.FLOP: Street.TURN,
    Street.TURN: Street.RIVER,
    Street.RIVER: None,  # Showdown after river
}


def _advance_street(state: GameState) -> GameState:
    """Advance to the next street, resetting betting state."""
    next_street = _NEXT_STREET.get(state.street)

    if next_street is None:
        # River completed → showdown
        return replace(
            state,
            is_terminal=True,
            actions_this_street=0,
        )

    return replace(
        state,
        street=next_street,
        current_player=Position.OOP,  # OOP acts first on new streets
        facing_bet=0.0,
        last_raise_size=0.0,
        street_contributions={Position.IP: 0.0, Position.OOP: 0.0},
        actions_this_street=0,
        last_aggressor=None,
    )


def apply_action(state: GameState, action: PokerAction) -> GameState:
    """
    Apply an action to the current game state, returning a new state.

    This is the core state machine of the poker engine.
    Raises ValueError if the action is illegal in the current state.
    """
    if state.is_terminal:
        raise ValueError("Cannot apply action to terminal state")

    player = state.current_player
    opponent = state.opponent
    new_history = list(state.action_history) + [
        ActionRecord(
            player=player,
            action_type=action.type,
            amount=action.amount,
            street=state.street,
        )
    ]

    if action.type == ActionType.FOLD:
        return replace(
            state,
            is_terminal=True,
            winner=opponent,
            folded_player=player,
            action_history=new_history,
        )

    if action.type == ActionType.CHECK:
        new_actions = state.actions_this_street + 1
        new_state = replace(
            state,
            current_player=opponent,
            action_history=new_history,
            actions_this_street=new_actions,
        )
        # If both players have checked (OOP checks, IP checks), advance street
        if new_actions >= 2 and state.facing_bet == 0:
            return _advance_street(new_state)
        return new_state

    if action.type == ActionType.CALL:
        call_amount = min(action.amount, state.stacks[player])
        new_stacks = dict(state.stacks)
        new_stacks[player] -= call_amount
        new_pot = state.pot + call_amount
        new_contribs = dict(state.street_contributions)
        new_contribs[player] += call_amount

        new_state = replace(
            state,
            stacks=new_stacks,
            pot=new_pot,
            facing_bet=0.0,
            current_player=opponent,
            action_history=new_history,
            actions_this_street=state.actions_this_street + 1,
            street_contributions=new_contribs,
        )

        # Call closes the action → advance street
        return _advance_street(new_state)

    if action.type in (ActionType.BET, ActionType.RAISE):
        bet_amount = action.amount
        new_stacks = dict(state.stacks)
        new_stacks[player] -= bet_amount
        new_pot = state.pot + bet_amount
        new_contribs = dict(state.street_contributions)
        new_contribs[player] += bet_amount

        # The opponent now faces the difference
        new_facing = bet_amount - state.street_contributions.get(opponent, 0.0)
        raise_size = bet_amount - state.facing_bet if state.facing_bet > 0 else bet_amount

        return replace(
            state,
            stacks=new_stacks,
            pot=new_pot,
            facing_bet=new_facing,
            last_raise_size=raise_size,
            current_player=opponent,
            action_history=new_history,
            actions_this_street=state.actions_this_street + 1,
            last_aggressor=player,
            street_contributions=new_contribs,
        )

    if action.type == ActionType.ALLIN:
        allin_amount = state.stacks[player]
        new_stacks = dict(state.stacks)
        new_stacks[player] = 0.0
        new_pot = state.pot + allin_amount
        new_contribs = dict(state.street_contributions)
        new_contribs[player] += allin_amount

        is_calling_allin = allin_amount <= state.facing_bet

        new_state = replace(
            state,
            stacks=new_stacks,
            pot=new_pot,
            facing_bet=0.0 if is_calling_allin else allin_amount - new_contribs.get(opponent, 0.0),
            current_player=opponent,
            action_history=new_history,
            actions_this_street=state.actions_this_street + 1,
            last_aggressor=player if not is_calling_allin else state.last_aggressor,
            street_contributions=new_contribs,
        )

        if is_calling_allin:
            # All-in call closes action → advance to showdown
            return replace(new_state, is_terminal=True)

        # Opponent still needs to act
        return new_state

    raise ValueError(f"Unknown action type: {action.type}")
