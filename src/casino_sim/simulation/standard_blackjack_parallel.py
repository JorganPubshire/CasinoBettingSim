from __future__ import annotations

import copy
import sys
from dataclasses import dataclass, field

from casino_sim.games.blackjack import Blackjack, BlackjackBranchOutcome
from casino_sim.models.card import Card
from casino_sim.models.player import Player
from casino_sim.round_debug import ParallelRoundDebugRecorder
from casino_sim.strategies.blackjack.standard.base import StandardBlackjackPlayerStrategy


def canonical_exposure_suffix(
    branch_dealt: list[Card], canonical_dealt: list[Card]
) -> list[Card]:
    """Cards from the canonical sequence after the longest common prefix with ``branch_dealt``."""
    k = 0
    n, m = len(branch_dealt), len(canonical_dealt)
    while k < n and k < m and branch_dealt[k] == canonical_dealt[k]:
        k += 1
    return list(canonical_dealt[k:])


@dataclass
class ParallelParticipantSummary:
    """
    ``busted_on_round`` is the first round bankroll fell below the table minimum (cannot
    bet further), not a count of blackjack hand busts. See ``hand_busts`` for 21 busts.

    ``wins`` / ``losses`` / ``pushes`` count each resolved player hand (splits can add
    several per table round). ``rounds_played`` counts only rounds where the strategy
    placed a legal wager (bankroll was at least table minimum and ante was valid).
    """

    name: str
    final_bankroll: float
    total_wagered: float
    total_won: float
    rounds_played: int
    busted_on_round: int | None
    hand_busts: int
    wins: int
    losses: int
    pushes: int


@dataclass
class StandardBlackjackParallelSession:
    """
    Compare many strategies against the same dealer shoe in one conceptual seat.

    Each round: the master shoe deals one shared four-card start (player, player, dealer,
    dealer). Every active strategy gets an **independent clone** of the remaining deck—same
    card order—then plays the hand against the same upcards. Strategies that hit, split, or
    extend the dealer run **further down that identical stream** than others.

    After all branches finish, the master shoe is replaced with the clone that has the
    **fewest cards remaining** (the deepest penetration into the shared stream for that
    round). Exposure callbacks use that branch's dealt sequence as canonical.
    """

    bet_min: float
    bet_max: float
    initial_bankroll: float
    rounds: int
    strategies: list[tuple[str, StandardBlackjackPlayerStrategy]]
    deck_count: int = 6
    include_slug: bool = False
    dealer_hits_soft_17: bool = True
    blackjack_payout_ratio: float = 1.5
    slug_position_range: tuple[float, float] = (0.72, 0.86)
    debug_parallel: bool = False

    _master: Blackjack = field(init=False, repr=False)
    _players: list[Player] = field(init=False, repr=False)
    _bust_round: dict[int, int | None] = field(init=False, repr=False)
    _rounds_played: list[int] = field(init=False, repr=False)
    _debug_recorder: ParallelRoundDebugRecorder | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        for _label, strategy in self.strategies:
            if strategy.supported_game_id != Blackjack.GAME_ID:
                raise ValueError(
                    f"Strategy {strategy!r} is not built for {Blackjack.GAME_ID!r} "
                    f"(reports {strategy.supported_game_id!r})."
                )

        self._master = Blackjack(
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
        self._bust_round = {i: None for i in range(len(self._players))}
        self._rounds_played = [0 for _ in self._players]
        self._wins = [0 for _ in self._players]
        self._losses = [0 for _ in self._players]
        self._pushes = [0 for _ in self._players]
        if self.debug_parallel:
            self._debug_recorder = ParallelRoundDebugRecorder()
        else:
            self._debug_recorder = None

    def run(self) -> list[ParallelParticipantSummary]:
        try:
            for round_index in range(self.rounds):
                self._run_single_round(round_index + 1)
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
            )
            for i, p in enumerate(self._players)
        ]

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

        # Shared stream: same four starter cards for every strategy this round.
        p0 = self._master._draw_playable_card()  # noqa: SLF001
        p1 = self._master._draw_playable_card()  # noqa: SLF001
        d0 = self._master._draw_playable_card()  # noqa: SLF001
        d1 = self._master._draw_playable_card()  # noqa: SLF001
        deck_after_initial = copy.deepcopy(self._master.deck)

        if dbg is not None:
            dbg.set_cloned_tail_remaining(deck_after_initial.cards_remaining())

        outcomes: list[tuple[int, BlackjackBranchOutcome]] = []
        for player_index, player, wager in active:
            # Identical deck tail per strategy; each fork draws the same next cards until
            # its own hand diverges (stand/hit/split/dealer path).
            fork = self._master.fork_for_branch(deck_after_initial)
            outcome = fork.play_strategy_branch(
                player,
                wager,
                (p0, p1),
                (d0, d1),
                branch_debug=dbg,
            )
            outcomes.append((player_index, outcome))
            self._rounds_played[player_index] += 1
            w, l, p_ct = Blackjack.tally_round_wlp(outcome.final_state)
            self._wins[player_index] += w
            self._losses[player_index] += l
            self._pushes[player_index] += p_ct

        # Deepest penetration = smallest cards_remaining() on the cloned shoe.
        deepest_idx = 0
        fewest_remaining = outcomes[0][1].final_deck.cards_remaining()
        for j in range(1, len(outcomes)):
            rem = outcomes[j][1].final_deck.cards_remaining()
            if rem < fewest_remaining:
                fewest_remaining = rem
                deepest_idx = j

        canonical_dealt = outcomes[deepest_idx][1].dealt_sequence
        canonical_slug = outcomes[deepest_idx][1].slug_triggered
        self._master.deck = copy.deepcopy(outcomes[deepest_idx][1].final_deck)

        for _j, (player_index, outcome) in enumerate(outcomes):
            player = self._players[player_index]
            suffix = canonical_exposure_suffix(outcome.dealt_sequence, canonical_dealt)
            player.strategy.on_post_round_exposure(suffix)

        if canonical_slug:
            for player in self._players:
                player.strategy.on_deck_shuffled()

        bet_min_f = float(self._master.bet_min)
        for i, player in enumerate(self._players):
            if self._bust_round[i] is None and player.bankroll < bet_min_f:
                self._bust_round[i] = round_number
