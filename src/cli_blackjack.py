from dataclasses import dataclass

from casino_sim.cli.terminal_menus import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    RST,
    WHITE,
    YELLOW,
    ansi_enabled,
    init_terminal,
    prompt_int,
    select_from_menu,
)
from casino_sim.games.blackjack import Blackjack, BlackjackRoundState
from casino_sim.games.lucky_queens_blackjack import (
    LuckyQueensBlackjack,
    classify_block_bonus,
    classify_lucky_queens,
    _chips_returned_block,
    _chips_returned_lucky_queens,
)
from casino_sim.models.betting import PlayerAction
from casino_sim.models.card import Card, Suit


def _format_card_cli(card: Card) -> str:
    if not ansi_enabled:
        return str(card)
    if card.is_slug:
        return f"{MAGENTA}{BOLD}{str(card)}{RST}"
    if card.suit is None or card.rank is None:
        return str(card)
    red = card.suit in (Suit.HEARTS, Suit.DIAMONDS)
    color = RED if red else WHITE
    return f"{color}{str(card)}{RST}"


def _style_table_block(text: str) -> str:
    """Apply labels, hidden card dimming, chips accent, and outcome colors."""
    if not ansi_enabled:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if line.startswith("Dealer:"):
            rest = line[len("Dealer:") :].lstrip()
            hidden = "[hidden]" in rest
            if hidden:
                parts = rest.split("[hidden]", 1)
                colored = (
                    f"{parts[0]}{DIM}[hidden]{RST}{parts[1] if len(parts) > 1 else ''}"
                )
            else:
                try:
                    rb = rest.rindex(" [")
                    if rest.endswith("]"):
                        colored = f"{rest[:rb]}{CYAN}{rest[rb:]}{RST}"
                    else:
                        colored = rest
                except ValueError:
                    colored = rest
            out.append(f"{CYAN}{BOLD}Dealer:{RST} {colored}")
            continue
        if line.startswith("Chips:"):
            rest = line[len("Chips:") :].strip()
            out.append(f"{YELLOW}{BOLD}Chips:{RST} {GREEN}{rest}{RST}")
            continue
        if line == "Insurance available.":
            out.append(f"{YELLOW}{line}{RST}")
            continue
        if line.startswith("*Hand ") or line.startswith(" Hand"):
            if line.startswith("*Hand "):
                body = line[1:]
                prefix = f"{GREEN}*{RST}"
            else:
                body = line.lstrip()
                prefix = " "
            colon = body.index(": ")
            head = body[:colon]
            rest = body[colon + 2 :]
            rb = rest.rindex(" [")
            cards_display = rest[:rb]
            total_display = rest[rb:]
            out.append(
                prefix
                + f"{BOLD}{head}{RST}: {cards_display}{CYAN}{total_display}{RST}"
            )
            continue
        if " | " in line or ": " in line and any(
            w in line.lower() for w in ("win", "lose", "push", "bust")
        ):
            out.append(_style_outcome_line(line))
            continue
        out.append(line)
    return "\n".join(out)


@dataclass(frozen=True)
class MainBetSelection:
    """Result of the main-wager menu (standard or Lucky Queens)."""

    cash_out: bool = False
    repeat_last: bool = False
    main_bet: int = 0


def _repeat_main_affordable(game: Blackjack, bankroll: int, last_main: int | None) -> bool:
    if last_main is None:
        return False
    lo, hi = int(game.bet_min), int(game.bet_max)
    return lo <= last_main <= hi and bankroll >= last_main


def _repeat_lucky_queens_affordable(
    game: Blackjack,
    bankroll: int,
    *,
    last_main: int,
    last_block: int,
    last_lucky: int,
    block_lo: int,
    block_hi: int,
    lucky_lo: int,
    lucky_hi: int,
) -> bool:
    total = last_main + last_block + last_lucky
    if bankroll < total:
        return False
    if not (block_lo <= last_block <= block_hi and lucky_lo <= last_lucky <= lucky_hi):
        return False
    lo, hi = int(game.bet_min), int(game.bet_max)
    return lo <= last_main <= hi


def _style_outcome_line(line: str) -> str:
    parts = line.split(" | ")
    styled: list[str] = []
    for p in parts:
        low = p.lower()
        if "push" in low:
            styled.append(f"{YELLOW}{p}{RST}")
        elif "lose" in low or "bust" in low:
            styled.append(f"{RED}{p}{RST}")
        elif "win" in low or "blackjack" in low:
            styled.append(f"{GREEN}{p}{RST}")
        else:
            styled.append(p)
    return " | ".join(styled)


def choose_main_wager(
    game: Blackjack,
    bankroll: int,
    *,
    last_main: int | None = None,
    last_block: int | None = None,
    last_lucky: int | None = None,
    block_lo: int | None = None,
    block_hi: int | None = None,
    lucky_lo: int | None = None,
    lucky_hi: int | None = None,
) -> MainBetSelection:
    options = game.get_bet_options(bankroll)
    if not options:
        return MainBetSelection(cash_out=True)

    bet_menu: list[tuple[str, str]] = [("0", "Cash out / exit")]

    show_repeat = False
    if (
        last_main is not None
        and last_block is not None
        and last_lucky is not None
        and block_lo is not None
        and block_hi is not None
        and lucky_lo is not None
        and lucky_hi is not None
    ):
        show_repeat = _repeat_lucky_queens_affordable(
            game,
            bankroll,
            last_main=last_main,
            last_block=last_block,
            last_lucky=last_lucky,
            block_lo=block_lo,
            block_hi=block_hi,
            lucky_lo=lucky_lo,
            lucky_hi=lucky_hi,
        )
    elif last_main is not None:
        show_repeat = _repeat_main_affordable(game, bankroll, last_main)

    if show_repeat:
        assert last_main is not None
        if last_block is not None and last_lucky is not None:
            rb, rl = last_block, last_lucky
            rlabel = f"Repeat last (main {last_main}, Block {rb}, LQ {rl})"
        else:
            rlabel = f"Repeat last (bet {last_main})"
        bet_menu.append(("repeat", rlabel))

    for bet in options:
        bet_menu.append((str(bet), f"Bet {bet}"))

    chosen = select_from_menu("Choose your wager", bet_menu)
    if chosen == "0":
        return MainBetSelection(cash_out=True)
    if chosen == "repeat":
        return MainBetSelection(repeat_last=True, main_bet=last_main or 0)
    return MainBetSelection(main_bet=int(chosen))


def choose_side_stake(title: str, lo: int, hi: int, max_affordable: int) -> int:
    """Pick a side-bet amount in [0, hi], respecting table bounds and bankroll cap."""
    if max_affordable <= 0 or hi <= 0:
        return 0
    hi_eff = min(hi, max_affordable)
    if hi_eff < lo:
        return 0

    candidates: list[int] = [0, lo]
    mid = (lo + hi_eff) // 2
    mid = max(lo, min(hi_eff, mid))
    for v in (mid, hi_eff):
        if lo <= v <= hi_eff and v not in candidates:
            candidates.append(v)
    candidates = sorted(set(candidates))

    menu: list[tuple[str, str]] = []
    for c in candidates:
        if c == 0:
            menu.append(("0", "Pass (0)"))
        else:
            menu.append((str(c), f"Wager {c}"))
    chosen = select_from_menu(title, menu)
    return int(chosen)


def choose_action(game: Blackjack, state: BlackjackRoundState) -> PlayerAction:
    actions = game.available_actions(state)
    action_menu: list[tuple[str, str]] = []
    labels = {
        PlayerAction.HIT: "Hit",
        PlayerAction.STAND: "Stand",
        PlayerAction.DOUBLE: "Double",
        PlayerAction.SPLIT: "Split",
    }
    for action in actions:
        action_menu.append((action.value, labels[action]))
    selected = select_from_menu("Choose action", action_menu)
    return PlayerAction(selected)


def _print_table(game: Blackjack, state: BlackjackRoundState, reveal_dealer: bool) -> None:
    raw = game.render_table(
        state, reveal_dealer=reveal_dealer, card_format=_format_card_cli
    )
    print(_style_table_block(raw))


def _play_cli_round_until_done(game: Blackjack, state: BlackjackRoundState) -> None:
    print()
    _print_table(game, state, reveal_dealer=False)
    while not state.round_over:
        action = choose_action(game, state)
        game.apply_player_action(state, action)
        print()
        _print_table(game, state, reveal_dealer=False)


def _print_side_settlements(
    state: BlackjackRoundState,
    initial_pair: tuple[Card, Card],
    block_stake: int,
    lucky_stake: int,
) -> float:
    """
    Print Block Bonus / Lucky Queens resolution (first two hole cards vs dealer up).
    Returns total chips returned from both side bets (including stake on wins/pushes).
    """
    p0, p1 = initial_pair
    dealer_up = state.dealer_cards[0]
    total_return = 0.0
    hdr = f"{CYAN}{BOLD}Side bets:{RST}" if ansi_enabled else "Side bets:"
    print(f"\n{hdr}")

    if block_stake > 0:
        cat = classify_block_bonus(p0, p1, dealer_up)
        ret = _chips_returned_block(float(block_stake), cat)
        total_return += ret
        net = ret - float(block_stake)
        line = (
            f"  Block Bonus ({block_stake}): {cat.value} → returned {ret:.0f} "
            f"(net {net:+.0f})"
        )
        print(line)

    if lucky_stake > 0:
        cat = classify_lucky_queens(p0, p1)
        ret = _chips_returned_lucky_queens(float(lucky_stake), cat)
        total_return += ret
        net = ret - float(lucky_stake)
        line = (
            f"  Lucky Queens ({lucky_stake}): {cat.value} → returned {ret:.0f} "
            f"(net {net:+.0f})"
        )
        print(line)

    if block_stake <= 0 and lucky_stake <= 0:
        print("  (none this hand)")

    return total_return


def run_standard_session(
    game: Blackjack,
    initial_bankroll: int,
) -> int:
    bankroll = initial_bankroll
    last_main: int | None = None
    while bankroll >= game.bet_min:
        chips_lbl = f"{YELLOW}{BOLD}Current chips:{RST}" if ansi_enabled else "Current chips:"
        chips_val = f"{GREEN}{bankroll}{RST}" if ansi_enabled else str(bankroll)
        print(f"\n{chips_lbl} {chips_val}")
        pick = choose_main_wager(game, bankroll, last_main=last_main)
        if pick.cash_out:
            break
        if pick.repeat_last:
            bet = last_main if last_main is not None else pick.main_bet
        else:
            bet = pick.main_bet

        state = game.start_cli_round(bankroll=bankroll, bet=bet)
        _play_cli_round_until_done(game, state)

        final_lbl = f"{CYAN}{BOLD}Final table:{RST}" if ansi_enabled else "Final table:"
        print(f"\n{final_lbl}")
        _print_table(game, state, reveal_dealer=True)
        bankroll = state.bankroll
        last_main = bet

    return bankroll


def run_lucky_queens_session(
    game: LuckyQueensBlackjack,
    initial_bankroll: int,
    block_lo: int,
    block_hi: int,
    lucky_lo: int,
    lucky_hi: int,
) -> int:
    bankroll = initial_bankroll
    last_main: int | None = None
    last_block: int | None = None
    last_lucky: int | None = None
    while bankroll >= game.bet_min:
        chips_lbl = f"{YELLOW}{BOLD}Current chips:{RST}" if ansi_enabled else "Current chips:"
        chips_val = f"{GREEN}{bankroll}{RST}" if ansi_enabled else str(bankroll)
        print(f"\n{chips_lbl} {chips_val}")
        pick = choose_main_wager(
            game,
            bankroll,
            last_main=last_main,
            last_block=last_block,
            last_lucky=last_lucky,
            block_lo=block_lo,
            block_hi=block_hi,
            lucky_lo=lucky_lo,
            lucky_hi=lucky_hi,
        )
        if pick.cash_out:
            break

        if pick.repeat_last:
            assert last_main is not None and last_block is not None and last_lucky is not None
            bet = last_main
            block_stake = last_block
            lucky_stake = last_lucky
        else:
            bet = pick.main_bet
            after_main = bankroll - bet
            block_stake = choose_side_stake(
                "Block Bonus (vs dealer up-card)",
                block_lo,
                block_hi,
                after_main,
            )
            lucky_stake = choose_side_stake(
                "Lucky Queens (first two player cards)",
                lucky_lo,
                lucky_hi,
                after_main - block_stake,
            )
            if block_stake + lucky_stake > after_main:
                warn = YELLOW if ansi_enabled else ""
                rst = RST if ansi_enabled else ""
                print(f"{warn}Side bets exceed chips after main wager; choose again.{rst}")
                continue

        bankroll_for_hand = bankroll - block_stake - lucky_stake
        state = game.start_cli_round(bankroll=bankroll_for_hand, bet=bet)
        initial_pair = (state.player_hands[0].cards[0], state.player_hands[0].cards[1])

        _play_cli_round_until_done(game, state)

        final_lbl = f"{CYAN}{BOLD}Final table:{RST}" if ansi_enabled else "Final table:"
        print(f"\n{final_lbl}")
        _print_table(game, state, reveal_dealer=True)

        side_return = _print_side_settlements(
            state, initial_pair, block_stake, lucky_stake
        )
        bankroll = int(round(float(state.bankroll) + side_return))
        last_main = bet
        last_block = block_stake
        last_lucky = lucky_stake

    return bankroll


def main() -> None:
    init_terminal()

    banner = "=== Blackjack CLI ==="
    if ansi_enabled:
        print(f"{MAGENTA}{BOLD}{banner}{RST}")
    else:
        print(banner)

    variant = select_from_menu(
        "Game variant",
        [
            ("standard", "Standard blackjack"),
            ("lucky_queens", "Lucky Queens (+ Block Bonus & Lucky Queens)"),
        ],
    )

    bankroll = prompt_int("Starting chips: ", minimum=5)
    table_min = prompt_int("Table minimum bet: ", minimum=5)
    table_max = prompt_int("Table maximum bet: ", minimum=table_min)

    if variant == "standard":
        game = Blackjack(
            bet_min=table_min, bet_max=table_max, deck_count=6, include_slug=True
        )
        final = run_standard_session(game, bankroll)
    else:
        print("\nSide-bet table limits (whole chips, same idea as the sim CLI).")
        block_lo = prompt_int("Block Bonus minimum: ", minimum=1)
        block_hi = prompt_int("Block Bonus maximum: ", minimum=block_lo)
        lucky_lo = prompt_int("Lucky Queens minimum: ", minimum=1)
        lucky_hi = prompt_int("Lucky Queens maximum: ", minimum=lucky_lo)
        game = LuckyQueensBlackjack(
            bet_min=table_min, bet_max=table_max, deck_count=6, include_slug=True
        )
        final = run_lucky_queens_session(
            game, bankroll, block_lo, block_hi, lucky_lo, lucky_hi
        )

    end_msg = f"Game over. Final chips: {final}"
    if ansi_enabled:
        print(f"\n{DIM}{end_msg}{RST}")
    else:
        print(f"\n{end_msg}")


if __name__ == "__main__":
    main()
