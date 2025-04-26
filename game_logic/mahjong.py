import random

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
    def __init__(self, tile_id: int):
        self.id = tile_id
        self.name = TILE_NAMES.get(tile_id, "Unknown")
        self.suit = self.get_suit(tile_id)
        # The image file is stored in the static/images/tiles directory.
        self.image_path = f"/static/images/tiles/{tile_id}.jpg"

    def get_suit(self, tile_id: int) -> str:
        """
        Determine the suit based on the tile id.
          - Bamboo: ids 0-8
          - Characters: ids 9-17
          - Dots: ids 18-26
          - Winds: ids 27-30
          - Dragons: ids 31-33
          - Bonus (flowers/seasons): ids 34-41
        """
        if 0 <= tile_id <= 8:
            return SUIT_NAMES[0]
        elif 9 <= tile_id <= 17:
            return SUIT_NAMES[1]
        elif 18 <= tile_id <= 26:
            return SUIT_NAMES[2]
        elif 27 <= tile_id <= 30:
            return SUIT_NAMES[3]
        elif 31 <= tile_id <= 33:
            return SUIT_NAMES[4]
        elif 34 <= tile_id <= 41:
            return SUIT_NAMES[5]
        else:
            return "unknown"

    def __repr__(self):
        return f"Tile(id={self.id}, name='{self.name}', suit='{self.suit}')"


def create_deck() -> list:
    """
    Create the full Mahjong deck.
      - Standard tiles (ids 0-33) have four copies each.
      - Bonus tiles (ids 34-41) have one copy each.
    """
    deck = []
    # For tiles 0-33, add 4 copies each.
    for tile_id in range(0, 34):
        for _ in range(4):
            deck.append(Tile(tile_id))
    # For bonus tiles (34-41), add one copy each.
    for tile_id in range(34, 42):
        deck.append(Tile(tile_id))
    return deck


def shuffle_deck(deck: list) -> None:
    """Shuffle the deck in-place."""
    random.shuffle(deck)


def deal_tiles(deck: list) -> (dict, list):
    """
    Deal tiles to four players.
      - Each player gets 13 tiles.
      - The dealer (East) receives an extra tile (total 14).
    
    Returns:
      - players_hands: dict with keys: 'east', 'south', 'west', 'north'
      - remaining deck after dealing.
    """
    players_hands = {
        'east': [],
        'south': [],
        'west': [],
        'north': []
    }
    # Deal 13 tiles to each player
    for _ in range(13):
        for player in ['east', 'south', 'west', 'north']:
            players_hands[player].append(deck.pop(0))
    # Dealer (north) gets an extra tile.
    players_hands['north'].append(deck.pop(0))
    return players_hands, deck

def can_claim_pong(hand, tile):

    """Return True if hand contains at least two copies of tile (for pong)."""
    count = sum(1 for t in hand if t.id == tile.id)
    return count >= 2

def can_claim_chi(hand, tile):
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

def can_claim_kong(hand, tile):
    """Return True if hand contains at least three copies of tile (for kong)."""
    count = sum(1 for t in hand if t.id == tile.id)
    return count >= 3


if __name__ == "__main__":
    # Quick test run:
    deck = create_deck()
    print("Initial deck count:", len(deck))  # Should be 144 tiles
    shuffle_deck(deck)
    players, remaining_deck = deal_tiles(deck)
    for position, hand in players.items():
        print(f"{position.capitalize()} hand ({len(hand)} tiles): {hand}")
    print("Remaining deck count:", len(remaining_deck))
