"""
PPO (Proximal Policy Optimization) Trading Strategy
Primary RL strategy for autonomous trading
"""
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from gymnasium import spaces
import gymnasium as gym

from ..utils.logger import get_logger


logger = get_logger(__name__)


class TradingEnvironment(gym.Env):
    """
    Custom trading environment for RL training
    Compatible with Gymnasium/Gym API
    """

    def __init__(
        self,
        data: np.ndarray,
        initial_balance: float = 100000,
        max_position_size: float = 1.0,
        transaction_cost: float = 0.001,
    ):
        super().__init__()

        self.data = data
        self.initial_balance = initial_balance
        self.max_position_size = max_position_size
        self.transaction_cost = transaction_cost

        # State space: [balance, position, price data, technical indicators]
        # Assuming data has shape (n_timesteps, n_features)
        n_features = data.shape[1]
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(n_features + 2,),  # +2 for balance and position
            dtype=np.float32
        )

        # Action space: continuous [-1, 1]
        # -1 = full short, 0 = neutral, +1 = full long
        self.action_space = spaces.Box(
            low=-1,
            high=1,
            shape=(1,),
            dtype=np.float32
        )

        self.reset()

    def reset(self, seed=None, options=None):
        """Reset the environment"""
        super().reset(seed=seed)

        self.current_step = 0
        self.balance = self.initial_balance
        self.position = 0.0  # -1 to +1 (percentage of portfolio)
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.trades = []

        return self._get_observation(), {}

    def _get_observation(self) -> np.ndarray:
        """Get current state observation"""
        if self.current_step >= len(self.data):
            self.current_step = len(self.data) - 1

        market_data = self.data[self.current_step]

        # Normalize balance and position
        normalized_balance = self.balance / self.initial_balance
        normalized_position = self.position

        obs = np.concatenate([
            [normalized_balance, normalized_position],
            market_data
        ]).astype(np.float32)

        return obs

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """Execute one step in the environment"""
        # Get target position from action
        target_position = np.clip(action[0], -self.max_position_size, self.max_position_size)

        # Get current price
        current_price = self.data[self.current_step, 0]  # Assuming first feature is price

        # Calculate reward
        reward = self._calculate_reward(current_price, target_position)

        # Execute trade if position changed
        if abs(target_position - self.position) > 0.01:
            self._execute_trade(current_price, target_position)

        # Move to next step
        self.current_step += 1

        # Check if episode is done
        done = self.current_step >= len(self.data) - 1
        truncated = False

        # Calculate portfolio value
        portfolio_value = self.balance + (self.position * self.balance * (
            current_price / self.entry_price - 1 if self.entry_price > 0 else 0
        ))

        # Check for bankruptcy
        if portfolio_value < self.initial_balance * 0.5:
            done = True
            reward = -100  # Severe penalty for losing too much

        info = {
            "balance": self.balance,
            "position": self.position,
            "portfolio_value": portfolio_value,
            "total_pnl": self.total_pnl,
            "num_trades": len(self.trades),
        }

        return self._get_observation(), reward, done, truncated, info

    def _calculate_reward(self, current_price: float, target_position: float) -> float:
        """Calculate reward for the current step"""
        # Calculate unrealized P&L
        if self.position != 0 and self.entry_price > 0:
            price_change = (current_price / self.entry_price) - 1
            pnl = self.position * self.balance * price_change
        else:
            pnl = 0

        # Reward is based on P&L
        reward = pnl / self.initial_balance * 100  # Normalize by initial balance

        # Penalize excessive trading (transaction costs)
        position_change = abs(target_position - self.position)
        reward -= position_change * self.transaction_cost * 10

        # Bonus for profitable trades
        if pnl > 0:
            reward *= 1.2

        return reward

    def _execute_trade(self, price: float, target_position: float):
        """Execute a trade to reach target position"""
        # Close existing position if any
        if self.position != 0 and self.entry_price > 0:
            price_change = (price / self.entry_price) - 1
            pnl = self.position * self.balance * price_change

            # Apply transaction cost
            transaction_cost = abs(self.position) * self.balance * self.transaction_cost

            net_pnl = pnl - transaction_cost
            self.balance += net_pnl
            self.total_pnl += net_pnl

            self.trades.append({
                "entry_price": self.entry_price,
                "exit_price": price,
                "position": self.position,
                "pnl": net_pnl,
                "step": self.current_step,
            })

        # Open new position
        self.position = target_position
        self.entry_price = price

        # Apply transaction cost
        transaction_cost = abs(self.position) * self.balance * self.transaction_cost
        self.balance -= transaction_cost

    def render(self):
        """Render the environment (optional)"""
        pass


class PPOStrategy:
    """
    PPO-based trading strategy
    Uses Proximal Policy Optimization for decision making
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = 1,
        learning_rate: float = 0.0003,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        device: str = "auto",
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.learning_rate = learning_rate
        self.device = device

        self.model = None
        self.env = None

        # PPO hyperparameters
        self.ppo_params = {
            "learning_rate": learning_rate,
            "n_steps": n_steps,
            "batch_size": batch_size,
            "n_epochs": n_epochs,
            "gamma": gamma,
            "gae_lambda": 0.95,
            "clip_range": 0.2,
            "ent_coef": 0.01,
            "vf_coef": 0.5,
            "max_grad_norm": 0.5,
            "device": device,
        }

        logger.info(f"Initialized PPO strategy with state_dim={state_dim}")

    def create_environment(
        self,
        data: np.ndarray,
        initial_balance: float = 100000,
        max_position_size: float = 1.0,
    ) -> TradingEnvironment:
        """Create trading environment"""
        env = TradingEnvironment(
            data=data,
            initial_balance=initial_balance,
            max_position_size=max_position_size,
        )
        return env

    def train(
        self,
        training_data: np.ndarray,
        total_timesteps: int = 100000,
        initial_balance: float = 100000,
        save_path: Optional[str] = None,
    ):
        """
        Train the PPO model

        Args:
            training_data: Historical market data (shape: n_timesteps x n_features)
            total_timesteps: Total training timesteps
            initial_balance: Initial account balance
            save_path: Path to save the trained model
        """
        logger.info(f"Starting PPO training for {total_timesteps} timesteps")

        # Create environment
        self.env = self.create_environment(
            data=training_data,
            initial_balance=initial_balance,
        )

        # Wrap in DummyVecEnv for stable-baselines3
        vec_env = DummyVecEnv([lambda: self.env])

        # Create PPO model
        self.model = PPO(
            "MlpPolicy",
            vec_env,
            verbose=1,
            **self.ppo_params
        )

        # Train the model
        self.model.learn(total_timesteps=total_timesteps)

        logger.info("PPO training completed")

        # Save model if path provided
        if save_path:
            self.save(save_path)
            logger.info(f"Model saved to {save_path}")

    def predict(
        self,
        state: np.ndarray,
        deterministic: bool = True,
    ) -> Tuple[float, float]:
        """
        Predict action for given state

        Args:
            state: Current market state
            deterministic: Use deterministic policy (True for trading)

        Returns:
            Tuple of (action, confidence)
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")

        action, _states = self.model.predict(state, deterministic=deterministic)
        confidence = 1.0  # PPO doesn't directly output confidence

        return float(action[0]), confidence

    def save(self, path: str):
        """Save model to disk"""
        if self.model:
            self.model.save(path)
            logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from disk"""
        self.model = PPO.load(path, device=self.device)
        logger.info(f"Model loaded from {path}")

    def backtest(
        self,
        test_data: np.ndarray,
        initial_balance: float = 100000,
    ) -> Dict:
        """
        Backtest the strategy on test data

        Args:
            test_data: Historical market data for testing
            initial_balance: Initial account balance

        Returns:
            Dictionary with performance metrics
        """
        logger.info("Starting backtest")

        env = self.create_environment(
            data=test_data,
            initial_balance=initial_balance,
        )

        obs, _ = env.reset()
        done = False
        episode_reward = 0

        while not done:
            action, _ = self.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step([action])
            episode_reward += reward
            done = done or truncated

        # Calculate performance metrics
        final_balance = info["balance"]
        total_pnl = info["total_pnl"]
        num_trades = info["num_trades"]
        total_return = (final_balance / initial_balance - 1) * 100

        # Calculate additional metrics
        trades = env.trades
        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] < 0]

        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        results = {
            "initial_balance": initial_balance,
            "final_balance": final_balance,
            "total_pnl": total_pnl,
            "total_return_pct": total_return,
            "num_trades": num_trades,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "episode_reward": episode_reward,
        }

        logger.info(f"Backtest completed: Return={total_return:.2f}%, "
                   f"Win Rate={win_rate:.1f}%, Profit Factor={profit_factor:.2f}")

        return results
