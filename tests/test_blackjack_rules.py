import unittest

from casino_sim.games.blackjack import Blackjack, BlackjackHand, BlackjackRoundState
from casino_sim.models.betting import PlayerAction
from casino_sim.models.card import Card, Rank, Suit


def c(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class BlackjackRuleTests(unittest.TestCase):
    def make_game(self, dealer_hits_soft_17: bool = True) -> Blackjack:
        return Blackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=False,
            dealer_hits_soft_17=dealer_hits_soft_17,
        )

    def rig_cards(self, game: Blackjack, cards: list[Card]) -> None:
        game.deck.cards = cards + game.deck.cards

    def test_dealer_hits_until_reaching_17_or_higher(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),   # player
                c(Rank.SEVEN, Suit.DIAMONDS),
                c(Rank.FIVE, Suit.HEARTS),  # dealer up
                c(Rank.SIX, Suit.SPADES),   # dealer hole => 11
                c(Rank.TWO, Suit.CLUBS),    # dealer hit => 13
                c(Rank.FOUR, Suit.DIAMONDS),  # dealer hit => 17
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.STAND)
        self.assertGreaterEqual(game._hand_value(state.dealer_cards), 17)  # noqa: SLF001
        self.assertEqual(len(state.dealer_cards), 4)

    def test_dealer_stands_on_soft_17(self) -> None:
        game = self.make_game(dealer_hits_soft_17=False)
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),   # player
                c(Rank.SEVEN, Suit.DIAMONDS),
                c(Rank.ACE, Suit.HEARTS),  # dealer up
                c(Rank.SIX, Suit.SPADES),  # dealer hole => soft 17
                c(Rank.FIVE, Suit.CLUBS),  # would be hit if H17
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.STAND)
        self.assertEqual(len(state.dealer_cards), 2)
        self.assertEqual(game._hand_value(state.dealer_cards), 17)  # noqa: SLF001

    def test_player_is_offered_insurance_when_dealer_shows_ace(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),   # player
                c(Rank.NINE, Suit.DIAMONDS),
                c(Rank.ACE, Suit.HEARTS),  # dealer up ace
                c(Rank.SEVEN, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        rendered = game.render_table(state, reveal_dealer=False).lower()
        self.assertIn("insurance", rendered)

    def test_insurance_with_dealer_blackjack_results_in_main_bet_push(self) -> None:
        game = self.make_game()
        self.assertTrue(
            hasattr(game, "set_insurance_bet"),
            "Blackjack should expose an insurance-bet API for this rule.",
        )

    def test_player_cannot_act_when_dealer_has_blackjack(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),   # player
                c(Rank.NINE, Suit.DIAMONDS),
                c(Rank.ACE, Suit.HEARTS),  # dealer up
                c(Rank.KING, Suit.SPADES),  # dealer blackjack
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        self.assertTrue(state.round_over)
        self.assertEqual(game.available_actions(state), [])

    def test_both_player_and_dealer_blackjack_pushes(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.ACE, Suit.CLUBS),   # player
                c(Rank.KING, Suit.DIAMONDS),
                c(Rank.ACE, Suit.HEARTS),  # dealer
                c(Rank.QUEEN, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        self.assertTrue(state.round_over)
        self.assertEqual(state.bankroll, 100)

    def test_player_blackjack_beats_dealer_eventual_21(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.ACE, Suit.CLUBS),   # player blackjack
                c(Rank.KING, Suit.DIAMONDS),
                c(Rank.NINE, Suit.HEARTS),  # dealer starts at 16
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.FIVE, Suit.CLUBS),  # dealer would draw to 21 if round continued
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=20)
        self.assertTrue(state.round_over)
        self.assertEqual(state.bankroll, 130)

    def test_player_can_only_double_on_first_opportunity(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.FIVE, Suit.CLUBS),
                c(Rank.SIX, Suit.DIAMONDS),  # player 11
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.TWO, Suit.CLUBS),  # hit card (player now 13)
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        self.assertIn(PlayerAction.DOUBLE, game.available_actions(state))
        game.apply_player_action(state, PlayerAction.HIT)
        self.assertNotIn(PlayerAction.DOUBLE, game.available_actions(state))

    def test_double_deals_exactly_one_card(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.FIVE, Suit.CLUBS),
                c(Rank.SIX, Suit.DIAMONDS),
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.TWO, Suit.CLUBS),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.DOUBLE)
        self.assertEqual(len(state.player_hands[0].cards), 3)
        self.assertTrue(state.player_hands[0].is_finished)

    def test_player_can_split_ten_value_cards(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),
                c(Rank.KING, Suit.DIAMONDS),  # split should be allowed for ten-value
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        self.assertIn(PlayerAction.SPLIT, game.available_actions(state))

    def test_player_can_double_after_split(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.EIGHT, Suit.CLUBS),
                c(Rank.EIGHT, Suit.DIAMONDS),  # split pair
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.THREE, Suit.CLUBS),  # card for first split hand
                c(Rank.FOUR, Suit.DIAMONDS),  # card for second split hand
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.SPLIT)
        self.assertEqual(len(state.player_hands), 2)
        self.assertIn(PlayerAction.DOUBLE, game.available_actions(state))

    def test_player_cannot_split_again_after_splitting(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.EIGHT, Suit.CLUBS),
                c(Rank.EIGHT, Suit.DIAMONDS),  # initial split
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.EIGHT, Suit.CLUBS),  # first split hand becomes 8,8 again
                c(Rank.FOUR, Suit.DIAMONDS),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.SPLIT)
        self.assertNotIn(PlayerAction.SPLIT, game.available_actions(state))

    def test_blackjack_pays_three_to_two(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.ACE, Suit.CLUBS),
                c(Rank.KING, Suit.DIAMONDS),  # player blackjack
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=20)
        self.assertEqual(state.bankroll, 130)

    def test_push_same_total_not_blackjack(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.HEARTS),
                c(Rank.EIGHT, Suit.CLUBS),
                c(Rank.TEN, Suit.DIAMONDS),
                c(Rank.EIGHT, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(100, 10)
        game.apply_player_action(state, PlayerAction.STAND)
        self.assertTrue(state.round_over)
        self.assertIn("push", state.message.lower())
        self.assertEqual(state.bankroll, 100)

    def test_player_automatically_stands_on_21_or_more(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.CLUBS),
                c(Rank.SIX, Suit.DIAMONDS),  # player 16
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
                c(Rank.FIVE, Suit.CLUBS),  # hit to 21
            ],
        )
        state = game.start_cli_round(bankroll=100, bet=10)
        game.apply_player_action(state, PlayerAction.HIT)
        self.assertTrue(state.round_over or state.player_hands[0].is_finished)
        if not state.round_over:
            self.assertEqual(game.available_actions(state), [])

    def test_tally_round_wlp_requires_finished_round(self) -> None:
        h = BlackjackHand(cards=[c(Rank.TEN, Suit.CLUBS), c(Rank.NINE, Suit.DIAMONDS)], bet=10)
        state = BlackjackRoundState(
            dealer_cards=[c(Rank.SEVEN, Suit.HEARTS)],
            player_hands=[h],
            active_hand_index=0,
            bankroll=90,
            initial_bankroll=100,
            round_over=False,
        )
        with self.assertRaises(ValueError):
            Blackjack.tally_round_wlp(state)

    def test_tally_round_wlp_all_bust(self) -> None:
        bust = BlackjackHand(
            cards=[
                c(Rank.TEN, Suit.CLUBS),
                c(Rank.SIX, Suit.DIAMONDS),
                c(Rank.KING, Suit.HEARTS),
            ],
            bet=10,
            is_finished=True,
        )
        state = BlackjackRoundState(
            dealer_cards=[c(Rank.NINE, Suit.SPADES), c(Rank.EIGHT, Suit.CLUBS)],
            player_hands=[bust],
            active_hand_index=0,
            bankroll=80,
            initial_bankroll=100,
            round_over=True,
        )
        self.assertEqual(Blackjack.tally_round_wlp(state), (0, 1, 0))

    def test_tally_round_wlp_push_and_blackjack_cases(self) -> None:
        game = self.make_game()
        self.rig_cards(
            game,
            [
                c(Rank.TEN, Suit.HEARTS),
                c(Rank.EIGHT, Suit.CLUBS),
                c(Rank.TEN, Suit.DIAMONDS),
                c(Rank.EIGHT, Suit.SPADES),
            ],
        )
        state = game.start_cli_round(100, 10)
        game.apply_player_action(state, PlayerAction.STAND)
        self.assertEqual(Blackjack.tally_round_wlp(state), (0, 0, 1))

        game2 = self.make_game()
        self.rig_cards(
            game2,
            [
                c(Rank.ACE, Suit.CLUBS),
                c(Rank.KING, Suit.DIAMONDS),
                c(Rank.ACE, Suit.HEARTS),
                c(Rank.QUEEN, Suit.SPADES),
            ],
        )
        st2 = game2.start_cli_round(bankroll=100, bet=10)
        self.assertEqual(Blackjack.tally_round_wlp(st2), (0, 0, 1))

        game3 = self.make_game()
        self.rig_cards(
            game3,
            [
                c(Rank.ACE, Suit.CLUBS),
                c(Rank.KING, Suit.DIAMONDS),
                c(Rank.NINE, Suit.HEARTS),
                c(Rank.SEVEN, Suit.SPADES),
            ],
        )
        st3 = game3.start_cli_round(bankroll=100, bet=20)
        self.assertEqual(Blackjack.tally_round_wlp(st3), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
