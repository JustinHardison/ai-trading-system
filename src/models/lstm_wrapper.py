"""
LSTM Model Wrapper (Lightweight Integration)
============================================

Provides LSTM predictions without blocking the main system.
- Falls back to XGBoost if LSTM not available
- Async loading to avoid startup delays
- Optional enhancement, not required

Author: AI Trading System
Created: 2025-01-13
"""

import numpy as np
from typing import Dict, Optional
from loguru import logger
from pathlib import Path


class LSTMWrapper:
    """
    Lightweight LSTM wrapper for integration.

    Features:
    - Optional (system works without it)
    - Lazy loading (doesn't block startup)
    - Graceful fallback to XGBoost
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize LSTM wrapper.

        Args:
            model_path: Optional path to pre-trained LSTM model
        """
        self.model_path = Path(model_path) if model_path else None
        self.model = None
        self.available = False
        self.tf = None

        # DON'T import TensorFlow at init time - it blocks for >2 minutes!
        # We'll check TensorFlow availability lazily when actually needed
        logger.info("✓ LSTM wrapper initialized (lazy loading)")

    def load_model(self) -> bool:
        """
        Load pre-trained LSTM model (lazy loading).

        Returns:
            True if loaded successfully
        """
        if self.model is not None:
            return True  # Already loaded

        # Try to load TensorFlow if not already loaded
        if self.tf is None:
            try:
                import tensorflow as tf
                self.tf = tf
                logger.info("✓ TensorFlow loaded (lazy init)")
            except ImportError:
                logger.warning("TensorFlow not available - LSTM disabled")
                return False

        if self.model_path is None or not self.model_path.exists():
            logger.warning(f"LSTM model not found at {self.model_path}")
            return False

        try:
            self.model = self.tf.keras.models.load_model(str(self.model_path))
            self.available = True
            logger.info(f"✓ LSTM model loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load LSTM model: {e}")
            return False

    def predict(
        self,
        sequence: np.ndarray,
        fallback_prediction: Optional[Dict] = None
    ) -> Dict:
        """
        Predict using LSTM or fall back to XGBoost.

        Args:
            sequence: (seq_len, n_features) sequence
            fallback_prediction: XGBoost prediction to use if LSTM fails

        Returns:
            Prediction dict with action, confidence, probabilities
        """
        # Try LSTM prediction
        if self.available and self.model is not None:
            try:
                # Reshape to batch
                X = sequence.reshape(1, *sequence.shape)

                # Predict
                probs = self.model.predict(X, verbose=0)[0]
                prediction = int(np.argmax(probs))

                # Map to actions
                action_map = {0: 'SELL', 1: 'HOLD', 2: 'BUY'}
                action = action_map[prediction]
                confidence = float(probs[prediction]) * 100

                result = {
                    'action': action,
                    'confidence': confidence,
                    'probabilities': {
                        'SELL': float(probs[0]) * 100,
                        'HOLD': float(probs[1]) * 100,
                        'BUY': float(probs[2]) * 100,
                    },
                    'model': 'LSTM'
                }

                logger.debug(f"LSTM prediction: {action} @ {confidence:.1f}%")
                return result

            except Exception as e:
                logger.error(f"LSTM prediction failed: {e}")
                # Fall through to fallback

        # Use fallback (XGBoost)
        if fallback_prediction:
            logger.debug("Using XGBoost fallback prediction")
            return {**fallback_prediction, 'model': 'XGBoost'}
        else:
            # Return neutral
            return {
                'action': 'HOLD',
                'confidence': 33.33,
                'probabilities': {
                    'SELL': 33.33,
                    'HOLD': 33.33,
                    'BUY': 33.33,
                },
                'model': 'None'
            }

    def ensemble_predict(
        self,
        sequence: np.ndarray,
        xgboost_prediction: Dict,
        lstm_weight: float = 0.3
    ) -> Dict:
        """
        Ensemble LSTM + XGBoost predictions.

        Args:
            sequence: Input sequence for LSTM
            xgboost_prediction: XGBoost prediction dict
            lstm_weight: Weight for LSTM (0-1), XGBoost gets (1-lstm_weight)

        Returns:
            Ensemble prediction
        """
        # Get LSTM prediction
        lstm_pred = self.predict(sequence, fallback_prediction=None)

        if lstm_pred['model'] != 'LSTM':
            # LSTM not available, use XGBoost only
            return xgboost_prediction

        # Ensemble: weighted average of probabilities
        xgb_weight = 1.0 - lstm_weight

        # Extract probabilities
        xgb_probs = xgboost_prediction.get('probabilities', {
            'SELL': 33.33, 'HOLD': 33.33, 'BUY': 33.33
        })
        lstm_probs = lstm_pred['probabilities']

        # Weighted average
        ensemble_probs = {
            'SELL': xgb_probs['SELL'] * xgb_weight + lstm_probs['SELL'] * lstm_weight,
            'HOLD': xgb_probs['HOLD'] * xgb_weight + lstm_probs['HOLD'] * lstm_weight,
            'BUY': xgb_probs['BUY'] * xgb_weight + lstm_probs['BUY'] * lstm_weight,
        }

        # Determine action from ensemble
        action = max(ensemble_probs, key=ensemble_probs.get)
        confidence = ensemble_probs[action]

        logger.info(f"📊 ENSEMBLE: {action} @ {confidence:.1f}% (XGB:{xgb_weight:.0%} + LSTM:{lstm_weight:.0%})")

        return {
            'action': action,
            'confidence': confidence,
            'probabilities': ensemble_probs,
            'model': 'Ensemble',
            'xgboost': xgboost_prediction,
            'lstm': lstm_pred
        }
