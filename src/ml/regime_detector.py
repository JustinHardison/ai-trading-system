"""
Market Regime Detection for US30
Detects trending, ranging, volatile, and quiet market conditions
AI adapts strategy based on current regime
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MarketRegime(Enum):
    """Market regime types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


class RegimeDetector:
    """
    Detects current market regime using multiple indicators

    Regimes affect trading strategy:
    - TRENDING: Follow trend, wider stops
    - RANGING: Fade extremes, tighter stops
    - HIGH_VOL: Reduce size, wider stops
    - LOW_VOL: Increase size, tighter stops
    - BREAKOUT: Enter aggressively
    - REVERSAL: Wait for confirmation
    """

    def __init__(self):
        self.current_regime = None
        self.regime_confidence = 0.0
        self.regime_duration = 0

    def detect_regime(
        self,
        df: pd.DataFrame,
        mtf_data: Dict[str, pd.DataFrame] = None
    ) -> Tuple[MarketRegime, float]:
        """
        Detect current market regime

        Args:
            df: Primary timeframe OHLCV data
            mtf_data: Multi-timeframe data for confirmation

        Returns:
            (MarketRegime, confidence_score)
        """
        if len(df) < 100:
            return MarketRegime.RANGING, 0.5

        # Calculate regime indicators
        trend_strength = self._calculate_trend_strength(df)
        volatility_level = self._calculate_volatility_level(df)
        range_strength = self._calculate_range_strength(df)
        momentum = self._calculate_momentum(df)

        # Multi-timeframe confirmation
        mtf_confirmation = 0.5
        if mtf_data:
            mtf_confirmation = self._check_mtf_alignment(mtf_data)

        # Detect regime based on indicators
        regime, confidence = self._classify_regime(
            trend_strength=trend_strength,
            volatility_level=volatility_level,
            range_strength=range_strength,
            momentum=momentum,
            mtf_confirmation=mtf_confirmation
        )

        # Update state
        if regime == self.current_regime:
            self.regime_duration += 1
        else:
            self.current_regime = regime
            self.regime_duration = 0

        self.regime_confidence = confidence

        logger.info(
            f"Regime: {regime.value} | "
            f"Confidence: {confidence:.2f} | "
            f"Duration: {self.regime_duration} bars"
        )

        return regime, confidence

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate trend strength (-1 to 1)
        -1 = strong downtrend, 0 = no trend, 1 = strong uptrend
        """
        try:
            # EMA alignment
            ema20 = df['close'].ewm(span=20).mean().iloc[-1]
            ema50 = df['close'].ewm(span=50).mean().iloc[-1]
            ema100 = df['close'].ewm(span=100).mean().iloc[-1]

            current_price = df['close'].iloc[-1]

            # Score based on EMA alignment
            if current_price > ema20 > ema50 > ema100:
                trend_score = 1.0  # Strong uptrend
            elif current_price < ema20 < ema50 < ema100:
                trend_score = -1.0  # Strong downtrend
            elif current_price > ema50 > ema100:
                trend_score = 0.7  # Moderate uptrend
            elif current_price < ema50 < ema100:
                trend_score = -0.7  # Moderate downtrend
            elif current_price > ema100:
                trend_score = 0.3  # Weak uptrend
            elif current_price < ema100:
                trend_score = -0.3  # Weak downtrend
            else:
                trend_score = 0.0  # No clear trend

            # ADX for trend strength confirmation
            adx = self._calculate_adx(df)
            if adx < 20:
                trend_score *= 0.5  # Weak trend
            elif adx > 40:
                trend_score *= 1.2  # Strong trend (but cap at ±1)

            return max(-1.0, min(1.0, trend_score))

        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 0.0

    def _calculate_volatility_level(self, df: pd.DataFrame) -> float:
        """
        Calculate volatility level (0 to 1)
        0 = low volatility, 1 = high volatility
        """
        try:
            # ATR percentile
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()

            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()

            current_atr = atr.iloc[-1]
            atr_percentile = (atr.tail(100) < current_atr).sum() / 100

            # Bollinger Band width
            sma20 = df['close'].rolling(20).mean()
            std20 = df['close'].rolling(20).std()
            bb_width = (std20.iloc[-1] * 2) / sma20.iloc[-1] if sma20.iloc[-1] > 0 else 0

            # Combine metrics
            vol_score = (atr_percentile + bb_width * 50) / 2

            return max(0.0, min(1.0, vol_score))

        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.5

    def _calculate_range_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate ranging strength (0 to 1)
        0 = not ranging, 1 = strong range
        """
        try:
            # Look at last 50 bars
            recent = df.tail(50)

            high_range = recent['high'].max()
            low_range = recent['low'].min()
            range_size = high_range - low_range

            # Count how many times price bounces off range boundaries
            touches_high = (recent['high'] >= high_range * 0.98).sum()
            touches_low = (recent['low'] <= low_range * 1.02).sum()

            bounce_ratio = (touches_high + touches_low) / len(recent)

            # Price position consistency (stays within range)
            mid_range = (high_range + low_range) / 2
            range_half = range_size / 2

            price_positions = (recent['close'] - mid_range).abs() / range_half if range_half > 0 else pd.Series([1.0])
            consistency = 1.0 - price_positions.mean()

            # Combine metrics
            range_score = (bounce_ratio + consistency) / 2

            return max(0.0, min(1.0, range_score))

        except Exception as e:
            logger.error(f"Error calculating range strength: {e}")
            return 0.0

    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """
        Calculate momentum (-1 to 1)
        -1 = strong bearish, 1 = strong bullish
        """
        try:
            # ROC (Rate of Change)
            roc_10 = (df['close'].iloc[-1] / df['close'].iloc[-10] - 1) * 100 if len(df) >= 10 else 0
            roc_20 = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1) * 100 if len(df) >= 20 else 0

            # RSI momentum
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss if loss.iloc[-1] != 0 else 100
            rsi = 100 - (100 / (1 + rs.iloc[-1]))

            rsi_momentum = (rsi - 50) / 50  # Normalize to -1 to 1

            # MACD momentum
            ema12 = df['close'].ewm(span=12).mean()
            ema26 = df['close'].ewm(span=26).mean()
            macd = ema12 - ema26
            macd_signal = macd.ewm(span=9).mean()
            macd_diff = macd.iloc[-1] - macd_signal.iloc[-1]

            macd_momentum = np.tanh(macd_diff / 100)  # Normalize

            # Combine
            momentum = (roc_10/5 + roc_20/10 + rsi_momentum + macd_momentum) / 4

            return max(-1.0, min(1.0, momentum))

        except Exception as e:
            logger.error(f"Error calculating momentum: {e}")
            return 0.0

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']

            # True Range
            high_low = high - low
            high_close = (high - close.shift()).abs()
            low_close = (low - close.shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

            # Directional Movement
            up_move = high.diff()
            down_move = -low.diff()

            plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
            minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)

            # Smooth
            atr = tr.rolling(period).mean()
            plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / atr)

            # ADX
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
            adx = dx.rolling(period).mean()

            return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0

        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
            return 0

    def _check_mtf_alignment(self, mtf_data: Dict[str, pd.DataFrame]) -> float:
        """
        Check multi-timeframe alignment
        Returns 0-1 score of how aligned timeframes are
        """
        try:
            alignments = []

            for tf, df in mtf_data.items():
                if len(df) < 50:
                    continue

                trend = self._calculate_trend_strength(df)
                alignments.append(trend)

            if not alignments:
                return 0.5

            # Check if all timeframes agree
            all_bullish = all(t > 0.3 for t in alignments)
            all_bearish = all(t < -0.3 for t in alignments)

            if all_bullish or all_bearish:
                return 0.9  # High confidence

            # Partial alignment
            avg_alignment = np.mean([abs(t) for t in alignments])
            return avg_alignment

        except Exception as e:
            logger.error(f"Error checking MTF alignment: {e}")
            return 0.5

    def _classify_regime(
        self,
        trend_strength: float,
        volatility_level: float,
        range_strength: float,
        momentum: float,
        mtf_confirmation: float
    ) -> Tuple[MarketRegime, float]:
        """Classify market regime based on indicators"""

        # Strong uptrend
        if trend_strength > 0.6 and momentum > 0.4 and volatility_level < 0.7:
            return MarketRegime.TRENDING_UP, 0.8 * mtf_confirmation

        # Strong downtrend
        if trend_strength < -0.6 and momentum < -0.4 and volatility_level < 0.7:
            return MarketRegime.TRENDING_DOWN, 0.8 * mtf_confirmation

        # Ranging market
        if range_strength > 0.6 and abs(trend_strength) < 0.3:
            return MarketRegime.RANGING, 0.7 * mtf_confirmation

        # High volatility
        if volatility_level > 0.75:
            return MarketRegime.HIGH_VOLATILITY, 0.75

        # Low volatility
        if volatility_level < 0.25:
            return MarketRegime.LOW_VOLATILITY, 0.7

        # Breakout (strong momentum + increasing volatility)
        if abs(momentum) > 0.7 and volatility_level > 0.5 and abs(trend_strength) > 0.5:
            if momentum > 0:
                return MarketRegime.BREAKOUT, 0.75
            else:
                return MarketRegime.BREAKOUT, 0.75

        # Reversal (momentum diverging from trend)
        if (trend_strength > 0.5 and momentum < -0.3) or (trend_strength < -0.5 and momentum > 0.3):
            return MarketRegime.REVERSAL, 0.65

        # Default: Ranging with low confidence
        return MarketRegime.RANGING, 0.5

    def get_regime_adjustments(self) -> Dict[str, float]:
        """
        Get trading parameter adjustments based on current regime

        Returns dict with multipliers for:
        - risk_multiplier: Position size adjustment
        - stop_multiplier: Stop loss distance adjustment
        - confidence_threshold: Minimum confidence to trade
        """
        if not self.current_regime:
            return {
                'risk_multiplier': 1.0,
                'stop_multiplier': 1.0,
                'confidence_threshold': 75.0
            }

        adjustments = {
            MarketRegime.TRENDING_UP: {
                'risk_multiplier': 1.2,  # Increase size in trends
                'stop_multiplier': 1.3,  # Wider stops
                'confidence_threshold': 55.0  # AGGRESSIVE FOR FTMO
            },
            MarketRegime.TRENDING_DOWN: {
                'risk_multiplier': 1.2,
                'stop_multiplier': 1.3,
                'confidence_threshold': 55.0  # AGGRESSIVE FOR FTMO
            },
            MarketRegime.RANGING: {
                'risk_multiplier': 0.8,  # Reduce size in ranges
                'stop_multiplier': 0.8,  # Tighter stops
                'confidence_threshold': 65.0  # LOWERED - need trades
            },
            MarketRegime.HIGH_VOLATILITY: {
                'risk_multiplier': 0.6,  # Much smaller size
                'stop_multiplier': 1.5,  # Much wider stops
                'confidence_threshold': 70.0  # LOWERED - can't avoid all vol
            },
            MarketRegime.LOW_VOLATILITY: {
                'risk_multiplier': 1.3,  # Larger size
                'stop_multiplier': 0.7,  # Tighter stops
                'confidence_threshold': 55.0  # AGGRESSIVE - best conditions
            },
            MarketRegime.BREAKOUT: {
                'risk_multiplier': 1.5,  # Aggressive sizing
                'stop_multiplier': 1.2,  # Moderate stops
                'confidence_threshold': 60.0  # LOWERED - catch breakouts
            },
            MarketRegime.REVERSAL: {
                'risk_multiplier': 0.5,  # Very cautious
                'stop_multiplier': 1.0,
                'confidence_threshold': 70.0  # LOWERED - need some reversal trades
            }
        }

        return adjustments.get(self.current_regime, {
            'risk_multiplier': 1.0,
            'stop_multiplier': 1.0,
            'confidence_threshold': 60.0  # DEFAULT LOWERED TO 60%
        })
