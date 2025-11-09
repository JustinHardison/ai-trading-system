#!/usr/bin/env python3
"""
Retrain ML models with M15, M30, H1, H4, D1 features for consistency.

This ensures the ML models use the SAME timeframes as the decision logic:
- M15: 10% weight in decisions
- M30: 15% weight in decisions  
- H1:  20% weight in decisions
- H4:  25% weight in decisions
- D1:  30% weight in decisions

Adding M15/M30 features gives ML visibility into shorter-term momentum shifts
that the decision logic already sees.
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

# Only retrain indices and gold (as requested)
SYMBOLS = ['us30', 'us100', 'us500', 'xau']


def add_all_timeframe_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add M15, M30, H1, H4, D1 features to match decision logic timeframes.
    
    Features per timeframe:
    - trend: Direction based on SMA
    - momentum: Rate of change
    - rsi: Relative Strength Index
    
    This adds to the EXISTING features, maintaining the 138+ feature set.
    """
    print("   Adding M15/M30/H1/H4/D1 features...")
    
    # M15 equivalent features (using ~3 bars of M5 = 15 minutes)
    m15_period = 3
    
    df['m15_sma_20'] = df['close'].rolling(window=m15_period * 20).mean()
    df['m15_trend'] = (df['close'] > df['m15_sma_20']).astype(float)
    df['m15_trend'] = df['m15_trend'].rolling(window=m15_period * 5).mean()
    
    df['m15_momentum'] = df['close'].pct_change(periods=m15_period * 5)
    df['m15_momentum'] = df['m15_momentum'].clip(-0.03, 0.03) / 0.03  # Normalize to -1 to 1
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=m15_period * 14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=m15_period * 14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['m15_rsi'] = (100 - (100 / (1 + rs))) / 100.0  # Normalize to 0-1
    
    # M30 equivalent features (using ~6 bars of M5 = 30 minutes)
    m30_period = 6
    
    df['m30_sma_20'] = df['close'].rolling(window=m30_period * 20).mean()
    df['m30_trend'] = (df['close'] > df['m30_sma_20']).astype(float)
    df['m30_trend'] = df['m30_trend'].rolling(window=m30_period * 5).mean()
    
    df['m30_momentum'] = df['close'].pct_change(periods=m30_period * 5)
    df['m30_momentum'] = df['m30_momentum'].clip(-0.03, 0.03) / 0.03
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=m30_period * 14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=m30_period * 14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['m30_rsi'] = (100 - (100 / (1 + rs))) / 100.0
    
    # H1 equivalent features (using ~12 bars of M5 = 1 hour)
    h1_period = 12
    
    df['h1_sma_20'] = df['close'].rolling(window=h1_period * 20).mean()
    df['h1_trend'] = (df['close'] > df['h1_sma_20']).astype(float)
    df['h1_trend'] = df['h1_trend'].rolling(window=h1_period).mean()
    
    df['h1_momentum'] = df['close'].pct_change(periods=h1_period * 5)
    df['h1_momentum'] = df['h1_momentum'].clip(-0.05, 0.05) / 0.05
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=h1_period * 14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=h1_period * 14).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['h1_rsi'] = (100 - (100 / (1 + rs))) / 100.0
    
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
    df['h4_rsi'] = (100 - (100 / (1 + rs))) / 100.0
    
    # D1 equivalent features (using ~288 bars of M5 = 1 day)
    d1_period = 288
    
    df['d1_sma_20'] = df['close'].rolling(window=min(d1_period * 20, len(df) // 2)).mean()
    df['d1_trend'] = (df['close'] > df['d1_sma_20']).astype(float)
    df['d1_trend'] = df['d1_trend'].rolling(window=min(d1_period, len(df) // 4)).mean()
    
    df['d1_momentum'] = df['close'].pct_change(periods=min(d1_period * 5, len(df) // 4))
    df['d1_momentum'] = df['d1_momentum'].clip(-0.05, 0.05) / 0.05
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=min(d1_period * 14, len(df) // 4)).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=min(d1_period * 14, len(df) // 4)).mean()
    rs = gain / loss.replace(0, 1e-10)
    df['d1_rsi'] = (100 - (100 / (1 + rs))) / 100.0
    
    # Multi-timeframe alignment scores (matching decision logic weights)
    # M15: 10%, M30: 15%, H1: 20%, H4: 25%, D1: 30%
    df['htf_alignment'] = (
        df['m15_trend'] * 0.10 + 
        df['m30_trend'] * 0.15 + 
        df['h1_trend'] * 0.20 + 
        df['h4_trend'] * 0.25 + 
        df['d1_trend'] * 0.30
    )
    
    df['htf_momentum'] = (
        df['m15_momentum'] * 0.10 + 
        df['m30_momentum'] * 0.15 + 
        df['h1_momentum'] * 0.20 + 
        df['h4_momentum'] * 0.25 + 
        df['d1_momentum'] * 0.30
    )
    
    # Drop intermediate columns
    df = df.drop(['m15_sma_20', 'm30_sma_20', 'h1_sma_20', 'h4_sma_20', 'd1_sma_20'], axis=1, errors='ignore')
    
    # Fill NaN values
    tf_cols = [
        'm15_trend', 'm15_momentum', 'm15_rsi',
        'm30_trend', 'm30_momentum', 'm30_rsi',
        'h1_trend', 'h1_momentum', 'h1_rsi', 
        'h4_trend', 'h4_momentum', 'h4_rsi', 
        'd1_trend', 'd1_momentum', 'd1_rsi',
        'htf_alignment', 'htf_momentum'
    ]
    for col in tf_cols:
        if col in df.columns:
            if 'trend' in col or 'alignment' in col:
                df[col] = df[col].fillna(0.5)
            elif 'rsi' in col:
                df[col] = df[col].fillna(0.5)
            else:
                df[col] = df[col].fillna(0)
    
    print(f"   ✅ Added {len(tf_cols)} timeframe features (M15-D1)")
    return df


def load_and_prepare_data(symbol: str) -> pd.DataFrame:
    """Load data from MT5 export and prepare features."""
    
    # Try multiple file patterns - prioritize FULL training data
    file_patterns = [
        f"{DATA_DIR}/{symbol}_training_data_FULL.csv",
        f"{DATA_DIR}/{symbol}_training_data.csv",
        f"{DATA_DIR}/{symbol.upper()}_M5_data.csv",
        f"{DATA_DIR}/{symbol}_M5_data.csv",
        f"/Users/justinhardison/ai-trading-system/data/{symbol.upper()}_M5_data.csv",
    ]
    
    df = None
    for pattern in file_patterns:
        if os.path.exists(pattern):
            print(f"   Loading: {pattern}")
            df = pd.read_csv(pattern)
            break
    
    if df is None:
        print(f"   ❌ No data file found for {symbol}")
        return None
    
    print(f"   Loaded {len(df)} rows")
    
    # Ensure required columns exist
    required = ['open', 'high', 'low', 'close', 'volume']
    for col in required:
        if col not in df.columns:
            col_lower = col.lower()
            col_upper = col.upper()
            if col_lower in df.columns:
                df[col] = df[col_lower]
            elif col_upper in df.columns:
                df[col] = df[col_upper]
    
    # Add basic features if not present
    if 'returns' not in df.columns:
        df['returns'] = df['close'].pct_change()
    if 'volatility' not in df.columns:
        df['volatility'] = df['close'].pct_change().rolling(20).std()
    
    # Add timeframe features (M15/M30/H1/H4/D1)
    df = add_all_timeframe_features(df)
    
    # Use existing target if available, otherwise create it
    if 'target' not in df.columns:
        lookahead = 12  # ~1 hour for M5 data
        df['target'] = (df['close'].shift(-lookahead) > df['close']).astype(int)
    
    # Drop rows with NaN
    df = df.dropna()
    
    return df


def calculate_rsi(prices, period=14):
    """Calculate RSI."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def train_model(symbol: str):
    """Train model for a single symbol with M15-D1 features."""
    
    print(f"\n{'='*60}")
    print(f"Training {symbol.upper()} with M15-D1 features")
    print('='*60)
    
    # Load data
    df = load_and_prepare_data(symbol)
    if df is None or len(df) < 1000:
        print(f"   ❌ Insufficient data for {symbol}")
        return None
    
    # Use ALL features from the training data PLUS new timeframe features
    # This maintains the 138+ feature set while adding M15/M30
    
    # Drop non-feature columns
    drop_cols = ['target', 'timestamp', 'symbol']
    X = df.drop([c for c in drop_cols if c in df.columns], axis=1)
    
    # Handle missing/inf values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    # Clip extreme outliers
    for col in X.columns:
        q1 = X[col].quantile(0.01)
        q99 = X[col].quantile(0.99)
        X[col] = X[col].clip(q1, q99)
    
    X = X.fillna(0)
    
    available_cols = list(X.columns)
    
    # Count timeframe features
    tf_features = [c for c in available_cols if any(tf in c for tf in ['m15_', 'm30_', 'h1_', 'h4_', 'd1_', 'htf_'])]
    print(f"   Using {len(available_cols)} features ({len(tf_features)} timeframe features)")
    
    X = df[available_cols]
    y = df['target']
    
    # Split data with stratification for balanced classes
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"   Train: {len(X_train)}, Test: {len(X_test)}")
    
    # Train Random Forest with better parameters
    print("   Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        max_features='sqrt',
        class_weight='balanced',
        n_jobs=-1,
        random_state=42
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)
    print(f"   RF Accuracy: {rf_acc:.1%}")
    
    # Train Gradient Boosting
    print("   Training Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42
    )
    gb.fit(X_train, y_train)
    gb_pred = gb.predict(X_test)
    gb_acc = accuracy_score(y_test, gb_pred)
    print(f"   GB Accuracy: {gb_acc:.1%}")
    
    # Create ensemble with proper probability averaging
    rf_proba = rf.predict_proba(X_test)
    gb_proba = gb.predict_proba(X_test)
    ensemble_proba = (rf_proba + gb_proba) / 2
    ensemble_pred = (ensemble_proba[:, 1] > 0.5).astype(int)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    print(f"   Ensemble Accuracy: {ensemble_acc:.1%}")
    
    # Save model
    model_data = {
        'rf_model': rf,
        'gb_model': gb,
        'feature_names': available_cols,
        'n_features': len(available_cols),
        'rf_accuracy': rf_acc,
        'gb_accuracy': gb_acc,
        'ensemble_accuracy': ensemble_acc,
        'trained_at': datetime.now().isoformat(),
        'symbol': symbol,
        'timeframes': ['m15', 'm30', 'h1', 'h4', 'd1'],
        'version': '2.0_m15_m30'
    }
    
    # Save as HTF model (replacing old one)
    model_path = f"{MODELS_DIR}/{symbol}_htf_ensemble.pkl"
    joblib.dump(model_data, model_path)
    print(f"   ✅ Saved: {model_path}")
    
    # Feature importance
    print("\n   Top 10 Feature Importance:")
    importance = pd.DataFrame({
        'feature': available_cols,
        'importance': rf.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for i, row in importance.head(10).iterrows():
        print(f"      {row['feature']}: {row['importance']:.3f}")
    
    return model_data


def main():
    print("="*60)
    print("RETRAINING MODELS WITH M15/M30/H1/H4/D1 FEATURES")
    print("="*60)
    print("\nThis ensures ML models use the SAME timeframes as decision logic:")
    print("  M15: 10% weight")
    print("  M30: 15% weight")
    print("  H1:  20% weight")
    print("  H4:  25% weight")
    print("  D1:  30% weight")
    print()
    
    results = {}
    for symbol in SYMBOLS:
        result = train_model(symbol)
        if result:
            results[symbol] = result['ensemble_accuracy']
    
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    for symbol, acc in results.items():
        print(f"  {symbol.upper()}: {acc:.1%}")
    
    print("\n✅ Models now include M15/M30 features for consistency with decision logic")
    print("   Restart the API to load the new models")


if __name__ == "__main__":
    main()
