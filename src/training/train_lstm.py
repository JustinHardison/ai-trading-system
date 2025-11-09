"""
LSTM Training Pipeline
======================

Trains LSTM model on historical data with proper:
- Data loading and preprocessing
- Feature engineering integration
- Train/val/test split
- Model training and evaluation
- Model saving

Author: AI Trading System
Created: 2025-01-13
"""

import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import Dict, Tuple
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.models.lstm_predictor import LSTMPredictor, TENSORFLOW_AVAILABLE
from src.ml.pro_feature_engineer import ProFeatureEngineer


class LSTMTrainer:
    """
    LSTM training pipeline.
    """

    def __init__(
        self,
        data_path: str,
        sequence_length: int = 60,
        test_size: float = 0.2,
        val_size: float = 0.1
    ):
        """
        Initialize LSTM trainer.

        Args:
            data_path: Path to historical data CSV
            sequence_length: Number of bars in sequence
            test_size: Fraction of data for testing
            val_size: Fraction of training data for validation
        """
        self.data_path = Path(data_path)
        self.sequence_length = sequence_length
        self.test_size = test_size
        self.val_size = val_size

        self.feature_engineer = ProFeatureEngineer()
        self.predictor = None

        logger.info(f"✓ LSTMTrainer initialized")
        logger.info(f"  Data: {self.data_path}")
        logger.info(f"  Sequence length: {sequence_length}")

    def load_data(self) -> pd.DataFrame:
        """
        Load historical data.

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Loading data from {self.data_path}...")

        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        df = pd.read_csv(self.data_path)

        logger.info(f"✓ Loaded {len(df)} bars")
        logger.info(f"  Columns: {list(df.columns)}")

        return df

    def engineer_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract features and labels from data.

        Args:
            df: OHLCV DataFrame

        Returns:
            features: (n_bars, n_features) array
            labels: (n_bars,) array (0=SELL, 1=HOLD, 2=BUY)
        """
        logger.info("Engineering features...")

        n_bars = len(df)
        features_list = []
        labels_list = []

        # Need at least sequence_length + 20 bars for feature extraction
        min_bars = self.sequence_length + 20

        for i in range(min_bars, n_bars):
            # Extract features for bar i
            features_dict = self.feature_engineer.extract_all_features(df, i)

            if features_dict:
                # Convert to array
                feature_values = list(features_dict.values())
                features_list.append(feature_values)

                # Create label based on future price movement
                # Look ahead 5 bars to determine if price went up/down
                current_close = df.iloc[i]['close']

                if i + 5 < n_bars:
                    future_close = df.iloc[i + 5]['close']
                    price_change_pct = (future_close - current_close) / current_close * 100

                    # Label thresholds
                    if price_change_pct > 0.15:  # >0.15% up
                        label = 2  # BUY
                    elif price_change_pct < -0.15:  # <-0.15% down
                        label = 0  # SELL
                    else:
                        label = 1  # HOLD
                else:
                    label = 1  # HOLD for last bars

                labels_list.append(label)

            if i % 1000 == 0:
                logger.info(f"  Processed {i}/{n_bars} bars...")

        features = np.array(features_list)
        labels = np.array(labels_list)

        logger.info(f"✓ Features extracted: {features.shape}")
        logger.info(f"✓ Labels created: {labels.shape}")

        # Label distribution
        unique, counts = np.unique(labels, return_counts=True)
        label_map = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
        logger.info("  Label distribution:")
        for label, count in zip(unique, counts):
            pct = count / len(labels) * 100
            logger.info(f"    {label_map[label]}: {count} ({pct:.1f}%)")

        return features, labels

    def train(
        self,
        epochs: int = 50,
        batch_size: int = 32,
        model_save_path: str = "models/lstm_model.h5"
    ) -> Dict:
        """
        Train LSTM model.

        Args:
            epochs: Number of training epochs
            batch_size: Batch size
            model_save_path: Path to save trained model

        Returns:
            Training history dict
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM training")

        # Load and prepare data
        df = self.load_data()
        features, labels = self.engineer_features(df)

        # Get number of features
        n_features = features.shape[1]

        # Initialize predictor
        self.predictor = LSTMPredictor(
            sequence_length=self.sequence_length,
            n_features=n_features,
            lstm_units=[128, 64, 32],
            dropout_rate=0.3,
            learning_rate=0.001
        )

        # Prepare sequences
        logger.info("Preparing sequences...")
        X, y = self.predictor.prepare_sequences(features, labels)
        logger.info(f"✓ Sequences prepared: {X.shape}")

        # Split data
        n_samples = len(X)
        test_split = int(n_samples * (1 - self.test_size))
        val_split = int(test_split * (1 - self.val_size))

        X_train = X[:val_split]
        y_train = y[:val_split]
        X_val = X[val_split:test_split]
        y_val = y[val_split:test_split]
        X_test = X[test_split:]
        y_test = y[test_split:]

        logger.info(f"✓ Data split:")
        logger.info(f"  Train: {X_train.shape}")
        logger.info(f"  Val: {X_val.shape}")
        logger.info(f"  Test: {X_test.shape}")

        # Train model
        logger.info("\n" + "=" * 70)
        logger.info("TRAINING LSTM MODEL")
        logger.info("=" * 70)

        history = self.predictor.train(
            X_train, y_train,
            X_val, y_val,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1
        )

        # Evaluate on test set
        logger.info("\n" + "=" * 70)
        logger.info("EVALUATING ON TEST SET")
        logger.info("=" * 70)

        test_predictions, test_probs = self.predictor.predict(X_test)
        test_accuracy = (test_predictions == y_test).mean()

        logger.info(f"✓ Test Accuracy: {test_accuracy * 100:.2f}%")

        # Per-class accuracy
        label_map = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
        for label in [0, 1, 2]:
            mask = y_test == label
            if mask.sum() > 0:
                class_acc = (test_predictions[mask] == label).mean()
                logger.info(f"  {label_map[label]} Accuracy: {class_acc * 100:.2f}%")

        # Save model
        logger.info(f"\nSaving model to {model_save_path}...")
        self.predictor.save(model_save_path)

        logger.info("\n" + "=" * 70)
        logger.info("TRAINING COMPLETE")
        logger.info("=" * 70)

        return {
            'history': history,
            'test_accuracy': test_accuracy,
            'n_features': n_features,
            'n_sequences': n_samples
        }


def main():
    """Main training script."""
    import argparse

    parser = argparse.ArgumentParser(description='Train LSTM model')
    parser.add_argument('--data', type=str, required=True, help='Path to historical data CSV')
    parser.add_argument('--epochs', type=int, default=50, help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--sequence-length', type=int, default=60, help='Sequence length')
    parser.add_argument('--output', type=str, default='models/lstm_model.h5', help='Output model path')

    args = parser.parse_args()

    # Create trainer
    trainer = LSTMTrainer(
        data_path=args.data,
        sequence_length=args.sequence_length
    )

    # Train
    results = trainer.train(
        epochs=args.epochs,
        batch_size=args.batch_size,
        model_save_path=args.output
    )

    print("\n✅ Training complete!")
    print(f"Test Accuracy: {results['test_accuracy'] * 100:.2f}%")


if __name__ == "__main__":
    main()
