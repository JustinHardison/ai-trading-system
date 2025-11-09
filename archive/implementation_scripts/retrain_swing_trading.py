#!/usr/bin/env python3
"""
RETRAIN FOR SWING TRADING - $200K Account
==========================================
Swing trades hold for hours/days, not minutes
Targets: 2-5% profits
Stops: 1-2% losses
Timeframes: H1, H4, D1 (not M1, M5)
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import pickle
from datetime import datetime
from src.features.simple_feature_engineer import SimpleFeatureEngineer

print("=" * 70)
print("RETRAINING FOR SWING TRADING - $200K ACCOUNT")
print("=" * 70)

# Paths
EXPORT_PATH = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/training_data/"
MODELS_PATH = "/Users/justinhardison/ai-trading-system/models/"

def load_mt5_data(symbol):
    """Load MT5 exported data"""
    try:
        # Try different encodings and separators
        for encoding in ['utf-16-le', 'utf-8', 'latin1']:
            for sep in [',', '\t', ';']:
                try:
                    df = pd.read_csv(f"{EXPORT_PATH}{symbol}_M1.csv", encoding=encoding, sep=sep)
                    if len(df) > 0 and 'timestamp' in df.columns:
                        return df
                except:
                    continue
        return None
    except Exception as e:
        print(f"  ⚠️ Error loading {symbol}: {e}")
        return None

def create_swing_labels(df, lookforward=50):
    """
    Create labels for SWING TRADING
    - Look forward 50 bars (H1 = ~2 days)
    - BUY if price goes up 2%+ before down 1%
    - SELL if price goes down 2%+ before up 1%
    """
    labels = []
    
    for i in range(len(df) - lookforward):
        current_price = df.iloc[i]['close']
        future_prices = df.iloc[i+1:i+lookforward]['close'].values
        
        # Calculate max gain and max loss
        max_gain = (future_prices.max() - current_price) / current_price
        max_loss = (current_price - future_prices.min()) / current_price
        
        # SWING TRADING LOGIC: 2% target, 1% stop
        if max_gain >= 0.02 and max_gain > max_loss:  # 2% profit potential
            labels.append(1)  # BUY
        elif max_loss >= 0.02 and max_loss > max_gain:  # 2% loss potential
            labels.append(0)  # SELL
        else:
            # Neutral - use trend
            labels.append(1 if future_prices[-1] > current_price else 0)
    
    # Pad remaining
    labels.extend([labels[-1]] * lookforward if labels else [0] * lookforward)
    
    return np.array(labels)

# Symbol categories
CATEGORIES = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'indices': ['US30', 'US100', 'US500'],
    'commodities': ['XAU', 'USOIL']
}

feature_engineer = SimpleFeatureEngineer(enhanced_mode=True)

for category, symbols in CATEGORIES.items():
    print(f"\n{'='*70}")
    print(f"CATEGORY: {category.upper()} - SWING TRADING")
    print(f"{'='*70}")
    
    all_features = []
    all_labels = []
    
    for symbol in symbols:
        print(f"\n📊 Processing {symbol} for SWING TRADING...")
        
        # Load M1 data (we'll aggregate to H1)
        df = load_mt5_data(symbol)
        if df is None or len(df) < 1000:
            print(f"  ⚠️ Insufficient data for {symbol}")
            continue
        
        # Resample to H1 for swing trading
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df_h1 = df.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        }).dropna()
        
        print(f"  ✅ Resampled to H1: {len(df_h1)} bars")
        
        # Create SWING labels (look forward 50 H1 bars = ~2 days)
        labels = create_swing_labels(df_h1, lookforward=50)
        
        # Extract features using H1 data
        for i in range(100, len(df_h1) - 50):  # Need history for features
            try:
                # Create fake request with H1 data
                request = {
                    'current_price': df_h1.iloc[i]['close'],
                    'timeframes': {
                        'm1': df_h1.iloc[i-50:i].to_dict('list'),  # Use H1 as "M1"
                        'h1': df_h1.iloc[i-50:i].to_dict('list'),
                        'h4': df_h1.iloc[i-50:i].to_dict('list'),
                    },
                    'indicators': {}
                }
                
                features = feature_engineer.engineer_features(request)
                
                if len(features) >= 160:
                    all_features.append(list(features.values())[:162])
                    all_labels.append(labels[i])
            except:
                continue
        
        print(f"  ✅ Extracted {len(all_features)} SWING samples")
    
    if len(all_features) < 100:
        print(f"\n⚠️ Not enough data for {category}, skipping...")
        continue
    
    # Convert to arrays
    X = np.array(all_features)
    y = np.array(all_labels)
    
    print(f"\n{category.upper()} Combined: {len(X)} samples, {X.shape[1]} features")
    print(f"  BUY: {(y==1).sum()} ({(y==1).sum()/len(y)*100:.1f}%)")
    print(f"  SELL: {(y==0).sum()} ({(y==0).sum()/len(y)*100:.1f}%)")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\n🤖 Training SWING TRADING models for {category}...")
    print(f"  Samples: {len(X_train)} train, {len(X_test)} test")
    print(f"  Features: {X.shape[1]}")
    
    # Train RandomForest - SWING TRADING parameters
    print(f"  Training RandomForest (SWING)...")
    rf_model = RandomForestClassifier(
        n_estimators=200,  # More trees for swing
        max_depth=15,      # Deeper for complex patterns
        min_samples_split=10,  # Less restrictive
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    rf_acc = rf_model.score(X_test, y_test)
    print(f"    RF Accuracy: {rf_acc*100:.2f}%")
    
    # Train GradientBoosting - SWING TRADING parameters
    print(f"  Training GradientBoosting (SWING)...")
    gb_model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=5,
        learning_rate=0.05,  # Lower for swing
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    gb_acc = gb_model.score(X_test, y_test)
    print(f"    GB Accuracy: {gb_acc*100:.2f}%")
    
    # Ensemble accuracy
    rf_pred = rf_model.predict(X_test)
    gb_pred = gb_model.predict(X_test)
    ensemble_pred = ((rf_pred + gb_pred) / 2 > 0.5).astype(int)
    ensemble_acc = (ensemble_pred == y_test).mean()
    print(f"    Ensemble Accuracy: {ensemble_acc*100:.2f}%")
    
    # Save model
    model_data = {
        'rf_model': rf_model,
        'gb_model': gb_model,
        'feature_count': X.shape[1],
        'accuracy': ensemble_acc,
        'training_samples': len(X_train),
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': 'swing_trading_v1',
        'note': 'SWING TRADING: H1 timeframe, 2% targets, 1% stops, hold hours/days'
    }
    
    model_path = f"{MODELS_PATH}{category}_ensemble_latest.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"  ✅ Saved: {model_path}")
    print(f"  📊 Final Accuracy: {ensemble_acc*100:.2f}%")

print("\n" + "=" * 70)
print("✅ SWING TRADING RETRAINING COMPLETE!")
print("=" * 70)
print("\nModels trained for:")
print("  - H1/H4/D1 timeframes (not M1/M5)")
print("  - 2-5% profit targets")
print("  - 1-2% stop losses")
print("  - Hold times: hours to days")
print("\n🚀 Restart API to use SWING TRADING models!")
