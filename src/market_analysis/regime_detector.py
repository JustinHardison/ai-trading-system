"""
Market Regime Detector
Detects if market is trending, ranging, or high volatility
Critical for adaptive strategy selection
"""
import numpy as np
import pandas as pd
from typing import Dict, Literal
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarketRegime:
    """Market regime classification"""
    regime: Literal['STRONG_TREND', 'WEAK_TREND', 'RANGE', 'HIGH_VOLATILITY', 'LOW_VOLATILITY']
    confidence: float
    trend_strength: float  # -1 to 1 (bearish to bullish)
    volatility_percentile: float  # 0 to 100
    adr_multiple: float  # Current range vs average daily range
    reasoning: str


class RegimeDetector:
    """
    Detects market regime to adapt trading strategy
    """

    def __init__(self):
        self.lookback_days = 20

    def detect_regime(self, df: pd.DataFrame) -> MarketRegime:
        """
        Detect current market regime

        Args:
            df: OHLCV data with at least 100 bars

        Returns:
            MarketRegime with classification and metrics
        """
        if len(df) < 100:
            return MarketRegime(
                regime='RANGE',
                confidence=0.5,
                trend_strength=0.0,
                volatility_percentile=50.0,
                adr_multiple=1.0,
                reasoning="Insufficient data for regime detection"
            )

        # Calculate regime metrics
        trend_strength = self._calculate_trend_strength(df)
        volatility_pct = self._calculate_volatility_percentile(df)
        adr_multiple = self._calculate_adr_multiple(df)
        range_efficiency = self._calculate_range_efficiency(df)

        # Classify regime
        regime, confidence, reasoning = self._classify_regime(
            trend_strength, volatility_pct, adr_multiple, range_efficiency
        )

        logger.info(f"Regime: {regime} ({confidence:.1%}), Trend: {trend_strength:.2f}, "
                   f"Volatility: {volatility_pct:.0f}%ile, ADR: {adr_multiple:.2f}x")

        return MarketRegime(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_percentile=volatility_pct,
            adr_multiple=adr_multiple,
            reasoning=reasoning
        )

    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """
        Calculate trend strength using ADX and price action
        Returns: -1 (strong down) to +1 (strong up)
        """
        # Use last 20 bars
        close = df['close'].tail(20)

        # Calculate directional movement
        highs = df['high'].tail(20)
        lows = df['low'].tail(20)

        # Simple trend strength: regression slope normalized
        x = np.arange(len(close))
        slope, _ = np.polyfit(x, close, 1)

        # Normalize by price
        avg_price = close.mean()
        normalized_slope = (slope / avg_price) * 100  # Percent per bar

        # Clamp to -1 to 1
        trend_strength = np.clip(normalized_slope * 10, -1, 1)

        return float(trend_strength)

    def _calculate_volatility_percentile(self, df: pd.DataFrame) -> float:
        """
        Calculate current volatility as percentile of historical volatility
        Returns: 0 to 100
        """
        # Calculate ATR for last 100 bars
        high = df['high'].tail(100)
        low = df['low'].tail(100)
        close = df['close'].tail(100)

        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - close.shift(1)),
                np.abs(low - close.shift(1))
            )
        )

        atr = tr.rolling(14).mean()
        current_atr = atr.iloc[-1]

        # Calculate percentile
        percentile = (atr < current_atr).sum() / len(atr) * 100

        return float(percentile)

    def _calculate_adr_multiple(self, df: pd.DataFrame) -> float:
        """
        Calculate current range as multiple of average daily range
        Returns: ratio (1.0 = average, 2.0 = double average)
        """
        # Get last 20 days
        daily = df.tail(20 * 24) if len(df) > 20 * 24 else df  # Assume hourly data

        # Calculate daily ranges
        daily_high = daily['high'].resample('D').max()
        daily_low = daily['low'].resample('D').min()
        daily_ranges = daily_high - daily_low

        if len(daily_ranges) < 2:
            return 1.0

        avg_daily_range = daily_ranges.mean()
        current_range = daily['high'].tail(24).max() - daily['low'].tail(24).min()

        if avg_daily_range == 0:
            return 1.0

        return float(current_range / avg_daily_range)

    def _calculate_range_efficiency(self, df: pd.DataFrame) -> float:
        """
        Calculate how efficiently price moved (straight line vs zigzag)
        Returns: 0 (choppy) to 1 (trending)
        """
        close = df['close'].tail(20)

        if len(close) < 2:
            return 0.5

        # Net movement
        net_move = abs(close.iloc[-1] - close.iloc[0])

        # Total movement (sum of all moves)
        total_move = abs(close.diff()).sum()

        if total_move == 0:
            return 0.0

        efficiency = net_move / total_move

        return float(efficiency)

    def _classify_regime(
        self,
        trend_strength: float,
        volatility_pct: float,
        adr_multiple: float,
        range_efficiency: float
    ) -> tuple[Literal['STRONG_TREND', 'WEAK_TREND', 'RANGE', 'HIGH_VOLATILITY', 'LOW_VOLATILITY'], float, str]:
        """
        Classify regime based on metrics
        """
        # High volatility overrides everything
        if volatility_pct > 80:
            return 'HIGH_VOLATILITY', 0.9, f"Volatility at {volatility_pct:.0f}th percentile. High risk environment."

        # Low volatility
        if volatility_pct < 20:
            return 'LOW_VOLATILITY', 0.8, f"Volatility at {volatility_pct:.0f}th percentile. Tight ranges expected."

        # Strong trend: high efficiency + strong directional movement
        if range_efficiency > 0.6 and abs(trend_strength) > 0.5:
            direction = "bullish" if trend_strength > 0 else "bearish"
            return 'STRONG_TREND', 0.85, f"Strong {direction} trend. Efficiency: {range_efficiency:.2f}, Strength: {trend_strength:.2f}"

        # Weak trend: some efficiency but not strong
        if range_efficiency > 0.4 and abs(trend_strength) > 0.2:
            direction = "bullish" if trend_strength > 0 else "bearish"
            return 'WEAK_TREND', 0.7, f"Weak {direction} trend forming. Efficiency: {range_efficiency:.2f}"

        # Range: low efficiency, weak trend
        return 'RANGE', 0.75, f"Ranging market. Low efficiency: {range_efficiency:.2f}, ADR: {adr_multiple:.2f}x"

    def get_regime_adjusted_params(self, regime: MarketRegime) -> Dict:
        """
        Get trading parameters adjusted for current regime
        """
        params = {
            'position_size_multiplier': 1.0,
            'stop_loss_multiplier': 1.0,
            'take_profit_multiplier': 1.0,
            'max_positions': 3,
            'scan_frequency_minutes': 5,
            'min_ml_confidence': 70.0
        }

        if regime.regime == 'STRONG_TREND':
            # Trend following: larger positions, wider stops, let it run
            params.update({
                'position_size_multiplier': 1.3,
                'stop_loss_multiplier': 1.2,
                'take_profit_multiplier': 1.5,
                'max_positions': 4,
                'scan_frequency_minutes': 5,
                'min_ml_confidence': 65.0
            })

        elif regime.regime == 'WEAK_TREND':
            # Normal trending: standard params
            params.update({
                'position_size_multiplier': 1.0,
                'stop_loss_multiplier': 1.0,
                'take_profit_multiplier': 1.2,
                'max_positions': 3,
                'scan_frequency_minutes': 5,
                'min_ml_confidence': 70.0
            })

        elif regime.regime == 'RANGE':
            # Mean reversion: smaller positions, tighter stops
            params.update({
                'position_size_multiplier': 0.7,
                'stop_loss_multiplier': 0.8,
                'take_profit_multiplier': 0.8,
                'max_positions': 2,
                'scan_frequency_minutes': 10,
                'min_ml_confidence': 75.0
            })

        elif regime.regime == 'HIGH_VOLATILITY':
            # High vol: much smaller positions, wider stops
            params.update({
                'position_size_multiplier': 0.5,
                'stop_loss_multiplier': 1.5,
                'take_profit_multiplier': 1.3,
                'max_positions': 2,
                'scan_frequency_minutes': 15,
                'min_ml_confidence': 80.0
            })

        elif regime.regime == 'LOW_VOLATILITY':
            # Low vol: tighter everything
            params.update({
                'position_size_multiplier': 0.8,
                'stop_loss_multiplier': 0.7,
                'take_profit_multiplier': 0.9,
                'max_positions': 3,
                'scan_frequency_minutes': 5,
                'min_ml_confidence': 70.0
            })

        return params
