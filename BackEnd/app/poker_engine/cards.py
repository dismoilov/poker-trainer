"""
Card and Hand representations.

Card is an immutable value object parsed from standard notation ("Ah", "Tc", "2d").
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering

from app.poker_engine.types import Rank, Suit, RANK_CHARS, SUIT_CHARS, RANK_TO_CHAR, SUIT_TO_CHAR


@total_ordering
@dataclass(frozen=True, slots=True)
class Card:
    rank: Rank
    suit: Suit

    @staticmethod
    def parse(s: str) -> Card:
        """Parse 'Ah', 'Tc', '2d' etc. into a Card."""
        if len(s) != 2:
            raise ValueError(f"Invalid card string: '{s}' (must be 2 chars)")
        rank_char, suit_char = s[0], s[1]
        rank = RANK_CHARS.get(rank_char)
        suit = SUIT_CHARS.get(suit_char)
        if rank is None:
            raise ValueError(f"Invalid rank: '{rank_char}'")
        if suit is None:
            raise ValueError(f"Invalid suit: '{suit_char}'")
        return Card(rank=rank, suit=suit)

    def __str__(self) -> str:
        return f"{RANK_TO_CHAR[self.rank]}{SUIT_TO_CHAR[self.suit]}"

    def __repr__(self) -> str:
        return f"Card('{self}')"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return (self.rank, self.suit.value) < (other.rank, other.suit.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))


def parse_cards(cards_str: list[str]) -> list[Card]:
    """Parse a list of card strings into Card objects."""
    return [Card.parse(s) for s in cards_str]
