"""
Core enumerations and type aliases for the poker engine.

All poker primitives are defined here to avoid circular imports.
"""

from enum import Enum, IntEnum
from typing import TypeAlias


class Suit(Enum):
    SPADES = "s"
    HEARTS = "h"
    DIAMONDS = "d"
    CLUBS = "c"


class Rank(IntEnum):
    """Rank values: 2=2 ... A=14. IntEnum so ranks are directly comparable."""
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14


RANK_CHARS: dict[str, Rank] = {
    "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR, "5": Rank.FIVE,
    "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT, "9": Rank.NINE,
    "T": Rank.TEN, "J": Rank.JACK, "Q": Rank.QUEEN, "K": Rank.KING,
    "A": Rank.ACE,
}

RANK_TO_CHAR: dict[Rank, str] = {v: k for k, v in RANK_CHARS.items()}

SUIT_CHARS: dict[str, Suit] = {
    "s": Suit.SPADES, "h": Suit.HEARTS, "d": Suit.DIAMONDS, "c": Suit.CLUBS,
}

SUIT_TO_CHAR: dict[Suit, str] = {v: k for k, v in SUIT_CHARS.items()}


class Street(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALLIN = "allin"


class Position(Enum):
    """Heads-up positions for Phase 1."""
    IP = "IP"    # In Position (acts last postflop)
    OOP = "OOP"  # Out of Position (acts first postflop)


class HandCategory(IntEnum):
    """Hand ranking categories, lowest to highest."""
    HIGH_CARD = 0
    PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


# Type alias for a strategy matrix: hand_label → {action_id → frequency}
StrategyMatrix: TypeAlias = dict[str, dict[str, float]]
