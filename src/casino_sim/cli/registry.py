"""
Registered games, variants, and strategies for simulation CLIs.

Add new entries here when you implement additional games or variants.

Simulation runners should only pass table/session bounds (e.g. main min/max, side-bet
min/max per id). Betting and play decisions belong in strategy implementations
(:class:`~casino_sim.interfaces.player_strategy.PlayerStrategy` and hooks such as
``place_side_bets_before_deal``).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from casino_sim.simulation.lucky_queens_parallel import LuckyQueensParallelSession
from casino_sim.simulation.standard_blackjack_parallel import (
    ParallelParticipantSummary,
    StandardBlackjackParallelSession,
)
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy
from casino_sim.strategies.blackjack.standard.dealer_strategy import DealerStrategy
from casino_sim.strategies.blackjack.standard.dummy_strategy import DummyStrategy
from casino_sim.strategies.blackjack.lucky_queens import (
    HoyleLuckyQueensMaxMaxStrategy,
    HoyleLuckyQueensMaxMidStrategy,
    HoyleLuckyQueensMaxMinStrategy,
    HoyleLuckyQueensMaxPassStrategy,
    HoyleLuckyQueensMidMaxStrategy,
    HoyleLuckyQueensMidMidStrategy,
    HoyleLuckyQueensMidMinStrategy,
    HoyleLuckyQueensMidPassStrategy,
    HoyleLuckyQueensMinMaxStrategy,
    HoyleLuckyQueensMinMidStrategy,
    HoyleLuckyQueensMinMinStrategy,
    HoyleLuckyQueensMinPassStrategy,
    HoyleLuckyQueensPassMaxStrategy,
    HoyleLuckyQueensPassMidStrategy,
    HoyleLuckyQueensPassMinStrategy,
    HoyleLuckyQueensPassPassStrategy,
)
from casino_sim.strategies.blackjack.standard.hoyle_basic_strategy import (
    HoyleBasicStrategyHigh,
    HoyleBasicStrategyLow,
    HoyleBasicStrategyMid,
)


@dataclass(frozen=True)
class StrategySpec:
    """``label`` is the canonical display name (simulation results table and strategy menus)."""

    id: str
    label: str
    factory: Callable[[], object]
    menu_label: str | None = None


def strategy_menu_label(spec: StrategySpec) -> str:
    """Display name for interactive menus; defaults to ``label``."""
    return spec.menu_label if spec.menu_label is not None else spec.label


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
    on_progress: Callable[[int, int], None] | None = None,
    **kwargs: object,
) -> list[ParallelParticipantSummary]:
    _ = kwargs
    session = StandardBlackjackParallelSession(
        bet_min=bet_min,
        bet_max=bet_max,
        initial_bankroll=initial_bankroll,
        rounds=rounds,
        strategies=strategy_pairs,
        deck_count=6,
        include_slug=True,
        debug_parallel=debug_parallel,
        on_progress=on_progress,
    )
    return session.run()


def _run_lucky_queens(
    *,
    initial_bankroll: float,
    bet_min: float,
    bet_max: float,
    rounds: int,
    strategy_pairs: list[tuple[str, StandardBlackjackPlayerStrategy]],
    debug_parallel: bool = False,
    side_bet_limits: dict[str, tuple[float, float]] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    **kwargs: object,
) -> list[ParallelParticipantSummary]:
    _ = kwargs
    session = LuckyQueensParallelSession(
        bet_min=bet_min,
        bet_max=bet_max,
        initial_bankroll=initial_bankroll,
        rounds=rounds,
        strategies=strategy_pairs,
        side_bet_limits=dict(side_bet_limits or {}),
        deck_count=6,
        include_slug=True,
        debug_parallel=debug_parallel,
        on_progress=on_progress,
    )
    return session.run()


_BLACKJACK_STANDARD_STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        "dummy",
        "Dummy - max bet, always stand",
        lambda: DummyStrategy(),
    ),
    StrategySpec(
        "dealer",
        "Dealer - house rules (H17)",
        lambda: DealerStrategy(dealer_hits_soft_17=True),
    ),
    StrategySpec(
        "hoyle_low",
        "Hoyle basic - low main bet",
        lambda: HoyleBasicStrategyLow(),
    ),
    StrategySpec(
        "hoyle_mid",
        "Hoyle basic - mid main bet",
        lambda: HoyleBasicStrategyMid(),
    ),
    StrategySpec(
        "hoyle_high",
        "Hoyle basic - high main bet",
        lambda: HoyleBasicStrategyHigh(),
    ),
)

_LUCKY_QUEENS_STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        "hoyle_lucky_queens_min_min",
        "Hoyle - Block low / Lucky low",
        lambda: HoyleLuckyQueensMinMinStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_min_mid",
        "Hoyle - Block low / Lucky mid",
        lambda: HoyleLuckyQueensMinMidStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_min_max",
        "Hoyle - Block low / Lucky high",
        lambda: HoyleLuckyQueensMinMaxStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_min_pass",
        "Hoyle - Block low / Lucky pass",
        lambda: HoyleLuckyQueensMinPassStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_mid_min",
        "Hoyle - Block mid / Lucky low",
        lambda: HoyleLuckyQueensMidMinStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_mid_mid",
        "Hoyle - Block mid / Lucky mid",
        lambda: HoyleLuckyQueensMidMidStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_mid_max",
        "Hoyle - Block mid / Lucky high",
        lambda: HoyleLuckyQueensMidMaxStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_mid_pass",
        "Hoyle - Block mid / Lucky pass",
        lambda: HoyleLuckyQueensMidPassStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_max_min",
        "Hoyle - Block high / Lucky low",
        lambda: HoyleLuckyQueensMaxMinStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_max_mid",
        "Hoyle - Block high / Lucky mid",
        lambda: HoyleLuckyQueensMaxMidStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_max_max",
        "Hoyle - Block high / Lucky high",
        lambda: HoyleLuckyQueensMaxMaxStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_max_pass",
        "Hoyle - Block high / Lucky pass",
        lambda: HoyleLuckyQueensMaxPassStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_pass_min",
        "Hoyle - Block pass / Lucky low",
        lambda: HoyleLuckyQueensPassMinStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_pass_mid",
        "Hoyle - Block pass / Lucky mid",
        lambda: HoyleLuckyQueensPassMidStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_pass_max",
        "Hoyle - Block pass / Lucky high",
        lambda: HoyleLuckyQueensPassMaxStrategy(),
    ),
    StrategySpec(
        "hoyle_lucky_queens_pass_pass",
        "Hoyle - Block pass / Lucky pass",
        lambda: HoyleLuckyQueensPassPassStrategy(),
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
            RegisteredVariant(
                id="lucky_queens",
                label=(
                    "Lucky Queens (+ Block Bonus & Lucky Queens; "
                    "Hoyle basic low main ante, 4×4 side-bet grid (incl. Pass))"
                ),
                strategies=_LUCKY_QUEENS_STRATEGIES,
                run=_run_lucky_queens,
            ),
        ),
    ),
)
