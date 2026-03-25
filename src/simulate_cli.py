"""
Interactive CLI: pick a registered game/variant, configure table and rounds,
select one or more strategies, run parallel simulation silently, then print stats.

Usage: ``python simulate_cli.py`` … optional ``--debug`` enables parallel session
debug recording; if the run raises, the last round’s branch state is printed to stderr.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections import defaultdict
from typing import cast

from casino_sim.cli.registry import REGISTERED_GAMES, RegisteredVariant, StrategySpec
from casino_sim.cli.simulate_results import results_table_lines
from casino_sim.cli.terminal_menus import (
    BOLD,
    CYAN,
    DIM,
    MAGENTA,
    RST,
    ansi_enabled,
    init_terminal,
    prompt_float,
    prompt_int,
    select_from_menu,
    select_strategy_indices_multimenu,
)
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


def _parse_cli_flags(argv: list[str]) -> tuple[list[str], bool]:
    """Remove ``--debug`` from argv; return (remaining_args, debug_parallel)."""
    debug = False
    rest: list[str] = []
    for item in argv:
        if item == "--debug":
            debug = True
        else:
            rest.append(item)
    return rest, debug


def _build_strategy_run_list(
    indices: list[int], specs: tuple[StrategySpec, ...]
) -> list[tuple[str, StandardBlackjackPlayerStrategy]]:
    counts: dict[str, int] = defaultdict(int)
    pairs: list[tuple[str, StandardBlackjackPlayerStrategy]] = []
    for idx in indices:
        spec = specs[idx - 1]
        counts[spec.id] += 1
        n = counts[spec.id]
        total_same = sum(1 for i in indices if i == idx)
        if total_same > 1:
            name = f"{spec.label} (#{n})"
        else:
            name = spec.label
        pairs.append((name, cast(StandardBlackjackPlayerStrategy, spec.factory())))
    return pairs


def main() -> None:
    _remaining, debug_parallel = _parse_cli_flags(sys.argv[1:])
    if _remaining:
        print("Unknown arguments (ignored):", " ".join(_remaining), file=sys.stderr)

    init_terminal()

    banner = "=== Casino betting simulation ==="
    if ansi_enabled:
        print(f"{MAGENTA}{BOLD}{banner}{RST}\n")
    else:
        print(f"{banner}\n")

    chosen_game_id = select_from_menu(
        "Select game type:", [(g.id, g.label) for g in REGISTERED_GAMES]
    )
    game = next(g for g in REGISTERED_GAMES if g.id == chosen_game_id)

    variant: RegisteredVariant
    if len(game.variants) == 1:
        variant = game.variants[0]
        msg = f"\nVariant: {variant.label} (only option)"
        if ansi_enabled:
            print(f"{DIM}{msg}{RST}")
        else:
            print(msg)
    else:
        v_id = select_from_menu(
            "Select variant:", [(v.id, v.label) for v in game.variants]
        )
        variant = next(v for v in game.variants if v.id == v_id)

    sec = "--- Table & session ---"
    if ansi_enabled:
        print(f"\n{CYAN}{BOLD}{sec}{RST}")
    else:
        print(f"\n{sec}")
    initial_bankroll = prompt_float("Starting chips per strategy: ", minimum=1.0)
    table_min = prompt_float("Table minimum bet: ", minimum=1.0)
    table_max = prompt_float("Table maximum bet: ", minimum=float(table_min))
    if table_max < table_min:
        warn = "Maximum must be >= minimum."
        print(f"{warn}")
        return
    if int(table_min) % 5 != 0 or int(table_max) % 5 != 0:
        warn = "For blackjack, minimum and maximum must be multiples of 5."
        print(warn)
        return

    rounds = prompt_int("Number of hands (rounds) to simulate: ", minimum=1)

    specs = variant.strategies
    indices_zero = select_strategy_indices_multimenu(specs)
    one_based = [i + 1 for i in indices_zero]
    strategy_pairs = _build_strategy_run_list(one_based, specs)

    run_msg = "\nRunning simulation (no live output)…"
    if ansi_enabled:
        print(f"{DIM}{run_msg}{RST}")
    else:
        print(run_msg)
    if debug_parallel:
        dbg_note = (
            "Parallel debug is ON: on crash, last-round branch state is printed to stderr."
        )
        if ansi_enabled:
            print(f"{DIM}{dbg_note}{RST}")
        else:
            print(dbg_note)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        summaries = variant.run(
            initial_bankroll=initial_bankroll,
            bet_min=float(table_min),
            bet_max=float(table_max),
            rounds=rounds,
            strategy_pairs=strategy_pairs,
            debug_parallel=debug_parallel,
        )

    _ = buf.getvalue()

    res_title = "=== Results ==="
    if ansi_enabled:
        print(f"\n{CYAN}{BOLD}{res_title}{RST}\n")
    else:
        print(f"\n{res_title}\n")

    table_lines, _ = results_table_lines(summaries, initial_bankroll)
    header_line, sep_line, *data_lines = table_lines
    if ansi_enabled:
        print(f"{BOLD}{header_line}{RST}")
        print(f"{DIM}{sep_line}{RST}")
    else:
        print(header_line)
        print(sep_line)
    for line in data_lines:
        print(line)

    notes = (
        "\nNotes: Wins / Losses / Pushes count each resolved player hand (splits can add "
        "several in one table round). Losses include busts and losing to the dealer. "
        "Rounds counts only rounds where the strategy had enough chips to place a legal "
        "bet. Final Total is ending bankroll; Net is that minus starting chips."
    )
    if ansi_enabled:
        print(f"{DIM}{notes}{RST}")
    else:
        print(notes)


if __name__ == "__main__":
    main()
