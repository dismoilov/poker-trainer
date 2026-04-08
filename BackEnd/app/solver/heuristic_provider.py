"""
Heuristic strategy provider — wraps the existing frequency-table logic.

HONEST DISCLOSURE:
This provider generates strategy matrices using hand-tier lookup tables,
board-texture classification, and deterministic jitter. It is NOT a real
GTO solver. It produces plausible frequency distributions that are useful
for training purposes, but they are approximations, not equilibrium strategies.

This module is the ONLY provider available in Phase 1. It exists to:
1. Maintain backward compatibility with Drill/Explore/Analytics flows
2. Provide a working default until a real solver is integrated
3. Serve as a reference implementation of the StrategyProvider interface
"""

from __future__ import annotations

from typing import Optional

from app.solver.base import StrategyProvider, ProviderType, SolveConfig
from app.poker_engine.types import StrategyMatrix

# Import the existing heuristic logic — unchanged functional behavior
from app.services.strategy import generate_strategy as _heuristic_generate


class HeuristicProvider(StrategyProvider):
    """
    Strategy generation via hand-tier frequency tables.

    NOT a solver. Produces training-quality approximations.
    See services/strategy.py and services/gto_data.py for the
    underlying lookup tables and jitter logic.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.HEURISTIC

    @property
    def supports_iterative(self) -> bool:
        return False  # Heuristic generation is instant, not iterative

    def generate_strategy(
        self,
        node_id: str,
        actions: list[dict],
        config: Optional[SolveConfig] = None,
    ) -> StrategyMatrix:
        """
        Generate a 169-hand strategy matrix using heuristic frequency tables.

        This delegates to the existing services/strategy.py logic.
        The config parameter is accepted but only partially used
        (board_texture, position, pot_type are derived from context).
        """
        # Extract hints from config if available
        board_texture = "dry"
        is_ip = True
        pot_type = "SRP"

        if config:
            pot_type = config.street  # rough mapping; the real hint comes from spot format
            # Future: use config.board to derive texture

        return _heuristic_generate(
            node_id=node_id,
            actions=actions,
            board_texture=board_texture,
            is_ip=is_ip,
            pot_type=pot_type,
        )


# Module-level singleton for convenience
_default_provider = HeuristicProvider()


def get_default_provider() -> HeuristicProvider:
    """Return the default heuristic provider instance."""
    return _default_provider
