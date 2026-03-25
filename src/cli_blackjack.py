import sys

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


def choose_bet(game: Blackjack, bankroll: int) -> int:
    options = game.get_bet_options(bankroll)
    if not options:
        return 0
    bet_menu: list[tuple[str, str]] = [("0", "Cash out / exit")]
    for bet in options:
        bet_menu.append((str(bet), f"Bet {bet}"))
    chosen = select_from_menu("Choose your wager", bet_menu)
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


def main() -> None:
    init_terminal()

    banner = "=== Blackjack CLI ==="
    if ansi_enabled:
        print(f"{MAGENTA}{BOLD}{banner}{RST}")
    else:
        print(banner)

    bankroll = prompt_int("Starting chips: ", minimum=5)
    table_min = prompt_int("Table minimum bet: ", minimum=5)
    table_max = prompt_int("Table maximum bet: ", minimum=table_min)
    game = Blackjack(bet_min=table_min, bet_max=table_max, deck_count=6, include_slug=True)

    while bankroll >= game.bet_min:
        chips_lbl = f"{YELLOW}{BOLD}Current chips:{RST}" if ansi_enabled else "Current chips:"
        chips_val = f"{GREEN}{bankroll}{RST}" if ansi_enabled else str(bankroll)
        print(f"\n{chips_lbl} {chips_val}")
        bet = choose_bet(game, bankroll)
        if bet == 0:
            break

        state = game.start_cli_round(bankroll=bankroll, bet=bet)
        print()
        _print_table(game, state, reveal_dealer=False)

        while not state.round_over:
            action = choose_action(game, state)
            game.apply_player_action(state, action)
            print()
            _print_table(game, state, reveal_dealer=False)

        final_lbl = f"{CYAN}{BOLD}Final table:{RST}" if ansi_enabled else "Final table:"
        print(f"\n{final_lbl}")
        _print_table(game, state, reveal_dealer=True)
        bankroll = state.bankroll

    end_msg = f"Game over. Final chips: {bankroll}"
    if ansi_enabled:
        print(f"\n{DIM}{end_msg}{RST}")
    else:
        print(f"\n{end_msg}")


if __name__ == "__main__":
    main()
