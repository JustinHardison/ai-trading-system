#!/usr/bin/env python3
"""
Train all 8 symbols with 131 features
Target: 80%+ accuracy with optimized hyperparameters
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import joblib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
MODELS_DIR = "/Users/justinhardison/ai-trading-system/models"

SYMBOLS = {
    'us30': 'INDEX',
    'us100': 'INDEX',
    'us500': 'INDEX',
    'eurusd': 'FOREX',
    'gbpusd': 'FOREX',
    'usdjpy': 'FOREX',
    'xau': 'COMMODITY',
    'usoil': 'COMMODITY'
}


def load_and_prepare_data(symbol):
    """Load enhanced data and prepare for training"""
    print(f"\n{'='*80}")
    print(f"LOADING: {symbol.upper()}")
    print(f"{'='*80}")
    
    data_file = f"{DATA_DIR}/{symbol}_training_data_FULL.csv"
    df = pd.read_csv(data_file)
    
    print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
    
    # Separate features and target
    if 'target' in df.columns:
        X = df.drop(['target', 'timestamp', 'symbol'], axis=1, errors='ignore')
        y = df['target']
    else:
        print("❌ No target column found!")
        return None, None
    
    # Handle missing/inf values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    # Clip extreme outliers
    for col in X.columns:
        q1 = X[col].quantile(0.01)
        q99 = X[col].quantile(0.99)
        X[col] = X[col].clip(q1, q99)
    
    X = X.fillna(0)
    
    print(f"✅ Features: {X.shape[1]}")
    print(f"✅ Target distribution: {y.value_counts().to_dict()}")
    
    return X, y


def train_optimized_model(symbol, X, y):
    """Train with optimized hyperparameters for 80%+ accuracy"""
    print(f"\n{'='*80}")
    print(f"TRAINING: {symbol.upper()} ({SYMBOLS[symbol]})")
    print(f"{'='*80}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"Training: {len(X_train):,} samples")
    print(f"Testing: {len(X_test):,} samples")
    
    # ===================================================================
    # OPTIMIZED RANDOM FOREST - Target 80%+
    # ===================================================================
    print("\n1. Training RandomForest (optimized for accuracy)...")
    
    rf_model = RandomForestClassifier(
        n_estimators=300,        # More trees = better accuracy
        max_depth=20,            # Deeper trees = capture complex patterns
        min_samples_split=5,     # Allow more splits
        min_samples_leaf=2,      # Smaller leaves = more detail
        max_features='sqrt',     # Good default
        class_weight='balanced', # Handle imbalanced data
        random_state=42,
        n_jobs=-1
    )
    
    rf_model.fit(X_train, y_train)
    rf_pred = rf_model.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    
    print(f"   ✅ RandomForest Accuracy: {rf_acc*100:.2f}%")
    
    # ===================================================================
    # OPTIMIZED GRADIENT BOOSTING - Target 80%+
    # ===================================================================
    print("\n2. Training GradientBoosting (optimized for accuracy)...")
    
    gb_model = GradientBoostingClassifier(
        n_estimators=300,        # More estimators
        max_depth=10,            # Deeper trees
        learning_rate=0.05,      # Lower learning rate with more estimators
        subsample=0.8,           # Use 80% of data per tree
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42
    )
    
    gb_model.fit(X_train, y_train)
    gb_pred = gb_model.predict(X_test)
    gb_acc = accuracy_score(y_test, gb_pred)
    
    print(f"   ✅ GradientBoosting Accuracy: {gb_acc*100:.2f}%")
    
    # ===================================================================
    # WEIGHTED ENSEMBLE - Combine both models
    # ===================================================================
    print("\n3. Creating Weighted Ensemble...")
    
    # Get probabilities
    rf_proba = rf_model.predict_proba(X_test)
    gb_proba = gb_model.predict_proba(X_test)
    
    # Weight by individual accuracy
    rf_weight = rf_acc / (rf_acc + gb_acc)
    gb_weight = gb_acc / (rf_acc + gb_acc)
    
    # Weighted average of probabilities
    ensemble_proba = rf_weight * rf_proba + gb_weight * gb_proba
    ensemble_pred = np.argmax(ensemble_proba, axis=1)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    
    print(f"   ✅ Ensemble Accuracy: {ensemble_acc*100:.2f}%")
    print(f"   Weights: RF={rf_weight:.2f}, GB={gb_weight:.2f}")
    
    # ===================================================================
    # EVALUATE
    # ===================================================================
    print(f"\n{'='*80}")
    print("EVALUATION")
    print(f"{'='*80}")
    
    if ensemble_acc >= 0.80:
        print(f"🎉 TARGET ACHIEVED: {ensemble_acc*100:.2f}% >= 80%")
    elif ensemble_acc >= 0.75:
        print(f"✅ GOOD: {ensemble_acc*100:.2f}% (75-80%)")
    else:
        print(f"⚠️  BELOW TARGET: {ensemble_acc*100:.2f}% < 75%")
    
    print(f"\nClassification Report:")
    print(classification_report(y_test, ensemble_pred, target_names=['SELL', 'BUY']))
    
    print(f"\nConfusion Matrix:")
    cm = confusion_matrix(y_test, ensemble_pred)
    print(cm)
    
    # Feature importance (top 20)
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': rf_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\nTop 20 Most Important Features:")
    for idx, row in feature_importance.head(20).iterrows():
        print(f"  {row['feature']:30s}: {row['importance']:.4f}")
    
    # ===================================================================
    # SAVE MODEL
    # ===================================================================
    model_package = {
        'symbol': symbol.upper(),
        'category': SYMBOLS[symbol],
        'rf_model': rf_model,
        'gb_model': gb_model,
        'rf_weight': rf_weight,
        'gb_weight': gb_weight,
        'feature_names': list(X.columns),
        'n_features': len(X.columns),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'rf_accuracy': rf_acc,
        'gb_accuracy': gb_acc,
        'ensemble_accuracy': ensemble_acc,
        'trained_on': symbol.upper(),
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': f'Optimized 131-feature model - {ensemble_acc*100:.2f}% accuracy'
    }
    
    model_file = f"{MODELS_DIR}/{symbol}_ensemble_latest.pkl"
    joblib.dump(model_package, model_file)
    print(f"\n✅ Model saved: {model_file}")
    
    return model_package


def main():
    """Train all symbols"""
    print("\n" + "="*80)
    print("TRAINING ALL SYMBOLS - 131 FEATURES - TARGET 80%+")
    print("="*80)
    
    results = {}
    
    for symbol in SYMBOLS.keys():
        try:
            # Load data
            X, y = load_and_prepare_data(symbol)
            
            if X is None:
                print(f"⚠️  Skipping {symbol} - no data")
                continue
            
            # Train model
            model = train_optimized_model(symbol, X, y)
            results[symbol] = model
            
        except Exception as e:
            print(f"❌ Error training {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # ===================================================================
    # FINAL SUMMARY
    # ===================================================================
    print("\n" + "="*80)
    print("TRAINING SUMMARY - ALL SYMBOLS")
    print("="*80)
    
    total_above_80 = 0
    total_above_75 = 0
    
    for symbol in SYMBOLS.keys():
        if symbol in results:
            model = results[symbol]
            acc = model['ensemble_accuracy'] * 100
            samples = model['training_samples']
            category = model['category']
            
            if acc >= 80:
                status = "🎉 TARGET"
                total_above_80 += 1
            elif acc >= 75:
                status = "✅ GOOD"
                total_above_75 += 1
            else:
                status = "⚠️  BELOW"
            
            print(f"{status} {symbol.upper():8s} ({category:9s}): {acc:6.2f}% ({samples:,} samples)")
        else:
            print(f"❌ {symbol.upper():8s}: FAILED")
    
    print("\n" + "="*80)
    print(f"✅ TRAINING COMPLETE: {len(results)}/{len(SYMBOLS)} symbols")
    print(f"🎉 Models >= 80%: {total_above_80}")
    print(f"✅ Models >= 75%: {total_above_75 + total_above_80}")
    print("="*80)
    
    if len(results) > 0:
        avg_acc = np.mean([m['ensemble_accuracy'] for m in results.values()]) * 100
        print(f"\n📊 Average Accuracy: {avg_acc:.2f}%")
        print(f"📊 Features: 131 (advanced)")
        print(f"📊 Total Training Samples: {sum(m['training_samples'] for m in results.values()):,}")


if __name__ == "__main__":
    main()
