"""
Preflop range parser and representation.

Parses standard poker range notation into a structured internal
representation. Supports:
- Individual hands: AA, AKs, AKo, AQ
- Plus notation: TT+, ATs+, A5s+
- Dash ranges: 76s-54s, TT-77
- Wildcards: AK (means AKs + AKo)

HONEST NOTE: This parser produces a set of hand combos. It does NOT
assign any frequencies or weights. Range weighting with strategies
is a solver-level concern not yet implemented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Rank ordering (highest first)
RANK_CHARS = "AKQJT98765432"
RANK_ORDER = {r: i for i, r in enumerate(RANK_CHARS)}

# All 169 canonical hand labels
ALL_HANDS: list[str] = []
for i, r1 in enumerate(RANK_CHARS):
    for j, r2 in enumerate(RANK_CHARS):
        if i < j:
            ALL_HANDS.append(f"{r1}{r2}s")
            ALL_HANDS.append(f"{r1}{r2}o")
        elif i == j:
            ALL_HANDS.append(f"{r1}{r2}")
ALL_HANDS_SET = frozenset(ALL_HANDS)


@dataclass
class ParsedRange:
    """A parsed preflop range: set of canonical hand labels."""
    hands: set[str] = field(default_factory=set)

    @property
    def count(self) -> int:
        return len(self.hands)

    @property
    def combos(self) -> int:
        total = 0
        for h in self.hands:
            if len(h) == 2:
                total += 6     # pair: C(4,2) = 6
            elif h.endswith('s'):
                total += 4     # suited: 4 combos
            else:
                total += 12    # offsuit: 12 combos
        return total

    @property
    def pct(self) -> float:
        return self.combos / 1326.0 * 100.0

    def contains(self, hand: str) -> bool:
        return _normalize_hand(hand) in self.hands

    def to_string(self) -> str:
        pairs = sorted([h for h in self.hands if len(h) == 2],
                       key=lambda h: RANK_ORDER[h[0]])
        suited = sorted([h for h in self.hands if h.endswith('s')],
                        key=lambda h: (RANK_ORDER[h[0]], RANK_ORDER[h[1]]))
        offsuit = sorted([h for h in self.hands if h.endswith('o')],
                         key=lambda h: (RANK_ORDER[h[0]], RANK_ORDER[h[1]]))
        return ','.join(pairs + suited + offsuit)


def _normalize_hand(hand: str) -> str:
    hand = hand.strip()
    if len(hand) == 2:
        r1, r2 = hand[0], hand[1]
        if RANK_ORDER.get(r1, 99) > RANK_ORDER.get(r2, 99):
            return f"{r2}{r1}"
        return hand
    if len(hand) == 3:
        r1, r2, s = hand[0], hand[1], hand[2]
        if RANK_ORDER.get(r1, 99) > RANK_ORDER.get(r2, 99):
            return f"{r2}{r1}{s}"
        return hand
    raise ValueError(f"Invalid hand label: {hand}")


def _pair_range_plus(rank_char: str) -> list[str]:
    """TT+ → TT, JJ, QQ, KK, AA"""
    idx = RANK_ORDER[rank_char]
    return [f"{RANK_CHARS[i]}{RANK_CHARS[i]}" for i in range(idx + 1)]


def _pair_range_dash(high: str, low: str) -> list[str]:
    """TT-77 → TT, 99, 88, 77"""
    hi = RANK_ORDER[high]
    lo = RANK_ORDER[low]
    if hi > lo:
        hi, lo = lo, hi
    return [f"{RANK_CHARS[i]}{RANK_CHARS[i]}" for i in range(hi, lo + 1)]


def _suited_range_plus(r1: str, r2: str) -> list[str]:
    """ATs+ → ATs, AJs, AQs, AKs"""
    idx2 = RANK_ORDER[r2]
    idx1 = RANK_ORDER[r1]
    results = []
    for i in range(idx1 + 1, idx2 + 1):
        results.append(f"{r1}{RANK_CHARS[i]}s")
    return results


def _offsuit_range_plus(r1: str, r2: str) -> list[str]:
    """ATo+ → ATo, AJo, AQo, AKo"""
    idx2 = RANK_ORDER[r2]
    idx1 = RANK_ORDER[r1]
    results = []
    for i in range(idx1 + 1, idx2 + 1):
        results.append(f"{r1}{RANK_CHARS[i]}o")
    return results


def _non_pair_range_dash(r1: str, r2_high: str, r2_low: str, suit: str) -> list[str]:
    """
    76s-54s → 76s, 65s, 54s
    Works by finding the gap between r1 and r2 in the first hand,
    then sliding down from the high end to the low end.
    """
    # For 76s-54s: first hand is 76s (r1=7, r2_high=6), last is 54s (r2_low=4)
    # Gap between ranks in each hand: RANK_ORDER[6] - RANK_ORDER[7] = 1
    r1_ord = RANK_ORDER[r1]
    r2h_ord = RANK_ORDER[r2_high]
    r2l_ord = RANK_ORDER[r2_low]

    gap = r2h_ord - r1_ord  # positive gap (r2 is lower rank = higher index)

    # Ensure ordering: r2h should be <= r2l in RANK_ORDER (higher rank first)
    if r2h_ord > r2l_ord:
        r2h_ord, r2l_ord = r2l_ord, r2h_ord

    results = []
    for bottom_idx in range(r2h_ord, r2l_ord + 1):
        top_idx = bottom_idx - gap
        if 0 <= top_idx < len(RANK_CHARS) and 0 <= bottom_idx < len(RANK_CHARS):
            results.append(f"{RANK_CHARS[top_idx]}{RANK_CHARS[bottom_idx]}{suit}")
    return results


_RE_PAIR_PLUS = re.compile(r'^([AKQJT2-9])\1\+$')
_RE_PAIR_DASH = re.compile(r'^([AKQJT2-9])\1-([AKQJT2-9])\2$')
_RE_PAIR = re.compile(r'^([AKQJT2-9])\1$')
_RE_HAND_PLUS = re.compile(r'^([AKQJT2-9])([AKQJT2-9])([so])\+$')
_RE_HAND_DASH = re.compile(r'^([AKQJT2-9])([AKQJT2-9])([so])-([AKQJT2-9])([AKQJT2-9])([so])$')
_RE_HAND = re.compile(r'^([AKQJT2-9])([AKQJT2-9])([so]?)$')


def parse_range(range_str: str) -> ParsedRange:
    """
    Parse a standard poker range string into a ParsedRange.

    Examples:
        parse_range("AA,KK,QQ")
        parse_range("TT+")
        parse_range("AKs,AQs+,76s-54s")
    """
    result = ParsedRange()
    if not range_str or not range_str.strip():
        return result

    tokens = [t.strip() for t in range_str.split(',') if t.strip()]
    for token in tokens:
        hands = _parse_token(token)
        result.hands.update(hands)

    return result


def _parse_token(token: str) -> list[str]:
    token = token.strip()

    m = _RE_PAIR_PLUS.match(token)
    if m:
        return _pair_range_plus(m.group(1))

    m = _RE_PAIR_DASH.match(token)
    if m:
        return _pair_range_dash(m.group(1), m.group(2))

    m = _RE_PAIR.match(token)
    if m:
        return [token]

    m = _RE_HAND_PLUS.match(token)
    if m:
        r1, r2, suit = m.group(1), m.group(2), m.group(3)
        if suit == 's':
            return _suited_range_plus(r1, r2)
        else:
            return _offsuit_range_plus(r1, r2)

    m = _RE_HAND_DASH.match(token)
    if m:
        r1a, r2a, sa = m.group(1), m.group(2), m.group(3)
        r1b, r2b, sb = m.group(4), m.group(5), m.group(6)
        if sa != sb:
            raise ValueError(f"Mixed suit types in dash range: {token}")
        return _non_pair_range_dash(r1a, r2a, r2b, sa)

    m = _RE_HAND.match(token)
    if m:
        r1, r2, suit = m.group(1), m.group(2), m.group(3)
        if r1 == r2:
            return [f"{r1}{r2}"]
        if not suit:
            return [f"{r1}{r2}s", f"{r1}{r2}o"]
        return [f"{r1}{r2}{suit}"]

    raise ValueError(f"Unrecognized range token: {token}")


def validate_range(range_str: str) -> tuple[bool, str]:
    """Validate a range string, returning (is_valid, error_message)."""
    try:
        parsed = parse_range(range_str)
        if parsed.count == 0:
            return False, "Empty range"
        for h in parsed.hands:
            if h not in ALL_HANDS_SET:
                return False, f"Invalid hand: {h}"
        return True, ""
    except ValueError as e:
        return False, str(e)
