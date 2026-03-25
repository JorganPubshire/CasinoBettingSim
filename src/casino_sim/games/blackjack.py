from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import InitVar, dataclass, field

from casino_sim.interfaces.casino_game import CasinoGame
from casino_sim.models.betting import BettingPhase, GameObservation, PlayerAction
from casino_sim.models.card import Card, Rank
from casino_sim.models.deck import Deck
from casino_sim.models.player import Player
from casino_sim.round_debug import ParallelRoundDebugRecorder


@dataclass
class BlackjackHand:
    cards: list[Card]
    bet: int
    is_finished: bool = False
    is_doubled: bool = False
    is_split_hand: bool = False


@dataclass
class BlackjackRoundState:
    dealer_cards: list[Card]
    player_hands: list[BlackjackHand]
    active_hand_index: int
    bankroll: int
    initial_bankroll: int
    insurance_offered: bool = False
    insurance_bet: int = 0
    message: str = ""
    round_over: bool = False


@dataclass
class BlackjackBranchOutcome:
    """Result of one strategy branch (same initial deal, independent deck tail)."""

    final_state: BlackjackRoundState
    dealt_sequence: list[Card]
    final_deck: Deck
    slug_triggered: bool


@dataclass
class Blackjack(CasinoGame):
    GAME_ID = "blackjack.standard"

    bet_min: float = 10.0
    bet_max: float = 500.0
    deck_count: int = 6
    dealer_hits_soft_17: bool = True
    blackjack_payout_ratio: float = 1.5
    include_slug: bool = True
    slug_position_range: tuple[float, float] = (0.72, 0.86)
    seed_deck: InitVar[Deck | None] = None
    deck: Deck = field(init=False)
    verbose: bool = field(default=True, repr=False)
    _reshuffle_after_hand: bool = field(default=False, init=False)
    _branch_dealt: list[Card] | None = field(default=None, init=False, repr=False)
    _branch_debug_recorder: ParallelRoundDebugRecorder | None = field(
        default=None, init=False, repr=False
    )

    # Common side bets, intentionally not implemented yet:
    # - Insurance
    # - Perfect Pairs
    # - 21+3
    # - Lucky Ladies
    # - Buster Blackjack
    _supported_side_bets: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {}, init=False
    )

    def __post_init__(self, seed_deck: Deck | None) -> None:
        if self.bet_min <= 0:
            raise ValueError("bet_min must be greater than 0")
        if self.bet_max < self.bet_min:
            raise ValueError("bet_max must be greater than or equal to bet_min")
        if int(self.bet_min) % 5 != 0 or int(self.bet_max) % 5 != 0:
            raise ValueError("bet_min and bet_max must be multiples of 5")
        if seed_deck is not None:
            self.deck = seed_deck
        else:
            self.deck = Deck(
                deck_count=self.deck_count,
                include_slug=self.include_slug,
                slug_position_range=self.slug_position_range,
            )
            self.deck.shuffle()

    @property
    def name(self) -> str:
        return "Blackjack"

    def side_bet_limits(self) -> dict[str, tuple[float, float]]:
        return dict(self._supported_side_bets)

    def get_bet_options(self, bankroll: int) -> list[int]:
        if bankroll < self.bet_min:
            return []

        min_bet = int(self.bet_min)
        max_bet_table = int(self.bet_max)
        max_bet = min(max_bet_table, bankroll - (bankroll % 5))
        if max_bet < min_bet:
            return []

        def snap_to_25(value: float) -> int:
            return int(round(value / 25.0) * 25)

        middle_values: list[int] = []
        for ratio in (0.25, 0.50, 0.75):
            target = min_bet + ((max_bet - min_bet) * ratio)
            snapped = snap_to_25(target)
            snapped = min(max(snapped, min_bet), max_bet)
            middle_values.append(snapped)

        # Ensure ascending order and keep middle values within bounds.
        middle_values.sort()
        for i in range(1, len(middle_values)):
            if middle_values[i] <= middle_values[i - 1]:
                candidate = middle_values[i - 1] + 25
                middle_values[i] = min(candidate, max_bet)

        options = [min_bet] + middle_values + [max_bet]
        deduped = [options[0]]
        for value in options[1:]:
            if value != deduped[-1]:
                deduped.append(value)
        return deduped

    def refresh_shoe_if_needed(self, min_cards_remaining: int = 4) -> bool:
        """
        Build a fresh shoe when too few cards remain or (with cut-card rules) the slug
        is missing. Call before dealing a new round so the slug is always present until
        drawn and the shoe can supply at least ``min_cards_remaining`` cards.

        Returns True if ``reset`` + ``shuffle`` ran.
        """
        if not self.include_slug:
            if self.deck.cards_remaining() < min_cards_remaining:
                self.deck.reset()
                self.deck.shuffle()
                return True
            return False

        if not self.deck.has_slug() or self.deck.cards_remaining() < min_cards_remaining:
            self.deck.reset()
            self.deck.shuffle()
            return True
        return False

    def _finish_branch_player_totals(
        self,
        player: Player,
        state: BlackjackRoundState,
        bankroll_after_ante: int,
    ) -> None:
        """Apply final bankroll, net chips gained this hand (paid out), and hand-bust tally."""
        gain = float(state.bankroll) - float(bankroll_after_ante)
        if gain > 0:
            player.total_won += gain
        player.bankroll = float(state.bankroll)
        player.hand_busts += sum(
            1 for h in state.player_hands if self._hand_value(h.cards) > 21
        )

    def fork_for_branch(self, deck: Deck) -> Blackjack:
        """Independent copy of this table rules with a cloned deck tail (after shared initial deal)."""
        return Blackjack(
            bet_min=self.bet_min,
            bet_max=self.bet_max,
            deck_count=self.deck_count,
            dealer_hits_soft_17=self.dealer_hits_soft_17,
            blackjack_payout_ratio=self.blackjack_payout_ratio,
            include_slug=self.include_slug,
            slug_position_range=self.slug_position_range,
            verbose=False,
            seed_deck=copy.deepcopy(deck),
        )

    def play_strategy_branch(
        self,
        player: Player,
        wager: int,
        player_cards: tuple[Card, Card],
        dealer_cards: tuple[Card, Card],
        branch_debug: ParallelRoundDebugRecorder | None = None,
    ) -> BlackjackBranchOutcome:
        """
        Play one full round from a fixed initial deal using ``player.strategy`` for
        insurance and actions. Mutates ``player.bankroll`` to match the outcome.

        ``branch_debug`` when provided receives structured lines for this branch only
        (parallel session debugging).
        """
        dealt: list[Card] = [
            player_cards[0],
            player_cards[1],
            dealer_cards[0],
            dealer_cards[1],
        ]
        self._branch_dealt = dealt
        self._reshuffle_after_hand = False
        self._branch_debug_recorder = branch_debug
        try:
            if branch_debug is not None:
                branch_debug.start_branch(player.name)

            bank_before_hand = int(player.bankroll + wager)
            bankroll_after_bet = int(player.bankroll)
            player_hand = BlackjackHand(
                cards=[player_cards[0], player_cards[1]],
                bet=wager,
            )
            d_list = [dealer_cards[0], dealer_cards[1]]
            state = BlackjackRoundState(
                dealer_cards=d_list,
                player_hands=[player_hand],
                active_hand_index=0,
                bankroll=bankroll_after_bet,
                initial_bankroll=bank_before_hand,
                insurance_offered=dealer_cards[0].rank is Rank.ACE,
            )

            if branch_debug is not None:
                branch_debug.append(
                    f"Initial — wager={wager} bankroll_after_ante={bankroll_after_bet} "
                    f"(stack before hand recorded as {bank_before_hand})"
                )
                branch_debug.append(
                    f"Fork deck_remaining after shared deal: {self.deck.cards_remaining()}"
                )
                branch_debug.append(
                    f"Player: {player_cards[0]}  {player_cards[1]} | "
                    f"Dealer up: {dealer_cards[0]} | hole: {dealer_cards[1]}"
                )

            player_natural = self._is_blackjack(player_hand.cards)
            dealer_natural = self._is_blackjack(d_list)
            if player_natural or dealer_natural:
                self._resolve_naturals_for_cli(state)
                state.round_over = True
                self._finalize_round()
                self._finish_branch_player_totals(player, state, bankroll_after_bet)
                if branch_debug is not None:
                    branch_debug.append(f"Natural / early resolution: {state.message!r}")
                    branch_debug.append(
                        f"End branch bankroll={state.bankroll} deck_remaining={self.deck.cards_remaining()}"
                    )
                return BlackjackBranchOutcome(
                    final_state=state,
                    dealt_sequence=list(dealt),
                    final_deck=copy.deepcopy(self.deck),
                    slug_triggered=self._reshuffle_after_hand,
                )

            if state.insurance_offered:
                wants = player.strategy.take_insurance(
                    bankroll=float(state.bankroll),
                    main_bet=float(wager),
                    player_cards=tuple(player_cards),
                )
                if branch_debug is not None:
                    branch_debug.append(f"Insurance offered — strategy_take_insurance={wants}")
                if wants:
                    insurance_amount = min(wager // 2, state.bankroll)
                    if insurance_amount > 0:
                        self.set_insurance_bet(state, insurance_amount)
                        if branch_debug is not None:
                            branch_debug.append(
                                f"Took insurance amount={insurance_amount} bankroll_now={state.bankroll}"
                            )

            self._advance_to_next_active_hand(state)
            while not state.round_over:
                hand = state.player_hands[state.active_hand_index]
                allowed = self.available_actions(state)
                obs = GameObservation(
                    phase=BettingPhase.MID_ROUND,
                    player_hand=tuple(hand.cards),
                    visible_table_cards=(state.dealer_cards[0],),
                    visible_opponent_cards={},
                    pot_size=float(hand.bet),
                    double_allowed=PlayerAction.DOUBLE in allowed,
                    split_allowed=PlayerAction.SPLIT in allowed,
                )
                decision = player.decide_bet(obs)
                action = decision.action or PlayerAction.STAND
                if action not in allowed:
                    action = PlayerAction.STAND
                if branch_debug is not None:
                    branch_debug.append(
                        f"Strategy chose {action.value} (allowed: {[a.value for a in allowed]}) "
                        f"active_hand_index={state.active_hand_index} deck_remaining={self.deck.cards_remaining()}"
                    )
                self.apply_player_action(state, action)
                if all(h.is_finished for h in state.player_hands):
                    self.complete_round(state)

            self._finish_branch_player_totals(player, state, bankroll_after_bet)
            return BlackjackBranchOutcome(
                final_state=state,
                dealt_sequence=list(dealt),
                final_deck=copy.deepcopy(self.deck),
                slug_triggered=self._reshuffle_after_hand,
            )
        finally:
            self._branch_dealt = None
            self._branch_debug_recorder = None

    def start_cli_round(self, bankroll: int, bet: int) -> BlackjackRoundState:
        if bankroll < self.bet_min:
            raise ValueError("bankroll is below table minimum")
        if bet < self.bet_min or bet > self.bet_max:
            raise ValueError("bet is outside table limits")
        if bet > bankroll:
            raise ValueError("bet cannot exceed bankroll")

        self._reshuffle_after_hand = False
        self.refresh_shoe_if_needed(min_cards_remaining=4)
        bankroll_after_bet = bankroll - bet

        player_hand = BlackjackHand(cards=[self._draw_playable_card(), self._draw_playable_card()], bet=bet)
        dealer_cards = [self._draw_playable_card(), self._draw_playable_card()]
        state = BlackjackRoundState(
            dealer_cards=dealer_cards,
            player_hands=[player_hand],
            active_hand_index=0,
            bankroll=bankroll_after_bet,
            initial_bankroll=bankroll,
            insurance_offered=dealer_cards[0].rank is Rank.ACE,
        )

        player_natural = self._is_blackjack(player_hand.cards)
        dealer_natural = self._is_blackjack(dealer_cards)
        if player_natural or dealer_natural:
            self._resolve_naturals_for_cli(state)
            state.round_over = True
            self._finalize_round()
            return state

        self._advance_to_next_active_hand(state)
        return state

    def available_actions(self, state: BlackjackRoundState) -> list[PlayerAction]:
        if state.round_over:
            return []
        hand = state.player_hands[state.active_hand_index]
        if hand.is_finished:
            return []

        actions = [PlayerAction.HIT, PlayerAction.STAND]
        if (
            len(hand.cards) == 2
            and not hand.is_doubled
            and state.bankroll >= hand.bet
        ):
            actions.append(PlayerAction.DOUBLE)

        can_split = (
            len(hand.cards) == 2
            and not hand.is_split_hand
            and self._can_split_cards(hand.cards[0], hand.cards[1])
            and state.bankroll >= hand.bet
        )
        if can_split:
            actions.append(PlayerAction.SPLIT)

        return actions

    def _branch_debug_emit_state(self, state: BlackjackRoundState, note: str) -> None:
        r = self._branch_debug_recorder
        if r is None:
            return
        hand_bits: list[str] = []
        for i, h in enumerate(state.player_hands, start=1):
            tv = self._hand_value(h.cards)
            st = "done" if h.is_finished else "active"
            hand_bits.append(
                f"H{i}[{st} bet={h.bet}]: {' '.join(str(c) for c in h.cards)} -> {tv}"
            )
        dv = self._hand_value(state.dealer_cards)
        r.append(
            f"{note} | bankroll={state.bankroll} | deck_remaining={self.deck.cards_remaining()} | "
            + " ; ".join(hand_bits)
            + f" | dealer: {' '.join(str(c) for c in state.dealer_cards)} (total {dv})"
        )

    def apply_player_action(self, state: BlackjackRoundState, action: PlayerAction) -> None:
        if state.round_over:
            return

        hand = state.player_hands[state.active_hand_index]
        allowed = self.available_actions(state)
        if action not in allowed:
            raise ValueError("action not allowed in current hand state")

        if action == PlayerAction.HIT:
            hand.cards.append(self._draw_playable_card())
            if self._hand_value(hand.cards) >= 21:
                hand.is_finished = True
                self._advance_to_next_active_hand(state)
            self._branch_debug_emit_state(state, "after HIT")
            return

        if action == PlayerAction.STAND:
            hand.is_finished = True
            self._advance_to_next_active_hand(state)
            self._branch_debug_emit_state(state, "after STAND")
            return

        if action == PlayerAction.DOUBLE:
            state.bankroll -= hand.bet
            hand.bet *= 2
            hand.is_doubled = True
            hand.cards.append(self._draw_playable_card())
            hand.is_finished = True
            self._advance_to_next_active_hand(state)
            self._branch_debug_emit_state(state, "after DOUBLE")
            return

        if action == PlayerAction.SPLIT:
            if len(hand.cards) != 2:
                raise ValueError("split requires exactly two cards")
            state.bankroll -= hand.bet
            card_a, card_b = hand.cards
            hand.cards = [card_a, self._draw_playable_card()]
            hand.is_split_hand = True

            new_hand = BlackjackHand(
                cards=[card_b, self._draw_playable_card()],
                bet=hand.bet,
                is_split_hand=True,
            )
            state.player_hands.insert(state.active_hand_index + 1, new_hand)

            if self._hand_value(hand.cards) >= 21:
                hand.is_finished = True
                self._advance_to_next_active_hand(state)
            self._branch_debug_emit_state(state, "after SPLIT")
            return

    def complete_round(self, state: BlackjackRoundState) -> None:
        if state.round_over:
            return
        if any(not hand.is_finished for hand in state.player_hands):
            raise ValueError("cannot complete round while player still has active hands")

        if all(self._hand_value(hand.cards) > 21 for hand in state.player_hands):
            state.round_over = True
            state.message = "All player hands bust."
            if self._branch_debug_recorder is not None:
                self._branch_debug_recorder.append(
                    "All player hands bust — dealer does not play this round."
                )
                self._branch_debug_emit_state(state, "end (all bust)")
            self._finalize_round()
            if self._branch_debug_recorder is not None:
                self._branch_debug_recorder.append(
                    f"post-finalize deck_remaining={self.deck.cards_remaining()} "
                    f"(slug_reshuffle={self._reshuffle_after_hand})"
                )
            return

        self._run_dealer_turn(state.dealer_cards)
        dealer_total = self._hand_value(state.dealer_cards)

        outcomes: list[str] = []
        for idx, hand in enumerate(state.player_hands, start=1):
            player_total = self._hand_value(hand.cards)
            if player_total > 21:
                outcomes.append(f"Hand {idx}: bust, lose {hand.bet}")
                continue
            if dealer_total > 21 or player_total > dealer_total:
                payout = hand.bet * 2
                state.bankroll += payout
                outcomes.append(f"Hand {idx}: win +{hand.bet}")
            elif player_total == dealer_total:
                state.bankroll += hand.bet
                outcomes.append(f"Hand {idx}: push")
            else:
                outcomes.append(f"Hand {idx}: lose {hand.bet}")

        state.round_over = True
        state.message = " | ".join(outcomes)
        self._finalize_round()
        if self._branch_debug_recorder is not None:
            self._branch_debug_recorder.append(f"Settlement: {state.message}")
            self._branch_debug_recorder.append(
                f"Final bankroll={state.bankroll} deck_remaining={self.deck.cards_remaining()}"
            )

    @staticmethod
    def tally_round_wlp(state: BlackjackRoundState) -> tuple[int, int, int]:
        """
        Wins, losses, and pushes counting each finished player hand (splits yield several).

        Losses include player busts and non-push losses to the dealer (including when the
        dealer has a natural). Requires ``state.round_over``.
        """
        if not state.round_over:
            raise ValueError("round must be finished before tallying outcomes")

        wins = losses = pushes = 0
        dealer_cards = state.dealer_cards
        dealer_total = Blackjack._hand_value(dealer_cards)
        dealer_bj = Blackjack._is_blackjack(dealer_cards)

        if all(Blackjack._hand_value(h.cards) > 21 for h in state.player_hands):
            for _ in state.player_hands:
                losses += 1
            return wins, losses, pushes

        for hand in state.player_hands:
            pt = Blackjack._hand_value(hand.cards)
            player_bj = Blackjack._is_blackjack(hand.cards)
            if pt > 21:
                losses += 1
                continue
            if dealer_bj:
                if player_bj:
                    pushes += 1
                else:
                    losses += 1
                continue
            if player_bj:
                wins += 1
                continue
            if dealer_total > 21 or pt > dealer_total:
                wins += 1
            elif pt == dealer_total:
                pushes += 1
            else:
                losses += 1
        return wins, losses, pushes

    def set_insurance_bet(self, state: BlackjackRoundState, amount: int) -> None:
        if not state.insurance_offered:
            raise ValueError("insurance is not offered this round")
        if amount < 0:
            raise ValueError("insurance bet cannot be negative")
        max_insurance = state.player_hands[0].bet // 2
        if amount > max_insurance:
            raise ValueError("insurance bet cannot exceed half of main bet")
        if amount > state.bankroll:
            raise ValueError("insurance bet cannot exceed bankroll")
        state.bankroll -= amount
        state.insurance_bet = amount

    def render_table(
        self,
        state: BlackjackRoundState,
        reveal_dealer: bool = False,
        card_format: Callable[[Card], str] | None = None,
    ) -> str:
        def cstr(card: Card) -> str:
            return card_format(card) if card_format is not None else str(card)

        card_gap = "  "
        if reveal_dealer:
            dealer_total = self._hand_value(state.dealer_cards)
            dealer_cards = (
                f"{card_gap.join(cstr(card) for card in state.dealer_cards)} "
                f"[{dealer_total}]"
            )
        else:
            dealer_cards = f"{cstr(state.dealer_cards[0])}  [hidden]"
        lines = [f"Dealer: {dealer_cards}"]
        for i, hand in enumerate(state.player_hands, start=1):
            hand_total = self._hand_value(hand.cards)
            active = "*" if i - 1 == state.active_hand_index and not state.round_over else " "
            lines.append(
                f"{active}Hand {i} (bet {hand.bet}): "
                f"{card_gap.join(cstr(card) for card in hand.cards)} "
                f"[{hand_total}]"
            )
        lines.append(f"Chips: {state.bankroll}")
        if state.insurance_offered and not state.round_over:
            lines.append("Insurance available.")
        if state.message:
            lines.append(state.message)
        return "\n".join(lines)

    def play_round(self, player: Player) -> None:
        if player.bankroll < self.bet_min:
            print(f"{player.name} does not have enough bankroll for table minimum.")
            return

        wager_value = self.begin_round_wager(player)
        if wager_value is None:
            print(f"{player.name} placed an invalid bet. No hand dealt.")
            return
        wager = int(wager_value)
        state = self.start_cli_round(bankroll=int(player.bankroll + wager), bet=wager)
        if state.insurance_offered:
            should_take_insurance = player.strategy.take_insurance(
                bankroll=float(state.bankroll),
                main_bet=float(wager),
                player_cards=tuple(state.player_hands[0].cards),
            )
            if should_take_insurance:
                insurance_amount = min(wager // 2, state.bankroll)
                if insurance_amount > 0:
                    self.set_insurance_bet(state, insurance_amount)

        while not state.round_over:
            hand = state.player_hands[state.active_hand_index]
            if self._hand_value(hand.cards) < 17:
                self.apply_player_action(state, PlayerAction.HIT)
            else:
                self.apply_player_action(state, PlayerAction.STAND)
            if all(h.is_finished for h in state.player_hands):
                self.complete_round(state)

        player.bankroll = float(state.bankroll)
        print(self.render_table(state, reveal_dealer=True))

    def _run_player_turn(
        self, player: Player, player_hand: list[Card], dealer_upcard: Card, wager: float
    ) -> None:
        while self._hand_value(player_hand) < 21:
            observation = GameObservation(
                phase=BettingPhase.MID_ROUND,
                player_hand=tuple(player_hand),
                visible_table_cards=(dealer_upcard,),
                visible_opponent_cards={},
                pot_size=wager,
            )
            decision = player.decide_bet(observation)
            action = decision.action or PlayerAction.STAND
            if action == PlayerAction.HIT:
                player_hand.append(self._draw_playable_card())
                continue
            if action == PlayerAction.STAND:
                return
            # Unsupported base-game actions are treated as stand for now.
            return

    def _run_dealer_turn(self, dealer_hand: list[Card]) -> None:
        r = self._branch_debug_recorder
        dealer_started = False
        while True:
            total = self._hand_value(dealer_hand)
            soft = self._is_soft_hand(dealer_hand)
            should_hit = total < 17 or (self.dealer_hits_soft_17 and total == 17 and soft)
            if not should_hit:
                if r is not None:
                    r.append(
                        f"Dealer STAND — {' '.join(str(c) for c in dealer_hand)} total={total} "
                        f"(soft17={soft}) deck_remaining={self.deck.cards_remaining()}"
                    )
                return
            if r is not None and not dealer_started:
                r.append(
                    f"Dealer turn start — {' '.join(str(c) for c in dealer_hand)} total={total} "
                    f"deck_remaining={self.deck.cards_remaining()}"
                )
                dealer_started = True
            dealer_hand.append(self._draw_playable_card())
            if r is not None:
                nt = self._hand_value(dealer_hand)
                r.append(
                    f"Dealer HIT — {' '.join(str(c) for c in dealer_hand)} total={nt} "
                    f"deck_remaining={self.deck.cards_remaining()}"
                )

    def _resolve_natural_blackjack(
        self, player: Player, wager: float, player_hand: list[Card], dealer_hand: list[Card]
    ) -> None:
        print(f"{player.name}: {player_hand} | Dealer: {dealer_hand}")
        player_natural = self._is_blackjack(player_hand)
        dealer_natural = self._is_blackjack(dealer_hand)

        if player_natural and dealer_natural:
            player.apply_payout(wager)
            print("Both have blackjack. Push.")
            return
        if player_natural:
            player.apply_payout(wager * (1 + self.blackjack_payout_ratio))
            print(f"{player.name} has blackjack and wins {wager * self.blackjack_payout_ratio:.2f}.")
            return
        print("Dealer blackjack.")

    def _resolve_naturals_for_cli(self, state: BlackjackRoundState) -> None:
        hand = state.player_hands[0]
        player_natural = self._is_blackjack(hand.cards)
        dealer_natural = self._is_blackjack(state.dealer_cards)
        if player_natural and dealer_natural:
            state.bankroll += hand.bet
            if state.insurance_bet > 0:
                state.bankroll += state.insurance_bet * 3
            state.message = "Both player and dealer have blackjack: push."
            return
        if player_natural:
            payout = hand.bet + int(round(hand.bet * self.blackjack_payout_ratio))
            state.bankroll += payout
            state.message = f"Blackjack! Paid {payout - hand.bet}."
            return
        if state.insurance_bet > 0:
            state.bankroll += state.insurance_bet * 3
        state.message = "Dealer has blackjack."

    def _advance_to_next_active_hand(self, state: BlackjackRoundState) -> None:
        for idx, hand in enumerate(state.player_hands):
            if not hand.is_finished and self._hand_value(hand.cards) < 21:
                state.active_hand_index = idx
                return
            if self._hand_value(hand.cards) >= 21:
                hand.is_finished = True

        if all(hand.is_finished for hand in state.player_hands):
            self.complete_round(state)

    def _draw_playable_card(self) -> Card:
        while True:
            if self.deck.cards_remaining() == 0:
                if not self.include_slug:
                    raise ValueError("not enough cards left in deck")
                self.deck.reset()
                self.deck.shuffle()
                self._reshuffle_after_hand = True
            card = self.deck.draw(1)[0]
            if self._branch_dealt is not None:
                self._branch_dealt.append(card)
            if card.is_slug:
                self._reshuffle_after_hand = True
                continue
            return card

    def _finalize_round(self) -> None:
        if self._reshuffle_after_hand:
            self.deck.reset()
            self.deck.shuffle()
            if self.verbose:
                print("Slug reached: shoe shuffled for next hand.")

    @staticmethod
    def _is_blackjack(hand: list[Card]) -> bool:
        return len(hand) == 2 and Blackjack._hand_value(hand) == 21

    @staticmethod
    def _is_soft_hand(hand: list[Card]) -> bool:
        aces = sum(1 for card in hand if card.rank and card.rank.value == "A")
        hard_total = sum(Blackjack._card_value(card) for card in hand)
        return aces > 0 and hard_total <= 11

    @staticmethod
    def _hand_value(hand: list[Card]) -> int:
        total = sum(Blackjack._card_value(card) for card in hand)
        aces = sum(1 for card in hand if card.rank and card.rank.value == "A")
        while aces > 0 and total + 10 <= 21:
            total += 10
            aces -= 1
        return total

    @staticmethod
    def _card_value(card: Card) -> int:
        if card.rank is None:
            raise ValueError("slug cards are not valid gameplay cards")
        if card.rank.value in {"J", "Q", "K"}:
            return 10
        if card.rank.value == "A":
            return 1
        return int(card.rank.value)

    @staticmethod
    def _can_split_cards(card_a: Card, card_b: Card) -> bool:
        if card_a.rank is None or card_b.rank is None:
            return False
        ten_value_ranks = {Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING}
        if card_a.rank in ten_value_ranks and card_b.rank in ten_value_ranks:
            return True
        return card_a.rank == card_b.rank
