"""
Real CFR+ solver for heads-up postflop hold'em.

THIS IS A GENUINE SOLVER. It implements Vanilla CFR+ (Tammelin 2014):
- Regret-matching+ with non-negative regret floor
- Full game tree traversal over concrete card combos
- Strategy accumulation for average (converged) strategy
- Counterfactual value computation at each information set

ARCHITECTURE (Phase 16C — current state):
- PRIMARY ENGINE: Rust (poker_core) — all flop, turn, and river solves
  run through poker_core.cfr_iterate with chunked progress/cancel support
- FALLBACK: Python _cfr_traverse — only used if Rust is genuinely unavailable
  (e.g., poker_core not compiled). This path is NOT expected to be hit in
  production and exists solely as a safety net.
- Equity: Rust batch_compute_equity (primary), Python fallback
- Arrays: NumPy regrets/strategy_sums shared with Rust via zero-copy

SCOPE:
- Flop subgames with rich action abstraction (7 bet sizes + overbets + 2 raises)
- Optional turn expansion with real bet/raise support (4 bet sizes, 1 raise)
- Optional river expansion with narrow abstraction (2 bet sizes, 0 raises)
- Combos: max 80/50/30 per side (flop/turn/river)
- Adaptive iteration budgets with convergence-based early stopping (Phase 16A/B)
- Exploitability is exact within the game abstraction only

The output is a real equilibrium approximation that improves with iterations.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from itertools import product
from typing import Callable, Optional

import numpy as np

from app.poker_engine.cards import Card
from app.poker_engine.hand_eval import evaluate_best
from app.poker_engine.types import Suit, Rank, RANK_CHARS as TYPE_RANK_CHARS, SUIT_CHARS
from app.poker_engine.ranges import parse_range, RANK_CHARS as RANGE_RANK_CHARS, RANK_ORDER
from app.solver.tree_builder import (
    GameTreeNode, NodeType, TreeConfig, build_tree_skeleton, GameTreeStats,
)

logger = logging.getLogger(__name__)

# ── Safety limits ──────────────────────────────────────────────
# Phase 15A: expanded limits for practical realistic ranges
# Evidence: serial Rust benchmarks on 8-core Mac
#   Flop 80 combos: ~2s at 100i → SAFE
#   Turn 50 combos: ~5s at 50i/3tc → SAFE
#   River 30 combos: ~1.5s at 30i/2tc2rc → SAFE

MAX_TREE_NODES_FLOP = 5000
MAX_TREE_NODES_TURN = 35000          # raised from 15K→25K→35K for richer turn trees
MAX_TREE_NODES_RIVER = 150000        # Phase 11A: river trees can be large
MAX_COMBOS_PER_SIDE = 80             # Phase 15A: raised from 60 for realistic broadways+pairs
MAX_COMBOS_PER_SIDE_TURN = 50        # Phase 15A: raised from 40 for practical turn ranges
MAX_COMBOS_PER_SIDE_RIVER = 30       # Phase 15A: raised from 20 for practical river ranges
MAX_TOTAL_MATCHUPS = 5000            # Phase 15A: raised from 3600 for wider range combos
MAX_ITERATIONS = 10000
MAX_TURN_CARDS = 15                  # raised from 10 for more turn coverage
MAX_RIVER_CARDS = 10                 # Phase 11A: max river cards per turn branch
ADAPTIVE_ITER_CAP_TURN_HEAVY = 300   # auto-cap iterations for heavy turn solves
ADAPTIVE_ITER_CAP_RIVER = 150        # Phase 11A: auto-cap for river solves


# ── Data structures ────────────────────────────────────────────

@dataclass
class SolveRequest:
    """Input for a real solve."""
    board: list[str]              # e.g. ["Ks", "7d", "2c"]
    ip_range: str                 # e.g. "AA,KK,AKs"
    oop_range: str                # e.g. "TT+,AQs+"
    pot: float = 6.5
    effective_stack: float = 97.0
    bet_sizes: list[float] = field(default_factory=lambda: [0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25])
    raise_sizes: list[float] = field(default_factory=lambda: [2.5, 3.5])
    max_iterations: int = 200
    max_raises: int = 3
    deterministic: bool = False   # Sort combos/matchups for reproducible results
    include_turn: bool = False    # Enable turn card dealing via chance nodes
    max_turn_cards: int = 8       # Max turn cards to explore (0 = all)
    # Phase 10A: Turn-specific action abstraction
    turn_bet_sizes: list[float] = field(default_factory=lambda: [0.33, 0.5, 0.75, 1.0])
    turn_raise_sizes: list[float] = field(default_factory=lambda: [2.5])
    turn_max_raises: int = 1
    # Phase 11A: River support
    include_river: bool = False   # Enable river card dealing via chance nodes
    max_river_cards: int = 4      # Max river cards to explore per turn branch
    river_bet_sizes: list[float] = field(default_factory=lambda: [0.5, 1.0])
    river_raise_sizes: list[float] = field(default_factory=list)
    river_max_raises: int = 0


@dataclass
class SolveOutput:
    """Output of a completed real solve."""
    strategies: dict[str, dict[str, dict[str, float]]]  # node_id → {combo_str → {action → freq}}
    iterations: int = 0
    elapsed_seconds: float = 0.0
    convergence_metric: float = float("inf")  # sum of positive regrets (lower = better)
    tree_nodes: int = 0
    ip_combos: int = 0
    oop_combos: int = 0
    matchups: int = 0
    converged: bool = False
    metadata: dict = field(default_factory=dict)
    exploitability_mbb: float = float("inf")  # Best-response exploitability in mbb/hand
    exploitability_result: dict = field(default_factory=dict)
    stop_reason: str = "max_iterations"  # Phase 16A: why the solve stopped


@dataclass
class SolveProgressInfo:
    """Progress information during solving."""
    iteration: int = 0
    total_iterations: int = 0
    convergence_metric: float = float("inf")
    elapsed_seconds: float = 0.0
    status: str = "initializing"


class SolverArrays:
    """
    Phase 12D: NumPy-backed flat array storage for solver state.
    
    Single source of truth for regrets and strategy sums.
    All hot-path reads/writes go through these arrays directly.
    No dict-based shadow storage — eliminates split-brain bugs.
    
    Layout: regrets[info_set_idx * max_actions + action_idx]
    Backing: numpy.ndarray (float64) for SIMD and future FFI.
    """
    __slots__ = ('num_info_sets', 'max_actions', 'regrets', 'strategy_sums', 'action_counts')
    
    def __init__(self, num_info_sets: int, max_actions: int):
        self.num_info_sets = num_info_sets
        self.max_actions = max_actions
        size = num_info_sets * max_actions
        self.regrets: np.ndarray = np.zeros(size, dtype=np.float64)
        self.strategy_sums: np.ndarray = np.zeros(size, dtype=np.float64)
        self.action_counts: np.ndarray = np.zeros(num_info_sets, dtype=np.int32)
    
    def get_regret(self, info_idx: int, action_idx: int) -> float:
        return float(self.regrets[info_idx * self.max_actions + action_idx])
    
    def set_regret(self, info_idx: int, action_idx: int, value: float):
        self.regrets[info_idx * self.max_actions + action_idx] = value
    
    def get_strategy_sum(self, info_idx: int, action_idx: int) -> float:
        return float(self.strategy_sums[info_idx * self.max_actions + action_idx])
    
    def add_strategy_sum(self, info_idx: int, action_idx: int, value: float):
        self.strategy_sums[info_idx * self.max_actions + action_idx] += value


# ── Combo expansion ────────────────────────────────────────────

def _expand_hand_to_combos(hand_label: str, dead_cards: set[tuple[int, str]]) -> list[tuple[Card, Card]]:
    """
    Expand a canonical hand label (e.g. "AKs", "TT") into specific card combos,
    excluding any dead cards (board cards).
    """
    suits = list("shdc")

    if len(hand_label) == 2:
        # Pair: e.g. "AA"
        rank_char = hand_label[0]
        rank = TYPE_RANK_CHARS[rank_char]
        combos = []
        for i in range(4):
            for j in range(i + 1, 4):
                c1 = Card(rank, SUIT_CHARS[suits[i]])
                c2 = Card(rank, SUIT_CHARS[suits[j]])
                if (c1.rank.value, c1.suit.value) not in dead_cards and \
                   (c2.rank.value, c2.suit.value) not in dead_cards:
                    combos.append((c1, c2))
        return combos

    r1_char, r2_char = hand_label[0], hand_label[1]
    rank1 = TYPE_RANK_CHARS[r1_char]
    rank2 = TYPE_RANK_CHARS[r2_char]
    suit_type = hand_label[2] if len(hand_label) == 3 else ""

    combos = []
    if suit_type == "s":
        # Suited
        for s in suits:
            c1 = Card(rank1, SUIT_CHARS[s])
            c2 = Card(rank2, SUIT_CHARS[s])
            if (c1.rank.value, c1.suit.value) not in dead_cards and \
               (c2.rank.value, c2.suit.value) not in dead_cards:
                combos.append((c1, c2))
    else:
        # Offsuit
        for s1 in suits:
            for s2 in suits:
                if s1 == s2:
                    continue
                c1 = Card(rank1, SUIT_CHARS[s1])
                c2 = Card(rank2, SUIT_CHARS[s2])
                if (c1.rank.value, c1.suit.value) not in dead_cards and \
                   (c2.rank.value, c2.suit.value) not in dead_cards:
                    combos.append((c1, c2))

    return combos


def expand_range_to_combos(range_str: str, board_cards: list[Card]) -> list[tuple[Card, Card]]:
    """Expand a range string into list of concrete (Card, Card) combos, removing board blockers."""
    parsed = parse_range(range_str)
    dead = {(c.rank.value, c.suit.value) for c in board_cards}

    all_combos = []
    for hand_label in sorted(parsed.hands):
        all_combos.extend(_expand_hand_to_combos(hand_label, dead))
    return all_combos


def combo_to_str(combo: tuple[Card, Card]) -> str:
    """Convert a combo to a string key like 'AhKh'."""
    return f"{combo[0]}{combo[1]}"


# ── Equity / showdown evaluation ───────────────────────────────

def compute_showdown_equity(
    ip_combo: tuple[Card, Card],
    oop_combo: tuple[Card, Card],
    board: list[Card],
) -> float:
    """
    Compute IP's equity at showdown.
    Returns 1.0 for IP win, 0.0 for OOP win, 0.5 for tie.
    """
    ip_cards = list(ip_combo) + board
    oop_cards = list(oop_combo) + board

    ip_rank = evaluate_best(ip_cards)
    oop_rank = evaluate_best(oop_cards)

    if ip_rank > oop_rank:
        return 1.0
    elif ip_rank < oop_rank:
        return 0.0
    else:
        return 0.5


# ── Information set key ────────────────────────────────────────

def info_set_key(node_id: str, player: str, combo: tuple[Card, Card]) -> str:
    """
    Generate an information set key.
    In poker, an info set = player's private cards + public action history.
    Here, node_id encodes the action history (tree path).
    """
    return f"{node_id}|{player}|{combo_to_str(combo)}"


# ── CFR+ Engine ────────────────────────────────────────────────

class CfrSolver:
    """
    Vanilla CFR+ solver for heads-up postflop poker.

    THIS IS A REAL SOLVER. It performs genuine counterfactual regret
    minimization over concrete card combos and action trees.

    Algorithm: CFR+ (Tammelin 2014)
    - Traverse game tree for each combo matchup
    - Track cumulative regrets per information set
    - Use regret-matching+ (floor regrets at 0)
    - Accumulate strategy profile for average strategy output
    
    Phase 12C: Internal storage uses flat arrays (SolverArrays) indexed
    by integer info-set IDs. This prepares the data layout for:
    - NumPy vectorization (Stage 1)
    - Numba JIT compilation (Stage 1)
    - Rust FFI (Stage 3)
    """

    def __init__(self):
        # Phase 12D: NumPy arrays are the SINGLE source of truth
        self._arrays: Optional[SolverArrays] = None
        self._info_set_map: dict[str, int] = {}  # info_key → integer index
        self._info_set_actions: dict[int, tuple] = {}  # info_idx → action tuple
        # Tree root
        self._root: Optional[GameTreeNode] = None
        self._board: list[Card] = []
        self._ip_combos: list[tuple[Card, Card]] = []
        self._oop_combos: list[tuple[Card, Card]] = []
        self._valid_matchups: list[tuple[int, int]] = []
        self._pot: float = 0.0
        self._progress = SolveProgressInfo()
        self._cancelled = False
        self._iteration_count = 0
        # ── Performance caches (populated during solve setup) ──
        self._combo_strs_ip: list[str] = []   # pre-formatted combo strings
        self._combo_strs_oop: list[str] = []
        self._combo_hole_strs_ip: list[set[str]] = []  # hole card strings for blocker checks
        self._combo_hole_strs_oop: list[set[str]] = []
        self._equity_cache: dict[tuple, float] = {}  # (ip_idx, oop_idx, board_key) → equity
        # Phase 12D: use_arrays flag (always True when info sets exist)
        self._use_arrays: bool = False

    def _get_current_strategy_arrays(self, info_idx: int, num_actions: int) -> list[float]:
        """
        Phase 12C: Compute current strategy via regret-matching+ using flat arrays.
        Returns a list[float] of strategy weights (len = num_actions).
        """
        arrays = self._arrays
        max_a = arrays.max_actions
        base = info_idx * max_a
        
        total = 0.0
        strategy = [0.0] * num_actions
        for a_idx in range(num_actions):
            r = arrays.regrets[base + a_idx]
            v = r if r > 0.0 else 0.0
            strategy[a_idx] = v
            total += v
        
        if total > 0.0:
            inv_total = 1.0 / total
            for a_idx in range(num_actions):
                strategy[a_idx] *= inv_total
        else:
            uniform = 1.0 / num_actions
            for a_idx in range(num_actions):
                strategy[a_idx] = uniform
        return strategy

    def _get_current_strategy(self, info_key: str, actions: tuple) -> dict[str, float]:
        """
        Compute current strategy via regret-matching+.
        If all regrets are non-positive, return uniform strategy.

        Phase 12D: Reads from NumPy-backed flat array. Uses Python math
        on the hot path (faster than np.maximum for 3-7 elements) while
        keeping numpy ndarray as the single storage backend.
        """
        info_idx = self._info_set_map.get(info_key, -1)
        n = len(actions)
        if info_idx < 0:
            uniform = 1.0 / n
            return {a: uniform for a in actions}

        arr = self._arrays.regrets
        base = info_idx * self._arrays.max_actions
        total = 0.0
        strategy = {}
        for i in range(n):
            r = float(arr[base + i])
            v = r if r > 0.0 else 0.0
            strategy[actions[i]] = v
            total += v

        if total > 0.0:
            inv_total = 1.0 / total
            for a in actions:
                strategy[a] *= inv_total
            return strategy
        else:
            uniform = 1.0 / n
            return {a: uniform for a in actions}

    def _accumulate_strategy(self, info_key: str, strategy: dict[str, float], reach_prob: float):
        """
        Add weighted strategy to cumulative strategy sums.
        Phase 12D: Writes directly to NumPy arrays.
        """
        info_idx = self._info_set_map.get(info_key, -1)
        if info_idx < 0:
            return
        base = info_idx * self._arrays.max_actions
        actions = self._info_set_actions[info_idx]
        for a_idx, action in enumerate(actions):
            self._arrays.strategy_sums[base + a_idx] += reach_prob * strategy[action]

    def _get_average_strategy(self, info_key: str, actions: list[str]) -> dict[str, float]:
        """Get the average strategy (converged output) for an information set.
        Phase 12D: Reads from NumPy arrays.
        """
        info_idx = self._info_set_map.get(info_key, -1)
        n = len(actions)
        if info_idx < 0:
            uniform = 1.0 / n
            return {a: uniform for a in actions}
        base = info_idx * self._arrays.max_actions
        sums_slice = self._arrays.strategy_sums[base:base + n]
        total = float(sums_slice.sum())
        if total > 0:
            return {actions[i]: float(sums_slice[i] / total) for i in range(n)}
        else:
            uniform = 1.0 / n
            return {a: uniform for a in actions}

    def _cfr_traverse(
        self,
        node: GameTreeNode,
        ip_combo_idx: int,
        oop_combo_idx: int,
        ip_reach: float,
        oop_reach: float,
        traversing_player: str,
        active_turn_card: str = "",
        active_river_card: str = "",
    ) -> float:
        """
        Recursive CFR+ traversal.

        Returns the counterfactual value for the traversing player at this node.

        Phase 12A: Optimized hot path — uses cached _is_terminal, _is_chance,
        _actions_tuple. Avoids dict.keys(), property lookups, and repeated
        dict accesses in the inner loop.
        """
        # ── Terminal node (uses cached bool) ──
        if node._is_terminal:
            return self._terminal_value_fast(
                node, ip_combo_idx, oop_combo_idx, traversing_player,
                active_turn_card, active_river_card,
            )

        # ── Chance node (uses cached bool) ──
        if node._is_chance:
            return self._traverse_chance_node(
                node, ip_combo_idx, oop_combo_idx,
                ip_reach, oop_reach, traversing_player,
                active_turn_card, active_river_card,
            )

        # ── Action node ──
        actions = node._actions_tuple  # Phase 12A: pre-built tuple
        if not actions:
            return 0.0

        player = node.player  # "IP" or "OOP"
        is_ip = (player == "IP")
        combo_idx = ip_combo_idx if is_ip else oop_combo_idx
        children = node.children  # Phase 12A: local reference

        # ── Phase 12D: NumPy array path (single source of truth) ──
        combo_str = self._combo_strs_ip[ip_combo_idx] if is_ip else self._combo_strs_oop[oop_combo_idx]
        info_key = f"{node.node_id}|{player}|{combo_str}"

        strategy = self._get_current_strategy(info_key, actions)

        if player == traversing_player:
            action_values_d: dict[str, float] = {}
            node_value = 0.0

            for action in actions:
                child = children[action]
                s_a = strategy[action]
                if is_ip:
                    child_val = self._cfr_traverse(
                        child, ip_combo_idx, oop_combo_idx,
                        ip_reach * s_a, oop_reach,
                        traversing_player, active_turn_card, active_river_card,
                    )
                else:
                    child_val = self._cfr_traverse(
                        child, ip_combo_idx, oop_combo_idx,
                        ip_reach, oop_reach * s_a,
                        traversing_player, active_turn_card, active_river_card,
                    )
                action_values_d[action] = child_val
                node_value += s_a * child_val

            # Phase 12D: Write regrets directly to NumPy array
            opponent_reach = oop_reach if is_ip else ip_reach
            info_idx = self._info_set_map.get(info_key, -1)
            if info_idx >= 0:
                arr = self._arrays.regrets
                base = info_idx * self._arrays.max_actions
                for a_idx in range(len(actions)):
                    regret = action_values_d[actions[a_idx]] - node_value
                    new_r = float(arr[base + a_idx]) + opponent_reach * regret
                    arr[base + a_idx] = new_r if new_r > 0.0 else 0.0

            return node_value
        else:
            self._accumulate_strategy(
                info_key, strategy,
                ip_reach if is_ip else oop_reach,
            )

            node_value = 0.0
            for action in actions:
                child = children[action]
                s_a = strategy[action]
                if is_ip:
                    child_val = self._cfr_traverse(
                        child, ip_combo_idx, oop_combo_idx,
                        ip_reach * s_a, oop_reach,
                        traversing_player, active_turn_card, active_river_card,
                    )
                else:
                    child_val = self._cfr_traverse(
                        child, ip_combo_idx, oop_combo_idx,
                        ip_reach, oop_reach * s_a,
                        traversing_player, active_turn_card, active_river_card,
                    )
                node_value += s_a * child_val

            return node_value

    def _terminal_value_fast(
        self,
        node: GameTreeNode,
        ip_combo_idx: int,
        oop_combo_idx: int,
        traversing_player: str,
        active_turn_card: str,
        active_river_card: str = "",
    ) -> float:
        """
        Compute terminal node value using precomputed equity cache.

        Phase 12A: Uses integer terminal type codes (1=fold_ip, 2=fold_oop,
        3=showdown) to avoid string comparison and getattr overhead.
        """
        pot = node.pot
        tag = node._terminal_type_int  # Phase 12A: integer type code

        if tag == 1:  # fold_ip
            return -pot / 2.0 if traversing_player == "IP" else pot / 2.0
        elif tag == 2:  # fold_oop
            return pot / 2.0 if traversing_player == "IP" else -pot / 2.0
        else:  # showdown (tag == 3 or 0)
            # Showdown: lookup precomputed equity
            cache_key = (ip_combo_idx, oop_combo_idx, active_turn_card, active_river_card)
            equity = self._equity_cache.get(cache_key)
            if equity is None:
                # Fallback: compute and cache (should rarely happen)
                ip_combo = self._ip_combos[ip_combo_idx]
                oop_combo = self._oop_combos[oop_combo_idx]
                board = list(self._board)
                if active_turn_card:
                    board = board + [Card.parse(active_turn_card)]
                if active_river_card:
                    board = board + [Card.parse(active_river_card)]
                equity = compute_showdown_equity(ip_combo, oop_combo, board)
                self._equity_cache[cache_key] = equity

            ip_ev = equity * pot - pot / 2.0
            return ip_ev if traversing_player == "IP" else -ip_ev

    def _precompute_equity_table(self, include_turn: bool, include_river: bool = False):
        """
        Precompute showdown equity for all valid matchups before iteration loop.

        Phase 13A: Uses Rust poker_core for batch equity computation when
        available. Falls back to Python compute_showdown_equity otherwise.

        CORRECTNESS: Equity depends only on (ip_hand, oop_hand, board).
        For a fixed board the result is deterministic and constant
        across all iterations. This cache is safe.
        """
        from app.solver.rust_bridge import RUST_AVAILABLE, rust_batch_equity

        logger.info(
            "Precomputing equity table: %d matchups, include_turn=%s, include_river=%s, rust=%s",
            len(self._valid_matchups), include_turn, include_river, RUST_AVAILABLE,
        )

        if RUST_AVAILABLE:
            self._precompute_equity_rust(include_turn, include_river)
        else:
            self._precompute_equity_python(include_turn, include_river)

        logger.info("Equity table precomputed: %d entries", len(self._equity_cache))

    def _precompute_equity_rust(self, include_turn: bool, include_river: bool = False):
        """Phase 13A: Rust-backed batch equity precomputation."""
        from app.solver.rust_bridge import rust_batch_equity, card_str_to_int, combo_to_ints, board_to_ints

        import poker_core

        # Convert combos and board to Rust-friendly format
        ip_hands = [combo_to_ints(c) for c in self._ip_combos]
        oop_hands = [combo_to_ints(c) for c in self._oop_combos]
        board_ints = board_to_ints(self._board)

        # ── Flop equity: single batch call ──
        flop_matchups = list(self._valid_matchups)
        flop_results = poker_core.batch_compute_equity(
            ip_hands, oop_hands, board_ints, flop_matchups
        )
        for i, (ip_idx, oop_idx) in enumerate(flop_matchups):
            self._equity_cache[(ip_idx, oop_idx, "", "")] = flop_results[i]

        # ── Turn equity: batch per turn card ──
        if include_turn and self._root:
            turn_cards = []
            self._collect_turn_cards(self._root, turn_cards)
            turn_cards = list(set(turn_cards))

            for turn_str in turn_cards:
                turn_board_ints = board_ints + [card_str_to_int(turn_str)]
                turn_matchups = []
                for ip_idx, oop_idx in self._valid_matchups:
                    hole_strs = self._combo_hole_strs_ip[ip_idx] | self._combo_hole_strs_oop[oop_idx]
                    if turn_str in hole_strs:
                        continue
                    turn_matchups.append((ip_idx, oop_idx))

                if turn_matchups:
                    results = poker_core.batch_compute_equity(
                        ip_hands, oop_hands, turn_board_ints, turn_matchups
                    )
                    for i, (ip_idx, oop_idx) in enumerate(turn_matchups):
                        self._equity_cache[(ip_idx, oop_idx, turn_str, "")] = results[i]

            # ── River equity: batch per (turn, river) pair ──
            if include_river:
                river_cards = []
                self._collect_river_cards(self._root, river_cards)
                river_cards = list(set(river_cards))

                for turn_str in turn_cards:
                    turn_card_int = card_str_to_int(turn_str)
                    for river_str in river_cards:
                        if river_str == turn_str:
                            continue
                        river_board_ints = board_ints + [turn_card_int, card_str_to_int(river_str)]
                        river_matchups = []
                        for ip_idx, oop_idx in self._valid_matchups:
                            hole_strs = self._combo_hole_strs_ip[ip_idx] | self._combo_hole_strs_oop[oop_idx]
                            if turn_str in hole_strs or river_str in hole_strs:
                                continue
                            river_matchups.append((ip_idx, oop_idx))

                        if river_matchups:
                            results = poker_core.batch_compute_equity(
                                ip_hands, oop_hands, river_board_ints, river_matchups
                            )
                            for i, (ip_idx, oop_idx) in enumerate(river_matchups):
                                self._equity_cache[(ip_idx, oop_idx, turn_str, river_str)] = results[i]

    def _precompute_equity_python(self, include_turn: bool, include_river: bool = False):
        """Original Python equity precomputation (fallback)."""
        # Flop equity
        for ip_idx, oop_idx in self._valid_matchups:
            ip_combo = self._ip_combos[ip_idx]
            oop_combo = self._oop_combos[oop_idx]
            equity = compute_showdown_equity(ip_combo, oop_combo, self._board)
            self._equity_cache[(ip_idx, oop_idx, "", "")] = equity

        # Turn equity
        if include_turn and self._root:
            turn_cards = []
            self._collect_turn_cards(self._root, turn_cards)
            turn_cards = list(set(turn_cards))

            for turn_str in turn_cards:
                turn_board = self._board + [Card.parse(turn_str)]
                for ip_idx, oop_idx in self._valid_matchups:
                    ip_combo = self._ip_combos[ip_idx]
                    oop_combo = self._oop_combos[oop_idx]
                    hole_strs = self._combo_hole_strs_ip[ip_idx] | self._combo_hole_strs_oop[oop_idx]
                    if turn_str in hole_strs:
                        continue
                    equity = compute_showdown_equity(ip_combo, oop_combo, turn_board)
                    self._equity_cache[(ip_idx, oop_idx, turn_str, "")] = equity

            # River equity
            if include_river:
                river_cards = []
                self._collect_river_cards(self._root, river_cards)
                river_cards = list(set(river_cards))

                for turn_str in turn_cards:
                    turn_card_parsed = Card.parse(turn_str)
                    for river_str in river_cards:
                        if river_str == turn_str:
                            continue
                        river_board = self._board + [turn_card_parsed, Card.parse(river_str)]
                        for ip_idx, oop_idx in self._valid_matchups:
                            hole_strs = self._combo_hole_strs_ip[ip_idx] | self._combo_hole_strs_oop[oop_idx]
                            if turn_str in hole_strs or river_str in hole_strs:
                                continue
                            ip_combo = self._ip_combos[ip_idx]
                            oop_combo = self._oop_combos[oop_idx]
                            equity = compute_showdown_equity(ip_combo, oop_combo, river_board)
                            self._equity_cache[(ip_idx, oop_idx, turn_str, river_str)] = equity

    def _collect_turn_cards(self, node: GameTreeNode, turn_cards: list[str]):
        """Recursively find all turn card strings in chance node children."""
        if node.node_type == NodeType.CHANCE:
            for child in node.children.values():
                if child.turn_card and child.turn_card not in turn_cards:
                    turn_cards.append(child.turn_card)
        for child in node.children.values():
            self._collect_turn_cards(child, turn_cards)

    def _collect_river_cards(self, node: GameTreeNode, river_cards: list[str]):
        """Recursively find all river card strings in chance node children (Phase 11A)."""
        if node.node_type == NodeType.CHANCE:
            for child in node.children.values():
                if child.river_card and child.river_card not in river_cards:
                    river_cards.append(child.river_card)
        for child in node.children.values():
            self._collect_river_cards(child, river_cards)

    def _traverse_chance_node(
        self,
        node: GameTreeNode,
        ip_combo_idx: int,
        oop_combo_idx: int,
        ip_reach: float,
        oop_reach: float,
        traversing_player: str,
        active_turn_card: str = "",
        active_river_card: str = "",
    ) -> float:
        """
        Handle chance node: average over turn or river card branches.

        Supports both turn chance nodes (flop→turn) and river chance nodes
        (turn→river, Phase 11A). Each card has equal probability. We skip
        cards that conflict with hole cards or other community cards.
        """
        hole_cards = self._combo_hole_strs_ip[ip_combo_idx] | self._combo_hole_strs_oop[oop_combo_idx]

        total_value = 0.0
        valid_count = 0

        for branch_label, child in node.children.items():
            # Determine if this is a turn or river chance branch
            if child.turn_card:
                card_str = child.turn_card
                if card_str in hole_cards:
                    continue
                child_val = self._cfr_traverse(
                    child, ip_combo_idx, oop_combo_idx,
                    ip_reach, oop_reach, traversing_player,
                    active_turn_card=card_str, active_river_card="",
                )
            elif child.river_card:
                card_str = child.river_card
                # Skip if river card conflicts with hole cards or active turn card
                if card_str in hole_cards or card_str == active_turn_card:
                    continue
                child_val = self._cfr_traverse(
                    child, ip_combo_idx, oop_combo_idx,
                    ip_reach, oop_reach, traversing_player,
                    active_turn_card=active_turn_card, active_river_card=card_str,
                )
            else:
                continue

            total_value += child_val
            valid_count += 1

        if valid_count == 0:
            return 0.0
        return total_value / valid_count

    def _tag_terminal_nodes(self, node: GameTreeNode, parent_action: str = "", parent_player: str = ""):
        """
        Pre-process tree to tag terminal nodes as fold/showdown.
        Phase 12A: Also sets _terminal_type_int (1=fold_ip, 2=fold_oop, 3=showdown)
        for fast integer comparison in the hot loop.
        """
        if node._is_terminal:
            if parent_action == "fold":
                if parent_player == "IP":
                    node._terminal_type = "fold_ip"
                    node._terminal_type_int = 1
                else:
                    node._terminal_type = "fold_oop"
                    node._terminal_type_int = 2
            else:
                node._terminal_type = "showdown"
                node._terminal_type_int = 3
            return

        for action_label, child in node.children.items():
            self._tag_terminal_nodes(child, action_label, node.player or "")

    def _build_info_set_index(self):
        """
        Phase 12C: Pre-enumerate all info sets and assign integer indices.
        
        Builds two lookup structures:
        1. _info_set_map: info_key (str) → idx (for strategy extraction)
        2. _fast_info_map: (node_int_id, combo_idx) → idx (for hot-path traversal)
        
        The _fast_info_map eliminates f-string construction and string dict
        lookup in the hot loop, using pure integer tuple keys instead.
        """
        self._info_set_map = {}
        self._info_set_actions = {}
        self._fast_info_map: dict[tuple[int, int], int] = {}
        max_actions = 0
        idx = 0
        
        num_ip = len(self._combo_strs_ip)
        num_oop = len(self._combo_strs_oop)
        
        def _walk(node: GameTreeNode):
            nonlocal idx, max_actions
            if node._is_terminal:
                return
            if node._is_chance:
                for child in node.children.values():
                    _walk(child)
                return
            # Action node: create info set entry for each combo
            actions = node._actions_tuple
            num_actions = len(actions)
            if num_actions > max_actions:
                max_actions = num_actions
            
            player = node.player
            node_int_id = node._int_id
            if player == "IP":
                combos = self._combo_strs_ip
                num_combos = num_ip
            else:
                combos = self._combo_strs_oop
                num_combos = num_oop
            
            for combo_idx, combo_str in enumerate(combos):
                key = f"{node.node_id}|{player}|{combo_str}"
                self._info_set_map[key] = idx
                self._info_set_actions[idx] = actions
                # Fast integer-keyed lookup for hot path
                self._fast_info_map[(node_int_id, combo_idx)] = idx
                idx += 1
            
            for child in node.children.values():
                _walk(child)
        
        _walk(self._root)
        
        if idx > 0 and max_actions > 0:
            self._arrays = SolverArrays(idx, max_actions)
            self._use_arrays = True
            logger.info(
                "Phase 12C: Built info-set index: %d info sets, max %d actions, "
                "array size=%d entries (%.1f KB)",
                idx, max_actions, idx * max_actions,
                (idx * max_actions * 8 * 2) / 1024,  # 2 arrays × 8 bytes/float
            )
        else:
            self._use_arrays = False
            logger.warning("Phase 12C: No info sets found, arrays disabled")

    # ── Phase 13B: Rust CFR iteration support ──────────────────────

    def _should_use_rust_cfr(self, request: SolveRequest, cancel_check=None, progress_callback=None) -> bool:
        """
        Phase 13D: Determine if Rust CFR traversal should be used.
        
        Conditions for Rust path:
        1. Rust poker_core is available with cfr_iterate
        2. Flop-only, turn-only, or turn+river solve
        3. Arrays are initialized
        
        Phase 15B: Progress/cancel callbacks are now supported natively via
        cfr_iterate_with_control — no more Python fallback required.
        """
        try:
            from app.solver.rust_bridge import RUST_AVAILABLE
            if not RUST_AVAILABLE:
                return False
            import poker_core
            if not hasattr(poker_core, 'cfr_iterate'):
                return False
        except ImportError:
            return False
        
        # Phase 15B: cancel/progress now handled in Rust via control array
        # No more Python fallback needed
        
        if not self._use_arrays or self._arrays is None:
            return False
        
        if request.include_river:
            scope = "turn+river"
        elif request.include_turn:
            scope = "turn"
        else:
            scope = "flop-only"
        logger.info("Phase 15B: %s solve → using Rust CFR traversal", scope)
        return True

    def _serialize_tree_for_rust(self, include_turn: bool = False, include_river: bool = False) -> dict:
        """
        Phase 13D: Serialize the Python game tree into flat NumPy arrays
        that Rust can process via zero-copy numpy access.
        
        Supports flop-only, turn-enabled, and river-enabled trees.
        
        Phase 13D changes from 13C:
        - node_type 5 = chance_river (new)
        - node_chance_card_abs: absolute card ints (card_str_to_int) for blocker checking
        - node_chance_equity_idx: equity sub-index per node (turn or river, 0-based)
        - ip/oop_hole_cards_abs: absolute card ints (2 slots per combo)
        - turn_idx_to_abs: maps turn equity index → absolute card int
        - equity_tables layout: (NT+1)*(NR+1) sub-tables
        - num_river_cards: new field
        
        Returns a dict with all arrays needed by poker_core.cfr_iterate().
        """
        from app.solver.rust_bridge import card_str_to_int
        
        # ── Collect all nodes via DFS ──
        all_nodes: list[GameTreeNode] = []
        def _collect(node: GameTreeNode):
            all_nodes.append(node)
            for child in node.children.values():
                _collect(child)
        _collect(self._root)
        
        num_nodes = len(all_nodes)
        num_ip = len(self._ip_combos)
        num_oop = len(self._oop_combos)
        
        # ── Collect turn cards ──
        turn_cards_list: list[str] = []
        turn_card_to_idx: dict[str, int] = {}
        if include_turn:
            tc = []
            self._collect_turn_cards(self._root, tc)
            turn_cards_list = sorted(set(tc))
            for i, tc_str in enumerate(turn_cards_list):
                turn_card_to_idx[tc_str] = i
        num_turn_cards = len(turn_cards_list)
        
        # ── Collect river cards (Phase 13D) ──
        river_cards_list: list[str] = []
        river_card_to_idx: dict[str, int] = {}
        if include_river:
            rc = []
            self._collect_river_cards(self._root, rc)
            river_cards_list = sorted(set(rc))
            for i, rc_str in enumerate(river_cards_list):
                river_card_to_idx[rc_str] = i
        num_river_cards = len(river_cards_list)
        
        # ── Allocate tree arrays ──
        node_types = np.zeros(num_nodes, dtype=np.int32)
        node_players = np.zeros(num_nodes, dtype=np.int32)
        node_pots = np.zeros(num_nodes, dtype=np.float64)
        node_num_actions = np.zeros(num_nodes, dtype=np.int32)
        node_first_child = np.zeros(num_nodes, dtype=np.int32)
        node_chance_card_abs = np.full(num_nodes, -1, dtype=np.int32)    # Phase 13D
        node_chance_equity_idx = np.full(num_nodes, -1, dtype=np.int32)  # Phase 13D
        
        # Count total edges
        total_edges = 0
        for node in all_nodes:
            if node._is_terminal:
                continue
            if node._is_chance:
                total_edges += len(node.children)
            elif node._actions_tuple:
                total_edges += len(node._actions_tuple)
        
        children_ids = np.zeros(max(total_edges, 1), dtype=np.int32)
        
        # ── Fill tree arrays ──
        edge_cursor = 0
        for node in all_nodes:
            nid = node._int_id
            if nid < 0 or nid >= num_nodes:
                continue
            
            node_pots[nid] = node.pot
            
            if node._is_terminal:
                node_types[nid] = node._terminal_type_int
                node_num_actions[nid] = 0
            elif node._is_chance:
                # Determine if this is a turn or river chance node
                branches = list(node.children.values())
                is_turn_chance = any(c.turn_card for c in branches)
                is_river_chance = any(c.river_card for c in branches)
                
                if is_turn_chance:
                    node_types[nid] = 4  # chance_turn
                elif is_river_chance:
                    node_types[nid] = 5  # chance_river (Phase 13D)
                else:
                    node_types[nid] = 4  # default to turn chance
                
                node_num_actions[nid] = len(branches)
                node_first_child[nid] = edge_cursor
                for child in branches:
                    children_ids[edge_cursor] = child._int_id
                    # Tag child with absolute card int and equity index
                    if child.turn_card:
                        node_chance_card_abs[child._int_id] = card_str_to_int(child.turn_card)
                        if child.turn_card in turn_card_to_idx:
                            node_chance_equity_idx[child._int_id] = turn_card_to_idx[child.turn_card]
                    elif child.river_card:
                        node_chance_card_abs[child._int_id] = card_str_to_int(child.river_card)
                        if child.river_card in river_card_to_idx:
                            node_chance_equity_idx[child._int_id] = river_card_to_idx[child.river_card]
                    edge_cursor += 1
            else:
                # Action node
                node_types[nid] = 0
                node_players[nid] = 0 if node.player == "IP" else 1
                actions = node._actions_tuple
                node_num_actions[nid] = len(actions)
                node_first_child[nid] = edge_cursor
                for action in actions:
                    child = node.children[action]
                    children_ids[edge_cursor] = child._int_id
                    edge_cursor += 1
        
        # ── Build info_map ──
        max_combos = max(num_ip, num_oop, 1)
        info_map = np.full(num_nodes * max_combos, -1, dtype=np.int32)
        
        for (node_int_id, combo_idx), info_idx in self._fast_info_map.items():
            flat_key = node_int_id * max_combos + combo_idx
            if flat_key < len(info_map):
                info_map[flat_key] = info_idx
        
        # ── Build hole card blocker arrays (Phase 13D: absolute card ints, 2 per combo) ──
        ip_hole_cards_abs = np.full(num_ip * 2, -1, dtype=np.int32)
        oop_hole_cards_abs = np.full(num_oop * 2, -1, dtype=np.int32)
        
        for combo_idx in range(num_ip):
            for h, card_str in enumerate(sorted(self._combo_hole_strs_ip[combo_idx])):
                if h < 2:
                    ip_hole_cards_abs[combo_idx * 2 + h] = card_str_to_int(card_str)
        for combo_idx in range(num_oop):
            for h, card_str in enumerate(sorted(self._combo_hole_strs_oop[combo_idx])):
                if h < 2:
                    oop_hole_cards_abs[combo_idx * 2 + h] = card_str_to_int(card_str)
        
        # ── Build turn_idx_to_abs mapping (Phase 13D) ──
        # Index 0 = no turn card (-1), index i+1 = absolute card int for turn card i
        turn_idx_to_abs = np.full(num_turn_cards + 1, -1, dtype=np.int32)
        for tc_str, tc_idx in turn_card_to_idx.items():
            turn_idx_to_abs[tc_idx + 1] = card_str_to_int(tc_str)
        
        # ── Build equity tables (Phase 13D: 2D layout) ──
        # Layout: (NT+1) * (NR+1) sub-tables, each of size num_ip * num_oop
        # equity_key = turn_idx * (NR+1) + river_idx
        # turn_idx: 0=no turn, 1..NT = turn cards
        # river_idx: 0=no river, 1..NR = river cards
        table_size = num_ip * num_oop
        nr1 = num_river_cards + 1
        num_equity_keys = (num_turn_cards + 1) * nr1
        equity_tables = np.zeros(num_equity_keys * table_size, dtype=np.float64)
        
        for (ip_idx, oop_idx, turn_card, river_card), eq in self._equity_cache.items():
            if turn_card == "" and river_card == "":
                # Flop equity → key 0
                equity_key = 0
            elif turn_card != "" and turn_card in turn_card_to_idx and river_card == "":
                # Turn-only equity → key (tc_idx+1) * (NR+1) + 0
                tc_idx = turn_card_to_idx[turn_card]
                equity_key = (tc_idx + 1) * nr1
            elif turn_card != "" and turn_card in turn_card_to_idx and river_card != "" and river_card in river_card_to_idx:
                # Turn+river equity → key (tc_idx+1) * (NR+1) + (rc_idx+1)
                tc_idx = turn_card_to_idx[turn_card]
                rc_idx = river_card_to_idx[river_card]
                equity_key = (tc_idx + 1) * nr1 + (rc_idx + 1)
            else:
                continue  # unmapped equity entry
            
            offset = equity_key * table_size + ip_idx * num_oop + oop_idx
            if offset < len(equity_tables):
                equity_tables[offset] = eq
        
        # ── Build matchup arrays ──
        matchup_ip = np.array([m[0] for m in self._valid_matchups], dtype=np.int32)
        matchup_oop = np.array([m[1] for m in self._valid_matchups], dtype=np.int32)
        
        logger.info(
            "Phase 13D: Tree serialized: %d nodes, %d edges, %d info_map, "
            "%d equity keys (%d turn, %d river cards), %d matchups, "
            "include_turn=%s, include_river=%s",
            num_nodes, edge_cursor, len(info_map), num_equity_keys,
            num_turn_cards, num_river_cards, len(self._valid_matchups),
            include_turn, include_river,
        )
        
        return {
            'node_types': node_types,
            'node_players': node_players,
            'node_pots': node_pots,
            'node_num_actions': node_num_actions,
            'node_first_child': node_first_child,
            'children_ids': children_ids,
            'node_chance_card_abs': node_chance_card_abs,
            'node_chance_equity_idx': node_chance_equity_idx,
            'ip_hole_cards_abs': ip_hole_cards_abs,
            'oop_hole_cards_abs': oop_hole_cards_abs,
            'turn_idx_to_abs': turn_idx_to_abs,
            'num_turn_cards': num_turn_cards,
            'num_river_cards': num_river_cards,
            'info_map': info_map,
            'max_combos': max_combos,
            'equity_tables': equity_tables,
            'num_ip': num_ip,
            'num_oop': num_oop,
            'matchup_ip': matchup_ip,
            'matchup_oop': matchup_oop,
            'root_node_id': self._root._int_id,
        }

    def _run_iterations_rust(self, max_iter: int, start_time: float, setup_time: float,
                             include_turn: bool = False, include_river: bool = False,
                             cancel_check=None, progress_callback=None,
                             budget=None, **kwargs) -> int:
        """
        Phase 15B: Run CFR+ iterations in Rust with progress/cancel support.
        
        When cancel_check or progress_callback are provided, iterations are run
        in chunks (CHUNK_SIZE at a time). Between chunks, Python checks for
        cancellation and reports progress. This avoids GIL conflicts with numpy.
        
        When no control is needed, uses the original single cfr_iterate call
        for zero overhead.
        
        Control model:
          - Chunked: Rust runs CHUNK_SIZE iterations, returns to Python, repeat
          - Progress: reported between chunks (iteration count / max)
          - Cancel: checked between chunks (cooperative, not mid-iteration)
          - Regrets/strategy arrays: valid after any completed chunk
        
        Returns: number of iterations actually completed.
        """
        import poker_core
        
        # Serialize tree to flat arrays (done once, reused across chunks)
        tree_data = self._serialize_tree_for_rust(
            include_turn=include_turn, include_river=include_river,
        )
        
        num_matchups = len(tree_data['matchup_ip'])
        use_parallel = False
        
        serialize_time = time.time() - start_time
        if include_river:
            scope = "turn+river"
        elif include_turn:
            scope = "turn"
        else:
            scope = "flop"
        mode = "serial"
        
        has_control = cancel_check is not None or progress_callback is not None
        
        # Phase 16A: budget for early stopping (passed as named parameter)
        from app.solver.solve_policy import ConvergenceTracker, StopReason

        if has_control:
            # Phase 16B: dynamic chunk size to reduce overhead on trivial/light solves
            # Benchmark showed ~20-40% overhead from chunking on fast solves.
            # Trivial/light: larger chunks = less overhead (fast anyway)
            # Moderate+: 25 per chunk = responsive progress/cancel
            CHUNK_SIZE = 50 if (budget and budget.target_iterations <= 100) else 25
            
            logger.info("Phase 15B: Rust CFR (%s, %s, %d matchups) starting %d iterations chunked/%d with control (serialize=%.3fs)",
                        scope, mode, num_matchups, max_iter, CHUNK_SIZE, serialize_time - setup_time)
            
            total_completed = 0
            was_cancelled = False
            convergence = 0.0
            
            # Phase 16A: convergence tracker for early stopping
            conv_tracker = ConvergenceTracker(budget) if budget else None
            early_stop_reason = None
            
            while total_completed < max_iter:
                # Check cancel before each chunk
                if cancel_check:
                    try:
                        if cancel_check():
                            was_cancelled = True
                            self._stop_reason = StopReason.CANCELLED
                            logger.info("Phase 15B: Cancel at iteration %d/%d", total_completed, max_iter)
                            break
                    except Exception:
                        pass
                
                # Determine chunk size (don't overshoot)
                remaining = max_iter - total_completed
                chunk = min(CHUNK_SIZE, remaining)
                
                # Run chunk in Rust (regrets/strategy_sums accumulate in-place)
                convergence = poker_core.cfr_iterate(
                    tree_data['node_types'],
                    tree_data['node_players'],
                    tree_data['node_pots'],
                    tree_data['node_num_actions'],
                    tree_data['node_first_child'],
                    tree_data['children_ids'],
                    tree_data['node_chance_card_abs'],
                    tree_data['node_chance_equity_idx'],
                    tree_data['ip_hole_cards_abs'],
                    tree_data['oop_hole_cards_abs'],
                    tree_data['turn_idx_to_abs'],
                    tree_data['num_turn_cards'],
                    tree_data['num_river_cards'],
                    tree_data['info_map'],
                    tree_data['max_combos'],
                    self._arrays.regrets,
                    self._arrays.strategy_sums,
                    self._arrays.max_actions,
                    tree_data['equity_tables'],
                    tree_data['num_ip'],
                    tree_data['num_oop'],
                    tree_data['matchup_ip'],
                    tree_data['matchup_oop'],
                    chunk,
                    tree_data['root_node_id'],
                    use_parallel,
                )
                
                total_completed += chunk
                self._iteration_count = total_completed
                
                # Phase 16A: track convergence and check early stopping
                if conv_tracker:
                    conv_tracker.record(convergence)
                    early_stop_reason = conv_tracker.should_stop(total_completed, convergence)
                
                # Report progress after each chunk (Phase 15C: proper SolveProgressInfo)
                if progress_callback:
                    try:
                        progress_info = SolveProgressInfo()
                        progress_info.iteration = total_completed
                        progress_info.total_iterations = max_iter
                        progress_info.convergence_metric = convergence
                        progress_info.elapsed_seconds = time.time() - start_time
                        progress_info.status = "running"
                        progress_callback(progress_info)
                    except Exception:
                        pass
                
                # Phase 16A: early stop if convergence conditions met
                if early_stop_reason and not was_cancelled:
                    self._stop_reason = early_stop_reason
                    logger.info(
                        "Phase 16A: Early stop at iteration %d/%d, reason=%s, convergence=%.6f",
                        total_completed, max_iter, early_stop_reason.value, convergence,
                    )
                    break
            
            # If loop ended normally (no early stop, no cancel)
            if not early_stop_reason and not was_cancelled:
                self._stop_reason = StopReason.MAX_ITERATIONS
            
            elapsed = time.time() - start_time
            status_label = "CANCELLED" if was_cancelled else (
                f"early-stop({early_stop_reason.value})" if early_stop_reason else "complete"
            )
            logger.info(
                "Phase 16A: Rust CFR (%s, %s) %s: %d/%d iterations, convergence=%.6f, elapsed=%.2fs (%.1f iter/s)",
                scope, mode, status_label, total_completed, max_iter, convergence, elapsed,
                total_completed / max(elapsed - setup_time, 0.001),
            )
            
            return total_completed
        
        else:
            # No control needed — single call, zero overhead
            logger.info("Phase 15B: Rust CFR (%s, %s, %d matchups) starting %d iterations (serialize=%.3fs)",
                        scope, mode, num_matchups, max_iter, serialize_time - setup_time)
            
            convergence = poker_core.cfr_iterate(
                tree_data['node_types'],
                tree_data['node_players'],
                tree_data['node_pots'],
                tree_data['node_num_actions'],
                tree_data['node_first_child'],
                tree_data['children_ids'],
                tree_data['node_chance_card_abs'],
                tree_data['node_chance_equity_idx'],
                tree_data['ip_hole_cards_abs'],
                tree_data['oop_hole_cards_abs'],
                tree_data['turn_idx_to_abs'],
                tree_data['num_turn_cards'],
                tree_data['num_river_cards'],
                tree_data['info_map'],
                tree_data['max_combos'],
                self._arrays.regrets,
                self._arrays.strategy_sums,
                self._arrays.max_actions,
                tree_data['equity_tables'],
                tree_data['num_ip'],
                tree_data['num_oop'],
                tree_data['matchup_ip'],
                tree_data['matchup_oop'],
                max_iter,
                tree_data['root_node_id'],
                use_parallel,
            )
            
            self._iteration_count = max_iter
            
            elapsed = time.time() - start_time
            logger.info(
                "Phase 15B: Rust CFR (%s, %s) complete: %d iterations, convergence=%.6f, elapsed=%.2fs (%.1f iter/s)",
                scope, mode, max_iter, convergence, elapsed,
                max_iter / max(elapsed - setup_time, 0.001),
            )
            
            return max_iter


    def _run_iterations_python(
        self, max_iter: int, log_interval: int,
        start_time: float, setup_time: float,
        cancel_check, progress_callback,
    ) -> int:
        """
        Phase 16C: Python CFR+ iteration loop — EMERGENCY FALLBACK ONLY.
        
        This path is NOT the primary engine. It exists solely as a safety net
        when the Rust poker_core extension is not available (e.g., during
        development or on unsupported platforms).
        
        In production, _run_iterations_rust is ALWAYS used for all solve types
        (flop, turn, river). This fallback is ~50-100x slower than Rust.
        """
        logger.warning(
            "Phase 16C: Using PYTHON FALLBACK iteration loop (Rust unavailable). "
            "This is ~50-100x slower than the Rust path."
        )
        iteration = 0
        for iteration in range(1, max_iter + 1):
            self._iteration_count = iteration
            # Check cancellation
            if cancel_check and cancel_check():
                self._cancelled = True
                logger.info("CFR+ solve cancelled at iteration %d", iteration)
                break

            # For each valid matchup, traverse for both players
            for ip_idx, oop_idx in self._valid_matchups:
                # Traverse for IP
                self._cfr_traverse(
                    self._root, ip_idx, oop_idx,
                    1.0, 1.0, "IP",
                )
                # Traverse for OOP
                self._cfr_traverse(
                    self._root, ip_idx, oop_idx,
                    1.0, 1.0, "OOP",
                )

            # Progress (adaptive interval)
            if iteration % log_interval == 0 or iteration == 1 or iteration == max_iter:
                convergence = self._compute_convergence()
                elapsed = time.time() - start_time
                # ETA estimation
                iter_rate = iteration / max(elapsed - setup_time, 0.001)
                eta_seconds = (max_iter - iteration) / iter_rate if iter_rate > 0 else 0.0

                self._progress = SolveProgressInfo(
                    iteration=iteration,
                    total_iterations=max_iter,
                    convergence_metric=convergence,
                    elapsed_seconds=elapsed,
                    status="solving",
                )

                if progress_callback:
                    progress_callback(self._progress)

                logger.info(
                    "CFR+ iter %d/%d: convergence=%.6f elapsed=%.1fs ETA=%.1fs",
                    iteration, max_iter, convergence, elapsed, eta_seconds,
                )
        
        return iteration

    def _compute_convergence(self) -> float:
        """
        Approximate convergence metric: average positive regret per info set,
        normalized by iteration count.

        HONEST NOTE: This is NOT exact exploitability. Computing exact
        exploitability requires a best-response traversal which is not
        implemented. This metric generally decreases as the solver converges
        and approaches 0 at Nash equilibrium, but its absolute value is not
        directly comparable to exploitability in bb/100.
        
        Phase 12D: Vectorized computation over NumPy arrays.
        """
        if not self._use_arrays or self._arrays is None:
            return float('inf')
        
        regrets = self._arrays.regrets
        positive = np.maximum(regrets, 0.0)
        total_regret = float(positive.sum())
        count = int(np.count_nonzero(positive))
        
        if count == 0:
            return 0.0
        norm = max(self._iteration_count, 1)
        return total_regret / (count * norm)

    def _precompute_valid_matchups(self):
        """Find all (ip_idx, oop_idx) pairs where hands don't share cards."""
        self._valid_matchups = []
        for i, ip_combo in enumerate(self._ip_combos):
            ip_cards = {(c.rank.value, c.suit.value) for c in ip_combo}
            for j, oop_combo in enumerate(self._oop_combos):
                oop_cards = {(c.rank.value, c.suit.value) for c in oop_combo}
                if not ip_cards & oop_cards:
                    self._valid_matchups.append((i, j))

    def solve(
        self,
        request: SolveRequest,
        progress_callback: Optional[Callable[[SolveProgressInfo], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> SolveOutput:
        """
        Run CFR+ solving on the given request.

        This is the main entry point. It:
        1. Validates inputs and checks size limits
        2. Builds the action tree
        3. Expands ranges to concrete combos
        4. Runs CFR+ iterations
        5. Extracts average strategies

        Args:
            request: Solve configuration
            progress_callback: Called with progress info each iteration
            cancel_check: Returns True if solve should be cancelled

        Returns:
            SolveOutput with real strategies
        """
        start_time = time.time()
        self._cancelled = False
        self._equity_cache = {}
        # Phase 12D: reset array state (arrays are single source of truth)
        self._arrays = None
        self._info_set_map = {}
        self._info_set_actions = {}
        self._fast_info_map = {}
        self._use_arrays = False

        # ── Step 1: Parse board ──
        board_cards = [Card.parse(c) for c in request.board]
        if len(board_cards) < 3:
            raise ValueError(f"Need at least 3 board cards (flop), got {len(board_cards)}")
        self._board = board_cards

        # ── Step 2: Expand ranges to combos ──
        self._ip_combos = expand_range_to_combos(request.ip_range, board_cards)
        self._oop_combos = expand_range_to_combos(request.oop_range, board_cards)

        if len(self._ip_combos) == 0:
            raise ValueError("IP range has 0 valid combos after removing board blockers")
        if len(self._oop_combos) == 0:
            raise ValueError("OOP range has 0 valid combos after removing board blockers")
        # Phase 15A: per-street combo limits (tighter for turn/river)
        if request.include_river:
            combo_limit = MAX_COMBOS_PER_SIDE_RIVER
            limit_note = " (river solve limit)"
        elif request.include_turn:
            combo_limit = MAX_COMBOS_PER_SIDE_TURN
            limit_note = " (turn solve limit)"
        else:
            combo_limit = MAX_COMBOS_PER_SIDE
            limit_note = ""
        if len(self._ip_combos) > combo_limit:
            raise ValueError(
                f"IP range has {len(self._ip_combos)} combos, max allowed is {combo_limit}{limit_note}. "
                f"Use a smaller range."
            )
        if len(self._oop_combos) > combo_limit:
            raise ValueError(
                f"OOP range has {len(self._oop_combos)} combos, max allowed is {combo_limit}{limit_note}. "
                f"Use a smaller range."
            )

        # ── Step 3: Find valid matchups (no card overlap) ──
        self._precompute_valid_matchups()
        if len(self._valid_matchups) > MAX_TOTAL_MATCHUPS:
            raise ValueError(
                f"Too many matchups ({len(self._valid_matchups)}), max {MAX_TOTAL_MATCHUPS}. "
                f"Use smaller ranges."
            )
        if len(self._valid_matchups) == 0:
            raise ValueError("No valid matchups (all combos overlap with board or each other)")

        # Deterministic mode: sort combos and matchups for reproducibility
        if request.deterministic:
            self._ip_combos.sort(key=lambda c: (str(c[0]), str(c[1])))
            self._oop_combos.sort(key=lambda c: (str(c[0]), str(c[1])))
            self._precompute_valid_matchups()  # re-compute after sort
            self._valid_matchups.sort()

        # ── Step 3b: Precompute performance caches ──
        # Pre-format combo strings (eliminates repeated str() calls in hot loop)
        self._combo_strs_ip = [combo_to_str(c) for c in self._ip_combos]
        self._combo_strs_oop = [combo_to_str(c) for c in self._oop_combos]
        # Pre-format hole card string sets for blocker checks at chance nodes
        self._combo_hole_strs_ip = [{f"{c}" for c in combo} for combo in self._ip_combos]
        self._combo_hole_strs_oop = [{f"{c}" for c in combo} for combo in self._oop_combos]

        # ── Step 4: Build action tree ──
        config = TreeConfig(
            starting_pot=request.pot,
            effective_stack=request.effective_stack,
            board=tuple(request.board),
            flop_bet_sizes=tuple(request.bet_sizes),
            flop_raise_sizes=tuple(request.raise_sizes),
            turn_bet_sizes=tuple(request.turn_bet_sizes),
            turn_raise_sizes=tuple(request.turn_raise_sizes),
            river_bet_sizes=tuple(request.river_bet_sizes) if request.river_bet_sizes else (0.5, 1.0),
            river_raise_sizes=tuple(request.river_raise_sizes) if request.river_raise_sizes else (),
            max_raises_per_street=request.max_raises,
            include_turn=request.include_turn,
            max_turn_cards=request.max_turn_cards,
            # Phase 10A: wire turn-specific abstraction
            turn_bet_sizes_override=tuple(request.turn_bet_sizes),
            turn_raise_sizes_override=tuple(request.turn_raise_sizes),
            turn_max_raises=request.turn_max_raises,
            # Phase 11A: river support
            include_river=request.include_river,
            max_river_cards=request.max_river_cards,
            river_bet_sizes_override=tuple(request.river_bet_sizes) if request.river_bet_sizes else (0.5, 1.0),
            river_raise_sizes_override=tuple(request.river_raise_sizes) if request.river_raise_sizes else (),
            river_max_raises=request.river_max_raises,
        )
        self._root, tree_stats = build_tree_skeleton(config)

        max_nodes = MAX_TREE_NODES_RIVER if request.include_river else (
            MAX_TREE_NODES_TURN if request.include_turn else MAX_TREE_NODES_FLOP
        )
        if tree_stats.total_nodes > max_nodes:
            raise ValueError(
                f"Action tree too large ({tree_stats.total_nodes} nodes, max {max_nodes}). "
                f"Reduce bet sizes or raise limit."
            )

        self._pot = request.pot

        # Tag terminal nodes
        self._tag_terminal_nodes(self._root)

        # ── Step 4b: Precompute equity table ──
        # This is the single biggest performance win. For a fixed board,
        # compute_showdown_equity is constant across iterations. Precomputing
        # eliminates ~62% of solver runtime (based on profiling).
        self._precompute_equity_table(request.include_turn, request.include_river)

        # ── Step 4c: Build info-set integer index (Phase 12C) ──
        self._build_info_set_index()

        setup_time = time.time() - start_time
        logger.info(
            "CFR+ solve starting: %d IP combos, %d OOP combos, %d matchups, %d tree nodes, "
            "%d iterations, equity_cache=%d entries, info_sets=%d (setup %.2fs)",
            len(self._ip_combos), len(self._oop_combos),
            len(self._valid_matchups), tree_stats.total_nodes,
            request.max_iterations, len(self._equity_cache),
            len(self._info_set_map), setup_time,
        )

        # ── Step 5: CFR+ iterations (Phase 16A: adaptive budget) ──
        from app.solver.solve_policy import (
            SolveDifficulty, compute_iteration_budget, ConvergenceTracker,
            StopReason, classify_solve_quality,
        )

        # Classify difficulty
        difficulty = SolveDifficulty(
            ip_combos=len(self._ip_combos),
            oop_combos=len(self._oop_combos),
            matchups=len(self._valid_matchups),
            tree_nodes=tree_stats.total_nodes,
            street_depth=config.street_depth,
            turn_cards=tree_stats.turn_cards_explored,
            river_cards=tree_stats.river_cards_explored,
        )
        difficulty.classify()

        # Determine preset from request metadata (default: standard)
        preset = getattr(request, '_preset', 'standard') or 'standard'

        # Compute adaptive budget
        budget = compute_iteration_budget(
            difficulty, preset=preset,
            user_max_iterations=request.max_iterations,
        )

        max_iter = min(budget.max_iterations, MAX_ITERATIONS)
        self._budget = budget
        self._difficulty = difficulty
        self._stop_reason = StopReason.MAX_ITERATIONS  # default

        logger.info(
            "Phase 16A: difficulty=%s preset=%s budget=(%d/%d/%d) conv_target=%.4f patience=%d",
            difficulty.grade, preset, budget.min_iterations,
            budget.target_iterations, budget.max_iterations,
            budget.convergence_target, budget.patience,
        )

        # Adaptive log interval: more frequent for short solves
        log_interval = 5 if max_iter <= 100 else 10

        # ── Phase 13C: Rust vs Python iteration dispatch ──
        use_rust_cfr = self._should_use_rust_cfr(request, cancel_check, progress_callback)

        if use_rust_cfr:
            iteration = self._run_iterations_rust(
                max_iter, start_time, setup_time,
                include_turn=request.include_turn,
                include_river=request.include_river,
                cancel_check=cancel_check,
                progress_callback=progress_callback,
                budget=budget,
            )
        else:
            iteration = self._run_iterations_python(
                max_iter, log_interval, start_time, setup_time,
                cancel_check, progress_callback,
            )

        # ── Step 6: Extract results (Phase 12D: arrays are already the source of truth) ──
        elapsed = time.time() - start_time
        convergence = self._compute_convergence()

        strategies = self._extract_strategies()

        # ── Step 7: Post-solve validation ──
        from app.solver.solver_validation import validate_solve_output
        validation = validate_solve_output(strategies, iteration, convergence)

        # ── Step 8: Best-response exploitability ──
        from app.solver.best_response import compute_exploitability
        exploit_result = compute_exploitability(self, SolveOutput(
            strategies=strategies, iterations=iteration,
        ))

        # Phase 16A: determine final stop reason and quality
        stop_reason = getattr(self, '_stop_reason', StopReason.MAX_ITERATIONS)
        quality = classify_solve_quality(
            stop_reason, convergence, budget.convergence_target,
            iteration, budget.target_iterations,
        )

        output = SolveOutput(
            strategies=strategies,
            iterations=iteration if not self._cancelled else iteration,
            elapsed_seconds=round(elapsed, 2),
            convergence_metric=round(convergence, 6),
            tree_nodes=tree_stats.total_nodes,
            ip_combos=len(self._ip_combos),
            oop_combos=len(self._oop_combos),
            matchups=len(self._valid_matchups),
            converged=convergence < 0.01,
            exploitability_mbb=round(exploit_result.exploitability_mbb_per_hand, 2),
            exploitability_result=exploit_result.to_dict(),
            stop_reason=stop_reason.value,
            metadata={
                "algorithm": "CFR+ (Tammelin 2014)",
                "scope": f"{config.street_depth.replace('_', ' ')} subgame",
                "street_depth": config.street_depth,
                "board": request.board,
                "ip_range": request.ip_range,
                "oop_range": request.oop_range,
                "pot": request.pot,
                "effective_stack": request.effective_stack,
                # Phase 10A: detailed action abstraction metadata
                "flop_bet_sizes": request.bet_sizes,
                "flop_raise_sizes": request.raise_sizes,
                "turn_bet_sizes": request.turn_bet_sizes,
                "turn_raise_sizes": request.turn_raise_sizes,
                "turn_max_raises": request.turn_max_raises,
                "max_raises_per_street": request.max_raises,
                "action_abstraction": (
                    f"Flop: {len(request.bet_sizes)} bet sizes "
                    f"({', '.join(f'{int(s*100)}%' for s in request.bet_sizes)}), "
                    f"{len(request.raise_sizes)} raise sizes; "
                    + (f"Turn: {len(request.turn_bet_sizes)} bet sizes, "
                       f"{len(request.turn_raise_sizes)} raise sizes, "
                       f"max {request.turn_max_raises} raises; "
                       if request.include_turn else "Turn: not included; ")
                    + (f"River: {len(request.river_bet_sizes)} bet sizes, "
                       f"{len(request.river_raise_sizes)} raise sizes, "
                       f"max {request.river_max_raises} raises"
                       if request.include_river else "River: not included")
                ),
                "deterministic": request.deterministic,
                "include_turn": request.include_turn,
                "include_river": request.include_river,
                "turn_cards_explored": tree_stats.turn_cards_explored,
                "river_cards_explored": tree_stats.river_cards_explored,
                "river_bet_sizes": request.river_bet_sizes if request.include_river else [],
                "river_raise_sizes": request.river_raise_sizes if request.include_river else [],
                "river_max_raises": request.river_max_raises if request.include_river else 0,
                "honest_note": (
                    f"Exploitability is exact within the game abstraction "
                    f"({config.street_depth.replace('_', ' ')}, fixed bet sizes). "
                    f"NOT full-NLHE exploitability."
                ),
                "cancelled": self._cancelled,
                "validation": validation.to_dict(),
                "exploitability": exploit_result.to_dict(),
                # Phase 16A: adaptive solve metadata
                "stop_reason": stop_reason.value,
                "stop_reason_label": stop_reason.label_ru,
                "stop_reason_icon": stop_reason.icon,
                "difficulty_grade": difficulty.grade,
                "adaptive_budget": {
                    "min_iterations": budget.min_iterations,
                    "target_iterations": budget.target_iterations,
                    "max_iterations": budget.max_iterations,
                    "convergence_target": budget.convergence_target,
                    "patience": budget.patience,
                },
                "solve_quality": quality,
            },
        )

        logger.info(
            "CFR+ solve complete: %d iterations, convergence=%.6f, exploitability=%.2f mbb/hand, "
            "stop_reason=%s, quality=%s, elapsed=%.1fs, validation=%s",
            output.iterations, output.convergence_metric, output.exploitability_mbb,
            stop_reason.value, quality.get("quality_class", "?"),
            output.elapsed_seconds, "PASS" if validation.passed else "FAIL",
        )

        return output

    def _extract_strategies(self) -> dict[str, dict[str, dict[str, float]]]:
        """
        Extract average strategies organized by node_id.

        Returns: node_id → {combo_str → {action → frequency}}
        
        Phase 12D: Reads from NumPy arrays (single source of truth).
        """
        strategies: dict[str, dict[str, dict[str, float]]] = {}

        for info_key, info_idx in self._info_set_map.items():
            parts = info_key.split("|")
            if len(parts) != 3:
                continue
            node_id, player, combo_str = parts

            actions = self._info_set_actions[info_idx]
            avg_strategy = self._get_average_strategy(info_key, list(actions))

            if node_id not in strategies:
                strategies[node_id] = {}
            strategies[node_id][combo_str] = avg_strategy

        return strategies


# ── Validation helpers ─────────────────────────────────────────

def validate_solve_request(request: SolveRequest) -> tuple[bool, str]:
    """Validate a solve request before starting.
    
    Includes turn-specific guardrails to prevent pathological configurations.
    """
    try:
        if len(request.board) < 3:
            return False, "Need at least 3 board cards"
        if len(request.board) > 5:
            return False, "Max 5 board cards"

        # Turn-specific board validation
        if request.include_turn and len(request.board) > 3:
            return False, (
                f"Cannot enable turn dealing with {len(request.board)}-card board. "
                "Turn support requires exactly 3 board cards (flop only)."
            )

        # Phase 11A: River requires turn
        if request.include_river and not request.include_turn:
            return False, "River support requires turn to be enabled (include_turn=True)."

        # Validate board cards
        for c in request.board:
            Card.parse(c)

        # Check for duplicate board cards
        if len(set(request.board)) != len(request.board):
            return False, "Duplicate board cards"

        board_cards = [Card.parse(c) for c in request.board]

        # Validate ranges
        ip_combos = expand_range_to_combos(request.ip_range, board_cards)
        oop_combos = expand_range_to_combos(request.oop_range, board_cards)

        if len(ip_combos) == 0:
            return False, "IP range has 0 valid combos"
        if len(oop_combos) == 0:
            return False, "OOP range has 0 valid combos"

        # Tighter combo limit for turn/river-enabled solves
        if request.include_river:
            combo_limit = MAX_COMBOS_PER_SIDE_RIVER
            limit_note = " (tight limit for river solves)"
        elif request.include_turn:
            combo_limit = MAX_COMBOS_PER_SIDE_TURN
            limit_note = " (tighter limit for turn solves)"
        else:
            combo_limit = MAX_COMBOS_PER_SIDE
            limit_note = ""
        if len(ip_combos) > combo_limit:
            return False, f"IP range too large ({len(ip_combos)} combos, max {combo_limit}{limit_note})"
        if len(oop_combos) > combo_limit:
            return False, f"OOP range too large ({len(oop_combos)} combos, max {combo_limit}{limit_note})"

        # Cap max_turn_cards
        if request.include_turn:
            if request.max_turn_cards > MAX_TURN_CARDS:
                return False, (
                    f"max_turn_cards={request.max_turn_cards} exceeds safety cap of {MAX_TURN_CARDS}. "
                    "Turn support is computationally expensive; use fewer cards."
                )
            # Phase 10A: relaxed guard — adaptive iteration cap handles heavy solves
            if request.max_iterations > 1000 and request.max_turn_cards > 5:
                return False, (
                    f"Turn solve with {request.max_turn_cards} cards and {request.max_iterations} iterations "
                    "is too expensive. Reduce iterations to ≤1000 or turn cards to ≤5."
                )

        # Phase 11A: Cap max_river_cards
        if request.include_river:
            if request.max_river_cards > MAX_RIVER_CARDS:
                return False, (
                    f"max_river_cards={request.max_river_cards} exceeds safety cap of {MAX_RIVER_CARDS}. "
                    "River support is computationally expensive; use fewer cards."
                )

        # Check tree size
        config = TreeConfig(
            starting_pot=request.pot,
            effective_stack=request.effective_stack,
            board=tuple(request.board),
            flop_bet_sizes=tuple(request.bet_sizes),
            flop_raise_sizes=tuple(request.raise_sizes),
            max_raises_per_street=request.max_raises,
            include_turn=request.include_turn,
            max_turn_cards=request.max_turn_cards,
            turn_bet_sizes_override=tuple(request.turn_bet_sizes),
            turn_raise_sizes_override=tuple(request.turn_raise_sizes),
            turn_max_raises=request.turn_max_raises,
            include_river=request.include_river,
            max_river_cards=request.max_river_cards,
            river_bet_sizes_override=tuple(request.river_bet_sizes) if request.river_bet_sizes else (0.5, 1.0),
            river_raise_sizes_override=tuple(request.river_raise_sizes) if request.river_raise_sizes else (),
            river_max_raises=request.river_max_raises,
        )
        _, stats = build_tree_skeleton(config)
        max_nodes = MAX_TREE_NODES_RIVER if request.include_river else (
            MAX_TREE_NODES_TURN if request.include_turn else MAX_TREE_NODES_FLOP
        )
        if stats.total_nodes > max_nodes:
            return False, f"Tree too large ({stats.total_nodes} nodes, max {max_nodes})"

        return True, ""

    except Exception as e:
        return False, str(e)
