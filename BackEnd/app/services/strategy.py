"""
Heuristic strategy generation (NOT a real solver).

Generates 169-hand strategy matrices using hand-tier lookup tables,
board-texture classification, and deterministic jitter. These are
plausible approximations useful for training, but they are NOT
equilibrium strategies computed by an iterative solver.

Inputs:
- Hand tier (1-8) from gto_data.py
- Board texture (dry/wet/paired/monotone/two_tone/semi_wet)
- Position (IP vs OOP)
- Pot type (SRP vs 3bet vs 4bet)
- Available actions (check/bet33/bet75/fold/call/raise)

For the real solver abstraction, see app/solver/base.py.
"""

import json
import logging
import random
from typing import Optional

from sqlalchemy.orm import Session

from app.models import StrategyModel
from app.services.gto_data import (
    get_hand_tier,
    BOARD_TEXTURES,
    IP_CBET_BY_TEXTURE,
    OOP_STRATEGY_BY_TEXTURE,
    FACING_BET_33,
    FACING_BET_75,
    THREBET_POT_MODIFIER,
)

logger = logging.getLogger(__name__)

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]


def get_hand_label(row: int, col: int) -> str:
    if row == col:
        return f"{RANKS[row]}{RANKS[col]}"
    if row < col:
        return f"{RANKS[row]}{RANKS[col]}s"
    return f"{RANKS[col]}{RANKS[row]}o"


ALL_HANDS = [get_hand_label(i, j) for i in range(13) for j in range(13)]


def _normalize(freqs: dict[str, float]) -> dict[str, float]:
    """Normalize frequencies to sum to 1.0."""
    total = sum(freqs.values())
    if total <= 0:
        n = len(freqs)
        return {k: 1.0 / n for k in freqs}
    return {k: v / total for k, v in freqs.items()}


def _add_jitter(freqs: dict[str, float], hand: str, node_id: str) -> dict[str, float]:
    """Add deterministic small jitter to avoid perfectly uniform output.
    This simulates the natural variance from GTO solvers where hands
    near strategy boundaries have slightly different frequencies.
    """
    seed = hash(f"{hand}:{node_id}") & 0x7FFFFFFF
    rng = random.Random(seed)

    result = {}
    for action, freq in freqs.items():
        jitter = rng.uniform(-0.05, 0.05)
        result[action] = max(0.0, freq + jitter)
    return _normalize(result)


def _get_action_set(actions: list[dict]) -> str:
    """Classify the action set: 'cbet' (check/bet), 'facing' (fold/call/raise), 'mixed'."""
    action_ids = {a["id"] if isinstance(a, dict) else a.id for a in actions}
    if "fold" in action_ids:
        return "facing"
    if "check" in action_ids:
        return "cbet"
    return "mixed"


def _detect_bet_size(actions: list[dict]) -> int:
    """Detect which bet size this is facing (from line description)."""
    for a in actions:
        aid = a["id"] if isinstance(a, dict) else a.id
        if aid == "fold":
            # Check if sibling actions have bet33 or bet75
            for other in actions:
                oid = other["id"] if isinstance(other, dict) else other.id
                size = other.get("size", None) if isinstance(other, dict) else getattr(other, "size", None)
                if size:
                    return int(size)
    return 33  # default: small bet


def generate_strategy(
    node_id: str,
    actions: list[dict],
    seed: Optional[int] = None,
    board_texture: str = "dry",
    is_ip: bool = True,
    pot_type: str = "SRP",
) -> dict[str, dict[str, float]]:
    """Generate a realistic 169-hand strategy matrix based on GTO data."""

    action_ids = [a["id"] if isinstance(a, dict) else a.id for a in actions]
    action_set = _get_action_set(actions)
    strategy: dict[str, dict[str, float]] = {}

    for i in range(13):
        for j in range(13):
            hand = get_hand_label(i, j)
            tier = get_hand_tier(hand)

            if action_set == "cbet":
                # Check / bet33 / bet75 — use positional c-bet tables
                if is_ip:
                    base_table = IP_CBET_BY_TEXTURE
                else:
                    base_table = OOP_STRATEGY_BY_TEXTURE

                texture_data = base_table.get(board_texture, base_table.get("dry", {}))
                base_freqs = texture_data.get(tier, {"check": 0.5, "bet33": 0.3, "bet75": 0.2})

                # Apply 3bet pot modifier
                if pot_type == "3bet":
                    mod = THREBET_POT_MODIFIER.get(tier, {})
                    freqs = {}
                    for aid in action_ids:
                        f = base_freqs.get(aid, 0.0) + mod.get(aid, 0.0)
                        freqs[aid] = max(0.0, f)
                elif pot_type == "4bet":
                    # 4bet pots: very polarized, strong hands bet big
                    if tier <= 2:
                        freqs = {aid: (0.05 if aid == "check" else 0.15 if aid == "bet33" else 0.80) for aid in action_ids}
                    elif tier <= 4:
                        freqs = {aid: (0.30 if aid == "check" else 0.35 if aid == "bet33" else 0.35) for aid in action_ids}
                    else:
                        freqs = {aid: (0.70 if aid == "check" else 0.20 if aid == "bet33" else 0.10) for aid in action_ids}
                else:
                    freqs = {aid: base_freqs.get(aid, 0.0) for aid in action_ids}

            elif action_set == "facing":
                # Fold / call / raise — use facing-bet tables
                bet_size = _detect_bet_size(actions)
                if bet_size >= 60:
                    facing_table = FACING_BET_75
                else:
                    facing_table = FACING_BET_33

                base_freqs = facing_table.get(tier, {"fold": 0.33, "call": 0.34, "raise": 0.33})
                freqs = {aid: base_freqs.get(aid, 0.0) for aid in action_ids}

            else:
                # Fallback: equal distribution
                n = len(action_ids)
                freqs = {aid: 1.0 / n for aid in action_ids}

            # Add jitter and normalize
            freqs = _add_jitter(freqs, hand, node_id)
            strategy[hand] = freqs

    return strategy


def get_or_create_strategy(
    db: Session, node_id: str, actions: list[dict]
) -> dict[str, dict[str, float]]:
    """Load cached strategy from DB or generate + save."""
    row = db.query(StrategyModel).filter(StrategyModel.node_id == node_id).first()
    if row:
        try:
            return json.loads(row.matrix_json)
        except json.JSONDecodeError:
            logger.warning("Corrupted strategy for %s, regenerating.", node_id)

    strategy = generate_strategy(node_id, actions)
    if row:
        row.matrix_json = json.dumps(strategy)
    else:
        row = StrategyModel(node_id=node_id, matrix_json=json.dumps(strategy))
        db.add(row)
    db.commit()
    logger.info("Generated strategy for %s", node_id)
    return strategy


def save_strategy(db: Session, node_id: str, strategy: dict) -> None:
    """Save a strategy matrix to DB."""
    row = db.query(StrategyModel).filter(StrategyModel.node_id == node_id).first()
    if row:
        row.matrix_json = json.dumps(strategy)
    else:
        row = StrategyModel(node_id=node_id, matrix_json=json.dumps(strategy))
        db.add(row)
    db.commit()
