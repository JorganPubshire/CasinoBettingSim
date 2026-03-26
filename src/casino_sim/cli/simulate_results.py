"""
USD-formatted result table for the simulate CLI (testable without TTY). The strategy
name column widens to fit the longest label in the run.
"""

from __future__ import annotations

from casino_sim.simulation.standard_blackjack_parallel import ParallelParticipantSummary

STRATEGY_HEADER = "Strategy Name"
COL_STRATEGY_DEFAULT = 28
COL_COUNT = 9
COL_MONEY = 14
COL_SIDE_NET = 16


def format_usd(amount: float) -> str:
    """Format a number as USD with commas (e.g. ``$1,234.56``, ``-$99.00``)."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def pad_strategy_label(name: str, width: int = COL_STRATEGY_DEFAULT) -> str:
    if len(name) <= width:
        return name.ljust(width)
    return name[: width - 1] + "…"


def _strategy_name_column_width(
    summaries: list[ParallelParticipantSummary],
    *,
    header: str = STRATEGY_HEADER,
) -> int:
    w = len(header)
    for row in summaries:
        w = max(w, len(row.name))
    return max(w, 1)


def results_table_lines(
    summaries: list[ParallelParticipantSummary],
    initial_bankroll: float,
    *,
    include_side_bet_nets: bool = False,
) -> tuple[list[str], int]:
    """
    Build aligned table lines (no ANSI). Returns (lines, separator_width).

    The strategy column is as wide as the header or longest ``row.name``, whichever
    is larger (no truncation for names in this table).

    Rounds counts only rounds where the strategy placed a legal wager. Win/loss/push
    counts are per resolved player hand (splits can exceed rounds).

    When ``include_side_bet_nets`` is True, insert Block Bonus and Lucky Queens net
    columns (chips returned minus stakes over the session) before the bankroll extrema.

    ``Min Bankroll`` / ``Max Bankroll`` are taken from each summary (tracked across the
    session, including the starting bankroll). They appear immediately before
    ``Final Total`` and ``Net``.

    Rows are ordered by ``final_bankroll`` descending (highest final total first).
    """
    ordered = sorted(summaries, key=lambda r: r.final_bankroll, reverse=True)
    strat_w = _strategy_name_column_width(ordered)
    headers = [
        pad_strategy_label(STRATEGY_HEADER, strat_w),
        f"{'Wins':>{COL_COUNT}}",
        f"{'Losses':>{COL_COUNT}}",
        f"{'Pushes':>{COL_COUNT}}",
        f"{'Rounds':>{COL_COUNT}}",
    ]
    if include_side_bet_nets:
        headers.extend(
            [
                f"{'Block Bonus Net':>{COL_SIDE_NET}}",
                f"{'Lucky Queens Net':>{COL_SIDE_NET}}",
            ]
        )
    headers.extend(
        [
            f"{'Min Bankroll':>{COL_MONEY}}",
            f"{'Max Bankroll':>{COL_MONEY}}",
            f"{'Final Total':>{COL_MONEY}}",
            f"{'Net':>{COL_MONEY}}",
        ]
    )
    header_line = " ".join(headers)
    sep_w = len(header_line)
    sep = "=" * sep_w

    lines: list[str] = [header_line, sep]
    for row in ordered:
        net = row.final_bankroll - initial_bankroll
        cells = [
            pad_strategy_label(row.name, strat_w),
            f"{row.wins:>{COL_COUNT}}",
            f"{row.losses:>{COL_COUNT}}",
            f"{row.pushes:>{COL_COUNT}}",
            f"{row.rounds_played:>{COL_COUNT}}",
        ]
        if include_side_bet_nets:
            cells.extend(
                [
                    f"{format_usd(row.block_bonus_net):>{COL_SIDE_NET}}",
                    f"{format_usd(row.lucky_queens_net):>{COL_SIDE_NET}}",
                ]
            )
        cells.extend(
            [
                f"{format_usd(row.min_bankroll):>{COL_MONEY}}",
                f"{format_usd(row.max_bankroll):>{COL_MONEY}}",
                f"{format_usd(row.final_bankroll):>{COL_MONEY}}",
                f"{format_usd(net):>{COL_MONEY}}",
            ]
        )
        lines.append(" ".join(cells))

    return lines, sep_w
