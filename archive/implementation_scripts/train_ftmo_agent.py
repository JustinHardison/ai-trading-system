"""
FTMO PPO Agent Training Script
===============================
Train PPO agent to trade US30 profitably while respecting FTMO rules.

Training Process:
1. Load historical M1 data (+ other timeframes if available)
2. Create FTMO trading environment
3. Initialize PPO agent with Transformer
4. Train for 1M timesteps (~10K episodes)
5. Save checkpoints every 100K steps
6. Evaluate on held-out data

Usage:
    python train_ftmo_agent.py
    python train_ftmo_agent.py --timesteps 500000 --save_freq 50000
"""

import argparse
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import torch
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.rl.ftmo_env import FTMOTradingEnv
from src.rl.ppo_agent import create_ftmo_ppo_agent, FTMOCallback
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.env_checker import check_env


def load_historical_data(data_dir: str = "./data") -> dict:
    """
    Load all available historical timeframe data.

    Returns:
        Dict of {'M1': df, 'H1': df, ...}
    """
    data = {}

    # M1 data
    m1_path = os.path.join(data_dir, "us30_historical_data.csv")
    if os.path.exists(m1_path):
        print(f"Loading M1 data from {m1_path}...")
        df = pd.read_csv(m1_path)
        # Ensure required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if all(col in df.columns for col in required_cols):
            data['M1'] = df
            print(f"  ✅ Loaded {len(df):,} M1 bars")
        else:
            print(f"  ⚠️ Missing required columns: {required_cols}")

    # H1 data
    h1_path = os.path.join(data_dir, "us30_h1_historical_data.csv")
    if os.path.exists(h1_path):
        print(f"Loading H1 data from {h1_path}...")
        df = pd.read_csv(h1_path)
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if all(col in df.columns for col in required_cols):
            data['H1'] = df
            print(f"  ✅ Loaded {len(df):,} H1 bars")

    # M5, M15, H4, D1 (if available)
    for tf, filename in [
        ('M5', 'us30_m5_historical_data.csv'),
        ('M15', 'us30_m15_historical_data.csv'),
        ('M30', 'us30_m30_historical_data.csv'),
        ('H4', 'us30_h4_historical_data.csv'),
        ('D1', 'us30_d1_historical_data.csv'),
    ]:
        path = os.path.join(data_dir, filename)
        if os.path.exists(path):
            print(f"Loading {tf} data from {path}...")
            df = pd.read_csv(path)
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if all(col in df.columns for col in required_cols):
                data[tf] = df
                print(f"  ✅ Loaded {len(df):,} {tf} bars")

    if len(data) == 0:
        raise ValueError("No historical data found! Please place CSV files in ./data/")

    print(f"\nTotal timeframes loaded: {len(data)}")
    return data


def split_data(data: dict, train_ratio: float = 0.8) -> tuple:
    """
    Split data into train/test sets (chronological split).

    Args:
        data: Dict of timeframe DataFrames
        train_ratio: Ratio for training data

    Returns:
        (train_data, test_data) - Each is a dict of DataFrames
    """
    train_data = {}
    test_data = {}

    for tf, df in data.items():
        split_idx = int(len(df) * train_ratio)
        train_data[tf] = df.iloc[:split_idx].reset_index(drop=True)
        test_data[tf] = df.iloc[split_idx:].reset_index(drop=True)

        print(f"{tf}: Train={len(train_data[tf]):,} bars, Test={len(test_data[tf]):,} bars")

    return train_data, test_data


def main(args):
    """Main training loop."""

    print("="*70)
    print("FTMO PPO Agent Training")
    print("="*70)
    print(f"Device: {args.device}")
    print(f"Total timesteps: {args.timesteps:,}")
    print(f"Learning rate: {args.learning_rate}")
    print(f"Batch size: {args.batch_size}")
    print(f"Checkpoint frequency: {args.save_freq:,}")
    print("="*70)

    # 1. Load historical data
    print("\n[1/6] Loading historical data...")
    try:
        data = load_historical_data(args.data_dir)
    except Exception as e:
        print(f"❌ Failed to load data: {e}")
        return

    # 2. Split into train/test
    print("\n[2/6] Splitting data (80% train, 20% test)...")
    train_data, test_data = split_data(data, train_ratio=0.8)

    # 3. Create environments
    print("\n[3/6] Creating FTMO trading environments...")

    train_env = FTMOTradingEnv(
        data=train_data,
        initial_balance=args.initial_balance,
        max_daily_loss=args.max_daily_loss,
        max_total_drawdown=args.max_total_drawdown,
        spread_points=args.spread,
        slippage_points=args.slippage,
        max_position_size=args.max_position_size,
    )

    test_env = FTMOTradingEnv(
        data=test_data,
        initial_balance=args.initial_balance,
        max_daily_loss=args.max_daily_loss,
        max_total_drawdown=args.max_total_drawdown,
        spread_points=args.spread,
        slippage_points=args.slippage,
        max_position_size=args.max_position_size,
    )

    print("✅ Environments created")

    # Optionally check environment
    if args.check_env:
        print("Checking environment compliance...")
        try:
            check_env(train_env)
            print("✅ Environment check passed")
        except Exception as e:
            print(f"⚠️ Environment check failed: {e}")

    # 4. Create PPO agent
    print("\n[4/6] Creating PPO agent with Transformer...")

    agent = create_ftmo_ppo_agent(
        env=train_env,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_range=args.clip_range,
        ent_coef=args.ent_coef,
        tensorboard_log=args.log_dir,
        device=args.device,
        verbose=1,
    )

    total_params = sum(p.numel() for p in agent.policy.parameters())
    print(f"✅ PPO agent created ({total_params:,} parameters)")

    # 5. Setup callbacks
    print("\n[5/6] Setting up training callbacks...")

    # Checkpoint callback (save model periodically)
    checkpoint_callback = CheckpointCallback(
        save_freq=args.save_freq,
        save_path=args.save_dir,
        name_prefix="ftmo_ppo",
        save_replay_buffer=False,
        save_vecnormalize=False,
    )

    # Evaluation callback (test on held-out data)
    eval_callback = EvalCallback(
        test_env,
        best_model_save_path=args.save_dir,
        log_path=args.log_dir,
        eval_freq=args.eval_freq,
        n_eval_episodes=5,
        deterministic=True,
        render=False,
    )

    # FTMO-specific callback
    ftmo_callback = FTMOCallback(verbose=1)

    callbacks = [checkpoint_callback, eval_callback, ftmo_callback]

    print("✅ Callbacks configured")

    # 6. Train agent
    print("\n[6/6] Starting training...")
    print("="*70)
    print(f"Training for {args.timesteps:,} timesteps")
    print(f"Monitor with: tensorboard --logdir {args.log_dir}")
    print("="*70)

    try:
        agent.learn(
            total_timesteps=args.timesteps,
            callback=callbacks,
            log_interval=10,
            progress_bar=True,
        )

        print("\n" + "="*70)
        print("✅ Training completed successfully!")
        print("="*70)

        # Save final model
        final_path = os.path.join(args.save_dir, "ftmo_ppo_final.zip")
        agent.save(final_path)
        print(f"💾 Final model saved to: {final_path}")

        # Save training info
        info_path = os.path.join(args.save_dir, "training_info.txt")
        with open(info_path, 'w') as f:
            f.write("FTMO PPO Training Info\n")
            f.write("="*50 + "\n")
            f.write(f"Date: {datetime.now()}\n")
            f.write(f"Total timesteps: {args.timesteps:,}\n")
            f.write(f"Learning rate: {args.learning_rate}\n")
            f.write(f"Batch size: {args.batch_size}\n")
            f.write(f"Model parameters: {total_params:,}\n")
            f.write(f"Device: {args.device}\n")
            f.write(f"Timeframes used: {list(data.keys())}\n")
            f.write(f"Train bars (M1): {len(train_data.get('M1', [])):,}\n")
            f.write(f"Test bars (M1): {len(test_data.get('M1', [])):,}\n")

        print(f"📝 Training info saved to: {info_path}")

        # Evaluate on test set
        print("\n" + "="*70)
        print("Evaluating on test set...")
        print("="*70)

        obs, _ = test_env.reset()
        total_reward = 0
        episode_rewards = []

        for ep in range(5):
            obs, _ = test_env.reset()
            done = False
            ep_reward = 0

            while not done:
                action, _ = agent.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = test_env.step(action)
                done = terminated or truncated
                ep_reward += reward

            episode_rewards.append(ep_reward)
            print(f"Episode {ep+1}: Reward={ep_reward:.2f}, Balance=${info['balance']:,.2f}")

        print(f"\nAverage test reward: {np.mean(episode_rewards):.2f}")
        print("="*70)

    except KeyboardInterrupt:
        print("\n⚠️ Training interrupted by user")
        save_path = os.path.join(args.save_dir, "ftmo_ppo_interrupted.zip")
        agent.save(save_path)
        print(f"💾 Model saved to: {save_path}")

    except Exception as e:
        print(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FTMO PPO trading agent")

    # Data
    parser.add_argument("--data_dir", type=str, default="./data",
                        help="Directory containing historical data CSVs")

    # Training
    parser.add_argument("--timesteps", type=int, default=1_000_000,
                        help="Total training timesteps (default: 1M)")
    parser.add_argument("--learning_rate", type=float, default=3e-4,
                        help="Learning rate (default: 3e-4)")
    parser.add_argument("--n_steps", type=int, default=2048,
                        help="Steps per rollout (default: 2048)")
    parser.add_argument("--batch_size", type=int, default=64,
                        help="Batch size (default: 64)")
    parser.add_argument("--n_epochs", type=int, default=10,
                        help="Epochs per rollout (default: 10)")
    parser.add_argument("--gamma", type=float, default=0.99,
                        help="Discount factor (default: 0.99)")
    parser.add_argument("--gae_lambda", type=float, default=0.95,
                        help="GAE lambda (default: 0.95)")
    parser.add_argument("--clip_range", type=float, default=0.2,
                        help="PPO clip range (default: 0.2)")
    parser.add_argument("--ent_coef", type=float, default=0.01,
                        help="Entropy coefficient (default: 0.01)")

    # FTMO rules
    parser.add_argument("--initial_balance", type=float, default=100000,
                        help="Initial account balance (default: 100K)")
    parser.add_argument("--max_daily_loss", type=float, default=5000,
                        help="Max daily loss (default: 5K)")
    parser.add_argument("--max_total_drawdown", type=float, default=10000,
                        help="Max total drawdown (default: 10K)")

    # Trading costs
    parser.add_argument("--spread", type=float, default=10.0,
                        help="Spread in points (default: 10)")
    parser.add_argument("--slippage", type=float, default=2.0,
                        help="Slippage in points (default: 2)")
    parser.add_argument("--max_position_size", type=float, default=10.0,
                        help="Max position size in lots (default: 10)")

    # Callbacks
    parser.add_argument("--save_freq", type=int, default=100_000,
                        help="Checkpoint save frequency (default: 100K)")
    parser.add_argument("--eval_freq", type=int, default=50_000,
                        help="Evaluation frequency (default: 50K)")

    # Paths
    parser.add_argument("--save_dir", type=str, default="./models/ftmo_ppo",
                        help="Directory to save models")
    parser.add_argument("--log_dir", type=str, default="./logs/ftmo_ppo",
                        help="Directory for TensorBoard logs")

    # Other
    parser.add_argument("--device", type=str, default="auto",
                        help="Device (cpu/cuda/auto)")
    parser.add_argument("--check_env", action="store_true",
                        help="Run environment checks before training")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed")

    args = parser.parse_args()

    # Create directories
    os.makedirs(args.save_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)

    # Set seed
    if args.seed is not None:
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)

    # Run training
    main(args)
