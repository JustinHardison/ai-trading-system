"""
Train Deep Learning Models (LSTM + Transformer)
Uses historical US30 data to train state-of-the-art time series models
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from sklearn.model_selection import train_test_split
import joblib

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.pro_feature_engineer import ProFeatureEngineer
from src.models.lstm_model import LSTMPredictor
from src.models.transformer_model import TransformerPredictor


def load_historical_data(csv_path: str) -> pd.DataFrame:
    """
    Load historical OHLCV data from CSV

    Args:
        csv_path: Path to CSV file

    Returns:
        DataFrame with OHLCV data
    """
    logger.info(f"📊 Loading historical data from {csv_path}...")

    df = pd.read_csv(csv_path)

    # Rename columns to match expected format
    df = df.rename(columns={
        'time': 'time',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'tick_volume': 'volume'
    })

    # Convert time to datetime
    df['time'] = pd.to_datetime(df['time'])

    logger.info(f"✅ Loaded {len(df):,} bars")
    logger.info(f"   Date range: {df['time'].min()} to {df['time'].max()}")
    logger.info(f"   Columns: {list(df.columns)}")

    return df


def create_labels(df: pd.DataFrame, forward_bars: int = 5, profit_threshold: float = 20.0) -> np.ndarray:
    """
    Create labels for training (BUY=0, HOLD=1, SELL=2)

    Strategy:
    - BUY: Price will go up by profit_threshold in next forward_bars
    - SELL: Price will go down by profit_threshold in next forward_bars
    - HOLD: No clear direction

    Args:
        df: DataFrame with OHLCV data
        forward_bars: How many bars to look ahead
        profit_threshold: Minimum price movement (in points)

    Returns:
        Array of labels (0=BUY, 1=HOLD, 2=SELL)
    """
    logger.info(f"🏷️  Creating labels (forward_bars={forward_bars}, threshold={profit_threshold} points)...")

    labels = []

    for i in range(len(df)):
        # Can't label last bars (no future data)
        if i >= len(df) - forward_bars:
            labels.append(1)  # HOLD for last bars
            continue

        current_close = df['close'].iloc[i]

        # Look at future prices
        future_highs = df['high'].iloc[i+1:i+1+forward_bars]
        future_lows = df['low'].iloc[i+1:i+1+forward_bars]

        max_profit = (future_highs.max() - current_close)
        max_loss = (current_close - future_lows.min())

        # Label based on which direction is stronger
        if max_profit >= profit_threshold and max_profit > max_loss:
            labels.append(0)  # BUY
        elif max_loss >= profit_threshold and max_loss > max_profit:
            labels.append(2)  # SELL
        else:
            labels.append(1)  # HOLD

    labels = np.array(labels)

    # Count distribution
    buy_count = np.sum(labels == 0)
    hold_count = np.sum(labels == 1)
    sell_count = np.sum(labels == 2)

    logger.info(f"✅ Labels created:")
    logger.info(f"   BUY:  {buy_count:,} ({buy_count/len(labels)*100:.1f}%)")
    logger.info(f"   HOLD: {hold_count:,} ({hold_count/len(labels)*100:.1f}%)")
    logger.info(f"   SELL: {sell_count:,} ({sell_count/len(labels)*100:.1f}%)")

    return labels


def extract_features_batch(df: pd.DataFrame, feature_engineer: ProFeatureEngineer) -> np.ndarray:
    """
    Extract features for all bars in DataFrame

    Args:
        df: DataFrame with OHLCV data
        feature_engineer: ProFeatureEngineer instance

    Returns:
        Array of features (n_bars, n_features)
    """
    logger.info(f"🔧 Extracting features for {len(df):,} bars...")

    features_list = []

    # Need at least 100 bars for technical indicators
    start_idx = 100

    for i in range(start_idx, len(df)):
        if i % 10000 == 0:
            logger.info(f"   Progress: {i}/{len(df)} ({i/len(df)*100:.1f}%)")

        # Extract features for this bar
        bar_features = feature_engineer.extract_all_features(df, i)

        if bar_features:
            # Convert to array using sorted keys (consistent order)
            feature_values = [bar_features.get(f, 0.0) for f in sorted(bar_features.keys())]
            features_list.append(feature_values)
        else:
            # If feature extraction fails, use zeros
            features_list.append([0.0] * 230)

    features = np.array(features_list)

    logger.info(f"✅ Features extracted: shape={features.shape}")

    return features, start_idx


def train_deep_learning_models(
    csv_path: str = "/Users/justinhardison/ai-trading-system/us30_historical_data.csv",
    sequence_length: int = 60,
    forward_bars: int = 5,
    profit_threshold: float = 20.0,
    val_split: float = 0.2,
    test_split: float = 0.1,
    epochs: int = 50,
    batch_size: int = 32
):
    """
    Train LSTM and Transformer models on historical data

    Args:
        csv_path: Path to historical CSV data
        sequence_length: Number of bars to look back
        forward_bars: Number of bars to look ahead for labels
        profit_threshold: Minimum price movement for BUY/SELL (points)
        val_split: Validation split ratio
        test_split: Test split ratio
        epochs: Number of training epochs
        batch_size: Training batch size
    """
    logger.info("="*70)
    logger.info("🚀 TRAINING DEEP LEARNING MODELS (LSTM + TRANSFORMER)")
    logger.info("="*70)

    # 1. Load historical data
    df = load_historical_data(csv_path)

    # 2. Initialize feature engineer
    logger.info("\n🔧 Initializing ProFeatureEngineer...")
    feature_engineer = ProFeatureEngineer()
    logger.info("✅ Feature engineer ready")

    # 3. Extract features
    features, start_idx = extract_features_batch(df, feature_engineer)

    # 4. Create labels (aligned with features)
    labels_full = create_labels(df, forward_bars, profit_threshold)
    labels = labels_full[start_idx:]  # Align with features

    # Verify alignment
    logger.info(f"\n📊 Data alignment:")
    logger.info(f"   Features shape: {features.shape}")
    logger.info(f"   Labels shape: {labels.shape}")

    if len(features) != len(labels):
        logger.error(f"❌ Feature/label mismatch: {len(features)} vs {len(labels)}")
        return

    # 5. Split data (train/val/test)
    logger.info(f"\n✂️  Splitting data (train/val/test)...")

    # First split: train+val vs test
    X_temp, X_test, y_temp, y_test = train_test_split(
        features, labels, test_size=test_split, shuffle=False  # Don't shuffle time series!
    )

    # Second split: train vs val
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp, test_size=val_split/(1-test_split), shuffle=False
    )

    logger.info(f"✅ Data split:")
    logger.info(f"   Train: {len(X_train):,} samples ({len(X_train)/len(features)*100:.1f}%)")
    logger.info(f"   Val:   {len(X_val):,} samples ({len(X_val)/len(features)*100:.1f}%)")
    logger.info(f"   Test:  {len(X_test):,} samples ({len(X_test)/len(features)*100:.1f}%)")

    # 6. Train LSTM model
    logger.info("\n" + "="*70)
    logger.info("🧠 TRAINING LSTM MODEL")
    logger.info("="*70)

    lstm_model = LSTMPredictor(
        sequence_length=sequence_length,
        n_features=features.shape[1],
        lstm_units=128,
        dropout_rate=0.3,
        model_path="models/lstm_predictor.h5"
    )

    try:
        lstm_history = lstm_model.train(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            epochs=epochs,
            batch_size=batch_size
        )
        logger.info("✅ LSTM training complete!")
    except Exception as e:
        logger.error(f"❌ LSTM training failed: {e}", exc_info=True)

    # 7. Train Transformer model
    logger.info("\n" + "="*70)
    logger.info("🧠 TRAINING TRANSFORMER MODEL")
    logger.info("="*70)

    transformer_model = TransformerPredictor(
        sequence_length=sequence_length,
        n_features=features.shape[1],
        num_heads=8,
        ff_dim=128,
        num_transformer_blocks=4,
        dropout_rate=0.3,
        model_path="models/transformer_predictor.h5"
    )

    try:
        transformer_history = transformer_model.train(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            epochs=epochs,
            batch_size=batch_size
        )
        logger.info("✅ Transformer training complete!")
    except Exception as e:
        logger.error(f"❌ Transformer training failed: {e}", exc_info=True)

    # 8. Evaluate on test set
    logger.info("\n" + "="*70)
    logger.info("📊 EVALUATING ON TEST SET")
    logger.info("="*70)

    if lstm_model.is_trained:
        logger.info("\n🧠 LSTM Test Evaluation:")
        test_predictions = []
        test_labels = []

        # Predict on test set
        X_test_seq, y_test_seq = lstm_model.prepare_sequences(X_test, y_test)
        predictions = lstm_model.model.predict(X_test_seq, verbose=0)

        # Calculate accuracy
        pred_classes = np.argmax(predictions, axis=1)
        accuracy = np.mean(pred_classes == y_test_seq)

        logger.info(f"   Test Accuracy: {accuracy*100:.2f}%")

        # Per-class accuracy
        for class_idx, class_name in enumerate(['BUY', 'HOLD', 'SELL']):
            mask = y_test_seq == class_idx
            if np.sum(mask) > 0:
                class_acc = np.mean(pred_classes[mask] == class_idx)
                logger.info(f"   {class_name} Accuracy: {class_acc*100:.2f}%")

    if transformer_model.is_trained:
        logger.info("\n🧠 Transformer Test Evaluation:")

        # Predict on test set
        X_test_seq, y_test_seq = transformer_model.prepare_sequences(X_test, y_test)
        predictions = transformer_model.model.predict(X_test_seq, verbose=0)

        # Calculate accuracy
        pred_classes = np.argmax(predictions, axis=1)
        accuracy = np.mean(pred_classes == y_test_seq)

        logger.info(f"   Test Accuracy: {accuracy*100:.2f}%")

        # Per-class accuracy
        for class_idx, class_name in enumerate(['BUY', 'HOLD', 'SELL']):
            mask = y_test_seq == class_idx
            if np.sum(mask) > 0:
                class_acc = np.mean(pred_classes[mask] == class_idx)
                logger.info(f"   {class_name} Accuracy: {class_acc*100:.2f}%")

    logger.info("\n" + "="*70)
    logger.info("🎉 DEEP LEARNING TRAINING COMPLETE!")
    logger.info("="*70)
    logger.info("Models saved to:")
    logger.info("   - models/lstm_predictor.h5")
    logger.info("   - models/transformer_predictor.h5")
    logger.info("\nTo use in production:")
    logger.info("   1. Restart the API: python ml_api_integrated.py")
    logger.info("   2. Models will auto-load on startup")
    logger.info("   3. Ensemble will use XGBoost (40%) + LSTM (30%) + Transformer (30%)")
    logger.info("="*70)


if __name__ == "__main__":
    # Train models with default parameters
    train_deep_learning_models(
        csv_path="/Users/justinhardison/ai-trading-system/us30_historical_data.csv",
        sequence_length=60,
        forward_bars=5,
        profit_threshold=20.0,
        val_split=0.2,
        test_split=0.1,
        epochs=50,
        batch_size=32
    )
