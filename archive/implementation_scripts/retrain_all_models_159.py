#!/usr/bin/env python3
"""
Retrain ALL ML models with 159 features from 7 timeframes
Uses the current FeatureEngineer to ensure compatibility
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import yfinance as yf
from loguru import logger

# Import our feature engineer - load directly from file
import sys
import importlib.util

spec = importlib.util.spec_from_file_location(
    "feature_engineer",
    "/Users/justinhardison/ai-trading-system/src/features/feature_engineer.py"
)
feature_engineer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature_engineer_module)
FeatureEngineer = feature_engineer_module.FeatureEngineer

logger.add("training_159_features.log", rotation="10 MB")

def download_data(symbol, period="6mo"):
    """Download historical data from Yahoo Finance"""
    logger.info(f"Downloading {symbol} data for {period}...")
    
    # Map our symbols to Yahoo Finance tickers
    ticker_map = {
        'forex': {
            'EURUSD': 'EURUSD=X',
            'GBPUSD': 'GBPUSD=X',
            'USDJPY': 'USDJPY=X',
            'AUDUSD': 'AUDUSD=X',
            'USDCAD': 'USDCAD=X'
        },
        'indices': {
            'US100': '^IXIC',  # NASDAQ
            'US30': '^DJI',    # Dow Jones
            'SPX500': '^GSPC'  # S&P 500
        },
        'commodities': {
            'XAUUSD': 'GC=F',  # Gold
            'XAGUSD': 'SI=F',  # Silver
            'USOIL': 'CL=F'    # Crude Oil
        }
    }
    
    # Find the ticker
    ticker = None
    for category, symbols in ticker_map.items():
        if symbol in symbols:
            ticker = symbols[symbol]
            break
    
    if not ticker:
        logger.warning(f"Unknown symbol {symbol}, using default")
        ticker = symbol
    
    try:
        data = yf.download(ticker, period=period, interval='1h', progress=False)
        if data.empty:
            logger.error(f"No data downloaded for {symbol}")
            return None
        
        logger.info(f"Downloaded {len(data)} bars for {symbol}")
        return data
    except Exception as e:
        logger.error(f"Error downloading {symbol}: {e}")
        return None

def create_labels(df, forward_periods=5):
    """Create labels: 0=SELL, 1=HOLD, 2=BUY"""
    df = df.copy()
    
    # Calculate forward returns
    df['forward_return'] = df['Close'].pct_change(forward_periods).shift(-forward_periods)
    
    # Create labels based on forward returns
    # BUY if price goes up > 0.3%
    # SELL if price goes down < -0.3%
    # HOLD otherwise
    df['label'] = 1  # Default HOLD
    df.loc[df['forward_return'] > 0.003, 'label'] = 2  # BUY
    df.loc[df['forward_return'] < -0.003, 'label'] = 0  # SELL
    
    # Drop rows with NaN labels
    df = df.dropna(subset=['label'])
    
    logger.info(f"Labels distribution:")
    logger.info(f"  SELL: {(df['label'] == 0).sum()} ({(df['label'] == 0).sum() / len(df) * 100:.1f}%)")
    logger.info(f"  HOLD: {(df['label'] == 1).sum()} ({(df['label'] == 1).sum() / len(df) * 100:.1f}%)")
    logger.info(f"  BUY:  {(df['label'] == 2).sum()} ({(df['label'] == 2).sum() / len(df) * 100:.1f}%)")
    
    return df

def extract_features_with_engineer(df):
    """Extract 159 features using FeatureEngineer"""
    logger.info("Extracting 159 features using FeatureEngineer...")
    
    engineer = FeatureEngineer()
    
    # Prepare timeframes dict (simulate what EA sends)
    timeframes = {
        'm1': df.copy(),
        'm5': df.copy(),
        'm15': df.copy(),
        'm30': df.copy(),
        'h1': df.copy(),
        'h4': df.copy(),
        'd1': df.copy()
    }
    
    all_features = []
    
    for i in range(100, len(df)):  # Need history for features
        try:
            # Get slice of data up to current bar
            current_timeframes = {
                tf: data.iloc[:i+1].copy() 
                for tf, data in timeframes.items()
            }
            
            # Extract features
            features = engineer.extract_features(current_timeframes)
            
            if len(features) == 159:
                all_features.append(features)
            else:
                logger.warning(f"Bar {i}: Got {len(features)} features instead of 159")
                
        except Exception as e:
            logger.error(f"Error extracting features at bar {i}: {e}")
            continue
    
    logger.info(f"Extracted features for {len(all_features)} bars")
    
    # Convert to DataFrame
    feature_df = pd.DataFrame(all_features)
    
    # Align with labels (skip first 100 bars)
    labels = df['label'].iloc[100:100+len(feature_df)].values
    
    logger.info(f"Feature matrix shape: {feature_df.shape}")
    logger.info(f"Labels shape: {labels.shape}")
    
    return feature_df, labels

def train_ensemble_model(X_train, y_train, X_test, y_test, model_name):
    """Train ensemble model with RF + GB"""
    logger.info(f"\n{'='*70}")
    logger.info(f"Training {model_name}")
    logger.info(f"{'='*70}")
    
    # Train Random Forest
    logger.info("Training Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
        class_weight='balanced'
    )
    rf.fit(X_train, y_train)
    
    # Train Gradient Boosting
    logger.info("Training Gradient Boosting...")
    gb = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42
    )
    gb.fit(X_train, y_train)
    
    # Evaluate
    rf_pred = rf.predict(X_test)
    gb_pred = gb.predict(X_test)
    
    rf_acc = accuracy_score(y_test, rf_pred)
    gb_acc = accuracy_score(y_test, gb_pred)
    
    logger.info(f"\nRandom Forest Accuracy: {rf_acc:.4f}")
    logger.info(f"Gradient Boosting Accuracy: {gb_acc:.4f}")
    
    # Ensemble prediction (voting)
    ensemble_pred = np.round((rf_pred + gb_pred) / 2).astype(int)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    
    logger.info(f"Ensemble Accuracy: {ensemble_acc:.4f}")
    
    # Classification report
    logger.info("\nClassification Report:")
    logger.info(classification_report(y_test, ensemble_pred, 
                                     target_names=['SELL', 'HOLD', 'BUY']))
    
    # Create ensemble dict
    ensemble = {
        'rf_model': rf,
        'gb_model': gb,
        'feature_count': X_train.shape[1],
        'trained_date': datetime.now().isoformat(),
        'accuracy': ensemble_acc,
        'version': '159_features_7_timeframes'
    }
    
    return ensemble

def main():
    logger.info("="*70)
    logger.info("RETRAINING ALL MODELS WITH 159 FEATURES")
    logger.info("="*70)
    
    models_dir = '/Users/justinhardison/ai-trading-system/models'
    os.makedirs(models_dir, exist_ok=True)
    
    # Define symbol groups
    symbol_groups = {
        'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
        'indices': ['US100', 'US30', 'SPX500'],
        'commodities': ['XAUUSD', 'USOIL']
    }
    
    trained_models = {}
    
    for category, symbols in symbol_groups.items():
        logger.info(f"\n{'='*70}")
        logger.info(f"TRAINING {category.upper()} MODELS")
        logger.info(f"{'='*70}")
        
        # Collect data from all symbols in category
        all_features = []
        all_labels = []
        
        for symbol in symbols:
            logger.info(f"\nProcessing {symbol}...")
            
            # Download data
            df = download_data(symbol, period="6mo")
            if df is None or len(df) < 200:
                logger.warning(f"Insufficient data for {symbol}, skipping")
                continue
            
            # Create labels
            df = create_labels(df)
            
            # Extract features
            features, labels = extract_features_with_engineer(df)
            
            if len(features) > 0:
                all_features.append(features)
                all_labels.append(labels)
                logger.info(f"✅ {symbol}: {len(features)} samples")
        
        if not all_features:
            logger.error(f"No data for {category}, skipping")
            continue
        
        # Combine all data
        X = pd.concat(all_features, ignore_index=True)
        y = np.concatenate(all_labels)
        
        logger.info(f"\n{category.upper()} Combined Dataset:")
        logger.info(f"  Total samples: {len(X)}")
        logger.info(f"  Features: {X.shape[1]}")
        logger.info(f"  Labels: {len(y)}")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train ensemble
        ensemble = train_ensemble_model(
            X_train, y_train, X_test, y_test,
            f"{category}_ensemble"
        )
        
        # Save model
        model_path = os.path.join(models_dir, f'{category}_ensemble_latest.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(ensemble, f)
        
        logger.info(f"✅ Saved {category} model to {model_path}")
        trained_models[category] = ensemble
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("TRAINING COMPLETE!")
    logger.info("="*70)
    
    for category, model in trained_models.items():
        logger.info(f"\n{category.upper()}:")
        logger.info(f"  Features: {model['feature_count']}")
        logger.info(f"  Accuracy: {model['accuracy']:.4f}")
        logger.info(f"  Version: {model['version']}")
    
    logger.info("\n✅ All models retrained with 159 features from 7 timeframes!")
    logger.info("🔄 Restart the API to load new models")

if __name__ == "__main__":
    main()
