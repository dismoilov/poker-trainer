"""
Phase 13A: Python ↔ Rust bridge module.

Provides a clean boundary between the Python solver and the Rust
poker_core native extension. Handles card encoding conversion and
provides batch equity computation with graceful fallback to Python
if Rust is unavailable.

CARD ENCODING:
  Python Card: Card(rank=Rank.ACE, suit=Suit.HEARTS) → "Ah"
  Rust int:    rank_idx * 4 + suit_idx
    rank_idx: 0=2, 1=3, ..., 12=A
    suit_idx: 0=clubs, 1=diamonds, 2=hearts, 3=spades
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Try to import Rust module ──────────────────────────────────

try:
    import poker_core as _rust
    RUST_AVAILABLE = True
    RUST_VERSION = _rust.version()
    logger.info("Rust poker_core loaded: %s", RUST_VERSION)
except ImportError:
    _rust = None
    RUST_AVAILABLE = False
    RUST_VERSION = None
    logger.info("Rust poker_core not available, using Python fallback")


# ── Card encoding ──────────────────────────────────────────────

# Suit mapping: Python Suit enum value → Rust suit index
_SUIT_TO_INT = {"c": 0, "d": 1, "h": 2, "s": 3}

# Rank mapping: Python Rank IntEnum value → Rust rank index
# Python: Rank.TWO=2 ... Rank.ACE=14
# Rust:   0=2 ... 12=Ace
# So: rank_idx = rank.value - 2


def card_to_int(card) -> int:
    """Convert a Python Card object to Rust integer encoding.
    
    Card encoding: rank_idx * 4 + suit_idx
    where rank_idx = card.rank.value - 2 (0=2, 12=A)
    and suit_idx = 0=c, 1=d, 2=h, 3=s
    """
    rank_idx = card.rank.value - 2  # Rank.TWO=2 → 0, Rank.ACE=14 → 12
    suit_idx = _SUIT_TO_INT[card.suit.value]  # Suit.CLUBS="c" → 0
    return rank_idx * 4 + suit_idx


def card_str_to_int(card_str: str) -> int:
    """Convert a card string like 'Ah' to Rust integer encoding."""
    from app.poker_engine.cards import Card
    return card_to_int(Card.parse(card_str))


def combo_to_ints(combo: tuple) -> tuple[int, int]:
    """Convert a combo (Card, Card) to Rust pair (int, int)."""
    return (card_to_int(combo[0]), card_to_int(combo[1]))


def board_to_ints(board: list) -> list[int]:
    """Convert a list of Card objects to Rust integer list."""
    return [card_to_int(c) for c in board]


# ── Rust-backed equity functions ───────────────────────────────

def rust_evaluate_hand(cards: list) -> Optional[int]:
    """Evaluate hand using Rust — returns comparable int rank or None."""
    if not RUST_AVAILABLE:
        return None
    card_ints = [card_to_int(c) for c in cards]
    return _rust.evaluate_hand(card_ints)


def rust_compute_equity(ip_combo, oop_combo, board) -> Optional[float]:
    """Compute single showdown equity using Rust. Returns None if unavailable."""
    if not RUST_AVAILABLE:
        return None
    ip_ints = combo_to_ints(ip_combo)
    oop_ints = combo_to_ints(oop_combo)
    board_ints = board_to_ints(board)
    return _rust.compute_equity(ip_ints, oop_ints, board_ints)


def rust_batch_equity(
    ip_combos: list,
    oop_combos: list,
    board: list,
    valid_matchups: list[tuple[int, int]],
) -> Optional[dict]:
    """
    Batch compute equity for all matchups on a board.
    
    Returns: dict of {(ip_idx, oop_idx): equity} or None if unavailable.
    """
    if not RUST_AVAILABLE:
        return None
    
    ip_hands = [combo_to_ints(c) for c in ip_combos]
    oop_hands = [combo_to_ints(c) for c in oop_combos]
    board_ints = board_to_ints(board)
    
    results = _rust.batch_compute_equity(ip_hands, oop_hands, board_ints, valid_matchups)
    
    equity_map = {}
    for i, (ip_idx, oop_idx) in enumerate(valid_matchups):
        equity_map[(ip_idx, oop_idx)] = results[i]
    
    return equity_map


def rust_batch_equity_multi_board(
    ip_combos: list,
    oop_combos: list,
    boards: list[list],
    matchups_per_board: list[list[tuple[int, int]]],
) -> Optional[list[tuple]]:
    """
    Batch compute equity across multiple board variants.
    
    Returns: list of (board_idx, ip_idx, oop_idx, equity) or None.
    """
    if not RUST_AVAILABLE:
        return None
    
    ip_hands = [combo_to_ints(c) for c in ip_combos]
    oop_hands = [combo_to_ints(c) for c in oop_combos]
    boards_ints = [board_to_ints(b) for b in boards]
    
    return _rust.batch_compute_equity_multi_board(
        ip_hands, oop_hands, boards_ints, matchups_per_board
    )
