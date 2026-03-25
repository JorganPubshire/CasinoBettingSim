"""
Debug recorder for :class:`StandardBlackjackParallelSession`.

Lives outside ``casino_sim.simulation`` to avoid import cycles with
``casino_sim.games.blackjack``.

When ``debug_parallel=True`` on the session, each strategy branch logs actions,
hands, bankroll, dealer cards, and deck counts. On any uncaught exception during
``run()``, the last round's log is printed to stderr.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParallelRoundDebugRecorder:
    """Accumulates per-strategy lines for one parallel round; survives until the next ``begin_round``."""

    round_number: int = 0
    master_shoe_before_shared_four: int = 0
    cloned_tail_after_shared_deal: int = -1
    _sections: list[tuple[str, list[str]]] = field(default_factory=list)

    def begin_round(self, round_number: int, master_shoe_cards_before_shared_deal: int) -> None:
        self.round_number = round_number
        self.master_shoe_before_shared_four = master_shoe_cards_before_shared_deal
        self.cloned_tail_after_shared_deal = -1
        self._sections.clear()

    def set_cloned_tail_remaining(self, count: int) -> None:
        self.cloned_tail_after_shared_deal = count

    def start_branch(self, strategy_name: str) -> None:
        self._sections.append((strategy_name, []))

    def append(self, line: str) -> None:
        if not self._sections:
            self.start_branch("(unnamed branch)")
        self._sections[-1][1].append(line)

    def format_report(self) -> str:
        lines = [
            "=== Parallel blackjack debug dump (last recorded round) ===",
            f"Round number: {self.round_number}",
            f"Master shoe — card count BEFORE shared 4-card deal: {self.master_shoe_before_shared_four}",
        ]
        if self.cloned_tail_after_shared_deal >= 0:
            lines.append(
                "Cloned tail — card count AFTER shared deal (identical copy for each strategy): "
                f"{self.cloned_tail_after_shared_deal}"
            )
        lines.append("")
        if not self._sections:
            lines.append("(No strategy branch had started yet this round.)")
        else:
            lines.append(
                "Each section is a strategy that entered play_strategy_branch (complete or partial log)."
            )
            lines.append("")
            for name, entries in self._sections:
                lines.append(f"--- Strategy: {name} ---")
                if not entries:
                    lines.append("  (no events after branch start)")
                else:
                    for e in entries:
                        lines.append(f"  {e}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"
