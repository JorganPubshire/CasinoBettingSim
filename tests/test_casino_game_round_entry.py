import unittest
from typing import Sequence

from casino_sim.games.blackjack import Blackjack
from casino_sim.interfaces.player_strategy import PlayerStrategy
from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card
from casino_sim.models.player import Player


class _SpyStrategy(PlayerStrategy):
    def __init__(self, ante_to_return: float) -> None:
        self.ante_to_return = ante_to_return
        self.place_ante_calls = 0
        self.decide_bet_calls = 0
        self.take_insurance_calls = 0

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        self.place_ante_calls += 1
        return self.ante_to_return

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        self.decide_bet_calls += 1
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        self.take_insurance_calls += 1
        return False


class CasinoGameRoundEntryTests(unittest.TestCase):
    def make_game(self) -> Blackjack:
        return Blackjack(bet_min=10, bet_max=100, deck_count=1, include_slug=False)

    def test_no_bet_skips_all_further_strategy_callbacks(self) -> None:
        game = self.make_game()
        strategy = _SpyStrategy(ante_to_return=0.0)
        player = Player(name="P1", bankroll=200.0, strategy=strategy)

        game.play_round(player)

        self.assertEqual(strategy.place_ante_calls, 1)
        self.assertEqual(strategy.decide_bet_calls, 0)
        self.assertEqual(strategy.take_insurance_calls, 0)
        self.assertEqual(player.bankroll, 200.0)

    def test_invalid_bet_skips_all_further_strategy_callbacks(self) -> None:
        game = self.make_game()
        strategy = _SpyStrategy(ante_to_return=1000.0)
        player = Player(name="P1", bankroll=200.0, strategy=strategy)

        game.play_round(player)

        self.assertEqual(strategy.place_ante_calls, 1)
        self.assertEqual(strategy.decide_bet_calls, 0)
        self.assertEqual(strategy.take_insurance_calls, 0)
        self.assertEqual(player.bankroll, 200.0)


if __name__ == "__main__":
    unittest.main()
