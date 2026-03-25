from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from casino_sim.models.player import Player


class CasinoGame(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-friendly game name."""

    @abstractmethod
    def bet_min(self) -> float:
        """Table minimum for the base game bet."""

    @property
    @abstractmethod
    def bet_max(self) -> float:
        """Table maximum for the base game bet."""

    @abstractmethod
    def side_bet_limits(self) -> dict[str, tuple[float, float]]:
        """Side-bet min/max limits keyed by side-bet name."""

    @abstractmethod
    def play_round(self, player: Player) -> None:
        """Run one full game round for a single player."""

    def collect_valid_ante(self, player: Player) -> float:
        """
        Ask a strategy for an ante and enforce shared invalid-bet handling.

        Returns 0 when no valid bet is placed so game implementations can
        cleanly skip the round.
        """
        return player.place_ante(self.bet_min, self.bet_max)

    def begin_round_wager(self, player: Player) -> float | None:
        """
        Shared round-entry gate for strategy-driven games.

        Returns None when no valid opening wager was placed. Game
        implementations should return early and avoid all further strategy
        callbacks for that round when this happens.
        """
        wager = self.collect_valid_ante(player)
        if wager <= 0:
            return None
        return wager
