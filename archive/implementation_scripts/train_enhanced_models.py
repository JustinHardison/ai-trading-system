#!/usr/bin/env python3
"""
Phase 6: Train Multi-Model Ensemble on Enhanced Features
Trains XGBoost on 500+ features (replaces old 106-feature model)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from loguru import logger

from src.features.feature_engineer import FeatureEngineer
from src.features.regime_detector import RegimeDetector

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add("/tmp/enhanced_training.log", level="DEBUG")

def load_data(file_path: str) -> pd.DataFrame:
    """Load historical M1 data"""
    logger.info(f"Loading data from {file_path}...")
    
    # Try different delimiters
    for delimiter in ['\t', ',']:
        try:
            df = pd.read_csv(file_path, delimiter=delimiter)
            if len(df.columns) > 1:
                logger.info(f"✓ Loaded with delimiter '{delimiter}': {len(df)} rows, {len(df.columns)} columns")
                return df
        except Exception as e:
            continue
    
    raise ValueError("Could not load data with tab or comma delimiter")


def prepare_enhanced_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare enhanced features from raw OHLCV data
    
    This simulates the EA sending complete data
    """
    logger.info("=" * 70)
    logger.info("PREPARING ENHANCED FEATURES")
    logger.info("=" * 70)
    
    feature_engineer = FeatureEngineer()
    regime_detector = RegimeDetector(lookback_bars=100)
    
    all_features = []
    all_labels = []
    
    # We need at least 100 bars for regime detection
    min_idx = 100
    
    logger.info(f"Processing {len(df) - min_idx} samples...")
    
    for i in range(min_idx, len(df)):
        if i % 5000 == 0:
            logger.info(f"  Progress: {i - min_idx}/{len(df) - min_idx} ({(i - min_idx) / (len(df) - min_idx) * 100:.1f}%)")
        
        try:
            # Simulate EA request format
            request = {
                'account': {
                    'balance': 100000,
                    'equity': 100000,
                    'profit': 0,
                    'margin': 0,
                    'margin_free': 100000,
                    'leverage': 100,
                    'assets': 100000,
                    'liabilities': 0
                },
                'symbol_info': {
                    'symbol': 'US30',
                    'bid': float(df.loc[i, 'close']),
                    'ask': float(df.loc[i, 'close']) + 1.0,
                    'volume_min': 1.0,
                    'volume_max': 100.0,
                    'volume_step': 1.0,
                    'tick_value': 0.01,
                    'tick_size': 0.01,
                    'contract_size': 1.0,
                    'session_volume': float(df.loc[i, 'tick_volume']) if 'tick_volume' in df.columns else 1000,
                    'spread': 1.0,
                    'stops_level': 10,
                    'freeze_level': 5
                },
                'market_data': {
                    'M1': {
                        'close': df.loc[max(0, i-100):i+1, 'close'].tolist(),
                        'high': df.loc[max(0, i-100):i+1, 'high'].tolist(),
                        'low': df.loc[max(0, i-100):i+1, 'low'].tolist(),
                        'open': df.loc[max(0, i-100):i+1, 'open'].tolist(),
                        'volume': df.loc[max(0, i-100):i+1, 'tick_volume'].tolist() if 'tick_volume' in df.columns else [1000] * (i - max(0, i-100) + 1)
                    }
                },
                'indicators': {
                    'atr': float((df.loc[i, 'high'] - df.loc[i, 'low'])),
                    'rsi': 50.0,
                    'macd_main': 0.0,
                    'macd_signal': 0.0,
                    'ma20': float(df.loc[max(0, i-20):i+1, 'close'].mean()),
                    'ma50': float(df.loc[max(0, i-50):i+1, 'close'].mean()) if i >= 50 else float(df.loc[i, 'close']),
                    'bb_upper': 0,
                    'bb_middle': 0,
                    'bb_lower': 0,
                    'adx': 20.0,
                    'stoch_main': 50.0,
                    'stoch_signal': 50.0
                },
                'positions': [],
                'market_depth': []
            }
            
            # Engineer features
            features = feature_engineer.engineer_all_features(request)
            
            # Add regime features
            m1_df = pd.DataFrame(request['market_data']['M1'])
            regime_features = regime_detector.get_all_features(m1_df)
            features.update(regime_features)
            
            # Create label (price movement in next 10 bars)
            future_idx = min(i + 10, len(df) - 1)
            future_price = df.loc[future_idx, 'close']
            current_price = df.loc[i, 'close']
            price_change_pct = (future_price - current_price) / current_price * 100
            
            # Label: 1 = bullish (>0.05%), 0 = bearish (<-0.05%), skip neutral
            if price_change_pct > 0.05:
                label = 1
            elif price_change_pct < -0.05:
                label = 0
            else:
                continue  # Skip neutral samples
            
            all_features.append(features)
            all_labels.append(label)
            
        except Exception as e:
            if i % 5000 == 0:
                logger.warning(f"Failed at index {i}: {e}")
            continue
    
    logger.info(f"✓ Created {len(all_features)} samples with enhanced features")
    
    # Convert to DataFrame
    features_df = pd.DataFrame(all_features)
    features_df['label'] = all_labels
    
    return features_df


def train_xgboost_enhanced(features_df: pd.DataFrame):
    """Train XGBoost on enhanced features"""
    logger.info("=" * 70)
    logger.info("TRAINING XGBOOST ON ENHANCED FEATURES")
    logger.info("=" * 70)
    
    # Prepare data
    X = features_df.drop('label', axis=1)
    y = features_df['label']
    
    # Handle inf/nan
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    logger.info(f"Features: {X.shape[1]}")
    logger.info(f"Samples: {len(X)}")
    logger.info(f"Bullish: {sum(y == 1)} ({sum(y == 1) / len(y) * 100:.1f}%)")
    logger.info(f"Bearish: {sum(y == 0)} ({sum(y == 0) / len(y) * 100:.1f}%)")
    
    # Split train/test (80/20)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Train XGBoost
    logger.info("Training XGBoost...")
    import xgboost as xgb
    
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    
    logger.info(f"✓ Train Accuracy: {train_acc * 100:.2f}%")
    logger.info(f"✓ Test Accuracy: {test_acc * 100:.2f}%")
    
    # Save model
    model_path = Path("models/xgboost_enhanced_m1.pkl")
    model_path.parent.mkdir(exist_ok=True)
    
    with open(model_path, 'wb') as f:
        pickle.dump({
            'model': model,
            'feature_names': list(X.columns),
            'train_acc': train_acc,
            'test_acc': test_acc,
            'trained_date': datetime.now().isoformat()
        }, f)
    
    logger.info(f"✓ Saved model to {model_path}")
    
    return model, list(X.columns)


def main():
    logger.info("=" * 70)
    logger.info("PHASE 6: ENHANCED MODEL TRAINING")
    logger.info("=" * 70)
    
    # Load data
    df = load_data("us30_historical_data.csv")
    
    # Prepare enhanced features
    features_df = prepare_enhanced_features(df)
    
    # Save features for inspection
    features_df.to_csv("models/enhanced_features_sample.csv", index=False)
    logger.info(f"✓ Saved features sample to models/enhanced_features_sample.csv")
    
    # Train XGBoost
    model, feature_names = train_xgboost_enhanced(features_df)
    
    logger.info("=" * 70)
    logger.info("✅ TRAINING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Model: models/xgboost_enhanced_m1.pkl")
    logger.info(f"Features: {len(feature_names)}")
    logger.info(f"Next: Integrate into ml_api_integrated.py")


if __name__ == "__main__":
    main()
