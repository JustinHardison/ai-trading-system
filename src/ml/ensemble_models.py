"""
ENSEMBLE ML SYSTEM - MULTIPLE MODELS
Combines XGBoost, LightGBM, CatBoost, GradientBoosting, RandomForest
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
import pickle
from pathlib import Path

try:
    import xgboost as xgb
    HAS_XGB = True
except:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except:
    HAS_LGB = False

try:
    import catboost as cb
    HAS_CAT = True
except:
    HAS_CAT = False

from ..utils.logger import get_logger

logger = get_logger(__name__)


class EnsemblePredictor:
    """
    Multi-model ensemble that votes on predictions
    Uses weighted voting based on model confidence
    """

    def __init__(self):
        self.models = {}
        self.model_weights = {}
        self.feature_names = []

    def load_models(self, model_dir: str = 'models'):
        """Load all available ensemble models"""
        model_dir = Path(model_dir)

        logger.info("=" * 70)
        logger.info("LOADING ENSEMBLE MODELS")
        logger.info("=" * 70)

        # Load existing gradient boosting model
        gb_path = model_dir / 'us30_optimized_latest.pkl'
        if gb_path.exists():
            with open(gb_path, 'rb') as f:
                gb_model = pickle.load(f)
                self.models['gradient_boosting'] = gb_model['model']
                self.model_weights['gradient_boosting'] = 0.25
                logger.info("✓ Gradient Boosting loaded (weight: 0.25)")

        # Load Random Forest if exists
        rf_path = model_dir / 'us30_rf_latest.pkl'
        if rf_path.exists():
            with open(rf_path, 'rb') as f:
                rf_model = pickle.load(f)
                self.models['random_forest'] = rf_model['model']
                self.model_weights['random_forest'] = 0.20
                logger.info("✓ Random Forest loaded (weight: 0.20)")

        # Load XGBoost if available
        if HAS_XGB:
            xgb_path = model_dir / 'us30_xgb_latest.pkl'
            if xgb_path.exists():
                with open(xgb_path, 'rb') as f:
                    xgb_model = pickle.load(f)
                    self.models['xgboost'] = xgb_model['model']
                    self.model_weights['xgboost'] = 0.25
                    logger.info("✓ XGBoost loaded (weight: 0.25)")

        # Load LightGBM if available
        if HAS_LGB:
            lgb_path = model_dir / 'us30_lgb_latest.pkl'
            if lgb_path.exists():
                with open(lgb_path, 'rb') as f:
                    lgb_model = pickle.load(f)
                    self.models['lightgbm'] = lgb_model['model']
                    self.model_weights['lightgbm'] = 0.20
                    logger.info("✓ LightGBM loaded (weight: 0.20)")

        # Load CatBoost if available
        if HAS_CAT:
            cat_path = model_dir / 'us30_cat_latest.pkl'
            if cat_path.exists():
                with open(cat_path, 'rb') as f:
                    cat_model = pickle.load(f)
                    self.models['catboost'] = cat_model['model']
                    self.model_weights['catboost'] = 0.10
                    logger.info("✓ CatBoost loaded (weight: 0.10)")

        # Normalize weights
        total_weight = sum(self.model_weights.values())
        if total_weight > 0:
            for model_name in self.model_weights:
                self.model_weights[model_name] /= total_weight

        logger.info(f"Loaded {len(self.models)} models for ensemble")
        logger.info("=" * 70)

        return len(self.models) > 0

    def predict(self, features_df: pd.DataFrame) -> Tuple[str, float, Dict]:
        """
        Weighted ensemble prediction

        Returns:
            direction: BUY, SELL, or HOLD
            confidence: 0-100
            model_votes: individual model predictions
        """
        if len(self.models) == 0:
            raise ValueError("No models loaded")

        # Get predictions from each model
        model_predictions = {}
        model_confidences = {}

        for model_name, model in self.models.items():
            try:
                probas = model.predict_proba(features_df)[0]
                pred = model.predict(features_df)[0]

                model_predictions[model_name] = int(pred)
                model_confidences[model_name] = float(probas.max())

            except Exception as e:
                logger.warning(f"Model {model_name} prediction failed: {e}")
                continue

        if len(model_predictions) == 0:
            raise ValueError("All models failed to predict")

        # Weighted voting
        direction_votes = {0: 0, 1: 0, 2: 0}  # HOLD, BUY, SELL

        for model_name, prediction in model_predictions.items():
            weight = self.model_weights.get(model_name, 1.0 / len(self.models))
            confidence_boost = model_confidences[model_name]

            # Weight by both model weight and confidence
            vote_strength = weight * confidence_boost
            direction_votes[prediction] += vote_strength

        # Get final prediction
        final_prediction = max(direction_votes, key=direction_votes.get)
        final_confidence = direction_votes[final_prediction] / sum(direction_votes.values()) * 100

        direction_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        final_direction = direction_map[final_prediction]

        # Build detailed vote breakdown
        vote_details = {}
        for model_name in model_predictions:
            vote_details[model_name] = {
                'prediction': direction_map[model_predictions[model_name]],
                'confidence': model_confidences[model_name] * 100,
                'weight': self.model_weights.get(model_name, 0) * 100
            }

        return final_direction, final_confidence, vote_details

    def get_ensemble_stats(self) -> Dict:
        """Get statistics about the ensemble"""
        return {
            'num_models': len(self.models),
            'model_names': list(self.models.keys()),
            'model_weights': {k: v * 100 for k, v in self.model_weights.items()},
            'has_xgboost': 'xgboost' in self.models,
            'has_lightgbm': 'lightgbm' in self.models,
            'has_catboost': 'catboost' in self.models
        }


class ModelTrainer:
    """Train ensemble models"""

    @staticmethod
    def train_xgboost(X_train, y_train, X_val, y_val):
        """Train XGBoost classifier"""
        if not HAS_XGB:
            logger.warning("XGBoost not installed")
            return None

        logger.info("Training XGBoost...")

        model = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            eval_metric='mlogloss',
            early_stopping_rounds=50,
            random_state=42
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )

        val_acc = model.score(X_val, y_val)
        logger.info(f"XGBoost validation accuracy: {val_acc:.3f}")

        return model

    @staticmethod
    def train_lightgbm(X_train, y_train, X_val, y_val):
        """Train LightGBM classifier"""
        if not HAS_LGB:
            logger.warning("LightGBM not installed")
            return None

        logger.info("Training LightGBM...")

        model = lgb.LGBMClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.05,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=20,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            eval_metric='multi_logloss',
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
        )

        val_acc = model.score(X_val, y_val)
        logger.info(f"LightGBM validation accuracy: {val_acc:.3f}")

        return model

    @staticmethod
    def train_catboost(X_train, y_train, X_val, y_val):
        """Train CatBoost classifier"""
        if not HAS_CAT:
            logger.warning("CatBoost not installed")
            return None

        logger.info("Training CatBoost...")

        model = cb.CatBoostClassifier(
            iterations=500,
            depth=8,
            learning_rate=0.05,
            l2_leaf_reg=3,
            random_seed=42,
            verbose=False
        )

        model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            early_stopping_rounds=50
        )

        val_acc = model.score(X_val, y_val)
        logger.info(f"CatBoost validation accuracy: {val_acc:.3f}")

        return model
