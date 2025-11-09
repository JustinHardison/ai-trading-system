#!/usr/bin/env python3
"""
PROPER TRAINING - Symbol-Specific Models
No shortcuts - train each symbol properly
"""

import os
import sys
import pandas as pd
import numpy as np
import joblib
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

def log(msg):
    print(f"[{msg}]")

def train_symbol(symbol, broker_symbol, data_file, models_dir):
    """Train symbol-specific model"""
    log(f"\n{'='*80}")
    log(f"TRAINING: {symbol.upper()} ({broker_symbol})")
    log(f"{'='*80}")
    
    # Load data
    df = pd.read_csv(data_file, low_memory=False)
    log(f"✅ Loaded {len(df)} rows")
    
    # Filter for this symbol if multi-symbol file
    if 'symbol' in df.columns:
        df = df[df['symbol'].str.contains(broker_symbol.replace('.sim', ''), case=False, na=False)]
        log(f"✅ Filtered to {len(df)} rows for {broker_symbol}")
    
    if len(df) < 1000:
        log(f"❌ Not enough data: {len(df)} rows")
        return None
    
    # Prepare data
    drop_cols = ['timestamp', 'symbol']
    for col in drop_cols:
        if col in df.columns:
            df = df.drop(col, axis=1)
    
    if 'target' not in df.columns:
        log("❌ No target column")
        return None
    
    X = df.drop('target', axis=1)
    y = df['target']
    
    # Clean data
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = pd.to_numeric(X[col], errors='coerce')
    
    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    
    # Remove constant columns
    constant_cols = [col for col in X.columns if X[col].nunique() <= 1]
    if constant_cols:
        log(f"Removing {len(constant_cols)} constant columns")
        X = X.drop(constant_cols, axis=1)
    
    log(f"✅ Features: {X.shape[1]}, Samples: {len(X)}")
    log(f"✅ Target distribution: {dict(y.value_counts())}")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Train LightGBM
    log("Training LightGBM...")
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'max_depth': 7,
    }
    
    lgb_model = lgb.train(
        params, train_data, num_boost_round=300,
        valid_sets=[test_data],
        callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(period=0)]
    )
    
    y_pred_lgb = (lgb_model.predict(X_test) > 0.5).astype(int)
    lgb_acc = accuracy_score(y_test, y_pred_lgb)
    
    # Train CatBoost
    log("Training CatBoost...")
    cat_model = CatBoostClassifier(
        iterations=300,
        learning_rate=0.05,
        depth=7,
        loss_function='Logloss',
        random_seed=42,
        verbose=0,
        early_stopping_rounds=30
    )
    
    cat_model.fit(X_train, y_train, eval_set=(X_test, y_test), use_best_model=True)
    
    y_pred_cat = cat_model.predict(X_test)
    cat_acc = accuracy_score(y_test, y_pred_cat)
    
    # Ensemble
    total_acc = lgb_acc + cat_acc
    ensemble = {
        'lgb_model': lgb_model,
        'cat_model': cat_model,
        'weights': {'lgb': lgb_acc/total_acc, 'cat': cat_acc/total_acc},
        'lgb_accuracy': lgb_acc,
        'cat_accuracy': cat_acc,
        'ensemble_accuracy': (lgb_acc + cat_acc) / 2,
        'feature_names': list(X.columns),
        'num_features': len(X.columns),
        'symbol': symbol,
        'broker_symbol': broker_symbol,
        'training_samples': len(X_train),
        'test_samples': len(X_test)
    }
    
    log(f"✅ LightGBM: {lgb_acc*100:.2f}%")
    log(f"✅ CatBoost: {cat_acc*100:.2f}%")
    log(f"✅ Ensemble: {ensemble['ensemble_accuracy']*100:.2f}%")
    
    # Save models
    for suffix in ['_ensemble_latest.pkl', '_ultimate_ensemble.pkl']:
        model_file = f"{models_dir}/{symbol}{suffix}"
        joblib.dump(ensemble, model_file)
        log(f"✅ Saved: {model_file}")
    
    return ensemble

def main():
    base_dir = "/Users/justinhardison/ai-trading-system"
    data_dir = f"{base_dir}/data"
    models_dir = f"{base_dir}/models"
    
    # Broker symbols
    broker_symbols = {
        'us30': 'US30Z25.sim',
        'us100': 'US100Z25.sim',
        'us500': 'US500Z25.sim',
        'eurusd': 'EURUSD.sim',
        'gbpusd': 'GBPUSD.sim',
        'usdjpy': 'USDJPY.sim',
        'xau': 'XAUG26.sim',
        'usoil': 'USOILF26.sim'
    }
    
    # Use the existing data file
    data_file = f"{data_dir}/ultimate_training_data.csv"
    
    if not os.path.exists(data_file):
        log(f"❌ Data file not found: {data_file}")
        return False
    
    log(f"✅ Using data file: {data_file}")
    
    # Train each symbol
    results = {}
    for symbol, broker_symbol in broker_symbols.items():
        try:
            ensemble = train_symbol(symbol, broker_symbol, data_file, models_dir)
            if ensemble:
                results[symbol] = ensemble
        except Exception as e:
            log(f"❌ Error training {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    log(f"\n{'='*80}")
    log("TRAINING SUMMARY")
    log(f"{'='*80}")
    
    for symbol, result in results.items():
        log(f"{symbol.upper()}: {result['ensemble_accuracy']*100:.2f}% ({result['num_features']} features)")
    
    log(f"\n✅ Trained {len(results)}/{len(broker_symbols)} symbols")
    
    return len(results) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
