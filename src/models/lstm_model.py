"""
LSTM Deep Learning Model for Time Series Prediction
Temporal pattern recognition using Long Short-Term Memory networks
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from loguru import logger
from typing import Dict, Tuple, Optional
import joblib
from pathlib import Path


class LSTMPredictor:
    """
    LSTM-based deep learning model for market prediction

    Features:
    - Multi-layer LSTM (temporal memory)
    - Attention mechanism (important feature detection)
    - Dropout regularization (prevent overfitting)
    - Bidirectional processing (look forward and backward)
    """

    def __init__(self,
                 sequence_length: int = 60,
                 n_features: int = 230,
                 lstm_units: int = 128,
                 dropout_rate: float = 0.3,
                 model_path: str = "models/lstm_predictor.h5"):
        """
        Initialize LSTM model

        Args:
            sequence_length: Number of time steps to look back
            n_features: Number of input features
            lstm_units: Number of LSTM units per layer
            dropout_rate: Dropout rate for regularization
            model_path: Path to save/load model
        """
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.model_path = Path(model_path)

        self.model = None
        self.scaler = None
        self.is_trained = False

        # Try to load existing model
        if self.model_path.exists():
            self.load_model()

    def build_model(self) -> keras.Model:
        """
        Build LSTM model with attention mechanism

        Architecture:
        1. Input Layer (sequence_length, n_features)
        2. Bidirectional LSTM (128 units, return sequences)
        3. Attention Layer (learn important time steps)
        4. LSTM (64 units)
        5. Dropout (regularization)
        6. Dense (32 units, ReLU)
        7. Output (3 classes: BUY, HOLD, SELL)
        """
        inputs = layers.Input(shape=(self.sequence_length, self.n_features))

        # Layer 1: Bidirectional LSTM (look forward and backward)
        x = layers.Bidirectional(
            layers.LSTM(self.lstm_units, return_sequences=True)
        )(inputs)
        x = layers.Dropout(self.dropout_rate)(x)

        # Layer 2: Attention Mechanism (learn important time steps)
        attention = layers.Dense(1, activation='tanh')(x)
        attention = layers.Flatten()(attention)
        attention = layers.Activation('softmax')(attention)
        attention = layers.RepeatVector(self.lstm_units * 2)(attention)
        attention = layers.Permute([2, 1])(attention)

        # Apply attention weights
        x = layers.Multiply()([x, attention])

        # Layer 3: LSTM (temporal pattern extraction)
        x = layers.LSTM(self.lstm_units // 2)(x)
        x = layers.Dropout(self.dropout_rate)(x)

        # Layer 4: Dense layers (feature combination)
        x = layers.Dense(32, activation='relu')(x)
        x = layers.Dropout(self.dropout_rate / 2)(x)

        # Output: 3 classes (BUY=0, HOLD=1, SELL=2)
        outputs = layers.Dense(3, activation='softmax')(x)

        model = keras.Model(inputs=inputs, outputs=outputs)

        # Compile with Adam optimizer
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

        logger.info(f"✅ LSTM model built: {model.count_params():,} parameters")
        return model

    def prepare_sequences(self, features: np.ndarray, labels: Optional[np.ndarray] = None) -> Tuple:
        """
        Convert features into sequences for LSTM

        Args:
            features: Feature array (n_samples, n_features)
            labels: Labels (n_samples,) - optional for prediction

        Returns:
            X_sequences: (n_samples - sequence_length, sequence_length, n_features)
            y_sequences: (n_samples - sequence_length,) if labels provided
        """
        n_samples = len(features)

        if n_samples < self.sequence_length:
            raise ValueError(f"Need at least {self.sequence_length} samples, got {n_samples}")

        # Create sequences
        X_sequences = []
        y_sequences = [] if labels is not None else None

        for i in range(self.sequence_length, n_samples):
            X_sequences.append(features[i - self.sequence_length:i])
            if labels is not None:
                y_sequences.append(labels[i])

        X_sequences = np.array(X_sequences)

        if labels is not None:
            y_sequences = np.array(y_sequences)
            return X_sequences, y_sequences

        return X_sequences

    def train(self,
              X_train: np.ndarray,
              y_train: np.ndarray,
              X_val: np.ndarray,
              y_val: np.ndarray,
              epochs: int = 50,
              batch_size: int = 32) -> Dict:
        """
        Train LSTM model

        Args:
            X_train: Training features
            y_train: Training labels (0=BUY, 1=HOLD, 2=SELL)
            X_val: Validation features
            y_val: Validation labels
            epochs: Number of training epochs
            batch_size: Batch size

        Returns:
            Training history
        """
        logger.info(f"🧠 Training LSTM model...")
        logger.info(f"   Training samples: {len(X_train)}")
        logger.info(f"   Validation samples: {len(X_val)}")
        logger.info(f"   Sequence length: {self.sequence_length}")
        logger.info(f"   Features: {self.n_features}")

        # Build model if not already built
        if self.model is None:
            self.model = self.build_model()

        # Prepare sequences
        X_train_seq, y_train_seq = self.prepare_sequences(X_train, y_train)
        X_val_seq, y_val_seq = self.prepare_sequences(X_val, y_val)

        logger.info(f"   Sequences created: {len(X_train_seq)} train, {len(X_val_seq)} val")

        # Callbacks
        early_stopping = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )

        reduce_lr = keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        )

        # Train
        history = self.model.fit(
            X_train_seq, y_train_seq,
            validation_data=(X_val_seq, y_val_seq),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stopping, reduce_lr],
            verbose=1
        )

        self.is_trained = True

        # Save model
        self.save_model()

        train_acc = history.history['accuracy'][-1]
        val_acc = history.history['val_accuracy'][-1]

        logger.info(f"✅ LSTM training complete!")
        logger.info(f"   Train accuracy: {train_acc:.4f}")
        logger.info(f"   Val accuracy: {val_acc:.4f}")

        return history.history

    def predict(self, features: np.ndarray) -> Dict:
        """
        Make prediction using LSTM

        Args:
            features: Feature sequence (n_samples, n_features)

        Returns:
            {
                'direction': 'BUY' or 'SELL' or 'HOLD',
                'confidence': float (0-100),
                'probabilities': {
                    'buy': float,
                    'hold': float,
                    'sell': float
                }
            }
        """
        if self.model is None:
            logger.warning("LSTM model not loaded/trained - returning neutral")
            return {
                'direction': 'HOLD',
                'confidence': 50.0,
                'probabilities': {'buy': 0.33, 'hold': 0.34, 'sell': 0.33}
            }

        # Prepare sequence (use last sequence_length samples)
        if len(features) < self.sequence_length:
            logger.warning(f"Not enough samples ({len(features)} < {self.sequence_length}) - returning neutral")
            return {
                'direction': 'HOLD',
                'confidence': 50.0,
                'probabilities': {'buy': 0.33, 'hold': 0.34, 'sell': 0.33}
            }

        # Take last sequence
        sequence = features[-self.sequence_length:]
        sequence = sequence.reshape(1, self.sequence_length, self.n_features)

        # Predict
        probs = self.model.predict(sequence, verbose=0)[0]

        # Get prediction (0=BUY, 1=HOLD, 2=SELL)
        pred_class = np.argmax(probs)
        confidence = probs[pred_class] * 100

        direction_map = {0: 'BUY', 1: 'HOLD', 2: 'SELL'}
        direction = direction_map[pred_class]

        return {
            'direction': direction,
            'confidence': float(confidence),
            'probabilities': {
                'buy': float(probs[0]),
                'hold': float(probs[1]),
                'sell': float(probs[2])
            }
        }

    def save_model(self):
        """Save model to disk"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(self.model_path)
        logger.info(f"✅ LSTM model saved to {self.model_path}")

    def load_model(self):
        """Load model from disk"""
        try:
            self.model = keras.models.load_model(self.model_path)
            self.is_trained = True
            logger.info(f"✅ LSTM model loaded from {self.model_path}")
        except Exception as e:
            logger.warning(f"Could not load LSTM model: {e}")
            self.model = None
            self.is_trained = False
