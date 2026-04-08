"""
Immutable game state representation.

GameState is a frozen dataclass that captures the complete state of a
heads-up postflop poker hand at any point during play.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.poker_engine.cards import Card
from app.poker_engine.types import Street, Position, ActionType


@dataclass(frozen=True, slots=True)
class ActionRecord:
    """Record of a single action taken during the hand."""
    player: Position
    action_type: ActionType
    amount: float
    street: Street


@dataclass(frozen=True)
class GameState:
    """
    Complete state of a heads-up postflop hand.

    This is an immutable value object. State transitions produce new
    GameState instances via transitions.apply_action().
    """
    # Players
    stacks: dict[Position, float]        # remaining stacks
    pot: float                           # total pot
    board: list[Card]                    # community cards dealt so far

    # Hole cards (None = unknown/face-down)
    hands: dict[Position, Optional[list[Card]]]

    # Game flow
    street: Street
    current_player: Position
    action_history: list[ActionRecord] = field(default_factory=list)

    # Betting state for current street
    facing_bet: float = 0.0              # how much current player needs to call
    last_raise_size: float = 0.0         # for min-raise calculation
    street_contributions: dict[Position, float] = field(
        default_factory=lambda: {Position.IP: 0.0, Position.OOP: 0.0}
    )

    # Terminal state
    is_terminal: bool = False
    winner: Optional[Position] = None
    folded_player: Optional[Position] = None

    # Street action tracking
    actions_this_street: int = 0
    last_aggressor: Optional[Position] = None

    @property
    def hero(self) -> Position:
        return Position.IP

    @property
    def villain(self) -> Position:
        return Position.OOP

    @property
    def opponent(self) -> Position:
        if self.current_player == Position.IP:
            return Position.OOP
        return Position.IP

    @property
    def is_showdown(self) -> bool:
        """True if hand reached river and both players completed action."""
        return self.is_terminal and self.folded_player is None

    @property
    def effective_stack(self) -> float:
        """Smallest remaining stack."""
        return min(self.stacks.values())


def create_initial_state(
    ip_stack: float,
    oop_stack: float,
    pot: float,
    board: list[Card],
    ip_hand: Optional[list[Card]] = None,
    oop_hand: Optional[list[Card]] = None,
    street: Street = Street.FLOP,
) -> GameState:
    """
    Create the initial state for a heads-up postflop hand.

    In postflop play, OOP acts first.
    """
    return GameState(
        stacks={Position.IP: ip_stack, Position.OOP: oop_stack},
        pot=pot,
        board=list(board),
        hands={Position.IP: ip_hand, Position.OOP: oop_hand},
        street=street,
        current_player=Position.OOP,  # OOP acts first postflop
        facing_bet=0.0,
        last_raise_size=0.0,
        street_contributions={Position.IP: 0.0, Position.OOP: 0.0},
    )
