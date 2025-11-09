"""
Reinforcement Learning Agent for US30 Trading
Learns optimal trading strategy through experience

Uses simplified Q-learning / DQN approach:
- State: Market features + position state
- Actions: BUY, SELL, HOLD, CLOSE
- Reward: Risk-adjusted P&L
- Updates policy based on realized outcomes
"""
import numpy as np
import pandas as pd
from collections import deque
from typing import Dict, List, Tuple, Optional
import pickle
from pathlib import Path
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RLTradingAgent:
    """
    Reinforcement Learning agent that learns from trading outcomes

    Core idea: Start with ML predictions, but adjust based on actual P&L
    - Good predictions that lead to profit → increase confidence
    - Bad predictions that lead to loss → decrease confidence
    - Learn which market conditions lead to best results
    """

    def __init__(
        self,
        learning_rate: float = 0.01,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.1,
        memory_size: int = 1000
    ):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate

        # Experience replay memory
        self.memory = deque(maxlen=memory_size)

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_profit = 0.0

        # Learned adjustments for different market conditions
        self.regime_adjustments = {}

        # Trade history for learning
        self.trade_history = []

    def record_experience(
        self,
        state: Dict[str, float],
        action: str,
        reward: float,
        next_state: Dict[str, float],
        done: bool
    ):
        """
        Record trading experience for learning

        Args:
            state: Market state when decision was made
            action: Action taken (BUY/SELL/HOLD/CLOSE)
            reward: Reward received (profit/loss)
            next_state: Market state after action
            done: Whether trade is closed
        """
        experience = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'done': done,
            'timestamp': datetime.now()
        }

        self.memory.append(experience)

        # Update statistics if trade completed
        if done and action in ['CLOSE', 'STOP_LOSS', 'TAKE_PROFIT']:
            self.total_trades += 1
            if reward > 0:
                self.winning_trades += 1
            self.total_profit += reward

            logger.info(
                f"RL Experience: {action} | "
                f"Reward: ${reward:.2f} | "
                f"Win Rate: {self.get_win_rate():.1f}%"
            )

    def learn_from_experience(self, batch_size: int = 32):
        """
        Learn from past experiences using experience replay

        This is where the agent improves its strategy
        """
        if len(self.memory) < batch_size:
            return

        # Sample random batch from memory
        indices = np.random.choice(len(self.memory), batch_size, replace=False)
        batch = [self.memory[i] for i in indices]

        # Learn from each experience
        for exp in batch:
            self._update_from_experience(exp)

        logger.info(f"RL Learning: Processed {batch_size} experiences")

    def _update_from_experience(self, exp: Dict):
        """
        Update agent's knowledge from single experience

        Key insights to learn:
        1. Which features predict profitable trades?
        2. Which market regimes are most profitable?
        3. What confidence thresholds work best?
        4. When to exit for maximum profit?
        """
        state = exp['state']
        action = exp['action']
        reward = exp['reward']

        # Extract key state features
        regime = state.get('regime', 'unknown')
        confidence = state.get('ml_confidence', 0)
        volatility = state.get('volatility', 0.5)

        # Create regime key
        regime_key = f"{regime}_{int(volatility*10)}"

        # Initialize regime tracking
        if regime_key not in self.regime_adjustments:
            self.regime_adjustments[regime_key] = {
                'total_trades': 0,
                'winning_trades': 0,
                'total_profit': 0.0,
                'avg_reward': 0.0,
                'confidence_adjustment': 0.0
            }

        regime_stats = self.regime_adjustments[regime_key]

        # Update regime statistics
        regime_stats['total_trades'] += 1
        regime_stats['total_profit'] += reward

        if reward > 0:
            regime_stats['winning_trades'] += 1

        # Calculate average reward
        regime_stats['avg_reward'] = (
            regime_stats['total_profit'] / regime_stats['total_trades']
        )

        # Adjust confidence threshold based on performance
        # If regime is profitable → lower confidence threshold (trade more)
        # If regime is unprofitable → raise confidence threshold (trade less)
        win_rate = regime_stats['winning_trades'] / regime_stats['total_trades']

        if win_rate > 0.6 and regime_stats['avg_reward'] > 0:
            # Good regime: lower threshold (trade more aggressively)
            regime_stats['confidence_adjustment'] = max(
                regime_stats['confidence_adjustment'] - self.learning_rate,
                -10.0  # Max 10 point reduction
            )
        elif win_rate < 0.4 or regime_stats['avg_reward'] < 0:
            # Bad regime: raise threshold (trade more cautiously)
            regime_stats['confidence_adjustment'] = min(
                regime_stats['confidence_adjustment'] + self.learning_rate,
                15.0  # Max 15 point increase
            )

    def get_adjusted_confidence_threshold(
        self,
        base_threshold: float,
        regime: str,
        volatility: float
    ) -> float:
        """
        Get RL-adjusted confidence threshold for current market regime

        Args:
            base_threshold: Base confidence threshold (e.g., 75)
            regime: Current market regime
            volatility: Current volatility level

        Returns:
            Adjusted confidence threshold
        """
        regime_key = f"{regime}_{int(volatility*10)}"

        if regime_key in self.regime_adjustments:
            adjustment = self.regime_adjustments[regime_key]['confidence_adjustment']
            adjusted = base_threshold + adjustment

            logger.info(
                f"RL Adjustment: {base_threshold} → {adjusted:.1f} "
                f"(regime: {regime_key}, adj: {adjustment:+.1f})"
            )

            return adjusted

        return base_threshold

    def should_take_action(
        self,
        ml_confidence: float,
        regime: str,
        volatility: float,
        base_threshold: float = 75.0
    ) -> bool:
        """
        Decide if ML prediction should be acted upon

        Combines ML confidence with RL-learned adjustments

        Args:
            ml_confidence: ML model's confidence (0-100)
            regime: Current market regime
            volatility: Current volatility
            base_threshold: Base confidence threshold

        Returns:
            True if should trade, False otherwise
        """
        # Get RL-adjusted threshold
        adjusted_threshold = self.get_adjusted_confidence_threshold(
            base_threshold=base_threshold,
            regime=regime,
            volatility=volatility
        )

        # Exploration: Sometimes take random actions to discover new strategies
        if np.random.random() < self.exploration_rate:
            logger.info("RL Exploration: Random action")
            return np.random.random() > 0.5

        # Exploitation: Use learned knowledge
        should_trade = ml_confidence >= adjusted_threshold

        logger.info(
            f"RL Decision: ML={ml_confidence:.1f} vs Threshold={adjusted_threshold:.1f} → "
            f"{'TRADE' if should_trade else 'SKIP'}"
        )

        return should_trade

    def get_position_size_multiplier(self, regime: str, volatility: float) -> float:
        """
        Get RL-learned position size multiplier for current regime

        Returns value between 0.5 and 1.5
        """
        regime_key = f"{regime}_{int(volatility*10)}"

        if regime_key in self.regime_adjustments:
            stats = self.regime_adjustments[regime_key]

            # If regime is very profitable, increase size
            if stats['avg_reward'] > 50 and stats['total_trades'] >= 10:
                return 1.3

            # If regime is unprofitable, decrease size
            if stats['avg_reward'] < -20:
                return 0.6

        return 1.0  # Default: no adjustment

    def get_win_rate(self) -> float:
        """Get overall win rate"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    def get_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio from trade history

        Sharpe = (mean return) / (std of returns)
        Higher is better (>1.0 is good)
        """
        if len(self.memory) < 10:
            return 0.0

        returns = [exp['reward'] for exp in self.memory if exp['done']]

        if len(returns) < 2:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        return mean_return / std_return

    def get_regime_performance(self) -> Dict[str, Dict]:
        """Get performance statistics for each regime"""
        return self.regime_adjustments.copy()

    def save(self, filepath: str):
        """Save RL agent state"""
        try:
            data = {
                'learning_rate': self.learning_rate,
                'discount_factor': self.discount_factor,
                'exploration_rate': self.exploration_rate,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'total_profit': self.total_profit,
                'regime_adjustments': self.regime_adjustments,
                'trade_history': list(self.memory)[-100:],  # Save last 100
                'timestamp': datetime.now().isoformat()
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f)

            logger.info(f"RL Agent saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving RL agent: {e}")

    @classmethod
    def load(cls, filepath: str) -> 'RLTradingAgent':
        """Load RL agent from file"""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            agent = cls(
                learning_rate=data['learning_rate'],
                discount_factor=data['discount_factor'],
                exploration_rate=data['exploration_rate']
            )

            agent.total_trades = data['total_trades']
            agent.winning_trades = data['winning_trades']
            agent.total_profit = data['total_profit']
            agent.regime_adjustments = data['regime_adjustments']
            agent.memory = deque(data['trade_history'], maxlen=1000)

            logger.info(f"RL Agent loaded from {filepath}")
            logger.info(f"Win Rate: {agent.get_win_rate():.1f}% | Total Profit: ${agent.total_profit:.2f}")

            return agent

        except Exception as e:
            logger.error(f"Error loading RL agent: {e}")
            return cls()  # Return fresh agent

    def get_statistics(self) -> Dict:
        """Get comprehensive RL agent statistics"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.total_trades - self.winning_trades,
            'win_rate': self.get_win_rate(),
            'total_profit': self.total_profit,
            'avg_profit_per_trade': self.total_profit / self.total_trades if self.total_trades > 0 else 0,
            'sharpe_ratio': self.get_sharpe_ratio(),
            'regimes_learned': len(self.regime_adjustments),
            'experiences_stored': len(self.memory)
        }

    def reset_exploration(self):
        """Reset exploration rate (e.g., after good performance)"""
        self.exploration_rate *= 0.9  # Decrease exploration over time
        self.exploration_rate = max(0.01, self.exploration_rate)  # Min 1%

        logger.info(f"Exploration rate decreased to {self.exploration_rate:.3f}")
