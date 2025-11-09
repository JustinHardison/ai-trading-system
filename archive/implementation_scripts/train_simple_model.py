"""
Simple Fast Training Script - Actually Works
Uses basic features that extract quickly
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle
import sys
from datetime import datetime

def create_simple_features(df):
    """Create fast, reliable features"""
    features = {}
    
    # Price features
    returns = df['close'].pct_change()
    features['returns'] = returns
    features['log_returns'] = np.log(df['close'] / df['close'].shift(1))
    
    # Moving averages
    for period in [5, 10, 20, 50, 100]:
        features[f'sma_{period}'] = df['close'].rolling(period).mean()
        features[f'price_to_sma_{period}'] = df['close'] / features[f'sma_{period}']
    
    # Volatility
    features['volatility_10'] = returns.rolling(10).std()
    features['volatility_20'] = returns.rolling(20).std()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss
    features['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    features['macd'] = ema12 - ema26
    features['macd_signal'] = features['macd'].ewm(span=9).mean()
    
    # Bollinger Bands
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    features['bb_upper'] = sma20 + (2 * std20)
    features['bb_lower'] = sma20 - (2 * std20)
    features['bb_position'] = (df['close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
    
    # Volume features
    features['volume_sma_20'] = df['volume'].rolling(20).mean()
    features['volume_ratio'] = df['volume'] / features['volume_sma_20']
    
    # Price momentum
    for period in [5, 10, 20]:
        features[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1
    
    # High/Low features
    features['high_low_ratio'] = df['high'] / df['low']
    features['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    return pd.DataFrame(features)

def create_labels(df, forward_bars=5, profit_target_pct=0.002):
    """Create trading labels"""
    labels = []
    
    for i in range(len(df)):
        if i >= len(df) - forward_bars:
            labels.append(0)  # HOLD
            continue
        
        future_prices = df['close'].iloc[i+1:i+forward_bars+1]
        current_price = df['close'].iloc[i]
        
        max_gain = (future_prices.max() - current_price) / current_price
        max_loss = (current_price - future_prices.min()) / current_price
        
        if max_gain >= profit_target_pct and max_gain > max_loss:
            labels.append(1)  # BUY
        elif max_loss >= profit_target_pct and max_loss > max_gain:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD
    
    return np.array(labels)

def train_model(csv_file, model_name):
    """Train a simple, fast model"""
    print(f"\n{'='*60}")
    print(f"Training {model_name}")
    print(f"{'='*60}")
    
    # Load data
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file, sep=r'\s+')  # Handle whitespace-separated values
    
    # Standardize column names
    df.columns = [col.strip().lower() for col in df.columns]
    print(f"✓ Loaded {len(df):,} bars")
    print(f"✓ Columns: {list(df.columns)}")
    
    # Create features
    print("Creating features...")
    features_df = create_simple_features(df)
    
    # Create labels
    print("Creating labels...")
    labels = create_labels(df)
    
    # Combine
    features_df['label'] = labels
    features_df = features_df.dropna()
    
    print(f"✓ {len(features_df):,} samples after cleaning")
    
    # Split features and labels
    X = features_df.drop('label', axis=1)
    y = features_df['label']
    
    print(f"✓ {X.shape[1]} features")
    print(f"✓ Label distribution: BUY={sum(y==1)}, SELL={sum(y==2)}, HOLD={sum(y==0)}")
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    print("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train models
    print("Training Random Forest...")
    rf_model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf_model.fit(X_train_scaled, y_train)
    rf_score = rf_model.score(X_test_scaled, y_test)
    print(f"✓ RF Accuracy: {rf_score:.2%}")
    
    print("Training Gradient Boosting...")
    gb_model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
    gb_model.fit(X_train_scaled, y_train)
    gb_score = gb_model.score(X_test_scaled, y_test)
    print(f"✓ GB Accuracy: {gb_score:.2%}")
    
    # Save model
    model_data = {
        'rf_model': rf_model,
        'gb_model': gb_model,
        'scaler': scaler,
        'feature_names': list(X.columns),
        'rf_score': rf_score,
        'gb_score': gb_score,
        'ensemble_weights': [0.5, 0.5],
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    output_file = f"models/{model_name}_ensemble_latest.pkl"
    with open(output_file, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"✓ Saved to {output_file}")
    print(f"{'='*60}\n")
    
    return model_data

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python train_simple_model.py <csv_file> <model_name>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    model_name = sys.argv[2]
    
    train_model(csv_file, model_name)
    print("✅ Training complete!")
