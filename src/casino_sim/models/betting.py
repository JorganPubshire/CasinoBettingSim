from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from casino_sim.models.card import Card


class BettingPhase(Enum):
    INITIAL_ANTE = "initial_ante"
    PRE_DRAW = "pre_draw"
    MID_ROUND = "mid_round"
    FINAL_BET = "final_bet"


class PlayerAction(Enum):
    HIT = "hit"
    STAND = "stand"
    DOUBLE = "double"
    SPLIT = "split"
    SURRENDER = "surrender"


@dataclass(frozen=True)
class BettingDecision:
    amount: float
    fold: bool = False
    action: PlayerAction | None = None
    metadata: Mapping[str, str] | None = None


@dataclass(frozen=True)
class GameObservation:
    phase: BettingPhase
    player_hand: Sequence[Card]
    visible_table_cards: Sequence[Card]
    visible_opponent_cards: Mapping[str, Sequence[Card]]
    pot_size: float
    double_allowed: bool = True
    split_allowed: bool = True
