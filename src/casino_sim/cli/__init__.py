"""Interactive CLIs and simulation registration."""

from casino_sim.cli.registry import REGISTERED_GAMES, RegisteredGame, RegisteredVariant, StrategySpec

__all__ = [
    "REGISTERED_GAMES",
    "RegisteredGame",
    "RegisteredVariant",
    "StrategySpec",
]
