from __future__ import annotations

import random
from dataclasses import dataclass, field

from casino_sim.models.card import Card, Rank, Suit


@dataclass
class Deck:
    deck_count: int = 1
    include_slug: bool = False
    slug_position_range: tuple[float, float] = (0.72, 0.86)
    cards: list[Card] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.deck_count < 1:
            raise ValueError("deck_count must be at least 1")
        min_position, max_position = self.slug_position_range
        if not (0 <= min_position < max_position <= 1):
            raise ValueError("slug_position_range must be between 0 and 1")
        if not self.cards:
            self.reset()

    def reset(self) -> None:
        self.cards = [
            Card(rank=rank, suit=suit)
            for _ in range(self.deck_count)
            for suit in Suit
            for rank in Rank
        ]
        if self.include_slug:
            self.insert_slug_randomly()

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> list[Card]:
        if count < 1:
            raise ValueError("draw count must be at least 1")
        if count > len(self.cards):
            raise ValueError("not enough cards left in deck")

        drawn = self.cards[:count]
        self.cards = self.cards[count:]
        return drawn

    def cards_remaining(self) -> int:
        return len(self.cards)

    def has_slug(self) -> bool:
        return any(c.is_slug for c in self.cards)

    def insert_slug(self, position: int | None = None) -> None:
        slug = Card.slug()
        if position is None:
            self.cards.append(slug)
            return
        if position < 0 or position > len(self.cards):
            raise ValueError("slug insertion position is out of range")
        self.cards.insert(position, slug)

    def insert_slug_randomly(self) -> None:
        total_cards = len(self.cards)
        min_position = int(total_cards * self.slug_position_range[0])
        max_position = int(total_cards * self.slug_position_range[1])
        if max_position > total_cards:
            max_position = total_cards
        slug_position = random.randint(min_position, max_position)
        self.insert_slug(position=slug_position)
