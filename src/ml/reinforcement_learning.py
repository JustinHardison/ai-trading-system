"""
Reinforcement Learning Agent for Adaptive Trading
Learns optimal entry/exit strategies from experience
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import deque
import pickle
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradingRLAgent:
    """
    Q-Learning agent for adaptive trading decisions
    
    State: Market conditions (volatility, trend, time-of-day, etc.)
    Actions: HOLD, BUY, SELL
    Reward: Risk-adjusted returns
    
    The agent learns which actions work best in different market states
    """
    
    def __init__(
        self,
        state_size: int = 20,
        action_size: int = 3,
        learning_rate: float = 0.001,
        gamma: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01
    ):
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        self.gamma = gamma  # Discount factor
        self.epsilon = epsilon  # Exploration rate
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Q-table: state -> action values
        self.q_table = {}
        
        # Experience replay
        self.memory = deque(maxlen=10000)
        
        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0.0
        
        logger.info(f"RL Agent initialized: state_size={state_size}, actions={action_size}")
    
    def get_state_key(self, state: np.ndarray) -> str:
        """Convert continuous state to discrete key for Q-table"""
        # Discretize state into bins
        discretized = []
        for val in state:
            if val < -1:
                bin_val = 0
            elif val < -0.5:
                bin_val = 1
            elif val < 0:
                bin_val = 2
            elif val < 0.5:
                bin_val = 3
            elif val < 1:
                bin_val = 4
            else:
                bin_val = 5
            discretized.append(bin_val)
        
        return ','.join(map(str, discretized))
    
    def get_action(self, state: np.ndarray, training: bool = True) -> int:
        """
        Choose action using epsilon-greedy policy
        
        Args:
            state: Current market state
            training: If True, use exploration; if False, use exploitation only
            
        Returns:
            Action (0=HOLD, 1=BUY, 2=SELL)
        """
        state_key = self.get_state_key(state)
        
        # Initialize Q-values for new states
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(self.action_size)
        
        # Epsilon-greedy: explore vs exploit
        if training and np.random.random() < self.epsilon:
            # Explore: random action
            return np.random.randint(self.action_size)
        else:
            # Exploit: best known action
            return np.argmax(self.q_table[state_key])
    
    def remember(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Store experience in replay memory"""
        self.memory.append((state, action, reward, next_state, done))
    
    def learn(self, batch_size: int = 32):
        """
        Learn from experience replay
        
        Updates Q-values based on Bellman equation:
        Q(s,a) = Q(s,a) + α * (reward + γ * max(Q(s',a')) - Q(s,a))
        """
        if len(self.memory) < batch_size:
            return
        
        # Sample random batch
        indices = np.random.choice(len(self.memory), batch_size, replace=False)
        batch = [self.memory[i] for i in indices]
        
        for state, action, reward, next_state, done in batch:
            state_key = self.get_state_key(state)
            next_state_key = self.get_state_key(next_state)
            
            # Initialize if needed
            if state_key not in self.q_table:
                self.q_table[state_key] = np.zeros(self.action_size)
            if next_state_key not in self.q_table:
                self.q_table[next_state_key] = np.zeros(self.action_size)
            
            # Q-learning update
            current_q = self.q_table[state_key][action]
            
            if done:
                target_q = reward
            else:
                target_q = reward + self.gamma * np.max(self.q_table[next_state_key])
            
            # Update Q-value
            self.q_table[state_key][action] = current_q + self.learning_rate * (target_q - current_q)
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
    
    def calculate_reward(
        self,
        profit_pct: float,
        bars_held: int,
        volatility: float,
        max_drawdown: float = 0.0
    ) -> float:
        """
        Calculate reward for a trade
        
        Reward function considers:
        - Profit/loss (primary)
        - Time efficiency (faster is better)
        - Risk-adjusted returns
        - Drawdown penalty
        
        Args:
            profit_pct: Profit percentage
            bars_held: Number of bars position was held
            volatility: Market volatility during trade
            max_drawdown: Maximum drawdown during trade
            
        Returns:
            Reward value
        """
        # Base reward: profit/loss
        reward = profit_pct * 10  # Scale up
        
        # Time penalty: holding too long is bad
        if bars_held > 20:
            reward -= (bars_held - 20) * 0.1
        
        # Risk adjustment: penalize high volatility losses
        if profit_pct < 0:
            reward -= volatility * abs(profit_pct) * 5
        
        # Drawdown penalty
        if max_drawdown > 0.5:  # More than 0.5% drawdown
            reward -= max_drawdown * 10
        
        # Bonus for quick profitable trades
        if profit_pct > 0.2 and bars_held < 10:
            reward += 2.0
        
        return reward
    
    def update_stats(self, profit_pct: float):
        """Update performance statistics"""
        self.total_trades += 1
        if profit_pct > 0:
            self.winning_trades += 1
        self.total_profit += profit_pct
    
    def get_stats(self) -> Dict:
        """Get performance statistics"""
        win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        avg_profit = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_profit': self.total_profit,
            'avg_profit_per_trade': avg_profit,
            'epsilon': self.epsilon,
            'q_table_size': len(self.q_table)
        }
    
    def save(self, filepath: str):
        """Save agent to file"""
        data = {
            'q_table': self.q_table,
            'epsilon': self.epsilon,
            'stats': self.get_stats(),
            'config': {
                'state_size': self.state_size,
                'action_size': self.action_size,
                'learning_rate': self.learning_rate,
                'gamma': self.gamma
            }
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"RL Agent saved to {filepath}")
    
    def load(self, filepath: str):
        """Load agent from file"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.q_table = data['q_table']
        self.epsilon = data['epsilon']
        
        stats = data['stats']
        self.total_trades = stats['total_trades']
        self.winning_trades = stats['winning_trades']
        self.total_profit = stats['total_profit']
        
        logger.info(f"RL Agent loaded from {filepath}")
        logger.info(f"Stats: {stats}")


class StateEncoder:
    """
    Encodes market conditions into RL state representation
    
    State features (20 dimensions):
    1. Price momentum (short/medium/long)
    2. Volatility regime
    3. Volume profile
    4. Time of day
    5. Trend strength
    6. Support/resistance proximity
    """
    
    @staticmethod
    def encode_state(features: Dict) -> np.ndarray:
        """
        Convert market features to RL state vector
        
        Args:
            features: Dictionary of market features
            
        Returns:
            State vector (20 dimensions)
        """
        state = []
        
        # 1-3: Price momentum (normalized)
        state.append(features.get('roc_1', 0) * 100)
        state.append(features.get('roc_5', 0) * 100)
        state.append(features.get('roc_10', 0) * 100)
        
        # 4-5: Volatility
        state.append(features.get('atr_pct', 0))
        state.append(features.get('hvol_ratio', 1.0) - 1.0)
        
        # 6-7: Volume
        state.append(features.get('vol_ratio_5', 1.0) - 1.0)
        state.append(features.get('volume_imbalance', 0))
        
        # 8-11: Time features
        state.append(features.get('hour_sin', 0))
        state.append(features.get('hour_cos', 0))
        state.append(features.get('ny_session', 0))
        state.append(features.get('ny_open_hour', 0))
        
        # 12-14: Trend
        state.append(features.get('price_vs_sma20', 0))
        state.append(features.get('trend_strength', 0))
        state.append(features.get('macd_histogram', 0))
        
        # 15-16: Support/Resistance
        state.append(features.get('dist_to_resistance', 0))
        state.append(features.get('dist_to_support', 0))
        
        # 17-18: RSI and Stochastic
        state.append((features.get('rsi_14', 50) - 50) / 50)  # Normalize to -1 to 1
        state.append((features.get('stoch_k', 50) - 50) / 50)
        
        # 19-20: Order flow
        state.append(features.get('delta_volume', 0) / 1000)
        state.append(features.get('cumulative_delta', 0))
        
        return np.array(state[:20])  # Ensure exactly 20 dimensions
