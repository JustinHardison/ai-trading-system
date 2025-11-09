"""
ML Model Training
Trains Random Forest classifier on historical trading data
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Optional
from pathlib import Path
import pickle
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ModelTrainer:
    """
    Trains and evaluates ML models for trade classification
    """

    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_dir = Path("models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train(
        self,
        training_data: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict:
        """
        Train Random Forest classifier

        Args:
            training_data: DataFrame with features and labels
            test_size: Fraction of data to use for testing
            random_state: Random seed for reproducibility

        Returns:
            Dict with training metrics
        """
        logger.info("Starting model training...")

        # Separate features and labels
        feature_cols = [col for col in training_data.columns
                       if not col.startswith('label_')]

        X = training_data[feature_cols]

        # Multi-class labels: 0=hold, 1=buy, 2=sell
        y = np.zeros(len(training_data))
        y[training_data['label_buy'] == 1] = 1
        y[training_data['label_sell'] == 1] = 2

        logger.info(f"Training data shape: {X.shape}")
        logger.info(f"Class distribution: Hold={sum(y==0)}, Buy={sum(y==1)}, Sell={sum(y==2)}")

        # Store feature names
        self.feature_names = feature_cols

        # Handle missing values
        X = X.fillna(0)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train Random Forest
        logger.info("Training Random Forest...")
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=random_state,
            n_jobs=-1,
            class_weight='balanced'  # Handle class imbalance
        )

        self.model.fit(X_train_scaled, y_train)

        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)

        logger.info(f"Training accuracy: {train_score:.3f}")
        logger.info(f"Test accuracy: {test_score:.3f}")

        # Cross-validation
        cv_scores = cross_val_score(self.model, X_train_scaled, y_train, cv=5)
        logger.info(f"Cross-validation scores: {cv_scores}")
        logger.info(f"CV mean: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")

        # Predictions
        y_pred = self.model.predict(X_test_scaled)

        # Classification report
        logger.info("\nClassification Report:")
        # Get unique classes present in the data
        unique_classes = sorted(np.unique(np.concatenate([y_test, y_pred])))
        class_names = ['Hold', 'Buy', 'Sell']
        labels_present = [class_names[int(i)] for i in unique_classes]

        report = classification_report(
            y_test, y_pred,
            labels=unique_classes,
            target_names=labels_present,
            zero_division=0
        )
        logger.info(f"\n{report}")

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        logger.info("\nConfusion Matrix:")
        logger.info(f"\n{cm}")

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info("\nTop 20 Most Important Features:")
        logger.info(f"\n{feature_importance.head(20)}")

        # Save model
        self.save_model()

        return {
            'train_accuracy': train_score,
            'test_accuracy': test_score,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'feature_importance': feature_importance
        }

    def predict(self, features: pd.DataFrame) -> Dict:
        """
        Predict trade action and confidence

        Args:
            features: DataFrame with feature values

        Returns:
            Dict with action, confidence, probabilities
        """
        if self.model is None or self.scaler is None:
            raise ValueError("Model not trained or loaded")

        # Ensure correct feature order
        X = features[self.feature_names].fillna(0)

        # Scale
        X_scaled = self.scaler.transform(X)

        # Predict
        prediction = self.model.predict(X_scaled)[0]
        probabilities = self.model.predict_proba(X_scaled)[0]

        # Map prediction to action
        action_map = {0: 'hold', 1: 'buy', 2: 'sell'}
        action = action_map[int(prediction)]

        # Confidence = probability of predicted class
        confidence = probabilities[int(prediction)] * 100

        return {
            'action': action,
            'confidence': confidence,
            'prob_hold': probabilities[0] * 100,
            'prob_buy': probabilities[1] * 100,
            'prob_sell': probabilities[2] * 100
        }

    def save_model(self, filename: Optional[str] = None):
        """Save trained model and scaler"""
        if self.model is None:
            logger.warning("No model to save")
            return

        if filename is None:
            filename = f"rf_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"

        filepath = self.model_dir / filename

        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved to {filepath}")

        # Also save as "latest"
        latest_path = self.model_dir / "rf_model_latest.pkl"
        with open(latest_path, 'wb') as f:
            pickle.dump(model_data, f)
        logger.info(f"Model also saved as {latest_path}")

    def load_model(self, filename: Optional[str] = None):
        """Load trained model"""
        if filename is None:
            filename = "rf_model_latest.pkl"

        filepath = self.model_dir / filename

        if not filepath.exists():
            logger.error(f"Model file not found: {filepath}")
            return False

        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)

            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']

            logger.info(f"Model loaded from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
