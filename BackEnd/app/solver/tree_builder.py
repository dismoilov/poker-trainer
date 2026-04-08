"""
Game tree builder — constructs game trees for the CFR+ solver.

This module defines the data structures and builder logic needed to
construct a game tree that the CFR+ solver consumes.

Supports:
- Flop subgames with rich action abstraction (multiple bet sizes + overbets)
- Flop+turn subgames with chance nodes (turn card dealing)
- Turn action trees with configurable bet sizes and raise support
- Flop+turn+river subgames (Phase 11A: minimal river layer)

HONEST NOTE: Turn and river support are real but bounded — configurable
bet/raise sizes and capped card counts for computation safety.
River is narrower than turn (2 bet sizes, 0 raises by default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.poker_engine.ranges import ParsedRange, parse_range


class NodeType(Enum):
    """Type of node in the game tree."""
    CHANCE = "chance"       # Dealer deals cards
    ACTION = "action"       # Player makes a decision
    TERMINAL = "terminal"   # Hand is over (fold/showdown)


@dataclass
class BetSizing:
    """Bet sizing option as fraction of pot."""
    fraction: float     # e.g. 0.33, 0.67, 1.0
    label: str = ""

    def __post_init__(self):
        if not self.label:
            pct = int(self.fraction * 100)
            self.label = f"{pct}%"


@dataclass
class RaiseSizing:
    """Raise sizing option as multiplier of facing bet."""
    multiplier: float   # e.g. 2.5, 3.0
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = f"{self.multiplier}x"


@dataclass(frozen=True)
class TreeConfig:
    """
    Configuration for building a game tree.

    This defines all the parameters the CFR+ solver needs to
    construct its internal game tree representation.

    Phase 10A: Expanded action abstraction
    - Flop: 7 bet sizes (25-125%), 2 raise sizes, overbet support
    - Turn: 4 bet sizes (33-100%), raise support (2.5x, 1 max raise)
    """
    # Ranges
    ip_range_str: str = ""
    oop_range_str: str = ""

    # Board
    board: tuple[str, ...] = ()

    # Geometry
    starting_pot: float = 6.5
    effective_stack: float = 97.0

    # Bet tree parameters (Phase 10A: richer abstraction)
    flop_bet_sizes: tuple[float, ...] = (0.25, 0.33, 0.5, 0.67, 0.75, 1.0, 1.25)
    flop_raise_sizes: tuple[float, ...] = (2.5, 3.5)
    turn_bet_sizes: tuple[float, ...] = (0.33, 0.5, 0.75, 1.0)
    turn_raise_sizes: tuple[float, ...] = (2.5,)
    river_bet_sizes: tuple[float, ...] = (0.5, 0.75, 1.0)
    river_raise_sizes: tuple[float, ...] = (2.5,)

    # Limits
    max_raises_per_street: int = 3
    all_in_threshold: float = 0.67  # go all-in if remaining stack < X * pot

    # Turn support (Phase 6A, expanded Phase 10A)
    include_turn: bool = False
    max_turn_cards: int = 8  # max turn cards to explore (0 = all remaining)
    turn_bet_sizes_override: tuple[float, ...] = (0.33, 0.5, 0.75, 1.0)  # richer turn tree
    turn_raise_sizes_override: tuple[float, ...] = (2.5,)  # raises on turn
    turn_max_raises: int = 1  # 1 raise allowed on turn

    # River support (Phase 11A: minimal river layer)
    include_river: bool = False
    max_river_cards: int = 4  # max river cards to explore per turn branch
    river_bet_sizes_override: tuple[float, ...] = (0.5, 1.0)  # narrow: 2 bet sizes
    river_raise_sizes_override: tuple[float, ...] = ()  # no raises on river by default
    river_max_raises: int = 0  # no raises on river by default

    @property
    def ip_range(self) -> ParsedRange:
        return parse_range(self.ip_range_str) if self.ip_range_str else ParsedRange()

    @property
    def oop_range(self) -> ParsedRange:
        return parse_range(self.oop_range_str) if self.oop_range_str else ParsedRange()

    @property
    def street_depth(self) -> str:
        """Return the supported street depth label."""
        if self.include_river:
            return "flop_plus_turn_plus_river"
        return "flop_plus_turn" if self.include_turn else "flop_only"


@dataclass
class GameTreeNode:
    """
    A node in the game tree.

    Represents action nodes (player decisions), chance nodes (card dealing),
    and terminal nodes (fold/showdown).
    """
    node_id: str
    node_type: NodeType
    player: Optional[str] = None           # "IP" or "OOP" for action nodes
    street: str = "flop"
    pot: float = 0.0
    ip_stack: float = 0.0
    oop_stack: float = 0.0
    children: dict[str, "GameTreeNode"] = field(default_factory=dict)
    turn_card: Optional[str] = None        # For chance node children: the dealt turn card
    river_card: Optional[str] = None       # For chance node children: the dealt river card
    # Phase 12A: cached performance fields (populated by finalize_tree)
    _is_terminal: bool = False
    _is_chance: bool = False
    _actions_tuple: tuple = ()             # Pre-built tuple of action keys
    _terminal_type_int: int = 0            # 0=unknown, 1=fold_ip, 2=fold_oop, 3=showdown
    # Phase 12C: integer node ID for flat array indexing
    _int_id: int = -1                      # Sequential integer ID assigned during finalization
    _action_indices: tuple = ()            # Integer indices for each action (0..num_actions-1)

    @property
    def is_terminal(self) -> bool:
        return self._is_terminal

    @property
    def action_count(self) -> int:
        return len(self.children)


@dataclass
class GameTreeStats:
    """Statistics about a built game tree."""
    total_nodes: int = 0
    action_nodes: int = 0
    terminal_nodes: int = 0
    chance_nodes: int = 0
    max_depth: int = 0
    ip_range_combos: int = 0
    oop_range_combos: int = 0
    turn_cards_explored: int = 0
    river_cards_explored: int = 0
    street_depth: str = "flop_only"


# All 52 cards in the deck
_ALL_CARDS = [
    f"{r}{s}" for r in "AKQJT98765432" for s in "shdc"
]


def build_tree_skeleton(config: TreeConfig) -> tuple[GameTreeNode, GameTreeStats]:
    """
    Build a game tree from the configuration.

    For flop-only: builds action tree for flop street only.
    For flop+turn: builds flop action tree, then inserts chance nodes
    at flop→turn transitions that fan out over possible turn cards.

    Returns:
        (root_node, stats)
    """
    stats = GameTreeStats(
        ip_range_combos=config.ip_range.combos if config.ip_range_str else 0,
        oop_range_combos=config.oop_range.combos if config.oop_range_str else 0,
        street_depth=config.street_depth,
    )

    root = _build_street_node(
        config=config,
        street="flop",
        pot=config.starting_pot,
        ip_stack=config.effective_stack,
        oop_stack=config.effective_stack,
        depth=0,
        node_counter=[0],
        stats=stats,
        raises_left=config.max_raises_per_street,
    )

    # Phase 12A: populate cached performance fields on all nodes
    _finalize_tree(root)

    return root, stats


def _finalize_tree(node: GameTreeNode, counter: list[int] | None = None):
    """
    Phase 12A/12C: Populate cached performance fields on all nodes.
    
    Phase 12A: Eliminates repeated property lookups and dict.keys() calls.
    Phase 12C: Assigns sequential integer IDs for flat array indexing.
    """
    if counter is None:
        counter = [0]
    
    node._int_id = counter[0]
    counter[0] += 1
    node._is_terminal = (node.node_type == NodeType.TERMINAL)
    node._is_chance = (node.node_type == NodeType.CHANCE)
    node._actions_tuple = tuple(node.children.keys())
    node._action_indices = tuple(range(len(node.children)))
    
    for child in node.children.values():
        _finalize_tree(child, counter)




def _get_bet_sizes(config: TreeConfig, street: str) -> tuple[float, ...]:
    if street == "flop":
        return config.flop_bet_sizes
    elif street == "turn":
        # Use override sizes if turn support is enabled (simpler tree)
        if config.include_turn and config.turn_bet_sizes_override:
            return config.turn_bet_sizes_override
        return config.turn_bet_sizes
    else:
        # River: use override sizes if river support is enabled
        if config.include_river and config.river_bet_sizes_override:
            return config.river_bet_sizes_override
        return config.river_bet_sizes


def _get_raise_sizes(config: TreeConfig, street: str) -> tuple[float, ...]:
    if street == "flop":
        return config.flop_raise_sizes
    elif street == "turn":
        if config.include_turn:
            return config.turn_raise_sizes_override
        return config.turn_raise_sizes
    else:
        # River: use override sizes if river support is enabled
        if config.include_river:
            return config.river_raise_sizes_override
        return config.river_raise_sizes


_NEXT_STREET = {"flop": "turn", "turn": "river", "river": None}


def _build_street_node(
    config: TreeConfig,
    street: str,
    pot: float,
    ip_stack: float,
    oop_stack: float,
    depth: int,
    node_counter: list[int],
    stats: GameTreeStats,
    raises_left: int,
    player: str = "OOP",
    facing_bet: float = 0.0,
) -> GameTreeNode:
    """Recursively build the game tree for a given street."""
    node_id = f"node_{node_counter[0]}"
    node_counter[0] += 1
    stats.total_nodes += 1
    stats.max_depth = max(stats.max_depth, depth)

    acting_stack = oop_stack if player == "OOP" else ip_stack

    node = GameTreeNode(
        node_id=node_id,
        node_type=NodeType.ACTION,
        player=player,
        street=street,
        pot=pot,
        ip_stack=ip_stack,
        oop_stack=oop_stack,
    )
    stats.action_nodes += 1

    opponent = "IP" if player == "OOP" else "OOP"

    # Fold (only if facing a bet)
    if facing_bet > 0:
        fold_id = f"node_{node_counter[0]}"
        node_counter[0] += 1
        node.children["fold"] = GameTreeNode(
            node_id=fold_id,
            node_type=NodeType.TERMINAL,
            street=street,
            pot=pot,
        )
        stats.total_nodes += 1
        stats.terminal_nodes += 1

    # Check or Call
    if facing_bet == 0:
        # Check
        if player == "IP":
            # IP checking after OOP checked → advance street
            next_st = _NEXT_STREET.get(street)
            should_terminal_check = (
                next_st is None
                or (next_st == "turn" and not config.include_turn)
                or (next_st == "river" and not config.include_river)
            )
            if should_terminal_check:
                # Terminal: showdown (no more streets to solve)
                sd_id = f"node_{node_counter[0]}"
                node_counter[0] += 1
                node.children["check"] = GameTreeNode(
                    node_id=sd_id,
                    node_type=NodeType.TERMINAL,
                    street=street,
                    pot=pot,
                )
                stats.total_nodes += 1
                stats.terminal_nodes += 1
            elif next_st == "turn" and config.include_turn:
                # Insert chance node for turn card dealing
                node.children["check"] = _build_chance_node(
                    config, pot, ip_stack, oop_stack,
                    depth + 1, node_counter, stats,
                )
            elif next_st == "river" and config.include_river:
                # Insert chance node for river card dealing
                node.children["check"] = _build_river_chance_node(
                    config, pot, ip_stack, oop_stack,
                    depth + 1, node_counter, stats,
                )
            else:
                node.children["check"] = _build_street_node(
                    config, next_st, pot, ip_stack, oop_stack,
                    depth + 1, node_counter, stats,
                    config.max_raises_per_street, "OOP", 0.0,
                )
        else:
            # OOP checks → IP acts
            node.children["check"] = _build_street_node(
                config, street, pot, ip_stack, oop_stack,
                depth + 1, node_counter, stats,
                raises_left, "IP", 0.0,
            )
    else:
        # Call
        call_amount = min(facing_bet, acting_stack)
        new_pot = pot + call_amount
        new_ip = ip_stack - (call_amount if player == "IP" else 0)
        new_oop = oop_stack - (call_amount if player == "OOP" else 0)

        next_st = _NEXT_STREET.get(street)
        should_terminate = (
            next_st is None
            or min(new_ip, new_oop) <= 0
            or (next_st == "turn" and not config.include_turn)
            or (next_st == "river" and not config.include_river)
        )
        if should_terminate:
            call_terminal_id = f"node_{node_counter[0]}"
            node_counter[0] += 1
            node.children["call"] = GameTreeNode(
                node_id=call_terminal_id,
                node_type=NodeType.TERMINAL,
                street=street,
                pot=new_pot,
            )
            stats.total_nodes += 1
            stats.terminal_nodes += 1
        elif next_st == "turn" and config.include_turn:
            # Insert chance node for turn card dealing
            node.children["call"] = _build_chance_node(
                config, new_pot, new_ip, new_oop,
                depth + 1, node_counter, stats,
            )
        elif next_st == "river" and config.include_river:
            # Insert chance node for river card dealing
            node.children["call"] = _build_river_chance_node(
                config, new_pot, new_ip, new_oop,
                depth + 1, node_counter, stats,
            )
        else:
            node.children["call"] = _build_street_node(
                config, next_st, new_pot, new_ip, new_oop,
                depth + 1, node_counter, stats,
                config.max_raises_per_street, "OOP", 0.0,
            )

    # Bets/Raises (if we have raises left and stack allows)
    if acting_stack > 0 and depth < 20:  # depth guard
        if facing_bet == 0:
            # Bet
            for frac in _get_bet_sizes(config, street):
                bet_amount = round(pot * frac, 1)
                if bet_amount >= acting_stack * config.all_in_threshold:
                    continue  # skip, all-in covers this
                if bet_amount > acting_stack:
                    continue
                label = f"bet_{int(frac * 100)}"
                new_pot2 = pot + bet_amount
                new_ip2 = ip_stack - (bet_amount if player == "IP" else 0)
                new_oop2 = oop_stack - (bet_amount if player == "OOP" else 0)
                node.children[label] = _build_street_node(
                    config, street, new_pot2, new_ip2, new_oop2,
                    depth + 1, node_counter, stats,
                    raises_left - 1, opponent, bet_amount,
                )
        elif raises_left > 0:
            # Raise
            for mult in _get_raise_sizes(config, street):
                raise_amount = round(facing_bet * mult, 1)
                if raise_amount >= acting_stack:
                    continue
                label = f"raise_{int(mult * 10)}x"
                new_pot2 = pot + raise_amount
                new_ip2 = ip_stack - (raise_amount if player == "IP" else 0)
                new_oop2 = oop_stack - (raise_amount if player == "OOP" else 0)
                node.children[label] = _build_street_node(
                    config, street, new_pot2, new_ip2, new_oop2,
                    depth + 1, node_counter, stats,
                    raises_left - 1, opponent, raise_amount,
                )

        # All-in
        if acting_stack > 0 and facing_bet < acting_stack:
            allin_id_node = _build_allin_subtree(
                config, street, pot, ip_stack, oop_stack,
                acting_stack, player, opponent,
                depth, node_counter, stats,
            )
            node.children["allin"] = allin_id_node

    return node


def _build_allin_subtree(
    config, street, pot, ip_stack, oop_stack,
    allin_amount, player, opponent,
    depth, node_counter, stats,
) -> GameTreeNode:
    """Build subtree after an all-in: opponent can fold or call."""
    new_pot = pot + allin_amount
    node_id = f"node_{node_counter[0]}"
    node_counter[0] += 1

    node = GameTreeNode(
        node_id=node_id,
        node_type=NodeType.ACTION,
        player=opponent,
        street=street,
        pot=new_pot,
    )
    stats.total_nodes += 1
    stats.action_nodes += 1

    # Fold
    fold_id = f"node_{node_counter[0]}"
    node_counter[0] += 1
    node.children["fold"] = GameTreeNode(
        node_id=fold_id, node_type=NodeType.TERMINAL, street=street, pot=new_pot,
    )
    stats.total_nodes += 1
    stats.terminal_nodes += 1

    # Call
    call_id = f"node_{node_counter[0]}"
    node_counter[0] += 1
    node.children["call"] = GameTreeNode(
        node_id=call_id, node_type=NodeType.TERMINAL, street=street,
        pot=new_pot + min(allin_amount, oop_stack if opponent == "OOP" else ip_stack),
    )
    stats.total_nodes += 1
    stats.terminal_nodes += 1

    return node


def _build_chance_node(
    config: TreeConfig,
    pot: float,
    ip_stack: float,
    oop_stack: float,
    depth: int,
    node_counter: list[int],
    stats: GameTreeStats,
) -> GameTreeNode:
    """
    Build a chance node for turn card dealing.

    The chance node fans out over possible turn cards. Each branch
    leads to a turn action subtree. The number of turn cards is
    capped by config.max_turn_cards to keep tree size manageable.

    HONEST NOTE: We sample a subset of turn cards when max_turn_cards > 0.
    This is an approximation — a full solver would enumerate all remaining cards.
    """
    chance_id = f"node_{node_counter[0]}"
    node_counter[0] += 1

    chance_node = GameTreeNode(
        node_id=chance_id,
        node_type=NodeType.CHANCE,
        street="flop",  # chance node sits between flop and turn
        pot=pot,
        ip_stack=ip_stack,
        oop_stack=oop_stack,
    )
    stats.total_nodes += 1
    stats.chance_nodes += 1

    # Determine which turn cards to explore
    board_set = set(config.board)
    available_cards = [c for c in _ALL_CARDS if c not in board_set]

    # Cap the number of turn cards
    if config.max_turn_cards > 0 and len(available_cards) > config.max_turn_cards:
        # Select evenly spaced cards for diversity
        step = len(available_cards) / config.max_turn_cards
        selected = [available_cards[int(i * step)] for i in range(config.max_turn_cards)]
        available_cards = selected

    stats.turn_cards_explored = len(available_cards)

    # Build a turn action subtree for each turn card
    turn_raises = config.turn_max_raises
    for card_str in available_cards:
        child = _build_street_node(
            config=config,
            street="turn",
            pot=pot,
            ip_stack=ip_stack,
            oop_stack=oop_stack,
            depth=depth + 1,
            node_counter=node_counter,
            stats=stats,
            raises_left=turn_raises,
            player="OOP",
            facing_bet=0.0,
        )
        child.turn_card = card_str
        chance_node.children[f"turn_{card_str}"] = child

    return chance_node


def _build_river_chance_node(
    config: TreeConfig,
    pot: float,
    ip_stack: float,
    oop_stack: float,
    depth: int,
    node_counter: list[int],
    stats: GameTreeStats,
) -> GameTreeNode:
    """
    Build a chance node for river card dealing.

    Phase 11A: mirrors _build_chance_node but for the turn→river transition.
    Each branch leads to a river action subtree with narrow abstraction.

    HONEST NOTE: We sample a subset of river cards. This is an approximation.
    River action abstraction is deliberately narrow (2 bet sizes, 0 raises)
    to keep tree size manageable.
    """
    chance_id = f"node_{node_counter[0]}"
    node_counter[0] += 1

    chance_node = GameTreeNode(
        node_id=chance_id,
        node_type=NodeType.CHANCE,
        street="turn",  # chance node sits between turn and river
        pot=pot,
        ip_stack=ip_stack,
        oop_stack=oop_stack,
    )
    stats.total_nodes += 1
    stats.chance_nodes += 1

    # Determine which river cards to explore
    # Must exclude ALL board cards (flop + turn card, which is set contextually)
    board_set = set(config.board)  # flop cards only at config level
    available_cards = [c for c in _ALL_CARDS if c not in board_set]

    # Cap the number of river cards
    if config.max_river_cards > 0 and len(available_cards) > config.max_river_cards:
        step = len(available_cards) / config.max_river_cards
        selected = [available_cards[int(i * step)] for i in range(config.max_river_cards)]
        available_cards = selected

    stats.river_cards_explored = max(stats.river_cards_explored, len(available_cards))

    # Build a river action subtree for each river card
    river_raises = config.river_max_raises
    for card_str in available_cards:
        child = _build_street_node(
            config=config,
            street="river",
            pot=pot,
            ip_stack=ip_stack,
            oop_stack=oop_stack,
            depth=depth + 1,
            node_counter=node_counter,
            stats=stats,
            raises_left=river_raises,
            player="OOP",
            facing_bet=0.0,
        )
        child.river_card = card_str
        chance_node.children[f"river_{card_str}"] = child

    return chance_node
