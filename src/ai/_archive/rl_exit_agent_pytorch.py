#!/usr/bin/env python3
"""
Reinforcement Learning Exit Agent - PyTorch Version (FAST!)

Uses PyTorch instead of TensorFlow - loads instantly!

NO HARDCODED THRESHOLDS - All decisions from learned Q-values.
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
    import torch
    import torch.nn as nn
    import torch.optim as optim
    HAS_PYTORCH = True
except ImportError:
    HAS_PYTORCH = False
    logger.warning("PyTorch not available - RL Exit Agent will use fallback linear model")


@dataclass
class ExitDecision:
    """RL-based exit decision (NO hardcoded thresholds!)"""
    action: str  # HOLD, CLOSE_ALL, SCALE_OUT_50, SCALE_OUT_25
    q_value: float  # Expected value from Q-network
    q_values_all: Dict[str, float]  # Q-values for all actions
    reason: str  # Human-readable explanation


class QNetwork(nn.Module):
    """Deep Q-Network using PyTorch"""

    def __init__(self, state_dim: int, action_dim: int):
        super(QNetwork, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim)
        )

    def forward(self, x):
        return self.network(x)


class RLExitAgent:
    """
    Deep Q-Network Exit Agent using PyTorch (FAST!)

    Learns optimal exit policy from backtest data using Q-learning.
    NO hardcoded thresholds - all decisions based on learned Q-values.
    """

    # Action space
    ACTION_SPACE = {
        0: "HOLD",
        1: "CLOSE_ALL",
        2: "SCALE_OUT_50",
        3: "SCALE_OUT_25"
    }

    ACTION_TO_IDX = {v: k for k, v in ACTION_SPACE.items()}

    def __init__(
        self,
        state_dim: int = 235,
        learning_rate: float = 0.001,
        gamma: float = 0.95,
        epsilon: float = 0.0,
        model_path: Optional[str] = None
    ):
        """
        Args:
            state_dim: Dimension of state vector
            learning_rate: Learning rate for neural network
            gamma: Discount factor for future rewards
            epsilon: Exploration rate (0 for deployment)
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
        if HAS_PYTORCH:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.q_network = QNetwork(state_dim, len(self.ACTION_SPACE)).to(self.device)
            self.optimizer = optim.Adam(self.q_network.parameters(), lr=learning_rate)
            self.criterion = nn.MSELoss()

            if model_path:
                try:
                    self.q_network.load_state_dict(torch.load(model_path, map_location=self.device))
                    self.q_network.eval()
                    logger.info(f"✅ Loaded pre-trained RL agent from {model_path}")
                except Exception as e:
                    logger.warning(f"Failed to load model from {model_path}: {e}")
                    logger.info("Using randomly initialized weights")
        else:
            # Fallback: Simple linear Q-function
            self.q_weights = np.random.randn(state_dim, len(self.ACTION_SPACE)) * 0.01
            logger.warning("Using fallback linear Q-function (PyTorch not available)")

    def extract_state(
        self,
        features: Dict[str, float],
        current_profit_points: float,
        bars_held: int,
        max_profit_points: float,
        entry_confidence: float = 0.0
    ) -> np.ndarray:
        """Extract state vector from features and position state"""
        # Market features (230 dimensions)
        feature_values = [features.get(f, 0.0) for f in sorted(features.keys())]

        # Position state features (5 dimensions)
        drawdown_from_peak = 0.0
        if max_profit_points > 0:
            drawdown_from_peak = (max_profit_points - current_profit_points) / max_profit_points

        position_state = [
            current_profit_points / 100.0,
            bars_held / 100.0,
            max_profit_points / 100.0,
            drawdown_from_peak,
            entry_confidence / 100.0
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
        if HAS_PYTORCH:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.q_network(state_tensor).cpu().numpy()[0]
        else:
            # Fallback linear Q-function
            q_values = np.dot(state, self.q_weights)

        # Epsilon-greedy policy
        if random.random() < self.epsilon:
            action_idx = random.randint(0, len(self.ACTION_SPACE) - 1)
        else:
            action_idx = int(np.argmax(q_values))

        action = self.ACTION_SPACE[action_idx]
        q_value = float(q_values[action_idx])

        # Format all Q-values
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
        """Generate human-readable explanation"""

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
        """Train Q-network from a single trade trajectory"""
        if not HAS_PYTORCH:
            logger.warning("Cannot train - PyTorch not available")
            return

        # Add trajectory to replay buffer
        for transition in trajectory:
            self.memory.append(transition)

        # Train on random batches
        if len(self.memory) < self.batch_size:
            return

        for _ in range(epochs):
            batch = random.sample(self.memory, self.batch_size)

            states = torch.FloatTensor([t[0] for t in batch]).to(self.device)
            actions = torch.LongTensor([t[1] for t in batch]).to(self.device)
            rewards = torch.FloatTensor([t[2] for t in batch]).to(self.device)
            next_states = torch.FloatTensor([t[3] for t in batch]).to(self.device)
            dones = torch.FloatTensor([t[4] for t in batch]).to(self.device)

            # Current Q-values
            current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze()

            # Next Q-values
            with torch.no_grad():
                next_q_values = self.q_network(next_states).max(1)[0]
                targets = rewards + (1 - dones) * self.gamma * next_q_values

            # Compute loss and update
            loss = self.criterion(current_q_values, targets)
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()

    def save(self, path: str):
        """Save trained Q-network"""
        if HAS_PYTORCH:
            torch.save(self.q_network.state_dict(), path)
            logger.info(f"✅ Saved RL Exit Agent to {path}")
        else:
            with open(path, 'wb') as f:
                pickle.dump(self.q_weights, f)
            logger.info(f"✅ Saved linear Q-weights to {path}")

    def load(self, path: str):
        """Load trained Q-network"""
        if HAS_PYTORCH:
            self.q_network.load_state_dict(torch.load(path, map_location=self.device))
            self.q_network.eval()
            logger.info(f"✅ Loaded RL Exit Agent from {path}")
        else:
            with open(path, 'rb') as f:
                self.q_weights = pickle.load(f)
            logger.info(f"✅ Loaded linear Q-weights from {path}")
