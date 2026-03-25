from __future__ import annotations

from typing import Sequence

from casino_sim.models.betting import BettingDecision, GameObservation, PlayerAction
from casino_sim.models.card import Card
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


class DummyStrategy(StandardBlackjackPlayerStrategy):
    """Simple baseline strategy for standard blackjack."""

    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        return min(bankroll, maximum_ante)

    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        return BettingDecision(amount=0.0, action=PlayerAction.STAND)

    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        return False
