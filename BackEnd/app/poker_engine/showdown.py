"""
Showdown logic: determine the winner of a hand.

Uses hand_eval to compare the best 5-card hands of each player.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.poker_engine.cards import Card
from app.poker_engine.hand_eval import evaluate_best, HandRank
from app.poker_engine.types import Position


@dataclass(frozen=True, slots=True)
class ShowdownResult:
    """Result of a showdown between two players."""
    winner: Optional[Position]  # None = split pot
    ip_rank: HandRank
    oop_rank: HandRank
    pot: float
    ip_winnings: float
    oop_winnings: float

    @property
    def is_split(self) -> bool:
        return self.winner is None


def determine_winner(
    board: list[Card],
    ip_hand: list[Card],
    oop_hand: list[Card],
    pot: float,
) -> ShowdownResult:
    """
    Evaluate both hands against the board and determine the winner.

    Args:
        board: 5 community cards.
        ip_hand: IP player's 2 hole cards.
        oop_hand: OOP player's 2 hole cards.
        pot: Total pot to award.

    Returns:
        ShowdownResult with winner, hand ranks, and winnings.
    """
    ip_cards = ip_hand + board
    oop_cards = oop_hand + board

    ip_rank = evaluate_best(ip_cards)
    oop_rank = evaluate_best(oop_cards)

    if ip_rank > oop_rank:
        winner = Position.IP
        ip_winnings = pot
        oop_winnings = 0.0
    elif oop_rank > ip_rank:
        winner = Position.OOP
        ip_winnings = 0.0
        oop_winnings = pot
    else:
        winner = None  # Split pot
        ip_winnings = pot / 2
        oop_winnings = pot / 2

    return ShowdownResult(
        winner=winner,
        ip_rank=ip_rank,
        oop_rank=oop_rank,
        pot=pot,
        ip_winnings=ip_winnings,
        oop_winnings=oop_winnings,
    )
