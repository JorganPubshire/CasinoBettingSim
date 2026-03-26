"""
Lucky Queens blackjack: standard rules plus optional Block Bonus and Lucky Queens side bets.

Side stakes are collected before ``play_strategy_branch`` runs; settlements are applied
after the main hand finishes. Statistics can be aggregated per simulation run.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum

from casino_sim.games.blackjack import Blackjack, BlackjackBranchOutcome
from casino_sim.models.card import Card, Rank, Suit
from casino_sim.models.deck import Deck
from casino_sim.models.player import Player
from casino_sim.round_debug import ParallelRoundDebugRecorder


class BlockBonusCategory(Enum):
    LOSS = "loss"
    PUSH = "push"
    NORMAL = "normal"
    FLUSH = "flush"
    PAIR = "pair"
    ULTIMATE = "ultimate"


BLOCK_BONUS_PAYOUT_TO_ONE: dict[BlockBonusCategory, int] = {
    BlockBonusCategory.ULTIMATE: 35,
    BlockBonusCategory.PAIR: 10,
    BlockBonusCategory.FLUSH: 5,
    BlockBonusCategory.NORMAL: 2,
    BlockBonusCategory.PUSH: 0,
    BlockBonusCategory.LOSS: 0,
}


class LuckyQueensCategory(Enum):
    LOSS = "loss"
    ONE_QUEEN_HEARTS = "one_queen_hearts"
    ANY_20 = "any_20"
    SUITED_20 = "suited_20"
    SUITED_PAIR = "suited_pair"
    QUEEN_HEARTS_PAIR = "queen_hearts_pair"


LUCKY_QUEENS_PAYOUT_TO_ONE: dict[LuckyQueensCategory, int] = {
    LuckyQueensCategory.QUEEN_HEARTS_PAIR: 150,
    LuckyQueensCategory.SUITED_PAIR: 25,
    LuckyQueensCategory.SUITED_20: 10,
    LuckyQueensCategory.ANY_20: 3,
    LuckyQueensCategory.ONE_QUEEN_HEARTS: 2,
    LuckyQueensCategory.LOSS: 0,
}


def _rank_order(rank: Rank) -> int:
    order = (
        Rank.TWO,
        Rank.THREE,
        Rank.FOUR,
        Rank.FIVE,
        Rank.SIX,
        Rank.SEVEN,
        Rank.EIGHT,
        Rank.NINE,
        Rank.TEN,
        Rank.JACK,
        Rank.QUEEN,
        Rank.KING,
        Rank.ACE,
    )
    return order.index(rank) + 2


def _playable(c: Card) -> bool:
    return not c.is_slug and c.rank is not None and c.suit is not None


def classify_block_bonus(player_first: Card, player_second: Card, dealer_up: Card) -> BlockBonusCategory:
    """Block Bonus using dealer up-card; ace high. Order: Ultimate → Pair → Flush → Normal → Push → Loss."""
    for c in (player_first, player_second, dealer_up):
        if not _playable(c):
            raise ValueError("block bonus requires normal playing cards")

    p0, p1, d = player_first, player_second, dealer_up
    r0, r1, rd = p0.rank, p1.rank, d.rank
    s0, s1, sd = p0.suit, p1.suit, d.suit
    assert r0 and r1 and rd and s0 and s1 and sd
    v0, v1, vd = _rank_order(r0), _rank_order(r1), _rank_order(rd)

    if r0 == r1 and s0 == s1 and s0 == sd and v0 > vd:
        return BlockBonusCategory.ULTIMATE

    if r0 == r1 and s0 != s1:
        if s0 == sd and v0 > vd:
            return BlockBonusCategory.PAIR
        if s1 == sd and v1 > vd:
            return BlockBonusCategory.PAIR

    if s0 == s1 == sd and r0 != r1 and (v0 > vd or v1 > vd):
        return BlockBonusCategory.FLUSH

    if r0 != r1 and s0 != s1:
        match0 = s0 == sd
        match1 = s1 == sd
        if match0 and not match1 and v0 > vd:
            return BlockBonusCategory.NORMAL
        if match1 and not match0 and v1 > vd:
            return BlockBonusCategory.NORMAL

    if p0.rank == d.rank and p0.suit == d.suit or (p1.rank == d.rank and p1.suit == d.suit):
        return BlockBonusCategory.PUSH

    return BlockBonusCategory.LOSS


def _is_queen_hearts(c: Card) -> bool:
    return bool(c.rank == Rank.QUEEN and c.suit == Suit.HEARTS)


def classify_lucky_queens(player_first: Card, player_second: Card) -> LuckyQueensCategory:
    """
    User pay table (first two cards only). Priority:

    1. Pair of queen of hearts — 150:1
    2. Suited pair (same rank & suit, multi-deck) — 25:1
    3. Suited 20 — 10:1 (same suit, total 20, not a suited identical pair)
    4. Any 20 — 3:1
    5. Exactly one queen of hearts — 2:1
    """
    for c in (player_first, player_second):
        if not _playable(c):
            raise ValueError("lucky queens requires normal playing cards")

    p0, p1 = player_first, player_second
    r0, r1 = p0.rank, p1.rank
    s0, s1 = p0.suit, p1.suit
    assert r0 and r1 and s0 and s1

    if _is_queen_hearts(p0) and _is_queen_hearts(p1):
        return LuckyQueensCategory.QUEEN_HEARTS_PAIR

    if r0 == r1 and s0 == s1:
        return LuckyQueensCategory.SUITED_PAIR

    total = Blackjack._hand_value([p0, p1])
    if total == 20 and s0 == s1:
        return LuckyQueensCategory.SUITED_20

    if total == 20:
        return LuckyQueensCategory.ANY_20

    if _is_queen_hearts(p0) ^ _is_queen_hearts(p1):
        return LuckyQueensCategory.ONE_QUEEN_HEARTS

    return LuckyQueensCategory.LOSS


def _chips_returned_block(stake: float, category: BlockBonusCategory) -> float:
    if stake <= 0:
        return 0.0
    if category is BlockBonusCategory.PUSH:
        return stake
    if category is BlockBonusCategory.LOSS:
        return 0.0
    mult = BLOCK_BONUS_PAYOUT_TO_ONE[category]
    return stake + mult * stake


def _chips_returned_lucky_queens(stake: float, category: LuckyQueensCategory) -> float:
    if stake <= 0:
        return 0.0
    if category is LuckyQueensCategory.LOSS:
        return 0.0
    mult = LUCKY_QUEENS_PAYOUT_TO_ONE[category]
    return stake + mult * stake


@dataclass
class SideBetRunStats:
    """Cumulative side-bet activity (e.g. one row per strategy in a parallel sim)."""

    block_stakes: int = 0
    block_profitable: int = 0
    block_pushes: int = 0
    block_losses: int = 0
    lucky_queens_stakes: int = 0
    lucky_queens_profitable: int = 0
    lucky_queens_losses: int = 0

    def record_block(self, stake: float, category: BlockBonusCategory) -> None:
        if stake <= 0:
            return
        self.block_stakes += 1
        if category is BlockBonusCategory.PUSH:
            self.block_pushes += 1
        elif category is BlockBonusCategory.LOSS:
            self.block_losses += 1
        else:
            self.block_profitable += 1

    def record_lucky_queens(self, stake: float, category: LuckyQueensCategory) -> None:
        if stake <= 0:
            return
        self.lucky_queens_stakes += 1
        if category is LuckyQueensCategory.LOSS:
            self.lucky_queens_losses += 1
        else:
            self.lucky_queens_profitable += 1


@dataclass
class LuckyQueensBranchOutcome:
    """Main-hand outcome plus side-bet resolution for one branch."""

    blackjack: BlackjackBranchOutcome
    block_bonus_stake: float
    lucky_queens_stake: float
    block_bonus_category: BlockBonusCategory | None
    lucky_queens_category: LuckyQueensCategory | None
    block_bonus_chips_returned: float
    lucky_queens_chips_returned: float


class LuckyQueensBlackjack(Blackjack):
    """
    Standard blackjack with optional Block Bonus and Lucky Queens stakes per branch.

    Use :meth:`play_strategy_branch_with_side_bets` so side wagers are posted before
    the hand and settled after it completes.

    ``GAME_ID`` is distinct from :attr:`Blackjack.GAME_ID` so parallel sims and
    strategies can require side-bet-aware implementations.
    """

    GAME_ID = "blackjack.lucky_queens"

    def fork_for_branch(self, deck: Deck) -> LuckyQueensBlackjack:
        return LuckyQueensBlackjack(
            bet_min=self.bet_min,
            bet_max=self.bet_max,
            deck_count=self.deck_count,
            dealer_hits_soft_17=self.dealer_hits_soft_17,
            blackjack_payout_ratio=self.blackjack_payout_ratio,
            include_slug=self.include_slug,
            slug_position_range=self.slug_position_range,
            verbose=False,
            seed_deck=copy.deepcopy(deck),
        )

    def play_strategy_branch_with_side_bets(
        self,
        player: Player,
        wager: int,
        player_cards: tuple[Card, Card],
        dealer_cards: tuple[Card, Card],
        *,
        block_bonus_stake: float = 0.0,
        lucky_queens_stake: float = 0.0,
        stats: SideBetRunStats | None = None,
        branch_debug: ParallelRoundDebugRecorder | None = None,
    ) -> LuckyQueensBranchOutcome:
        if block_bonus_stake < 0 or lucky_queens_stake < 0:
            raise ValueError("side bet stakes cannot be negative")

        side_total = float(block_bonus_stake) + float(lucky_queens_stake)
        if side_total > player.bankroll + 1e-9:
            raise ValueError("insufficient bankroll for side bets")

        if block_bonus_stake > 0:
            player.apply_bet(block_bonus_stake)
        if lucky_queens_stake > 0:
            player.apply_bet(lucky_queens_stake)

        b_out = super().play_strategy_branch(
            player, wager, player_cards, dealer_cards, branch_debug=branch_debug
        )

        dealer_up = dealer_cards[0]
        block_cat = (
            classify_block_bonus(player_cards[0], player_cards[1], dealer_up)
            if block_bonus_stake > 0
            else None
        )
        lq_cat = (
            classify_lucky_queens(player_cards[0], player_cards[1])
            if lucky_queens_stake > 0
            else None
        )

        block_return = _chips_returned_block(block_bonus_stake, block_cat or BlockBonusCategory.LOSS)
        lq_return = _chips_returned_lucky_queens(
            lucky_queens_stake, lq_cat or LuckyQueensCategory.LOSS
        )

        if block_return > 0:
            player.bankroll += block_return
            profit = block_return - block_bonus_stake
            if profit > 0:
                player.total_won += profit
        if lq_return > 0:
            player.bankroll += lq_return
            profit = lq_return - lucky_queens_stake
            if profit > 0:
                player.total_won += profit

        if stats is not None:
            if block_cat is not None:
                stats.record_block(block_bonus_stake, block_cat)
            if lq_cat is not None:
                stats.record_lucky_queens(lucky_queens_stake, lq_cat)

        return LuckyQueensBranchOutcome(
            blackjack=b_out,
            block_bonus_stake=float(block_bonus_stake),
            lucky_queens_stake=float(lucky_queens_stake),
            block_bonus_category=block_cat,
            lucky_queens_category=lq_cat,
            block_bonus_chips_returned=block_return,
            lucky_queens_chips_returned=lq_return,
        )
