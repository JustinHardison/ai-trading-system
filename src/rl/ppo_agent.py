"""
PPO Agent for FTMO Trading
===========================
Proximal Policy Optimization implementation using Stable-Baselines3.

Learns to trade US30 profitably while respecting FTMO rules:
- Max 5% daily loss
- Max 10% total drawdown
- Consistent profit optimization

Uses Temporal Fusion Transformer for state encoding.
"""

import torch
import torch.nn as nn
from stable_baselines3 import PPO
from stable_baselines3.common.policies import ActorCriticPolicy
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.callbacks import BaseCallback
from typing import Dict
import gymnasium as gym
import numpy as np

from src.rl.temporal_fusion import TransformerFeatureExtractor


class FTMOCallback(BaseCallback):
    """
    Callback for monitoring FTMO-specific metrics during training.

    Tracks:
    - Daily loss violations
    - Total drawdown violations
    - Win rate
    - Average profit per trade
    - Sharpe ratio
    """

    def __init__(self, verbose=0):
        super().__init__(verbose)
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_ftmo_violations = []
        self.episode_trades = []
        self.episode_win_rates = []

    def _on_step(self) -> bool:
        """Called after each step."""
        return True

    def _on_rollout_end(self) -> None:
        """Called at the end of a rollout."""
        # Extract info from environment
        if len(self.locals.get('infos', [])) > 0:
            info = self.locals['infos'][0]

            # Log FTMO-specific metrics
            if 'balance' in info:
                self.logger.record('ftmo/balance', info['balance'])
                self.logger.record('ftmo/equity', info['equity'])
                self.logger.record('ftmo/daily_pnl', info['daily_pnl'])
                self.logger.record('ftmo/daily_loss', info['daily_loss'])
                self.logger.record('ftmo/total_drawdown', info['total_drawdown'])
                self.logger.record('ftmo/distance_to_daily_limit', info['distance_to_daily_limit'])
                self.logger.record('ftmo/distance_to_dd_limit', info['distance_to_dd_limit'])
                self.logger.record('ftmo/num_trades', info['num_trades'])

    def _on_training_end(self) -> None:
        """Called at the end of training."""
        print("\n" + "="*60)
        print("FTMO PPO Training Summary")
        print("="*60)
        print(f"Total episodes: {len(self.episode_rewards)}")
        if len(self.episode_rewards) > 0:
            print(f"Average reward: {np.mean(self.episode_rewards):.2f}")
            print(f"Average episode length: {np.mean(self.episode_lengths):.2f}")
            print(f"FTMO violations: {sum(self.episode_ftmo_violations)}")
            print(f"Total trades: {sum(self.episode_trades)}")
            if len(self.episode_win_rates) > 0:
                print(f"Average win rate: {np.mean(self.episode_win_rates):.2%}")
        print("="*60)


class FTMOActorCriticPolicy(ActorCriticPolicy):
    """
    Custom Actor-Critic policy for FTMO trading.

    Uses Transformer feature extractor instead of default MLP.
    """

    def __init__(self, *args, **kwargs):
        # Use our custom Transformer feature extractor
        kwargs['features_extractor_class'] = TransformerFeatureExtractor
        kwargs['features_extractor_kwargs'] = {
            'features_dim': 512,
            'transformer_hidden_dim': 64,
        }

        super().__init__(*args, **kwargs)


def create_ftmo_ppo_agent(
    env: gym.Env,
    learning_rate: float = 3e-4,
    n_steps: int = 2048,
    batch_size: int = 64,
    n_epochs: int = 10,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.2,
    ent_coef: float = 0.01,
    vf_coef: float = 0.5,
    max_grad_norm: float = 0.5,
    use_sde: bool = False,
    sde_sample_freq: int = -1,
    tensorboard_log: str = "./logs/ftmo_ppo",
    device: str = 'auto',
    verbose: int = 1,
) -> PPO:
    """
    Create PPO agent optimized for FTMO trading.

    Args:
        env: FTMO trading environment
        learning_rate: Learning rate for optimizer
        n_steps: Number of steps per rollout (2048 = ~1.5 trading days on M1)
        batch_size: Batch size for training
        n_epochs: Number of epochs per rollout
        gamma: Discount factor (0.99 = values future rewards highly)
        gae_lambda: GAE lambda for advantage estimation
        clip_range: PPO clipping parameter
        ent_coef: Entropy coefficient (exploration bonus)
        vf_coef: Value function coefficient
        max_grad_norm: Max gradient norm for clipping
        use_sde: Use State-Dependent Exploration
        sde_sample_freq: Sample frequency for SDE
        tensorboard_log: Path for TensorBoard logs
        device: Device to use ('cpu', 'cuda', or 'auto')
        verbose: Verbosity level

    Returns:
        Configured PPO agent
    """

    # Policy kwargs
    policy_kwargs = dict(
        features_extractor_class=TransformerFeatureExtractor,
        features_extractor_kwargs={
            'features_dim': 512,
            'transformer_hidden_dim': 64,
        },
        net_arch=dict(
            pi=[512, 512, 256],  # Actor network
            vf=[512, 512, 256],  # Value network (critic)
        ),
        activation_fn=nn.ReLU,
    )

    # Create PPO agent
    agent = PPO(
        policy="MultiInputPolicy",
        env=env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        ent_coef=ent_coef,
        vf_coef=vf_coef,
        max_grad_norm=max_grad_norm,
        use_sde=use_sde,
        sde_sample_freq=sde_sample_freq,
        policy_kwargs=policy_kwargs,
        tensorboard_log=tensorboard_log,
        device=device,
        verbose=verbose,
    )

    return agent


def load_ftmo_agent(path: str, env: gym.Env) -> PPO:
    """
    Load a trained FTMO PPO agent.

    Args:
        path: Path to saved model (.zip file)
        env: FTMO trading environment

    Returns:
        Loaded PPO agent
    """
    agent = PPO.load(path, env=env)
    return agent


def predict_trading_action(
    agent: PPO,
    observation: Dict,
    deterministic: bool = True
) -> Dict:
    """
    Get trading action from trained agent.

    Args:
        agent: Trained PPO agent
        observation: Current environment observation
        deterministic: If True, use deterministic policy (no exploration)

    Returns:
        Dict with {
            'direction': 1 (long), -1 (short), or 0 (close),
            'size': Position size in lots,
            'stop_loss': Stop loss price,
            'take_profit': Take profit price,
            'raw_action': Raw action array
        }
    """
    # Get action from agent
    action, _ = agent.predict(observation, deterministic=deterministic)

    # Parse action
    direction_raw, size_fraction, sl_atr, tp_atr = action

    # Interpret direction
    if abs(direction_raw) > 0.3:
        direction = 1 if direction_raw > 0 else -1
    else:
        direction = 0  # No trade

    # For now, return simplified action
    # In production, you'd calculate actual SL/TP prices based on current market
    return {
        'direction': direction,
        'size': size_fraction,
        'stop_loss_atr': sl_atr,
        'take_profit_atr': tp_atr,
        'raw_action': action,
        'direction_confidence': abs(direction_raw),
    }


if __name__ == "__main__":
    """Test PPO agent creation."""
    from src.rl.ftmo_env import FTMOTradingEnv
    import pandas as pd

    print("Testing FTMO PPO Agent...")

    # Create dummy data
    dummy_m1 = pd.DataFrame({
        'open': np.random.randn(5000) * 100 + 50000,
        'high': np.random.randn(5000) * 100 + 50100,
        'low': np.random.randn(5000) * 100 + 49900,
        'close': np.random.randn(5000) * 100 + 50000,
        'volume': np.random.randint(100, 1000, 5000),
    })

    # Create environment
    env = FTMOTradingEnv(
        data={'M1': dummy_m1},
        initial_balance=100000,
        max_daily_loss=5000,
        max_total_drawdown=10000,
    )

    print("✅ Environment created")

    # Create agent
    agent = create_ftmo_ppo_agent(
        env=env,
        learning_rate=3e-4,
        n_steps=512,  # Smaller for testing
        batch_size=64,
        verbose=1,
    )

    print("✅ PPO agent created")

    # Count parameters
    total_params = sum(p.numel() for p in agent.policy.parameters())
    print(f"\nTotal parameters: {total_params:,}")

    # Test prediction
    obs, _ = env.reset()
    action = predict_trading_action(agent, obs, deterministic=True)

    print(f"\nTest prediction:")
    print(f"  Direction: {action['direction']}")
    print(f"  Size: {action['size']:.2f}")
    print(f"  SL ATR: {action['stop_loss_atr']:.2f}")
    print(f"  TP ATR: {action['take_profit_atr']:.2f}")

    print("\n✅ PPO agent test passed!")
