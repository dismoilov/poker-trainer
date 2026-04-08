"""
Heuristic villain action policy — replaces purely random action selection.

This policy uses board texture and hand strength to weight action
selection. It is NOT GTO, NOT equilibrium play. It is a scripted
heuristic that produces more realistic play than random selection.

HONEST LABEL: This is a scripted heuristic policy.
"""

from __future__ import annotations

import random
from typing import Sequence

from app.poker_engine.cards import Card
from app.poker_engine.hand_eval import evaluate_best, HandRank
from app.poker_engine.types import HandCategory


def _hand_strength_tier(hand: list[Card], board: list[Card]) -> int:
    """
    Evaluate hand strength as a tier 0-5.
    0 = nothing/weak, 5 = monster.
    """
    if len(board) < 3 or len(hand) < 2:
        return 2  # default mid-tier with no board

    all_cards = hand + board
    if len(all_cards) < 5:
        return 2

    rank = evaluate_best(all_cards)
    cat = rank.category

    if cat >= HandCategory.STRAIGHT_FLUSH:
        return 5
    elif cat >= HandCategory.FOUR_OF_A_KIND:
        return 5
    elif cat >= HandCategory.FULL_HOUSE:
        return 5
    elif cat >= HandCategory.FLUSH:
        return 4
    elif cat >= HandCategory.STRAIGHT:
        return 4
    elif cat >= HandCategory.THREE_OF_A_KIND:
        return 3
    elif cat >= HandCategory.TWO_PAIR:
        return 3
    elif cat >= HandCategory.PAIR:
        # Check if it's top pair or better
        if rank.kickers and rank.kickers[0] >= 10:
            return 2
        return 1
    else:
        return 0


def _board_wetness(board: list[Card]) -> float:
    """
    Estimate board wetness 0.0 (dry) to 1.0 (wet).
    Considers flush draws and straight potential.
    """
    if len(board) < 3:
        return 0.5

    suits = [c.suit for c in board]
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    max_suited = max(suit_counts.values())

    ranks = sorted([c.rank.value for c in board])
    gaps = sum(1 for i in range(len(ranks) - 1) if ranks[i + 1] - ranks[i] <= 2)

    wetness = 0.0
    if max_suited >= 3:
        wetness += 0.4
    elif max_suited >= 2:
        wetness += 0.2

    wetness += min(gaps * 0.15, 0.4)

    return min(wetness, 1.0)


from app.poker_engine.actions import PokerAction


def choose_villain_action(
    legal_actions: list[PokerAction],
    villain_hand: list[Card],
    board: list[Card],
    pot: float,
    facing_bet: float,
) -> PokerAction:
    """
    Choose a villain action using heuristic hand-strength policy.

    HONEST LABEL: This is a scripted heuristic, not GTO or solver-based.

    Policy:
    - Monsters (tier 4-5): usually bet/raise/call, rarely check/fold
    - Strong (tier 3): mix of betting and checking/calling
    - Marginal (tier 1-2): mostly check/call, sometimes fold to aggression
    - Air (tier 0): usually check/fold, bluff occasionally
    """
    if not legal_actions:
        raise ValueError("No legal actions available")

    if len(legal_actions) == 1:
        return legal_actions[0]

    tier = _hand_strength_tier(villain_hand, board)
    wetness = _board_wetness(board)

    # Build action type map
    by_type: dict[str, list[PokerAction]] = {}
    for a in legal_actions:
        by_type.setdefault(a.type.value, []).append(a)

    has_check = 'check' in by_type
    has_fold = 'fold' in by_type
    has_call = 'call' in by_type
    has_bet = 'bet' in by_type
    has_raise = 'raise' in by_type
    aggressive = by_type.get('bet', []) + by_type.get('raise', [])

    # Assign weights to action categories based on tier
    weights: dict[str, float] = {}

    if tier >= 4:  # Monster
        weights['aggressive'] = 0.65
        weights['passive'] = 0.30   # check or call
        weights['fold'] = 0.00
        weights['allin'] = 0.05
    elif tier == 3:  # Strong
        weights['aggressive'] = 0.40
        weights['passive'] = 0.50
        weights['fold'] = 0.02
        weights['allin'] = 0.08
    elif tier == 2:  # Marginal-decent
        weights['aggressive'] = 0.20
        weights['passive'] = 0.65
        weights['fold'] = 0.10
        weights['allin'] = 0.05
    elif tier == 1:  # Weak
        weights['aggressive'] = 0.10
        weights['passive'] = 0.50
        weights['fold'] = 0.35
        weights['allin'] = 0.05
    else:  # Air
        bluff_freq = 0.15 + wetness * 0.10  # bluff more on wet boards
        weights['aggressive'] = bluff_freq
        weights['passive'] = 0.30
        weights['fold'] = 0.55 - bluff_freq
        weights['allin'] = 0.00

    # Facing a bet → shift toward fold for weak hands
    if facing_bet > 0:
        bet_ratio = facing_bet / max(pot, 1.0)
        if tier <= 1:
            weights['fold'] += bet_ratio * 0.3
            weights['passive'] -= bet_ratio * 0.15
            weights['aggressive'] -= bet_ratio * 0.15

    # Build weighted action list
    candidates: list[tuple[PokerAction, float]] = []

    # Passive actions
    if has_check:
        for a in by_type['check']:
            candidates.append((a, weights.get('passive', 0.3)))
    if has_call:
        for a in by_type['call']:
            candidates.append((a, weights.get('passive', 0.3)))

    # Aggressive actions
    if aggressive:
        per_action_w = weights.get('aggressive', 0.2) / max(len(aggressive), 1)
        for a in aggressive:
            candidates.append((a, per_action_w))

    # Fold
    if has_fold:
        for a in by_type['fold']:
            candidates.append((a, weights.get('fold', 0.1)))

    # Allin
    if 'allin' in by_type:
        for a in by_type['allin']:
            candidates.append((a, weights.get('allin', 0.02)))

    if not candidates:
        return random.choice(legal_actions)

    # Weighted random selection
    total = sum(w for _, w in candidates)
    if total <= 0:
        return random.choice(legal_actions)

    r = random.random() * total
    cumulative = 0.0
    for action, w in candidates:
        cumulative += w
        if r <= cumulative:
            return action

    return candidates[-1][0]
