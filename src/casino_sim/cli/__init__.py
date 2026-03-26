"""Interactive CLIs and simulation registration."""

from casino_sim.cli.registry import (
    REGISTERED_GAMES,
    RegisteredGame,
    RegisteredVariant,
    StrategySpec,
    strategy_menu_label,
)

__all__ = [
    "REGISTERED_GAMES",
    "RegisteredGame",
    "RegisteredVariant",
    "StrategySpec",
    "strategy_menu_label",
]
