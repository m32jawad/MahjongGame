import random
from typing import List, Tuple, Optional, Union

# Define suit and tile names as provided.
SUIT_NAMES = {
    0: "bamboo",
    1: "characters",
    2: "dots",
    3: "winds",
    4: "dragons",
    5: "bonus",
}

TILE_NAMES = {
    0: "bamboo 1",
    1: "bamboo 2",
    2: "bamboo 3",
    3: "bamboo 4",
    4: "bamboo 5",
    5: "bamboo 6",
    6: "bamboo 7",
    7: "bamboo 8",
    8: "bamboo 9",
    9: "characters 1",
    10: "characters 2",
    11: "characters 3",
    12: "characters 4",
    13: "characters 5",
    14: "characters 6",
    15: "characters 7",
    16: "characters 8",
    17: "characters 9",
    18: "dots 1",
    19: "dots 2",
    20: "dots 3",
    21: "dots 4",
    22: "dots 5",
    23: "dots 6",
    24: "dots 7",
    25: "dots 8",
    26: "dots 9",
    27: "east",
    28: "south",
    29: "west",
    30: "north",
    31: "green dragon",
    32: "red dragon",
    33: "white dragon",
    34: "flower 1",
    35: "flower 2",
    36: "flower 3",
    37: "flower 4",
    38: "season 1",
    39: "season 2",
    40: "season 3",
    41: "season 4",
}


class Tile:
    """
    Represents a Mahjong tile.
    """
    def __init__(self, id: int):
        self.id = id
        self.suit = "bamboo" if id < 9 else "characters" if id < 18 else "dots"
        self.name = f"{self.suit} {id % 9 + 1}"
        # The image file is stored in the static/images/tiles directory.
        self.image_path = f"/static/images/tiles/{id}.jpg"

    def __repr__(self):
        return f"Tile(id={self.id}, name='{self.name}', suit='{self.suit}')"


def create_deck() -> List[Tile]:
    """
    Create the full Mahjong deck.
      - Standard tiles (ids 0-33) have four copies each.
      - Bonus tiles (ids 34-41) have one copy each.
    """
    return [Tile(i) for i in range(27)]


def shuffle_deck(deck: List[Tile]) -> None:
    """Shuffle the deck in-place."""
    random.shuffle(deck)


def deal_tiles(deck: List[Tile]) -> Tuple[dict[str, List[Tile]], List[Tile]]:
    """
    Deal tiles to four players.
      - Each player gets 13 tiles.
      - The dealer (East) receives an extra tile (total 14).
    Returns:
      - players_hands: dict with keys: 'east', 'south', 'west', 'north'
      - remaining deck after dealing.
    """
    hands = {
        "east": deck[0:14],      # Dealer gets 14
        "south": deck[14:27],
        "west": deck[27:40],
        "north": deck[40:53]
    }
    remaining = deck[53:]
    return hands, remaining

def can_claim_pong(hand: List[Tile], tile: Tile) -> bool:
    """Return True if hand contains at least two copies of tile (for pong)."""
    return sum(1 for t in hand if t.id == tile.id) >= 2

def can_claim_chi(hand: List[Tile], tile: Tile) -> Tuple[bool, Optional[List[int]]]:
    """
    Check if a chi meld is possible with the discarded tile.
    Only applicable for suited tiles (bamboo, characters, dots).
    Returns (True, sequence) if valid, else (False, None).
    """
    if tile.suit not in ['bamboo', 'characters', 'dots']:
        return False, None
    try:
        tile_number = int(tile.name.split()[1])
    except Exception:
        return False, None

    hand_numbers = []
    for t in hand:
        if t.suit == tile.suit:
            try:
                num = int(t.name.split()[1])
                hand_numbers.append(num)
            except Exception:
                continue

    sequences = []
    # Check for sequence possibilities:
    if (tile_number - 2 in hand_numbers) and (tile_number - 1 in hand_numbers):
        sequences.append([tile_number - 2, tile_number - 1, tile_number])
    if (tile_number - 1 in hand_numbers) and (tile_number + 1 in hand_numbers):
        sequences.append([tile_number - 1, tile_number, tile_number + 1])
    if (tile_number + 1 in hand_numbers) and (tile_number + 2 in hand_numbers):
        sequences.append([tile_number, tile_number + 1, tile_number + 2])
    
    if sequences:
        # Return the first valid sequence.
        return True, sequences[0]
    return False, None

def can_claim_kong(hand: List[Tile], tile: Tile) -> bool:
    """Return True if hand contains at least three copies of tile (for kong)."""
    return sum(1 for t in hand if t.id == tile.id) >= 3


if __name__ == "__main__":
    # Quick test run:
    deck = create_deck()
    print("Initial deck count:", len(deck))  # Should be 144 tiles
    shuffle_deck(deck)
    players, remaining_deck = deal_tiles(deck)
    for position, hand in players.items():
        print(f"{position.capitalize()} hand ({len(hand)} tiles): {hand}")
    print("Remaining deck count:", len(remaining_deck))
