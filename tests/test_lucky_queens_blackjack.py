"""Lucky Queens blackjack: side bet classification and branch with side stakes."""

import unittest

from casino_sim.games.lucky_queens_blackjack import (
    BLOCK_BONUS_PAYOUT_TO_ONE,
    LUCKY_QUEENS_PAYOUT_TO_ONE,
    BlockBonusCategory,
    LuckyQueensBlackjack,
    LuckyQueensCategory,
    SideBetRunStats,
    classify_block_bonus,
    classify_lucky_queens,
)
from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.models.player import Player
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


def c(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


class MinStand(StandardBlackjackPlayerStrategy):
    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return minimum_ante

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: tuple[Card, ...]
    ) -> bool:
        return False


class BlockBonusClassificationTests(unittest.TestCase):
    def test_wizard_examples_subset(self) -> None:
        Js, Qs, Ks = c(Rank.JACK, Suit.SPADES), c(Rank.QUEEN, Suit.SPADES), c(Rank.KING, Suit.SPADES)
        Jc, Qc = c(Rank.JACK, Suit.CLUBS), c(Rank.QUEEN, Suit.CLUBS)
        five_d, five_c, five_s = (
            c(Rank.FIVE, Suit.DIAMONDS),
            c(Rank.FIVE, Suit.CLUBS),
            c(Rank.FIVE, Suit.SPADES),
        )
        self.assertEqual(classify_block_bonus(Js, Qc, five_d), BlockBonusCategory.LOSS)
        self.assertEqual(classify_block_bonus(Js, Qc, five_c), BlockBonusCategory.NORMAL)
        self.assertEqual(classify_block_bonus(Js, Qs, Js), BlockBonusCategory.FLUSH)
        self.assertEqual(classify_block_bonus(Js, Jc, five_s), BlockBonusCategory.PAIR)
        self.assertEqual(classify_block_bonus(Js, Js, five_s), BlockBonusCategory.ULTIMATE)

    def test_pay_table_mapping(self) -> None:
        self.assertEqual(BLOCK_BONUS_PAYOUT_TO_ONE[BlockBonusCategory.ULTIMATE], 35)
        self.assertEqual(BLOCK_BONUS_PAYOUT_TO_ONE[BlockBonusCategory.NORMAL], 2)


class LuckyQueensClassificationTests(unittest.TestCase):
    def test_priority(self) -> None:
        qh = c(Rank.QUEEN, Suit.HEARTS)
        self.assertEqual(classify_lucky_queens(qh, qh), LuckyQueensCategory.QUEEN_HEARTS_PAIR)

        t10 = c(Rank.TEN, Suit.SPADES)
        self.assertEqual(classify_lucky_queens(t10, t10), LuckyQueensCategory.SUITED_PAIR)

        k_h = c(Rank.KING, Suit.HEARTS)
        self.assertEqual(classify_lucky_queens(k_h, qh), LuckyQueensCategory.SUITED_20)

        t_h = c(Rank.TEN, Suit.CLUBS)
        j_c = c(Rank.JACK, Suit.DIAMONDS)
        self.assertEqual(classify_lucky_queens(t_h, j_c), LuckyQueensCategory.ANY_20)

        self.assertEqual(classify_lucky_queens(qh, c(Rank.FIVE, Suit.CLUBS)), LuckyQueensCategory.ONE_QUEEN_HEARTS)

    def test_pay_table_mapping(self) -> None:
        self.assertEqual(LUCKY_QUEENS_PAYOUT_TO_ONE[LuckyQueensCategory.QUEEN_HEARTS_PAIR], 150)


class LuckyQueensBranchTests(unittest.TestCase):
    def test_side_bets_settle_after_hand(self) -> None:
        game = LuckyQueensBlackjack(
            bet_min=10,
            bet_max=100,
            deck_count=1,
            include_slug=False,
        )
        # Block: J♠ Q♣ vs 5♣ up = Normal Block; dealer busts on next hit.
        rig = [
            c(Rank.JACK, Suit.SPADES),
            c(Rank.QUEEN, Suit.CLUBS),
            c(Rank.FIVE, Suit.CLUBS),
            c(Rank.KING, Suit.DIAMONDS),
            c(Rank.NINE, Suit.HEARTS),
        ]
        game.deck.cards = rig + game.deck.cards[len(rig) :]

        p0, p1, d0, d1 = rig[0], rig[1], rig[2], rig[3]
        player = Player(name="p", bankroll=500.0, strategy=MinStand())
        stats = SideBetRunStats()

        # Main ante 10 already taken in real flow; mimic post-ante bankroll.
        player.bankroll = 490.0
        wager = 10
        out = game.play_strategy_branch_with_side_bets(
            player,
            wager,
            (p0, p1),
            (d0, d1),
            block_bonus_stake=5.0,
            lucky_queens_stake=5.0,
            stats=stats,
        )

        self.assertEqual(out.block_bonus_category, BlockBonusCategory.NORMAL)
        self.assertEqual(out.lucky_queens_category, LuckyQueensCategory.ANY_20)
        self.assertEqual(stats.block_stakes, 1)
        self.assertEqual(stats.block_profitable, 1)
        self.assertEqual(stats.lucky_queens_stakes, 1)
        self.assertEqual(stats.lucky_queens_profitable, 1)
        self.assertEqual(stats.lucky_queens_losses, 0)
        # Normal block 2:1 on 5 -> return 5 + 10 = 15; any 20 3:1 -> 5 + 15 = 20
        self.assertAlmostEqual(out.block_bonus_chips_returned, 15.0)
        self.assertAlmostEqual(out.lucky_queens_chips_returned, 20.0)


if __name__ == "__main__":
    unittest.main()
