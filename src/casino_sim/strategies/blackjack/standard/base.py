from __future__ import annotations

from abc import ABC

from casino_sim.games.blackjack import Blackjack
from casino_sim.interfaces.player_strategy import PlayerStrategy


class StandardBlackjackPlayerStrategy(PlayerStrategy, ABC):
    """Strategies compatible with :class:`Blackjack` in ``blackjack.standard`` rules."""

    @property
    def supported_game_id(self) -> str:
        return Blackjack.GAME_ID
