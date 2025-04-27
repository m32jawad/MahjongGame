from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import uuid
import random
from threading import Thread
from time import sleep

from game_logic.mahjong import (
    create_deck,
    shuffle_deck,
    deal_tiles,
    can_claim_pong,
    can_claim_chi,
    can_claim_kong,
    Tile
)

NGROK_ACCESS_TOKEN = "2u4fhbHxSuoU8f80aTtpez81L3X_7hAz7AwyFrRuvpP9Fpsq2"
NGROK_DOMAIN = "sunbird-close-newt.ngrok-free.app"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for game rooms and state.
rooms = {}

# Enable test mode so that we get a predictable deck order.
TEST_MODE = True

# Turn order
POSITIONS = ["north", "east", "south", "west"]

def create_test_deck():
    full_deck = create_deck()
    full_deck.sort(key=lambda t: t.id)
    # Remove two copies of tile id 5 for forcing a meld (e.g. for Pong)
    copies_of_5 = [t for t in full_deck if t.id == 5]
    if len(copies_of_5) < 2:
         raise Exception("Not enough copies of tile id 5 for testing")
    for _ in range(2):
         tile5 = copies_of_5.pop(0)
         full_deck.remove(tile5)
    # Deal hands manually: 13 tiles each, then one extra for North.
    north_hand = full_deck[0:13]
    east_hand = full_deck[13:26]
    south_hand = full_deck[26:39]
    west_hand = full_deck[39:52]
    north_extra = full_deck[52]
    # Force East hand to have two copies of tile id 5.
    east_hand[0] = Tile(5)
    east_hand[1] = Tile(5)
    players_hands = {
         "north": north_hand + [north_extra],
         "east": east_hand,
         "south": south_hand,
         "west": west_hand
    }
    remaining_deck = full_deck[53:]
    return players_hands, remaining_deck

def get_next_turn(current_turn: str) -> str:
    idx = POSITIONS.index(current_turn)
    return POSITIONS[(idx + 1) % len(POSITIONS)]

def update_hand_counts(room_id: str):
    room_data = rooms[room_id]
    counts = {
        pos: len(room_data["game_state"]["players_hands"].get(pos, []))
        for pos in POSITIONS
    }
    socketio.emit('hand_update', {'hand_counts': counts}, room=room_id)

# --- AI Helpers ---
def schedule_ai_move(room_id: str):
    """If the next turn belongs to a bot, fire off its move in a thread."""
    room_data = rooms[room_id]
    next_pos = room_data["game_state"]["current_turn"]
    # find the username at that position
    next_user = next(u for u, p in room_data["positions"].items() if p == next_pos)
    if next_user in room_data["bots"]:
        Thread(target=handle_ai_turn, args=(room_id, next_user)).start()

def handle_ai_turn(room_id: str, bot_username: str):
    """Bot draws one tile, then discards via ai_discard_tile."""
    sleep(1.5)  # give a slight pause
    
    room_data = rooms[room_id]
    position = room_data["positions"][bot_username]
    deck = room_data["game_state"]["remaining_deck"]
     # Check if the bot can claim a meld
    last_discard = room_data["game_state"].get("last_discard")
    meld_claimed = False
    if last_discard:
          bot_hand = room_data["game_state"]["players_hands"][position]
          can_claim_flag, _ = can_claim_chi(bot_hand, last_discard)
          if can_claim_pong(bot_hand, last_discard):
               on_claim_meld({
                    'room': room_id,
                    'username': bot_username,
                    'meld_type': 'pong'
               })
               meld_claimed = True
          elif can_claim_flag:
               on_claim_meld({
                    'room': room_id,
                    'username': bot_username,
                    'meld_type': 'chi'
               })
               meld_claimed = True
          elif can_claim_kong(bot_hand, last_discard):
               on_claim_meld({
                    'room': room_id,
                    'username': bot_username,
                    'meld_type': 'kong'
               })
               meld_claimed = True
               
    if not deck:
        scores, winner = settle_scores(room_id, None, 0)
        socketio.emit('game_over',{'winner':winner,'score_table':scores,'reason':'draw—no tiles left'},room=room_id)
        return
    
    if deck and not meld_claimed:
        drawn = deck.pop(0)
        room_data["game_state"]["players_hands"][position].append(drawn)
        # update other players' view of hand counts
        update_hand_counts(room_id)
    # now discard
    ai_discard_tile(room_id, bot_username)

def ai_discard_tile(room_id: str, username: str):
    """Heuristic for medium‑level AI: discard tiles least useful for melds."""
    room_data = rooms[room_id]
    position = room_data["positions"][username]
    hand = room_data["game_state"]["players_hands"][position]

    # # 1) find all tiles whose removal DOES NOT break meld potential
    # candidates = []
    # for t in hand:
    #     temp = hand.copy()
    #     temp.remove(t)
    #     if not can_form_sets([tile.id for tile in temp]):
    #         candidates.append(t)

    # # 2) pick one
    
    # tile_to_discard = candidates[0] if candidates else hand[0]

    # 2  Build a score for each tile
    scores = {}
    for t in hand:
        s = 0
        # 1) Pong potential
        copies = sum(1 for x in hand if x.id == t.id) - 1
        s += copies

        # 2) Chow potential (suited only)
        if 0 <= t.id <= 26:
            for neighbor in (t.id - 2, t.id - 1, t.id + 1, t.id + 2):
                if any(x.id == neighbor for x in hand):
                    s += 1

        # 3) Isolation penalty
        if copies == 0 and not (0 <= t.id <= 26 and any(
                abs(x.id - t.id) in (1,2) for x in hand)):
            s -= 1

        scores[t] = s

    # Find the lowest‑scoring tile(s)
    min_score = min(scores.values())
    candidates = [t for t,sc in scores.items() if sc == min_score]

    # Tie-breaker: pick the one with highest ID
    tile_to_discard = max(candidates, key=lambda t: t.id)

    # 3) remove it and broadcast
    hand.remove(tile_to_discard)
    room_data["game_state"]["discard_pile"].append(tile_to_discard)
    room_data["game_state"]["last_discard"] = tile_to_discard

    emit_data = {
        'username': username,
        'tile': {
            'id': tile_to_discard.id,
            'name': tile_to_discard.name,
            'suit': tile_to_discard.suit,
            'image_path': tile_to_discard.image_path
        }
    }
    socketio.emit('tile_discarded', emit_data, room=room_id)

    # advance turn
    next_pos = get_next_turn(position)
    room_data["game_state"]["current_turn"] = next_pos
    socketio.emit('turn_update', {'current_turn': next_pos}, room=room_id)

    # check win
    win, score = check_win_and_score(room_id, username)
    if win:
        new_scores, winner = settle_scores(room_id, username, score)
        socketio.emit('game_over', {
            'winner': winner,
            'score_table': new_scores,
            'reason': 'win'
        }, room=room_id)

    update_hand_counts(room_id)

    # chain into next bot if needed
    schedule_ai_move(room_id)

# --- Flask routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_room', methods=['POST'])
def create_room_route():
    room_id = str(uuid.uuid4())[:8]
    user = request.form.get('username') or "Anonymous"
    rooms[room_id] = {
        "human_players": [user],
        "bots": [],
        "positions": {},
        "sids": {},
        "game_started": False,
        "game_state": {},
        "scores": {}
    }
    return redirect(url_for('game', room_id=room_id) + '?username=' + user)

@app.route('/game/<room_id>')
def game(room_id):
    if room_id not in rooms:
        return "Room does not exist", 404
    return render_template('game.html', room_id=room_id)

# --- SocketIO handlers ---
@socketio.on('join_room')
def on_join(data):
    room = data['room']
    user = data['username']
    if room not in rooms:
        emit('error', {'message': 'Room does not exist.'})
        return

    room_data = rooms[room]
    if len(room_data["human_players"]) >= 4:
        emit('error', {'message': 'Room is full.'})
        return

    # register human
    if user not in room_data["human_players"]:
        room_data["human_players"].append(user)
    room_data["sids"][user] = request.sid
    # assign a position
    idx = len(room_data["positions"])
    room_data["positions"][user] = POSITIONS[idx]

    join_room(room)
    # tell everyone who's in (HUMANS only for now; bots show up at game start)
    emit('player_joined', {
        'username': user,
        'players': room_data["human_players"]
    }, room=room)

@socketio.on('start_game')
def on_start_game(data):
    room = data['room']
    room_data = rooms.get(room)
    if not room_data:
        emit('error', {'message': 'Room does not exist.'})
        return

    humans = room_data["human_players"]
    if len(humans) < 1:
        emit('error', {'message': 'Need at least one human to start.'})
        return

    # fill bots up to 4 total
    needed = 4 - len(humans)
    room_data["bots"] = []
    for i in range(needed):
        bot_name = f"AI_Player_{i+1}"
        room_data["bots"].append(bot_name)
        idx = len(room_data["positions"])
        room_data["positions"][bot_name] = POSITIONS[idx]
        room_data["sids"][bot_name] = None  # no real socket

    # build full participant list
    participants = humans + room_data["bots"]

    if TEST_MODE:
         hands, remaining = create_test_deck()
    else:
          # deal
          deck = create_deck()
          shuffle_deck(deck)
          hands, remaining = deal_tiles(deck)

    room_data["game_started"] = True
    room_data["game_state"] = {
        "players_hands": hands,
        "remaining_deck": remaining,
        "discard_pile": [],
        "current_turn": "north",
        "players_melds": {}
    }
    room_data["scores"] = {p: 2000 for p in participants}

    # send each human their hand
    for p in participants:
        pos = room_data["positions"][p]
        sid = room_data["sids"].get(p)
        if sid:
            socketio.emit('deal_hand', {
                'hand': [{
                    'id': t.id, 'name': t.name,
                    'suit': t.suit, 'image_path': t.image_path
                } for t in hands[pos]],
                'position': pos
            }, room=sid)

    # announce start
    socketio.emit('game_started', {
        'message': 'Game has started!',
        'current_turn': 'north'
    }, room=room)
    
    # tell everyone who's in (HUMANS only for now; bots show up at game start)
    emit('player_joined', {
        'players': room_data["human_players"] + room_data['bots']
    }, room=room)

    
    update_hand_counts(room)
    # if north is a bot, let it play immediately
    if next_u := next((u for u in room_data["bots"]
                       if room_data["positions"][u] == "north"), None):
        schedule_ai_move(room)

@socketio.on('draw_tile')
def on_draw_tile(data):
    room = data['room']
    user = data['username']
    rd = rooms.get(room)
    if not rd:
        emit('error', {'message': 'Room not found.'})
        return

    pos = rd["positions"][user]
    if pos != rd["game_state"]["current_turn"]:
        emit('error', {'message': "It's not your turn."})
        return

    deck = rd["game_state"]["remaining_deck"]
    if not deck:
    #     emit('error', {'message': 'No more tiles to draw.'})
    #     return

    # if not deck:
        # check for win or draw
            win, score = settle_scores(room, user)
            socketio.emit('game_over',{'winner':None,'score_table':rd["scores"],'reason':'draw—no tiles left'},room=rd["room"])
            return
    tile = deck.pop(0)
    rd["game_state"]["players_hands"][pos].append(tile)

    sid = rd["sids"].get(user)
    if sid:
        socketio.emit('tile_drawn', {
            'tile': {
                'id': tile.id, 'name': tile.name,
                'suit': tile.suit,
                'image_path': tile.image_path
            }
        }, room=sid)

    update_hand_counts(room)

    # advance turn
#     rd["game_state"]["current_turn"] = get_next_turn(pos)
#     socketio.emit('turn_update', {
#         'current_turn': rd["game_state"]["current_turn"]
#     }, room=room)

@socketio.on('discard_tile')
def on_discard_tile(data):
    room = data['room']
    user = data['username']
    tile_id = data['tile_id']
    rd = rooms.get(room)
    if not rd:
        emit('error', {'message': 'Room not found.'})
        return

    pos = rd["positions"][user]
    if pos != rd["game_state"]["current_turn"]:
        emit('error', {'message': "It's not your turn."})
        return

    hand = rd["game_state"]["players_hands"][pos]
    tile = next((t for t in hand if t.id == tile_id), None)
    if not tile:
        emit('error', {'message': 'Tile not found in hand.'})
        return

    hand.remove(tile)
    rd["game_state"]["discard_pile"].append(tile)
    rd["game_state"]["last_discard"] = tile

    socketio.emit('tile_discarded', {
        'username': user,
        'tile': {
            'id': tile.id, 'name': tile.name,
            'suit': tile.suit, 'image_path': tile.image_path
        }
    }, room=room)

    # advance turn
    rd["game_state"]["current_turn"] = get_next_turn(pos)
    socketio.emit('turn_update', {
        'current_turn': rd["game_state"]["current_turn"]
    }, room=room)

    update_hand_counts(room)

    # check human win
    win, score = check_win_and_score(room, user)
    if win:
        new_scores = settle_scores(room, user, score)
        socketio.emit('game_over', {
            'winner': user,
            'score_table': new_scores,
            "reason": 'win'
        }, room=room)
        return

    # if next is bot, let it play
    schedule_ai_move(room)

# --- Other event handlers and logic ---
# --- Simplified win–checking functions ---
def can_form_sets(tile_ids):
    # Recursively check if tile_ids can be partitioned into sets (pung/chow).
    if not tile_ids:
         return True
    first = tile_ids[0]
    # Check for pung:
    if tile_ids.count(first) >= 3:
         new_ids = tile_ids.copy()
         for _ in range(3):
              new_ids.remove(first)
         if can_form_sets(new_ids):
              return True
    # Check for chow (only for suited tiles, assume ids 0–26 are suited)
    if first <= 26:
         second, third = first+1, first+2
         if second in tile_ids and third in tile_ids:
              new_ids = tile_ids.copy()
              new_ids.remove(first)
              new_ids.remove(second)
              new_ids.remove(third)
              if can_form_sets(new_ids):
                   return True
    return False

def check_win_and_score(room, username):
    """
    In our simplified win checker, we assume a winning hand is reached if the total tile count (melds plus hand)
    equals 14 and the remaining hand is exactly a pair.
    """
    room_data = rooms[room]
    position = room_data["positions"].get(username)
    melds = room_data["game_state"]["players_melds"].get(position, [])
    hand = room_data["game_state"]["players_hands"].get(position, [])
    total = len(hand)
    for meld in melds:
         if meld['meld_type'] == 'kong':
              total += 4
         else:
              total += 3
    # Simplified: win if total == 14 and the remaining hand is a pair.
    if total == 14 and len(hand) == 2 and hand[0].id == hand[1].id:
         win_details = {'self_drawn': True}  # For demo purposes.
         score = compute_score(hand, melds, win_details)
         return True, score
    return False, 0

def compute_score(hand, melds, win_details):
    """
    A simplified scoring function based on the provided rules.
    (For demonstration, we add points for each meld and a winner bonus.)
    """
    score = 0
    for meld in melds:
         if meld['meld_type'] == 'pong':
              # For simples (assume tile ids 0-8 correspond to bamboo 1–9) add 2 points for non-terminals, 4 for terminals.
              tile_id = meld['tiles'][0]['id']
              if tile_id in [0, 8]:
                   score += 4
              else:
                   score += 2
         elif meld['meld_type'] == 'kong':
              tile_id = meld['tiles'][0]['id']
              if tile_id in [0, 8]:
                   score += 8
              else:
                   score += 4
         # For chi, we assume no direct score.
    # Winner bonus points:
    if win_details.get('self_drawn'):
         score += 2
    else:
         score += 2
    return score



def settle_scores(room, winner=None, win_score=0):
    room_data = rooms[room]
    scores = room_data.get("scores", {})
    if not scores:
        scores = {user: 2000 for user in room_data["positions"].keys()}
        room_data["scores"] = scores

    # Calculate scores based on melds
    player_scores = {}
    for position, melds in room_data["game_state"]["players_melds"].items():
        player_score = 0
        for meld in melds:
            if meld['meld_type'] == 'pong':
                tile_id = meld['tiles'][0]['id']
                player_score += 4 if tile_id in [0, 8] else 2
            elif meld['meld_type'] == 'kong':
                tile_id = meld['tiles'][0]['id']
                player_score += 8 if tile_id in [0, 8] else 4
            elif meld['meld_type'] == 'chi':
                player_score += 1  # Assign 1 point for each chi meld
        player_scores[position] = player_score

    # Determine the winner based on the highest score
    winner_position = max(player_scores, key=player_scores.get)
    winner_score = player_scores[winner_position]
    winner = next(user for user, pos in room_data["positions"].items() if pos == winner_position)

    # Adjust scores: losers pay the winner
    for user, position in room_data["positions"].items():
        if user == winner:
            for loser, loser_position in room_data["positions"].items():
                if loser != winner:
                    if winner_position == "east":
                        scores[winner] += 2 * winner_score
                        scores[loser] -= 2 * winner_score
                    else:
                        scores[winner] += winner_score
                        scores[loser] -= winner_score

    return scores, winner

def settle_scores_old(room, winner, win_score):
    room_data = rooms[room]
    scores = room_data.get("scores", {})
    if not scores:
         scores = {user: 2000 for user in room_data["players"]}
         room_data["scores"] = scores
    for user in room_data["players"]:
         if user == winner:
              for loser in room_data["players"]:
                   if loser != winner:
                        if room_data["positions"][winner] == "east":
                             scores[winner] += 2 * win_score
                             scores[loser] -= 2 * win_score
                        else:
                             scores[winner] += win_score
                             scores[loser] -= win_score
         # Losers pay the winner.
    return scores


@socketio.on('claim_meld')
def on_claim_meld(data):
    room = data['room']
    username = data['username']
    meld_type = data['meld_type']
    room_data = rooms.get(room)
    if not room_data:
         emit('error', {'message': 'Room not found.'})
         return
    position = room_data["positions"].get(username)
    if not position:
         emit('error', {'message': 'Player not found.'})
         return
    last_discard = room_data["game_state"].get("last_discard")
    if not last_discard:
         emit('error', {'message': 'No tile available to claim.'})
         return
    hand = room_data["game_state"]["players_hands"].get(position, [])
    valid = False
    meld_tiles = []
    if meld_type == 'pong':
         if can_claim_pong(hand, last_discard):
              valid = True
              count = 0
              for t in hand[:]:
                   if t.id == last_discard.id and count < 2:
                        meld_tiles.append(t)
                        hand.remove(t)
                        count += 1
    elif meld_type == 'chi':
         can_claim_flag, sequence = can_claim_chi(hand, last_discard)
         if can_claim_flag:
              valid = True
              needed_numbers = [n for n in sequence if n != int(last_discard.name.split()[1])]
              for n in needed_numbers:
                   for t in hand[:]:
                        if t.suit == last_discard.suit and int(t.name.split()[1]) == n:
                             meld_tiles.append(t)
                             hand.remove(t)
                             break
    elif meld_type == 'kong':
         if can_claim_kong(hand, last_discard):
              valid = True
              count = 0
              for t in hand[:]:
                   if t.id == last_discard.id and count < 3:
                        meld_tiles.append(t)
                        hand.remove(t)
                        count += 1
    else:
         emit('error', {'message': 'Invalid meld type.'})
         return
    if not valid:
         emit('error', {'message': f"Cannot claim {meld_type} with the last discarded tile."})
         return
    if room_data["game_state"]["discard_pile"]:
         room_data["game_state"]["discard_pile"].pop()
    meld_info = {
         'meld_type': meld_type,
         'tiles': [{
              'id': last_discard.id,
              'name': last_discard.name,
              'suit': last_discard.suit,
              'image_path': last_discard.image_path
         }] + [{
              'id': t.id,
              'name': t.name,
              'suit': t.suit,
              'image_path': t.image_path
         } for t in meld_tiles],
         'claimed_by': username
    }
    if "players_melds" not in room_data["game_state"]:
         room_data["game_state"]["players_melds"] = {}
    if position not in room_data["game_state"]["players_melds"]:
         room_data["game_state"]["players_melds"][position] = []
    room_data["game_state"]["players_melds"][position].append(meld_info)
    room_data["game_state"]["current_turn"] = position
    socketio.emit('meld_claimed', meld_info, room=room)
    # socketio.emit('turn_update', {'current_turn': position}, room=room)
    update_hand_counts(room)
    socketio.emit('meld_update', {'players_melds': room_data["game_state"]["players_melds"]}, room=room)
    
    # NEW: Send updated hand to the claiming player
    updated_hand = room_data["game_state"]["players_hands"][position]
    sid = room_data["sids"].get(username)
    if sid:
         hand_data = [{
              'id': tile.id,
              'name': tile.name,
              'suit': tile.suit,
              'image_path': tile.image_path
         } for tile in updated_hand]
         socketio.emit('update_hand', {'hand': hand_data}, room=sid)
    
    
    win, score = check_win_and_score(room, username)
    if win:
         new_scores = settle_scores(room, username, score)
         socketio.emit('game_over', {'winner': username, "reason": "win", 'score_table': new_scores}, room=room)

@socketio.on('check_meld')
def on_check_meld(data):
    room = data['room']
    username = data['username']
    room_data = rooms.get(room)
    if not room_data:
         emit('error', {'message': 'Room not found.'})
         return
    position = room_data["positions"].get(username)
    if not position:
         emit('error', {'message': 'Player not found.'})
         return
    last_discard = room_data["game_state"].get("last_discard")
    if not last_discard:
         emit('meld_options', {'options': []}, room=request.sid)
         return
    hand = room_data["game_state"]["players_hands"].get(position, [])
    options = []
    if can_claim_pong(hand, last_discard):
         options.append('pong')
    can_claim_flag, _ = can_claim_chi(hand, last_discard)
    if can_claim_flag:
         options.append('chi')
    if can_claim_kong(hand, last_discard):
         options.append('kong')
    emit('meld_options', {'options': options}, room=request.sid)

@socketio.on('chat_message')
def on_chat_message(data):
    room = data['room']
    username = data['username']
    message = data['message']
    socketio.emit('chat_message', {'username': username, 'message': message}, room=room)




@socketio.on('connect')
def on_connect():
     emit('connection_success', {'message': 'Connected successfully!'}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, port=5000, debug=True)
