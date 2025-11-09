#!/usr/bin/env python3
"""
RETRAIN SWING TRADING MODELS - Using H1, H4, D1 Data
====================================================
$200K Account - Swing Trading
Targets: 2-5% | Stops: 1-2% | Hold: Hours to Days
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import pickle
from datetime import datetime
from src.features.simple_feature_engineer import SimpleFeatureEngineer

print("=" * 70)
print("SWING TRADING - RETRAINING WITH H1/H4/D1 DATA")
print("=" * 70)

# Paths
SWING_PATH = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/training_data/swing/"
MODELS_PATH = "/Users/justinhardison/ai-trading-system/models/"

def load_swing_data(symbol, timeframe):
    """Load H1/H4/D1 data"""
    try:
        filename = f"{SWING_PATH}{symbol}_{timeframe}.csv"
        df = pd.read_csv(filename, encoding='utf-8')
        if len(df) > 0:
            print(f"  ✅ Loaded {symbol} {timeframe}: {len(df)} bars")
            return df
        return None
    except Exception as e:
        print(f"  ⚠️ Error loading {symbol} {timeframe}: {e}")
        return None

def create_swing_labels_h1(df, lookforward=48):
    """
    SWING TRADING LABELS for H1 data
    Look forward 48 bars (2 days)
    BUY: Price goes up 2%+ before down 1%
    SELL: Price goes down 2%+ before up 1%
    """
    labels = []
    
    for i in range(len(df) - lookforward):
        current_price = df.iloc[i]['close']
        future_prices = df.iloc[i+1:i+lookforward]['close'].values
        
        max_gain = (future_prices.max() - current_price) / current_price
        max_loss = (current_price - future_prices.min()) / current_price
        
        # SWING: 2% target, 1% stop
        if max_gain >= 0.02 and max_gain > max_loss * 1.5:
            labels.append(1)  # BUY
        elif max_loss >= 0.02 and max_loss > max_gain * 1.5:
            labels.append(0)  # SELL
        else:
            # Neutral - use H4 trend
            labels.append(1 if future_prices[-1] > current_price else 0)
    
    # Pad
    labels.extend([labels[-1]] * lookforward if labels else [0] * lookforward)
    return np.array(labels)

# Symbol categories
CATEGORIES = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'indices': ['US30', 'US100', 'US500'],
    'commodities': ['XAUUSD', 'USOIL']
}

feature_engineer = SimpleFeatureEngineer(enhanced_mode=True)

for category, symbols in CATEGORIES.items():
    print(f"\n{'='*70}")
    print(f"CATEGORY: {category.upper()} - SWING TRADING")
    print(f"{'='*70}")
    
    all_features = []
    all_labels = []
    
    for symbol in symbols:
        print(f"\n📊 Processing {symbol}...")
        
        # Load H1, H4, D1 data
        h1_df = load_swing_data(symbol, 'H1')
        h4_df = load_swing_data(symbol, 'H4')
        d1_df = load_swing_data(symbol, 'D1')
        
        if h1_df is None or len(h1_df) < 200:
            print(f"  ⚠️ Insufficient H1 data for {symbol}")
            continue
        
        # Create swing labels from H1 data
        labels = create_swing_labels_h1(h1_df, lookforward=48)
        
        print(f"  Labels: {(labels==1).sum()} BUY, {(labels==0).sum()} SELL")
        
        # Extract features from H1 data (use as M1 for feature engineer)
        for i in range(100, len(h1_df) - 48):
            try:
                # Create request with H1 data
                request = {
                    'current_price': h1_df.iloc[i]['close'],
                    'timeframes': {
                        'm1': {  # Use H1 as "M1"
                            'close': h1_df.iloc[i-50:i]['close'].tolist(),
                            'high': h1_df.iloc[i-50:i]['high'].tolist(),
                            'low': h1_df.iloc[i-50:i]['low'].tolist(),
                            'open': h1_df.iloc[i-50:i]['open'].tolist(),
                            'tick_volume': h1_df.iloc[i-50:i]['tick_volume'].tolist(),
                        },
                        'h1': {  # Use H4 as "H1"
                            'close': h4_df.iloc[max(0,i//4-50):i//4]['close'].tolist() if h4_df is not None else [],
                            'high': h4_df.iloc[max(0,i//4-50):i//4]['high'].tolist() if h4_df is not None else [],
                            'low': h4_df.iloc[max(0,i//4-50):i//4]['low'].tolist() if h4_df is not None else [],
                            'open': h4_df.iloc[max(0,i//4-50):i//4]['open'].tolist() if h4_df is not None else [],
                            'tick_volume': h4_df.iloc[max(0,i//4-50):i//4]['tick_volume'].tolist() if h4_df is not None else [],
                        },
                        'h4': {  # Use D1 as "H4"
                            'close': d1_df.iloc[max(0,i//24-50):i//24]['close'].tolist() if d1_df is not None else [],
                            'high': d1_df.iloc[max(0,i//24-50):i//24]['high'].tolist() if d1_df is not None else [],
                            'low': d1_df.iloc[max(0,i//24-50):i//24]['low'].tolist() if d1_df is not None else [],
                            'open': d1_df.iloc[max(0,i//24-50):i//24]['open'].tolist() if d1_df is not None else [],
                            'tick_volume': d1_df.iloc[max(0,i//24-50):i//24]['tick_volume'].tolist() if d1_df is not None else [],
                        },
                    },
                    'indicators': {}
                }
                
                features = feature_engineer.engineer_features(request)
                
                if len(features) >= 160:
                    all_features.append(list(features.values())[:162])
                    all_labels.append(labels[i])
            except Exception as e:
                continue
        
        print(f"  ✅ Extracted {len(all_features)} swing samples")
    
    if len(all_features) < 100:
        print(f"\n⚠️ Not enough data for {category}, skipping...")
        continue
    
    # Convert to arrays
    X = np.array(all_features)
    y = np.array(all_labels)
    
    print(f"\n{category.upper()} Combined: {len(X)} samples, {X.shape[1]} features")
    print(f"  BUY: {(y==1).sum()} ({(y==1).sum()/len(y)*100:.1f}%)")
    print(f"  SELL: {(y==0).sum()} ({(y==0).sum()/len(y)*100:.1f}%)")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\n🤖 Training SWING models for {category}...")
    print(f"  Train: {len(X_train)} | Test: {len(X_test)}")
    
    # RandomForest - SWING parameters
    rf_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    rf_acc = rf_model.score(X_test, y_test)
    print(f"  RF Accuracy: {rf_acc*100:.2f}%")
    
    # GradientBoosting - SWING parameters
    gb_model = GradientBoostingClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        learning_rate=0.03,
        random_state=42
    )
    gb_model.fit(X_train, y_train)
    gb_acc = gb_model.score(X_test, y_test)
    print(f"  GB Accuracy: {gb_acc*100:.2f}%")
    
    # Ensemble
    rf_pred = rf_model.predict(X_test)
    gb_pred = gb_model.predict(X_test)
    ensemble_pred = ((rf_pred + gb_pred) / 2 > 0.5).astype(int)
    ensemble_acc = (ensemble_pred == y_test).mean()
    print(f"  Ensemble: {ensemble_acc*100:.2f}%")
    
    # Save
    model_data = {
        'rf_model': rf_model,
        'gb_model': gb_model,
        'feature_count': X.shape[1],
        'accuracy': ensemble_acc,
        'training_samples': len(X_train),
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': 'swing_h1h4d1_v1',
        'trading_style': 'swing',
        'timeframes': 'H1, H4, D1',
        'targets': '2-5%',
        'stops': '1-2%',
        'note': 'SWING TRADING: H1/H4/D1 data, 2% targets, hold hours/days, $200K account'
    }
    
    model_path = f"{MODELS_PATH}{category}_ensemble_latest.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"  ✅ Saved: {model_path}")

print("\n" + "=" * 70)
print("✅ SWING TRADING MODELS COMPLETE!")
print("=" * 70)
print("\nNext: Create individual symbol models and restart API")
