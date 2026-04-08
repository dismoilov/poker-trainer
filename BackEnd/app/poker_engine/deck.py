"""
Standard 52-card deck with shuffle, deal, and dead-card removal.
"""

from __future__ import annotations

import random
from typing import Optional

from app.poker_engine.cards import Card
from app.poker_engine.types import Rank, Suit


def _build_full_deck() -> list[Card]:
    """Build a sorted 52-card deck."""
    return [Card(rank=r, suit=s) for s in Suit for r in Rank]


class Deck:
    """Mutable 52-card deck."""

    def __init__(self, seed: Optional[int] = None):
        self._cards: list[Card] = _build_full_deck()
        self._rng = random.Random(seed)

    def shuffle(self) -> None:
        self._rng.shuffle(self._cards)

    def deal(self, n: int = 1) -> list[Card]:
        """Deal n cards from the top. Raises if not enough cards."""
        if n > len(self._cards):
            raise ValueError(f"Cannot deal {n} cards, only {len(self._cards)} remaining")
        dealt = self._cards[:n]
        self._cards = self._cards[n:]
        return dealt

    def deal_one(self) -> Card:
        """Deal a single card."""
        return self.deal(1)[0]

    def remove(self, cards: list[Card]) -> None:
        """Remove specific cards (dead cards / known cards)."""
        card_set = set(cards)
        self._cards = [c for c in self._cards if c not in card_set]

    @property
    def remaining(self) -> int:
        return len(self._cards)

    def __len__(self) -> int:
        return len(self._cards)
