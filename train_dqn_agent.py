"""
DQN Agent Training Script
Trains the Advanced DQN Agent on historical trade data

This script:
1. Loads historical trade data from logs/database
2. Extracts states, actions, and rewards
3. Trains the DQN agent using experience replay
4. Validates performance
5. Saves trained agent

STANDALONE - Does not affect current trading system
"""
import sys
import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import directly without going through __init__
import importlib.util

# Load DQN agent module directly
dqn_spec = importlib.util.spec_from_file_location(
    "advanced_dqn_agent",
    os.path.join(os.path.dirname(__file__), 'src/ai/advanced_dqn_agent.py')
)
dqn_module = importlib.util.module_from_spec(dqn_spec)
dqn_spec.loader.exec_module(dqn_module)
AdvancedDQNAgent = dqn_module.AdvancedDQNAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


class DQNTrainer:
    """
    Trains DQN Agent on historical trade data
    """
    
    def __init__(self, agent: AdvancedDQNAgent):
        self.agent = agent
        self.training_episodes = []
        self.validation_episodes = []
    
    def load_historical_data(self, data_path: str = None):
        """
        Load historical trade data
        
        Data sources:
        1. MT5 exported CSV files
        2. API logs (parsed)
        3. Database (if available)
        
        Expected format:
        - Timestamp
        - Symbol
        - All 173 features
        - Position state (profit, age, etc.)
        - Action taken (if any)
        - Outcome (profit/loss)
        """
        
        logger.info("=" * 70)
        logger.info("LOADING HISTORICAL DATA")
        logger.info("=" * 70)
        
        # Check for training data files
        data_dir = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
        
        training_files = []
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                if 'training_data' in file.lower() and file.endswith('.csv'):
                    training_files.append(os.path.join(data_dir, file))
        
        if not training_files:
            logger.warning("⚠️  No training data files found")
            logger.info(f"   Looked in: {data_dir}")
            logger.info("   Expected files: *training_data*.csv")
            return False
        
        logger.info(f"✅ Found {len(training_files)} training data files")
        
        # Load and combine data
        all_data = []
        for file_path in training_files:
            try:
                df = pd.read_csv(file_path)
                logger.info(f"   Loaded {file_path}: {len(df)} rows, {len(df.columns)} columns")
                all_data.append(df)
            except Exception as e:
                logger.error(f"   Failed to load {file_path}: {e}")
        
        if not all_data:
            logger.error("❌ No data loaded")
            return False
        
        # Combine all data
        combined_df = pd.concat(all_data, ignore_index=True)
        logger.info(f"✅ Total data: {len(combined_df)} rows")
        
        # Convert to episodes
        self._create_episodes_from_data(combined_df)
        
        return True
    
    def _create_episodes_from_data(self, df: pd.DataFrame):
        """
        Convert raw data into training episodes
        
        An episode is a complete trade from entry to exit
        Each step in the episode is a state-action-reward tuple
        """
        
        logger.info("")
        logger.info("Creating training episodes...")
        
        # Group by trade (if we have trade IDs)
        # Otherwise, create synthetic episodes
        
        # For now, create synthetic episodes from sequential data
        episode_length = 50  # Each episode is 50 bars
        
        num_episodes = len(df) // episode_length
        
        for i in range(num_episodes):
            start_idx = i * episode_length
            end_idx = start_idx + episode_length
            
            if end_idx > len(df):
                break
            
            episode_data = df.iloc[start_idx:end_idx]
            
            # Create episode
            episode = {
                'states': [],
                'actions': [],
                'rewards': [],
                'symbol': episode_data.iloc[0].get('symbol', 'UNKNOWN')
            }
            
            # Extract states and rewards
            for idx, row in episode_data.iterrows():
                # Create mock state (you'll need to extract real features)
                state = self._extract_state_from_row(row)
                episode['states'].append(state)
                
                # Mock action (HOLD for now)
                episode['actions'].append(0)  # HOLD
                
                # Mock reward (based on price change)
                if idx < len(episode_data) - 1:
                    next_row = episode_data.iloc[idx + 1]
                    price_change = (next_row.get('close', 0) - row.get('close', 0)) / row.get('close', 1)
                    episode['rewards'].append(price_change * 100)  # Reward as %
                else:
                    episode['rewards'].append(0)
            
            self.training_episodes.append(episode)
        
        logger.info(f"✅ Created {len(self.training_episodes)} training episodes")
        logger.info(f"   Average episode length: {episode_length} steps")
    
    def _extract_state_from_row(self, row: pd.Series) -> np.ndarray:
        """
        Extract state vector from data row
        
        This needs to match the state extraction in AdvancedDQNAgent
        """
        
        state = []
        
        # Extract features from row
        # This is a simplified version - you'll need to extract all 173 features
        state.append(row.get('close', 0))
        state.append(row.get('high', 0))
        state.append(row.get('low', 0))
        state.append(row.get('open', 0))
        state.append(row.get('volume', 0))
        state.append(row.get('rsi', 50))
        state.append(row.get('macd', 0))
        state.append(row.get('atr', 0))
        
        # Pad to 180 dimensions
        while len(state) < 180:
            state.append(0.0)
        
        return np.array(state, dtype=np.float32)
    
    def train(self, num_epochs: int = 100, save_every: int = 10):
        """
        Train the DQN agent
        
        Args:
            num_epochs: Number of training epochs
            save_every: Save checkpoint every N epochs
        """
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("STARTING DQN TRAINING")
        logger.info("=" * 70)
        logger.info(f"Episodes: {len(self.training_episodes)}")
        logger.info(f"Epochs: {num_epochs}")
        logger.info("")
        
        for epoch in range(num_epochs):
            epoch_loss = []
            epoch_rewards = []
            
            # Shuffle episodes
            np.random.shuffle(self.training_episodes)
            
            # Train on each episode
            for ep_idx, episode in enumerate(self.training_episodes):
                if ep_idx % 1000 == 0:
                    logger.info(f"   Processing episode {ep_idx}/{len(self.training_episodes)}...")
                states = episode['states']
                actions = episode['actions']
                rewards = episode['rewards']
                
                # Process each step in episode
                for t in range(len(states) - 1):
                    state = states[t]
                    action = actions[t]
                    reward = rewards[t]
                    next_state = states[t + 1]
                    done = (t == len(states) - 2)
                    
                    # Store experience
                    self.agent.store_experience(state, action, reward, next_state, done)
                    
                    # Train
                    loss = self.agent.train_step()
                    if loss is not None:
                        epoch_loss.append(loss)
                    
                    epoch_rewards.append(reward)
            
            # Log progress
            if len(epoch_loss) > 0:
                avg_loss = np.mean(epoch_loss)
                avg_reward = np.mean(epoch_rewards)
                logger.info(f"Epoch {epoch+1}/{num_epochs} | Loss: {avg_loss:.4f} | Avg Reward: {avg_reward:.4f} | Epsilon: {self.agent.epsilon:.3f}")
            
            # Save checkpoint
            if (epoch + 1) % save_every == 0:
                checkpoint_path = f"models/dqn_checkpoint_epoch_{epoch+1}.pt"
                self.agent.save(checkpoint_path)
                logger.info(f"   💾 Saved checkpoint: {checkpoint_path}")
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 70)
    
    def validate(self):
        """
        Validate trained agent on validation set
        """
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("VALIDATING AGENT")
        logger.info("=" * 70)
        
        if not self.validation_episodes:
            logger.warning("⚠️  No validation data available")
            return
        
        total_reward = 0
        action_counts = {action: 0 for action in self.agent.actions}
        
        for episode in self.validation_episodes:
            states = episode['states']
            
            for state in states:
                action_idx = self.agent.select_action(state, training=False)
                action_name = self.agent.get_action_name(action_idx)
                action_counts[action_name] += 1
        
        logger.info("Action distribution:")
        for action, count in action_counts.items():
            pct = (count / sum(action_counts.values())) * 100
            logger.info(f"   {action}: {count} ({pct:.1f}%)")
        
        logger.info("")
        logger.info("✅ Validation complete")


def main():
    """Main training function"""
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("DQN AGENT TRAINING")
    logger.info("=" * 70)
    logger.info("")
    
    # Initialize agent
    logger.info("Initializing DQN Agent...")
    agent = AdvancedDQNAgent(
        state_dim=180,
        learning_rate=0.0001,
        gamma=0.95,
        epsilon_start=1.0,
        epsilon_end=0.01,
        epsilon_decay=0.995,
        memory_size=50000,
        batch_size=64
    )
    
    # Initialize trainer
    trainer = DQNTrainer(agent)
    
    # Load data
    if not trainer.load_historical_data():
        logger.error("❌ Failed to load training data")
        logger.info("")
        logger.info("To train the DQN agent, you need historical data:")
        logger.info("1. Export training data from MT5")
        logger.info("2. Place CSV files in MQL5/Files directory")
        logger.info("3. Files should contain all 173 features")
        logger.info("")
        return
    
    # Train (reduced epochs for faster training)
    trainer.train(num_epochs=10, save_every=5)
    
    # Validate
    trainer.validate()
    
    # Save final model
    final_path = "models/advanced_dqn_agent_final.pt"
    agent.save(final_path)
    logger.info(f"")
    logger.info(f"✅ Final model saved: {final_path}")
    logger.info("")
    logger.info("=" * 70)
    logger.info("TRAINING COMPLETE - Agent ready for integration")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
