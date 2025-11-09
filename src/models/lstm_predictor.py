"""
LSTM Deep Learning Model for Trading
====================================

Uses sequence prediction to capture temporal patterns:
- 60-bar lookback sequences
- 3-layer LSTM architecture
- Dropout for regularization
- Batch normalization
- Target: 72-78% accuracy

Author: AI Trading System
Created: 2025-01-13
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from loguru import logger
import pickle
from pathlib import Path

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, callbacks
    TENSORFLOW_AVAILABLE = True
except ImportError:
    logger.warning("TensorFlow not available - LSTM model disabled")
    TENSORFLOW_AVAILABLE = False
    tf = None
    keras = None


class LSTMPredictor:
    """
    LSTM-based sequence predictor for trading.

    Architecture:
    - Input: (batch, 60 bars, features)
    - LSTM Layer 1: 128 units, return sequences
    - Dropout: 0.3
    - LSTM Layer 2: 64 units, return sequences
    - Dropout: 0.3
    - LSTM Layer 3: 32 units
    - Dropout: 0.3
    - Dense: 16 units, ReLU
    - Output: 3 classes (BUY, HOLD, SELL)
    """

    def __init__(
        self,
        sequence_length: int = 60,
        n_features: int = 230,
        lstm_units: List[int] = [128, 64, 32],
        dropout_rate: float = 0.3,
        learning_rate: float = 0.001
    ):
        """
        Initialize LSTM predictor.

        Args:
            sequence_length: Number of bars in sequence
            n_features: Number of features per bar
            lstm_units: Units in each LSTM layer
            dropout_rate: Dropout rate for regularization
            learning_rate: Learning rate for optimizer
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required for LSTM model")

        self.sequence_length = sequence_length
        self.n_features = n_features
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.model = None
        self.history = None

        logger.info(f"✓ LSTMPredictor initialized ({sequence_length} bars, {n_features} features)")

    def build_model(self) -> None:
        """Build LSTM model architecture."""
        # Input layer
        inputs = keras.Input(shape=(self.sequence_length, self.n_features))

        # LSTM layers with dropout
        x = inputs

        for i, units in enumerate(self.lstm_units):
            return_sequences = (i < len(self.lstm_units) - 1)  # All but last return sequences

            x = layers.LSTM(
                units,
                return_sequences=return_sequences,
                name=f'lstm_{i+1}'
            )(x)

            x = layers.Dropout(self.dropout_rate, name=f'dropout_{i+1}')(x)

        # Dense layers
        x = layers.Dense(16, activation='relu', name='dense_1')(x)
        x = layers.Dropout(self.dropout_rate, name='dropout_final')(x)

        # Output layer (3 classes: SELL, HOLD, BUY)
        outputs = layers.Dense(3, activation='softmax', name='output')(x)

        # Build model
        self.model = models.Model(inputs=inputs, outputs=outputs, name='LSTM_Predictor')

        # Compile
        self.model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

        logger.info("✓ LSTM model built and compiled")
        self.model.summary(print_fn=logger.info)

    def prepare_sequences(
        self,
        features: np.ndarray,
        labels: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Prepare sequences from feature data.

        Args:
            features: (n_bars, n_features) array
            labels: Optional (n_bars,) labels

        Returns:
            X: (n_sequences, sequence_length, n_features)
            y: Optional (n_sequences,) labels
        """
        n_bars = len(features)
        n_sequences = n_bars - self.sequence_length

        if n_sequences <= 0:
            raise ValueError(f"Not enough bars ({n_bars}) for sequence length ({self.sequence_length})")

        # Create sequences
        X = np.zeros((n_sequences, self.sequence_length, self.n_features))

        for i in range(n_sequences):
            X[i] = features[i:i + self.sequence_length]

        if labels is not None:
            # Labels correspond to bar AFTER sequence
            y = labels[self.sequence_length:]
            return X, y
        else:
            return X, None

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        verbose: int = 1
    ) -> Dict:
        """
        Train LSTM model.

        Args:
            X_train: Training sequences (n_samples, seq_len, n_features)
            y_train: Training labels (n_samples,)
            X_val: Validation sequences
            y_val: Validation labels
            epochs: Number of epochs
            batch_size: Batch size
            verbose: Verbosity level

        Returns:
            Training history dict
        """
        if self.model is None:
            self.build_model()

        # Callbacks
        callback_list = [
            callbacks.EarlyStopping(
                monitor='val_loss' if X_val is not None else 'loss',
                patience=10,
                restore_best_weights=True,
                verbose=1
            ),
            callbacks.ReduceLROnPlateau(
                monitor='val_loss' if X_val is not None else 'loss',
                factor=0.5,
                patience=5,
                min_lr=1e-6,
                verbose=1
            )
        ]

        # Train
        logger.info(f"Training LSTM model: {epochs} epochs, batch size {batch_size}")

        validation_data = (X_val, y_val) if X_val is not None else None

        self.history = self.model.fit(
            X_train,
            y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callback_list,
            verbose=verbose
        )

        # Get final metrics
        train_loss, train_acc = self.model.evaluate(X_train, y_train, verbose=0)
        logger.info(f"✓ Training complete: Loss={train_loss:.4f}, Accuracy={train_acc:.4f}")

        if X_val is not None:
            val_loss, val_acc = self.model.evaluate(X_val, y_val, verbose=0)
            logger.info(f"✓ Validation: Loss={val_loss:.4f}, Accuracy={val_acc:.4f}")

        return self.history.history

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict on sequences.

        Args:
            X: Sequences (n_samples, seq_len, n_features)

        Returns:
            predictions: Class predictions (n_samples,)
            probabilities: Class probabilities (n_samples, 3)
        """
        if self.model is None:
            raise ValueError("Model not built or loaded")

        probabilities = self.model.predict(X, verbose=0)
        predictions = np.argmax(probabilities, axis=1)

        return predictions, probabilities

    def predict_single(self, sequence: np.ndarray) -> Dict[str, any]:
        """
        Predict on single sequence.

        Args:
            sequence: (seq_len, n_features) array

        Returns:
            Dict with prediction, confidence, probabilities
        """
        # Reshape to batch
        X = sequence.reshape(1, self.sequence_length, self.n_features)

        predictions, probabilities = self.predict(X)

        prediction = predictions[0]
        probs = probabilities[0]

        # Map to actions
        action_map = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
        action = action_map[prediction]
        confidence = float(probs[prediction]) * 100

        return {
            'action': action,
            'confidence': confidence,
            'probabilities': {
                'SELL': float(probs[0]) * 100,
                'HOLD': float(probs[1]) * 100,
                'BUY': float(probs[2]) * 100,
            }
        }

    def save(self, path: str) -> None:
        """
        Save model to disk.

        Args:
            path: Path to save model
        """
        if self.model is None:
            raise ValueError("No model to save")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save model
        self.model.save(str(path))

        # Save config
        config = {
            'sequence_length': self.sequence_length,
            'n_features': self.n_features,
            'lstm_units': self.lstm_units,
            'dropout_rate': self.dropout_rate,
            'learning_rate': self.learning_rate,
        }

        config_path = path.parent / f"{path.stem}_config.pkl"
        with open(config_path, 'wb') as f:
            pickle.dump(config, f)

        logger.info(f"✓ Model saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'LSTMPredictor':
        """
        Load model from disk.

        Args:
            path: Path to load model from

        Returns:
            Loaded LSTMPredictor
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow is required to load LSTM model")

        path = Path(path)

        # Load config
        config_path = path.parent / f"{path.stem}_config.pkl"
        with open(config_path, 'rb') as f:
            config = pickle.load(f)

        # Create instance
        predictor = cls(**config)

        # Load model
        predictor.model = keras.models.load_model(str(path))

        logger.info(f"✓ Model loaded from {path}")

        return predictor


# Test function
def test_lstm_predictor():
    """Test LSTM predictor with dummy data."""
    if not TENSORFLOW_AVAILABLE:
        print("TensorFlow not available - skipping test")
        return

    print("═══════════════════════════════════════════════════════════════════")
    print("🧪 LSTM PREDICTOR TEST")
    print("═══════════════════════════════════════════════════════════════════\n")

    # Create dummy data
    n_bars = 500
    n_features = 50
    sequence_length = 60

    np.random.seed(42)

    # Features
    features = np.random.randn(n_bars, n_features)

    # Labels (0=SELL, 1=HOLD, 2=BUY)
    labels = np.random.randint(0, 3, n_bars)

    print(f"Data: {n_bars} bars, {n_features} features\n")

    # Initialize predictor
    predictor = LSTMPredictor(
        sequence_length=sequence_length,
        n_features=n_features,
        lstm_units=[64, 32],
        dropout_rate=0.3,
        learning_rate=0.001
    )

    # Build model
    predictor.build_model()

    # Prepare sequences
    print("Preparing sequences...")
    X, y = predictor.prepare_sequences(features, labels)
    print(f"Sequences: {X.shape}, Labels: {y.shape}\n")

    # Split train/val
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]

    print(f"Train: {X_train.shape}, Val: {X_val.shape}\n")

    # Train (just 5 epochs for test)
    print("Training model (5 epochs)...\n")
    history = predictor.train(
        X_train, y_train,
        X_val, y_val,
        epochs=5,
        batch_size=32,
        verbose=0
    )

    # Predict on single sequence
    print("\nTesting single prediction...")
    test_sequence = X_val[0]
    result = predictor.predict_single(test_sequence)

    print(f"  Action: {result['action']}")
    print(f"  Confidence: {result['confidence']:.2f}%")
    print(f"  Probabilities:")
    for action, prob in result['probabilities'].items():
        print(f"    {action}: {prob:.2f}%")

    print("\n═══════════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    test_lstm_predictor()
