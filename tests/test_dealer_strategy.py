import unittest

from casino_sim.models.betting import BettingPhase, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.strategies.blackjack.standard.dealer_strategy import DealerStrategy


def c(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class DealerStrategyTests(unittest.TestCase):
    def _obs(self, *cards: Card) -> GameObservation:
        return GameObservation(
            phase=BettingPhase.MID_ROUND,
            player_hand=cards,
            visible_table_cards=(c(Rank.SIX, Suit.HEARTS),),
            visible_opponent_cards={},
            pot_size=10.0,
            double_allowed=True,
            split_allowed=True,
        )

    def test_antes_minimum(self) -> None:
        s = DealerStrategy()
        self.assertEqual(s.place_initial_ante(500.0, 25.0, 100.0), 25.0)

    def test_no_insurance(self) -> None:
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.NINE, Suit.DIAMONDS))
        self.assertFalse(DealerStrategy().take_insurance(1000.0, 10.0, hand))

    def test_hard_16_hits(self) -> None:
        s = DealerStrategy()
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.SIX, Suit.DIAMONDS))
        d = s.decide_bet(self._obs(*hand), 1000.0)
        self.assertEqual(d.action, PlayerAction.HIT)

    def test_hard_17_stands(self) -> None:
        s = DealerStrategy(dealer_hits_soft_17=True)
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.SEVEN, Suit.DIAMONDS))
        d = s.decide_bet(self._obs(*hand), 1000.0)
        self.assertEqual(d.action, PlayerAction.STAND)

    def test_soft_17_hits_when_h17(self) -> None:
        s = DealerStrategy(dealer_hits_soft_17=True)
        hand = (c(Rank.ACE, Suit.CLUBS), c(Rank.SIX, Suit.DIAMONDS))
        d = s.decide_bet(self._obs(*hand), 1000.0)
        self.assertEqual(d.action, PlayerAction.HIT)

    def test_soft_17_stands_when_s17(self) -> None:
        s = DealerStrategy(dealer_hits_soft_17=False)
        hand = (c(Rank.ACE, Suit.CLUBS), c(Rank.SIX, Suit.DIAMONDS))
        d = s.decide_bet(self._obs(*hand), 1000.0)
        self.assertEqual(d.action, PlayerAction.STAND)


if __name__ == "__main__":
    unittest.main()
