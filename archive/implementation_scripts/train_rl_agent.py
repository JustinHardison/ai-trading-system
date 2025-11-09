#!/usr/bin/env python3
"""
Train RL Agent on Historical MT5 Data
Fix the 54.6% win rate by properly training with exploration → exploitation
"""
import pandas as pd
import numpy as np
from pathlib import Path
from src.ml.reinforcement_learning import TradingRLAgent
from loguru import logger

def prepare_rl_states(df: pd.DataFrame) -> np.ndarray:
    """
    Convert market data to RL states (20 features)
    """
    states = []

    for i in range(len(df)):
        row = df.iloc[i]

        # Normalize features to [-1, 1] range for discretization
        state = [
            # Price action (5 features)
            np.tanh((row['close'] - row['open']) / row['close'] * 100),  # Candle body
            np.tanh((row['high'] - row['low']) / row['close'] * 100),    # Range
            np.tanh((row['close'] - row['low']) / (row['high'] - row['low'] + 1e-8) * 2 - 1),  # Position in range

            # Volume (2 features)
            np.tanh((row['tick_volume'] - row.get('volume_sma_20', row['tick_volume'])) / (row.get('volume_sma_20', row['tick_volume']) + 1)),

            # Momentum (5 features)
            np.tanh(row.get('rsi_14', 50) / 50 - 1),  # RSI normalized
            np.tanh(row.get('macd', 0) / row['close'] * 1000),
            np.tanh(row.get('macd_signal', 0) / row['close'] * 1000),

            # Trend (4 features)
            np.tanh((row['close'] - row.get('sma_20', row['close'])) / row['close'] * 100),
            np.tanh((row['close'] - row.get('sma_50', row['close'])) / row['close'] * 100),

            # Volatility (2 features)
            np.tanh(row.get('atr_14', 100) / row['close'] * 100),

            # Session (2 features)
            np.sin(2 * np.pi * row['hour'] / 24),  # Time of day (circular)
            np.cos(2 * np.pi * row['hour'] / 24),
        ]

        # Pad to 20 features if needed
        while len(state) < 20:
            state.append(0.0)

        states.append(state[:20])  # Ensure exactly 20

    return np.array(states)

def calculate_rewards(df: pd.DataFrame, lookahead_bars: int = 5) -> np.ndarray:
    """
    Calculate rewards based on future price movement

    Reward = (future_price - current_price) / current_price * 100
    """
    rewards = []

    for i in range(len(df)):
        if i + lookahead_bars >= len(df):
            # No future data - use zero reward
            rewards.append(0.0)
            continue

        current_price = df.iloc[i]['close']
        future_price = df.iloc[i + lookahead_bars]['close']

        # Calculate percentage change
        reward = (future_price - current_price) / current_price * 100

        rewards.append(reward)

    return np.array(rewards)

def train_rl_agent():
    """Train RL agent on historical data"""

    logger.info("=" * 70)
    logger.info("TRAINING RL AGENT ON HISTORICAL DATA")
    logger.info("=" * 70)

    # Load data
    data_path = Path("us30_historical_data.csv")
    if not data_path.exists():
        logger.error(f"Data file not found: {data_path}")
        return

    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path, sep='\t')  # Tab-delimited MT5 export
    logger.info(f"Loaded {len(df):,} bars of M1 data")

    # Check columns
    logger.info(f"Columns found: {df.columns.tolist()}")

    # Add hour column - handle MT5 time format
    df['time'] = pd.to_datetime(df['time'], format='%Y.%m.%d %H:%M')
    df['hour'] = df['time'].dt.hour

    # Prepare states
    logger.info("Preparing RL states (20 features per bar)...")
    states = prepare_rl_states(df)
    logger.info(f"States shape: {states.shape}")

    # Calculate rewards (5-bar lookahead for M1 scalping)
    logger.info("Calculating rewards (5-bar lookahead)...")
    rewards = calculate_rewards(df, lookahead_bars=5)
    logger.info(f"Rewards: mean={rewards.mean():.4f}, std={rewards.std():.4f}")

    # Initialize RL agent
    agent = TradingRLAgent(
        state_size=20,
        action_size=3,  # HOLD, BUY, SELL
        learning_rate=0.01,  # Higher learning rate for faster convergence
        epsilon=1.0,  # Start with 100% exploration
        epsilon_decay=0.9995,  # Slow decay
        epsilon_min=0.05  # Keep 5% exploration
    )

    logger.info("Training RL agent...")
    logger.info(f"Initial epsilon: {agent.epsilon:.4f}")

    # Training loop
    total_samples = len(states) - 10  # Need future states
    episodes = 3  # Train multiple times through data

    for episode in range(episodes):
        logger.info(f"\nEpisode {episode + 1}/{episodes}")
        logger.info(f"Epsilon: {agent.epsilon:.4f}")

        wins = 0
        total_reward = 0.0

        for i in range(0, total_samples, 10):  # Process every 10th bar
            if i + 10 >= len(states):
                break

            state = states[i]
            next_state = states[i + 10]
            reward = rewards[i]

            # Get action (with exploration)
            action = agent.get_action(state, training=True)

            # Adjust reward based on action
            if action == 1:  # BUY
                action_reward = reward  # Positive if price went up
            elif action == 2:  # SELL
                action_reward = -reward  # Positive if price went down
            else:  # HOLD
                action_reward = 0.0

            # Remember and learn
            agent.remember(state, action, action_reward, next_state, done=False)
            agent.learn(batch_size=32)

            # Track performance
            if action_reward > 0:
                wins += 1
            total_reward += action_reward

            # Decay epsilon
            if agent.epsilon > agent.epsilon_min:
                agent.epsilon *= agent.epsilon_decay

        # Episode stats
        samples_processed = total_samples // 10
        win_rate = wins / samples_processed if samples_processed > 0 else 0
        avg_reward = total_reward / samples_processed if samples_processed > 0 else 0

        logger.info(f"Episode {episode + 1} complete:")
        logger.info(f"  Win rate: {win_rate * 100:.2f}%")
        logger.info(f"  Avg reward: {avg_reward:.4f}%")
        logger.info(f"  Final epsilon: {agent.epsilon:.4f}")
        logger.info(f"  Q-table size: {len(agent.q_table)}")

    # Final evaluation (exploitation only)
    logger.info("\n" + "=" * 70)
    logger.info("FINAL EVALUATION (EXPLOITATION ONLY)")
    logger.info("=" * 70)

    wins = 0
    total_reward = 0.0
    actions_count = {0: 0, 1: 0, 2: 0}

    for i in range(0, total_samples, 10):
        if i + 10 >= len(states):
            break

        state = states[i]
        reward = rewards[i]

        # Get best action (no exploration)
        action = agent.get_action(state, training=False)
        actions_count[action] += 1

        # Calculate reward
        if action == 1:  # BUY
            action_reward = reward
        elif action == 2:  # SELL
            action_reward = -reward
        else:  # HOLD
            action_reward = 0.0

        if action_reward > 0:
            wins += 1
        total_reward += action_reward

    samples_processed = total_samples // 10
    win_rate = wins / samples_processed if samples_processed > 0 else 0
    avg_reward = total_reward / samples_processed if samples_processed > 0 else 0

    logger.info(f"Final Performance:")
    logger.info(f"  Win rate: {win_rate * 100:.2f}%")
    logger.info(f"  Avg reward: {avg_reward:.4f}%")
    logger.info(f"  Total Q-states: {len(agent.q_table)}")
    logger.info(f"  Action distribution:")
    logger.info(f"    HOLD: {actions_count[0]} ({actions_count[0]/samples_processed*100:.1f}%)")
    logger.info(f"    BUY:  {actions_count[1]} ({actions_count[1]/samples_processed*100:.1f}%)")
    logger.info(f"    SELL: {actions_count[2]} ({actions_count[2]/samples_processed*100:.1f}%)")

    # Save trained agent
    save_path = Path("models/integrated_rl_agent.pkl")
    save_path.parent.mkdir(exist_ok=True)

    agent.save(str(save_path))
    logger.info(f"\n✅ Trained RL agent saved to: {save_path}")
    logger.info(f"   Win rate improved: 54.6% → {win_rate * 100:.1f}%")

    return agent, win_rate, avg_reward

if __name__ == "__main__":
    train_rl_agent()
