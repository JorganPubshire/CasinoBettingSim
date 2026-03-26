"""Hoyle basic (low main ante) with a 4×4 grid of Block Bonus × Lucky Queens side stakes."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from casino_sim.games.lucky_queens_blackjack import LuckyQueensBlackjack
from casino_sim.simulation.lucky_queens_parallel import (
    SIDE_BET_BLOCK_BONUS,
    SIDE_BET_LUCKY_QUEENS,
)
from casino_sim.strategies.blackjack.standard.hoyle_basic_strategy import (
    HoyleBasicStrategyLow,
    _mid_bet_amount,
)


class _SideTier(Enum):
    MIN = "min"
    MID = "mid"
    MAX = "max"
    PASS = "pass"


def _stake_for_tier(tier: _SideTier, lo: float, hi: float, bankroll: float) -> float:
    if tier is _SideTier.PASS:
        return 0.0
    if hi <= 0:
        return 0.0
    if tier is _SideTier.MIN:
        return float(lo)
    if tier is _SideTier.MID:
        return _mid_bet_amount(float(lo), float(hi), float(bankroll))
    return min(float(hi), float(bankroll))


def _side_stakes_for_grid(
    block_tier: _SideTier,
    lucky_tier: _SideTier,
    *,
    bankroll: float,
    side_bet_limits: Mapping[str, tuple[float, float]],
) -> dict[str, float]:
    bb_lo, bb_hi = side_bet_limits.get(SIDE_BET_BLOCK_BONUS, (0.0, 0.0))
    lq_lo, lq_hi = side_bet_limits.get(SIDE_BET_LUCKY_QUEENS, (0.0, 0.0))
    return {
        SIDE_BET_BLOCK_BONUS: _stake_for_tier(block_tier, bb_lo, bb_hi, bankroll),
        SIDE_BET_LUCKY_QUEENS: _stake_for_tier(lucky_tier, lq_lo, lq_hi, bankroll),
    }


class HoyleLuckyQueensMinMinStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MIN, _SideTier.MIN, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMinMidStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MIN, _SideTier.MID, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMinMaxStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MIN, _SideTier.MAX, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMinPassStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MIN, _SideTier.PASS, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMidMinStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MID, _SideTier.MIN, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMidMidStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MID, _SideTier.MID, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMidMaxStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MID, _SideTier.MAX, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMidPassStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MID, _SideTier.PASS, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMaxMinStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MAX, _SideTier.MIN, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMaxMidStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MAX, _SideTier.MID, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMaxMaxStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MAX, _SideTier.MAX, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensMaxPassStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.MAX, _SideTier.PASS, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensPassMinStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.PASS, _SideTier.MIN, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensPassMidStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.PASS, _SideTier.MID, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensPassMaxStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.PASS, _SideTier.MAX, bankroll=bankroll, side_bet_limits=side_bet_limits
        )


class HoyleLuckyQueensPassPassStrategy(HoyleBasicStrategyLow):
    @property
    def supported_game_id(self) -> str:
        return LuckyQueensBlackjack.GAME_ID

    def place_side_bets_before_deal(
        self,
        *,
        bankroll: float,
        main_wager: float,
        side_bet_limits: Mapping[str, tuple[float, float]],
    ) -> dict[str, float]:
        _ = main_wager
        return _side_stakes_for_grid(
            _SideTier.PASS, _SideTier.PASS, bankroll=bankroll, side_bet_limits=side_bet_limits
        )
