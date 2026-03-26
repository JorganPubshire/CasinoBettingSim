"""
Interactive CLI: pick a registered game/variant, configure table and rounds,
select one or more strategies, run parallel simulation silently, then print stats.

Usage: ``python simulate_cli.py`` … optional ``--debug`` enables parallel session
debug recording; if the run raises, the last round’s branch state is printed to stderr.
``--no-plot`` skips the bankroll chart (requires ``plotly`` otherwise).
"""

from __future__ import annotations

import contextlib
import io
import sys
import threading
import time
from collections import defaultdict
from typing import cast

from casino_sim.cli.registry import (
    REGISTERED_GAMES,
    RegisteredVariant,
    StrategySpec,
    strategy_menu_label,
)
from casino_sim.simulation.lucky_queens_parallel import (
    SIDE_BET_BLOCK_BONUS,
    SIDE_BET_LUCKY_QUEENS,
)
from casino_sim.cli.bankroll_chart import try_show_bankroll_chart
from casino_sim.cli.simulate_results import results_table_lines
from casino_sim.cli.terminal_menus import (
    BOLD,
    CYAN,
    DIM,
    MAGENTA,
    RST,
    YELLOW,
    ansi_enabled,
    init_terminal,
    prompt_float,
    prompt_int,
    select_from_menu,
    select_strategy_indices_multimenu,
)
from casino_sim.simulation.standard_blackjack_parallel import ParallelParticipantSummary
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy

# Real console stream: simulation thread uses redirect_stdout, which replaces global sys.stdout.
_PROGRESS_OUT = sys.__stdout__

_PROGRESS_BLINK_PERIOD_SEC = 0.12


def _simulation_progress_percent(completed: int, total: int) -> int:
    if total <= 0:
        return 100
    return min(100, (100 * completed) // total)


def _simulation_progress_line(completed: int, total: int, *, blink_on: bool) -> str:
    """``[==========] N%`` with one blinking ``=`` for the in-progress 10% bucket."""
    pct = _simulation_progress_percent(completed, total)
    cells: list[str] = []
    for i in range(10):
        segment_end = (i + 1) * 10
        segment_start = i * 10
        if pct >= segment_end:
            cells.append("=")
        elif pct >= segment_start:
            cells.append("=" if blink_on else " ")
        else:
            cells.append(" ")
    return f"[{''.join(cells)}] {pct}%"


def _parse_cli_flags(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Parse ``--debug`` / ``--no-plot``; return (remaining_args, debug_parallel, no_plot)."""
    debug = False
    no_plot = False
    rest: list[str] = []
    for item in argv:
        if item == "--debug":
            debug = True
        elif item == "--no-plot":
            no_plot = True
        else:
            rest.append(item)
    return rest, debug, no_plot


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
        disp = strategy_menu_label(spec)
        if total_same > 1:
            name = f"{disp} (#{n})"
        else:
            name = disp
        pairs.append((name, cast(StandardBlackjackPlayerStrategy, spec.factory())))
    return pairs


def _run_variant_with_live_progress(
    variant: RegisteredVariant,
    *,
    initial_bankroll: float,
    table_min: float,
    table_max: float,
    rounds: int,
    strategy_pairs: list[tuple[str, StandardBlackjackPlayerStrategy]],
    debug_parallel: bool,
    run_kwargs: dict[str, object],
) -> tuple[list[ParallelParticipantSummary], str]:
    """Run the variant in a worker thread while the main thread draws a progress bar."""
    state: dict[str, object] = {
        "done": 0,
        "tot": rounds,
        "summaries": None,
        "exc": None,
    }
    buf = io.StringIO()

    def on_progress(done: int, tot: int) -> None:
        state["done"] = done
        state["tot"] = tot

    def worker() -> None:
        try:
            with contextlib.redirect_stdout(buf):
                summaries = variant.run(
                    initial_bankroll=initial_bankroll,
                    bet_min=float(table_min),
                    bet_max=float(table_max),
                    rounds=rounds,
                    strategy_pairs=strategy_pairs,
                    debug_parallel=debug_parallel,
                    on_progress=on_progress,
                    **run_kwargs,
                )
            state["summaries"] = summaries
        except BaseException as e:
            state["exc"] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while thread.is_alive():
        blink = int(time.monotonic() / _PROGRESS_BLINK_PERIOD_SEC) % 2 == 0
        line = _simulation_progress_line(
            int(state["done"]), int(state["tot"]), blink_on=blink
        )
        print(f"\r{line}", end="", file=_PROGRESS_OUT, flush=True)
        time.sleep(0.05)
    thread.join()

    line = _simulation_progress_line(
        int(state["done"]), int(state["tot"]), blink_on=True
    )
    print(f"\r{line}", end="", file=_PROGRESS_OUT, flush=True)
    print(file=_PROGRESS_OUT)

    if state["exc"] is not None:
        raise state["exc"]
    summaries = state["summaries"]
    assert summaries is not None
    return summaries, buf.getvalue()


def main() -> None:
    _remaining, debug_parallel, no_plot = _parse_cli_flags(sys.argv[1:])
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

    if not variant.strategies:
        msg = (
            f"This variant ({variant.label}) has no registered simulation strategies yet. "
            "Add entries to the Lucky Queens strategy list in casino_sim/cli/registry.py "
            "(each strategy must report the Lucky Queens game id from supported_game_id)."
        )
        if ansi_enabled:
            print(f"\n{YELLOW}{msg}{RST}")
        else:
            print(f"\n{msg}")
        return

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

    run_kwargs: dict[str, object] = {}
    include_side_bet_columns = variant.id == "lucky_queens"
    if include_side_bet_columns:
        bb_lo = prompt_float(
            "Block Bonus side bet — table minimum (0 if not offered): ", minimum=0.0
        )
        bb_hi = prompt_float(
            "Block Bonus side bet — table maximum: ", minimum=float(bb_lo)
        )
        lq_lo = prompt_float(
            "Lucky Queens side bet — table minimum (0 if not offered): ", minimum=0.0
        )
        lq_hi = prompt_float(
            "Lucky Queens side bet — table maximum: ", minimum=float(lq_lo)
        )
        run_kwargs["side_bet_limits"] = {
            SIDE_BET_BLOCK_BONUS: (float(bb_lo), float(bb_hi)),
            SIDE_BET_LUCKY_QUEENS: (float(lq_lo), float(lq_hi)),
        }

    specs = variant.strategies
    indices_zero = select_strategy_indices_multimenu(specs)
    one_based = [i + 1 for i in indices_zero]
    strategy_pairs = _build_strategy_run_list(one_based, specs)

    run_msg = "\nRunning simulation:"
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

    summaries, _captured_stdout = _run_variant_with_live_progress(
        variant,
        initial_bankroll=initial_bankroll,
        table_min=float(table_min),
        table_max=float(table_max),
        rounds=rounds,
        strategy_pairs=strategy_pairs,
        debug_parallel=debug_parallel,
        run_kwargs=run_kwargs,
    )
    _ = _captured_stdout

    res_title = "=== Results ==="
    if ansi_enabled:
        print(f"\n{CYAN}{BOLD}{res_title}{RST}\n")
    else:
        print(f"\n{res_title}\n")

    table_lines, _ = results_table_lines(
        summaries,
        initial_bankroll,
        include_side_bet_nets=include_side_bet_columns,
    )
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
    if include_side_bet_columns:
        notes += (
            " You set each side bet's table min/max; each strategy decides whether to "
            "play and how much within those limits and its bankroll. Block Bonus Net and "
            "Lucky Queens Net are total side-bet profit (payouts minus wagers) over the run."
        )
    if ansi_enabled:
        print(f"{DIM}{notes}{RST}")
    else:
        print(notes)

    if not no_plot:
        chart_note = "Opening bankroll chart in your browser (close this message’s tab when done)."
        if ansi_enabled:
            print(f"\n{CYAN}{chart_note}{RST}")
        else:
            print(f"\n{chart_note}")
        chart_title = f"{game.label} — {variant.label}"
        shown = try_show_bankroll_chart(
            summaries,
            float(initial_bankroll),
            title=chart_title,
        )
        if not shown:
            tip = "Install plotly to show the bankroll chart: pip install plotly"
            if ansi_enabled:
                print(f"\n{DIM}{tip}{RST}")
            else:
                print(f"\n{tip}")


if __name__ == "__main__":
    main()
