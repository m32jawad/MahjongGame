import random
import math
import logging
from typing import List, Dict, Tuple, Optional
from collections import OrderedDict
from game_logic.mahjong import Tile, can_claim_pong, can_claim_chi, can_claim_kong

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCTSNode:
    def __init__(self, state: Dict, parent=None, action=None):
        """
        Initialize a node in the MCTS tree.
        
        Args:
            state: Current game state
            parent: Parent node
            action: Action that led to this state
        """
        self.state = state
        self.parent = parent
        self.action = action
        self.children: List[MCTSNode] = []
        self.visits = 0
        self.value = 0
        self.untried_actions = []

    def ucb1(self, exploration_weight=1.41) -> float:
        """Calculate UCB1 value for this node."""
        if self.visits == 0:
            return float('inf')
        exploitation = self.value / self.visits
        exploration = exploration_weight * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration

    def select_child(self) -> 'MCTSNode':
        """Select child node with highest UCB1 value."""
        return max(self.children, key=lambda c: c.ucb1())

    def add_child(self, action: Tuple[str, Tile], state: Dict) -> 'MCTSNode':
        """Add a new child node."""
        child = MCTSNode(state, parent=self, action=action)
        self.untried_actions.remove(action)
        self.children.append(child)
        return child

    def update(self, value: float):
        """Update node statistics."""
        self.visits += 1
        self.value += value

class MCTS:
    def __init__(self, max_iterations=1000, exploration_weight=1.41, cache_size=1000):
        """
        Initialize MCTS with configuration parameters.
        
        Args:
            max_iterations: Maximum number of MCTS iterations
            exploration_weight: Weight for exploration in UCB1 formula
            cache_size: Maximum size of state evaluation cache
        """
        self.max_iterations = max_iterations
        self.exploration_weight = exploration_weight
        self.cache = OrderedDict()
        self.cache_size = cache_size
        logger.info(f"Initialized MCTS with {max_iterations} iterations")

    def _get_available_actions(self, state: Dict) -> List[Tuple[str, Tile]]:
        """Get all possible actions from this state."""
        try:
            actions = []
            hand = state["current_hand"]
            
            # Add discard actions for each tile in hand
            for tile in hand:
                actions.append(("discard", tile))
                
            # Add meld claim actions if applicable
            last_discard = state.get("last_discard")
            if last_discard:
                if can_claim_pong(hand, last_discard):
                    actions.append(("pong", last_discard))
                if can_claim_chi(hand, last_discard):
                    actions.append(("chi", last_discard))
                if can_claim_kong(hand, last_discard):
                    actions.append(("kong", last_discard))
                    
            return actions
        except Exception as e:
            logger.error(f"Error getting available actions: {str(e)}")
            return []

    def _get_cached_evaluation(self, state: Dict) -> Optional[float]:
        """Get cached evaluation for a state if available."""
        state_key = str(sorted([(t.id, t.suit) for t in state["current_hand"]]))
        return self.cache.get(state_key)

    def _cache_evaluation(self, state: Dict, value: float):
        """Cache state evaluation."""
        state_key = str(sorted([(t.id, t.suit) for t in state["current_hand"]]))
        if len(self.cache) >= self.cache_size:
            self.cache.popitem(last=False)  # Remove oldest item
        self.cache[state_key] = value

    def _simulate_random_playout(self, state: Dict) -> float:
        """Simulate a random playout from the given state."""
        try:
            current_state = state.copy()
            while not self._is_terminal_state(current_state):
                actions = self._get_available_actions(current_state)
                if not actions:
                    break
                action = random.choice(actions)
                current_state = self._apply_action(current_state, action)
            return self._evaluate_state(current_state)
        except Exception as e:
            logger.error(f"Error in random playout: {str(e)}")
            return 0.0

    def _is_terminal_state(self, state: Dict) -> bool:
        """Check if the state is terminal (game over)."""
        return len(state["current_hand"]) == 0

    def _evaluate_state(self, state: Dict) -> float:
        """Evaluate the state and return a score between -1 and 1."""
        # Check cache first
        cached_value = self._get_cached_evaluation(state)
        if cached_value is not None:
            return cached_value

        try:
            hand = state["current_hand"]
            score = 0
            
            # Count potential melds
            for tile in hand:
                # Check for pong potential
                copies = sum(1 for t in hand if t.id == tile.id)
                score += copies * 0.2
                
                # Check for chi potential
                if 0 <= tile.id <= 26:  # Suited tiles
                    for neighbor in (tile.id - 2, tile.id - 1, tile.id + 1, tile.id + 2):
                        if any(t.id == neighbor for t in hand):
                            score += 0.1
            
            # Normalize score to [-1, 1]
            final_score = max(-1, min(1, score / 10))
            
            # Cache the result
            self._cache_evaluation(state, final_score)
            
            return final_score
        except Exception as e:
            logger.error(f"Error evaluating state: {str(e)}")
            return 0.0

    def _apply_action(self, state: Dict, action: Tuple[str, Tile]) -> Dict:
        """Apply an action to the state and return the new state."""
        try:
            new_state = state.copy()
            action_type, tile = action
            
            if action_type == "discard":
                # Find and remove the tile from hand
                for i, t in enumerate(new_state["current_hand"]):
                    if t.id == tile.id and t.suit == tile.suit:
                        new_state["current_hand"].pop(i)
                        break
                new_state["discard_pile"].append(tile)
            elif action_type in ["pong", "chi", "kong"]:
                # Handle meld claims
                # Find and remove the tile from hand
                for i, t in enumerate(new_state["current_hand"]):
                    if t.id == tile.id and t.suit == tile.suit:
                        new_state["current_hand"].pop(i)
                        break
                if action_type not in new_state["melds"]:
                    new_state["melds"][action_type] = []
                new_state["melds"][action_type].append(tile)
                
            return new_state
        except Exception as e:
            logger.error(f"Error applying action: {str(e)}")
            return state

    def _fallback_heuristic(self, state: Dict) -> Tuple[str, Tile]:
        """Fallback to simple heuristic if MCTS fails."""
        try:
            hand = state["current_hand"]
            if not hand:
                raise ValueError("No tiles in hand")
                
            # Simple heuristic: discard the tile with lowest potential
            scores = {}
            for tile in hand:
                score = 0
                # Count copies
                copies = sum(1 for t in hand if t.id == tile.id)
                score += copies
                
                # Check for chi potential
                if 0 <= tile.id <= 26:
                    for neighbor in (tile.id - 2, tile.id - 1, tile.id + 1, tile.id + 2):
                        if any(t.id == neighbor for t in hand):
                            score += 1
                            
                scores[tile] = score
                
            if not scores:
                # If no scores calculated, just pick the first tile
                return ("discard", hand[0])
                
            worst_tile = min(scores.items(), key=lambda x: x[1])[0]
            return ("discard", worst_tile)
            
        except Exception as e:
            logger.error(f"Fallback heuristic failed: {str(e)}")
            # Last resort: just pick the first tile
            return ("discard", state["current_hand"][0])

    def get_best_action(self, state: Dict) -> Tuple[str, Tile]:
        """Find the best action using MCTS."""
        logger.info(f"Starting MCTS with {self.max_iterations} iterations")
        
        if not state["current_hand"]:
            raise ValueError("No tiles in hand")
        
        try:
            root = MCTSNode(state)
            root.untried_actions = self._get_available_actions(state)
            
            if not root.untried_actions:
                logger.warning("No available actions, using fallback heuristic")
                return self._fallback_heuristic(state)
            
            for i in range(self.max_iterations):
                node = root
                
                # Selection
                while node.untried_actions == [] and node.children != []:
                    node = node.select_child()
                
                # Expansion
                if node.untried_actions:
                    action = random.choice(node.untried_actions)
                    new_state = self._apply_action(node.state, action)
                    node = node.add_child(action, new_state)
                
                # Simulation
                value = self._simulate_random_playout(node.state)
                
                # Backpropagation
                while node is not None:
                    node.update(value)
                    node = node.parent
                    value = -value  # Negamax style
                
                if i % 100 == 0:
                    logger.debug(f"Completed {i} iterations")
            
            if not root.children:
                logger.warning("No children nodes after MCTS, using fallback heuristic")
                return self._fallback_heuristic(state)
                
            # Return the action from the most visited child
            best_child = max(root.children, key=lambda c: c.visits)
            logger.info(f"Selected action {best_child.action} with {best_child.visits} visits")
            return best_child.action
            
        except Exception as e:
            logger.error(f"MCTS failed: {str(e)}")
            return self._fallback_heuristic(state) 