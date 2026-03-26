"""
Bankroll-over-time chart for parallel simulation summaries.

Uses `plotly` (MIT License) loaded only when :func:`try_show_bankroll_chart` runs, so
the rest of the package stays importable without it installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from casino_sim.simulation.standard_blackjack_parallel import ParallelParticipantSummary


def bankroll_xy_for_run(
    history: tuple[float, ...], initial_bankroll: float
) -> tuple[list[int], list[float]]:
    """
    X = round index (0 = before first round, k = after round k). Y = bankroll after
    each point. Empty ``history`` yields a single point at the starting bankroll.
    """
    ib = float(initial_bankroll)
    if not history:
        return [0], [ib]
    return list(range(0, len(history) + 1)), [ib] + [float(x) for x in history]


def try_show_bankroll_chart(
    summaries: list[ParallelParticipantSummary],
    initial_bankroll: float,
    *,
    title: str | None = None,
) -> bool:
    """
    Plot one line per strategy (same order as the results table: highest final bankroll
    first). Opens the chart in the default browser (Plotly).

    Returns True if a figure was generated and ``show()`` completed without error, False
    if plotly is not installed or there is nothing to plot.
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        return False

    if not summaries:
        return False

    ordered = sorted(summaries, key=lambda r: r.final_bankroll, reverse=True)
    fig = go.Figure()
    for row in ordered:
        xs, ys = bankroll_xy_for_run(row.bankroll_after_each_round, initial_bankroll)
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name=row.name,
                line=dict(width=2),
                marker=dict(size=5),
            )
        )

    ib = float(initial_bankroll)
    fig.add_hline(
        y=ib,
        line_dash="dash",
        line_color="rgba(80,80,80,0.85)",
        line_width=1.5,
        annotation_text="Starting bankroll",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title=title or "Bankroll by round",
        xaxis_title="Round (0 = start, n = after round n)",
        yaxis_title="Bankroll",
        template="plotly_white",
        height=640,
        width=1000,
        legend=dict(
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=10),
        ),
        margin=dict(r=200, t=60, b=60, l=70),
    )

    try:
        fig.show()
    except Exception:
        return False
    return True
