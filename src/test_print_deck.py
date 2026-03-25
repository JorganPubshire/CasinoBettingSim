import sys

from casino_sim.models import Deck


def print_deck(deck: Deck, title: str) -> None:
    print(title)
    for card in deck.cards:
        print(card)


def main() -> None:
    # Needed on some Windows terminals for suit emoji output.
    sys.stdout.reconfigure(encoding="utf-8")
    deck = Deck(deck_count=1)

    print_deck(deck, "Ordered standard deck:")
    print("\n" + "-" * 24 + "\n")

    deck.shuffle()
    print_deck(deck, "Shuffled deck:")


if __name__ == "__main__":
    main()
