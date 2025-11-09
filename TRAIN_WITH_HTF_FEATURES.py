#!/usr/bin/env python3
"""
Train ML models with Higher Timeframe (HTF) features
Adds H1, H4, D1 trend/momentum/RSI features to match exit logic

This creates COHESIVE models that use the same timeframes as entry/exit logic.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from datetime import datetime
import warnings
import os
warnings.filterwarnings('ignore')

DATA_DIR = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
MODELS_DIR = "/Users/justinhardison/ai-trading-system/models"

SYMBOLS = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']


def add_htf_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Higher Timeframe features to match what entry/exit logic uses.
    
    These are SIMULATED from the base data since we don't have actual H1/H4/D1 bars,
    but they capture the same concepts:
    - Trend direction over longer periods
    - Momentum over longer periods
    - RSI smoothed over longer periods
    """
    print("   Adding HTF features...")
    
    # H1 equivalent features (using ~12 bars of M5 = 1 hour)
    h1_period = 12
    
    # H1 Trend (SMA-based)
    df['h1_sma_20'] = df['close'].rolling(window=h1_period * 20).mean()
    df['h1_trend'] = (df['close'] > df['h1_sma_20']).astype(float)
    df['h1_trend'] = df['h1_trend'].rolling(window=h1_period).mean()  # Smooth it
    
    # H1 Momentum (rate of change over H1 period)
    df['h1_momentum'] = df['close'].pct_change(periods=h1_period * 5)
    df['h1_momentum'] = df['h1_momentum'].clip(-0.05, 0.05) / 0.05  # Normalize to -1 to 1
    
    # H1 RSI (smoothed)
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=h1_period * 14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=h1_period * 14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['h1_rsi'] = 100 - (100 / (1 + rs))
    
    # H4 equivalent features (using ~48 bars of M5 = 4 hours)
    h4_period = 48
    
    df['h4_sma_20'] = df['close'].rolling(window=h4_period * 20).mean()
    df['h4_trend'] = (df['close'] > df['h4_sma_20']).astype(float)
    df['h4_trend'] = df['h4_trend'].rolling(window=h4_period).mean()
    
    df['h4_momentum'] = df['close'].pct_change(periods=h4_period * 5)
    df['h4_momentum'] = df['h4_momentum'].clip(-0.05, 0.05) / 0.05
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=h4_period * 14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=h4_period * 14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['h4_rsi'] = 100 - (100 / (1 + rs))
    
    # D1 equivalent features (using ~288 bars of M5 = 1 day)
    d1_period = 288
    
    df['d1_sma_20'] = df['close'].rolling(window=min(d1_period * 20, len(df) // 2)).mean()
    df['d1_trend'] = (df['close'] > df['d1_sma_20']).astype(float)
    df['d1_trend'] = df['d1_trend'].rolling(window=min(d1_period, len(df) // 4)).mean()
    
    df['d1_momentum'] = df['close'].pct_change(periods=min(d1_period * 5, len(df) // 4))
    df['d1_momentum'] = df['d1_momentum'].clip(-0.05, 0.05) / 0.05
    
    # Multi-timeframe alignment score
    df['htf_alignment'] = (df['h1_trend'] + df['h4_trend'] + df['d1_trend']) / 3.0
    
    # HTF momentum alignment
    df['htf_momentum'] = (df['h1_momentum'] + df['h4_momentum'] + df['d1_momentum']) / 3.0
    
    # Drop intermediate columns
    df = df.drop(['h1_sma_20', 'h4_sma_20', 'd1_sma_20'], axis=1, errors='ignore')
    
    # Fill NaN values
    htf_cols = ['h1_trend', 'h1_momentum', 'h1_rsi', 'h4_trend', 'h4_momentum', 'h4_rsi', 
                'd1_trend', 'd1_momentum', 'htf_alignment', 'htf_momentum']
    for col in htf_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0.5 if 'trend' in col else 0)
    
    print(f"   ✅ Added {len(htf_cols)} HTF features")
    return df


def load_and_prepare_data(symbol):
    """Load data and add HTF features"""
    print(f"\n{'='*80}")
    print(f"LOADING: {symbol.upper()}")
    print(f"{'='*80}")
    
    data_file = f"{DATA_DIR}/{symbol}_training_data_FULL.csv"
    
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        return None, None, None
    
    df = pd.read_csv(data_file)
    print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Add HTF features
    df = add_htf_features(df)
    
    # Separate features and target
    if 'target' not in df.columns:
        print("❌ No target column found!")
        return None, None, None
    
    # Drop non-feature columns
    drop_cols = ['target', 'timestamp', 'symbol']
    X = df.drop([c for c in drop_cols if c in df.columns], axis=1)
    y = df['target']
    
    # Handle missing/inf values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    # Clip extreme outliers
    for col in X.columns:
        q1 = X[col].quantile(0.01)
        q99 = X[col].quantile(0.99)
        X[col] = X[col].clip(q1, q99)
    
    X = X.fillna(0)
    
    feature_names = list(X.columns)
    print(f"✅ Total features: {len(feature_names)}")
    print(f"✅ HTF features included: h1_trend, h1_momentum, h1_rsi, h4_trend, h4_momentum, h4_rsi, d1_trend, d1_momentum, htf_alignment, htf_momentum")
    print(f"✅ Target distribution: {y.value_counts().to_dict()}")
    
    return X, y, feature_names


def train_model(symbol, X, y, feature_names):
    """Train model with HTF features"""
    print(f"\n{'='*80}")
    print(f"TRAINING: {symbol.upper()} with HTF features")
    print(f"{'='*80}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"Training: {len(X_train):,} samples")
    print(f"Testing: {len(X_test):,} samples")
    
    # Train Random Forest
    print("\n1. Training RandomForest...")
    rf_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    rf_pred = rf_model.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    print(f"   RF Accuracy: {rf_acc:.1%}")
    
    # Train Gradient Boosting
    print("\n2. Training GradientBoosting...")
    gb_model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    gb_pred = gb_model.predict(X_test)
    gb_acc = accuracy_score(y_test, gb_pred)
    print(f"   GB Accuracy: {gb_acc:.1%}")
    
    # Ensemble prediction
    rf_proba = rf_model.predict_proba(X_test)
    gb_proba = gb_model.predict_proba(X_test)
    ensemble_proba = (rf_proba + gb_proba) / 2
    ensemble_pred = np.argmax(ensemble_proba, axis=1)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    print(f"\n   🎯 ENSEMBLE Accuracy: {ensemble_acc:.1%}")
    
    # Save model
    model_data = {
        'rf_model': rf_model,
        'gb_model': gb_model,
        'feature_names': feature_names,
        'rf_accuracy': rf_acc,
        'gb_accuracy': gb_acc,
        'ensemble_accuracy': ensemble_acc,
        'trained_at': datetime.now().isoformat(),
        'htf_features': True,  # Flag that this model has HTF features
        'n_features': len(feature_names)
    }
    
    model_file = f"{MODELS_DIR}/{symbol}_htf_ensemble.pkl"
    joblib.dump(model_data, model_file)
    print(f"\n✅ Saved: {model_file}")
    
    return ensemble_acc


def main():
    print("="*80)
    print("TRAINING ML MODELS WITH HTF FEATURES")
    print("This creates COHESIVE models matching entry/exit timeframes")
    print("="*80)
    
    results = {}
    
    for symbol in SYMBOLS:
        try:
            X, y, feature_names = load_and_prepare_data(symbol)
            if X is None:
                print(f"⚠️ Skipping {symbol} - no data")
                continue
            
            acc = train_model(symbol, X, y, feature_names)
            results[symbol] = acc
            
        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*80)
    print("TRAINING COMPLETE - SUMMARY")
    print("="*80)
    for symbol, acc in results.items():
        print(f"   {symbol.upper()}: {acc:.1%}")
    
    print("\n✅ Models saved with '_htf_ensemble.pkl' suffix")
    print("   To use: Update api.py to load these models instead")


if __name__ == "__main__":
    main()
