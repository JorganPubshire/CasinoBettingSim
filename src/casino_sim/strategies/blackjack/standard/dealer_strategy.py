"""
Player strategy that mimics the house dealer: only hit or stand, using the same
thresholds as :meth:`Blackjack._run_dealer_turn` (17 rule + optional soft-17 hit).
"""

from __future__ import annotations

from typing import Sequence

from casino_sim.games.blackjack import Blackjack
from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


class DealerStrategy(StandardBlackjackPlayerStrategy):
    """
    Hit until hard total is 17+, or soft 17 when ``dealer_hits_soft_17`` matches the table.
    Never doubles, splits, or takes insurance.
    """

    def __init__(self, dealer_hits_soft_17: bool = True) -> None:
        self._dealer_hits_soft_17 = dealer_hits_soft_17

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return minimum_ante

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        hand = list(observation.player_hand)
        if not hand:
            return BettingDecision(amount=0.0, action=PlayerAction.STAND)

        total = Blackjack._hand_value(hand)
        soft = Blackjack._is_soft_hand(hand)
        should_hit = total < 17 or (
            self._dealer_hits_soft_17 and total == 17 and soft
        )
        if should_hit:
            return BettingDecision(amount=0.0, action=PlayerAction.HIT)
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)
