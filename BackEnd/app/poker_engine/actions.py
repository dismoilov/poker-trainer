"""
Legal action generation based on game state.

Given a game state, produces the list of actions the current player
can legally take. Handles fold, check, call, bet, raise, and all-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.poker_engine.types import ActionType


@dataclass(frozen=True, slots=True)
class PokerAction:
    """A concrete action a player can take."""
    type: ActionType
    amount: float = 0.0  # chip amount for bet/raise/call/allin

    def __str__(self) -> str:
        if self.type in (ActionType.FOLD, ActionType.CHECK):
            return self.type.value
        return f"{self.type.value} {self.amount:.1f}"


def get_legal_actions(
    pot: float,
    facing_bet: float,
    player_stack: float,
    min_raise_to: float,
    can_check: bool,
) -> list[PokerAction]:
    """
    Generate all legal actions for the current player.

    Args:
        pot: Current total pot size (before this action).
        facing_bet: How much more the player needs to call (0 if no bet to face).
        player_stack: Player's remaining stack.
        min_raise_to: Minimum legal raise-to amount (typically last raise size or BB).
        can_check: Whether check is legal (True if no bet to face).

    Returns:
        List of legal PokerAction objects.
    """
    actions: list[PokerAction] = []

    if player_stack <= 0:
        return actions  # Player is already all-in

    if facing_bet > 0:
        # Facing a bet/raise
        actions.append(PokerAction(type=ActionType.FOLD))

        if player_stack <= facing_bet:
            # Can only call all-in
            actions.append(PokerAction(type=ActionType.ALLIN, amount=player_stack))
        else:
            # Normal call
            actions.append(PokerAction(type=ActionType.CALL, amount=facing_bet))

            # Raise options (if stack allows)
            if player_stack > facing_bet:
                # Min raise
                actual_min_raise = min(min_raise_to, player_stack)
                if actual_min_raise > facing_bet:
                    actions.append(PokerAction(type=ActionType.RAISE, amount=actual_min_raise))

                # Pot-sized raise
                pot_raise = pot + facing_bet * 2
                if pot_raise < player_stack and pot_raise > actual_min_raise:
                    actions.append(PokerAction(type=ActionType.RAISE, amount=round(pot_raise, 1)))

                # All-in (if different from other raises)
                if player_stack > facing_bet and player_stack != actual_min_raise:
                    actions.append(PokerAction(type=ActionType.ALLIN, amount=player_stack))
    else:
        # No bet to face
        if can_check:
            actions.append(PokerAction(type=ActionType.CHECK))

        if player_stack > 0:
            # Bet options
            # Small bet (33% pot)
            bet_33 = round(pot * 0.33, 1)
            if 0 < bet_33 <= player_stack:
                actions.append(PokerAction(type=ActionType.BET, amount=bet_33))

            # Medium bet (66% pot)
            bet_66 = round(pot * 0.66, 1)
            if bet_66 > bet_33 and bet_66 <= player_stack:
                actions.append(PokerAction(type=ActionType.BET, amount=bet_66))

            # Pot bet
            bet_pot = round(pot, 1)
            if bet_pot > bet_66 and bet_pot <= player_stack:
                actions.append(PokerAction(type=ActionType.BET, amount=bet_pot))

            # All-in (if not already covered)
            if player_stack > bet_pot:
                actions.append(PokerAction(type=ActionType.ALLIN, amount=player_stack))

    return actions
