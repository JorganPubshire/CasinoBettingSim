import unittest

from casino_sim.models.betting import BettingPhase, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.strategies.blackjack.standard.hoyle_basic_strategy import (
    HoyleBasicStrategyHigh,
    HoyleBasicStrategyLow,
    HoyleBasicStrategyMid,
    hoyle_basic_action,
)


def c(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class HoyleBasicStrategyTests(unittest.TestCase):
    def test_hard_16_vs_10_hits(self) -> None:
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.SIX, Suit.DIAMONDS))
        up = c(Rank.TEN, Suit.HEARTS)
        self.assertEqual(
            hoyle_basic_action(hand, up, can_double=True, can_split=False),
            PlayerAction.HIT,
        )

    def test_hard_12_vs_5_stands(self) -> None:
        hand = (c(Rank.SEVEN, Suit.CLUBS), c(Rank.FIVE, Suit.DIAMONDS))
        up = c(Rank.FIVE, Suit.HEARTS)
        self.assertEqual(
            hoyle_basic_action(hand, up, can_double=True, can_split=False),
            PlayerAction.STAND,
        )

    def test_pair_aces_always_split(self) -> None:
        hand = (c(Rank.ACE, Suit.CLUBS), c(Rank.ACE, Suit.DIAMONDS))
        up = c(Rank.KING, Suit.HEARTS)
        self.assertEqual(
            hoyle_basic_action(hand, up, can_double=True, can_split=True),
            PlayerAction.SPLIT,
        )

    def test_pair_tens_never_split(self) -> None:
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.KING, Suit.DIAMONDS))
        up = c(Rank.SIX, Suit.HEARTS)
        act = hoyle_basic_action(hand, up, can_double=True, can_split=True)
        self.assertNotEqual(act, PlayerAction.SPLIT)

    def test_never_insurance(self) -> None:
        s = HoyleBasicStrategyLow()
        hand = (c(Rank.TEN, Suit.CLUBS), c(Rank.NINE, Suit.DIAMONDS))
        self.assertFalse(s.take_insurance(1000.0, 10.0, hand))

    def test_low_mid_high_ante(self) -> None:
        self.assertEqual(
            HoyleBasicStrategyLow().place_initial_ante(500.0, 25.0, 100.0), 25.0
        )
        self.assertEqual(
            HoyleBasicStrategyHigh().place_initial_ante(500.0, 25.0, 100.0), 100.0
        )
        self.assertEqual(
            HoyleBasicStrategyMid().place_initial_ante(500.0, 10.0, 100.0), 55.0
        )

    def test_decide_respects_split_flag(self) -> None:
        s = HoyleBasicStrategyLow()
        hand = (c(Rank.ACE, Suit.CLUBS), c(Rank.ACE, Suit.DIAMONDS))
        obs = GameObservation(
            phase=BettingPhase.MID_ROUND,
            player_hand=hand,
            visible_table_cards=(c(Rank.SIX, Suit.HEARTS),),
            visible_opponent_cards={},
            pot_size=10.0,
            split_allowed=False,
        )
        d = s.decide_bet(obs, 1000.0)
        self.assertNotEqual(d.action, PlayerAction.SPLIT)


if __name__ == "__main__":
    unittest.main()
