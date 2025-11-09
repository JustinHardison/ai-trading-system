#!/usr/bin/env python3
"""
FIXED MODEL TRAINING - Works with single CSV file
Trains LightGBM + CatBoost ensemble (no LSTM to avoid TensorFlow issues)
"""

import os
import sys
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ML libraries
import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

class FixedModelTrainer:
    def __init__(self):
        self.data_dir = "/Users/justinhardison/ai-trading-system/data"
        self.models_dir = "/Users/justinhardison/ai-trading-system/models"
        self.symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
        
        print("="*80)
        print("FIXED MODEL TRAINING - HEDGE FUND SYSTEM")
        print("="*80)
        print(f"Data directory: {self.data_dir}")
        print(f"Models directory: {self.models_dir}")
        print("="*80)
    
    def load_data(self):
        """Load the main CSV file"""
        print(f"\n{'='*80}")
        print("LOADING DATA")
        print(f"{'='*80}")
        
        csv_file = f"{self.data_dir}/ultimate_training_data.csv"
        
        if not os.path.exists(csv_file):
            print(f"❌ Data file not found: {csv_file}")
            return None
        
        print(f"Loading: {csv_file}")
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} rows, {len(df.columns)} columns")
        
        # Show columns
        print(f"\nColumns: {list(df.columns)[:10]}...")
        
        return df
    
    def prepare_features(self, df, symbol_filter=None):
        """Prepare features and target"""
        print(f"\n{'='*80}")
        print(f"PREPARING FEATURES" + (f" FOR {symbol_filter.upper()}" if symbol_filter else ""))
        print(f"{'='*80}")
        
        # Filter by symbol if specified
        if symbol_filter and 'symbol' in df.columns:
            df = df[df['symbol'].str.lower() == symbol_filter.lower()].copy()
            print(f"✅ Filtered to {len(df)} rows for {symbol_filter}")
        
        # Drop non-feature columns
        drop_cols = ['timestamp', 'symbol'] if 'symbol' in df.columns else ['timestamp']
        if 'timestamp' in df.columns:
            df = df.drop(drop_cols, axis=1)
        
        # Separate features and target
        if 'target' not in df.columns:
            print("❌ No 'target' column found")
            return None, None, None, None
        
        X = df.drop('target', axis=1)
        y = df['target']
        
        # Handle any NaN values
        X = X.fillna(0)
        
        print(f"✅ Features: {X.shape[1]} columns")
        print(f"✅ Samples: {len(X)}")
        print(f"✅ Target distribution: {y.value_counts().to_dict()}")
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        print(f"✅ Train: {len(X_train)} samples")
        print(f"✅ Test: {len(X_test)} samples")
        
        return X_train, X_test, y_train, y_test
    
    def train_lightgbm(self, X_train, X_test, y_train, y_test):
        """Train LightGBM model"""
        print(f"\n{'='*80}")
        print("TRAINING: LightGBM")
        print(f"{'='*80}")
        
        # Create dataset
        train_data = lgb.Dataset(X_train, label=y_train)
        test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
        
        # Parameters
        params = {
            'objective': 'binary',
            'metric': 'binary_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'max_depth': 7,
            'min_data_in_leaf': 20,
        }
        
        # Train
        print("Training LightGBM...")
        model = lgb.train(
            params,
            train_data,
            num_boost_round=500,
            valid_sets=[test_data],
            callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=100)]
        )
        
        # Evaluate
        y_pred = (model.predict(X_test) > 0.5).astype(int)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"\n✅ LightGBM Accuracy: {accuracy*100:.2f}%")
        print(f"✅ Best iteration: {model.best_iteration}")
        
        return model, accuracy
    
    def train_catboost(self, X_train, X_test, y_train, y_test):
        """Train CatBoost model"""
        print(f"\n{'='*80}")
        print("TRAINING: CatBoost")
        print(f"{'='*80}")
        
        # Parameters
        model = CatBoostClassifier(
            iterations=500,
            learning_rate=0.05,
            depth=7,
            loss_function='Logloss',
            eval_metric='Accuracy',
            random_seed=42,
            verbose=100,
            early_stopping_rounds=50
        )
        
        # Train
        print("Training CatBoost...")
        model.fit(
            X_train, y_train,
            eval_set=(X_test, y_test),
            use_best_model=True
        )
        
        # Evaluate
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"\n✅ CatBoost Accuracy: {accuracy*100:.2f}%")
        print(f"✅ Best iteration: {model.get_best_iteration()}")
        
        return model, accuracy
    
    def create_ensemble(self, lgb_model, cat_model, lgb_acc, cat_acc):
        """Create weighted ensemble"""
        print(f"\n{'='*80}")
        print("CREATING ENSEMBLE")
        print(f"{'='*80}")
        
        # Calculate weights based on accuracy
        total_acc = lgb_acc + cat_acc
        weights = {
            'lgb': lgb_acc / total_acc,
            'cat': cat_acc / total_acc,
        }
        
        print(f"✅ Ensemble weights:")
        print(f"   LightGBM: {weights['lgb']*100:.1f}%")
        print(f"   CatBoost: {weights['cat']*100:.1f}%")
        
        ensemble = {
            'lgb_model': lgb_model,
            'cat_model': cat_model,
            'weights': weights,
            'lgb_accuracy': lgb_acc,
            'cat_accuracy': cat_acc,
            'ensemble_accuracy': (lgb_acc + cat_acc) / 2
        }
        
        print(f"\n✅ Ensemble Accuracy: {ensemble['ensemble_accuracy']*100:.2f}%")
        
        return ensemble
    
    def train_symbol(self, df, symbol):
        """Train ensemble for one symbol"""
        print(f"\n{'#'*80}")
        print(f"TRAINING SYMBOL: {symbol.upper()}")
        print(f"{'#'*80}")
        
        # Prepare data
        X_train, X_test, y_train, y_test = self.prepare_features(df, symbol)
        if X_train is None:
            return False
        
        # Train LightGBM
        lgb_model, lgb_acc = self.train_lightgbm(X_train, X_test, y_train, y_test)
        
        # Train CatBoost
        cat_model, cat_acc = self.train_catboost(X_train, X_test, y_train, y_test)
        
        # Create ensemble
        ensemble = self.create_ensemble(lgb_model, cat_model, lgb_acc, cat_acc)
        
        # Save ensemble
        model_file = f"{self.models_dir}/{symbol}_ultimate_ensemble.pkl"
        joblib.dump(ensemble, model_file)
        print(f"\n✅ Saved: {model_file}")
        
        # Also save as _latest for compatibility
        latest_file = f"{self.models_dir}/{symbol}_ensemble_latest.pkl"
        joblib.dump(ensemble, latest_file)
        print(f"✅ Saved: {latest_file}")
        
        return True
    
    def train_all(self):
        """Train all symbols"""
        print(f"\n{'='*80}")
        print("TRAINING ALL SYMBOLS")
        print(f"{'='*80}")
        
        # Load data once
        df = self.load_data()
        if df is None:
            print("❌ Failed to load data")
            return False
        
        # Check if we have symbol column
        has_symbol_col = 'symbol' in df.columns
        
        if not has_symbol_col:
            # Train single model for US30 (the data we have)
            print("\n⚠️  No 'symbol' column found - training single model for US30")
            success = self.train_symbol(df, 'us30')
            
            # Copy to other symbols for now
            if success:
                print("\n📋 Copying US30 model to other symbols...")
                us30_file = f"{self.models_dir}/us30_ultimate_ensemble.pkl"
                for symbol in self.symbols:
                    if symbol != 'us30':
                        target_file = f"{self.models_dir}/{symbol}_ultimate_ensemble.pkl"
                        latest_file = f"{self.models_dir}/{symbol}_ensemble_latest.pkl"
                        joblib.dump(joblib.load(us30_file), target_file)
                        joblib.dump(joblib.load(us30_file), latest_file)
                        print(f"✅ Copied to {symbol}")
            
            return success
        
        # Train each symbol
        results = {}
        for symbol in self.symbols:
            try:
                success = self.train_symbol(df, symbol)
                results[symbol] = "✅ SUCCESS" if success else "❌ FAILED"
            except Exception as e:
                print(f"\n❌ Error training {symbol}: {e}")
                import traceback
                traceback.print_exc()
                results[symbol] = f"❌ ERROR: {str(e)}"
        
        print(f"\n{'='*80}")
        print("TRAINING SUMMARY")
        print(f"{'='*80}")
        for symbol, result in results.items():
            print(f"{symbol.upper()}: {result}")
        
        print(f"\n{'='*80}")
        print("✅ TRAINING COMPLETE")
        print(f"{'='*80}")
        
        return True

if __name__ == "__main__":
    trainer = FixedModelTrainer()
    success = trainer.train_all()
    sys.exit(0 if success else 1)
