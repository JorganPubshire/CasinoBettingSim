import unittest
from typing import Sequence

from casino_sim.interfaces.player_strategy import PlayerStrategy
from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card
from casino_sim.models.player import Player


class _StubStrategy(PlayerStrategy):
    def __init__(self, ante_to_return: float) -> None:
        self._ante_to_return = ante_to_return

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return self._ante_to_return

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False


class StrategyBetValidationTests(unittest.TestCase):
    def test_invalid_strategy_ante_below_minimum_is_rejected(self) -> None:
        player = Player(name="P1", bankroll=500.0, strategy=_StubStrategy(ante_to_return=5.0))
        ante = player.place_ante(minimum_ante=25.0, maximum_ante=100.0)
        self.assertEqual(ante, 0.0)
        self.assertEqual(player.bankroll, 500.0)

    def test_invalid_strategy_ante_above_maximum_is_rejected(self) -> None:
        player = Player(name="P1", bankroll=500.0, strategy=_StubStrategy(ante_to_return=500.0))
        ante = player.place_ante(minimum_ante=25.0, maximum_ante=100.0)
        self.assertEqual(ante, 0.0)
        self.assertEqual(player.bankroll, 500.0)

    def test_invalid_strategy_ante_above_bankroll_is_rejected(self) -> None:
        player = Player(name="P1", bankroll=60.0, strategy=_StubStrategy(ante_to_return=100.0))
        ante = player.place_ante(minimum_ante=25.0, maximum_ante=100.0)
        self.assertEqual(ante, 0.0)
        self.assertEqual(player.bankroll, 60.0)


if __name__ == "__main__":
    unittest.main()
