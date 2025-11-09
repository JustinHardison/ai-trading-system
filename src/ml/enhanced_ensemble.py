"""
Enhanced Ensemble with 4+ Models
XGBoost + LightGBM + Neural Network + Random Forest + CatBoost
"""
import numpy as np
import pandas as pd
from typing import Dict, Tuple
import pickle
from pathlib import Path
from datetime import datetime

import xgboost as xgb
import lightgbm as lgb
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

try:
    import catboost as cb
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("⚠️  CatBoost not available - using 4 models instead of 5")

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedEnsembleTrainer:
    """
    Enhanced ensemble with 4-5 models
    
    Models:
    1. XGBoost - Gradient boosting, excellent for trends
    2. LightGBM - Fast, efficient, great for high-frequency
    3. Neural Network - Pattern recognition, non-linear
    4. Random Forest - Robust, handles noise well
    5. CatBoost - Advanced boosting (if available)
    
    Ensemble: Weighted voting based on validation performance
    """
    
    def __init__(self):
        self.xgb_model = None
        self.lgb_model = None
        self.nn_model = None
        self.rf_model = None
        self.cb_model = None if not CATBOOST_AVAILABLE else None
        self.ensemble_weights = None
        self.feature_names = None
        self.n_models = 5 if CATBOOST_AVAILABLE else 4
        
    def train_ensemble(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray
    ) -> Dict:
        """Train all models and determine optimal ensemble weights"""
        logger.info("="*70)
        logger.info(f"TRAINING ENHANCED ENSEMBLE ({self.n_models} MODELS)")
        logger.info("="*70)
        
        self.feature_names = list(X_train.columns)
        
        # Train all models
        logger.info("\n1. Training XGBoost...")
        xgb_metrics = self._train_xgboost(X_train, y_train, X_val, y_val)
        
        logger.info("\n2. Training LightGBM...")
        lgb_metrics = self._train_lightgbm(X_train, y_train, X_val, y_val)
        
        logger.info("\n3. Training Neural Network...")
        nn_metrics = self._train_neural_network(X_train, y_train, X_val, y_val)
        
        logger.info("\n4. Training Random Forest...")
        rf_metrics = self._train_random_forest(X_train, y_train, X_val, y_val)
        
        if CATBOOST_AVAILABLE:
            logger.info("\n5. Training CatBoost...")
            cb_metrics = self._train_catboost(X_train, y_train, X_val, y_val)
        
        # Calculate ensemble weights
        accuracies = [
            xgb_metrics['accuracy'],
            lgb_metrics['accuracy'],
            nn_metrics['accuracy'],
            rf_metrics['accuracy']
        ]
        
        if CATBOOST_AVAILABLE and cb_metrics:
            accuracies.append(cb_metrics['accuracy'])
        
        # Weighted by accuracy
        total_acc = sum(accuracies)
        self.ensemble_weights = [acc / total_acc for acc in accuracies]
        
        logger.info("\n" + "="*70)
        logger.info("ENSEMBLE WEIGHTS:")
        logger.info(f"  XGBoost:        {self.ensemble_weights[0]:.3f} (acc: {accuracies[0]:.3f})")
        logger.info(f"  LightGBM:       {self.ensemble_weights[1]:.3f} (acc: {accuracies[1]:.3f})")
        logger.info(f"  Neural Network: {self.ensemble_weights[2]:.3f} (acc: {accuracies[2]:.3f})")
        logger.info(f"  Random Forest:  {self.ensemble_weights[3]:.3f} (acc: {accuracies[3]:.3f})")
        if CATBOOST_AVAILABLE:
            logger.info(f"  CatBoost:       {self.ensemble_weights[4]:.3f} (acc: {accuracies[4]:.3f})")
        logger.info("="*70)
        
        # Test ensemble
        ensemble_acc = self._test_ensemble(X_val, y_val)
        logger.info(f"\n✅ ENSEMBLE ACCURACY: {ensemble_acc:.3f}")
        
        return {
            'xgb': xgb_metrics,
            'lgb': lgb_metrics,
            'nn': nn_metrics,
            'rf': rf_metrics,
            'cb': cb_metrics if CATBOOST_AVAILABLE else None,
            'ensemble_accuracy': ensemble_acc,
            'ensemble_weights': self.ensemble_weights
        }
    
    def _train_xgboost(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train XGBoost model"""
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='mlogloss'
        )
        
        self.xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        y_pred = self.xgb_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"  XGBoost Accuracy: {accuracy:.3f}")
        return {'accuracy': accuracy}
    
    def _train_lightgbm(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train LightGBM model"""
        self.lgb_model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            verbose=-1
        )
        
        self.lgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.log_evaluation(0)]
        )
        
        y_pred = self.lgb_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"  LightGBM Accuracy: {accuracy:.3f}")
        return {'accuracy': accuracy}
    
    def _train_neural_network(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train Neural Network"""
        self.nn_model = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            alpha=0.001,
            batch_size=256,
            learning_rate='adaptive',
            max_iter=100,
            random_state=42,
            verbose=False
        )
        
        self.nn_model.fit(X_train, y_train)
        
        y_pred = self.nn_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"  Neural Network Accuracy: {accuracy:.3f}")
        return {'accuracy': accuracy}
    
    def _train_random_forest(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train Random Forest"""
        self.rf_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
            verbose=0
        )
        
        self.rf_model.fit(X_train, y_train)
        
        y_pred = self.rf_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"  Random Forest Accuracy: {accuracy:.3f}")
        return {'accuracy': accuracy}
    
    def _train_catboost(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train CatBoost (if available)"""
        if not CATBOOST_AVAILABLE:
            return None
            
        self.cb_model = cb.CatBoostClassifier(
            iterations=200,
            depth=6,
            learning_rate=0.05,
            random_seed=42,
            verbose=False
        )
        
        self.cb_model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            verbose=False
        )
        
        y_pred = self.cb_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"  CatBoost Accuracy: {accuracy:.3f}")
        return {'accuracy': accuracy}
    
    def _test_ensemble(self, X_val, y_val) -> float:
        """Test ensemble prediction"""
        # Get predictions from all models
        xgb_pred = self.xgb_model.predict(X_val)
        lgb_pred = self.lgb_model.predict(X_val)
        nn_pred = self.nn_model.predict(X_val)
        rf_pred = self.rf_model.predict(X_val)
        
        # Weighted voting
        ensemble_pred = (
            xgb_pred * self.ensemble_weights[0] +
            lgb_pred * self.ensemble_weights[1] +
            nn_pred * self.ensemble_weights[2] +
            rf_pred * self.ensemble_weights[3]
        )
        
        if CATBOOST_AVAILABLE and self.cb_model:
            cb_pred = self.cb_model.predict(X_val)
            if len(cb_pred.shape) > 1:
                cb_pred = cb_pred.flatten()
            ensemble_pred += cb_pred * self.ensemble_weights[4]
        
        ensemble_pred = np.round(ensemble_pred).astype(int)
        
        return accuracy_score(y_val, ensemble_pred)
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Predict using ensemble"""
        xgb_pred = self.xgb_model.predict(X)
        lgb_pred = self.lgb_model.predict(X)
        nn_pred = self.nn_model.predict(X)
        rf_pred = self.rf_model.predict(X)
        
        ensemble_pred = (
            xgb_pred * self.ensemble_weights[0] +
            lgb_pred * self.ensemble_weights[1] +
            nn_pred * self.ensemble_weights[2] +
            rf_pred * self.ensemble_weights[3]
        )
        
        if CATBOOST_AVAILABLE and self.cb_model:
            cb_pred = self.cb_model.predict(X)
            if len(cb_pred.shape) > 1:
                cb_pred = cb_pred.flatten()
            ensemble_pred += cb_pred * self.ensemble_weights[4]
        
        ensemble_pred = np.round(ensemble_pred).astype(int)
        
        # Get probabilities
        xgb_proba = self.xgb_model.predict_proba(X)
        lgb_proba = self.lgb_model.predict_proba(X)
        nn_proba = self.nn_model.predict_proba(X)
        rf_proba = self.rf_model.predict_proba(X)
        
        ensemble_proba = (
            xgb_proba * self.ensemble_weights[0] +
            lgb_proba * self.ensemble_weights[1] +
            nn_proba * self.ensemble_weights[2] +
            rf_proba * self.ensemble_weights[3]
        )
        
        if CATBOOST_AVAILABLE and self.cb_model:
            cb_proba = self.cb_model.predict_proba(X)
            ensemble_proba += cb_proba * self.ensemble_weights[4]
        
        return ensemble_pred, ensemble_proba
    
    def save(self, filepath: str):
        """Save ensemble"""
        model_dict = {
            'xgb_model': self.xgb_model,
            'lgb_model': self.lgb_model,
            'nn_model': self.nn_model,
            'rf_model': self.rf_model,
            'cb_model': self.cb_model if CATBOOST_AVAILABLE else None,
            'ensemble_weights': self.ensemble_weights,
            'feature_names': self.feature_names,
            'n_models': self.n_models
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_dict, f)
        
        logger.info(f"✅ Enhanced ensemble saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str):
        """Load ensemble"""
        with open(filepath, 'rb') as f:
            model_dict = pickle.load(f)
        
        ensemble = cls()
        ensemble.xgb_model = model_dict['xgb_model']
        ensemble.lgb_model = model_dict['lgb_model']
        ensemble.nn_model = model_dict['nn_model']
        ensemble.rf_model = model_dict['rf_model']
        ensemble.cb_model = model_dict.get('cb_model')
        ensemble.ensemble_weights = model_dict['ensemble_weights']
        ensemble.feature_names = model_dict['feature_names']
        ensemble.n_models = model_dict.get('n_models', 4)
        
        logger.info(f"✅ Enhanced ensemble loaded from {filepath} ({ensemble.n_models} models)")
        return ensemble
