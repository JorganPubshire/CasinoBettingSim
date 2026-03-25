# Casino Betting Simulator

Foundation-only project for simulating casino betting strategies.

## Included so far

- Reusable card/deck domain components
- `Deck(deck_count=...)` support for multi-deck games like blackjack
- Optional slug insertion via `Deck(include_slug=True)`, placed randomly in the
  back segment of the deck (default 72%-86% penetration)
- `Card` supports a special slug marker for shuffle-trigger workflows
- `Player` model with bankroll tracking
- `PlayerStrategy` interface for ante + phase-based betting decisions
- `CasinoGame` interface with configurable `bet_min` / `bet_max`
- Base Blackjack implementation (6-deck default)
- `DummyStrategy` (always bets max, always stands)
- Minimal console bootstrap (`src/main.py`) that runs one blackjack round

## Run

```bash
python src/main.py
```

Interactive CLI blackjack:

```bash
python src/cli_blackjack.py
```

## Next step

Add richer strategy logic and optional side-bet implementations.
