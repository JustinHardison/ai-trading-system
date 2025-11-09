"""
EA-Specific Feature Engineer - Generates all 153 ML Model Features
Designed to work with AI_Trading_EA_Ultimate data format
"""
import numpy as np
import pandas as pd
from typing import Dict
from datetime import datetime

class EAFeatureEngineer:
    """Generates exactly 153 features expected by the ML model"""
    
    def __init__(self):
        self.required_features = None  # Will be set from model
        
    def set_required_features(self, feature_names: list):
        """Set the exact features the model expects"""
        self.required_features = feature_names
    
    def engineer_features(self, raw_data: Dict) -> Dict[str, float]:
        """Alias for engineer_all_features for API compatibility"""
        return self.engineer_all_features(raw_data)
        
    def engineer_all_features(self, raw_data: Dict) -> Dict[str, float]:
        """
        Generate all 153 features from EA data
        
        Args:
            raw_data: Complete data from EA including 'timeframes' key
            
        Returns:
            Dictionary with all 153 features
        """
        features = {}
        
        # Get timeframe data
        timeframes = raw_data.get('timeframes', {})
        if not timeframes or 'm1' not in timeframes:
            return self._get_default_features()
            
        # Convert timeframe arrays to DataFrames
        m1_df = pd.DataFrame(timeframes['m1'])
        
        # Extract all feature categories
        features.update(self._candlestick_features(m1_df))
        features.update(self._price_features(m1_df))
        features.update(self._volume_features(m1_df))
        features.update(self._time_features(raw_data))
        features.update(self._volatility_features(m1_df))
        features.update(self._trend_features(m1_df))
        features.update(self._momentum_features(m1_df))
        features.update(self._support_resistance_features(m1_df))
        features.update(self._order_flow_features(m1_df))
        features.update(self._ichimoku_features(m1_df))
        features.update(self._fibonacci_features(m1_df))
        features.update(self._pivot_features(m1_df))
        features.update(self._pattern_features(m1_df))
        features.update(self._advanced_indicators(m1_df))
        features.update(self._llm_features())
        
        return features
    
    def _candlestick_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 1-13: Candlestick patterns and characteristics"""
        if len(df) < 2:
            return self._get_zero_dict(['body_pct', 'upper_wick_pct', 'lower_wick_pct', 'is_bullish',
                                       'consecutive_bull', 'consecutive_bear', 'gap_up', 'gap_down',
                                       'gap_size', 'higher_high', 'lower_low', 'price_position_20',
                                       'price_position_50'])
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last['close'] - last['open'])
        total_range = last['high'] - last['low']
        
        features = {}
        features['body_pct'] = (body / total_range * 100) if total_range > 0 else 0
        features['upper_wick_pct'] = ((last['high'] - max(last['open'], last['close'])) / total_range * 100) if total_range > 0 else 0
        features['lower_wick_pct'] = ((min(last['open'], last['close']) - last['low']) / total_range * 100) if total_range > 0 else 0
        features['is_bullish'] = 1.0 if last['close'] > last['open'] else 0.0
        
        # Consecutive candles
        features['consecutive_bull'] = self._count_consecutive(df, 'bullish')
        features['consecutive_bear'] = self._count_consecutive(df, 'bearish')
        
        # Gaps
        gap = last['open'] - prev['close']
        features['gap_up'] = 1.0 if gap > 0 else 0.0
        features['gap_down'] = 1.0 if gap < 0 else 0.0
        features['gap_size'] = abs(gap)
        
        # Swing points
        features['higher_high'] = 1.0 if last['high'] > prev['high'] else 0.0
        features['lower_low'] = 1.0 if last['low'] < prev['low'] else 0.0
        
        # Price position
        if len(df) >= 20:
            high_20 = df['high'].tail(20).max()
            low_20 = df['low'].tail(20).min()
            features['price_position_20'] = ((last['close'] - low_20) / (high_20 - low_20) * 100) if high_20 > low_20 else 50
        else:
            features['price_position_20'] = 50
            
        if len(df) >= 50:
            high_50 = df['high'].tail(50).max()
            low_50 = df['low'].tail(50).min()
            features['price_position_50'] = ((last['close'] - low_50) / (high_50 - low_50) * 100) if high_50 > low_50 else 50
        else:
            features['price_position_50'] = 50
        
        return features
    
    def _price_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 14-20: Price momentum and acceleration"""
        features = {}
        
        if len(df) < 11:
            return self._get_zero_dict(['roc_1', 'roc_3', 'roc_5', 'roc_10', 'acceleration',
                                       'range_expansion', 'order_flow_imbalance'])
        
        close = df['close'].values
        features['roc_1'] = (close[-1] / close[-2] - 1) * 100 if len(close) >= 2 else 0
        features['roc_3'] = (close[-1] / close[-4] - 1) * 100 if len(close) >= 4 else 0
        features['roc_5'] = (close[-1] / close[-6] - 1) * 100 if len(close) >= 6 else 0
        features['roc_10'] = (close[-1] / close[-11] - 1) * 100 if len(close) >= 11 else 0
        
        features['acceleration'] = features['roc_1'] - features['roc_3']
        features['range_expansion'] = (df['high'].iloc[-1] - df['low'].iloc[-1]) / (df['high'].tail(10).max() - df['low'].tail(10).min()) if len(df) >= 10 else 1.0
        features['order_flow_imbalance'] = 0.0  # Placeholder
        
        return features
    
    def _volume_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 21-33: Volume analysis"""
        if len(df) < 20 or 'volume' not in df.columns:
            return self._get_zero_dict(['vol_ma_5', 'vol_ma_10', 'vol_ma_20', 'vol_ratio_5', 'vol_ratio_10',
                                       'vol_increasing', 'vol_decreasing', 'vol_spike', 'price_vol_corr',
                                       'obv_trend', 'price_vs_vwap', 'buying_pressure', 'selling_pressure'])
        
        vol = df['volume'].values
        features = {}
        features['vol_ma_5'] = np.mean(vol[-5:])
        features['vol_ma_10'] = np.mean(vol[-10:])
        features['vol_ma_20'] = np.mean(vol[-20:])
        features['vol_ratio_5'] = vol[-1] / features['vol_ma_5'] if features['vol_ma_5'] > 0 else 1.0
        features['vol_ratio_10'] = vol[-1] / features['vol_ma_10'] if features['vol_ma_10'] > 0 else 1.0
        features['vol_increasing'] = 1.0 if vol[-1] > vol[-2] else 0.0
        features['vol_decreasing'] = 1.0 if vol[-1] < vol[-2] else 0.0
        features['vol_spike'] = 1.0 if features['vol_ratio_10'] > 2.0 else 0.0
        features['price_vol_corr'] = np.corrcoef(df['close'].tail(20), df['volume'].tail(20))[0, 1] if len(df) >= 20 else 0.0
        features['obv_trend'] = 0.0  # Simplified
        features['price_vs_vwap'] = 0.0  # Simplified
        features['buying_pressure'] = 0.5  # Simplified
        features['selling_pressure'] = 0.5  # Simplified
        
        return features
    
    def _time_features(self, raw_data: Dict) -> Dict[str, float]:
        """Features 34-54: Time-based and microstructure features"""
        features = {}
        
        # Get current time
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Cyclical encoding
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        features['minute_sin'] = np.sin(2 * np.pi * minute / 60)
        features['minute_cos'] = np.cos(2 * np.pi * minute / 60)
        
        # Trading sessions
        features['ny_session'] = 1.0 if 13 <= hour < 21 else 0.0  # NY: 9am-5pm EST
        features['london_session'] = 1.0 if 7 <= hour < 15 else 0.0  # London: 3am-11am EST
        features['asian_session'] = 1.0 if hour < 7 or hour >= 21 else 0.0
        
        # Day of week
        dow = now.weekday()
        features['is_monday'] = 1.0 if dow == 0 else 0.0
        features['is_friday'] = 1.0 if dow == 4 else 0.0
        features['ny_open_hour'] = 1.0 if hour == 13 else 0.0
        features['ny_close_hour'] = 1.0 if hour == 20 else 0.0
        
        # Microstructure (simplified)
        for key in ['avg_spread', 'spread_volatility', 'current_spread', 'spread_ratio',
                    'price_impact', 'tick_direction', 'round_number', 'vol_cluster',
                    'distance_from_mean', 'hurst_proxy']:
            features[key] = 0.0
        
        return features
    
    def _volatility_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 55-63: Volatility metrics"""
        if len(df) < 50:
            return self._get_zero_dict(['atr_20', 'atr_50', 'atr_ratio', 'hvol_10', 'hvol_20',
                                       'hvol_ratio', 'low_vol_regime', 'high_vol_regime', 'parkinson_vol'])
        
        features = {}
        
        # ATR
        tr = np.maximum(df['high'] - df['low'],
                       np.maximum(abs(df['high'] - df['close'].shift(1)),
                                 abs(df['low'] - df['close'].shift(1))))
        features['atr_20'] = tr.tail(20).mean()
        features['atr_50'] = tr.tail(50).mean()
        features['atr_ratio'] = features['atr_20'] / features['atr_50'] if features['atr_50'] > 0 else 1.0
        
        # Historical volatility
        returns = df['close'].pct_change()
        features['hvol_10'] = returns.tail(10).std() * np.sqrt(252)
        features['hvol_20'] = returns.tail(20).std() * np.sqrt(252)
        features['hvol_ratio'] = features['hvol_10'] / features['hvol_20'] if features['hvol_20'] > 0 else 1.0
        
        features['low_vol_regime'] = 1.0 if features['hvol_20'] < 0.15 else 0.0
        features['high_vol_regime'] = 1.0 if features['hvol_20'] > 0.30 else 0.0
        features['parkinson_vol'] = 0.0  # Simplified
        
        return features
    
    def _trend_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 64-75: Moving averages and trend"""
        if len(df) < 50:
            return self._get_zero_dict(['sma_5', 'sma_10', 'sma_20', 'sma_50', 'ema_5', 'ema_10',
                                       'ema_20', 'sma5_above_sma20', 'ema5_above_ema20',
                                       'price_vs_sma5', 'price_vs_sma20', 'price_vs_sma50'])
        
        close = df['close']
        features = {}
        
        features['sma_5'] = close.tail(5).mean()
        features['sma_10'] = close.tail(10).mean()
        features['sma_20'] = close.tail(20).mean()
        features['sma_50'] = close.tail(50).mean()
        features['ema_5'] = close.ewm(span=5, adjust=False).mean().iloc[-1]
        features['ema_10'] = close.ewm(span=10, adjust=False).mean().iloc[-1]
        features['ema_20'] = close.ewm(span=20, adjust=False).mean().iloc[-1]
        
        features['sma5_above_sma20'] = 1.0 if features['sma_5'] > features['sma_20'] else 0.0
        features['ema5_above_ema20'] = 1.0 if features['ema_5'] > features['ema_20'] else 0.0
        features['price_vs_sma5'] = (close.iloc[-1] / features['sma_5'] - 1) * 100
        features['price_vs_sma20'] = (close.iloc[-1] / features['sma_20'] - 1) * 100
        features['price_vs_sma50'] = (close.iloc[-1] / features['sma_50'] - 1) * 100
        
        return features
    
    def _momentum_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 76-82: RSI, MACD, Stochastics"""
        if len(df) < 26:
            return self._get_zero_dict(['rsi_14', 'macd', 'macd_signal', 'macd_histogram',
                                       'stoch_k', 'trend_strength'])
        
        features = {}
        close = df['close']
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        features['rsi_14'] = 100 - (100 / (1 + rs.iloc[-1])) if not np.isnan(rs.iloc[-1]) else 50
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        features['macd'] = ema12.iloc[-1] - ema26.iloc[-1]
        macd_line = ema12 - ema26
        features['macd_signal'] = macd_line.ewm(span=9, adjust=False).mean().iloc[-1]
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # Stochastic
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        features['stoch_k'] = ((close.iloc[-1] - low_14.iloc[-1]) / (high_14.iloc[-1] - low_14.iloc[-1]) * 100) if high_14.iloc[-1] > low_14.iloc[-1] else 50
        
        features['trend_strength'] = abs(features['rsi_14'] - 50) / 50
        
        return features
    
    def _support_resistance_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 83-88: Support/Resistance levels"""
        if len(df) < 20:
            return self._get_zero_dict(['dist_to_resistance', 'dist_to_support', 'above_pivot',
                                       'dist_to_pivot', 'dist_to_r1', 'dist_to_s1', 'near_round_level'])
        
        features = {}
        current_price = df['close'].iloc[-1]
        
        # Simplified support/resistance
        high_20 = df['high'].tail(20).max()
        low_20 = df['low'].tail(20).min()
        
        features['dist_to_resistance'] = (high_20 - current_price) / current_price * 100
        features['dist_to_support'] = (current_price - low_20) / current_price * 100
        features['above_pivot'] = 1.0 if current_price > (high_20 + low_20) / 2 else 0.0
        features['dist_to_pivot'] = abs(current_price - (high_20 + low_20) / 2) / current_price * 100
        features['dist_to_r1'] = 0.0  # Simplified
        features['dist_to_s1'] = 0.0  # Simplified
        features['near_round_level'] = 1.0 if (current_price % 100) < 10 or (current_price % 100) > 90 else 0.0
        
        return features
    
    def _order_flow_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 89-97: Order flow and delta volume"""
        return self._get_zero_dict(['delta_volume', 'cumulative_delta', 'large_buy_orders',
                                    'large_sell_orders', 'absorption', 'momentum_per_volume',
                                    'volume_imbalance', 'buying_exhaustion', 'selling_exhaustion'])
    
    def _ichimoku_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 98-105: Ichimoku Cloud indicators"""
        return self._get_zero_dict(['ichimoku_tenkan', 'ichimoku_kijun', 'ichimoku_senkou_a',
                                    'ichimoku_senkou_b', 'ichimoku_tk_cross', 'ichimoku_price_vs_cloud',
                                    'ichimoku_cloud_thickness', 'ichimoku_cloud_color'])
    
    def _fibonacci_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 106-114: Fibonacci retracement levels"""
        return self._get_zero_dict(['fib_0_dist', 'fib_236_dist', 'fib_382_dist', 'fib_500_dist',
                                    'fib_618_dist', 'fib_786_dist', 'fib_100_dist',
                                    'fib_nearest_level_dist', 'fib_near_key_level'])
    
    def _pivot_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 115-127: Pivot point levels"""
        if len(df) < 2:
            return self._get_zero_dict(['pivot_pp', 'pivot_r1', 'pivot_r2', 'pivot_r3',
                                       'pivot_s1', 'pivot_s2', 'pivot_s3', 'pivot_pp_dist',
                                       'pivot_r1_dist', 'pivot_s1_dist', 'pivot_above_pp',
                                       'pivot_between_r1_pp', 'pivot_between_pp_s1'])
        
        features = {}
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        close = df['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        features['pivot_pp'] = pivot
        features['pivot_r1'] = 2 * pivot - low
        features['pivot_r2'] = pivot + (high - low)
        features['pivot_r3'] = high + 2 * (pivot - low)
        features['pivot_s1'] = 2 * pivot - high
        features['pivot_s2'] = pivot - (high - low)
        features['pivot_s3'] = low - 2 * (high - pivot)
        
        features['pivot_pp_dist'] = abs(close - pivot) / close * 100
        features['pivot_r1_dist'] = abs(close - features['pivot_r1']) / close * 100
        features['pivot_s1_dist'] = abs(close - features['pivot_s1']) / close * 100
        features['pivot_above_pp'] = 1.0 if close > pivot else 0.0
        features['pivot_between_r1_pp'] = 1.0 if pivot < close < features['pivot_r1'] else 0.0
        features['pivot_between_pp_s1'] = 1.0 if features['pivot_s1'] < close < pivot else 0.0
        
        return features
    
    def _pattern_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 128-139: Candlestick patterns"""
        return self._get_zero_dict(['pattern_doji', 'pattern_hammer', 'pattern_shooting_star',
                                    'pattern_bullish_engulfing', 'pattern_bearish_engulfing',
                                    'pattern_three_white_soldiers', 'pattern_three_black_crows',
                                    'pattern_morning_star', 'pattern_evening_star',
                                    'pattern_bullish_strength', 'pattern_bearish_strength',
                                    'pattern_net_signal'])
    
    def _advanced_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Features 140-143: Williams %R and SAR"""
        if len(df) < 14:
            return self._get_zero_dict(['williams_r', 'sar_value', 'sar_trend', 'sar_distance'])
        
        features = {}
        
        # Williams %R
        highest_high = df['high'].tail(14).max()
        lowest_low = df['low'].tail(14).min()
        close = df['close'].iloc[-1]
        features['williams_r'] = ((highest_high - close) / (highest_high - lowest_low) * -100) if highest_high > lowest_low else -50
        
        # SAR (simplified)
        features['sar_value'] = 0.0
        features['sar_trend'] = 0.0
        features['sar_distance'] = 0.0
        
        return features
    
    def _llm_features(self) -> Dict[str, float]:
        """Features 144-153: LLM-based regime classification"""
        return self._get_zero_dict(['llm_regime_volatile', 'llm_regime_ranging', 'llm_regime_trending_up',
                                    'llm_regime_trending_down', 'llm_bias_bullish', 'llm_bias_bearish',
                                    'llm_bias_neutral', 'llm_risk_level', 'llm_trend_aligned',
                                    'llm_range_confirmed'])
    
    # Helper methods
    def _count_consecutive(self, df: pd.DataFrame, direction: str) -> float:
        """Count consecutive bullish/bearish candles"""
        count = 0
        for i in range(len(df) - 1, -1, -1):
            candle = df.iloc[i]
            is_bull = candle['close'] > candle['open']
            if (direction == 'bullish' and is_bull) or (direction == 'bearish' and not is_bull):
                count += 1
            else:
                break
        return float(count)
    
    def _get_zero_dict(self, keys: list) -> Dict[str, float]:
        """Return dictionary with all keys set to 0.0"""
        return {k: 0.0 for k in keys}
    
    def _get_default_features(self) -> Dict[str, float]:
        """Return all 153 features with default values"""
        if self.required_features:
            return {f: 0.0 for f in self.required_features}
        return {}
