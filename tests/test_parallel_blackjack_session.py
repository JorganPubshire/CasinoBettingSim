import random
import unittest
from typing import Sequence

from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.simulation.standard_blackjack_parallel import (
    StandardBlackjackParallelSession,
    canonical_exposure_suffix,
)
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


def card(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class AlwaysMinBetStandStrategy(StandardBlackjackPlayerStrategy):
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


class HitOnceThenStandStrategy(StandardBlackjackPlayerStrategy):
    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return minimum_ante

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        if len(observation.player_hand) == 2:
            return BettingDecision(amount=0.0, action=PlayerAction.HIT)
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False


class RecordingExposureStrategy(StandardBlackjackPlayerStrategy):
    def __init__(self) -> None:
        self.exposures: list[list[Card]] = []

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

    def on_post_round_exposure(self, cards) -> None:
        self.exposures.append(list(cards))


class ShuffleCountStrategy(StandardBlackjackPlayerStrategy):
    def __init__(self) -> None:
        self.shuffle_count = 0

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

    def on_deck_shuffled(self) -> None:
        self.shuffle_count += 1


class WrongGameStrategy(StandardBlackjackPlayerStrategy):
    @property
    def supported_game_id(self) -> str:
        return "other.game"

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


class ParallelBlackjackSessionTests(unittest.TestCase):
    def test_rejects_strategy_for_wrong_game(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            StandardBlackjackParallelSession(
                bet_min=10,
                bet_max=100,
                initial_bankroll=1000.0,
                rounds=1,
                strategies=[("wrong", WrongGameStrategy())],
                deck_count=1,
                include_slug=False,
            )
        self.assertIn("not built", str(ctx.exception).lower())

    def test_canonical_exposure_suffix_matches_lcp_rule(self) -> None:
        a = [card(Rank.TWO, Suit.CLUBS), card(Rank.THREE, Suit.DIAMONDS)]
        b = [
            card(Rank.TWO, Suit.CLUBS),
            card(Rank.THREE, Suit.DIAMONDS),
            card(Rank.FOUR, Suit.HEARTS),
            card(Rank.FIVE, Suit.SPADES),
        ]
        self.assertEqual(
            canonical_exposure_suffix(a, b),
            [card(Rank.FOUR, Suit.HEARTS), card(Rank.FIVE, Suit.SPADES)],
        )

    def test_parallel_syncs_deck_to_deepest_branch(self) -> None:
        stander = AlwaysMinBetStandStrategy()
        hitter = HitOnceThenStandStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("stand", stander), ("hit_once", hitter)],
            deck_count=1,
            include_slug=False,
        )
        # After shuffle, replace with fixed order (top = first dealt).
        # Initial: P 5+6=11, D 10+7=17 (dealer stands). Stand uses 4 cards from tail.
        # Hit-once: P draws next (8) -> 19, dealer still 17. Same dealer path, one extra player card.
        rig = [
            card(Rank.FIVE, Suit.CLUBS),
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.TEN, Suit.HEARTS),
            card(Rank.SEVEN, Suit.SPADES),
            card(Rank.EIGHT, Suit.CLUBS),
        ]
        deck = session._master.deck.cards
        total_before = len(deck)
        session._master.deck.cards = rig + deck[len(rig) :]

        session.run()

        self.assertEqual(session._master.deck.cards_remaining(), total_before - 5)

    def test_exposure_feeds_shorter_branch_extra_cards(self) -> None:
        rec = RecordingExposureStrategy()
        hitter = HitOnceThenStandStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("rec", rec), ("hit", hitter)],
            deck_count=1,
            include_slug=False,
        )
        rig = [
            card(Rank.FIVE, Suit.CLUBS),
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.TEN, Suit.HEARTS),
            card(Rank.SEVEN, Suit.SPADES),
            card(Rank.EIGHT, Suit.CLUBS),
        ]
        session._master.deck.cards = rig + session._master.deck.cards[len(rig) :]

        session.run()

        self.assertEqual(len(rec.exposures), 1)
        self.assertEqual(len(rec.exposures[0]), 1)
        self.assertEqual(rec.exposures[0][0], card(Rank.EIGHT, Suit.CLUBS))

    def test_busted_participant_stops_playing_and_reports_round(self) -> None:
        # Initial shoe shuffle is RNG-dependent; fix seed so the rigged first hand
        # and subsequent tails deterministically bust before five rounds complete.
        random.seed(1)
        strat = AlwaysMinBetStandStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=25.0,
            rounds=5,
            strategies=[("p", strat)],
            deck_count=1,
            include_slug=False,
        )
        rig = [
            card(Rank.TEN, Suit.CLUBS),
            card(Rank.TWO, Suit.DIAMONDS),
            card(Rank.KING, Suit.HEARTS),
            card(Rank.NINE, Suit.SPADES),
        ]
        session._master.deck.cards = rig + session._master.deck.cards[len(rig) :]

        summary = session.run()[0]
        self.assertLess(summary.final_bankroll, 10)
        self.assertIsNotNone(summary.busted_on_round)
        self.assertEqual(summary.rounds_played, summary.busted_on_round)

    def test_slug_triggers_shuffle_notification_for_all_strategies(self) -> None:
        s1 = ShuffleCountStrategy()
        s2 = ShuffleCountStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("a", s1), ("b", s2)],
            deck_count=1,
            include_slug=False,
        )
        # Player 16 vs dealer 11; dealer must hit and draw the slug next.
        small = [
            card(Rank.TEN, Suit.CLUBS),
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.SIX, Suit.HEARTS),
            card(Rank.FIVE, Suit.SPADES),
            Card.slug(),
        ]
        session._master.deck.cards = small + session._master.deck.cards[len(small) :]

        session.run()

        self.assertGreaterEqual(s1.shuffle_count, 1)
        self.assertGreaterEqual(s2.shuffle_count, 1)

    def test_total_won_tracks_positive_stack_delta_on_win(self) -> None:
        """Branch play must credit Player.total_won (CLI \"Paid out\") on winning hands."""
        random.seed(0)
        stander = AlwaysMinBetStandStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("p", stander)],
            deck_count=1,
            include_slug=False,
        )
        # P 17 stands; dealer 6+5=11, hits 5 -> 16, hits 10 -> 26 bust.
        rig = [
            card(Rank.TEN, Suit.CLUBS),
            card(Rank.SEVEN, Suit.DIAMONDS),
            card(Rank.SIX, Suit.HEARTS),
            card(Rank.FIVE, Suit.SPADES),
            card(Rank.FIVE, Suit.CLUBS),
            card(Rank.TEN, Suit.DIAMONDS),
        ]
        session._master.deck.cards = rig + session._master.deck.cards[len(rig) :]

        summary = session.run()[0]
        self.assertEqual(summary.hand_busts, 0)
        self.assertGreater(summary.total_won, 0.0)
        self.assertEqual(summary.final_bankroll, 510.0)
        self.assertEqual((summary.wins, summary.losses, summary.pushes), (1, 0, 0))

    def test_bankroll_snapshots_each_round_and_extrema(self) -> None:
        random.seed(1)
        stander = AlwaysMinBetStandStrategy()
        rounds = 3
        init = 500.0
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=init,
            rounds=rounds,
            strategies=[("p", stander)],
            deck_count=1,
            include_slug=False,
        )
        summary = session.run()[0]
        self.assertEqual(len(summary.bankroll_after_each_round), rounds)
        self.assertEqual(summary.bankroll_after_each_round[-1], summary.final_bankroll)
        self.assertLessEqual(summary.min_bankroll, summary.final_bankroll)
        self.assertGreaterEqual(summary.max_bankroll, summary.final_bankroll)
        self.assertLessEqual(summary.min_bankroll, init + 1e-9)
        self.assertGreaterEqual(summary.max_bankroll, init - 1e-9)

    def test_hand_busts_count_player_hands_over_21(self) -> None:
        random.seed(0)
        hitter = HitOnceThenStandStrategy()
        session = StandardBlackjackParallelSession(
            bet_min=10,
            bet_max=100,
            initial_bankroll=500.0,
            rounds=1,
            strategies=[("p", hitter)],
            deck_count=1,
            include_slug=False,
        )
        # P 10+6=16, one hit K -> 26 bust. Dealer K+7=17 (unused if player busts first).
        rig = [
            card(Rank.TEN, Suit.CLUBS),
            card(Rank.SIX, Suit.DIAMONDS),
            card(Rank.KING, Suit.HEARTS),
            card(Rank.SEVEN, Suit.SPADES),
            card(Rank.KING, Suit.CLUBS),
        ]
        session._master.deck.cards = rig + session._master.deck.cards[len(rig) :]

        summary = session.run()[0]
        self.assertEqual(summary.hand_busts, 1)
        self.assertEqual(summary.total_won, 0.0)
        self.assertEqual((summary.wins, summary.losses, summary.pushes), (0, 1, 0))


if __name__ == "__main__":
    unittest.main()
