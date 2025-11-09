#!/usr/bin/env python3
"""
Train model for the symbol we have data for, then copy to all symbols
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
from sklearn.metrics import accuracy_score

print("="*80)
print("TRAINING MODEL FOR AVAILABLE DATA")
print("="*80)

# Load data
df = pd.read_csv('/Users/justinhardison/ai-trading-system/data/ultimate_training_data.csv', low_memory=False)
print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")

# Check symbol
if 'symbol' in df.columns:
    print(f"✅ Symbol: {df['symbol'].iloc[0]}")
    symbol_name = df['symbol'].iloc[0].lower().replace('z25.sim', '').replace('.sim', '')
    if symbol_name.startswith('us'):
        symbol_name = symbol_name[:5]  # us100, us30, us500
    print(f"✅ Normalized symbol: {symbol_name}")
else:
    symbol_name = 'us30'
    print(f"⚠️  No symbol column, assuming: {symbol_name}")

# Drop non-feature columns
drop_cols = []
if 'timestamp' in df.columns:
    drop_cols.append('timestamp')
if 'symbol' in df.columns:
    drop_cols.append('symbol')

df = df.drop(drop_cols, axis=1)

# Separate features and target
X = df.drop('target', axis=1)
y = df['target']

# Convert object columns to numeric (handle huge numbers)
for col in X.columns:
    if X[col].dtype == 'object':
        X[col] = pd.to_numeric(X[col], errors='coerce')

# Fill NaN with 0
X = X.fillna(0)

# Replace inf with large numbers
X = X.replace([np.inf, -np.inf], 0)

print(f"✅ Features: {X.shape[1]} columns")
print(f"✅ Samples: {len(X)}")
print(f"✅ Target: {y.value_counts().to_dict()}")

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"✅ Train: {len(X_train)}, Test: {len(X_test)}")

# Train LightGBM
print("\n" + "="*80)
print("TRAINING LIGHTGBM")
print("="*80)

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
    params,
    train_data,
    num_boost_round=300,
    valid_sets=[test_data],
    callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(period=50)]
)

y_pred_lgb = (lgb_model.predict(X_test) > 0.5).astype(int)
lgb_acc = accuracy_score(y_test, y_pred_lgb)
print(f"\n✅ LightGBM Accuracy: {lgb_acc*100:.2f}%")

# Train CatBoost
print("\n" + "="*80)
print("TRAINING CATBOOST")
print("="*80)

cat_model = CatBoostClassifier(
    iterations=300,
    learning_rate=0.05,
    depth=7,
    loss_function='Logloss',
    random_seed=42,
    verbose=50,
    early_stopping_rounds=30
)

cat_model.fit(
    X_train, y_train,
    eval_set=(X_test, y_test),
    use_best_model=True
)

y_pred_cat = cat_model.predict(X_test)
cat_acc = accuracy_score(y_test, y_pred_cat)
print(f"\n✅ CatBoost Accuracy: {cat_acc*100:.2f}%")

# Create ensemble
total_acc = lgb_acc + cat_acc
weights = {
    'lgb': lgb_acc / total_acc,
    'cat': cat_acc / total_acc,
}

ensemble = {
    'lgb_model': lgb_model,
    'cat_model': cat_model,
    'weights': weights,
    'lgb_accuracy': lgb_acc,
    'cat_accuracy': cat_acc,
    'ensemble_accuracy': (lgb_acc + cat_acc) / 2,
    'feature_names': list(X.columns)
}

print(f"\n✅ Ensemble Accuracy: {ensemble['ensemble_accuracy']*100:.2f}%")
print(f"✅ Weights: LGB={weights['lgb']*100:.1f}%, CAT={weights['cat']*100:.1f}%")

# Save for all symbols
models_dir = '/Users/justinhardison/ai-trading-system/models'
symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']

print("\n" + "="*80)
print("SAVING MODELS")
print("="*80)

for symbol in symbols:
    # Save as ultimate_ensemble
    ultimate_file = f"{models_dir}/{symbol}_ultimate_ensemble.pkl"
    joblib.dump(ensemble, ultimate_file)
    print(f"✅ Saved: {symbol}_ultimate_ensemble.pkl")
    
    # Save as ensemble_latest (for compatibility)
    latest_file = f"{models_dir}/{symbol}_ensemble_latest.pkl"
    joblib.dump(ensemble, latest_file)
    print(f"✅ Saved: {symbol}_ensemble_latest.pkl")

print("\n" + "="*80)
print("✅ TRAINING COMPLETE - ALL MODELS SAVED")
print("="*80)
print(f"Trained on: {symbol_name.upper()} data")
print(f"Accuracy: {ensemble['ensemble_accuracy']*100:.2f}%")
print(f"Models saved for all 8 symbols")
print("="*80)
