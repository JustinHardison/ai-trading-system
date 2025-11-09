"""
Deep Learning Ensemble for Market Prediction
Combines XGBoost, LSTM, and Transformer models for superior accuracy
"""

import numpy as np
from loguru import logger
from typing import Dict, Optional
from pathlib import Path
import joblib

# Import our deep learning models
from src.models.lstm_model import LSTMPredictor
from src.models.transformer_model import TransformerPredictor


class DeepLearningEnsemble:
    """
    Ensemble of XGBoost + LSTM + Transformer models

    Voting Strategy:
    - Weighted average of probabilities from all models
    - XGBoost: 40% weight (proven accuracy)
    - LSTM: 30% weight (temporal memory)
    - Transformer: 30% weight (attention mechanism)

    Confidence:
    - High confidence: All 3 models agree (>80% consensus)
    - Medium confidence: 2/3 models agree (60-80% consensus)
    - Low confidence: Models disagree (<60% consensus)
    """

    def __init__(self,
                 xgboost_model_path: str = "models/xgboost_m1.pkl",
                 sequence_length: int = 60,
                 n_features: int = 230):
        """
        Initialize ensemble with all models

        Args:
            xgboost_model_path: Path to trained XGBoost model
            sequence_length: Sequence length for LSTM/Transformer
            n_features: Number of input features
        """
        self.xgboost_model_path = Path(xgboost_model_path)
        self.sequence_length = sequence_length
        self.n_features = n_features

        # Model weights (must sum to 1.0)
        self.weights = {
            'xgboost': 0.40,  # Proven track record
            'lstm': 0.30,      # Temporal memory
            'transformer': 0.30  # Attention mechanism
        }

        # Initialize models
        self.xgboost_model = None
        self.lstm_model = None
        self.transformer_model = None

        # Load models
        self.load_models()

    def load_models(self):
        """Load all ensemble models"""
        logger.info("🧠 Loading Deep Learning Ensemble...")

        # Load XGBoost (existing model)
        try:
            if self.xgboost_model_path.exists():
                self.xgboost_model = joblib.load(self.xgboost_model_path)
                logger.info(f"   ✅ XGBoost loaded from {self.xgboost_model_path}")
            else:
                logger.warning(f"   ⚠️  XGBoost model not found at {self.xgboost_model_path}")
        except Exception as e:
            logger.error(f"   ❌ Failed to load XGBoost: {e}")

        # Load LSTM
        try:
            self.lstm_model = LSTMPredictor(
                sequence_length=self.sequence_length,
                n_features=self.n_features,
                model_path="models/lstm_predictor.h5"
            )
            if self.lstm_model.is_trained:
                logger.info(f"   ✅ LSTM loaded")
            else:
                logger.warning(f"   ⚠️  LSTM not trained yet")
        except Exception as e:
            logger.error(f"   ❌ Failed to load LSTM: {e}")

        # Load Transformer
        try:
            self.transformer_model = TransformerPredictor(
                sequence_length=self.sequence_length,
                n_features=self.n_features,
                model_path="models/transformer_predictor.h5"
            )
            if self.transformer_model.is_trained:
                logger.info(f"   ✅ Transformer loaded")
            else:
                logger.warning(f"   ⚠️  Transformer not trained yet")
        except Exception as e:
            logger.error(f"   ❌ Failed to load Transformer: {e}")

        # Count active models
        active_models = sum([
            self.xgboost_model is not None,
            self.lstm_model is not None and self.lstm_model.is_trained,
            self.transformer_model is not None and self.transformer_model.is_trained
        ])

        logger.info(f"🧠 Ensemble ready: {active_models}/3 models active")

    def predict(self, features: np.ndarray) -> Dict:
        """
        Make ensemble prediction

        Args:
            features: Feature array (n_samples, n_features)
                     For XGBoost: Use last row only
                     For LSTM/Transformer: Use full sequence

        Returns:
            {
                'direction': 'BUY' or 'SELL' or 'HOLD',
                'confidence': float (0-100),
                'probabilities': {
                    'buy': float,
                    'hold': float,
                    'sell': float
                },
                'individual_predictions': {
                    'xgboost': {...},
                    'lstm': {...},
                    'transformer': {...}
                },
                'consensus': float (0-100),  # Agreement level
                'model_count': int  # Number of active models
            }
        """
        if len(features) == 0:
            logger.warning("Empty features - returning neutral")
            return self._neutral_prediction()

        # Collect predictions from all models
        predictions = {}

        # 1. XGBoost prediction (use last row only)
        if self.xgboost_model is not None:
            try:
                last_features = features[-1:] if len(features.shape) > 1 else features.reshape(1, -1)
                xgb_probs = self.xgboost_model.predict_proba(last_features)[0]

                # XGBoost outputs: [BUY, SELL] - need to add HOLD
                # Convert to [BUY, HOLD, SELL] format
                predictions['xgboost'] = {
                    'probabilities': {
                        'buy': float(xgb_probs[0]),
                        'hold': 0.0,  # XGBoost doesn't predict HOLD
                        'sell': float(xgb_probs[1])
                    },
                    'direction': 'BUY' if xgb_probs[0] > xgb_probs[1] else 'SELL',
                    'confidence': float(max(xgb_probs) * 100)
                }
                logger.debug(f"XGBoost: {predictions['xgboost']['direction']} ({predictions['xgboost']['confidence']:.1f}%)")
            except Exception as e:
                logger.warning(f"XGBoost prediction failed: {e}")
                predictions['xgboost'] = None

        # 2. LSTM prediction (use full sequence)
        if self.lstm_model is not None and self.lstm_model.is_trained:
            try:
                lstm_pred = self.lstm_model.predict(features)
                predictions['lstm'] = lstm_pred
                logger.debug(f"LSTM: {lstm_pred['direction']} ({lstm_pred['confidence']:.1f}%)")
            except Exception as e:
                logger.warning(f"LSTM prediction failed: {e}")
                predictions['lstm'] = None

        # 3. Transformer prediction (use full sequence)
        if self.transformer_model is not None and self.transformer_model.is_trained:
            try:
                transformer_pred = self.transformer_model.predict(features)
                predictions['transformer'] = transformer_pred
                logger.debug(f"Transformer: {transformer_pred['direction']} ({transformer_pred['confidence']:.1f}%)")
            except Exception as e:
                logger.warning(f"Transformer prediction failed: {e}")
                predictions['transformer'] = None

        # Filter out failed predictions
        valid_predictions = {k: v for k, v in predictions.items() if v is not None}

        if len(valid_predictions) == 0:
            logger.warning("No valid predictions - returning neutral")
            return self._neutral_prediction()

        # Combine predictions using weighted average
        ensemble_result = self._combine_predictions(valid_predictions)
        ensemble_result['individual_predictions'] = predictions
        ensemble_result['model_count'] = len(valid_predictions)

        logger.info(f"🧠 Ensemble: {ensemble_result['direction']} ({ensemble_result['confidence']:.1f}%) | "
                   f"Consensus: {ensemble_result['consensus']:.1f}% | Models: {ensemble_result['model_count']}/3")

        return ensemble_result

    def _combine_predictions(self, predictions: Dict) -> Dict:
        """
        Combine multiple model predictions using weighted average

        Args:
            predictions: Dict of {model_name: prediction_dict}

        Returns:
            Combined prediction with consensus score
        """
        # Initialize probability accumulators
        prob_buy = 0.0
        prob_hold = 0.0
        prob_sell = 0.0
        total_weight = 0.0

        # Weighted average of probabilities
        for model_name, pred in predictions.items():
            weight = self.weights.get(model_name, 1.0 / len(predictions))

            probs = pred['probabilities']
            prob_buy += probs['buy'] * weight
            prob_hold += probs['hold'] * weight
            prob_sell += probs['sell'] * weight
            total_weight += weight

        # Normalize probabilities
        if total_weight > 0:
            prob_buy /= total_weight
            prob_hold /= total_weight
            prob_sell /= total_weight

        # Get final direction
        probs_array = np.array([prob_buy, prob_hold, prob_sell])
        max_prob = np.max(probs_array)
        direction_map = {0: 'BUY', 1: 'HOLD', 2: 'SELL'}
        direction = direction_map[np.argmax(probs_array)]

        # Calculate consensus (how much models agree)
        consensus = self._calculate_consensus(predictions, direction)

        return {
            'direction': direction,
            'confidence': float(max_prob * 100),
            'probabilities': {
                'buy': float(prob_buy),
                'hold': float(prob_hold),
                'sell': float(prob_sell)
            },
            'consensus': float(consensus)
        }

    def _calculate_consensus(self, predictions: Dict, final_direction: str) -> float:
        """
        Calculate how much models agree on the final direction

        Args:
            predictions: Dict of {model_name: prediction_dict}
            final_direction: Final ensemble direction

        Returns:
            Consensus percentage (0-100)
        """
        if len(predictions) == 0:
            return 0.0

        # Count how many models agree with final direction
        agree_count = sum(1 for pred in predictions.values()
                         if pred['direction'] == final_direction)

        # Consensus = (agree_count / total_models) * 100
        consensus = (agree_count / len(predictions)) * 100

        return consensus

    def _neutral_prediction(self) -> Dict:
        """Return neutral prediction when no models available"""
        return {
            'direction': 'HOLD',
            'confidence': 50.0,
            'probabilities': {
                'buy': 0.33,
                'hold': 0.34,
                'sell': 0.33
            },
            'individual_predictions': {},
            'consensus': 0.0,
            'model_count': 0
        }

    def get_status(self) -> Dict:
        """
        Get ensemble status

        Returns:
            {
                'total_models': int,
                'active_models': int,
                'models': {
                    'xgboost': bool,
                    'lstm': bool,
                    'transformer': bool
                },
                'weights': dict
            }
        """
        active_models = {
            'xgboost': self.xgboost_model is not None,
            'lstm': self.lstm_model is not None and self.lstm_model.is_trained,
            'transformer': self.transformer_model is not None and self.transformer_model.is_trained
        }

        return {
            'total_models': 3,
            'active_models': sum(active_models.values()),
            'models': active_models,
            'weights': self.weights
        }
