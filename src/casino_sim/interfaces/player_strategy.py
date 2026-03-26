from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Sequence

from casino_sim.models.betting import BettingDecision, GameObservation
from casino_sim.models.card import Card


class PlayerStrategy(ABC):
    @abstractmethod
    def place_initial_ante(
        self, bankroll: float, minimum_ante: float, maximum_ante: float
    ) -> float:
        """Return the ante amount to place at game start."""

    @abstractmethod
    def decide_bet(self, observation: GameObservation, bankroll: float) -> BettingDecision:
        """Return a decision for the current game phase."""

    @abstractmethod
    def take_insurance(
        self, bankroll: float, main_bet: float, player_cards: Sequence[Card]
    ) -> bool:
        """Return True to place insurance, False to decline.

        Only called when the dealer shows an ace (insurance offered).
        """

    def on_post_round_exposure(self, cards: Sequence[Card]) -> None:
        """Extra cards revealed from the canonical shoe tail after this branch ended."""
        pass

    def on_deck_shuffled(self) -> None:
        """Called when the shared shoe was shuffled before the next round."""
        pass

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        """
        Optional side-bet stakes before the initial deal (variant-specific).

        The simulation / table layer supplies ``side_bet_limits``: maps a side-bet id
        (defined by each game variant, e.g. ``block_bonus``) to ``(minimum, maximum)``
        allowed wagers. Implementations return a dict of the same keys they wish to play;
        missing keys mean no wager on that side bet.

        Return amounts in ``[0, bankroll]``; for a non-zero wager on a key, the amount
        must lie within that key's inclusive limits or the host will treat it as zero.

        Default: no side bets (empty dict). Override in strategies that participate.
        """
        return {}
