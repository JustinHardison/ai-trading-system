"""
Train ML/RL from MT5 exported historical data
No EA needed - just export CSV from MT5
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.ml.multi_action_rl import MultiActionRLAgent
from src.ml.pro_feature_engineer import ProFeatureEngineer

def train_from_csv(csv_file):
    """Train RL agent from MT5 exported CSV data"""
    
    print("=" * 80)
    print("TRAINING FROM MT5 HISTORICAL DATA")
    print("=" * 80)
    
    # Load data
    print(f"\n📊 Loading data from {csv_file}...")
    df = pd.read_csv(csv_file, sep='\t')  # Tab-separated
    
    # Rename columns to match our format
    df.columns = [c.lower().strip() for c in df.columns]
    
    # Parse time column properly
    if 'time' in df.columns:
        # Convert time strings to datetime objects
        df['time'] = pd.to_datetime(df['time'], format='%Y.%m.%d %H:%M')
    
    print(f"✅ Loaded {len(df)} bars")
    if 'time' in df.columns:
        print(f"   Period: {df['time'].min()} to {df['time'].max()}")
    print(f"   Columns: {list(df.columns)}")
    
    # Initialize
    rl_agent = MultiActionRLAgent()
    feature_engineer = ProFeatureEngineer()
    
    # Simulate trades and learn
    print("\n🧠 Training RL agent...")
    
    position = None
    trades_simulated = 0
    
    for i in range(100, len(df)):
        # Extract features - use simple approach without feature engineer
        current_bar = df.iloc[i]
        
        # Calculate basic features manually
        recent_closes = df.iloc[i-20:i]['close'].values
        
        # Simple momentum (ROC)
        if len(recent_closes) >= 5:
            momentum = (recent_closes[-1] - recent_closes[-5]) / recent_closes[-5] * 100
        else:
            momentum = 0
        
        # Simple volume ratio
        recent_volumes = df.iloc[i-20:i]['tick_volume'].values
        if len(recent_volumes) > 0 and recent_volumes.mean() > 0:
            volume_ratio = recent_volumes[-1] / recent_volumes.mean()
        else:
            volume_ratio = 1.0
        
        # Trend strength (simple)
        if len(recent_closes) >= 10:
            trend_strength = abs((recent_closes[-1] - recent_closes[-10]) / recent_closes[-10])
        else:
            trend_strength = 0
        
        features = {
            'roc_5': momentum,
            'volume_ratio': volume_ratio,
            'trend_strength': trend_strength
        }
        
        if features is None:
            continue
        
        # Simulate position
        if position is None:
            # Random entry for training
            if np.random.random() > 0.95:  # 5% entry rate
                position = {
                    'entry_price': df.iloc[i]['close'],
                    'entry_bar': i,
                    'direction': 'BUY' if np.random.random() > 0.5 else 'SELL'
                }
        else:
            # Calculate P&L
            current_price = df.iloc[i]['close']
            if position['direction'] == 'BUY':
                profit = current_price - position['entry_price']
            else:
                profit = position['entry_price'] - current_price
            
            profit_dollars = profit * 10  # $10 per point for US30
            bars_held = i - position['entry_bar']
            
            # Build state
            state = {
                'floating_profit': profit_dollars,
                'profit_velocity': profit_dollars / max(bars_held, 1),
                'momentum': features.get('roc_5', 0),
                'volume_ratio': features.get('volume_ratio', 1.0),
                'trend_strength': features.get('trend_strength', 0),
                'time_in_trade': bars_held
            }
            
            # Get action
            action_id, action_name, confidence = rl_agent.get_action(state)
            
            # Simulate outcome
            if action_name in ['TAKE_PROFIT_FULL', 'STOP_LOSS'] or bars_held > 50:
                # Close position
                reward = profit_dollars / max(bars_held, 1)  # $/bar
                rl_agent.learn_from_tick(profit_dollars)
                position = None
                trades_simulated += 1
                
                if trades_simulated % 100 == 0:
                    print(f"   Simulated {trades_simulated} trades, Q-table: {len(rl_agent.q_table)} states")
    
    print(f"\n✅ Training complete!")
    print(f"   Trades simulated: {trades_simulated}")
    print(f"   States learned: {len(rl_agent.q_table)}")
    print(f"   Decisions made: {rl_agent.total_decisions}")
    
    # Save Q-table
    output_file = 'models/multi_action_q_table.pkl'
    rl_agent.save_q_table(output_file)
    print(f"\n💾 Saved to {output_file}")
    
    return rl_agent

if __name__ == "__main__":
    # Example usage
    csv_file = "us30_historical_data.csv"
    
    if not Path(csv_file).exists():
        print(f"\n❌ File not found: {csv_file}")
        print("\nTo export from MT5:")
        print("1. Open US30 chart")
        print("2. Right-click → 'Save as' → CSV")
        print("3. Save as 'us30_historical_data.csv'")
        print("4. Run this script again")
    else:
        train_from_csv(csv_file)
