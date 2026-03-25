"""
Reproduce: parallel standard blackjack sim with high round count and all strategies.
Run from repo root:  py scripts/repro_simulate_exhaustion.py
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import cast

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_REPO_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from casino_sim.cli.registry import REGISTERED_GAMES  # noqa: E402
from casino_sim.simulation.standard_blackjack_parallel import StandardBlackjackParallelSession  # noqa: E402
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy  # noqa: E402


def main() -> None:
    variant = REGISTERED_GAMES[0].variants[0]
    specs = variant.strategies
    strategy_pairs: list[tuple[str, StandardBlackjackPlayerStrategy]] = [
        (s.label, cast(StandardBlackjackPlayerStrategy, s.factory())) for s in specs
    ]

    session = StandardBlackjackParallelSession(
        bet_min=100.0,
        bet_max=1000.0,
        initial_bankroll=10_000.0,
        rounds=1000,
        strategies=strategy_pairs,
        deck_count=6,
        include_slug=True,
    )

    print(
        f"Running {len(strategy_pairs)} strategies × {session.rounds} rounds, "
        f"slug={session.include_slug}, deck_count={session.deck_count}"
    )
    print(f"Master shoe before run: {session._master.deck.cards_remaining()} cards")

    orig_run_round = session._run_single_round
    last_round = [0]

    def wrapped_run(rn: int) -> None:
        last_round[0] = rn
        return orig_run_round(rn)

    session._run_single_round = wrapped_run  # type: ignore[method-assign]

    try:
        session.run()
        print("Completed without error.")
    except ValueError as e:
        print(f"\nValueError: {e}  (last completed round index before failure: {last_round[0]})")
        traceback.print_exc()
        # Inspect master deck at failure if session still exists
        try:
            rem = session._master.deck.cards_remaining()
            print(f"\nMaster deck cards_remaining at failure: {rem}")
        except Exception as ex:  # noqa: BLE001
            print(f"(could not read master deck: {ex})")


if __name__ == "__main__":
    main()
