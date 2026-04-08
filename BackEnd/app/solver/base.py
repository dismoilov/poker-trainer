"""
Solver abstraction layer — base interfaces and contracts.

Defines StrategyProvider: the abstract interface that any strategy
generation backend must implement. This decouples the trainer/explore
flows from the specific strategy generation method.

HONEST NOTE: The current system uses a heuristic provider
(hand-tier lookup tables + board texture + jitter). This is NOT
a real GTO solver. The real solver interface is defined here so
that a true CFR/LP solver can be plugged in cleanly in a future phase.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.poker_engine.types import StrategyMatrix


class ProviderType(Enum):
    HEURISTIC = "heuristic"
    REAL_SOLVER = "real_solver"


@dataclass(frozen=True)
class SolveConfig:
    """Configuration for a solve/generation request."""
    board: list[str]                              # Board cards (e.g. ["Ks", "7d", "2c"])
    ip_range: Optional[str] = None                # IP preflop range string (e.g. "AA,KK,QQ,AKs")
    oop_range: Optional[str] = None               # OOP preflop range string
    pot: float = 6.5                              # Starting pot in bb
    ip_stack: float = 97.0                        # IP remaining stack in bb
    oop_stack: float = 97.0                       # OOP remaining stack in bb
    rake_pct: float = 0.0                         # Rake percentage
    rake_cap: float = 0.0                         # Rake cap in bb
    allowed_bet_sizes: list[float] = field(default_factory=lambda: [0.33, 0.66, 1.0])
    allowed_raise_sizes: list[float] = field(default_factory=lambda: [2.5, 3.0])
    max_iterations: int = 1000                    # For iterative solvers
    target_exploitability: float = 0.5            # Target exploitability in bb/100
    street: str = "flop"


@dataclass
class SolveProgress:
    """Progress of an ongoing solve."""
    iterations_done: int = 0
    total_iterations: int = 0
    exploitability: float = float("inf")
    converged: bool = False
    cancelled: bool = False
    message: str = ""


@dataclass(frozen=True)
class SolveResult:
    """Result of a completed strategy generation/solve."""
    strategy_by_node: dict[str, StrategyMatrix]   # node_id → strategy matrix
    provider_type: ProviderType
    iterations: int = 0
    exploitability: float = float("inf")          # in bb/100; inf = unknown (heuristic)
    converged: bool = False
    metadata: dict = field(default_factory=dict)


class StrategyProvider(ABC):
    """
    Abstract interface for strategy generation.

    Implementations:
    - HeuristicProvider: hand-tier frequency tables (current system)
    - RealSolverProvider: true iterative solver (future phase)
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the type of this provider."""
        ...

    @property
    @abstractmethod
    def supports_iterative(self) -> bool:
        """Whether this provider supports iterative solving with progress."""
        ...

    @abstractmethod
    def generate_strategy(
        self,
        node_id: str,
        actions: list[dict],
        config: Optional[SolveConfig] = None,
    ) -> StrategyMatrix:
        """
        Generate a 169-hand strategy matrix for a single node.

        Args:
            node_id: Unique ID of the decision node.
            actions: List of available actions (dicts with 'id', 'label', 'type', etc.)
            config: Optional solve configuration.

        Returns:
            Strategy matrix: {hand_label: {action_id: frequency}}
        """
        ...

    def get_progress(self) -> SolveProgress:
        """Get current progress. Default: no progress tracking."""
        return SolveProgress()

    def cancel(self) -> None:
        """Cancel an ongoing solve. Default: no-op."""
        pass
