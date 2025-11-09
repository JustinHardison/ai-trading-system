"""
Train Deep RL Agent on Historical Data
Phase 2 & 3 - World-Class AI
"""

import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.ml.deep_rl_agent import DeepRLAgent

def train_deep_rl(csv_file='us30_historical_data.csv'):
    """Train Deep RL agent on historical data"""
    
    print("=" * 80)
    print("TRAINING DEEP RL AGENT - PHASE 2 & 3 UPGRADE")
    print("=" * 80)
    
    # Load data
    print(f"\n📊 Loading data from {csv_file}...")
    df = pd.read_csv(csv_file, sep='\t')
    df.columns = [c.lower().strip() for c in df.columns]
    
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], format='%Y.%m.%d %H:%M')
    
    print(f"✅ Loaded {len(df)} bars")
    if 'time' in df.columns:
        print(f"   Period: {df['time'].min()} to {df['time'].max()}")
    
    # Initialize Deep RL agent
    agent = DeepRLAgent(state_size=6, action_size=9)
    
    print("\n🧠 Training Deep RL Agent...")
    print("   Using: Deep Q-Network (DQN)")
    print("   Features: Experience replay + Target network")
    
    position = None
    trades_simulated = 0
    total_reward = 0
    episode = 0
    update_target_every = 100
    
    for i in range(100, len(df)):
        # Calculate features
        current_bar = df.iloc[i]
        recent_closes = df.iloc[i-20:i]['close'].values
        recent_volumes = df.iloc[i-20:i]['tick_volume'].values
        
        # Simple features
        if len(recent_closes) >= 5:
            momentum = (recent_closes[-1] - recent_closes[-5]) / recent_closes[-5] * 100
        else:
            momentum = 0
        
        if len(recent_volumes) > 0 and recent_volumes.mean() > 0:
            volume_ratio = recent_volumes[-1] / recent_volumes.mean()
        else:
            volume_ratio = 1.0
        
        if len(recent_closes) >= 10:
            trend_strength = abs((recent_closes[-1] - recent_closes[-10]) / recent_closes[-10])
        else:
            trend_strength = 0
        
        # Simulate position
        if position is None:
            # Random entry for training
            if np.random.random() > 0.95:
                position = {
                    'entry_price': df.iloc[i]['close'],
                    'entry_bar': i,
                    'direction': 'BUY' if np.random.random() > 0.5 else 'SELL',
                    'entry_state': None
                }
        else:
            # Calculate P&L
            current_price = df.iloc[i]['close']
            if position['direction'] == 'BUY':
                profit = current_price - position['entry_price']
            else:
                profit = position['entry_price'] - current_price
            
            profit_dollars = profit * 10
            bars_held = i - position['entry_bar']
            
            # Build state
            state = {
                'floating_profit': profit_dollars,
                'profit_velocity': profit_dollars / max(bars_held, 1),
                'momentum': momentum,
                'volume_ratio': volume_ratio,
                'trend_strength': trend_strength,
                'time_in_trade': bars_held
            }
            
            # Get state vector
            state_vector = agent.get_state_vector(state)
            
            # Store entry state
            if position['entry_state'] is None:
                position['entry_state'] = state_vector
            
            # Get action
            action_id, action_name, confidence = agent.get_action(state, training=True)
            
            # Check if trade should close
            done = False
            reward = 0
            
            if action_name in ['TAKE_PROFIT_FULL', 'STOP_LOSS'] or bars_held > 50:
                # Close position
                reward = profit_dollars / max(bars_held, 1)  # $/bar
                done = True
                trades_simulated += 1
                total_reward += reward
                
                # Store experience
                agent.remember(
                    position['entry_state'],
                    action_id,
                    reward,
                    state_vector,
                    done
                )
                
                # Train
                if len(agent.memory) >= agent.batch_size:
                    loss = agent.replay()
                
                # Update target network
                if trades_simulated % update_target_every == 0:
                    agent.update_target_network()
                    print(f"   Updated target network at trade {trades_simulated}")
                
                position = None
                episode += 1
                
                if trades_simulated % 100 == 0:
                    avg_reward = total_reward / trades_simulated
                    print(f"   Trades: {trades_simulated}, Avg Reward: ${avg_reward:.2f}/bar, Epsilon: {agent.epsilon:.3f}")
    
    print(f"\n✅ Training complete!")
    print(f"   Trades simulated: {trades_simulated}")
    print(f"   Total reward: ${total_reward:.2f}")
    print(f"   Average reward: ${total_reward/max(trades_simulated, 1):.2f}/trade")
    print(f"   Memory size: {len(agent.memory)}")
    print(f"   Epsilon: {agent.epsilon:.3f}")
    
    # Save model
    output_file = 'models/deep_rl_agent.pth'
    agent.save(output_file)
    print(f"\n💾 Saved to {output_file}")
    
    return agent

if __name__ == "__main__":
    csv_file = "us30_historical_data.csv"
    
    import os
    if not os.path.exists(csv_file):
        print(f"\n❌ File not found: {csv_file}")
        print("\nRun the export script first:")
        print("1. Compile ExportHistoricalData.mq5 (F7)")
        print("2. Run on US30 M1 chart")
        print("3. Run this script again")
    else:
        train_deep_rl(csv_file)
