"""Tests for simulate CLI result table formatting."""

import unittest

from dataclasses import replace

from casino_sim.cli.simulate_results import format_usd, pad_strategy_label, results_table_lines
from casino_sim.simulation.standard_blackjack_parallel import ParallelParticipantSummary


def _row(**kwargs) -> ParallelParticipantSummary:
    base = ParallelParticipantSummary(
        name="X",
        final_bankroll=0.0,
        total_wagered=0.0,
        total_won=0.0,
        rounds_played=0,
        busted_on_round=None,
        hand_busts=0,
        wins=0,
        losses=0,
        pushes=0,
    )
    return replace(base, **kwargs)


class SimulateResultsFormatTests(unittest.TestCase):
    def test_format_usd_positive_with_commas(self) -> None:
        self.assertEqual(format_usd(1234.56), "$1,234.56")
        self.assertEqual(format_usd(1000000.0), "$1,000,000.00")

    def test_format_usd_negative(self) -> None:
        self.assertEqual(format_usd(-99.5), "-$99.50")

    def test_pad_strategy_truncates_long_name(self) -> None:
        long = "A" * 50
        out = pad_strategy_label(long, width=10)
        self.assertEqual(len(out), 10)
        self.assertTrue(out.endswith("…"))

    def test_results_table_fixed_width_rows(self) -> None:
        summaries = [
            _row(
                name="Short",
                final_bankroll=10000.0,
                total_wagered=5000.0,
                total_won=5200.0,
                rounds_played=100,
                busted_on_round=None,
                hand_busts=3,
                wins=40,
                losses=45,
                pushes=15,
            ),
            _row(
                name="Another",
                final_bankroll=0.0,
                total_wagered=1000000.0,
                total_won=0.0,
                rounds_played=1,
                busted_on_round=1,
                hand_busts=0,
                wins=0,
                losses=1,
                pushes=0,
            ),
        ]
        lines, sep_w = results_table_lines(summaries, initial_bankroll=5000.0)
        self.assertGreaterEqual(len(lines), 4)
        self.assertEqual(len(lines[0]), sep_w)
        for line in lines[2:]:
            self.assertEqual(
                len(line),
                sep_w,
                f"row length mismatch: {line!r}",
            )
        self.assertIn("$10,000.00", lines[2])
        self.assertIn("$0.00", lines[3])
        net_line2 = lines[2]
        self.assertIn("$5,000.00", net_line2)
        self.assertIn("       40", lines[2])
        self.assertIn("       45", lines[2])
        self.assertIn("       15", lines[2])

    def test_net_column_uses_initial_bankroll(self) -> None:
        summaries = [
            _row(
                name="P",
                final_bankroll=7500.0,
                total_wagered=0.0,
                total_won=0.0,
                rounds_played=1,
                busted_on_round=None,
                hand_busts=0,
                wins=0,
                losses=0,
                pushes=0,
            )
        ]
        lines, _ = results_table_lines(summaries, initial_bankroll=10000.0)
        data = lines[2]
        self.assertIn("-$2,500.00", data)


if __name__ == "__main__":
    unittest.main()
