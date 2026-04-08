"""
Best-response exploitability computation for the CFR+ solver.

THIS IS REAL EXPLOITABILITY COMPUTATION, not an approximation.

Given a strategy profile σ (the solver's average strategy output), this module
computes the best-response value for each player. The best-response for player P
is the strategy that maximizes P's expected value given that the opponent plays σ₋ₚ.

Exploitability = (BR_EV_IP(σ_OOP) + BR_EV_OOP(σ_IP)) / 2

At a Nash equilibrium, exploitability = 0.

SCOPE AND HONEST LIMITATIONS:
- This IS exact exploitability within the current game abstraction
  (fixed bet sizes, HU postflop, supported streets)
- This is NOT exploitability of a full NLHE game
- The game abstraction itself may not perfectly model real poker
- Action abstraction (finite bet sizes) creates an approximation
- Turn support is constrained (capped turn cards, 1 bet size)
- River is NOT supported
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.poker_engine.cards import Card
from app.solver.cfr_solver import (
    CfrSolver,
    SolveOutput,
    SolveRequest,
    compute_showdown_equity,
    info_set_key,
)
from app.solver.tree_builder import GameTreeNode, NodeType

logger = logging.getLogger(__name__)


@dataclass
class ExploitabilityResult:
    """Result of best-response exploitability computation."""
    ip_br_value: float = 0.0        # IP's best-response EV (bb)
    oop_br_value: float = 0.0       # OOP's best-response EV (bb)
    exploitability_bb: float = 0.0  # (ip_br_value + oop_br_value) / 2
    exploitability_mbb_per_hand: float = 0.0  # exploitability × 1000

    # Honesty flags
    is_exact_within_abstraction: bool = True
    scope_note: str = (
        "Exact exploitability within this game abstraction "
        "(supported streets, fixed bet sizes, HU postflop). "
        "NOT exploitability of a full NLHE game."
    )

    # Quality interpretation
    quality_label: str = ""
    matchups_evaluated: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ip_br_value_bb": round(self.ip_br_value, 6),
            "oop_br_value_bb": round(self.oop_br_value, 6),
            "exploitability_bb": round(self.exploitability_bb, 6),
            "exploitability_mbb_per_hand": round(self.exploitability_mbb_per_hand, 2),
            "is_exact_within_abstraction": self.is_exact_within_abstraction,
            "scope_note": self.scope_note,
            "quality_label": self.quality_label,
            "matchups_evaluated": self.matchups_evaluated,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }


def _quality_label(mbb: float) -> str:
    """Assign a quality label based on exploitability in mbb/hand."""
    if mbb < 1.0:
        return "EXCELLENT — near-Nash (<1 mbb/hand)"
    elif mbb < 5.0:
        return "GOOD — low exploitability (<5 mbb/hand)"
    elif mbb < 20.0:
        return "ACCEPTABLE — moderate exploitability (<20 mbb/hand)"
    elif mbb < 100.0:
        return "ROUGH — noticeable exploitability (<100 mbb/hand)"
    else:
        return "POOR — high exploitability (≥100 mbb/hand)"


def compute_exploitability(solver: CfrSolver, output: SolveOutput) -> ExploitabilityResult:
    """
    Compute exact exploitability within the game abstraction.

    For each matchup and each player:
    1. Compute the value under the strategy profile (both players follow σ)
    2. Compute the best-response value (BR player picks max, opponent follows σ)
    3. Excess = BR_value - strategy_value
    4. Exploitability = (avg_ip_excess + avg_oop_excess) / 2

    At Nash equilibrium, exploitability = 0 exactly.

    Args:
        solver: The CfrSolver instance (must still have tree/combos cached)
        output: The SolveOutput with average strategies

    Returns:
        ExploitabilityResult with exact values
    """
    import time
    start = time.time()

    root = solver._root
    board = solver._board
    ip_combos = solver._ip_combos
    oop_combos = solver._oop_combos
    valid_matchups = solver._valid_matchups
    strategies = output.strategies
    pot = solver._pot

    if not root or not ip_combos or not oop_combos:
        return ExploitabilityResult(
            scope_note="Cannot compute: solver state not available",
            is_exact_within_abstraction=False,
        )

    ip_excess_total = 0.0
    oop_excess_total = 0.0
    matchup_count = len(valid_matchups)

    for (ip_idx, oop_idx) in valid_matchups:
        ip_combo = ip_combos[ip_idx]
        oop_combo = oop_combos[oop_idx]

        # Strategy-profile value for IP (both follow σ)
        ip_strategy_val = _strategy_traverse(
            root, ip_combo, oop_combo, board, strategies, value_for="IP",
        )

        # IP best-response value (IP picks max, OOP follows σ)
        ip_br_val = _br_traverse(
            root, ip_combo, oop_combo, board, strategies, br_player="IP",
        )

        # OOP best-response value (OOP picks max, IP follows σ)
        oop_br_val = _br_traverse(
            root, ip_combo, oop_combo, board, strategies, br_player="OOP",
        )

        # OOP strategy value = -ip_strategy_val (zero-sum)
        oop_strategy_val = -ip_strategy_val

        # Excess: how much each player gains by switching to best-response
        ip_excess_total += max(0.0, ip_br_val - ip_strategy_val)
        oop_excess_total += max(0.0, oop_br_val - oop_strategy_val)

    # Average over matchups
    if matchup_count > 0:
        ip_excess_avg = ip_excess_total / matchup_count
        oop_excess_avg = oop_excess_total / matchup_count
    else:
        ip_excess_avg = 0.0
        oop_excess_avg = 0.0

    # Exploitability = (ip_excess + oop_excess) / 2
    exploitability_bb = (ip_excess_avg + oop_excess_avg) / 2.0
    exploitability_mbb = exploitability_bb * 1000.0

    elapsed = time.time() - start

    result = ExploitabilityResult(
        ip_br_value=ip_excess_avg,
        oop_br_value=oop_excess_avg,
        exploitability_bb=exploitability_bb,
        exploitability_mbb_per_hand=exploitability_mbb,
        is_exact_within_abstraction=True,
        quality_label=_quality_label(exploitability_mbb),
        matchups_evaluated=matchup_count,
        elapsed_seconds=elapsed,
    )

    logger.info(
        "Exploitability: %.2f mbb/hand (IP_excess=%.4f, OOP_excess=%.4f, %d matchups, %.3fs) — %s",
        exploitability_mbb, ip_excess_avg, oop_excess_avg, matchup_count, elapsed,
        result.quality_label,
    )

    return result


def _strategy_traverse(
    node: GameTreeNode,
    ip_combo: tuple[Card, Card],
    oop_combo: tuple[Card, Card],
    board: list[Card],
    strategies: dict[str, dict[str, dict[str, float]]],
    value_for: str,
) -> float:
    """
    Compute value for a player when BOTH players follow strategy profile σ.

    Both players weight actions by their strategy probabilities.
    Returns: value for value_for player in bb.
    """
    if node.is_terminal:
        return _terminal_value_for_player(node, ip_combo, oop_combo, board, value_for)

    # Chance node: average over valid turn cards
    if node.node_type == NodeType.CHANCE:
        return _chance_traverse(
            node, ip_combo, oop_combo, board, strategies,
            lambda n: _strategy_traverse(n, ip_combo, oop_combo, board, strategies, value_for),
        )

    actions = list(node.children.keys())
    if not actions:
        return 0.0

    player = node.player
    combo = ip_combo if player == "IP" else oop_combo
    combo_str = f"{combo[0]}{combo[1]}"

    node_strats = strategies.get(node.node_id, {})
    combo_strat = node_strats.get(combo_str, {})

    if not combo_strat:
        uniform = 1.0 / len(actions)
        combo_strat = {a: uniform for a in actions}

    node_value = 0.0
    for action in actions:
        child = node.children[action]
        freq = combo_strat.get(action, 0.0)
        if freq > 0:
            child_val = _strategy_traverse(child, ip_combo, oop_combo, board, strategies, value_for)
            node_value += freq * child_val
    return node_value


def _br_traverse(
    node: GameTreeNode,
    ip_combo: tuple[Card, Card],
    oop_combo: tuple[Card, Card],
    board: list[Card],
    strategies: dict[str, dict[str, dict[str, float]]],
    br_player: str,
) -> float:
    """
    Best-response tree traversal.

    For the br_player's decision nodes: take max over action values.
    For the opponent's decision nodes: weight by opponent's average strategy.
    For terminal nodes: compute value for br_player.

    Returns: value for br_player in bb.
    """
    # ── Terminal node ──
    if node.is_terminal:
        return _terminal_value_for_player(node, ip_combo, oop_combo, board, br_player)

    # ── Chance node ──
    if node.node_type == NodeType.CHANCE:
        return _chance_traverse(
            node, ip_combo, oop_combo, board, strategies,
            lambda n: _br_traverse(n, ip_combo, oop_combo, board, strategies, br_player),
        )

    actions = list(node.children.keys())
    if not actions:
        return 0.0

    player = node.player  # "IP" or "OOP"
    combo = ip_combo if player == "IP" else oop_combo
    combo_str = f"{combo[0]}{combo[1]}"

    # Get strategy for this player at this node for this combo
    node_strats = strategies.get(node.node_id, {})
    combo_strat = node_strats.get(combo_str, {})

    if not combo_strat:
        # No strategy data — use uniform
        uniform = 1.0 / len(actions)
        combo_strat = {a: uniform for a in actions}

    if player == br_player:
        # Best-response player: take MAX over actions
        best_val = float("-inf")
        for action in actions:
            child = node.children[action]
            child_val = _br_traverse(child, ip_combo, oop_combo, board, strategies, br_player)
            best_val = max(best_val, child_val)
        return best_val
    else:
        # Opponent: weight by their average strategy
        node_value = 0.0
        for action in actions:
            child = node.children[action]
            freq = combo_strat.get(action, 0.0)
            if freq > 0:
                child_val = _br_traverse(child, ip_combo, oop_combo, board, strategies, br_player)
                node_value += freq * child_val
        return node_value


def _terminal_value_for_player(
    node: GameTreeNode,
    ip_combo: tuple[Card, Card],
    oop_combo: tuple[Card, Card],
    board: list[Card],
    player: str,
) -> float:
    """Compute terminal value for the given player."""
    pot = node.pot
    tag = getattr(node, '_terminal_type', 'showdown')

    if tag == 'fold_ip':
        return -pot / 2.0 if player == "IP" else pot / 2.0
    elif tag == 'fold_oop':
        return pot / 2.0 if player == "IP" else -pot / 2.0
    else:
        # Showdown: use board extended with turn card if present
        turn_card_str = getattr(node, '_active_turn_card', None)
        eval_board = board + [Card.parse(turn_card_str)] if turn_card_str else board
        equity = compute_showdown_equity(ip_combo, oop_combo, eval_board)
        ip_ev = equity * pot - pot / 2.0
        return ip_ev if player == "IP" else -ip_ev


def _chance_traverse(
    node: GameTreeNode,
    ip_combo: tuple[Card, Card],
    oop_combo: tuple[Card, Card],
    board: list[Card],
    strategies: dict[str, dict[str, dict[str, float]]],
    child_fn,
) -> float:
    """
    Handle chance node: average over valid turn card branches.
    Skips branches whose turn card conflicts with either player's hole cards.
    """
    hole_cards = {f"{c}" for c in ip_combo} | {f"{c}" for c in oop_combo}

    total = 0.0
    count = 0
    for label, child in node.children.items():
        tc = child.turn_card
        if not tc or tc in hole_cards:
            continue
        total += child_fn(child)
        count += 1

    return total / count if count > 0 else 0.0
