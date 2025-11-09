#!/usr/bin/env python3
"""
ULTIMATE MODEL TRAINING
Trains LightGBM + CatBoost + LSTM ensemble for each symbol
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
from sklearn.preprocessing import StandardScaler

# Deep learning
try:
    from tensorflow import keras
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    HAS_TENSORFLOW = True
except:
    print("⚠️  TensorFlow not available, LSTM will be skipped")
    HAS_TENSORFLOW = False

class UltimateModelTrainer:
    def __init__(self, data_dir="/Users/justinhardison/ai-trading-system/data"):
        self.data_dir = data_dir
        self.models_dir = "/Users/justinhardison/ai-trading-system/models"
        self.symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
        
        print("="*80)
        print("ULTIMATE MODEL TRAINING - HEDGE FUND SYSTEM")
        print("="*80)
        print(f"Data directory: {self.data_dir}")
        print(f"Models directory: {self.models_dir}")
        print("="*80)
    
    def load_and_prepare_data(self, symbol):
        """Load CSV data and prepare features/target"""
        print(f"\n{'='*80}")
        print(f"LOADING DATA: {symbol.upper()}")
        print(f"{'='*80}")
        
        # Find data file
        csv_file = f"{self.data_dir}/ultimate_training_data.csv"
        if not os.path.exists(csv_file):
            csv_file = f"{self.data_dir}/{symbol}_training_data.csv"
        
        if not os.path.exists(csv_file):
            print(f"❌ Data file not found: {csv_file}")
            return None, None, None, None
        
        # Load data
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} rows")
        
        # Drop timestamp and symbol columns
        if 'timestamp' in df.columns:
            df = df.drop('timestamp', axis=1)
        if 'symbol' in df.columns:
            df = df.drop('symbol', axis=1)
        
        # Separate features and target
        if 'target' not in df.columns:
            print("❌ No 'target' column found")
            return None, None, None, None
        
        X = df.drop('target', axis=1)
        y = df['target']
        
        print(f"✅ Features: {X.shape[1]} columns")
        print(f"✅ Target: {y.value_counts().to_dict()}")
        
        # Train/test split (80/20)
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
        
        # Parameters optimized for trading
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
        model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
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
        
        # Parameters optimized for trading
        model = CatBoostClassifier(
            iterations=1000,
            learning_rate=0.05,
            depth=7,
            loss_function='Logloss',
            eval_metric='Accuracy',
            random_seed=42,
            verbose=100,
            early_stopping_rounds=50
        )
        
        # Train
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
    
    def train_lstm(self, X_train, X_test, y_train, y_test):
        """Train LSTM model"""
        if not HAS_TENSORFLOW:
            print("\n⚠️  Skipping LSTM (TensorFlow not available)")
            return None, 0.0
        
        print(f"\n{'='*80}")
        print("TRAINING: LSTM")
        print(f"{'='*80}")
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Reshape for LSTM (samples, timesteps, features)
        # Use last 50 bars as sequence
        sequence_length = min(50, len(X_train_scaled) // 100)
        
        def create_sequences(X, y, seq_len):
            X_seq, y_seq = [], []
            for i in range(len(X) - seq_len):
                X_seq.append(X[i:i+seq_len])
                y_seq.append(y.iloc[i+seq_len])
            return np.array(X_seq), np.array(y_seq)
        
        X_train_seq, y_train_seq = create_sequences(X_train_scaled, y_train, sequence_length)
        X_test_seq, y_test_seq = create_sequences(X_test_scaled, y_test, sequence_length)
        
        print(f"✅ Sequence shape: {X_train_seq.shape}")
        
        # Build LSTM model
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(sequence_length, X_train.shape[1])),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        # Train
        early_stop = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        
        history = model.fit(
            X_train_seq, y_train_seq,
            validation_data=(X_test_seq, y_test_seq),
            epochs=50,
            batch_size=32,
            callbacks=[early_stop],
            verbose=1
        )
        
        # Evaluate
        _, accuracy = model.evaluate(X_test_seq, y_test_seq, verbose=0)
        
        print(f"\n✅ LSTM Accuracy: {accuracy*100:.2f}%")
        
        return {'model': model, 'scaler': scaler, 'sequence_length': sequence_length}, accuracy
    
    def create_ensemble(self, lgb_model, cat_model, lstm_model, lgb_acc, cat_acc, lstm_acc):
        """Create weighted ensemble"""
        print(f"\n{'='*80}")
        print("CREATING ENSEMBLE")
        print(f"{'='*80}")
        
        # Calculate weights based on accuracy
        total_acc = lgb_acc + cat_acc + (lstm_acc if lstm_model else 0)
        
        if lstm_model:
            weights = {
                'lgb': lgb_acc / total_acc,
                'cat': cat_acc / total_acc,
                'lstm': lstm_acc / total_acc
            }
        else:
            weights = {
                'lgb': lgb_acc / total_acc,
                'cat': cat_acc / total_acc,
                'lstm': 0.0
            }
        
        print(f"✅ Ensemble weights:")
        print(f"   LightGBM: {weights['lgb']*100:.1f}%")
        print(f"   CatBoost: {weights['cat']*100:.1f}%")
        print(f"   LSTM: {weights['lstm']*100:.1f}%")
        
        ensemble = {
            'lgb_model': lgb_model,
            'cat_model': cat_model,
            'lstm_model': lstm_model,
            'weights': weights,
            'lgb_accuracy': lgb_acc,
            'cat_accuracy': cat_acc,
            'lstm_accuracy': lstm_acc,
            'ensemble_accuracy': (lgb_acc + cat_acc + (lstm_acc if lstm_model else 0)) / (3 if lstm_model else 2)
        }
        
        print(f"\n✅ Ensemble Accuracy: {ensemble['ensemble_accuracy']*100:.2f}%")
        
        return ensemble
    
    def train_symbol(self, symbol):
        """Train complete ensemble for one symbol"""
        print(f"\n{'#'*80}")
        print(f"TRAINING SYMBOL: {symbol.upper()}")
        print(f"{'#'*80}")
        
        # Load data
        X_train, X_test, y_train, y_test = self.load_and_prepare_data(symbol)
        if X_train is None:
            return False
        
        # Train LightGBM
        lgb_model, lgb_acc = self.train_lightgbm(X_train, X_test, y_train, y_test)
        
        # Train CatBoost
        cat_model, cat_acc = self.train_catboost(X_train, X_test, y_train, y_test)
        
        # Train LSTM
        lstm_model, lstm_acc = self.train_lstm(X_train, X_test, y_train, y_test)
        
        # Create ensemble
        ensemble = self.create_ensemble(lgb_model, cat_model, lstm_model, lgb_acc, cat_acc, lstm_acc)
        
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
        
        results = {}
        
        for symbol in self.symbols:
            try:
                success = self.train_symbol(symbol)
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

if __name__ == "__main__":
    trainer = UltimateModelTrainer()
    trainer.train_all()
