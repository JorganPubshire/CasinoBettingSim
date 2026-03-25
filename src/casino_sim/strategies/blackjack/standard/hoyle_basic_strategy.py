"""
Standard blackjack basic strategy aligned with classic published charts (e.g. Hoyle /
Wizard of Odds style play): multi-deck, dealer hits soft 17, double after split allowed,
no surrender. Never take insurance (per Hoyle-style published advice).
"""

from __future__ import annotations

from abc import ABC
from typing import Sequence

from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy

_TEN_RANKS = frozenset({Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING})


def _dealer_upcard_value(up: Card) -> int:
    if up.rank is None:
        raise ValueError("invalid upcard")
    if up.rank == Rank.ACE:
        return 11
    if up.rank in _TEN_RANKS:
        return 10
    return int(up.rank.value)


def _low_value(card: Card) -> int:
    if card.rank is None:
        raise ValueError("invalid card")
    if card.rank in _TEN_RANKS:
        return 10
    if card.rank == Rank.ACE:
        return 1
    return int(card.rank.value)


def _hand_total_soft(cards: Sequence[Card]) -> tuple[int, bool]:
    total = sum(_low_value(c) for c in cards)
    aces = sum(1 for c in cards if c.rank == Rank.ACE)
    is_soft = False
    while aces > 0 and total + 10 <= 21:
        total += 10
        is_soft = True
        aces -= 1
    return total, is_soft


def _pair_key(card: Card) -> int | str:
    if card.rank is None:
        raise ValueError("invalid card")
    if card.rank == Rank.ACE:
        return "A"
    if card.rank in _TEN_RANKS:
        return 10
    return int(card.rank.value)


def _is_pair(cards: Sequence[Card]) -> bool:
    return len(cards) == 2 and _pair_key(cards[0]) == _pair_key(cards[1])


def _should_split(pair: tuple[int | str, int | str], d: int) -> bool:
    a, b = pair
    if a != b:
        return False
    p = a
    if p == "A":
        return True
    if p == 8:
        return True
    if p == 10:
        return False
    if p == 5:
        return False
    if p in (2, 3):
        return 2 <= d <= 7
    if p == 4:
        return d in (5, 6)
    if p == 6:
        return 2 <= d <= 6
    if p == 7:
        return 2 <= d <= 7
    if p == 9:
        return (2 <= d <= 6) or d in (8, 9)
    return False


def _soft_action(total: int, d: int, can_double: bool) -> PlayerAction:
    # Soft 13–14 (A,2 / A,3): double vs 5–6; else hit
    if total <= 14:
        if can_double and d in (5, 6):
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    # Soft 15–16 (A,4 / A,5): double vs 4–6; else hit
    if total in (15, 16):
        if can_double and 4 <= d <= 6:
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    # Soft 17 (A,6): double vs 4–6; else hit
    if total == 17:
        if can_double and 4 <= d <= 6:
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    if total == 18:
        if can_double and d in (3, 4, 5, 6):
            return PlayerAction.DOUBLE
        if d in (2, 7, 8):
            return PlayerAction.STAND
        return PlayerAction.HIT
    if total == 19:
        if can_double and d == 6:
            return PlayerAction.DOUBLE
        return PlayerAction.STAND
    return PlayerAction.STAND


def _hard_action(total: int, d: int, can_double: bool) -> PlayerAction:
    if total <= 8:
        return PlayerAction.HIT
    if total == 9:
        if can_double and 3 <= d <= 6:
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    if total == 10:
        if can_double and 2 <= d <= 9:
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    if total == 11:
        if can_double:
            return PlayerAction.DOUBLE
        return PlayerAction.HIT
    if total == 12:
        if d in (4, 5, 6):
            return PlayerAction.STAND
        return PlayerAction.HIT
    if 13 <= total <= 16:
        if 2 <= d <= 6:
            return PlayerAction.STAND
        return PlayerAction.HIT
    return PlayerAction.STAND


def hoyle_basic_action(
    player_hand: Sequence[Card],
    dealer_upcard: Card,
    *,
    can_double: bool,
    can_split: bool,
) -> PlayerAction:
    d = _dealer_upcard_value(dealer_upcard)
    if _is_pair(player_hand) and can_split:
        pk = (_pair_key(player_hand[0]), _pair_key(player_hand[1]))
        if _should_split(pk, d):
            return PlayerAction.SPLIT

    total, soft = _hand_total_soft(player_hand)
    n = len(player_hand)
    can_d = can_double and n == 2

    if soft:
        return _soft_action(total, d, can_d)
    return _hard_action(total, d, can_d)


def _mid_bet_amount(minimum_ante: float, maximum_ante: float, bankroll: float) -> float:
    mid = (minimum_ante + maximum_ante) / 2.0
    snapped = round(mid / 5.0) * 5.0
    bet = min(maximum_ante, max(minimum_ante, snapped))
    return min(bet, bankroll)


class _HoyleBasicStrategyBase(StandardBlackjackPlayerStrategy, ABC):
    """Shared Hoyle-style basic strategy; subclasses fix bet sizing only."""

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        hand = observation.player_hand
        if not hand:
            return BettingDecision(amount=0.0, action=PlayerAction.STAND)
        up = observation.visible_table_cards[0]
        can_double = observation.double_allowed
        can_split = observation.split_allowed and len(hand) == 2
        action = hoyle_basic_action(
            hand, up, can_double=can_double, can_split=can_split
        )
        return BettingDecision(amount=0.0, action=action)


class HoyleBasicStrategyLow(_HoyleBasicStrategyBase):
    """Hoyle-style basic strategy; always antes the table minimum."""

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return minimum_ante


class HoyleBasicStrategyHigh(_HoyleBasicStrategyBase):
    """Hoyle-style basic strategy; always antes the table maximum (capped by bankroll)."""

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return min(maximum_ante, bankroll)


class HoyleBasicStrategyMid(_HoyleBasicStrategyBase):
    """Hoyle-style basic strategy; antes average of min/max rounded to nearest multiple of 5."""

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return _mid_bet_amount(minimum_ante, maximum_ante, bankroll)


# Backward-compatible names
HoyleBasicStrategyMinBet = HoyleBasicStrategyLow
HoyleBasicStrategyMaxBet = HoyleBasicStrategyHigh
HoyleBasicStrategyMidBet = HoyleBasicStrategyMid
