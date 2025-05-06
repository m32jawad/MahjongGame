from typing import List, Dict, Any, Tuple
from .mcts import MCTS, MCTSConfig
from .mahjong import Tile, can_claim_pong, can_claim_chi, can_claim_kong
import random
import copy

class MahjongMCTS:
    """Mahjong-specific MCTS implementation"""
    def __init__(self, config: MCTSConfig = None):
        self.config = config or MCTSConfig()
        self.mcts = MCTS(self.config)

    def get_best_action(self, room_data: Dict[str, Any], username: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Get the best action for the current game state using MCTS
        
        Args:
            room_data: Current game state from rooms[room_id]
            username: Username of the AI player
            
        Returns:
            Tuple of (best_action, stats)
        """
        position = room_data["positions"][username]
        state = self._create_state_representation(room_data, position)
        
        return self.mcts.get_best_action(
            state=state,
            get_legal_moves=self._get_legal_moves,
            apply_move=self._apply_move,
            simulate=self._simulate
        )

    def _create_state_representation(self, room_data: Dict[str, Any], position: str) -> Dict[str, Any]:
        """Create a simplified state representation for MCTS"""
        return {
            'hand': copy.deepcopy(room_data["game_state"]["players_hands"][position]),
            'last_discard': copy.deepcopy(room_data["game_state"].get("last_discard")),
            'remaining_deck': copy.deepcopy(room_data["game_state"]["remaining_deck"]),
            'position': position,
            'melds': copy.deepcopy(room_data["game_state"]["players_melds"].get(position, []))
        }

    def _get_legal_moves(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all legal moves from the current state"""
        moves = []
        hand = state['hand']
        last_discard = state['last_discard']
        
        # Add discard moves
        for tile in hand:
            moves.append({
                'type': 'discard',
                'tile': copy.deepcopy(tile)
            })
        
        # Add meld claims if there's a last discard
        if last_discard:
            if can_claim_pong(hand, last_discard):
                moves.append({
                    'type': 'pong',
                    'tile': copy.deepcopy(last_discard)
                })
            
            can_chi, _ = can_claim_chi(hand, last_discard)
            if can_chi:
                moves.append({
                    'type': 'chi',
                    'tile': copy.deepcopy(last_discard)
                })
            
            if can_claim_kong(hand, last_discard):
                moves.append({
                    'type': 'kong',
                    'tile': copy.deepcopy(last_discard)
                })
        
        return moves

    def _apply_move(self, state: Dict[str, Any], move: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a move to the state and return new state"""
        new_state = copy.deepcopy(state)
        hand = new_state['hand']
        
        if move['type'] == 'discard':
            # Find and remove the tile by ID
            tile_id = move['tile'].id
            tile_to_remove = next((t for t in hand if t.id == tile_id), None)
            if tile_to_remove:
                hand.remove(tile_to_remove)
                new_state['last_discard'] = copy.deepcopy(tile_to_remove)
        elif move['type'] in ['pong', 'chi', 'kong']:
            # Remove tiles used in meld
            meld_tiles = self._get_meld_tiles(hand, move)
            for tile in meld_tiles:
                hand.remove(tile)
            
            # Remove the last discard tile
            if move['tile'] in hand:
                hand.remove(move['tile'])
            
            # Add meld to melds list
            if 'melds' not in new_state:
                new_state['melds'] = []
            new_state['melds'].append({
                'type': move['type'],
                'tiles': meld_tiles + [move['tile']]
            })
        
        new_state['hand'] = hand
        return new_state

    def _get_meld_tiles(self, hand: List[Tile], move: Dict[str, Any]) -> List[Tile]:
        """Get tiles needed for a meld"""
        if move['type'] == 'pong':
            return [t for t in hand if t.id == move['tile'].id][:2]
        elif move['type'] == 'kong':
            return [t for t in hand if t.id == move['tile'].id][:3]
        elif move['type'] == 'chi':
            # Simplified chi implementation - would need more logic for proper sequence
            return [t for t in hand if t.suit == move['tile'].suit][:2]
        return []

    def _simulate(self, state: Dict[str, Any]) -> float:
        """
        Simulate a random game from the current state and return reward
        Returns a value between -1 and 1
        """
        # Simplified simulation - could be made more sophisticated
        current_state = copy.deepcopy(state)
        depth = 0
        max_depth = 10  # Limit simulation depth
        
        while depth < max_depth:
            moves = self._get_legal_moves(current_state)
            if not moves:
                break
                
            # Random move selection
            move = random.choice(moves)
            try:
                current_state = self._apply_move(current_state, move)
            except ValueError:
                # If we encounter an error (e.g., tile not found), end simulation
                break
            depth += 1
        
        # Simple reward function based on hand size and melds
        hand_size = len(current_state['hand'])
        num_melds = len(current_state.get('melds', []))
        
        # Normalize reward between -1 and 1
        reward = (num_melds * 0.3) - (hand_size * 0.1)
        return max(-1, min(1, reward)) 