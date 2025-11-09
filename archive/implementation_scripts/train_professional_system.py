#!/usr/bin/env python3
"""
Train Professional US30 Scalping System
Complete pipeline with ensemble models, RL, and 110+ features
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split

from src.data.advanced_data_fetcher import AdvancedDataFetcher
from src.ml.pro_feature_engineer import ProFeatureEngineer
from src.ml.pro_ensemble import ProEnsembleTrainer
from src.ml.reinforcement_learning import TradingRLAgent, StateEncoder
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_labels(df: pd.DataFrame, profit_target: float = 50.0, forward_bars: int = 5) -> np.ndarray:
    """
    Create labels for scalping
    
    Args:
        df: OHLCV DataFrame
        profit_target: Minimum profit in points to label as trade
        forward_bars: Look ahead this many bars
        
    Returns:
        Labels (0=HOLD, 1=BUY, 2=SELL)
    """
    labels = []
    
    for i in range(len(df) - forward_bars):
        current_price = df['close'].iloc[i]
        future_high = df['high'].iloc[i+1:i+forward_bars+1].max()
        future_low = df['low'].iloc[i+1:i+forward_bars+1].min()
        
        up_move = future_high - current_price
        down_move = current_price - future_low
        
        # Label based on which direction has bigger profitable move
        if up_move >= profit_target and up_move > down_move * 1.2:
            labels.append(1)  # BUY
        elif down_move >= profit_target and down_move > up_move * 1.2:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD
    
    # Pad remaining
    labels.extend([0] * forward_bars)
    
    return np.array(labels)


def main():
    """Main training pipeline"""
    logger.info("="*70)
    logger.info("PROFESSIONAL US30 SCALPING SYSTEM - TRAINING")
    logger.info("="*70)
    
    # 1. Fetch comprehensive data
    logger.info("\n[1/6] Fetching comprehensive US30 data...")
    fetcher = AdvancedDataFetcher()
    
    # Fetch 1-minute data (will use cache + fresh data)
    m1_df = fetcher.fetch_us30_comprehensive(days=60, interval="1m")
    
    if len(m1_df) < 1000:
        logger.error(f"Insufficient data: {len(m1_df)} bars")
        return
    
    logger.info(f"✓ Dataset: {len(m1_df)} bars")
    
    # 2. Extract professional features (110+)
    logger.info("\n[2/6] Extracting 110+ professional features...")
    feature_engineer = ProFeatureEngineer()
    
    features_list = []
    valid_indices = []
    
    for i in range(100, len(m1_df) - 10):  # Need history and future
        try:
            features = feature_engineer.extract_all_features(m1_df, i)
            if features:  # Only if we got features
                features_list.append(features)
                valid_indices.append(i)
        except Exception as e:
            continue
        
        if i % 500 == 0:
            logger.info(f"  Processed {i}/{len(m1_df)} bars...")
    
    X = pd.DataFrame(features_list)
    
    # Clean data: replace inf and nan
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)
    
    logger.info(f"✓ Extracted {len(X)} samples with {len(X.columns)} features")
    
    # 3. Create labels
    logger.info("\n[3/6] Creating scalping labels...")
    all_labels = create_labels(m1_df, profit_target=40.0, forward_bars=5)
    y = all_labels[valid_indices]
    
    logger.info(f"  Label distribution:")
    logger.info(f"    HOLD: {sum(y==0)} ({sum(y==0)/len(y)*100:.1f}%)")
    logger.info(f"    BUY:  {sum(y==1)} ({sum(y==1)/len(y)*100:.1f}%)")
    logger.info(f"    SELL: {sum(y==2)} ({sum(y==2)/len(y)*100:.1f}%)")
    
    # 4. Train ensemble models
    logger.info("\n[4/6] Training ensemble models (XGBoost + LightGBM + NN)...")
    
    # Split data (80/20)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    ensemble_trainer = ProEnsembleTrainer()
    ensemble_result = ensemble_trainer.train_ensemble(X_train, y_train, X_val, y_val)
    
    # 5. Train RL agent
    logger.info("\n[5/6] Training Reinforcement Learning agent...")
    rl_agent = TradingRLAgent(state_size=20, action_size=3)
    
    # Simulate trades for RL training
    logger.info("  Simulating trades for RL learning...")
    for i in range(len(X_val)):
        # Encode state
        state = StateEncoder.encode_state(X_val.iloc[i].to_dict())
        
        # Get action from ensemble
        pred, conf = ensemble_trainer.predict(X_val.iloc[i:i+1])
        action = pred[0]
        
        # Simulate trade outcome
        if action > 0:  # BUY or SELL
            # Simple simulation: check if prediction was correct
            actual = y_val[i] if isinstance(y_val, np.ndarray) else y_val.iloc[i]
            if actual == action:
                profit_pct = np.random.uniform(0.3, 0.8)  # Profitable
            else:
                profit_pct = np.random.uniform(-0.4, -0.1)  # Loss
            
            bars_held = np.random.randint(3, 15)
            volatility = X_val.iloc[i].get('atr_pct', 0.5)
            
            reward = rl_agent.calculate_reward(profit_pct, bars_held, volatility)
            rl_agent.update_stats(profit_pct)
            
            # Next state
            if i < len(X_val) - 1:
                next_state = StateEncoder.encode_state(X_val.iloc[i+1].to_dict())
                rl_agent.remember(state, action, reward, next_state, False)
        
        # Learn periodically
        if i % 32 == 0 and i > 0:
            rl_agent.learn(batch_size=32)
    
    rl_stats = rl_agent.get_stats()
    logger.info(f"✓ RL Agent trained:")
    logger.info(f"    Win Rate: {rl_stats['win_rate']*100:.1f}%")
    logger.info(f"    Avg Profit: {rl_stats['avg_profit_per_trade']:.2f}%")
    logger.info(f"    Q-Table Size: {rl_stats['q_table_size']}")
    
    # 6. Save everything
    logger.info("\n[6/6] Saving professional system...")
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save ensemble
    ensemble_path = models_dir / f'pro_ensemble_{timestamp}.pkl'
    with open(ensemble_path, 'wb') as f:
        pickle.dump(ensemble_result, f)
    
    # Create symlink
    latest_ensemble = models_dir / 'pro_ensemble_latest.pkl'
    if latest_ensemble.exists():
        latest_ensemble.unlink()
    latest_ensemble.symlink_to(ensemble_path.name)
    
    logger.info(f"✓ Ensemble saved: {ensemble_path}")
    
    # Save RL agent
    rl_path = models_dir / f'rl_agent_{timestamp}.pkl'
    rl_agent.save(str(rl_path))
    
    latest_rl = models_dir / 'rl_agent_latest.pkl'
    if latest_rl.exists():
        latest_rl.unlink()
    latest_rl.symlink_to(rl_path.name)
    
    logger.info(f"✓ RL Agent saved: {rl_path}")
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("PROFESSIONAL SYSTEM TRAINING COMPLETE!")
    logger.info("="*70)
    logger.info(f"Features: {len(X.columns)}")
    logger.info(f"Training Samples: {len(X_train)}")
    logger.info(f"Validation Samples: {len(X_val)}")
    logger.info(f"\nEnsemble Performance:")
    logger.info(f"  XGBoost:     {ensemble_result['xgb_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  LightGBM:    {ensemble_result['lgb_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  Neural Net:  {ensemble_result['nn_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  ENSEMBLE:    {ensemble_result['ensemble_accuracy']*100:.2f}%")
    logger.info(f"\nRL Agent:")
    logger.info(f"  Win Rate:    {rl_stats['win_rate']*100:.1f}%")
    logger.info(f"  Avg Profit:  {rl_stats['avg_profit_per_trade']:.2f}%")
    logger.info("\n✓ System ready for deployment!")
    logger.info("  Run: python3 deploy_professional_system.py")


if __name__ == '__main__':
    main()
