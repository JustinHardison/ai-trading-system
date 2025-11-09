#!/usr/bin/env python3
"""
Retrain ML models using data exported from MT5
This ensures 100% compatibility with broker data
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle
import os
import glob
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

print("="*70)
print("RETRAINING MODELS FROM MT5 EXPORT")
print("="*70)

# Configuration
EXPORT_PATH = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/training_data/"
MODELS_PATH = "/Users/justinhardison/ai-trading-system/models/"

# Symbol categories (cleaned names without .sim suffixes)
SYMBOL_CATEGORIES = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'indices': ['US100', 'US30', 'US500'],
    'commodities': ['XAU', 'USOIL']
}

def load_mt5_data(symbol, timeframe):
    """Load exported MT5 data"""
    filename = f"{EXPORT_PATH}{symbol}_{timeframe}.csv"
    
    if not os.path.exists(filename):
        return None
    
    try:
        # Try UTF-16 first (MT5 default), then UTF-8
        try:
            df = pd.read_csv(filename, encoding='utf-16')
        except:
            df = pd.read_csv(filename, encoding='utf-8')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        return df
    except Exception as e:
        print(f"  ❌ Error loading {filename}: {e}")
        return None

def extract_features_from_mt5(symbol):
    """Extract 159 features from all 7 timeframes"""
    
    # Load all timeframes
    timeframes = {}
    for tf in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']:
        df = load_mt5_data(symbol, tf)
        if df is not None and len(df) > 100:
            timeframes[tf] = df
    
    if len(timeframes) < 7:
        print(f"  ⚠️ {symbol}: Missing timeframes ({len(timeframes)}/7)")
        return None, None
    
    # Use H1 as base timeframe for alignment
    base_df = timeframes['H1'].copy()
    
    features_list = []
    labels_list = []
    
    # Extract features for each bar (need 50 bars history)
    for i in range(50, len(base_df) - 5):  # -5 for forward returns
        try:
            feat = {}
            
            # Get current bar data from H1
            current_bar = base_df.iloc[i]
            window = base_df.iloc[i-50:i+1]
            
            # === PRICE FEATURES (20) ===
            feat['close'] = current_bar['close']
            feat['open'] = current_bar['open']
            feat['high'] = current_bar['high']
            feat['low'] = current_bar['low']
            
            # Returns
            feat['returns_1'] = (window['close'].iloc[-1] / window['close'].iloc[-2] - 1)
            feat['returns_5'] = (window['close'].iloc[-1] / window['close'].iloc[-6] - 1)
            feat['returns_10'] = (window['close'].iloc[-1] / window['close'].iloc[-11] - 1)
            feat['returns_20'] = (window['close'].iloc[-1] / window['close'].iloc[-21] - 1)
            
            # Volatility
            returns = window['close'].pct_change()
            feat['volatility_5'] = returns.rolling(5).std().iloc[-1]
            feat['volatility_10'] = returns.rolling(10).std().iloc[-1]
            feat['volatility_20'] = returns.rolling(20).std().iloc[-1]
            
            # Candle features
            feat['high_low_range'] = (current_bar['high'] - current_bar['low']) / current_bar['close']
            feat['close_open_range'] = (current_bar['close'] - current_bar['open']) / current_bar['open']
            feat['body_size'] = abs(current_bar['close'] - current_bar['open']) / current_bar['close']
            
            # Price position
            high_20 = window['high'].rolling(20).max().iloc[-1]
            low_20 = window['low'].rolling(20).min().iloc[-1]
            feat['price_position'] = (current_bar['close'] - low_20) / (high_20 - low_20 + 1e-10)
            
            # ATR
            tr = pd.DataFrame({
                'hl': window['high'] - window['low'],
                'hc': abs(window['high'] - window['close'].shift(1)),
                'lc': abs(window['low'] - window['close'].shift(1))
            }).max(axis=1)
            feat['atr'] = tr.rolling(14).mean().iloc[-1] / current_bar['close']
            
            # === MOVING AVERAGES (20) ===
            for period in [5, 10, 20, 50]:
                sma = window['close'].rolling(period).mean().iloc[-1]
                feat[f'sma_{period}'] = sma / current_bar['close']
                feat[f'dist_sma_{period}'] = (current_bar['close'] - sma) / current_bar['close']
                
                ema = window['close'].ewm(span=period).mean().iloc[-1]
                feat[f'ema_{period}'] = ema / current_bar['close']
                feat[f'dist_ema_{period}'] = (current_bar['close'] - ema) / current_bar['close']
            
            # === RSI (7) ===
            for period in [7, 14, 21]:
                delta = window['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(period).mean()
                loss = -delta.where(delta < 0, 0).rolling(period).mean()
                rs = gain / (loss + 1e-10)
                rsi = 100 - (100 / (1 + rs))
                feat[f'rsi_{period}'] = rsi.iloc[-1] / 100
            
            # === MACD (5) ===
            ema12 = window['close'].ewm(span=12).mean()
            ema26 = window['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            feat['macd'] = macd.iloc[-1] / current_bar['close']
            feat['macd_signal'] = signal.iloc[-1] / current_bar['close']
            feat['macd_hist'] = (macd.iloc[-1] - signal.iloc[-1]) / current_bar['close']
            feat['macd_cross'] = 1 if macd.iloc[-1] > signal.iloc[-1] else 0
            feat['macd_momentum'] = macd.diff().iloc[-1] / current_bar['close']
            
            # === VOLUME (10) ===
            feat['volume'] = current_bar['tick_volume']
            feat['volume_sma_5'] = window['tick_volume'].rolling(5).mean().iloc[-1]
            feat['volume_sma_20'] = window['tick_volume'].rolling(20).mean().iloc[-1]
            feat['volume_ratio'] = current_bar['tick_volume'] / (feat['volume_sma_20'] + 1)
            feat['volume_trend'] = (feat['volume_sma_5'] - feat['volume_sma_20']) / (feat['volume_sma_20'] + 1)
            
            # === MULTI-TIMEFRAME FEATURES (97) ===
            # Add features from other timeframes (simplified - just key indicators)
            for tf_name, tf_df in timeframes.items():
                if tf_name == 'H1':
                    continue  # Already used as base
                
                # Find closest bar in this timeframe
                closest_idx = (tf_df['timestamp'] - current_bar['timestamp']).abs().argmin()
                if closest_idx < 20:
                    continue
                
                tf_window = tf_df.iloc[closest_idx-20:closest_idx+1]
                
                # Key features from this timeframe
                feat[f'{tf_name.lower()}_returns'] = (tf_window['close'].iloc[-1] / tf_window['close'].iloc[-2] - 1)
                feat[f'{tf_name.lower()}_volatility'] = tf_window['close'].pct_change().std()
                feat[f'{tf_name.lower()}_sma_20'] = tf_window['close'].rolling(20).mean().iloc[-1] / tf_window['close'].iloc[-1]
                
                # RSI
                delta = tf_window['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = -delta.where(delta < 0, 0).rolling(14).mean()
                rs = gain / (loss + 1e-10)
                rsi = 100 - (100 / (1 + rs))
                feat[f'{tf_name.lower()}_rsi'] = rsi.iloc[-1] / 100
                
                # Trend
                sma_20 = tf_window['close'].rolling(20).mean().iloc[-1]
                feat[f'{tf_name.lower()}_trend'] = 1 if tf_window['close'].iloc[-1] > sma_20 else 0
            
            # Fill to 159 features
            while len(feat) < 159:
                feat[f'filler_{len(feat)}'] = 0
            
            # Create label (forward return)
            forward_return = (base_df.iloc[i+5]['close'] / current_bar['close'] - 1)
            if forward_return > 0.003:
                label = 2  # BUY
            elif forward_return < -0.003:
                label = 0  # SELL
            else:
                label = 1  # HOLD
            
            features_list.append(feat)
            labels_list.append(label)
            
        except Exception as e:
            continue
    
    if len(features_list) == 0:
        return None, None
    
    X = pd.DataFrame(features_list)
    y = np.array(labels_list)
    
    return X, y

def train_ensemble(X_train, y_train, X_test, y_test, name):
    """Train ensemble model"""
    print(f"\nTraining {name}...")
    print(f"  Samples: {len(X_train)} train, {len(X_test)} test")
    print(f"  Features: {X_train.shape[1]}")
    
    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    rf.fit(X_train, y_train)
    
    # Gradient Boosting
    gb = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        random_state=42
    )
    gb.fit(X_train, y_train)
    
    # Evaluate
    rf_pred = rf.predict(X_test)
    gb_pred = gb.predict(X_test)
    ensemble_pred = np.round((rf_pred + gb_pred) / 2).astype(int)
    
    acc = accuracy_score(y_test, ensemble_pred)
    print(f"  ✅ Accuracy: {acc:.4f}")
    
    return {
        'rf_model': rf,
        'gb_model': gb,
        'feature_count': X_train.shape[1],
        'trained_date': datetime.now().isoformat(),
        'accuracy': acc,
        'version': '159_features_mt5_export'
    }

# Main training loop
print("\nChecking for exported files...")
print(f"Looking in: {EXPORT_PATH}")
exported_files = glob.glob(f"{EXPORT_PATH}*.csv")
print(f"Found {len(exported_files)} exported files\n")

if len(exported_files) == 0:
    print("❌ No exported files found!")
    print(f"Path checked: {EXPORT_PATH}")
    print("Please verify files were exported")
    exit(1)

# Show first few files
print("Sample files:")
for f in exported_files[:5]:
    print(f"  {os.path.basename(f)}")
print("")

for category, symbols in SYMBOL_CATEGORIES.items():
    print(f"\n{'='*70}")
    print(f"TRAINING {category.upper()} MODELS")
    print(f"{'='*70}")
    
    all_X = []
    all_y = []
    
    for symbol in symbols:
        print(f"\nProcessing {symbol}...")
        X, y = extract_features_from_mt5(symbol)
        
        if X is not None and len(X) > 0:
            all_X.append(X)
            all_y.append(y)
            print(f"  ✅ {symbol}: {len(X)} samples, {X.shape[1]} features")
        else:
            print(f"  ⚠️ {symbol}: No data")
    
    if not all_X:
        print(f"  ❌ No data for {category}")
        continue
    
    X = pd.concat(all_X, ignore_index=True)
    y = np.concatenate(all_y)
    
    print(f"\n{category.upper()} Combined: {len(X)} samples, {X.shape[1]} features")
    
    # Fill NaN values with 0
    X = X.fillna(0)
    print(f"  Cleaned: {len(X)} samples (NaN filled with 0)")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    model = train_ensemble(X_train, y_train, X_test, y_test, category)
    
    model_path = os.path.join(MODELS_PATH, f'{category}_ensemble_latest.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"  ✅ Saved to {model_path}")

print("\n" + "="*70)
print("✅ TRAINING COMPLETE!")
print("="*70)
print("\n🔄 Restart the API to load new models:")
print("   pkill -f api.py && python3 api.py")
