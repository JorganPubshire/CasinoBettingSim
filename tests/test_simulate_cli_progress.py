"""Tests for simulate_cli progress bar formatting (helpers live in simulate_cli)."""

import sys
import unittest
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import simulate_cli as sc  # noqa: E402


class SimulateCliProgressTests(unittest.TestCase):
    def test_percent_integer_floor(self) -> None:
        self.assertEqual(sc._simulation_progress_percent(0, 10), 0)
        self.assertEqual(sc._simulation_progress_percent(1, 10), 10)
        self.assertEqual(sc._simulation_progress_percent(9, 10), 90)
        self.assertEqual(sc._simulation_progress_percent(10, 10), 100)

    def test_line_full_solid(self) -> None:
        self.assertEqual(
            sc._simulation_progress_line(10, 10, blink_on=True),
            "[==========] 100%",
        )
        self.assertEqual(
            sc._simulation_progress_line(10, 10, blink_on=False),
            "[==========] 100%",
        )

    def test_line_zero_blinks_first_cell_only(self) -> None:
        on = sc._simulation_progress_line(0, 10, blink_on=True)
        off = sc._simulation_progress_line(0, 10, blink_on=False)
        self.assertTrue(on.startswith("[="))
        self.assertTrue(off.startswith("[ "))

    def test_line_seventy_percent_seven_solid_one_blink_slot(self) -> None:
        on = sc._simulation_progress_line(7, 10, blink_on=True)
        off = sc._simulation_progress_line(7, 10, blink_on=False)
        self.assertIn("] 70%", on)
        self.assertEqual(on.count("="), 8)
        self.assertEqual(off.count("="), 7)


if __name__ == "__main__":
    unittest.main()
