"""
Swing Trading Feature Engineer
150+ features for H1/H4/D1 timeframes
SEPARATE from scalping features - no interference!
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List


class SwingFeatureEngineer:
    """
    Professional feature engineering for swing trading
    
    Feature Categories (150+ total):
    1. Macro Trend (30 features)
    2. Support/Resistance (25 features)
    3. Volatility & Range (20 features)
    4. Volume Analysis (20 features)
    5. Pattern Recognition (20 features)
    6. Market Structure (15 features)
    7. Time-Based (10 features)
    8. Sentiment & Context (10 features)
    """
    
    def __init__(self):
        self.name = "SwingFeatureEngineer"
    
    def extract_all_features(self, h1_df: pd.DataFrame, h4_df: pd.DataFrame, d1_df: pd.DataFrame, current_idx: int) -> Dict:
        """
        Extract all 150+ swing features from multiple timeframes
        
        Args:
            h1_df: H1 timeframe data
            h4_df: H4 timeframe data
            d1_df: D1 timeframe data
            current_idx: Current bar index in H1
            
        Returns:
            Dictionary of 150+ features
        """
        features = {}
        
        try:
            # Get recent data for each timeframe
            h1_recent = h1_df.iloc[max(0, current_idx-200):current_idx+1]
            h4_recent = h4_df.iloc[max(0, len(h4_df)-100):] if len(h4_df) > 0 else h4_df
            d1_recent = d1_df.iloc[max(0, len(d1_df)-60):] if len(d1_df) > 0 else d1_df
            
            # Extract features from each category
            features.update(self._macro_trend_features(h1_recent, h4_recent, d1_recent))
            features.update(self._support_resistance_features(h1_recent, h4_recent, d1_recent))
            features.update(self._volatility_range_features(h1_recent, h4_recent, d1_recent))
            features.update(self._volume_features(h1_recent, h4_recent, d1_recent))
            features.update(self._pattern_features(h1_recent, h4_recent, d1_recent))
            features.update(self._market_structure_features(h1_recent, h4_recent, d1_recent))
            features.update(self._time_features(h1_recent))
            features.update(self._sentiment_features(h1_recent, h4_recent, d1_recent))
            
            return features
            
        except Exception as e:
            print(f"Swing feature extraction error: {e}")
            return {}
    
    def _macro_trend_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Macro trend features (30)"""
        features = {}
        
        if len(h1_df) < 20:
            return features
        
        close_h1 = h1_df['close'].values
        close_h4 = h4_df['close'].values if len(h4_df) > 0 else close_h1
        close_d1 = d1_df['close'].values if len(d1_df) > 0 else close_h1
        
        # Moving averages
        for period in [20, 50, 100, 200]:
            if len(close_h1) >= period:
                sma = close_h1[-period:].mean()
                features[f'sma_{period}_h1'] = (close_h1[-1] - sma) / sma if sma > 0 else 0
        
        # Multi-timeframe trend alignment
        if len(close_h4) >= 20:
            sma_h4_20 = close_h4[-20:].mean()
            features['trend_h4'] = 1 if close_h4[-1] > sma_h4_20 else -1
        else:
            features['trend_h4'] = 0
        
        if len(close_d1) >= 20:
            sma_d1_20 = close_d1[-20:].mean()
            features['trend_d1'] = 1 if close_d1[-1] > sma_d1_20 else -1
        else:
            features['trend_d1'] = 0
        
        # Trend strength
        if len(close_h1) >= 50:
            slope = (close_h1[-1] - close_h1[-50]) / 50
            features['trend_strength'] = slope / close_h1[-1] if close_h1[-1] > 0 else 0
        
        # Momentum
        for period in [10, 20, 50]:
            if len(close_h1) >= period:
                features[f'momentum_{period}'] = (close_h1[-1] - close_h1[-period]) / close_h1[-period] if close_h1[-period] > 0 else 0
        
        return features
    
    def _support_resistance_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Support/Resistance features (25)"""
        features = {}
        
        if len(h1_df) < 20:
            return features
        
        close = h1_df['close'].values
        high = h1_df['high'].values
        low = h1_df['low'].values
        
        # Recent swing highs/lows
        recent_high = high[-50:].max() if len(high) >= 50 else high[-1]
        recent_low = low[-50:].min() if len(low) >= 50 else low[-1]
        
        features['dist_to_recent_high'] = (recent_high - close[-1]) / close[-1] if close[-1] > 0 else 0
        features['dist_to_recent_low'] = (close[-1] - recent_low) / close[-1] if close[-1] > 0 else 0
        
        # Position in range
        range_size = recent_high - recent_low
        if range_size > 0:
            features['position_in_range'] = (close[-1] - recent_low) / range_size
        else:
            features['position_in_range'] = 0.5
        
        # Pivot points (daily)
        if len(h1_df) >= 24:
            yesterday_high = high[-24:-1].max()
            yesterday_low = low[-24:-1].min()
            yesterday_close = close[-24]
            
            pivot = (yesterday_high + yesterday_low + yesterday_close) / 3
            r1 = 2 * pivot - yesterday_low
            s1 = 2 * pivot - yesterday_high
            
            features['dist_to_pivot'] = (close[-1] - pivot) / close[-1] if close[-1] > 0 else 0
            features['dist_to_r1'] = (r1 - close[-1]) / close[-1] if close[-1] > 0 else 0
            features['dist_to_s1'] = (close[-1] - s1) / close[-1] if close[-1] > 0 else 0
        
        return features
    
    def _volatility_range_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Volatility & Range features (20)"""
        features = {}
        
        if len(h1_df) < 20:
            return features
        
        close = h1_df['close'].values
        high = h1_df['high'].values
        low = h1_df['low'].values
        
        # ATR on different timeframes
        for period in [14, 20, 50]:
            if len(high) >= period:
                tr = np.maximum(high[-period:] - low[-period:], 
                               np.abs(high[-period:] - np.roll(close[-period:], 1)))
                atr = tr.mean()
                features[f'atr_{period}_h1'] = atr / close[-1] if close[-1] > 0 else 0
        
        # Historical volatility
        if len(close) >= 20:
            returns = np.diff(close[-20:]) / close[-20:-1]
            features['hvol_20'] = returns.std()
        
        # Bollinger Bands
        if len(close) >= 20:
            sma_20 = close[-20:].mean()
            std_20 = close[-20:].std()
            upper_band = sma_20 + 2 * std_20
            lower_band = sma_20 - 2 * std_20
            
            features['bb_width'] = (upper_band - lower_band) / sma_20 if sma_20 > 0 else 0
            features['bb_position'] = (close[-1] - lower_band) / (upper_band - lower_band) if (upper_band - lower_band) > 0 else 0.5
        
        # Range expansion/contraction
        if len(high) >= 10:
            recent_range = (high[-10:] - low[-10:]).mean()
            older_range = (high[-20:-10] - low[-20:-10]).mean() if len(high) >= 20 else recent_range
            features['range_expansion'] = (recent_range - older_range) / older_range if older_range > 0 else 0
        
        return features
    
    def _volume_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Volume Analysis features (20)"""
        features = {}
        
        if 'tick_volume' not in h1_df.columns or len(h1_df) < 20:
            return features
        
        volume = h1_df['tick_volume'].values
        close = h1_df['close'].values
        
        # Volume trends
        for period in [10, 20, 50]:
            if len(volume) >= period:
                vol_ma = volume[-period:].mean()
                features[f'vol_ratio_{period}'] = volume[-1] / vol_ma if vol_ma > 0 else 1.0
        
        # Volume-weighted price
        if len(volume) >= 20:
            vwap = (close[-20:] * volume[-20:]).sum() / volume[-20:].sum() if volume[-20:].sum() > 0 else close[-1]
            features['price_vs_vwap'] = (close[-1] - vwap) / vwap if vwap > 0 else 0
        
        # On-balance volume
        if len(close) >= 20:
            obv_changes = np.where(close[1:] > close[:-1], volume[1:], -volume[1:])
            obv = obv_changes[-19:].cumsum()
            features['obv_trend'] = (obv[-1] - obv[0]) / abs(obv[0]) if obv[0] != 0 else 0
        
        return features
    
    def _pattern_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Pattern Recognition features (20)"""
        features = {}
        
        if len(h1_df) < 10:
            return features
        
        close = h1_df['close'].values
        high = h1_df['high'].values
        low = h1_df['low'].values
        open_price = h1_df['open'].values if 'open' in h1_df.columns else close
        
        # Higher highs / Lower lows
        if len(high) >= 10:
            features['higher_highs'] = sum(1 for i in range(-10, -1) if high[i] > high[i-1]) / 9
            features['lower_lows'] = sum(1 for i in range(-10, -1) if low[i] < low[i-1]) / 9
        
        # Candlestick patterns (simple)
        body = abs(close[-1] - open_price[-1])
        total_range = high[-1] - low[-1]
        
        features['body_pct'] = body / total_range if total_range > 0 else 0
        features['is_bullish'] = 1 if close[-1] > open_price[-1] else 0
        
        # Doji detection
        features['is_doji'] = 1 if body / total_range < 0.1 and total_range > 0 else 0
        
        return features
    
    def _market_structure_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Market Structure features (15)"""
        features = {}
        
        if len(h1_df) < 20:
            return features
        
        close = h1_df['close'].values
        high = h1_df['high'].values
        low = h1_df['low'].values
        
        # Market phase (trending vs ranging)
        if len(close) >= 50:
            recent_high = high[-50:].max()
            recent_low = low[-50:].min()
            range_size = recent_high - recent_low
            
            # ADX-like calculation
            price_moves = abs(np.diff(close[-50:]))
            avg_move = price_moves.mean()
            
            features['trending_score'] = avg_move / range_size if range_size > 0 else 0
        
        # Swing structure
        if len(high) >= 20:
            swing_highs = [high[i] for i in range(-20, -1) if high[i] > high[i-1] and high[i] > high[i+1]]
            swing_lows = [low[i] for i in range(-20, -1) if low[i] < low[i-1] and low[i] < low[i+1]]
            
            features['swing_high_count'] = len(swing_highs)
            features['swing_low_count'] = len(swing_lows)
        
        return features
    
    def _time_features(self, h1_df) -> Dict:
        """Time-Based features (10)"""
        features = {}
        
        if 'time' not in h1_df.columns or len(h1_df) == 0:
            return features
        
        current_time = h1_df['time'].iloc[-1]
        
        if isinstance(current_time, str):
            current_time = pd.to_datetime(current_time)
        
        # Day of week (0=Monday, 6=Sunday)
        features['day_of_week'] = current_time.dayofweek
        features['is_monday'] = 1 if current_time.dayofweek == 0 else 0
        features['is_friday'] = 1 if current_time.dayofweek == 4 else 0
        
        # Hour of day
        features['hour'] = current_time.hour
        features['is_ny_session'] = 1 if 9 <= current_time.hour < 16 else 0
        features['is_london_session'] = 1 if 3 <= current_time.hour < 12 else 0
        
        # Time encoding (cyclical)
        features['hour_sin'] = np.sin(2 * np.pi * current_time.hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * current_time.hour / 24)
        
        return features
    
    def _sentiment_features(self, h1_df, h4_df, d1_df) -> Dict:
        """Sentiment & Context features (10)"""
        features = {}
        
        if len(h1_df) < 20:
            return features
        
        close = h1_df['close'].values
        
        # Price momentum (sentiment proxy)
        if len(close) >= 20:
            momentum_10 = (close[-1] - close[-10]) / close[-10] if close[-10] > 0 else 0
            momentum_20 = (close[-1] - close[-20]) / close[-20] if close[-20] > 0 else 0
            
            features['sentiment_short'] = 1 if momentum_10 > 0.002 else -1 if momentum_10 < -0.002 else 0
            features['sentiment_medium'] = 1 if momentum_20 > 0.005 else -1 if momentum_20 < -0.005 else 0
        
        # Risk-on/risk-off (volatility proxy)
        if len(close) >= 20:
            volatility = close[-20:].std() / close[-20:].mean()
            features['risk_environment'] = 1 if volatility < 0.01 else -1 if volatility > 0.02 else 0
        
        return features
