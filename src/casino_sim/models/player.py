from __future__ import annotations

from dataclasses import dataclass, field

from casino_sim.interfaces.player_strategy import PlayerStrategy
from casino_sim.models.betting import BettingDecision, GameObservation


@dataclass
class Player:
    name: str
    bankroll: float
    strategy: PlayerStrategy
    total_wagered: float = field(default=0.0, init=False)
    total_won: float = field(default=0.0, init=False)
    hand_busts: int = field(default=0, init=False)

    def can_afford(self, amount: float) -> bool:
        return 0 <= amount <= self.bankroll

    def place_ante(self, minimum_ante: float, maximum_ante: float) -> float:
        proposed = self.strategy.place_initial_ante(
            self.bankroll, minimum_ante, maximum_ante
        )
        ante = proposed
        if ante < minimum_ante or ante > maximum_ante or ante > self.bankroll:
            return 0.0
        self._wager(ante)
        return ante

    def decide_bet(self, observation: GameObservation) -> BettingDecision:
        decision = self.strategy.decide_bet(observation, self.bankroll)
        if decision.fold:
            return decision
        if decision.amount < 0:
            raise ValueError("bet amount cannot be negative")
        if decision.amount > self.bankroll:
            raise ValueError("bet amount cannot exceed bankroll")
        return decision

    def apply_bet(self, amount: float) -> None:
        self._wager(amount)

    def apply_payout(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("payout amount cannot be negative")
        self.bankroll += amount
        self.total_won += amount

    def _wager(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("wager amount cannot be negative")
        if amount > self.bankroll:
            raise ValueError("wager amount cannot exceed bankroll")
        self.bankroll -= amount
        self.total_wagered += amount
