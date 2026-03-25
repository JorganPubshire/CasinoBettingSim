from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Self


class Suit(Enum):
    CLUBS = "Clubs"
    DIAMONDS = "Diamonds"
    HEARTS = "Hearts"
    SPADES = "Spades"


class Rank(Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


@dataclass(frozen=True)
class Card:
    rank: Rank | None
    suit: Suit | None
    is_slug: bool = False

    @classmethod
    def slug(cls) -> Self:
        return cls(rank=None, suit=None, is_slug=True)

    def __str__(self) -> str:
        if self.is_slug:
            return "SLUG"
        if self.rank is None or self.suit is None:
            return "Unknown Card"
        suit_emoji = {
            Suit.CLUBS: "♣️",
            Suit.DIAMONDS: "♦️",
            Suit.HEARTS: "♥️",
            Suit.SPADES: "♠️",
        }[self.suit]
        return f"{self.rank.value}{suit_emoji}"

    def __repr__(self) -> str:
        return self.__str__()
