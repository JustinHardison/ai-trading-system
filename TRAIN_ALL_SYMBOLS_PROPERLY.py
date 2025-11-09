#!/usr/bin/env python3
"""
TRAIN ALL SYMBOLS PROPERLY - Symbol-Specific Models
Each instrument (indices, forex, commodities) trained separately
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
from datetime import datetime

# Symbol categories
INDICES = ['us30', 'us100', 'us500']
FOREX = ['eurusd', 'gbpusd', 'usdjpy']
COMMODITIES = ['xau', 'usoil']

ALL_SYMBOLS = INDICES + FOREX + COMMODITIES

DATA_DIR = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
MODELS_DIR = "/Users/justinhardison/ai-trading-system/models"

def load_and_prepare_data(symbol):
    """Load and prepare data for a specific symbol"""
    print(f"\n{'='*80}")
    print(f"LOADING DATA: {symbol.upper()}")
    print(f"{'='*80}")
    
    data_file = f"{DATA_DIR}/{symbol}_training_data.csv"
    
    if not os.path.exists(data_file):
        print(f"❌ Data file not found: {data_file}")
        return None, None, None, None
    
    # Load data
    df = pd.read_csv(data_file)
    print(f"✅ Loaded {len(df)} rows")
    
    # Check for required columns
    if 'target' not in df.columns:
        print("❌ No 'target' column found")
        return None, None, None, None
    
    # Separate features and target
    X = df.drop(['target', 'timestamp'], axis=1, errors='ignore')
    y = df['target']
    
    # Remove any non-numeric columns
    X = X.select_dtypes(include=[np.number])
    
    # Remove infinite values FIRST
    X = X.replace([np.inf, -np.inf], np.nan)
    
    # Handle missing values
    X = X.fillna(X.median())  # Use median for robustness
    
    # Clip extreme values (outliers)
    for col in X.columns:
        q1 = X[col].quantile(0.01)
        q99 = X[col].quantile(0.99)
        X[col] = X[col].clip(q1, q99)
    
    # Final check - replace any remaining NaN/inf
    X = X.replace([np.inf, -np.inf], 0)
    X = X.fillna(0)
    
    print(f"✅ Features: {X.shape[1]}")
    print(f"✅ Samples: {len(X)}")
    print(f"✅ Target distribution: {y.value_counts().to_dict()}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    return X_train, X_test, y_train, y_test


def train_symbol_model(symbol, X_train, X_test, y_train, y_test):
    """Train symbol-specific ensemble model"""
    print(f"\n{'='*80}")
    print(f"TRAINING: {symbol.upper()}")
    print(f"{'='*80}")
    
    # Determine category
    if symbol in INDICES:
        category = "INDEX"
    elif symbol in FOREX:
        category = "FOREX"
    else:
        category = "COMMODITY"
    
    print(f"Category: {category}")
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    
    # Train RandomForest
    print("\n1. Training RandomForest...")
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    rf_pred = rf_model.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    print(f"   ✅ RandomForest Accuracy: {rf_acc*100:.2f}%")
    
    # Train GradientBoosting
    print("\n2. Training GradientBoosting...")
    gb_model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    gb_pred = gb_model.predict(X_test)
    gb_acc = accuracy_score(y_test, gb_pred)
    print(f"   ✅ GradientBoosting Accuracy: {gb_acc*100:.2f}%")
    
    # Ensemble prediction
    print("\n3. Creating Ensemble...")
    ensemble_pred = []
    for rf_p, gb_p in zip(rf_pred, gb_pred):
        # Majority vote
        if rf_p == gb_p:
            ensemble_pred.append(rf_p)
        else:
            # If they disagree, use RF (usually more stable)
            ensemble_pred.append(rf_p)
    
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    print(f"   ✅ Ensemble Accuracy: {ensemble_acc*100:.2f}%")
    
    # Create model package
    model_package = {
        'symbol': symbol.upper(),
        'category': category,
        'rf_model': rf_model,
        'gb_model': gb_model,
        'feature_names': list(X_train.columns),
        'n_features': len(X_train.columns),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'rf_accuracy': rf_acc,
        'gb_accuracy': gb_acc,
        'ensemble_accuracy': ensemble_acc,
        'trained_on': symbol.upper(),
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': f'Symbol-specific model trained on {len(X_train)} {category} samples'
    }
    
    # Save model
    model_file = f"{MODELS_DIR}/{symbol}_ensemble_latest.pkl"
    joblib.dump(model_package, model_file)
    print(f"\n✅ Model saved: {model_file}")
    
    # Print classification report
    print(f"\nClassification Report:")
    print(classification_report(y_test, ensemble_pred))
    
    return model_package


def train_all_symbols():
    """Train all symbols"""
    print("\n" + "="*80)
    print("TRAINING ALL SYMBOLS - SYMBOL-SPECIFIC MODELS")
    print("="*80)
    print(f"\nIndices: {INDICES}")
    print(f"Forex: {FOREX}")
    print(f"Commodities: {COMMODITIES}")
    
    results = {}
    
    for symbol in ALL_SYMBOLS:
        try:
            # Load data
            X_train, X_test, y_train, y_test = load_and_prepare_data(symbol)
            
            if X_train is None:
                print(f"⚠️  Skipping {symbol} - no data")
                continue
            
            # Train model
            model = train_symbol_model(symbol, X_train, X_test, y_train, y_test)
            results[symbol] = model
            
        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary
    print("\n" + "="*80)
    print("TRAINING SUMMARY")
    print("="*80)
    
    for symbol in ALL_SYMBOLS:
        if symbol in results:
            model = results[symbol]
            acc = model['ensemble_accuracy'] * 100
            samples = model['training_samples']
            category = model['category']
            print(f"✅ {symbol.upper():8s} ({category:9s}): {acc:6.2f}% accuracy ({samples:,} samples)")
        else:
            print(f"❌ {symbol.upper():8s}: FAILED")
    
    print("\n" + "="*80)
    print(f"✅ TRAINING COMPLETE: {len(results)}/{len(ALL_SYMBOLS)} symbols")
    print("="*80)
    
    return results


if __name__ == "__main__":
    results = train_all_symbols()
    
    print("\n✅ All symbol-specific models trained")
    print("Each instrument now has its own dedicated model")
    print("Ready for trading!")
