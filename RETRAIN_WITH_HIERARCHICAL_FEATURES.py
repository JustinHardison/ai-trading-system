"""
RETRAIN ML MODELS WITH HIERARCHICAL TIMEFRAME FEATURES

This script retrains all ML models with the new hierarchical features:
- w1_trend (Weekly trend)
- htf_bias (Weighted: W1 40%, D1 30%, H4 20%, H1 10%)
- htf_cascade (Multiplicative confirmation)
- htf_confirmation (How many lower TFs confirm higher TF)

Run this after collecting enough data with the new features.
"""

import os
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Symbols to train
SYMBOLS = ['eurusd', 'gbpusd', 'usdjpy', 'us30', 'us100', 'us500', 'xau', 'usoil']

# New hierarchical features to add
HIERARCHICAL_FEATURES = [
    'w1_trend',
    'w1_momentum', 
    'htf_bias',
    'htf_cascade',
    'htf_confirmation'
]

def load_training_data(symbol: str) -> pd.DataFrame:
    """Load training data for a symbol"""
    data_path = f"data/training/{symbol}_training_data.csv"
    if os.path.exists(data_path):
        return pd.read_csv(data_path)
    
    # Try alternative paths
    alt_paths = [
        f"models/{symbol}_training_data.csv",
        f"data/{symbol}_data.csv",
        f"training_data/{symbol}.csv"
    ]
    
    for path in alt_paths:
        if os.path.exists(path):
            return pd.read_csv(path)
    
    print(f"⚠️ No training data found for {symbol}")
    return None


def add_hierarchical_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add hierarchical timeframe features to training data
    
    If w1_trend is not available, estimate from d1_trend
    """
    # Check if we have the new features
    if 'w1_trend' not in df.columns:
        # Estimate w1_trend from d1_trend (weekly is smoother version of daily)
        if 'd1_trend' in df.columns:
            # Use rolling average of d1_trend as proxy for w1_trend
            df['w1_trend'] = df['d1_trend'].rolling(window=5, min_periods=1).mean()
        else:
            df['w1_trend'] = 0.5
    
    if 'w1_momentum' not in df.columns:
        if 'd1_momentum' in df.columns:
            df['w1_momentum'] = df['d1_momentum'].rolling(window=5, min_periods=1).mean()
        else:
            df['w1_momentum'] = 0.0
    
    # Calculate hierarchical features
    if 'htf_bias' not in df.columns:
        w1 = df.get('w1_trend', 0.5)
        d1 = df.get('d1_trend', 0.5)
        h4 = df.get('h4_trend', 0.5)
        h1 = df.get('h1_trend', 0.5)
        
        # Weighted bias: W1 40%, D1 30%, H4 20%, H1 10%
        df['htf_bias'] = w1 * 0.4 + d1 * 0.3 + h4 * 0.2 + h1 * 0.1
    
    if 'htf_cascade' not in df.columns:
        w1 = df.get('w1_trend', 0.5)
        d1 = df.get('d1_trend', 0.5)
        h4 = df.get('h4_trend', 0.5)
        h1 = df.get('h1_trend', 0.5)
        
        # Multiplicative cascade (all must agree for high score)
        df['htf_cascade'] = (w1 * d1 * h4 * h1) ** 0.25
    
    if 'htf_confirmation' not in df.columns:
        w1 = df.get('w1_trend', 0.5)
        d1 = df.get('d1_trend', 0.5)
        h4 = df.get('h4_trend', 0.5)
        h1 = df.get('h1_trend', 0.5)
        
        # Count how many lower TFs confirm the W1 direction
        def calc_confirmation(row):
            if row['w1_trend'] > 0.5:
                return sum([row['d1_trend'] > 0.5, row['h4_trend'] > 0.5, row['h1_trend'] > 0.5]) / 3.0
            else:
                return sum([row['d1_trend'] < 0.5, row['h4_trend'] < 0.5, row['h1_trend'] < 0.5]) / 3.0
        
        df['htf_confirmation'] = df.apply(calc_confirmation, axis=1)
    
    return df


def train_model(symbol: str, df: pd.DataFrame) -> dict:
    """Train a model for a symbol with hierarchical features"""
    
    print(f"\n{'='*60}")
    print(f"Training model for {symbol.upper()}")
    print(f"{'='*60}")
    
    # Add hierarchical features
    df = add_hierarchical_features(df)
    
    # Define feature columns (excluding target and non-feature columns)
    exclude_cols = ['target', 'label', 'direction', 'timestamp', 'date', 'time', 'symbol']
    feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    # Ensure hierarchical features are included
    for feat in HIERARCHICAL_FEATURES:
        if feat in df.columns and feat not in feature_cols:
            feature_cols.append(feat)
    
    print(f"Features: {len(feature_cols)}")
    print(f"Hierarchical features included: {[f for f in HIERARCHICAL_FEATURES if f in feature_cols]}")
    
    # Prepare data
    X = df[feature_cols].fillna(0)
    
    # Target column
    if 'target' in df.columns:
        y = df['target']
    elif 'label' in df.columns:
        y = df['label']
    elif 'direction' in df.columns:
        y = df['direction'].map({'BUY': 1, 'SELL': 0, 'HOLD': 0.5})
    else:
        print(f"⚠️ No target column found for {symbol}")
        return None
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"Training samples: {len(X_train)}")
    print(f"Test samples: {len(X_test)}")
    
    # Train model
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n✅ Model trained successfully!")
    print(f"   Accuracy: {accuracy:.1%}")
    
    # Feature importance (top 10)
    importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\n   Top 10 Features:")
    for i, row in importance.head(10).iterrows():
        marker = "🎯" if row['feature'] in HIERARCHICAL_FEATURES else "  "
        print(f"   {marker} {row['feature']}: {row['importance']:.4f}")
    
    # Save model
    model_path = f"models/htf_{symbol}_model.joblib"
    os.makedirs("models", exist_ok=True)
    
    model_data = {
        'model': model,
        'feature_names': feature_cols,
        'accuracy': accuracy,
        'trained_at': datetime.now().isoformat(),
        'hierarchical_features': HIERARCHICAL_FEATURES
    }
    
    joblib.dump(model_data, model_path)
    print(f"   Saved to: {model_path}")
    
    return {
        'symbol': symbol,
        'accuracy': accuracy,
        'features': len(feature_cols),
        'model_path': model_path
    }


def main():
    print("="*60)
    print("RETRAINING ML MODELS WITH HIERARCHICAL FEATURES")
    print("="*60)
    print(f"\nNew features being added:")
    for feat in HIERARCHICAL_FEATURES:
        print(f"  - {feat}")
    
    results = []
    
    for symbol in SYMBOLS:
        df = load_training_data(symbol)
        if df is not None and len(df) > 100:
            result = train_model(symbol, df)
            if result:
                results.append(result)
        else:
            print(f"\n⚠️ Skipping {symbol} - insufficient data")
    
    # Summary
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    
    if results:
        for r in results:
            print(f"  {r['symbol'].upper()}: {r['accuracy']:.1%} accuracy ({r['features']} features)")
        
        avg_accuracy = np.mean([r['accuracy'] for r in results])
        print(f"\n  Average Accuracy: {avg_accuracy:.1%}")
        print(f"\n✅ Models saved to models/htf_*.joblib")
        print("   To use: Update api.py to load htf_* models instead of current models")
    else:
        print("  No models trained - check training data availability")


if __name__ == "__main__":
    main()
