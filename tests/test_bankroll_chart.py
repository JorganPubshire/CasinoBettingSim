"""Tests for bankroll chart coordinate helper (no plotly required)."""

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from casino_sim.cli.bankroll_chart import bankroll_xy_for_run  # noqa: E402


class BankrollXYTests(unittest.TestCase):
    def test_empty_history_single_start_point(self) -> None:
        xs, ys = bankroll_xy_for_run((), 1000.0)
        self.assertEqual(xs, [0])
        self.assertEqual(ys, [1000.0])

    def test_three_rounds_inclusive_start(self) -> None:
        xs, ys = bankroll_xy_for_run((990.0, 1005.0, 998.0), 1000.0)
        self.assertEqual(xs, [0, 1, 2, 3])
        self.assertEqual(ys, [1000.0, 990.0, 1005.0, 998.0])


if __name__ == "__main__":
    unittest.main()
