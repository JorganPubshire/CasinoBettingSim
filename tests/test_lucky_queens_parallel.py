"""Lucky Queens parallel session smoke tests."""

import random
import unittest
from collections.abc import Mapping

from casino_sim.games.lucky_queens_blackjack import LuckyQueensBlackjack
from casino_sim.simulation.lucky_queens_parallel import (
    SIDE_BET_BLOCK_BONUS,
    SIDE_BET_LUCKY_QUEENS,
    LuckyQueensParallelSession,
)
from casino_sim.strategies.blackjack.standard.dummy_strategy import DummyStrategy


class FixedSideBetStrategy(DummyStrategy):
    """Dummy that always proposes fixed side stakes (host still validates limits)."""

    def __init__(self, block: float, lucky: float) -> None:
        super().__init__()
        self._block = float(block)
        self._lucky = float(lucky)

    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = bankroll, main_wager, side_bet_limits
        return {
            SIDE_BET_BLOCK_BONUS: self._block,
            SIDE_BET_LUCKY_QUEENS: self._lucky,
        }


class LuckyQueensParallelSessionTests(unittest.TestCase):
    def test_rejects_standard_only_strategy_game_id(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            LuckyQueensParallelSession(
                bet_min=10,
                bet_max=100,
                initial_bankroll=100.0,
                rounds=1,
                strategies=[("d", DummyStrategy())],
                deck_count=1,
                include_slug=False,
            )
        self.assertIn(LuckyQueensBlackjack.GAME_ID, str(ctx.exception))

    def test_run_with_side_limits_and_strategy_stakes(self) -> None:
        random.seed(0)
        session = LuckyQueensParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=2,
            strategies=[("d", FixedSideBetStrategy(1.0, 1.0))],
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
        self.assertEqual(len(summaries[0].bankroll_after_each_round), 2)
        self.assertIsInstance(summaries[0].block_bonus_net, float)
        self.assertIsInstance(summaries[0].lucky_queens_net, float)

    def test_run_no_side_bets_when_limits_zero(self) -> None:
        random.seed(1)
        session = LuckyQueensParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("d", FixedSideBetStrategy(5.0, 5.0))],
            side_bet_limits={
                SIDE_BET_BLOCK_BONUS: (0.0, 0.0),
                SIDE_BET_LUCKY_QUEENS: (0.0, 0.0),
            },
            deck_count=1,
            include_slug=False,
        )
        summaries = session.run()
        self.assertEqual(summaries[0].block_bonus_net, 0.0)
        self.assertEqual(summaries[0].lucky_queens_net, 0.0)


if __name__ == "__main__":
    unittest.main()
