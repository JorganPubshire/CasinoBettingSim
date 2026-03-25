"""Tests for cut-card shoe refresh and slug presence (parallel + Blackjack)."""

import unittest
from typing import Sequence

from casino_sim.games.blackjack import Blackjack
from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.models.deck import Deck
from casino_sim.simulation.standard_blackjack_parallel import StandardBlackjackParallelSession
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


def c(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class MinBetStand(StandardBlackjackPlayerStrategy):
    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return minimum_ante

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False


class ShoeRefreshTests(unittest.TestCase):
    def test_deck_has_slug_false_until_inserted(self) -> None:
        d = Deck(deck_count=1, include_slug=False)
        self.assertFalse(d.has_slug())
        d.insert_slug(position=0)
        self.assertTrue(d.has_slug())

    def test_deck_reset_with_include_slug_inserts_slug(self) -> None:
        d = Deck(deck_count=1, include_slug=True)
        self.assertTrue(d.has_slug())
        d.cards.clear()
        self.assertFalse(d.has_slug())
        d.reset()
        self.assertTrue(d.has_slug())
        self.assertEqual(d.cards_remaining(), 53)

    def test_refresh_shoe_no_slug_mode_when_short(self) -> None:
        game = Blackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=False,
        )
        game.deck.cards = [c(Rank.TWO, Suit.CLUBS), c(Rank.THREE, Suit.DIAMONDS)]
        self.assertTrue(game.refresh_shoe_if_needed(min_cards_remaining=4))
        self.assertGreaterEqual(game.deck.cards_remaining(), 50)
        self.assertFalse(game.deck.has_slug())

    def test_refresh_shoe_slug_mode_when_slug_missing(self) -> None:
        game = Blackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=True,
        )
        game.deck.cards = [c(Rank.TWO, Suit.CLUBS), c(Rank.THREE, Suit.DIAMONDS)]
        self.assertTrue(game.refresh_shoe_if_needed(min_cards_remaining=4))
        self.assertTrue(game.deck.has_slug())
        self.assertGreaterEqual(game.deck.cards_remaining(), 50)

    def test_refresh_shoe_slug_mode_when_enough_cards_and_slug_present(self) -> None:
        game = Blackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=True,
        )
        before = game.deck.cards_remaining()
        self.assertTrue(game.deck.has_slug())
        self.assertFalse(game.refresh_shoe_if_needed(min_cards_remaining=4))
        self.assertEqual(game.deck.cards_remaining(), before)

    def test_draw_playable_replenishes_when_empty_with_slug_mode(self) -> None:
        game = Blackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=True,
        )
        game.deck.cards = []
        game._branch_dealt = []
        card = game._draw_playable_card()
        self.assertFalse(card.is_slug)
        self.assertTrue(game.deck.has_slug())
        game._branch_dealt = None

    def test_parallel_session_refreshes_before_deal_when_tail_invalid(self) -> None:
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=2,
            strategies=[("a", MinBetStand()), ("b", MinBetStand())],
            deck_count=1,
            include_slug=True,
        )
        session._master.deck.cards = [c(Rank.FIVE, Suit.CLUBS), c(Rank.SIX, Suit.DIAMONDS)]
        session.run()
        self.assertTrue(session._master.deck.has_slug())
        self.assertGreaterEqual(session._master.deck.cards_remaining(), 4)


if __name__ == "__main__":
    unittest.main()
