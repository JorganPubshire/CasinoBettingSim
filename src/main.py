import sys

from casino_sim.games import Blackjack
from casino_sim.models.player import Player
from casino_sim.strategies import DummyStrategy


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    player = Player(name="Dummy", bankroll=1000.0, strategy=DummyStrategy())
    game = Blackjack(bet_min=10.0, bet_max=200.0, deck_count=6)

    print("Running one blackjack round with DummyStrategy...")
    game.play_round(player)
    print(f"Bankroll after round: {player.bankroll:.2f}")


if __name__ == "__main__":
    main()
