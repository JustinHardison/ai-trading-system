"""
Retrain models using SimpleFeatureEngineer - MATCHES API EXACTLY
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pickle
import glob
from datetime import datetime
from src.features.simple_feature_engineer import SimpleFeatureEngineer

# Paths
EXPORT_PATH = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/training_data/"
MODELS_PATH = "/Users/justinhardison/ai-trading-system/models/"

# Symbol categories
SYMBOL_CATEGORIES = {
    'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
    'indices': ['US100', 'US30', 'US500'],
    'commodities': ['XAU', 'USOIL']
}

def load_mt5_data(symbol, timeframe):
    """Load MT5 exported CSV data"""
    # Try multiple symbol name variations
    possible_names = [
        f"{symbol}_{timeframe}.csv",
        f"{symbol}G26_{timeframe}.csv",  # Gold with contract
        f"{symbol}F26_{timeframe}.csv",  # Oil with contract
        f"{symbol}Z25_{timeframe}.csv",  # Indices with contract
    ]
    
    for name in possible_names:
        filename = f"{EXPORT_PATH}{name}"
        try:
            try:
                df = pd.read_csv(filename, encoding='utf-16')
            except:
                df = pd.read_csv(filename, encoding='utf-8')
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            return df
        except:
            continue
    
    print(f"  ❌ Could not load {symbol}_{timeframe} (tried {len(possible_names)} variations)")
    return None

def extract_features_with_api_engineer(symbol):
    """Extract features using SimpleFeatureEngineer - EXACTLY like API"""
    
    print(f"\n📊 Processing {symbol}...")
    
    # Load all 7 timeframes
    timeframes = {}
    for tf in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']:
        df = load_mt5_data(symbol, tf)
        # Lower requirement for D1 (commodities have less D1 data)
        min_bars = 50 if tf == 'D1' else 100
        if df is not None and len(df) > min_bars:
            timeframes[tf.lower()] = df.to_dict('records')
            print(f"    ✅ {tf}: {len(df)} bars")
    
    if len(timeframes) < 7:
        print(f"  ⚠️ Missing timeframes ({len(timeframes)}/7)")
        return None, None
    
    # Use H1 as base
    h1_data = pd.DataFrame(timeframes['h1'])
    
    # Initialize feature engineer
    feature_engineer = SimpleFeatureEngineer()
    
    features_list = []
    labels_list = []
    
    # Extract features for each bar
    for i in range(50, len(h1_data) - 5):
        try:
            # Create request-like structure (mimics EA request)
            request = {
                'timeframes': {
                    tf: [timeframes[tf][max(0, i-50):i+1]] for tf in timeframes.keys()
                },
                'current_price': {'bid': h1_data.iloc[i]['close']},
                'account': {'balance': 100000, 'equity': 100000},
                'symbol_info': {'symbol': symbol},
                'indicators': {},
                'positions': [],
                'recent_trades': [],
                'order_book': {'bids': [], 'asks': []},
                'metadata': {}
            }
            
            # Extract features using API's feature engineer
            features = feature_engineer.engineer_features(request)
            
            # Create label (forward return)
            forward_return = (h1_data.iloc[i+5]['close'] / h1_data.iloc[i]['close'] - 1)
            if forward_return > 0.003:
                label = 1  # BUY
            elif forward_return < -0.003:
                label = 0  # SELL
            else:
                continue  # Skip HOLD for now
            
            features_list.append(features)
            labels_list.append(label)
            
        except Exception as e:
            continue
    
    if len(features_list) == 0:
        return None, None
    
    X = pd.DataFrame(features_list)
    y = np.array(labels_list)
    
    print(f"  ✅ Extracted {len(X)} samples with {X.shape[1]} features")
    
    return X, y

def train_ensemble(X_train, y_train, X_test, y_test, name):
    """Train Random Forest + Gradient Boosting ensemble"""
    
    print(f"\n🤖 Training {name}...")
    print(f"  Samples: {len(X_train)} train, {len(X_test)} test")
    print(f"  Features: {X_train.shape[1]}")
    
    # Random Forest
    print("  Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    rf_acc = accuracy_score(y_test, rf.predict(X_test))
    print(f"    RF Accuracy: {rf_acc*100:.2f}%")
    
    # Gradient Boosting
    print("  Training Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42
    )
    gb.fit(X_train, y_train)
    gb_acc = accuracy_score(y_test, gb.predict(X_test))
    print(f"    GB Accuracy: {gb_acc*100:.2f}%")
    
    # Ensemble
    rf_pred = rf.predict(X_test)
    gb_pred = gb.predict(X_test)
    ensemble_pred = ((rf_pred + gb_pred) / 2 > 0.5).astype(int)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    print(f"    Ensemble Accuracy: {ensemble_acc*100:.2f}%")
    
    # Save model
    model = {
        'rf_model': rf,
        'gb_model': gb,
        'feature_count': X_train.shape[1],
        'trained_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'accuracy': ensemble_acc,
        'version': 'api_features_v1'
    }
    
    filename = f"{MODELS_PATH}{name}_ensemble_latest.pkl"
    with open(filename, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"  ✅ Saved: {filename}")
    print(f"  📊 Final Accuracy: {ensemble_acc*100:.2f}%")
    
    return model

def main():
    print("=" * 70)
    print("RETRAINING MODELS WITH API FEATURE ENGINEER")
    print("=" * 70)
    
    for category, symbols in SYMBOL_CATEGORIES.items():
        print(f"\n{'='*70}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*70}")
        
        all_X = []
        all_y = []
        
        for symbol in symbols:
            X, y = extract_features_with_api_engineer(symbol)
            if X is not None:
                all_X.append(X)
                all_y.append(y)
        
        if not all_X:
            print(f"  ❌ No data for {category}")
            continue
        
        # Combine all symbols in category
        X = pd.concat(all_X, ignore_index=True)
        y = np.concatenate(all_y)
        
        print(f"\n{category.upper()} Combined: {len(X)} samples, {X.shape[1]} features")
        
        # Fill NaN
        X = X.fillna(0)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train
        model = train_ensemble(X_train, y_train, X_test, y_test, category)
    
    print("\n" + "="*70)
    print("✅ RETRAINING COMPLETE!")
    print("="*70)
    print("\nModels saved:")
    for category in SYMBOL_CATEGORIES.keys():
        print(f"  - {MODELS_PATH}{category}_ensemble_latest.pkl")
    print("\n🚀 Restart API to use new models!")

if __name__ == "__main__":
    main()
