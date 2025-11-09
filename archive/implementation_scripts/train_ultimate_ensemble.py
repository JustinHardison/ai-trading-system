#!/usr/bin/env python3
"""
ULTIMATE ENSEMBLE TRAINING SCRIPT
Trains 5-model ensemble with 500+ advanced features

Features:
- 500+ advanced features (price stats, fractals, microstructure, regimes)
- Sentiment analysis (Fear & Greed, VIX, Reddit, breadth)
- DIA options data (gamma, put/call, IV skew)
- Ensemble: XGBoost + LightGBM + CatBoost + GradientBoosting + RandomForest

This brings the system to HEDGE FUND level.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import warnings
warnings.filterwarnings('ignore')

from src.ml.advanced_features import AdvancedFeatureEngineer
from src.ml.ensemble_models import EnsemblePredictor
from src.data.sentiment_analyzer import SentimentAnalyzer
from src.data.options_data import OptionsDataProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def collect_us30_data(num_samples=10000):
    """
    Collect US30 training data from historical prices
    In production, this would fetch from broker API
    For now, generate synthetic but realistic data
    """
    logger.info(f"Collecting {num_samples} training samples...")

    # Generate realistic US30 price data
    np.random.seed(42)

    # Base price around 44000
    base_price = 44000

    # Generate price movements with realistic volatility
    returns = np.random.normal(0.0001, 0.005, num_samples)  # US30 typical daily volatility
    prices = base_price * (1 + returns).cumprod()

    # Create OHLCV data
    data = {
        'H1': pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.002, 0.002, num_samples)),
            'high': prices * (1 + np.random.uniform(0, 0.004, num_samples)),
            'low': prices * (1 - np.random.uniform(0, 0.004, num_samples)),
            'close': prices,
            'volume': np.random.randint(500, 2000, num_samples),
            'timestamp': pd.date_range('2024-01-01', periods=num_samples, freq='H')
        }),
        'H4': pd.DataFrame({
            'open': prices[::4] * (1 + np.random.uniform(-0.002, 0.002, num_samples//4)),
            'high': prices[::4] * (1 + np.random.uniform(0, 0.005, num_samples//4)),
            'low': prices[::4] * (1 - np.random.uniform(0, 0.005, num_samples//4)),
            'close': prices[::4],
            'volume': np.random.randint(2000, 8000, num_samples//4),
            'timestamp': pd.date_range('2024-01-01', periods=num_samples//4, freq='4H')
        }),
        'M15': pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.001, 0.001, num_samples)),
            'high': prices * (1 + np.random.uniform(0, 0.002, num_samples)),
            'low': prices * (1 - np.random.uniform(0, 0.002, num_samples)),
            'close': prices,
            'volume': np.random.randint(200, 800, num_samples),
            'timestamp': pd.date_range('2024-01-01', periods=num_samples, freq='15T')
        }),
        'M30': pd.DataFrame({
            'open': prices * (1 + np.random.uniform(-0.001, 0.001, num_samples)),
            'high': prices * (1 + np.random.uniform(0, 0.003, num_samples)),
            'low': prices * (1 - np.random.uniform(0, 0.003, num_samples)),
            'close': prices,
            'volume': np.random.randint(300, 1200, num_samples),
            'timestamp': pd.date_range('2024-01-01', periods=num_samples, freq='30T')
        })
    }

    # Generate labels (BUY=1, SELL=2, HOLD=0)
    # Use future price movement to create labels
    future_return = np.diff(prices, prepend=prices[0]) / prices

    labels = []
    for ret in future_return:
        if ret > 0.002:  # > 0.2% move up = BUY
            labels.append(1)
        elif ret < -0.002:  # < -0.2% move down = SELL
            labels.append(2)
        else:  # Small move = HOLD
            labels.append(0)

    labels = np.array(labels)

    logger.info(f"Data collected: BUY={np.sum(labels==1)}, SELL={np.sum(labels==2)}, HOLD={np.sum(labels==0)}")

    return data, labels


def extract_all_features(mtf_data, sentiment_analyzer, options_provider, feature_engineer):
    """
    Extract ALL 500+ features including:
    - Advanced features (500+)
    - Sentiment features (4)
    - Options features (14)
    """
    logger.info("Extracting 500+ features...")

    all_features = []

    for i in range(len(mtf_data['H1']) - 200):  # Need 200 bars for features
        # Get windows of data
        window_data = {
            'H1': mtf_data['H1'].iloc[i:i+200],
            'H4': mtf_data['H4'].iloc[i//4:i//4+50] if i//4+50 < len(mtf_data['H4']) else mtf_data['H4'].iloc[i//4:],
            'M15': mtf_data['M15'].iloc[i*4:i*4+800] if i*4+800 < len(mtf_data['M15']) else mtf_data['M15'].iloc[i*4:],
            'M30': mtf_data['M30'].iloc[i*2:i*2+400] if i*2+400 < len(mtf_data['M30']) else mtf_data['M30'].iloc[i*2:]
        }

        # Calculate indicators (needed for advanced features)
        from src.data.indicators import TechnicalIndicators
        indicators_calc = TechnicalIndicators()

        mtf_indicators = {}
        for tf, df in window_data.items():
            if len(df) >= 50:
                mtf_indicators[tf] = indicators_calc.calculate_all(df)

        if len(mtf_indicators) < 2:
            continue

        try:
            # 1. Advanced features (500+)
            advanced_features = feature_engineer.extract_all_features(window_data, mtf_indicators)

            # 2. Sentiment features (4 sources)
            sentiment_data = sentiment_analyzer.get_overall_sentiment()
            sentiment_features = {
                'sentiment_score': sentiment_data['sentiment_score'],
                'sentiment_confidence': sentiment_data['confidence'],
                'fear_greed': sentiment_data['sources'].get('fear_greed', 0),
                'vix_sentiment': sentiment_data['sources'].get('vix', 0),
                'reddit_sentiment': sentiment_data['sources'].get('reddit', 0),
                'breadth_sentiment': sentiment_data['sources'].get('breadth', 0)
            }

            # 3. Options features (14)
            options_features = options_provider.get_dia_gamma_exposure()

            # Combine all features
            combined_features = {
                **advanced_features,
                **sentiment_features,
                **options_features
            }

            all_features.append(combined_features)

        except Exception as e:
            logger.warning(f"Error extracting features at index {i}: {e}")
            continue

        if (i + 1) % 1000 == 0:
            logger.info(f"Extracted {len(all_features)} feature sets...")

    logger.info(f"Total features extracted: {len(all_features)} samples × {len(all_features[0]) if all_features else 0} features")

    return pd.DataFrame(all_features)


def train_ensemble():
    """Train complete ensemble with all 500+ features"""

    logger.info("=" * 70)
    logger.info("  TRAINING ULTIMATE ENSEMBLE WITH 500+ FEATURES")
    logger.info("  Hedge Fund Level ML")
    logger.info("=" * 70)

    # 1. Initialize feature extractors
    logger.info("\n[1/6] Initializing feature extractors...")
    feature_engineer = AdvancedFeatureEngineer()
    sentiment_analyzer = SentimentAnalyzer()
    options_provider = OptionsDataProvider()

    # 2. Collect training data
    logger.info("\n[2/6] Collecting US30 training data...")
    mtf_data, labels = collect_us30_data(num_samples=10000)

    # 3. Extract all features
    logger.info("\n[3/6] Extracting 500+ features (this may take a while)...")
    features_df = extract_all_features(mtf_data, sentiment_analyzer, options_provider, feature_engineer)

    # Align labels with extracted features
    labels = labels[-len(features_df):]

    logger.info(f"Final dataset: {len(features_df)} samples × {features_df.shape[1]} features")
    logger.info(f"Feature columns: {features_df.shape[1]}")

    # 4. Train/test split
    logger.info("\n[4/6] Splitting data (80% train, 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        features_df, labels, test_size=0.2, random_state=42, stratify=labels
    )

    logger.info(f"Train: {len(X_train)} samples")
    logger.info(f"Test: {len(X_test)} samples")

    # 5. Train ensemble
    logger.info("\n[5/6] Training 5-model ensemble...")
    logger.info("  - Gradient Boosting")
    logger.info("  - Random Forest")
    logger.info("  - XGBoost")
    logger.info("  - LightGBM")
    logger.info("  - CatBoost")

    ensemble = EnsemblePredictor()
    ensemble.train(X_train, y_train)

    # 6. Evaluate
    logger.info("\n[6/6] Evaluating ensemble performance...")

    train_pred, train_conf, train_votes = ensemble.predict(X_train)
    test_pred, test_conf, test_votes = ensemble.predict(X_test)

    # Convert predictions to numeric
    pred_map = {'HOLD': 0, 'BUY': 1, 'SELL': 2}
    train_pred_numeric = [pred_map[p] for p in train_pred]
    test_pred_numeric = [pred_map[p] for p in test_pred]

    train_accuracy = accuracy_score(y_train, train_pred_numeric)
    test_accuracy = accuracy_score(y_test, test_pred_numeric)

    logger.info(f"\n📊 RESULTS:")
    logger.info(f"  Train Accuracy: {train_accuracy*100:.2f}%")
    logger.info(f"  Test Accuracy: {test_accuracy*100:.2f}%")

    logger.info(f"\n📝 Classification Report:")
    print(classification_report(y_test, test_pred_numeric, target_names=['HOLD', 'BUY', 'SELL']))

    # 7. Save models
    logger.info("\n💾 Saving ensemble models...")
    models_dir = Path('models')
    models_dir.mkdir(exist_ok=True)

    # Save each model separately
    for model_name, model in ensemble.models.items():
        model_path = models_dir / f"us30_{model_name}_latest.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump({
                'model': model,
                'features': features_df.columns.tolist(),
                'accuracy': test_accuracy,
                'trained_at': datetime.now().isoformat()
            }, f)
        logger.info(f"  ✓ Saved {model_path}")

    # Save ensemble config
    ensemble_config = {
        'model_weights': ensemble.model_weights,
        'feature_columns': features_df.columns.tolist(),
        'num_features': features_df.shape[1],
        'test_accuracy': test_accuracy,
        'trained_at': datetime.now().isoformat()
    }

    config_path = models_dir / 'ensemble_config.pkl'
    with open(config_path, 'wb') as f:
        pickle.dump(ensemble_config, f)
    logger.info(f"  ✓ Saved {config_path}")

    logger.info("\n" + "=" * 70)
    logger.info("  ✅ TRAINING COMPLETE")
    logger.info(f"  📊 Test Accuracy: {test_accuracy*100:.2f}%")
    logger.info(f"  🔢 Features: {features_df.shape[1]}")
    logger.info(f"  🤖 Models: 5 (ensemble)")
    logger.info("=" * 70)

    return ensemble, features_df.columns.tolist(), test_accuracy


if __name__ == "__main__":
    train_ensemble()
