"""
Advanced Technical Indicators
Ichimoku, Fibonacci, Pivots, Candlestick Patterns
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class AdvancedIndicators:
    """
    Professional technical indicators missing from base system
    """
    
    @staticmethod
    def ichimoku_cloud(df: pd.DataFrame) -> Dict[str, float]:
        """
        Ichimoku Cloud - Comprehensive trend system
        
        Components:
        - Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
        - Kijun-sen (Base Line): (26-period high + 26-period low)/2
        - Senkou Span A (Leading Span A): (Conversion + Base)/2, shifted 26 ahead
        - Senkou Span B (Leading Span B): (52-period high + 52-period low)/2, shifted 26 ahead
        - Chikou Span (Lagging Span): Close shifted 26 behind
        """
        features = {}
        
        if len(df) < 52:
            return features
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Tenkan-sen (Conversion Line) - 9 period
        period9_high = pd.Series(high).rolling(9).max().values
        period9_low = pd.Series(high).rolling(9).min().values
        tenkan = (period9_high + period9_low) / 2
        
        # Kijun-sen (Base Line) - 26 period
        period26_high = pd.Series(high).rolling(26).max().values
        period26_low = pd.Series(low).rolling(26).min().values
        kijun = (period26_high + period26_low) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_a = (tenkan + kijun) / 2
        
        # Senkou Span B (Leading Span B) - 52 period
        period52_high = pd.Series(high).rolling(52).max().values
        period52_low = pd.Series(low).rolling(52).min().values
        senkou_b = (period52_high + period52_low) / 2
        
        # Current values
        features['ichimoku_tenkan'] = tenkan[-1] if not np.isnan(tenkan[-1]) else 0
        features['ichimoku_kijun'] = kijun[-1] if not np.isnan(kijun[-1]) else 0
        features['ichimoku_senkou_a'] = senkou_a[-1] if not np.isnan(senkou_a[-1]) else 0
        features['ichimoku_senkou_b'] = senkou_b[-1] if not np.isnan(senkou_b[-1]) else 0
        
        # Signals
        features['ichimoku_tk_cross'] = 1 if tenkan[-1] > kijun[-1] else -1  # Bullish/Bearish
        features['ichimoku_price_vs_cloud'] = (
            1 if close[-1] > max(senkou_a[-1], senkou_b[-1]) else
            -1 if close[-1] < min(senkou_a[-1], senkou_b[-1]) else 0
        )
        features['ichimoku_cloud_thickness'] = abs(senkou_a[-1] - senkou_b[-1])
        features['ichimoku_cloud_color'] = 1 if senkou_a[-1] > senkou_b[-1] else -1  # Green/Red
        
        return features
    
    @staticmethod
    def fibonacci_levels(df: pd.DataFrame, lookback: int = 100) -> Dict[str, float]:
        """
        Fibonacci Retracement Levels
        
        Calculates key Fibonacci levels based on recent swing high/low
        """
        features = {}
        
        # REDUCED lookback to work with smaller datasets
        actual_lookback = min(lookback, len(df))
        if actual_lookback < 20:
            return features
        
        recent = df.tail(lookback)
        high = recent['high'].max()
        low = recent['low'].min()
        diff = high - low
        current_price = df['close'].iloc[-1]
        
        # Fibonacci levels
        fib_levels = {
            'fib_0': high,
            'fib_236': high - (diff * 0.236),
            'fib_382': high - (diff * 0.382),
            'fib_500': high - (diff * 0.500),
            'fib_618': high - (diff * 0.618),
            'fib_786': high - (diff * 0.786),
            'fib_100': low
        }
        
        # Distance from each level (normalized)
        for level_name, level_price in fib_levels.items():
            features[f'{level_name}_dist'] = (current_price - level_price) / diff if diff > 0 else 0
        
        # Find nearest level
        distances = [(abs(current_price - price), name) for name, price in fib_levels.items()]
        nearest_dist, nearest_level = min(distances)
        features['fib_nearest_level_dist'] = nearest_dist / diff if diff > 0 else 0
        
        # Is price near a key level? (within 1% of range)
        threshold = diff * 0.01
        features['fib_near_key_level'] = 1 if nearest_dist < threshold else 0
        
        return features
    
    @staticmethod
    def pivot_points(df: pd.DataFrame) -> Dict[str, float]:
        """
        Pivot Points - Classic support/resistance levels
        
        Uses previous day's high, low, close to calculate:
        - Pivot Point (PP)
        - Support levels (S1, S2, S3)
        - Resistance levels (R1, R2, R3)
        """
        features = {}
        
        if len(df) < 2:
            return features
        
        # Use previous bar for pivot calculation
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        prev_close = df['close'].iloc[-2]
        current_price = df['close'].iloc[-1]
        
        # Pivot Point
        pp = (prev_high + prev_low + prev_close) / 3
        
        # Support and Resistance
        r1 = (2 * pp) - prev_low
        s1 = (2 * pp) - prev_high
        r2 = pp + (prev_high - prev_low)
        s2 = pp - (prev_high - prev_low)
        r3 = prev_high + 2 * (pp - prev_low)
        s3 = prev_low - 2 * (prev_high - pp)
        
        # Store levels
        features['pivot_pp'] = pp
        features['pivot_r1'] = r1
        features['pivot_r2'] = r2
        features['pivot_r3'] = r3
        features['pivot_s1'] = s1
        features['pivot_s2'] = s2
        features['pivot_s3'] = s3
        
        # Distance from levels (normalized by ATR)
        atr = df['high'].iloc[-20:].max() - df['low'].iloc[-20:].min()
        if atr > 0:
            features['pivot_pp_dist'] = (current_price - pp) / atr
            features['pivot_r1_dist'] = (current_price - r1) / atr
            features['pivot_s1_dist'] = (current_price - s1) / atr
        
        # Position relative to pivot
        features['pivot_above_pp'] = 1 if current_price > pp else 0
        features['pivot_between_r1_pp'] = 1 if pp < current_price < r1 else 0
        features['pivot_between_pp_s1'] = 1 if s1 < current_price < pp else 0
        
        return features
    
    @staticmethod
    def candlestick_patterns(df: pd.DataFrame) -> Dict[str, int]:
        """
        Candlestick Pattern Recognition
        
        Detects common patterns:
        - Doji, Hammer, Shooting Star
        - Engulfing (Bullish/Bearish)
        - Morning Star, Evening Star
        - Three White Soldiers, Three Black Crows
        """
        features = {}
        
        if len(df) < 3:
            return features
        
        # Get last 3 candles
        c0 = df.iloc[-1]  # Current
        c1 = df.iloc[-2]  # Previous
        c2 = df.iloc[-3]  # 2 bars ago
        
        # Candle properties
        def candle_body(candle):
            return abs(candle['close'] - candle['open'])
        
        def candle_range(candle):
            return candle['high'] - candle['low']
        
        def is_bullish(candle):
            return candle['close'] > candle['open']
        
        def is_bearish(candle):
            return candle['close'] < candle['open']
        
        def upper_wick(candle):
            return candle['high'] - max(candle['close'], candle['open'])
        
        def lower_wick(candle):
            return min(candle['close'], candle['open']) - candle['low']
        
        # DOJI - Small body, long wicks
        body_ratio = candle_body(c0) / candle_range(c0) if candle_range(c0) > 0 else 0
        features['pattern_doji'] = 1 if body_ratio < 0.1 else 0
        
        # HAMMER - Small body at top, long lower wick
        lower_wick_ratio = lower_wick(c0) / candle_range(c0) if candle_range(c0) > 0 else 0
        features['pattern_hammer'] = 1 if (lower_wick_ratio > 0.6 and body_ratio < 0.3) else 0
        
        # SHOOTING STAR - Small body at bottom, long upper wick
        upper_wick_ratio = upper_wick(c0) / candle_range(c0) if candle_range(c0) > 0 else 0
        features['pattern_shooting_star'] = 1 if (upper_wick_ratio > 0.6 and body_ratio < 0.3) else 0
        
        # BULLISH ENGULFING - Current bullish candle engulfs previous bearish
        features['pattern_bullish_engulfing'] = 1 if (
            is_bullish(c0) and is_bearish(c1) and
            c0['open'] < c1['close'] and c0['close'] > c1['open']
        ) else 0
        
        # BEARISH ENGULFING - Current bearish candle engulfs previous bullish
        features['pattern_bearish_engulfing'] = 1 if (
            is_bearish(c0) and is_bullish(c1) and
            c0['open'] > c1['close'] and c0['close'] < c1['open']
        ) else 0
        
        # THREE WHITE SOLDIERS - 3 consecutive bullish candles
        features['pattern_three_white_soldiers'] = 1 if (
            is_bullish(c0) and is_bullish(c1) and is_bullish(c2) and
            c0['close'] > c1['close'] > c2['close']
        ) else 0
        
        # THREE BLACK CROWS - 3 consecutive bearish candles
        features['pattern_three_black_crows'] = 1 if (
            is_bearish(c0) and is_bearish(c1) and is_bearish(c2) and
            c0['close'] < c1['close'] < c2['close']
        ) else 0
        
        # MORNING STAR - Bearish, small body, bullish (reversal)
        features['pattern_morning_star'] = 1 if (
            is_bearish(c2) and body_ratio < 0.3 and is_bullish(c0)
        ) else 0
        
        # EVENING STAR - Bullish, small body, bearish (reversal)
        features['pattern_evening_star'] = 1 if (
            is_bullish(c2) and body_ratio < 0.3 and is_bearish(c0)
        ) else 0
        
        # Pattern strength (sum of all patterns)
        bullish_patterns = (
            features['pattern_hammer'] +
            features['pattern_bullish_engulfing'] +
            features['pattern_three_white_soldiers'] +
            features['pattern_morning_star']
        )
        bearish_patterns = (
            features['pattern_shooting_star'] +
            features['pattern_bearish_engulfing'] +
            features['pattern_three_black_crows'] +
            features['pattern_evening_star']
        )
        
        features['pattern_bullish_strength'] = bullish_patterns
        features['pattern_bearish_strength'] = bearish_patterns
        features['pattern_net_signal'] = bullish_patterns - bearish_patterns
        
        return features
    
    @staticmethod
    def williams_r(df: pd.DataFrame, period: int = 14) -> float:
        """Williams %R - Momentum indicator"""
        if len(df) < period:
            return 0.0
        
        recent = df.tail(period)
        highest_high = recent['high'].max()
        lowest_low = recent['low'].min()
        current_close = df['close'].iloc[-1]
        
        if highest_high == lowest_low:
            return 0.0
        
        williams = ((highest_high - current_close) / (highest_high - lowest_low)) * -100
        return williams
    
    @staticmethod
    def parabolic_sar(df: pd.DataFrame, af_start: float = 0.02, af_max: float = 0.2) -> Dict[str, float]:
        """Parabolic SAR - Trend following indicator"""
        features = {}
        
        if len(df) < 5:
            return features
        
        # Simplified SAR calculation (last 5 bars)
        high = df['high'].values[-5:]
        low = df['low'].values[-5:]
        close = df['close'].values[-5:]
        
        # Determine trend
        is_uptrend = close[-1] > close[-5]
        
        if is_uptrend:
            sar = low.min()
        else:
            sar = high.max()
        
        features['sar_value'] = sar
        features['sar_trend'] = 1 if is_uptrend else -1
        features['sar_distance'] = abs(close[-1] - sar)
        
        return features
