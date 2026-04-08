"""
5-card poker hand evaluator.

Evaluates the best 5-card hand from any set of cards (typically 7: 2 hole + 5 board).
Returns a HandRank that is directly comparable.

This is a straightforward combinatorial evaluator — not optimized for
millions of evaluations per second. Sufficient for game play and
unit testing. A future phase can swap in a lookup-table evaluator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from app.poker_engine.cards import Card
from app.poker_engine.types import HandCategory, Rank


@dataclass(frozen=True, slots=True, order=True)
class HandRank:
    """
    Comparable hand ranking.

    Comparison is (category, kickers) where kickers is a tuple of
    rank values in descending significance order.
    """
    category: HandCategory
    kickers: tuple[int, ...]

    @property
    def name(self) -> str:
        return _CATEGORY_NAMES.get(self.category, "Unknown")


_CATEGORY_NAMES = {
    HandCategory.HIGH_CARD: "High Card",
    HandCategory.PAIR: "Pair",
    HandCategory.TWO_PAIR: "Two Pair",
    HandCategory.THREE_OF_A_KIND: "Three of a Kind",
    HandCategory.STRAIGHT: "Straight",
    HandCategory.FLUSH: "Flush",
    HandCategory.FULL_HOUSE: "Full House",
    HandCategory.FOUR_OF_A_KIND: "Four of a Kind",
    HandCategory.STRAIGHT_FLUSH: "Straight Flush",
}


def _is_flush(cards: Sequence[Card]) -> bool:
    return len(set(c.suit for c in cards)) == 1


def _straight_high(ranks: list[int]) -> int | None:
    """
    Return the high card of a straight, or None.
    Handles wheel (A-2-3-4-5) as high=5.
    """
    unique = sorted(set(ranks), reverse=True)
    if len(unique) < 5:
        return None

    # Check normal straights
    for i in range(len(unique) - 4):
        if unique[i] - unique[i + 4] == 4:
            return unique[i]

    # Check wheel: A-2-3-4-5
    if set(unique) >= {14, 2, 3, 4, 5}:
        return 5

    return None


def evaluate_5(cards: Sequence[Card]) -> HandRank:
    """Evaluate exactly 5 cards."""
    assert len(cards) == 5

    ranks = sorted([c.rank.value for c in cards], reverse=True)
    rank_counts = Counter(ranks)
    flush = _is_flush(cards)
    straight_high = _straight_high(ranks)

    # Straight flush
    if flush and straight_high is not None:
        return HandRank(HandCategory.STRAIGHT_FLUSH, (straight_high,))

    # Four of a kind
    freq = rank_counts.most_common()
    if freq[0][1] == 4:
        quad_rank = freq[0][0]
        kicker = freq[1][0]
        return HandRank(HandCategory.FOUR_OF_A_KIND, (quad_rank, kicker))

    # Full house
    if freq[0][1] == 3 and freq[1][1] == 2:
        return HandRank(HandCategory.FULL_HOUSE, (freq[0][0], freq[1][0]))

    # Flush
    if flush:
        return HandRank(HandCategory.FLUSH, tuple(ranks))

    # Straight
    if straight_high is not None:
        return HandRank(HandCategory.STRAIGHT, (straight_high,))

    # Three of a kind
    if freq[0][1] == 3:
        trip_rank = freq[0][0]
        kickers = sorted([r for r, c in freq if c != 3], reverse=True)
        return HandRank(HandCategory.THREE_OF_A_KIND, (trip_rank, *kickers))

    # Two pair
    if freq[0][1] == 2 and freq[1][1] == 2:
        pairs = sorted([r for r, c in freq if c == 2], reverse=True)
        kicker = [r for r, c in freq if c == 1][0]
        return HandRank(HandCategory.TWO_PAIR, (*pairs, kicker))

    # One pair
    if freq[0][1] == 2:
        pair_rank = freq[0][0]
        kickers = sorted([r for r, c in freq if c == 1], reverse=True)
        return HandRank(HandCategory.PAIR, (pair_rank, *kickers))

    # High card
    return HandRank(HandCategory.HIGH_CARD, tuple(ranks))


def evaluate_best(cards: list[Card]) -> HandRank:
    """
    Find the best 5-card hand from any number of cards (typically 7).

    Enumerates all C(n, 5) combinations and returns the best.
    """
    if len(cards) < 5:
        raise ValueError(f"Need at least 5 cards, got {len(cards)}")

    if len(cards) == 5:
        return evaluate_5(cards)

    best: HandRank | None = None
    for combo in combinations(cards, 5):
        rank = evaluate_5(combo)
        if best is None or rank > best:
            best = rank

    assert best is not None
    return best
