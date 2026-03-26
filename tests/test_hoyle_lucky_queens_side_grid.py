"""Tests for Hoyle low × Lucky Queens 4×4 side-bet grid strategies."""

import random
import unittest

from casino_sim.games.lucky_queens_blackjack import LuckyQueensBlackjack
from casino_sim.simulation.lucky_queens_parallel import (
    SIDE_BET_BLOCK_BONUS,
    SIDE_BET_LUCKY_QUEENS,
    LuckyQueensParallelSession,
)
from casino_sim.strategies.blackjack import lucky_queens as lq_grid
from casino_sim.strategies.blackjack.lucky_queens import (
    HoyleLuckyQueensMidMidStrategy,
    HoyleLuckyQueensMinMinStrategy,
    HoyleLuckyQueensPassPassStrategy,
)
from casino_sim.strategies.blackjack.lucky_queens.hoyle_low_side_grid import (
    _SideTier,
    _stake_for_tier,
)


class StakeForTierTests(unittest.TestCase):
    def test_hi_nonpositive_returns_zero(self) -> None:
        for tier in _SideTier:
            self.assertEqual(_stake_for_tier(tier, 5.0, 0.0, 100.0), 0.0)
            self.assertEqual(_stake_for_tier(tier, 5.0, -1.0, 100.0), 0.0)

    def test_pass_always_zero_even_when_limits_open(self) -> None:
        self.assertEqual(_stake_for_tier(_SideTier.PASS, 1.0, 100.0, 500.0), 0.0)

    def test_min_returns_lo(self) -> None:
        self.assertEqual(_stake_for_tier(_SideTier.MIN, 3.0, 10.0, 1.0), 3.0)

    def test_max_caps_by_bankroll(self) -> None:
        self.assertEqual(_stake_for_tier(_SideTier.MAX, 1.0, 100.0, 40.0), 40.0)
        self.assertEqual(_stake_for_tier(_SideTier.MAX, 1.0, 30.0, 100.0), 30.0)

    def test_mid_matches_hoyle_snap_and_clamp(self) -> None:
        # (10+30)/2 = 20, multiple of 5
        self.assertEqual(_stake_for_tier(_SideTier.MID, 10.0, 30.0, 500.0), 20.0)
        # mid 17 -> snap 15, within [10, 24]
        self.assertEqual(_stake_for_tier(_SideTier.MID, 10.0, 24.0, 500.0), 15.0)
        # snapped 15 exceeds hi 14 -> clamp to hi
        self.assertEqual(_stake_for_tier(_SideTier.MID, 12.0, 14.0, 500.0), 14.0)
        self.assertEqual(_stake_for_tier(_SideTier.MID, 10.0, 30.0, 15.0), 15.0)


class GridStrategyGameIdTests(unittest.TestCase):
    def test_all_exported_strategies_report_lucky_queens_game_id(self) -> None:
        self.assertEqual(len(lq_grid.__all__), 16)
        for name in lq_grid.__all__:
            cls = getattr(lq_grid, name)
            s = cls()
            with self.subTest(name=name):
                self.assertEqual(s.supported_game_id, LuckyQueensBlackjack.GAME_ID)


class PlaceSideBetsTests(unittest.TestCase):
    def test_mid_mid_proposes_expected_stakes(self) -> None:
        s = HoyleLuckyQueensMidMidStrategy()
        out = s.place_side_bets_before_deal(
            bankroll=500.0,
            main_wager=10.0,
            side_bet_limits={
                SIDE_BET_BLOCK_BONUS: (10.0, 30.0),
                SIDE_BET_LUCKY_QUEENS: (3.0, 3.0),
            },
        )
        self.assertEqual(out[SIDE_BET_BLOCK_BONUS], 20.0)
        self.assertEqual(out[SIDE_BET_LUCKY_QUEENS], 3.0)

    def test_pass_pass_zeros_both(self) -> None:
        s = HoyleLuckyQueensPassPassStrategy()
        out = s.place_side_bets_before_deal(
            bankroll=500.0,
            main_wager=10.0,
            side_bet_limits={
                SIDE_BET_BLOCK_BONUS: (10.0, 30.0),
                SIDE_BET_LUCKY_QUEENS: (1.0, 10.0),
            },
        )
        self.assertEqual(out[SIDE_BET_BLOCK_BONUS], 0.0)
        self.assertEqual(out[SIDE_BET_LUCKY_QUEENS], 0.0)


class HoyleLuckyQueensParallelSmokeTests(unittest.TestCase):
    def test_min_min_runs_short_session(self) -> None:
        random.seed(2)
        session = LuckyQueensParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=2,
            strategies=[("h", HoyleLuckyQueensMinMinStrategy())],
            side_bet_limits={
                SIDE_BET_BLOCK_BONUS: (1.0, 10.0),
                SIDE_BET_LUCKY_QUEENS: (1.0, 10.0),
            },
            deck_count=1,
            include_slug=False,
        )
        summaries = session.run()
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].rounds_played, 2)

    def test_pass_pass_runs_short_session(self) -> None:
        random.seed(3)
        session = LuckyQueensParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("p", HoyleLuckyQueensPassPassStrategy())],
            side_bet_limits={
                SIDE_BET_BLOCK_BONUS: (1.0, 10.0),
                SIDE_BET_LUCKY_QUEENS: (1.0, 10.0),
            },
            deck_count=1,
            include_slug=False,
        )
        summaries = session.run()
        self.assertEqual(summaries[0].rounds_played, 1)
        self.assertEqual(summaries[0].block_bonus_net, 0.0)
        self.assertEqual(summaries[0].lucky_queens_net, 0.0)


if __name__ == "__main__":
    unittest.main()
