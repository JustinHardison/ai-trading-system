#!/usr/bin/env python3
"""
Train Swing Trading System
SEPARATE from scalping - no interference!
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split

from src.data.advanced_data_fetcher import AdvancedDataFetcher
from src.ml.swing_feature_engineer import SwingFeatureEngineer
from src.ml.pro_ensemble import ProEnsembleTrainer
from src.ml.reinforcement_learning import TradingRLAgent, StateEncoder
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_swing_labels(h1_df: pd.DataFrame, profit_target: float = 500.0, forward_bars: int = 48) -> np.ndarray:
    """
    Create labels for swing trading
    
    Args:
        h1_df: H1 timeframe data
        profit_target: Minimum profit in points (500-2000 for swings)
        forward_bars: Look ahead 48 H1 bars = 2 days
        
    Returns:
        Labels (0=HOLD, 1=LONG, 2=SHORT)
    """
    labels = []
    
    for i in range(len(h1_df) - forward_bars):
        current_price = h1_df['close'].iloc[i]
        future_high = h1_df['high'].iloc[i+1:i+forward_bars+1].max()
        future_low = h1_df['low'].iloc[i+1:i+forward_bars+1].min()
        
        up_move = future_high - current_price
        down_move = current_price - future_low
        
        # Label based on which direction has bigger swing move
        if up_move >= profit_target and up_move > down_move * 1.5:
            labels.append(1)  # LONG
        elif down_move >= profit_target and down_move > up_move * 1.5:
            labels.append(2)  # SHORT
        else:
            labels.append(0)  # HOLD
    
    # Pad remaining
    labels.extend([0] * forward_bars)
    
    return np.array(labels)


def main():
    """Main swing training pipeline"""
    logger.info("="*70)
    logger.info("SWING TRADING SYSTEM - TRAINING (SEPARATE FROM SCALPING)")
    logger.info("="*70)
    
    # 1. Fetch swing data (H1, H4, D1)
    logger.info("\n[1/5] Fetching swing trading data (H1/H4/D1)...")
    fetcher = AdvancedDataFetcher()
    
    # Fetch multiple timeframes
    h1_df = fetcher.fetch_us30_comprehensive(days=60, interval="1h")
    h4_df = fetcher.fetch_us30_comprehensive(days=60, interval="4h")
    d1_df = fetcher.fetch_us30_comprehensive(days=60, interval="1d")
    
    logger.info(f"✓ H1 data: {len(h1_df)} bars")
    logger.info(f"✓ H4 data: {len(h4_df)} bars")
    logger.info(f"✓ D1 data: {len(d1_df)} bars")
    
    if len(h1_df) < 250:
        logger.error(f"Insufficient H1 data: {len(h1_df)} bars (need 250+)")
        return
    
    logger.info(f"✓ Using {len(h1_df)} H1 bars for swing training")
    
    # 2. Extract swing features (150+)
    logger.info("\n[2/5] Extracting 150+ swing features...")
    feature_engineer = SwingFeatureEngineer()
    
    features_list = []
    valid_indices = []
    
    for i in range(200, len(h1_df) - 50):  # Need history and future
        try:
            features = feature_engineer.extract_all_features(h1_df, h4_df, d1_df, i)
            if features and len(features) > 50:  # Only if we got features
                features_list.append(features)
                valid_indices.append(i)
        except Exception as e:
            continue
        
        if i % 200 == 0:
            logger.info(f"  Processed {i}/{len(h1_df)} bars...")
    
    X = pd.DataFrame(features_list)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    logger.info(f"✓ Extracted {len(X)} samples with {len(X.columns) if len(X) > 0 else 0} features")
    
    if len(X) == 0:
        logger.error("No features extracted! Not enough data for swing trading.")
        logger.info("Need more H1 bars or adjust feature extraction logic.")
        return
    
    # 3. Create swing labels (500+ point targets)
    logger.info("\n[3/5] Creating swing labels (500+ point targets)...")
    all_labels = create_swing_labels(h1_df, profit_target=500.0, forward_bars=48)
    y = all_labels[valid_indices]
    
    if len(y) == 0:
        logger.error("No labels created!")
        return
    
    logger.info(f"  Label distribution:")
    logger.info(f"    HOLD:  {sum(y==0)} ({sum(y==0)/len(y)*100:.1f}%)")
    logger.info(f"    LONG:  {sum(y==1)} ({sum(y==1)/len(y)*100:.1f}%)")
    logger.info(f"    SHORT: {sum(y==2)} ({sum(y==2)/len(y)*100:.1f}%)")
    
    # 4. Train swing ensemble (SEPARATE from scalping!)
    logger.info("\n[4/5] Training SWING ensemble models...")
    
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    swing_ensemble = ProEnsembleTrainer()
    ensemble_result = swing_ensemble.train_ensemble(X_train, y_train, X_val, y_val)
    
    # 5. Train swing RL agent (SEPARATE from scalping!)
    logger.info("\n[5/5] Training SWING RL agent...")
    swing_rl = TradingRLAgent(state_size=20, action_size=3)
    
    # Simulate swing trades
    for i in range(len(X_val)):
        state = StateEncoder.encode_state(X_val.iloc[i].to_dict())
        pred, conf = swing_ensemble.predict(X_val.iloc[i:i+1])
        action = pred[0]
        
        if action > 0:
            actual = y_val[i] if isinstance(y_val, np.ndarray) else y_val.iloc[i]
            if actual == action:
                profit_pct = np.random.uniform(1.5, 5.0)  # Swing profits larger
            else:
                profit_pct = np.random.uniform(-2.0, -0.5)  # Swing losses larger
            
            bars_held = np.random.randint(24, 120)  # 1-5 days
            volatility = X_val.iloc[i].get('atr_14_h1', 0.01)
            
            reward = swing_rl.calculate_reward(profit_pct, bars_held, volatility)
            swing_rl.update_stats(profit_pct)
            
            if i < len(X_val) - 1:
                next_state = StateEncoder.encode_state(X_val.iloc[i+1].to_dict())
                swing_rl.remember(state, action, reward, next_state, False)
        
        if i % 32 == 0 and i > 0:
            swing_rl.learn(batch_size=32)
    
    rl_stats = swing_rl.get_stats()
    logger.info(f"✓ Swing RL Agent trained:")
    logger.info(f"    Win Rate: {rl_stats['win_rate']*100:.1f}%")
    logger.info(f"    Avg Profit: {rl_stats['avg_profit_per_trade']:.2f}%")
    
    # 6. Save SWING models (SEPARATE directory!)
    logger.info("\n[6/6] Saving SWING models (separate from scalping)...")
    models_dir = Path('models/swing')
    models_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save swing ensemble
    swing_ensemble_path = models_dir / f'swing_ensemble_{timestamp}.pkl'
    ensemble_result['model_type'] = 'swing_trading'
    ensemble_result['timeframes'] = ['H1', 'H4', 'D1']
    ensemble_result['feature_count'] = len(X.columns)
    
    with open(swing_ensemble_path, 'wb') as f:
        pickle.dump(ensemble_result, f)
    
    latest_swing_ensemble = models_dir / 'swing_ensemble_latest.pkl'
    if latest_swing_ensemble.exists():
        latest_swing_ensemble.unlink()
    latest_swing_ensemble.symlink_to(swing_ensemble_path.name)
    
    logger.info(f"✓ Swing ensemble saved: {swing_ensemble_path}")
    
    # Save swing RL
    swing_rl_path = models_dir / f'swing_rl_{timestamp}.pkl'
    swing_rl.save(str(swing_rl_path))
    
    latest_swing_rl = models_dir / 'swing_rl_latest.pkl'
    if latest_swing_rl.exists():
        latest_swing_rl.unlink()
    latest_swing_rl.symlink_to(swing_rl_path.name)
    
    logger.info(f"✓ Swing RL saved: {swing_rl_path}")
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("SWING TRADING SYSTEM COMPLETE!")
    logger.info("="*70)
    logger.info(f"Features: {len(X.columns)}")
    logger.info(f"Training Samples: {len(X_train)}")
    logger.info(f"Validation Samples: {len(X_val)}")
    logger.info(f"\nSwing Ensemble Performance:")
    logger.info(f"  XGBoost:     {ensemble_result['xgb_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  LightGBM:    {ensemble_result['lgb_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  Neural Net:  {ensemble_result['nn_metrics']['accuracy']*100:.2f}%")
    logger.info(f"  ENSEMBLE:    {ensemble_result['ensemble_accuracy']*100:.2f}%")
    logger.info(f"\nSwing RL Agent:")
    logger.info(f"  Win Rate:    {rl_stats['win_rate']*100:.1f}%")
    logger.info(f"  Avg Profit:  {rl_stats['avg_profit_per_trade']:.2f}%")
    logger.info("\n✓ Swing models saved separately from scalping!")
    logger.info("  Scalping: models/integrated_ensemble_latest.pkl")
    logger.info("  Swing:    models/swing/swing_ensemble_latest.pkl")
    logger.info("\nNext: Integrate into API with dual-mode support")


if __name__ == '__main__':
    main()
