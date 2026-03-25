"""
Registered games, variants, and strategies for simulation CLIs.

Add new entries here when you implement additional games or variants.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from casino_sim.simulation.standard_blackjack_parallel import (
    ParallelParticipantSummary,
    StandardBlackjackParallelSession,
)
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy
from casino_sim.strategies.blackjack.standard.dealer_strategy import DealerStrategy
from casino_sim.strategies.blackjack.standard.dummy_strategy import DummyStrategy
from casino_sim.strategies.blackjack.standard.hoyle_basic_strategy import (
    HoyleBasicStrategyHigh,
    HoyleBasicStrategyLow,
    HoyleBasicStrategyMid,
)


@dataclass(frozen=True)
class StrategySpec:
    id: str
    label: str
    factory: Callable[[], object]


SimulationRunner = Callable[..., list[ParallelParticipantSummary]]


@dataclass(frozen=True)
class RegisteredVariant:
    id: str
    label: str
    strategies: tuple[StrategySpec, ...]
    run: SimulationRunner


@dataclass(frozen=True)
class RegisteredGame:
    id: str
    label: str
    variants: tuple[RegisteredVariant, ...]


def _run_blackjack_standard(
    *,
    initial_bankroll: float,
    bet_min: float,
    bet_max: float,
    rounds: int,
    strategy_pairs: list[tuple[str, StandardBlackjackPlayerStrategy]],
    debug_parallel: bool = False,
) -> list[ParallelParticipantSummary]:
    session = StandardBlackjackParallelSession(
        bet_min=bet_min,
        bet_max=bet_max,
        initial_bankroll=initial_bankroll,
        rounds=rounds,
        strategies=strategy_pairs,
        deck_count=6,
        include_slug=True,
        debug_parallel=debug_parallel,
    )
    return session.run()


_BLACKJACK_STANDARD_STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        "dummy",
        "Dummy — table max bet, always stand",
        lambda: DummyStrategy(),
    ),
    StrategySpec(
        "dealer",
        "Dealer rule — hit/stand like the house (H17 matches table default)",
        lambda: DealerStrategy(dealer_hits_soft_17=True),
    ),
    StrategySpec(
        "hoyle_low",
        "Hoyle basic strategy — low (minimum ante)",
        lambda: HoyleBasicStrategyLow(),
    ),
    StrategySpec(
        "hoyle_mid",
        "Hoyle basic strategy — mid (mean of min/max, nearest multiple of 5)",
        lambda: HoyleBasicStrategyMid(),
    ),
    StrategySpec(
        "hoyle_high",
        "Hoyle basic strategy — high (maximum ante)",
        lambda: HoyleBasicStrategyHigh(),
    ),
)

REGISTERED_GAMES: tuple[RegisteredGame, ...] = (
    RegisteredGame(
        id="blackjack",
        label="Blackjack",
        variants=(
            RegisteredVariant(
                id="standard",
                label="Standard (6-deck shoe, H17, DAS, 3:2, optional cut card)",
                strategies=_BLACKJACK_STANDARD_STRATEGIES,
                run=_run_blackjack_standard,
            ),
        ),
    ),
)
