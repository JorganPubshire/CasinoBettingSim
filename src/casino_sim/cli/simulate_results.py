"""
Fixed-width, USD-formatted result table for the simulate CLI (testable without TTY).
"""

from __future__ import annotations

from casino_sim.simulation.standard_blackjack_parallel import ParallelParticipantSummary

COL_STRATEGY = 28
COL_COUNT = 9
COL_MONEY = 14


def format_usd(amount: float) -> str:
    """Format a number as USD with commas (e.g. ``$1,234.56``, ``-$99.00``)."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def pad_strategy_label(name: str, width: int = COL_STRATEGY) -> str:
    if len(name) <= width:
        return name.ljust(width)
    return name[: width - 1] + "…"


def results_table_lines(
    summaries: list[ParallelParticipantSummary],
    initial_bankroll: float,
) -> tuple[list[str], int]:
    """
    Build fixed-width table lines (no ANSI). Returns (lines, separator_width).

    Rounds counts only rounds where the strategy placed a legal wager. Win/loss/push
    counts are per resolved player hand (splits can exceed rounds).
    """
    headers = [
        pad_strategy_label("Strategy Name"),
        f"{'Wins':>{COL_COUNT}}",
        f"{'Losses':>{COL_COUNT}}",
        f"{'Pushes':>{COL_COUNT}}",
        f"{'Rounds':>{COL_COUNT}}",
        f"{'Final Total':>{COL_MONEY}}",
        f"{'Net':>{COL_MONEY}}",
    ]
    header_line = " ".join(headers)
    sep_w = len(header_line)
    sep = "=" * sep_w

    lines: list[str] = [header_line, sep]
    for row in summaries:
        net = row.final_bankroll - initial_bankroll
        cells = [
            pad_strategy_label(row.name),
            f"{row.wins:>{COL_COUNT}}",
            f"{row.losses:>{COL_COUNT}}",
            f"{row.pushes:>{COL_COUNT}}",
            f"{row.rounds_played:>{COL_COUNT}}",
            f"{format_usd(row.final_bankroll):>{COL_MONEY}}",
            f"{format_usd(net):>{COL_MONEY}}",
        ]
        lines.append(" ".join(cells))

    return lines, sep_w
