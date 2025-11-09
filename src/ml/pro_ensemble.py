"""
Professional Ensemble Model System for US30 Scalping
Combines XGBoost, LightGBM, and Neural Network predictions
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import pickle
from pathlib import Path
from datetime import datetime

import xgboost as xgb
import lightgbm as lgb
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import VotingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProEnsembleTrainer:
    """
    Professional ensemble model trainer
    
    Models:
    1. XGBoost - Excellent for trend detection and feature interactions
    2. LightGBM - Fast, efficient, great for high-frequency data
    3. Neural Network - Pattern recognition and non-linear relationships
    
    Ensemble Method: Weighted voting based on validation performance
    """
    
    def __init__(self):
        self.xgb_model = None
        self.lgb_model = None
        self.nn_model = None
        self.ensemble_weights = None
        self.feature_names = None
        
    def train_ensemble(
        self,
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        X_val: pd.DataFrame,
        y_val: np.ndarray
    ) -> Dict:
        """
        Train all three models and determine optimal ensemble weights
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            
        Returns:
            Dictionary with trained models and metrics
        """
        logger.info("="*70)
        logger.info("TRAINING PROFESSIONAL ENSEMBLE SYSTEM")
        logger.info("="*70)
        
        self.feature_names = list(X_train.columns)
        
        # Train XGBoost
        logger.info("\n1. Training XGBoost...")
        xgb_metrics = self._train_xgboost(X_train, y_train, X_val, y_val)
        
        # Train LightGBM
        logger.info("\n2. Training LightGBM...")
        lgb_metrics = self._train_lightgbm(X_train, y_train, X_val, y_val)
        
        # Train Neural Network
        logger.info("\n3. Training Neural Network...")
        nn_metrics = self._train_neural_network(X_train, y_train, X_val, y_val)
        
        # Determine ensemble weights based on validation accuracy
        logger.info("\n4. Calculating Ensemble Weights...")
        self.ensemble_weights = self._calculate_weights(xgb_metrics, lgb_metrics, nn_metrics)
        
        # Test ensemble
        ensemble_acc = self._test_ensemble(X_val, y_val)
        
        logger.info("\n" + "="*70)
        logger.info("ENSEMBLE TRAINING COMPLETE")
        logger.info("="*70)
        logger.info(f"XGBoost Accuracy:     {xgb_metrics['accuracy']*100:.2f}%")
        logger.info(f"LightGBM Accuracy:    {lgb_metrics['accuracy']*100:.2f}%")
        logger.info(f"Neural Net Accuracy:  {nn_metrics['accuracy']*100:.2f}%")
        logger.info(f"Ensemble Accuracy:    {ensemble_acc*100:.2f}%")
        logger.info(f"\nEnsemble Weights: XGB={self.ensemble_weights[0]:.2f}, LGB={self.ensemble_weights[1]:.2f}, NN={self.ensemble_weights[2]:.2f}")
        
        return {
            'xgb_model': self.xgb_model,
            'lgb_model': self.lgb_model,
            'nn_model': self.nn_model,
            'ensemble_weights': self.ensemble_weights,
            'feature_names': self.feature_names,
            'xgb_metrics': xgb_metrics,
            'lgb_metrics': lgb_metrics,
            'nn_metrics': nn_metrics,
            'ensemble_accuracy': ensemble_acc,
            'timestamp': datetime.now().isoformat()
        }
    
    def _train_xgboost(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train XGBoost model"""
        params = {
            'objective': 'multi:softmax',
            'num_class': 3,
            'max_depth': 6,
            'learning_rate': 0.1,
            'n_estimators': 200,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'tree_method': 'hist',
            'eval_metric': 'mlogloss'
        }
        
        self.xgb_model = xgb.XGBClassifier(**params)
        self.xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )
        
        y_pred = self.xgb_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"✓ XGBoost trained: {accuracy*100:.2f}% accuracy")
        
        return {
            'accuracy': accuracy,
            'predictions': y_pred
        }
    
    def _train_lightgbm(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train LightGBM model"""
        params = {
            'objective': 'multiclass',
            'num_class': 3,
            'max_depth': 6,
            'learning_rate': 0.1,
            'n_estimators': 200,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'verbose': -1
        }
        
        self.lgb_model = lgb.LGBMClassifier(**params)
        self.lgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.log_evaluation(0)]
        )
        
        y_pred = self.lgb_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"✓ LightGBM trained: {accuracy*100:.2f}% accuracy")
        
        return {
            'accuracy': accuracy,
            'predictions': y_pred
        }
    
    def _train_neural_network(self, X_train, y_train, X_val, y_val) -> Dict:
        """Train Neural Network model"""
        self.nn_model = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            alpha=0.0001,
            batch_size=32,
            learning_rate='adaptive',
            max_iter=200,
            random_state=42,
            verbose=False
        )
        
        self.nn_model.fit(X_train, y_train)
        
        y_pred = self.nn_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"✓ Neural Network trained: {accuracy*100:.2f}% accuracy")
        
        return {
            'accuracy': accuracy,
            'predictions': y_pred
        }
    
    def _calculate_weights(self, xgb_metrics, lgb_metrics, nn_metrics) -> np.ndarray:
        """Calculate ensemble weights based on validation performance"""
        accuracies = np.array([
            xgb_metrics['accuracy'],
            lgb_metrics['accuracy'],
            nn_metrics['accuracy']
        ])
        
        # Softmax to convert accuracies to weights
        exp_acc = np.exp(accuracies * 10)  # Scale for more pronounced differences
        weights = exp_acc / exp_acc.sum()
        
        return weights
    
    def _test_ensemble(self, X_val, y_val) -> float:
        """Test ensemble predictions"""
        # Get predictions from all models
        xgb_pred = self.xgb_model.predict(X_val)
        lgb_pred = self.lgb_model.predict(X_val)
        nn_pred = self.nn_model.predict(X_val)
        
        # Weighted voting
        ensemble_pred = []
        for i in range(len(X_val)):
            votes = np.zeros(3)
            votes[xgb_pred[i]] += self.ensemble_weights[0]
            votes[lgb_pred[i]] += self.ensemble_weights[1]
            votes[nn_pred[i]] += self.ensemble_weights[2]
            ensemble_pred.append(np.argmax(votes))
        
        accuracy = accuracy_score(y_val, ensemble_pred)
        return accuracy
    
    def predict(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make ensemble prediction
        
        Args:
            X: Features
            
        Returns:
            (predictions, confidences)
        """
        # Get predictions from all models
        xgb_pred = self.xgb_model.predict(X)
        lgb_pred = self.lgb_model.predict(X)
        nn_pred = self.nn_model.predict(X)
        
        # Get probabilities
        xgb_proba = self.xgb_model.predict_proba(X)
        lgb_proba = self.lgb_model.predict_proba(X)
        nn_proba = self.nn_model.predict_proba(X)
        
        # Weighted ensemble
        ensemble_pred = []
        ensemble_conf = []
        
        for i in range(len(X)):
            # Weighted voting for prediction
            votes = np.zeros(3)
            votes[xgb_pred[i]] += self.ensemble_weights[0]
            votes[lgb_pred[i]] += self.ensemble_weights[1]
            votes[nn_pred[i]] += self.ensemble_weights[2]
            pred = np.argmax(votes)
            ensemble_pred.append(pred)
            
            # Weighted average for confidence
            weighted_proba = (
                xgb_proba[i] * self.ensemble_weights[0] +
                lgb_proba[i] * self.ensemble_weights[1] +
                nn_proba[i] * self.ensemble_weights[2]
            )
            conf = weighted_proba[pred] * 100
            ensemble_conf.append(conf)
        
        return np.array(ensemble_pred), np.array(ensemble_conf)
