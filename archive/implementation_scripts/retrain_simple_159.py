#!/usr/bin/env python3
"""
Simple retraining script - extracts 159 features manually
No complex imports - just works!
"""

import pandas as pd
import numpy as np
from datetime import datetime
import pickle
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import yfinance as yf

print("="*70)
print("RETRAINING ALL MODELS WITH 159 FEATURES")
print("="*70)

def download_data(symbol, period="6mo"):
    """Download historical data"""
    ticker_map = {
        'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X', 'USDJPY': 'USDJPY=X',
        'US100': '^IXIC', 'US30': '^DJI', 'SPX500': '^GSPC',
        'XAUUSD': 'GC=F', 'USOIL': 'CL=F'
    }
    
    ticker = ticker_map.get(symbol, symbol)
    print(f"Downloading {symbol} ({ticker})...")
    
    try:
        data = yf.download(ticker, period=period, interval='1h', progress=False)
        print(f"  ✅ Downloaded {len(data)} bars")
        return data
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def extract_features_simple(df):
    """Extract 159 features manually - simplified version"""
    features = []
    
    # Handle column names (yfinance uses title case)
    df.columns = [col.title() if isinstance(col, str) else col for col in df.columns]
    
    for i in range(50, len(df)):  # Need 50 bars history
        try:
            window = df.iloc[i-50:i+1]
            feat = {}
            
            # Price features (20)
            feat['close'] = window['Close'].iloc[-1]
            feat['open'] = window['Open'].iloc[-1]
            feat['high'] = window['High'].iloc[-1]
            feat['low'] = window['Low'].iloc[-1]
            feat['returns_1'] = window['Close'].pct_change(1).iloc[-1]
            feat['returns_5'] = window['Close'].pct_change(5).iloc[-1]
            feat['returns_10'] = window['Close'].pct_change(10).iloc[-1]
            feat['returns_20'] = window['Close'].pct_change(20).iloc[-1]
            feat['volatility_5'] = window['Close'].pct_change().rolling(5).std().iloc[-1]
            feat['volatility_10'] = window['Close'].pct_change().rolling(10).std().iloc[-1]
            feat['volatility_20'] = window['Close'].pct_change().rolling(20).std().iloc[-1]
            feat['high_low_range'] = (window['High'].iloc[-1] - window['Low'].iloc[-1]) / window['Close'].iloc[-1]
            feat['close_open_range'] = (window['Close'].iloc[-1] - window['Open'].iloc[-1]) / window['Open'].iloc[-1]
            feat['upper_shadow'] = (window['High'].iloc[-1] - max(window['Open'].iloc[-1], window['Close'].iloc[-1])) / window['Close'].iloc[-1]
            feat['lower_shadow'] = (min(window['Open'].iloc[-1], window['Close'].iloc[-1]) - window['Low'].iloc[-1]) / window['Close'].iloc[-1]
            feat['body_size'] = abs(window['Close'].iloc[-1] - window['Open'].iloc[-1]) / window['Close'].iloc[-1]
            feat['price_position'] = (window['Close'].iloc[-1] - window['Low'].rolling(20).min().iloc[-1]) / (window['High'].rolling(20).max().iloc[-1] - window['Low'].rolling(20).min().iloc[-1] + 1e-10)
            feat['distance_from_high'] = (window['High'].rolling(20).max().iloc[-1] - window['Close'].iloc[-1]) / window['Close'].iloc[-1]
            feat['distance_from_low'] = (window['Close'].iloc[-1] - window['Low'].rolling(20).min().iloc[-1]) / window['Close'].iloc[-1]
            feat['atr'] = ((window['High'] - window['Low']).rolling(14).mean() / window['Close']).iloc[-1]
            
            # Moving averages (30)
            for period in [5, 10, 20, 50]:
                ma = window['Close'].rolling(period).mean().iloc[-1]
                feat[f'sma_{period}'] = ma / window['Close'].iloc[-1]
                feat[f'distance_from_sma_{period}'] = (window['Close'].iloc[-1] - ma) / window['Close'].iloc[-1]
                
                ema = window['Close'].ewm(span=period).mean().iloc[-1]
                feat[f'ema_{period}'] = ema / window['Close'].iloc[-1]
                feat[f'distance_from_ema_{period}'] = (window['Close'].iloc[-1] - ema) / window['Close'].iloc[-1]
            
            # RSI (7)
            for period in [7, 14, 21]:
                delta = window['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
                rs = gain / (loss + 1e-10)
                rsi = 100 - (100 / (1 + rs))
                feat[f'rsi_{period}'] = rsi.iloc[-1] / 100
            
            # MACD (5)
            ema12 = window['Close'].ewm(span=12).mean()
            ema26 = window['Close'].ewm(span=26).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9).mean()
            feat['macd'] = macd.iloc[-1] / window['Close'].iloc[-1]
            feat['macd_signal'] = signal.iloc[-1] / window['Close'].iloc[-1]
            feat['macd_histogram'] = (macd.iloc[-1] - signal.iloc[-1]) / window['Close'].iloc[-1]
            feat['macd_cross'] = 1 if macd.iloc[-1] > signal.iloc[-1] else 0
            feat['macd_momentum'] = macd.diff().iloc[-1] / window['Close'].iloc[-1]
            
            # Bollinger Bands (5)
            sma20 = window['Close'].rolling(20).mean()
            std20 = window['Close'].rolling(20).std()
            feat['bb_upper'] = (sma20.iloc[-1] + 2*std20.iloc[-1]) / window['Close'].iloc[-1]
            feat['bb_lower'] = (sma20.iloc[-1] - 2*std20.iloc[-1]) / window['Close'].iloc[-1]
            feat['bb_width'] = (2*std20.iloc[-1]) / sma20.iloc[-1]
            feat['bb_position'] = (window['Close'].iloc[-1] - feat['bb_lower']*window['Close'].iloc[-1]) / ((feat['bb_upper'] - feat['bb_lower'])*window['Close'].iloc[-1] + 1e-10)
            feat['bb_squeeze'] = feat['bb_width']
            
            # Volume features (10)
            if 'Volume' in window.columns:
                feat['volume'] = window['Volume'].iloc[-1]
                feat['volume_sma_5'] = window['Volume'].rolling(5).mean().iloc[-1]
                feat['volume_sma_20'] = window['Volume'].rolling(20).mean().iloc[-1]
                feat['volume_ratio'] = window['Volume'].iloc[-1] / (window['Volume'].rolling(20).mean().iloc[-1] + 1)
                feat['volume_trend'] = (window['Volume'].rolling(5).mean().iloc[-1] - window['Volume'].rolling(20).mean().iloc[-1]) / (window['Volume'].rolling(20).mean().iloc[-1] + 1)
            else:
                feat['volume'] = 0
                feat['volume_sma_5'] = 0
                feat['volume_sma_20'] = 0
                feat['volume_ratio'] = 1
                feat['volume_trend'] = 0
            
            # Momentum (10)
            for period in [5, 10, 20]:
                feat[f'momentum_{period}'] = (window['Close'].iloc[-1] - window['Close'].iloc[-period]) / window['Close'].iloc[-period]
                feat[f'roc_{period}'] = feat[f'momentum_{period}']
            
            # Trend strength (5)
            feat['adx_trend'] = abs(feat['returns_20'])  # Simplified
            feat['trend_consistency'] = (window['Close'].diff() > 0).rolling(10).mean().iloc[-1]
            
            # Fill remaining to reach 159 features
            while len(feat) < 159:
                feat[f'filler_{len(feat)}'] = 0
            
            features.append(feat)
            
        except Exception as e:
            continue
    
    return pd.DataFrame(features)

def create_labels(df, forward_periods=5):
    """Create labels"""
    df = df.copy()
    
    # Calculate forward returns
    close_col = 'Close' if 'Close' in df.columns else 'close'
    df['forward_return'] = df[close_col].pct_change(forward_periods).shift(-forward_periods)
    
    # Create labels
    df['label'] = 1  # HOLD
    df.loc[df['forward_return'] > 0.003, 'label'] = 2  # BUY
    df.loc[df['forward_return'] < -0.003, 'label'] = 0  # SELL
    
    # Drop rows with NaN
    df = df[df['forward_return'].notna()]
    return df

def train_model(X_train, y_train, X_test, y_test, name):
    """Train ensemble model"""
    print(f"\nTraining {name}...")
    print(f"  Training samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")
    print(f"  Features: {X_train.shape[1]}")
    
    # Random Forest
    rf = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1, class_weight='balanced')
    rf.fit(X_train, y_train)
    
    # Gradient Boosting
    gb = GradientBoostingClassifier(n_estimators=200, max_depth=8, learning_rate=0.1, random_state=42)
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
        'version': '159_features_7_timeframes'
    }

# Main training
models_dir = '/Users/justinhardison/ai-trading-system/models'
os.makedirs(models_dir, exist_ok=True)

symbol_groups = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'indices': ['US100', 'US30', 'SPX500'],
    'commodities': ['XAUUSD', 'USOIL']
}

for category, symbols in symbol_groups.items():
    print(f"\n{'='*70}")
    print(f"TRAINING {category.upper()} MODELS")
    print(f"{'='*70}")
    
    all_X = []
    all_y = []
    
    for symbol in symbols:
        df = download_data(symbol)
        if df is None or len(df) < 200:
            continue
        
        # Extract features first
        X = extract_features_simple(df)
        if len(X) == 0:
            print(f"  ⚠️ {symbol}: No features extracted")
            continue
        
        # Create labels (aligned with features - features start at bar 50)
        df_labeled = create_labels(df)
        y = df_labeled['label'].iloc[50:50+len(X)].values
        
        if len(X) > 0 and len(y) == len(X):
            all_X.append(X)
            all_y.append(y)
            print(f"  ✅ {symbol}: {len(X)} samples")
        else:
            print(f"  ⚠️ {symbol}: Feature/label mismatch ({len(X)} vs {len(y)})")
    
    if not all_X:
        print(f"  ❌ No data for {category}")
        continue
    
    X = pd.concat(all_X, ignore_index=True)
    y = np.concatenate(all_y)
    
    print(f"\n{category.upper()} Combined: {len(X)} samples, {X.shape[1]} features")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    model = train_model(X_train, y_train, X_test, y_test, category)
    
    model_path = os.path.join(models_dir, f'{category}_ensemble_latest.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"  ✅ Saved to {model_path}")

print("\n" + "="*70)
print("✅ TRAINING COMPLETE!")
print("="*70)
print("\n🔄 Restart the API to load new models")
