"""Parallel session for Lucky Queens blackjack (main hand + Block Bonus + Lucky Queens side bets)."""

from __future__ import annotations

import copy
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

from casino_sim.games.blackjack import Blackjack
from casino_sim.games.lucky_queens_blackjack import (
    LuckyQueensBlackjack,
    LuckyQueensBranchOutcome,
)
from casino_sim.models.player import Player
from casino_sim.round_debug import ParallelRoundDebugRecorder
from casino_sim.simulation.standard_blackjack_parallel import (
    ParallelParticipantSummary,
    canonical_exposure_suffix,
)
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy

# Side-bet ids for this variant (strategies and CLI/registry use these keys).
SIDE_BET_BLOCK_BONUS = "block_bonus"
SIDE_BET_LUCKY_QUEENS = "lucky_queens"


def _validated_side_stake(
    proposed: float,
    bankroll: float,
    lo: float,
    hi: float,
) -> float:
    """Return a legal stake or 0 if the proposal is out of range or unaffordable."""
    if hi <= 0:
        return 0.0
    if lo < 0 or hi < lo:
        return 0.0
    a = float(proposed)
    if a <= 0:
        return 0.0
    if a + 1e-9 < lo or a > hi + 1e-9:
        return 0.0
    return min(a, float(bankroll))


@dataclass
class LuckyQueensParallelSession:
    """
    Same deal-equality model as :class:`StandardBlackjackParallelSession`, using
    :class:`LuckyQueensBlackjack`.

    ``side_bet_limits`` maps side-bet ids (e.g. :data:`SIDE_BET_BLOCK_BONUS`) to
    ``(minimum, maximum)`` wagers allowed on the table. Each strategy chooses stakes
    via :meth:`~casino_sim.interfaces.player_strategy.PlayerStrategy.place_side_bets_before_deal`;
    invalid proposals are treated as zero.

    Strategies must report :attr:`LuckyQueensBlackjack.GAME_ID` from
    ``supported_game_id`` (standard blackjack strategies are not valid here).
    """

    bet_min: float
    bet_max: float
    initial_bankroll: float
    rounds: int
    strategies: list[tuple[str, StandardBlackjackPlayerStrategy]]
    side_bet_limits: dict[str, tuple[float, float]] = field(default_factory=dict)
    deck_count: int = 6
    include_slug: bool = False
    dealer_hits_soft_17: bool = True
    blackjack_payout_ratio: float = 1.5
    slug_position_range: tuple[float, float] = (0.72, 0.86)
    debug_parallel: bool = False
    on_progress: Callable[[int, int], None] | None = None

    _master: LuckyQueensBlackjack = field(init=False, repr=False)
    _players: list[Player] = field(init=False, repr=False)
    _bust_round: dict[int, int | None] = field(init=False, repr=False)
    _rounds_played: list[int] = field(init=False, repr=False)
    _wins: list[int] = field(init=False, repr=False)
    _losses: list[int] = field(init=False, repr=False)
    _pushes: list[int] = field(init=False, repr=False)
    _block_net: list[float] = field(init=False, repr=False)
    _lq_net: list[float] = field(init=False, repr=False)
    _min_bankroll_track: list[float] = field(init=False, repr=False)
    _max_bankroll_track: list[float] = field(init=False, repr=False)
    _bankroll_history: list[list[float]] = field(init=False, repr=False)
    _side_bet_limits: dict[str, tuple[float, float]] = field(init=False, repr=False)
    _debug_recorder: ParallelRoundDebugRecorder | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        lq_id = LuckyQueensBlackjack.GAME_ID
        for _label, strategy in self.strategies:
            if strategy.supported_game_id != lq_id:
                raise ValueError(
                    f"Strategy {strategy!r} is not built for Lucky Queens blackjack "
                    f"(need {lq_id!r}, reports {strategy.supported_game_id!r})."
                )

        self._side_bet_limits = dict(self.side_bet_limits)
        for key, pair in self._side_bet_limits.items():
            lo, hi = pair
            if lo < 0 or hi < lo:
                raise ValueError(
                    f"invalid side bet limits for {key!r}: minimum={lo} maximum={hi}"
                )

        self._master = LuckyQueensBlackjack(
            bet_min=self.bet_min,
            bet_max=self.bet_max,
            deck_count=self.deck_count,
            dealer_hits_soft_17=self.dealer_hits_soft_17,
            blackjack_payout_ratio=self.blackjack_payout_ratio,
            include_slug=self.include_slug,
            slug_position_range=self.slug_position_range,
            verbose=False,
        )
        self._players = [
            Player(name=label, bankroll=float(self.initial_bankroll), strategy=strategy)
            for label, strategy in self.strategies
        ]
        n = len(self._players)
        self._bust_round = {i: None for i in range(n)}
        self._rounds_played = [0] * n
        self._wins = [0] * n
        self._losses = [0] * n
        self._pushes = [0] * n
        self._block_net = [0.0] * n
        self._lq_net = [0.0] * n
        init_br = float(self.initial_bankroll)
        self._min_bankroll_track = [init_br] * n
        self._max_bankroll_track = [init_br] * n
        self._bankroll_history = [[] for _ in range(n)]
        self._debug_recorder = (
            ParallelRoundDebugRecorder() if self.debug_parallel else None
        )

    def run(self) -> list[ParallelParticipantSummary]:
        try:
            for round_index in range(self.rounds):
                self._run_single_round(round_index + 1)
                self._record_bankroll_snapshots()
                if self.on_progress is not None:
                    self.on_progress(round_index + 1, self.rounds)
        except Exception:
            if self._debug_recorder is not None:
                print(self._debug_recorder.format_report(), file=sys.stderr)
            raise

        return [
            ParallelParticipantSummary(
                name=p.name,
                final_bankroll=p.bankroll,
                total_wagered=p.total_wagered,
                total_won=p.total_won,
                rounds_played=self._rounds_played[i],
                busted_on_round=self._bust_round[i],
                hand_busts=p.hand_busts,
                wins=self._wins[i],
                losses=self._losses[i],
                pushes=self._pushes[i],
                min_bankroll=self._min_bankroll_track[i],
                max_bankroll=self._max_bankroll_track[i],
                bankroll_after_each_round=tuple(self._bankroll_history[i]),
                block_bonus_net=self._block_net[i],
                lucky_queens_net=self._lq_net[i],
            )
            for i, p in enumerate(self._players)
        ]

    def _record_bankroll_snapshots(self) -> None:
        for i, player in enumerate(self._players):
            b = float(player.bankroll)
            self._bankroll_history[i].append(b)
            self._min_bankroll_track[i] = min(self._min_bankroll_track[i], b)
            self._max_bankroll_track[i] = max(self._max_bankroll_track[i], b)

    def _resolve_side_stakes(self, player: Player, wager: int) -> tuple[float, float]:
        limits = self._side_bet_limits
        proposed = player.strategy.place_side_bets_before_deal(
            bankroll=float(player.bankroll),
            main_wager=float(wager),
            side_bet_limits=limits,
        )
        br = float(player.bankroll)
        bb_lo, bb_hi = limits.get(SIDE_BET_BLOCK_BONUS, (0.0, 0.0))
        raw_bb = float(proposed.get(SIDE_BET_BLOCK_BONUS, 0) or 0)
        bb = _validated_side_stake(raw_bb, br, bb_lo, bb_hi)
        lq_lo, lq_hi = limits.get(SIDE_BET_LUCKY_QUEENS, (0.0, 0.0))
        raw_lq = float(proposed.get(SIDE_BET_LUCKY_QUEENS, 0) or 0)
        lq = _validated_side_stake(raw_lq, br - bb, lq_lo, lq_hi)
        return bb, lq

    def _run_single_round(self, round_number: int) -> None:
        bet_min_f = float(self._master.bet_min)
        active: list[tuple[int, Player, int]] = []
        for i, player in enumerate(self._players):
            if player.bankroll < bet_min_f:
                continue
            wager_value = self._master.begin_round_wager(player)
            if wager_value is None:
                continue
            wager = int(wager_value)
            active.append((i, player, wager))

        if not active:
            return

        self._master._reshuffle_after_hand = False
        shoe_refreshed = self._master.refresh_shoe_if_needed(min_cards_remaining=4)
        if shoe_refreshed:
            for player in self._players:
                player.strategy.on_deck_shuffled()

        dbg = self._debug_recorder
        if dbg is not None:
            dbg.begin_round(round_number, self._master.deck.cards_remaining())

        p0 = self._master._draw_playable_card()  # noqa: SLF001
        p1 = self._master._draw_playable_card()  # noqa: SLF001
        d0 = self._master._draw_playable_card()  # noqa: SLF001
        d1 = self._master._draw_playable_card()  # noqa: SLF001
        deck_after_initial = copy.deepcopy(self._master.deck)

        if dbg is not None:
            dbg.set_cloned_tail_remaining(deck_after_initial.cards_remaining())

        outcomes: list[tuple[int, LuckyQueensBranchOutcome]] = []
        for player_index, player, wager in active:
            bb, lq = self._resolve_side_stakes(player, wager)
            fork = self._master.fork_for_branch(deck_after_initial)
            lq_out = fork.play_strategy_branch_with_side_bets(
                player,
                wager,
                (p0, p1),
                (d0, d1),
                block_bonus_stake=bb,
                lucky_queens_stake=lq,
                branch_debug=dbg,
            )
            outcomes.append((player_index, lq_out))
            self._rounds_played[player_index] += 1
            w, l_ct, p_ct = Blackjack.tally_round_wlp(lq_out.blackjack.final_state)
            self._wins[player_index] += w
            self._losses[player_index] += l_ct
            self._pushes[player_index] += p_ct
            self._block_net[player_index] += (
                lq_out.block_bonus_chips_returned - lq_out.block_bonus_stake
            )
            self._lq_net[player_index] += (
                lq_out.lucky_queens_chips_returned - lq_out.lucky_queens_stake
            )

        deepest_idx = 0
        fewest_remaining = outcomes[0][1].blackjack.final_deck.cards_remaining()
        for j in range(1, len(outcomes)):
            rem = outcomes[j][1].blackjack.final_deck.cards_remaining()
            if rem < fewest_remaining:
                fewest_remaining = rem
                deepest_idx = j

        canonical_dealt = outcomes[deepest_idx][1].blackjack.dealt_sequence
        canonical_slug = outcomes[deepest_idx][1].blackjack.slug_triggered
        self._master.deck = copy.deepcopy(outcomes[deepest_idx][1].blackjack.final_deck)

        for _j, (player_index, lq_out) in enumerate(outcomes):
            player = self._players[player_index]
            suffix = canonical_exposure_suffix(
                lq_out.blackjack.dealt_sequence, canonical_dealt
            )
            player.strategy.on_post_round_exposure(suffix)

        if canonical_slug:
            for player in self._players:
                player.strategy.on_deck_shuffled()

        bet_min_f = float(self._master.bet_min)
        for i, player in enumerate(self._players):
            if self._bust_round[i] is None and player.bankroll < bet_min_f:
                self._bust_round[i] = round_number
