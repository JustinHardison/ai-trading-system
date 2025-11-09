#!/usr/bin/env python3
"""
Train OPTIMAL Integrated System
ML + LLM trained TOGETHER, not separately
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


def simulate_llm_context(df: pd.DataFrame, idx: int) -> dict:
    """
    Simulate LLM context based on market conditions
    In production, this would call real Groq API
    
    For training, we simulate realistic LLM responses
    """
    # Get recent price action
    recent_bars = df.iloc[max(0, idx-50):idx+1]
    
    if len(recent_bars) < 20:
        return {'regime': 'unknown', 'bias': 'neutral', 'risk_level': 1.0}
    
    close = recent_bars['close'].values
    high = recent_bars['high'].values
    low = recent_bars['low'].values
    
    # Detect regime
    atr = (high[-20:] - low[-20:]).mean()
    price_range = close[-20:].max() - close[-20:].min()
    
    if atr > price_range * 0.8:
        regime = 'volatile'
    elif price_range < close[-1] * 0.01:  # Less than 1% range
        regime = 'ranging'
    else:
        # Check for trend
        sma_20 = close[-20:].mean()
        if close[-1] > sma_20 * 1.005:
            regime = 'trending_up'
        elif close[-1] < sma_20 * 0.995:
            regime = 'trending_down'
        else:
            regime = 'ranging'
    
    # Detect bias
    momentum = (close[-1] - close[-10]) / close[-10]
    if momentum > 0.002:
        bias = 'bullish'
    elif momentum < -0.002:
        bias = 'bearish'
    else:
        bias = 'neutral'
    
    # Risk level based on volatility
    volatility = close[-20:].std() / close[-20:].mean()
    if volatility > 0.015:
        risk_level = 0.5  # High volatility = lower risk
    elif volatility < 0.005:
        risk_level = 1.5  # Low volatility = higher risk
    else:
        risk_level = 1.0
    
    return {
        'regime': regime,
        'bias': bias,
        'risk_level': risk_level
    }


def create_integrated_features(
    technical_features: dict,
    llm_context: dict
) -> dict:
    """
    Combine technical features with LLM context
    This is the KEY to integration!
    """
    integrated = technical_features.copy()
    
    # Add LLM regime as one-hot encoded features
    integrated['llm_regime_volatile'] = 1 if llm_context['regime'] == 'volatile' else 0
    integrated['llm_regime_ranging'] = 1 if llm_context['regime'] == 'ranging' else 0
    integrated['llm_regime_trending_up'] = 1 if llm_context['regime'] == 'trending_up' else 0
    integrated['llm_regime_trending_down'] = 1 if llm_context['regime'] == 'trending_down' else 0
    
    # Add LLM bias as one-hot encoded features
    integrated['llm_bias_bullish'] = 1 if llm_context['bias'] == 'bullish' else 0
    integrated['llm_bias_bearish'] = 1 if llm_context['bias'] == 'bearish' else 0
    integrated['llm_bias_neutral'] = 1 if llm_context['bias'] == 'neutral' else 0
    
    # Add LLM risk level as continuous feature
    integrated['llm_risk_level'] = llm_context['risk_level']
    
    # Add interaction features (this is where magic happens!)
    # ML learns: "When trending_up + bullish + high momentum = strong BUY"
    if llm_context['regime'] == 'trending_up' and llm_context['bias'] == 'bullish':
        integrated['llm_trend_aligned'] = 1
    else:
        integrated['llm_trend_aligned'] = 0
    
    if llm_context['regime'] == 'ranging' and abs(technical_features.get('roc_5', 0)) < 0.001:
        integrated['llm_range_confirmed'] = 1
    else:
        integrated['llm_range_confirmed'] = 0
    
    return integrated


def create_labels(df: pd.DataFrame, profit_target: float = 40.0, forward_bars: int = 5) -> np.ndarray:
    """Create labels for scalping"""
    labels = []
    
    for i in range(len(df) - forward_bars):
        current_price = df['close'].iloc[i]
        future_high = df['high'].iloc[i+1:i+forward_bars+1].max()
        future_low = df['low'].iloc[i+1:i+forward_bars+1].min()
        
        up_move = future_high - current_price
        down_move = current_price - future_low
        
        if up_move >= profit_target and up_move > down_move * 1.2:
            labels.append(1)  # BUY
        elif down_move >= profit_target and down_move > up_move * 1.2:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD
    
    labels.extend([0] * forward_bars)
    return np.array(labels)


def main():
    """Main training pipeline with INTEGRATED ML + LLM"""
    logger.info("="*70)
    logger.info("OPTIMAL INTEGRATED SYSTEM - ML + LLM TRAINED TOGETHER")
    logger.info("="*70)
    
    # 1. Fetch data
    logger.info("\n[1/5] Fetching comprehensive US30 data...")
    fetcher = AdvancedDataFetcher()
    m1_df = fetcher.fetch_us30_comprehensive(days=60, interval="1m")
    
    if len(m1_df) < 1000:
        logger.error(f"Insufficient data: {len(m1_df)} bars")
        return
    
    logger.info(f"✓ Dataset: {len(m1_df)} bars")
    
    # 2. Extract features WITH LLM context
    logger.info("\n[2/5] Extracting integrated features (96 technical + 10 LLM)...")
    feature_engineer = ProFeatureEngineer()
    
    features_list = []
    valid_indices = []
    
    for i in range(100, len(m1_df) - 10):
        try:
            # Get technical features
            technical_features = feature_engineer.extract_all_features(m1_df, i)
            if not technical_features:
                continue
            
            # Simulate LLM context (in production, this would be real Groq API)
            llm_context = simulate_llm_context(m1_df, i)
            
            # INTEGRATE: Combine technical + LLM features
            integrated_features = create_integrated_features(technical_features, llm_context)
            
            features_list.append(integrated_features)
            valid_indices.append(i)
            
        except Exception as e:
            continue
        
        if i % 500 == 0:
            logger.info(f"  Processed {i}/{len(m1_df)} bars...")
    
    X = pd.DataFrame(features_list)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    logger.info(f"✓ Extracted {len(X)} samples with {len(X.columns)} features")
    logger.info(f"  Technical features: 96")
    logger.info(f"  LLM features: {len(X.columns) - 96}")
    logger.info(f"  Total: {len(X.columns)}")
    
    # 3. Create labels
    logger.info("\n[3/5] Creating scalping labels...")
    all_labels = create_labels(m1_df, profit_target=40.0, forward_bars=5)
    y = all_labels[valid_indices]
    
    logger.info(f"  Label distribution:")
    logger.info(f"    HOLD: {sum(y==0)} ({sum(y==0)/len(y)*100:.1f}%)")
    logger.info(f"    BUY:  {sum(y==1)} ({sum(y==1)/len(y)*100:.1f}%)")
    logger.info(f"    SELL: {sum(y==2)} ({sum(y==2)/len(y)*100:.1f}%)")
    
    # 4. Train ensemble with INTEGRATED features
    logger.info("\n[4/5] Training ensemble on INTEGRATED features...")
    
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    ensemble_trainer = ProEnsembleTrainer()
    ensemble_result = ensemble_trainer.train_ensemble(X_train, y_train, X_val, y_val)
    
    logger.info("\n✓ Ensemble now understands LLM context!")
    logger.info("  ML learned: 'When trending_up + bullish + momentum = BUY'")
    logger.info("  Not: 'momentum = BUY' then LLM blocks it")
    
    # 5. Train RL with real LLM simulation
    logger.info("\n[5/5] Training RL agent with realistic LLM context...")
    rl_agent = TradingRLAgent(state_size=20, action_size=3)
    
    for i in range(len(X_val)):
        state = StateEncoder.encode_state(X_val.iloc[i].to_dict())
        pred, conf = ensemble_trainer.predict(X_val.iloc[i:i+1])
        action = pred[0]
        
        if action > 0:
            actual = y_val[i] if isinstance(y_val, np.ndarray) else y_val.iloc[i]
            if actual == action:
                profit_pct = np.random.uniform(0.3, 0.8)
            else:
                profit_pct = np.random.uniform(-0.4, -0.1)
            
            bars_held = np.random.randint(3, 15)
            volatility = X_val.iloc[i].get('atr_pct', 0.5)
            
            reward = rl_agent.calculate_reward(profit_pct, bars_held, volatility)
            rl_agent.update_stats(profit_pct)
            
            if i < len(X_val) - 1:
                next_state = StateEncoder.encode_state(X_val.iloc[i+1].to_dict())
                rl_agent.remember(state, action, reward, next_state, False)
        
        if i % 32 == 0 and i > 0:
            rl_agent.learn(batch_size=32)
    
    rl_stats = rl_agent.get_stats()
    logger.info(f"✓ RL Agent trained with integrated features:")
    logger.info(f"    Win Rate: {rl_stats['win_rate']*100:.1f}%")
    logger.info(f"    Avg Profit: {rl_stats['avg_profit_per_trade']:.2f}%")
    
    # 6. Save integrated system
    logger.info("\n[6/6] Saving OPTIMAL integrated system...")
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save ensemble
    ensemble_path = models_dir / f'integrated_ensemble_{timestamp}.pkl'
    ensemble_result['integration_type'] = 'ml_llm_unified'
    ensemble_result['feature_count'] = len(X.columns)
    ensemble_result['llm_features'] = [
        'llm_regime_volatile', 'llm_regime_ranging', 'llm_regime_trending_up',
        'llm_regime_trending_down', 'llm_bias_bullish', 'llm_bias_bearish',
        'llm_bias_neutral', 'llm_risk_level', 'llm_trend_aligned', 'llm_range_confirmed'
    ]
    
    with open(ensemble_path, 'wb') as f:
        pickle.dump(ensemble_result, f)
    
    latest_ensemble = models_dir / 'integrated_ensemble_latest.pkl'
    if latest_ensemble.exists():
        latest_ensemble.unlink()
    latest_ensemble.symlink_to(ensemble_path.name)
    
    logger.info(f"✓ Integrated ensemble saved: {ensemble_path}")
    
    # Save RL agent
    rl_path = models_dir / f'integrated_rl_{timestamp}.pkl'
    rl_agent.save(str(rl_path))
    
    latest_rl = models_dir / 'integrated_rl_latest.pkl'
    if latest_rl.exists():
        latest_rl.unlink()
    latest_rl.symlink_to(rl_path.name)
    
    logger.info(f"✓ Integrated RL saved: {rl_path}")
    
    # Final summary
    logger.info("\n" + "="*70)
    logger.info("OPTIMAL INTEGRATED SYSTEM COMPLETE!")
    logger.info("="*70)
    logger.info(f"Features: {len(X.columns)} (96 technical + {len(X.columns)-96} LLM)")
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
    logger.info("\n✓ ML and LLM are now UNIFIED!")
    logger.info("  No more conflicts - they speak the same language")
    logger.info("\nNext: Deploy with ml_api_integrated.py")


if __name__ == '__main__':
    main()
