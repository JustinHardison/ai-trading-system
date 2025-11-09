#!/usr/bin/env python3
"""
Train Forex Models - EURUSD, GBPUSD, USDJPY
============================================
Uses REAL historical M1 data from CSV files.
Same approach as US30/US100/US500 training.
Memory-safe, one model at a time.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
from datetime import datetime
import gc
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.features.simple_feature_engineer import SimpleFeatureEngineer

# Forex symbols to train
FOREX_SYMBOLS = ['eurusd', 'gbpusd', 'usdjpy']

# Data directory
DATA_DIR = '/Users/justinhardison/ai-trading-system'

# Model directory
MODELS_DIR = '/Users/justinhardison/ai-trading-system/models'

def load_forex_historical_data(symbol: str):
    """
    Load real historical M1 data for Forex symbol.
    """
    csv_file = os.path.join(DATA_DIR, f"{symbol}_m1_historical_data.csv")
    
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"Historical data not found: {csv_file}")
    
    print(f"Loading historical data from: {csv_file}")
    df = pd.read_csv(csv_file, sep='\t')  # Tab-separated
    
    # Rename columns to standard format
    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    print(f"✅ Loaded {len(df)} bars of historical data")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Date range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
    
    return df

def extract_features_from_data(df: pd.DataFrame, symbol: str, max_samples: int = 10000):
    """
    Extract features from real historical data using SimpleFeatureEngineer.
    """
    print(f"Extracting features from {len(df)} bars...")
    
    # Use SimpleFeatureEngineer (will use enhanced mode automatically if data available)
    feature_engineer = SimpleFeatureEngineer()
    
    # Prepare data in format expected by feature engineer
    # Assuming CSV has columns: timestamp, open, high, low, close, volume
    m1_data = df.copy()
    if 'timestamp' not in m1_data.columns and 'time' in m1_data.columns:
        m1_data = m1_data.rename(columns={'time': 'timestamp'})
    
    # Extract features for each window
    features_list = []
    labels_list = []
    
    # Use sliding window (need at least 200 bars for features)
    window_size = 200
    step_size = 50  # Extract every 50 bars to get more samples
    
    for i in range(window_size, min(len(df), max_samples * step_size), step_size):
        try:
            window_data = df.iloc[i-window_size:i].copy()
            
            # Create mock request format
            mock_request = {
                'm1': window_data,
                'symbol_info': {'symbol': symbol.upper()},
                'current_price': {'bid': window_data.iloc[-1]['close']}
            }
            
            # Extract features
            features = feature_engineer.engineer_features(mock_request)
            
            if features and len(features) > 0:
                features_list.append(features)
                
                # Generate label based on future price movement
                if i + 20 < len(df):  # Look ahead 20 bars
                    current_close = window_data.iloc[-1]['close']
                    future_close = df.iloc[i + 20]['close']
                    price_change_pct = ((future_close - current_close) / current_close) * 100
                    
                    # Label: BUY if price goes up >0.05%, SELL if down <-0.05%, else HOLD
                    if price_change_pct > 0.05:
                        labels_list.append(1)  # BUY
                    elif price_change_pct < -0.05:
                        labels_list.append(-1)  # SELL
                    else:
                        labels_list.append(0)  # HOLD
                else:
                    labels_list.append(0)  # HOLD for last bars
                    
        except Exception as e:
            continue
    
    if len(features_list) == 0:
        raise ValueError(f"No features extracted from data")
    
    # Convert to DataFrame
    X = pd.DataFrame(features_list)
    y = np.array(labels_list)
    
    label_counts = pd.Series(y).value_counts()
    print(f"✅ Extracted {len(X)} samples with {len(X.columns)} features")
    print(f"   Label distribution: SELL={label_counts.get(-1, 0)}, HOLD={label_counts.get(0, 0)}, BUY={label_counts.get(1, 0)}")
    
    return X, y

def train_forex_model(symbol: str, model_type: str = 'rf'):
    """Train a single Forex model using real historical data."""
    print(f"\n{'='*70}")
    print(f"Training {model_type.upper()} model for {symbol.upper()}")
    print(f"{'='*70}")
    
    # Load real historical data
    df = load_forex_historical_data(symbol)
    
    # Extract features from real data
    X, y = extract_features_from_data(df, symbol, max_samples=10000)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Train model
    if model_type == 'rf':
        print(f"Training RandomForest (n_estimators=100, max_depth=10)...")
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=2  # Limit CPU usage
        )
    else:  # gb
        print(f"Training GradientBoosting (n_estimators=100, max_depth=5)...")
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)
    
    print(f"✅ Training complete!")
    print(f"   Train accuracy: {train_score:.3f}")
    print(f"   Test accuracy: {test_score:.3f}")
    
    # Save model
    model_filename = f"{symbol}_{model_type}_model.pkl"
    model_path = os.path.join(MODELS_DIR, model_filename)
    joblib.dump(model, model_path)
    print(f"✅ Model saved: {model_filename}")
    
    # Clean up memory
    del model, X, y, X_train, X_test, y_train, y_test
    gc.collect()
    
    return train_score, test_score

def main():
    """Train all Forex models."""
    print("="*70)
    print("FOREX MODEL TRAINING - MEMORY SAFE")
    print("="*70)
    print(f"\nStarting training at {datetime.now()}")
    print(f"Models directory: {MODELS_DIR}")
    print(f"Forex symbols: {FOREX_SYMBOLS}")
    print(f"Memory-safe mode: Training one model at a time\n")
    
    results = {}
    
    for symbol in FOREX_SYMBOLS:
        print(f"\n{'#'*70}")
        print(f"# SYMBOL: {symbol.upper()}")
        print(f"{'#'*70}")
        
        # Train RandomForest
        rf_train, rf_test = train_forex_model(symbol, 'rf')
        results[f"{symbol}_rf"] = {'train': rf_train, 'test': rf_test}
        
        # Train GradientBoosting
        gb_train, gb_test = train_forex_model(symbol, 'gb')
        results[f"{symbol}_gb"] = {'train': gb_train, 'test': gb_test}
    
    # Summary
    print(f"\n{'='*70}")
    print("TRAINING COMPLETE - SUMMARY")
    print(f"{'='*70}")
    
    for symbol in FOREX_SYMBOLS:
        rf_key = f"{symbol}_rf"
        gb_key = f"{symbol}_gb"
        print(f"✅ {symbol.upper()} RandomForest: Train={results[rf_key]['train']:.3f}, Test={results[rf_key]['test']:.3f}")
        print(f"✅ {symbol.upper()} GradientBoosting: Train={results[gb_key]['train']:.3f}, Test={results[gb_key]['test']:.3f}")
    
    print(f"\nSuccess rate: {len(results)}/{len(FOREX_SYMBOLS)*2} models trained")
    print(f"Completed at {datetime.now()}")
    
    print(f"\n{'='*70}")
    print("Forex models are ready to use!")
    print("Restart API to load new models.")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
