"""
ML Scanner
Scans for trading opportunities using trained ML model
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime

from src.ml.model_trainer import ModelTrainer
from src.ml.feature_engineering import FeatureEngineer
from src.data.indicators import TechnicalIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MLScanner:
    """
    Scans for trading opportunities using ML model
    """

    def __init__(self, model_path: str = 'models/rf_model_latest.pkl'):
        """
        Args:
            model_path: Path to trained ML model
        """
        # Load model directly using pickle
        import pickle
        from pathlib import Path

        model_file = Path(model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        with open(model_file, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.feature_engineer = FeatureEngineer()
        logger.info(f"Initialized ML Scanner with model: {model_path}")

    def scan_opportunities(
        self,
        symbols: List[str],
        market_data: Dict[str, Dict],
        min_confidence: float = 65.0
    ) -> List[Dict]:
        """
        Scan for trading opportunities

        Args:
            symbols: List of symbols to scan
            market_data: Dict of {symbol: {timeframes: dataframes}}
            min_confidence: Minimum ML confidence threshold

        Returns:
            List of opportunities with ML predictions
        """
        opportunities = []

        for symbol in symbols:
            if symbol not in market_data:
                continue

            try:
                # Get multi-timeframe data
                mtf_data = market_data[symbol]

                # Ensure we have required timeframes
                if 'H1' not in mtf_data or 'H4' not in mtf_data or 'D1' not in mtf_data:
                    logger.warning(f"Missing timeframe data for {symbol}")
                    continue

                # Calculate indicators
                mtf_indicators = {}
                for tf, df in mtf_data.items():
                    if len(df) < 50:
                        continue
                    mtf_indicators[tf] = TechnicalIndicators.calculate_all(df)

                # Extract features
                features = self.feature_engineer.extract_features(
                    symbol=symbol,
                    mtf_data=mtf_data,
                    mtf_indicators=mtf_indicators
                )

                # Predict with ML model
                prediction = self._predict(features)

                # Debug: Log all predictions to see confidence levels
                logger.debug(
                    f"{symbol}: {prediction['direction']} @ {prediction['confidence']:.1f}% "
                    f"(buy:{prediction['buy_prob']:.2f}, sell:{prediction['sell_prob']:.2f}, hold:{prediction['hold_prob']:.2f})"
                )

                if prediction['direction'] != 'HOLD' and prediction['confidence'] >= min_confidence:
                    # Get current price and ATR for entry/exit calculation
                    current_price = mtf_data['H1']['close'].iloc[-1]
                    atr = mtf_indicators['H1'].get('atr', current_price * 0.001)

                    opportunity = {
                        'symbol': symbol,
                        'direction': prediction['direction'],
                        'confidence': prediction['confidence'],
                        'entry_price': current_price,
                        'atr': atr,
                        'features': features,
                        'timeframe_votes': self._get_timeframe_votes(mtf_data, mtf_indicators),
                        'timestamp': datetime.now()
                    }

                    opportunities.append(opportunity)
                    logger.info(
                        f"Opportunity found: {symbol} {prediction['direction']} "
                        f"(confidence: {prediction['confidence']:.1f}%)"
                    )

            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue

        logger.info(f"Scan complete: Found {len(opportunities)} opportunities from {len(symbols)} symbols")
        return opportunities

    def _predict(self, features: Dict) -> Dict:
        """
        Make ML prediction

        Returns:
            Dict with direction and confidence
        """
        # Convert features to DataFrame
        feature_df = pd.DataFrame([features])

        # Get prediction probabilities
        probabilities = self.model.predict_proba(feature_df)[0]

        # Classes: [BUY, SELL, HOLD]
        buy_prob = probabilities[0]
        sell_prob = probabilities[1]
        hold_prob = probabilities[2]

        # Determine direction and confidence
        if buy_prob > sell_prob and buy_prob > hold_prob:
            return {
                'direction': 'BUY',
                'confidence': buy_prob * 100,
                'buy_prob': buy_prob,
                'sell_prob': sell_prob,
                'hold_prob': hold_prob
            }
        elif sell_prob > buy_prob and sell_prob > hold_prob:
            return {
                'direction': 'SELL',
                'confidence': sell_prob * 100,
                'buy_prob': buy_prob,
                'sell_prob': sell_prob,
                'hold_prob': hold_prob
            }
        else:
            return {
                'direction': 'HOLD',
                'confidence': hold_prob * 100,
                'buy_prob': buy_prob,
                'sell_prob': sell_prob,
                'hold_prob': hold_prob
            }

    def _get_timeframe_votes(
        self,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict]
    ) -> Dict[str, str]:
        """
        Get simple timeframe votes based on trend

        Returns:
            Dict of {timeframe: 'BUY'/'SELL'/'NEUTRAL'}
        """
        votes = {}

        for tf, indicators in mtf_indicators.items():
            if 'ema_20' in indicators and 'ema_50' in indicators:
                ema_20 = indicators['ema_20']
                ema_50 = indicators['ema_50']

                if ema_20 > ema_50 * 1.001:  # 0.1% threshold
                    votes[tf] = 'BUY'
                elif ema_20 < ema_50 * 0.999:
                    votes[tf] = 'SELL'
                else:
                    votes[tf] = 'NEUTRAL'
            else:
                votes[tf] = 'NEUTRAL'

        return votes

    def get_required_timeframes(self) -> List[str]:
        """Get list of required timeframes for scanning"""
        return ['M15', 'M30', 'H1', 'H4', 'D1']
