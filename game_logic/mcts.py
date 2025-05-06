import math
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time

@dataclass
class MCTSConfig:
    """Configuration for MCTS algorithm"""
    num_simulations: int = 1000
    max_time_per_move: float = 1.0  # seconds
    exploration_constant: float = 1.41  # UCB1 exploration parameter
    random_seed: Optional[int] = None

class MCTSNode:
    """Node in the MCTS tree"""
    def __init__(self, state: Dict[str, Any], parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action  # Action that led to this state
        self.children: List[MCTSNode] = []
        self.visits = 0
        self.value = 0.0
        self.untried_actions = []  # Will be populated with legal actions

    def ucb1(self, exploration_constant: float) -> float:
        """Calculate UCB1 value for this node"""
        if self.visits == 0:
            return float('inf')
        exploitation = self.value / self.visits
        exploration = exploration_constant * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration

    def best_child(self, exploration_constant: float) -> 'MCTSNode':
        """Select best child using UCB1"""
        return max(self.children, key=lambda c: c.ucb1(exploration_constant))

    def rollout_policy(self) -> Any:
        """Select random action from untried actions"""
        return random.choice(self.untried_actions)

class MCTS:
    """Monte Carlo Tree Search implementation"""
    def __init__(self, config: MCTSConfig):
        self.config = config
        if config.random_seed is not None:
            random.seed(config.random_seed)

    def get_best_action(self, state: Dict[str, Any], 
                       get_legal_moves: callable,
                       apply_move: callable,
                       simulate: callable) -> Tuple[Any, Dict[str, Any]]:
        """
        Find the best action using MCTS
        
        Args:
            state: Current game state
            get_legal_moves: Function that returns list of legal moves from a state
            apply_move: Function that applies a move to a state and returns new state
            simulate: Function that simulates from a state and returns reward
            
        Returns:
            Tuple of (best_action, stats)
        """
        root = MCTSNode(state)
        root.untried_actions = get_legal_moves(state)
        
        start_time = time.time()
        simulations = 0
        
        while (simulations < self.config.num_simulations and 
               time.time() - start_time < self.config.max_time_per_move):
            
            # Selection
            node = self._select(root)
            
            # Expansion
            if node.untried_actions:
                node = self._expand(node, get_legal_moves, apply_move)
            
            # Simulation
            reward = simulate(node.state)
            
            # Backpropagation
            self._backpropagate(node, reward)
            
            simulations += 1
        
        # Select best action based on most visits
        best_child = max(root.children, key=lambda c: c.visits)
        
        stats = {
            'simulations': simulations,
            'time_taken': time.time() - start_time,
            'root_visits': root.visits,
            'best_child_visits': best_child.visits,
            'best_child_value': best_child.value / best_child.visits if best_child.visits > 0 else 0
        }
        
        return best_child.action, stats

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Selection phase - traverse tree using UCB1 until leaf node"""
        while not node.untried_actions and node.children:
            node = node.best_child(self.config.exploration_constant)
        return node

    def _expand(self, node: MCTSNode, 
                get_legal_moves: callable,
                apply_move: callable) -> MCTSNode:
        """Expansion phase - create new child node"""
        action = node.rollout_policy()
        node.untried_actions.remove(action)
        
        new_state = apply_move(node.state, action)
        child = MCTSNode(new_state, parent=node, action=action)
        child.untried_actions = get_legal_moves(new_state)
        
        node.children.append(child)
        return child

    def _backpropagate(self, node: MCTSNode, reward: float):
        """Backpropagation phase - update node statistics"""
        while node is not None:
            node.visits += 1
            node.value += reward
            node = node.parent 