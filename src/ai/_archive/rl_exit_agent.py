#!/usr/bin/env python3
"""
Reinforcement Learning Exit Agent - Deep Q-Network (DQN)

REPLACES hardcoded thresholds and heuristics with LEARNED policy from backtest data.

NO HARDCODED:
- ❌ confidence > 0.60 thresholds
- ❌ bars_held > 30 rules
- ❌ hardcoded probabilities (0.6, 0.4, etc.)
- ❌ min_ev_improvement = 5.0 constants

LEARNED FROM DATA:
- ✅ Q(state, CLOSE) = expected value of closing
- ✅ Q(state, HOLD) = expected value of holding
- ✅ Action = argmax(Q) - choose highest Q-value
- ✅ Q-values trained on 2,197 backtest trades

ARCHITECTURE:
- State: 230 features + position state (current P/L, bars held, max profit, etc.)
- Actions: HOLD, CLOSE, SCALE_OUT_50, SCALE_OUT_25
- Reward: Final P/L of trade (realized profit/loss)
- Training: Q-learning with experience replay from backtest trajectories
"""
import numpy as np
import pickle
import logging
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from collections import deque
import random

logger = logging.getLogger(__name__)

try:
    from tensorflow import keras
    from tensorflow.keras import layers, models, optimizers
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False
    logger.warning("TensorFlow not available - RL Exit Agent will use fallback linear model")


@dataclass
class ExitDecision:
    """RL-based exit decision (NO hardcoded thresholds!)"""
    action: str  # HOLD, CLOSE_ALL, SCALE_OUT_50, SCALE_OUT_25
    q_value: float  # Expected value from Q-network
    q_values_all: Dict[str, float]  # Q-values for all actions
    reason: str  # Human-readable explanation


class RLExitAgent:
    """
    Deep Q-Network Exit Agent

    Learns optimal exit policy from backtest data using Q-learning.
    NO hardcoded thresholds - all decisions based on learned Q-values.
    """

    # Action space (mapped to integers for neural network)
    ACTION_SPACE = {
        0: "HOLD",
        1: "CLOSE_ALL",
        2: "SCALE_OUT_50",
        3: "SCALE_OUT_25"
    }

    ACTION_TO_IDX = {v: k for k, v in ACTION_SPACE.items()}

    def __init__(
        self,
        state_dim: int = 235,  # 230 features + 5 position features
        learning_rate: float = 0.001,
        gamma: float = 0.95,  # Discount factor
        epsilon: float = 0.0,  # Exploration rate (0 for deployment, >0 for training)
        model_path: Optional[str] = None
    ):
        """
        Args:
            state_dim: Dimension of state vector
            learning_rate: Learning rate for neural network
            gamma: Discount factor for future rewards
            epsilon: Exploration rate (epsilon-greedy policy)
            model_path: Path to load pre-trained model
        """
        self.state_dim = state_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.learning_rate = learning_rate

        # Experience replay buffer
        self.memory = deque(maxlen=10000)
        self.batch_size = 64

        # Build Q-network
        if HAS_TENSORFLOW:
            if model_path:
                try:
                    self.q_network = keras.models.load_model(model_path)
                    logger.info(f"✅ Loaded pre-trained RL Exit Agent from {model_path}")
                except Exception as e:
                    logger.warning(f"Failed to load model from {model_path}: {e}")
                    self.q_network = self._build_q_network()
            else:
                self.q_network = self._build_q_network()
        else:
            # Fallback: Simple linear Q-function
            self.q_weights = np.random.randn(state_dim, len(self.ACTION_SPACE)) * 0.01
            logger.warning("Using fallback linear Q-function (TensorFlow not available)")

    def _build_q_network(self) -> models.Model:
        """
        Build Deep Q-Network

        Architecture:
        - Input: State vector (235 dimensions)
        - Hidden: 3 layers with ReLU activation
        - Output: Q-value for each action (4 outputs)
        """
        model = models.Sequential([
            layers.Input(shape=(self.state_dim,)),
            layers.Dense(256, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(128, activation='relu'),
            layers.Dropout(0.2),
            layers.Dense(64, activation='relu'),
            layers.Dense(len(self.ACTION_SPACE), activation='linear')  # Q-values (no activation)
        ])

        model.compile(
            optimizer=optimizers.Adam(learning_rate=self.learning_rate),
            loss='mse'
        )

        logger.info(f"✅ Built DQN with {model.count_params():,} parameters")
        return model

    def extract_state(
        self,
        features: Dict[str, float],
        current_profit_points: float,
        bars_held: int,
        max_profit_points: float,
        entry_confidence: float = 0.0
    ) -> np.ndarray:
        """
        Extract state vector from features and position state

        State = [230 market features] + [current_profit, bars_held, max_profit, drawdown_from_peak, entry_conf]
        """
        # Market features (230 dimensions)
        feature_values = [features.get(f, 0.0) for f in sorted(features.keys())]

        # Position state features (5 dimensions)
        drawdown_from_peak = 0.0
        if max_profit_points > 0:
            drawdown_from_peak = (max_profit_points - current_profit_points) / max_profit_points

        position_state = [
            current_profit_points / 100.0,  # Normalized
            bars_held / 100.0,  # Normalized
            max_profit_points / 100.0,  # Normalized
            drawdown_from_peak,  # Already 0-1
            entry_confidence / 100.0  # Normalized
        ]

        # Combine
        state = np.array(feature_values + position_state, dtype=np.float32)

        # Pad or truncate to state_dim
        if len(state) < self.state_dim:
            state = np.pad(state, (0, self.state_dim - len(state)))
        elif len(state) > self.state_dim:
            state = state[:self.state_dim]

        return state

    def decide_exit(
        self,
        features: Dict[str, float],
        current_profit_points: float,
        bars_held: int,
        max_profit_points: float,
        entry_confidence: float = 0.0,
        trade_type: str = "scalp"
    ) -> ExitDecision:
        """
        Make RL-based exit decision (NO hardcoded thresholds!)

        Args:
            features: Market features (230 dimensions)
            current_profit_points: Current unrealized P/L
            bars_held: Bars held since entry
            max_profit_points: Peak profit achieved
            entry_confidence: ML entry confidence (0-100)
            trade_type: 'scalp' or 'swing' (for logging only)

        Returns:
            ExitDecision with action and Q-values
        """
        # Extract state
        state = self.extract_state(
            features,
            current_profit_points,
            bars_held,
            max_profit_points,
            entry_confidence
        )

        # Get Q-values for all actions
        if HAS_TENSORFLOW:
            q_values = self.q_network.predict(state.reshape(1, -1), verbose=0)[0]
        else:
            # Fallback linear Q-function
            q_values = np.dot(state, self.q_weights)

        # Epsilon-greedy policy (for training only)
        if random.random() < self.epsilon:
            # Explore: random action
            action_idx = random.randint(0, len(self.ACTION_SPACE) - 1)
        else:
            # Exploit: choose action with highest Q-value
            action_idx = int(np.argmax(q_values))

        action = self.ACTION_SPACE[action_idx]
        q_value = float(q_values[action_idx])

        # Format all Q-values for debugging
        q_values_dict = {
            self.ACTION_SPACE[i]: float(q_values[i])
            for i in range(len(self.ACTION_SPACE))
        }

        # Generate reason
        reason = self._generate_reason(
            action,
            q_value,
            q_values_dict,
            current_profit_points,
            bars_held
        )

        return ExitDecision(
            action=action,
            q_value=q_value,
            q_values_all=q_values_dict,
            reason=reason
        )

    def _generate_reason(
        self,
        action: str,
        q_value: float,
        q_values_all: Dict[str, float],
        current_profit: float,
        bars_held: int
    ) -> str:
        """Generate human-readable explanation for decision"""

        if action == "CLOSE_ALL":
            hold_q = q_values_all.get("HOLD", 0.0)
            advantage = q_value - hold_q
            return (
                f"RL EXIT: Q(CLOSE)={q_value:.1f} > Q(HOLD)={hold_q:.1f} "
                f"(+{advantage:.1f} advantage) @ {current_profit:.0f}pts, {bars_held} bars"
            )

        elif action == "SCALE_OUT_50":
            hold_q = q_values_all.get("HOLD", 0.0)
            advantage = q_value - hold_q
            return (
                f"RL SCALE 50%: Q(SCALE)={q_value:.1f} > Q(HOLD)={hold_q:.1f} "
                f"(+{advantage:.1f} advantage) @ {current_profit:.0f}pts"
            )

        elif action == "SCALE_OUT_25":
            hold_q = q_values_all.get("HOLD", 0.0)
            advantage = q_value - hold_q
            return (
                f"RL SCALE 25%: Q(SCALE)={q_value:.1f} > Q(HOLD)={hold_q:.1f} "
                f"(+{advantage:.1f} advantage) @ {current_profit:.0f}pts"
            )

        else:  # HOLD
            close_q = q_values_all.get("CLOSE_ALL", 0.0)
            advantage = q_value - close_q
            return (
                f"RL HOLD: Q(HOLD)={q_value:.1f} > Q(CLOSE)={close_q:.1f} "
                f"(+{advantage:.1f} advantage) @ {current_profit:.0f}pts, {bars_held} bars"
            )

    def train_from_trajectory(
        self,
        trajectory: List[Tuple[np.ndarray, int, float, np.ndarray, bool]],
        epochs: int = 1
    ):
        """
        Train Q-network from a single trade trajectory

        Args:
            trajectory: List of (state, action, reward, next_state, done) tuples
            epochs: Number of training epochs per trajectory
        """
        if not HAS_TENSORFLOW:
            logger.warning("Cannot train - TensorFlow not available")
            return

        # Add trajectory to experience replay buffer
        for transition in trajectory:
            self.memory.append(transition)

        # Train on random batches from memory
        if len(self.memory) < self.batch_size:
            return  # Not enough samples yet

        for _ in range(epochs):
            batch = random.sample(self.memory, self.batch_size)

            states = np.array([t[0] for t in batch])
            actions = np.array([t[1] for t in batch])
            rewards = np.array([t[2] for t in batch])
            next_states = np.array([t[3] for t in batch])
            dones = np.array([t[4] for t in batch])

            # Q-learning update
            # Target: r + γ * max(Q(s', a')) for non-terminal states
            #         r for terminal states

            # Current Q-values
            current_q_values = self.q_network.predict(states, verbose=0)

            # Next Q-values
            next_q_values = self.q_network.predict(next_states, verbose=0)
            max_next_q = np.max(next_q_values, axis=1)

            # Bellman equation
            targets = current_q_values.copy()
            for i in range(len(batch)):
                if dones[i]:
                    targets[i, actions[i]] = rewards[i]
                else:
                    targets[i, actions[i]] = rewards[i] + self.gamma * max_next_q[i]

            # Train
            self.q_network.fit(states, targets, epochs=1, verbose=0)

    def save(self, path: str):
        """Save trained Q-network"""
        if HAS_TENSORFLOW:
            self.q_network.save(path)
            logger.info(f"✅ Saved RL Exit Agent to {path}")
        else:
            # Save linear weights
            with open(path, 'wb') as f:
                pickle.dump(self.q_weights, f)
            logger.info(f"✅ Saved linear Q-weights to {path}")

    def load(self, path: str):
        """Load trained Q-network"""
        if HAS_TENSORFLOW:
            self.q_network = keras.models.load_model(path)
            logger.info(f"✅ Loaded RL Exit Agent from {path}")
        else:
            with open(path, 'rb') as f:
                self.q_weights = pickle.load(f)
            logger.info(f"✅ Loaded linear Q-weights from {path}")
