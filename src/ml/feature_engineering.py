"""
Feature Engineering for ML Trading Models
Extracts 40+ features from multi-timeframe technical data
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)


class FeatureEngineer:
    """
    Extracts sophisticated features from multi-timeframe data
    for ML model training and prediction
    """

    def __init__(self):
        self.feature_names = []

    def extract_features(
        self,
        symbol: str,
        mtf_data: Dict[str, pd.DataFrame],
        mtf_indicators: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Extract all features from multi-timeframe data

        Args:
            symbol: Trading symbol
            mtf_data: Dict of {timeframe: OHLCV DataFrame}
            mtf_indicators: Dict of {timeframe: indicators dict}

        Returns:
            Dictionary of feature_name: value
        """
        features = {}

        # Basic info
        features['symbol'] = hash(symbol) % 1000  # Numeric encoding
        features['timestamp'] = datetime.now().timestamp()

        # Extract features for each timeframe
        # Using all 5 timeframes for US30 scalping (M5, M15, M30, H1, H4)
        for tf in ['M5', 'M15', 'M30', 'H1', 'H4']:
            if tf not in mtf_data or tf not in mtf_indicators:
                continue

            df = mtf_data[tf]
            indicators = mtf_indicators[tf]

            # Trend features
            features[f'{tf}_trend_ema'] = self._trend_direction(df, 'ema')
            features[f'{tf}_trend_sma'] = self._trend_direction(df, 'sma')
            features[f'{tf}_price_position'] = self._price_position(df, indicators)

            # Momentum features
            features[f'{tf}_rsi'] = indicators.get('rsi', 50)
            features[f'{tf}_rsi_oversold'] = 1 if indicators.get('rsi', 50) < 30 else 0
            features[f'{tf}_rsi_overbought'] = 1 if indicators.get('rsi', 50) > 70 else 0

            features[f'{tf}_macd'] = indicators.get('macd', 0)
            features[f'{tf}_macd_signal'] = indicators.get('macd_signal', 0)
            features[f'{tf}_macd_diff'] = indicators.get('macd', 0) - indicators.get('macd_signal', 0)
            features[f'{tf}_macd_bullish'] = 1 if features[f'{tf}_macd_diff'] > 0 else 0

            # Volatility features
            features[f'{tf}_atr'] = indicators.get('atr', 0)
            features[f'{tf}_atr_percentile'] = self._atr_percentile(df, indicators.get('atr', 0))
            features[f'{tf}_bb_width'] = self._bb_width(indicators)
            features[f'{tf}_bb_position'] = self._bb_position(df, indicators)

            # Volume features
            features[f'{tf}_volume_ratio'] = indicators.get('volume_ratio', 1.0)
            features[f'{tf}_volume_spike'] = 1 if indicators.get('volume_ratio', 1.0) > 1.5 else 0
            features[f'{tf}_volume_trend'] = self._volume_trend(df)

            # Price action features
            features[f'{tf}_higher_highs'] = self._count_higher_highs(df)
            features[f'{tf}_lower_lows'] = self._count_lower_lows(df)
            features[f'{tf}_price_momentum'] = self._price_momentum(df)
            features[f'{tf}_candle_strength'] = self._candle_strength(df)

        # Multi-timeframe alignment features
        features['mtf_trend_agreement'] = self._mtf_trend_agreement(mtf_indicators)
        features['mtf_momentum_agreement'] = self._mtf_momentum_agreement(mtf_indicators)
        features['mtf_rsi_average'] = self._mtf_rsi_average(mtf_indicators)
        features['mtf_timeframes_bullish'] = self._count_bullish_timeframes(mtf_indicators)
        features['mtf_timeframes_bearish'] = self._count_bearish_timeframes(mtf_indicators)

        # Market timing features
        now = datetime.now()
        features['hour_of_day'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_london_session'] = 1 if 3 <= now.hour <= 12 else 0
        features['is_ny_session'] = 1 if 8 <= now.hour <= 17 else 0
        features['is_asian_session'] = 1 if (19 <= now.hour or now.hour <= 4) else 0

        # Store feature names for later
        if not self.feature_names:
            self.feature_names = list(features.keys())

        return features

    def _trend_direction(self, df: pd.DataFrame, ma_type: str = 'ema') -> int:
        """Determine trend direction using moving averages"""
        try:
            if len(df) < 50:
                return 0

            if ma_type == 'ema':
                ma20 = df['close'].ewm(span=20).mean().iloc[-1]
                ma50 = df['close'].ewm(span=50).mean().iloc[-1]
            else:
                ma20 = df['close'].rolling(20).mean().iloc[-1]
                ma50 = df['close'].rolling(50).mean().iloc[-1]

            if ma20 > ma50:
                return 1  # Bullish
            elif ma20 < ma50:
                return -1  # Bearish
            else:
                return 0  # Neutral
        except:
            return 0

    def _price_position(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Where is price relative to moving averages (0-1)"""
        try:
            current_price = df['close'].iloc[-1]
            sma20 = indicators.get('sma_20', current_price)
            sma50 = indicators.get('sma_50', current_price)

            if sma50 == 0:
                return 0.5

            # Normalize: 0 = below both, 0.5 = between, 1 = above both
            if current_price > sma20 and current_price > sma50:
                return 1.0
            elif current_price < sma20 and current_price < sma50:
                return 0.0
            else:
                return 0.5
        except:
            return 0.5

    def _atr_percentile(self, df: pd.DataFrame, current_atr: float) -> float:
        """ATR percentile rank (0-100)"""
        try:
            if len(df) < 50 or current_atr == 0:
                return 50

            # Calculate ATR for last 50 bars
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()

            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr_series = tr.rolling(14).mean().tail(50)

            percentile = (atr_series < current_atr).sum() / len(atr_series) * 100
            return percentile
        except:
            return 50

    def _bb_width(self, indicators: Dict) -> float:
        """Bollinger Band width (volatility measure)"""
        try:
            bb_upper = indicators.get('bb_upper', 0)
            bb_lower = indicators.get('bb_lower', 0)
            bb_middle = indicators.get('bb_middle', 1)

            if bb_middle == 0:
                return 0

            width = (bb_upper - bb_lower) / bb_middle
            return width
        except:
            return 0

    def _bb_position(self, df: pd.DataFrame, indicators: Dict) -> float:
        """Where is price in BB channel (0-1)"""
        try:
            current_price = df['close'].iloc[-1]
            bb_upper = indicators.get('bb_upper', current_price)
            bb_lower = indicators.get('bb_lower', current_price)

            if bb_upper == bb_lower:
                return 0.5

            position = (current_price - bb_lower) / (bb_upper - bb_lower)
            return max(0, min(1, position))  # Clamp to 0-1
        except:
            return 0.5

    def _volume_trend(self, df: pd.DataFrame) -> float:
        """Volume trend direction"""
        try:
            if len(df) < 50:
                return 1.0

            vol_ema20 = df['volume'].ewm(span=20).mean().iloc[-1]
            vol_ema50 = df['volume'].ewm(span=50).mean().iloc[-1]

            if vol_ema50 == 0:
                return 1.0

            return vol_ema20 / vol_ema50
        except:
            return 1.0

    def _count_higher_highs(self, df: pd.DataFrame, lookback: int = 10) -> int:
        """Count higher highs in recent bars"""
        try:
            if len(df) < lookback + 1:
                return 0

            highs = df['high'].tail(lookback + 1)
            count = 0

            for i in range(1, len(highs)):
                if highs.iloc[i] > highs.iloc[i-1]:
                    count += 1

            return count
        except:
            return 0

    def _count_lower_lows(self, df: pd.DataFrame, lookback: int = 10) -> int:
        """Count lower lows in recent bars"""
        try:
            if len(df) < lookback + 1:
                return 0

            lows = df['low'].tail(lookback + 1)
            count = 0

            for i in range(1, len(lows)):
                if lows.iloc[i] < lows.iloc[i-1]:
                    count += 1

            return count
        except:
            return 0

    def _price_momentum(self, df: pd.DataFrame, periods: int = 10) -> float:
        """Price momentum over last N periods"""
        try:
            if len(df) < periods + 1:
                return 0

            current = df['close'].iloc[-1]
            past = df['close'].iloc[-periods-1]

            if past == 0:
                return 0

            momentum = (current - past) / past * 100
            return momentum
        except:
            return 0

    def _candle_strength(self, df: pd.DataFrame) -> float:
        """Strength of most recent candle"""
        try:
            if len(df) < 2:
                return 0

            last_candle = df.iloc[-1]
            candle_body = abs(last_candle['close'] - last_candle['open'])
            candle_range = last_candle['high'] - last_candle['low']

            if candle_range == 0:
                return 0

            # Body as % of total range (strong candle = large body)
            strength = candle_body / candle_range
            return strength
        except:
            return 0

    def _mtf_trend_agreement(self, mtf_indicators: Dict) -> float:
        """How many timeframes agree on trend direction"""
        try:
            trends = []
            for tf, indicators in mtf_indicators.items():
                macd = indicators.get('macd', 0)
                macd_signal = indicators.get('macd_signal', 0)
                trends.append(1 if macd > macd_signal else -1)

            if not trends:
                return 0

            # Percentage agreement
            bullish_count = sum(1 for t in trends if t == 1)
            bearish_count = sum(1 for t in trends if t == -1)

            max_agreement = max(bullish_count, bearish_count)
            return max_agreement / len(trends)
        except:
            return 0

    def _mtf_momentum_agreement(self, mtf_indicators: Dict) -> float:
        """How many timeframes show strong momentum"""
        try:
            strong_momentum = 0
            total = 0

            for tf, indicators in mtf_indicators.items():
                macd = indicators.get('macd', 0)
                macd_signal = indicators.get('macd_signal', 0)
                diff = abs(macd - macd_signal)

                if diff > 0.001:  # Strong momentum threshold
                    strong_momentum += 1
                total += 1

            if total == 0:
                return 0

            return strong_momentum / total
        except:
            return 0

    def _mtf_rsi_average(self, mtf_indicators: Dict) -> float:
        """Average RSI across all timeframes"""
        try:
            rsi_values = []
            for tf, indicators in mtf_indicators.items():
                rsi = indicators.get('rsi', 50)
                rsi_values.append(rsi)

            if not rsi_values:
                return 50

            return sum(rsi_values) / len(rsi_values)
        except:
            return 50

    def _count_bullish_timeframes(self, mtf_indicators: Dict) -> int:
        """Count timeframes showing bullish signals"""
        try:
            count = 0
            for tf, indicators in mtf_indicators.items():
                macd = indicators.get('macd', 0)
                macd_signal = indicators.get('macd_signal', 0)
                rsi = indicators.get('rsi', 50)

                # Bullish: MACD above signal and RSI not overbought
                if macd > macd_signal and rsi < 70:
                    count += 1

            return count
        except:
            return 0

    def _count_bearish_timeframes(self, mtf_indicators: Dict) -> int:
        """Count timeframes showing bearish signals"""
        try:
            count = 0
            for tf, indicators in mtf_indicators.items():
                macd = indicators.get('macd', 0)
                macd_signal = indicators.get('macd_signal', 0)
                rsi = indicators.get('rsi', 50)

                # Bearish: MACD below signal and RSI not oversold
                if macd < macd_signal and rsi > 30:
                    count += 1

            return count
        except:
            return 0

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names"""
        return self.feature_names
