"""
Live Feature Engineer - Matches 131 training features exactly
Calculates same features as ENHANCE_FEATURES_TO_143.py for live predictions
"""

import numpy as np
import pandas as pd
from datetime import datetime


class LiveFeatureEngineer:
    """
    Generates 131 features for live trading that match training data exactly
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
        self.feature_count = len(self.feature_names)  # Dynamic count from actual features
    
    def _get_feature_names(self):
        """Return exact feature names matching training data"""
        features = [
            # Base OHLCV (5)
            'open', 'high', 'low', 'close', 'volume',
            
            # Base indicators from MT5 (7)
            'rsi', 'macd', 'macd_signal', 'stoch_k', 'stoch_d',
            'sma_5', 'sma_10', 'sma_20', 'sma_50',
            
            # Base candlestick (4)
            'body_pct', 'upper_wick', 'lower_wick', 'is_bullish',
            
            # Base metrics (3)
            'atr_20', 'vol_ratio', 'price_vs_sma20',
            
            # Enhanced candlestick (9)
            'consecutive_bull', 'consecutive_bear', 'gap_up', 'gap_down', 'gap_size',
            'higher_high', 'lower_low', 'price_position_20', 'price_position_50',
            
            # Price momentum (6)
            'roc_1', 'roc_3', 'roc_5', 'roc_10', 'acceleration', 'range_expansion',
            
            # Volume features (12)
            'vol_ma_5', 'vol_ma_10', 'vol_ma_20', 'vol_ratio_5', 'vol_ratio_10',
            'vol_increasing', 'vol_decreasing', 'vol_spike', 'price_vol_corr',
            'obv_trend', 'buying_pressure', 'selling_pressure',
            
            # Time features (11)
            'hour_sin', 'hour_cos', 'minute_sin', 'minute_cos',
            'ny_session', 'london_session', 'asian_session',
            'is_monday', 'is_friday', 'ny_open_hour', 'ny_close_hour',
            
            # Volatility (8)
            'atr_50', 'atr_ratio', 'hvol_10', 'hvol_20', 'hvol_ratio',
            'low_vol_regime', 'high_vol_regime', 'parkinson_vol',
            
            # Trend (8)
            'ema_5', 'ema_10', 'ema_20', 'sma5_above_sma20', 'ema5_above_ema20',
            'price_vs_sma5', 'price_vs_sma50', 'trend_strength',
            
            # Support/Resistance (7)
            'dist_to_resistance', 'dist_to_support', 'above_pivot', 'dist_to_pivot',
            'dist_to_r1', 'dist_to_s1', 'near_round_level',
            
            # Ichimoku (8)
            'ichimoku_tenkan', 'ichimoku_kijun', 'ichimoku_senkou_a', 'ichimoku_senkou_b',
            'ichimoku_tk_cross', 'ichimoku_price_vs_cloud', 'ichimoku_cloud_thickness', 'ichimoku_cloud_color',
            
            # Fibonacci (9)
            'fib_0_dist', 'fib_236_dist', 'fib_382_dist', 'fib_500_dist',
            'fib_618_dist', 'fib_786_dist', 'fib_100_dist',
            'fib_nearest_level_dist', 'fib_near_key_level',
            
            # Pivot points (13)
            'pivot_pp', 'pivot_r1', 'pivot_r2', 'pivot_r3',
            'pivot_s1', 'pivot_s2', 'pivot_s3',
            'pivot_pp_dist', 'pivot_r1_dist', 'pivot_s1_dist',
            'pivot_above_pp', 'pivot_between_r1_pp', 'pivot_between_pp_s1',
            
            # Patterns (12)
            'pattern_doji', 'pattern_hammer', 'pattern_shooting_star',
            'pattern_bullish_engulfing', 'pattern_bearish_engulfing',
            'pattern_three_white_soldiers', 'pattern_three_black_crows',
            'pattern_morning_star', 'pattern_evening_star',
            'pattern_bullish_strength', 'pattern_bearish_strength', 'pattern_net_signal',
            
            # Advanced indicators (4)
            'williams_r', 'sar_value', 'sar_trend', 'sar_distance',
            
            # Returns and volatility (2) - Required by HTF models
            'returns', 'volatility',
            
            # HTF features (10) - MUST MATCH MODEL TRAINING
            'h1_trend', 'h1_momentum', 'h1_rsi',
            'h4_trend', 'h4_momentum', 'h4_rsi',
            'd1_trend', 'd1_momentum',
            'htf_alignment', 'htf_momentum'
        ]
        
        return features
    
    def get_feature_count(self):
        """Return number of features this engineer produces"""
        return self.feature_count
    
    def _calculate_trend(self, price_vs_sma20, price_vs_sma5):
        """
        Calculate trend value from 0.0-1.0 where:
        0.0 = strong bearish, 0.5 = neutral, 1.0 = strong bullish
        """
        avg_position = (price_vs_sma20 + price_vs_sma5) / 2.0
        
        if avg_position <= -5.0:
            return 0.0
        elif avg_position >= 5.0:
            return 1.0
        else:
            return 0.5 + (avg_position / 10.0)
    
    def _calculate_trend_from_bars(self, bars, use_completed_only=False):
        """
        Calculate trend from timeframe bars using SMA crossover and price position.
        Returns 0.0-1.0 where 0.5 is neutral.
        
        Args:
            bars: List of OHLCV bars (bars[0] is most recent)
            use_completed_only: If True, skip bars[0] (current incomplete bar)
                               This prevents HTF trends from flip-flopping due to
                               real-time price updates on incomplete bars.
        """
        if not bars or len(bars) < 21:
            return 0.5
        
        try:
            # For HTF (H1+), use completed bars only to prevent flip-flopping
            # bars[0] is the current (incomplete) bar, bars[1] is the last completed bar
            if use_completed_only:
                bars = bars[1:]  # Skip current incomplete bar
            
            if len(bars) < 20:
                return 0.5
            
            current = bars[0]
            current_close = current.get('close', 0)
            
            closes = [b.get('close', 0) for b in bars[:50] if b.get('close', 0) > 0]
            
            if len(closes) < 20:
                return 0.5
            
            sma20 = sum(closes[:20]) / 20
            sma50 = sum(closes[:50]) / 50 if len(closes) >= 50 else sma20
            
            vs_sma20 = ((current_close - sma20) / sma20 * 100) if sma20 > 0 else 0
            vs_sma50 = ((current_close - sma50) / sma50 * 100) if sma50 > 0 else 0
            
            avg_position = (vs_sma20 + vs_sma50) / 2.0
            
            if avg_position <= -5.0:
                return 0.0
            elif avg_position >= 5.0:
                return 1.0
            else:
                return 0.5 + (avg_position / 10.0)
                
        except Exception as e:
            return 0.5
    
    def _calculate_momentum_from_bars(self, bars):
        """
        Calculate momentum from timeframe bars.
        Returns -1.0 to 1.0 where 0 is neutral.
        """
        if not bars or len(bars) < 10:
            return 0.0
        
        try:
            closes = [b.get('close', 0) for b in bars[:20] if b.get('close', 0) > 0]
            
            if len(closes) < 5:
                return 0.0
            
            # Rate of change over 5 bars
            roc = (closes[0] - closes[4]) / closes[4] if closes[4] > 0 else 0
            
            # Normalize to -1 to 1 (assuming max 5% move)
            momentum = max(-1.0, min(1.0, roc / 0.05))
            
            return momentum
            
        except Exception as e:
            return 0.0
    
    def _calculate_rsi_from_bars(self, bars):
        """
        Calculate RSI from timeframe bars.
        Returns 0-100.
        """
        if not bars or len(bars) < 15:
            return 50.0
        
        try:
            closes = [b.get('close', 0) for b in bars[:20] if b.get('close', 0) > 0]
            
            if len(closes) < 15:
                return 50.0
            
            # Calculate price changes
            gains = []
            losses = []
            for i in range(len(closes) - 1):
                change = closes[i] - closes[i + 1]  # bars[0] is most recent
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            if len(gains) < 14:
                return 50.0
            
            avg_gain = sum(gains[:14]) / 14
            avg_loss = sum(losses[:14]) / 14
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            return 50.0
    
    def _calculate_volatility_from_bars(self, bars):
        """
        Calculate ATR-like volatility from timeframe bars.
        Returns volatility as a price value (not percentage).
        This is critical for stop loss calculations.
        """
        if not bars or len(bars) < 14:
            return 0.0
        
        try:
            # Calculate True Range for each bar
            true_ranges = []
            for i in range(min(14, len(bars) - 1)):
                bar = bars[i]
                prev_bar = bars[i + 1]
                
                high = bar.get('high', 0)
                low = bar.get('low', 0)
                prev_close = prev_bar.get('close', 0)
                
                if high > 0 and low > 0 and prev_close > 0:
                    tr = max(
                        high - low,
                        abs(high - prev_close),
                        abs(low - prev_close)
                    )
                    true_ranges.append(tr)
            
            if len(true_ranges) < 5:
                return 0.0
            
            # Average True Range
            atr = sum(true_ranges) / len(true_ranges)
            
            return atr
            
        except Exception as e:
            return 0.0
    
    def _calculate_adx_from_bars(self, bars, period=14):
        """
        Calculate ADX (Average Directional Index) from timeframe bars.
        ADX measures trend strength (not direction):
        - 0-20: Weak/No trend (ranging market)
        - 20-40: Moderate trend
        - 40-60: Strong trend
        - 60+: Very strong trend
        
        Returns 0-100.
        """
        if not bars or len(bars) < period + 2:
            return 25.0  # Default to weak trend
        
        try:
            plus_dm_list = []
            minus_dm_list = []
            tr_list = []
            
            for i in range(min(period + 1, len(bars) - 1)):
                bar = bars[i]
                prev_bar = bars[i + 1]
                
                high = bar.get('high', 0)
                low = bar.get('low', 0)
                prev_high = prev_bar.get('high', 0)
                prev_low = prev_bar.get('low', 0)
                prev_close = prev_bar.get('close', 0)
                
                if high == 0 or low == 0 or prev_high == 0 or prev_low == 0:
                    continue
                
                # True Range
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
                
                # Directional Movement
                plus_dm = max(0, high - prev_high) if (high - prev_high) > (prev_low - low) else 0
                minus_dm = max(0, prev_low - low) if (prev_low - low) > (high - prev_high) else 0
                
                plus_dm_list.append(plus_dm)
                minus_dm_list.append(minus_dm)
            
            if len(tr_list) < period:
                return 25.0
            
            # Smoothed averages
            atr = sum(tr_list[:period]) / period
            plus_di = (sum(plus_dm_list[:period]) / period) / atr * 100 if atr > 0 else 0
            minus_di = (sum(minus_dm_list[:period]) / period) / atr * 100 if atr > 0 else 0
            
            # DX and ADX
            di_sum = plus_di + minus_di
            dx = abs(plus_di - minus_di) / di_sum * 100 if di_sum > 0 else 0
            
            # For simplicity, return DX as ADX (proper ADX needs smoothing over time)
            return min(100, max(0, dx))
            
        except Exception as e:
            return 25.0
    
    def _calculate_volume_trend_from_bars(self, bars, period=10):
        """
        Calculate volume trend from HTF bars.
        Returns -1.0 to 1.0:
        - Positive: Volume increasing (confirms moves)
        - Negative: Volume decreasing (divergence warning)
        - Near 0: Stable volume
        """
        if not bars or len(bars) < period + 1:
            return 0.0
        
        try:
            volumes = [b.get('volume', 0) for b in bars[:period + 1] if b.get('volume', 0) > 0]
            
            if len(volumes) < period:
                return 0.0
            
            # Compare recent volume to older volume
            recent_avg = sum(volumes[:period // 2]) / (period // 2)
            older_avg = sum(volumes[period // 2:period]) / (period // 2)
            
            if older_avg == 0:
                return 0.0
            
            # Volume change ratio
            change = (recent_avg - older_avg) / older_avg
            
            # Normalize to -1 to 1 (assuming max 100% change)
            return max(-1.0, min(1.0, change))
            
        except Exception as e:
            return 0.0
    
    def _calculate_htf_volume_divergence(self, bars, period=10):
        """
        Calculate volume divergence on HTF (H4/D1).
        Divergence = price moving but volume not confirming.
        
        Returns 0.0 to 1.0:
        - 0.0: No divergence (volume confirms price)
        - 1.0: Strong divergence (price moving, volume declining)
        """
        if not bars or len(bars) < period + 1:
            return 0.0
        
        try:
            closes = [b.get('close', 0) for b in bars[:period + 1] if b.get('close', 0) > 0]
            volumes = [b.get('volume', 0) for b in bars[:period + 1] if b.get('volume', 0) > 0]
            
            if len(closes) < period or len(volumes) < period:
                return 0.0
            
            # Price direction (positive = up, negative = down)
            price_change = (closes[0] - closes[-1]) / closes[-1] if closes[-1] > 0 else 0
            
            # Volume trend
            recent_vol = sum(volumes[:period // 2]) / (period // 2)
            older_vol = sum(volumes[period // 2:]) / (period // 2)
            vol_change = (recent_vol - older_vol) / older_vol if older_vol > 0 else 0
            
            # Divergence: price moving up but volume declining, or vice versa
            if abs(price_change) > 0.005:  # Significant price move
                if (price_change > 0 and vol_change < -0.1) or (price_change < 0 and vol_change < -0.1):
                    # Price moving but volume declining = divergence
                    divergence = min(1.0, abs(vol_change) * 2)
                    return divergence
            
            return 0.0
            
        except Exception as e:
            return 0.0
    
    def _calculate_market_structure(self, bars, period=20):
        """
        Calculate market structure from HTF bars.
        Detects higher highs/higher lows (uptrend) or lower highs/lower lows (downtrend).
        
        Returns -1.0 to 1.0:
        - 1.0: Strong uptrend structure (HH + HL)
        - -1.0: Strong downtrend structure (LH + LL)
        - 0.0: No clear structure (ranging)
        """
        if not bars or len(bars) < period:
            return 0.0
        
        try:
            highs = [b.get('high', 0) for b in bars[:period] if b.get('high', 0) > 0]
            lows = [b.get('low', 0) for b in bars[:period] if b.get('low', 0) > 0]
            
            if len(highs) < 10 or len(lows) < 10:
                return 0.0
            
            # Find swing points (simplified)
            recent_high = max(highs[:5])
            older_high = max(highs[5:10])
            recent_low = min(lows[:5])
            older_low = min(lows[5:10])
            
            # Count structure signals
            hh = 1 if recent_high > older_high else 0  # Higher high
            hl = 1 if recent_low > older_low else 0    # Higher low
            lh = 1 if recent_high < older_high else 0  # Lower high
            ll = 1 if recent_low < older_low else 0    # Lower low
            
            # Uptrend: HH + HL
            # Downtrend: LH + LL
            bullish_score = (hh + hl) / 2.0
            bearish_score = (lh + ll) / 2.0
            
            return bullish_score - bearish_score
            
        except Exception as e:
            return 0.0
    
    def _calculate_support_resistance_distance(self, bars, current_price, period=50):
        """
        Calculate distance to nearest support and resistance from HTF bars.
        
        Returns tuple: (dist_to_support, dist_to_resistance) as percentages.
        """
        if not bars or len(bars) < period or current_price <= 0:
            return (0.0, 0.0)
        
        try:
            highs = [b.get('high', 0) for b in bars[:period] if b.get('high', 0) > 0]
            lows = [b.get('low', 0) for b in bars[:period] if b.get('low', 0) > 0]
            
            if len(highs) < 10 or len(lows) < 10:
                return (0.0, 0.0)
            
            # Find key levels
            resistance = max(highs)  # Recent high
            support = min(lows)      # Recent low
            
            # Distance as percentage
            dist_to_resistance = ((resistance - current_price) / current_price * 100) if current_price > 0 else 0
            dist_to_support = ((current_price - support) / current_price * 100) if current_price > 0 else 0
            
            return (max(0, dist_to_support), max(0, dist_to_resistance))
            
        except Exception as e:
            return (0.0, 0.0)
    
    def engineer_features(self, request: dict) -> dict:
        """
        Generate all 131 features from EA request
        
        Args:
            request: Dictionary from EA containing market data
            
        Returns:
            Dictionary of 131 features
        """
        try:
            # Extract data from request (EA sends 'timeframes' and 'indicators')
            timeframes = request.get('timeframes', {})
            indicators = request.get('indicators', {})
            symbol_info = request.get('symbol_info', {})
            current_price = request.get('current_price', 0)
            
            # Get current bar data from M5 timeframe
            # EA sends timeframes as LISTS of bars, not dicts!
            m5_list = timeframes.get('m5', timeframes.get('M5', []))
            m5 = m5_list[0] if isinstance(m5_list, list) and len(m5_list) > 0 else {}
            
            features = {}
            
            # ===================================================================
            # BASE OHLCV (5)
            # ===================================================================
            features['open'] = m5.get('open', current_price)
            features['high'] = m5.get('high', current_price)
            features['low'] = m5.get('low', current_price)
            features['close'] = m5.get('close', current_price)
            features['volume'] = m5.get('volume', 0)
            
            # ===================================================================
            # BASE INDICATORS FROM MT5 (9)
            # ===================================================================
            # EA sends indicators separately in 'indicators' dict
            features['rsi'] = indicators.get('rsi_14', 50)
            features['macd'] = indicators.get('macd_main', 0)
            features['macd_signal'] = indicators.get('macd_signal', 0)
            features['stoch_k'] = indicators.get('stoch_k', 50)
            features['stoch_d'] = indicators.get('stoch_d', 50)
            features['sma_5'] = indicators.get('sma_5', indicators.get('sma_20', features['close']))
            features['sma_10'] = indicators.get('sma_10', indicators.get('sma_20', features['close']))
            features['sma_20'] = indicators.get('sma_20', features['close'])
            features['sma_50'] = indicators.get('sma_50', features['close'])
            
            # ===================================================================
            # BASE CANDLESTICK (4)
            # ===================================================================
            body = abs(features['close'] - features['open'])
            range_val = features['high'] - features['low']
            
            features['body_pct'] = (body / range_val * 100) if range_val > 0 else 0
            features['upper_wick'] = ((features['high'] - max(features['open'], features['close'])) / range_val * 100) if range_val > 0 else 0
            features['lower_wick'] = ((min(features['open'], features['close']) - features['low']) / range_val * 100) if range_val > 0 else 0
            features['is_bullish'] = 1 if features['close'] > features['open'] else 0
            
            # ===================================================================
            # BASE METRICS (3)
            # ===================================================================
            features['atr_20'] = indicators.get('atr_20', indicators.get('atr_14', 0))
            features['vol_ratio'] = 1.0  # Will be calculated properly after vol_ma_20
            features['price_vs_sma20'] = ((features['close'] / features['sma_20'] - 1) * 100) if features['sma_20'] > 0 else 0
            
            # ===================================================================
            # ENHANCED CANDLESTICK (9) - Calculate from historical bars
            # ===================================================================
            # Count consecutive bullish/bearish candles
            consecutive_bull = 0
            consecutive_bear = 0
            for i, bar in enumerate(m5_list[:10] if len(m5_list) >= 10 else m5_list):
                if bar.get('close', 0) > bar.get('open', 0):
                    consecutive_bull += 1
                    if consecutive_bear == 0:  # Still counting bulls
                        continue
                    else:
                        break
                else:
                    consecutive_bear += 1
                    if consecutive_bull == 0:  # Still counting bears
                        continue
                    else:
                        break
            
            features['consecutive_bull'] = consecutive_bull if m5.get('close', 0) > m5.get('open', 0) else 0
            features['consecutive_bear'] = consecutive_bear if m5.get('close', 0) <= m5.get('open', 0) else 0
            
            # Gap detection
            prev_bar = m5_list[1] if len(m5_list) > 1 else m5
            features['gap_up'] = 1 if m5.get('open', 0) > prev_bar.get('close', 0) else 0
            features['gap_down'] = 1 if m5.get('open', 0) < prev_bar.get('close', 0) else 0
            features['gap_size'] = abs(m5.get('open', 0) - prev_bar.get('close', 0))
            features['higher_high'] = 1 if m5.get('high', 0) > prev_bar.get('high', 0) else 0
            features['lower_low'] = 1 if m5.get('low', 0) < prev_bar.get('low', 0) else 0
            
            # Price position in range (20 and 50 bars)
            if len(m5_list) >= 20:
                high_20 = max([b.get('high', 0) for b in m5_list[:20]])
                low_20 = min([b.get('low', 0) for b in m5_list[:20]])
                features['price_position_20'] = ((features['close'] - low_20) / (high_20 - low_20) * 100) if high_20 > low_20 else 50
            else:
                features['price_position_20'] = 50
                
            if len(m5_list) >= 50:
                high_50 = max([b.get('high', 0) for b in m5_list[:50]])
                low_50 = min([b.get('low', 0) for b in m5_list[:50]])
                features['price_position_50'] = ((features['close'] - low_50) / (high_50 - low_50) * 100) if high_50 > low_50 else 50
            else:
                features['price_position_50'] = 50
            
            # ===================================================================
            # PRICE MOMENTUM (6) - Calculate from historical bars
            # ===================================================================
            close_1 = m5_list[1].get('close', features['close']) if len(m5_list) > 1 else features['close']
            close_3 = m5_list[3].get('close', features['close']) if len(m5_list) > 3 else features['close']
            close_5 = m5_list[5].get('close', features['close']) if len(m5_list) > 5 else features['close']
            close_10 = m5_list[10].get('close', features['close']) if len(m5_list) > 10 else features['close']
            
            features['roc_1'] = ((features['close'] / close_1 - 1) * 100) if close_1 > 0 else 0
            features['roc_3'] = ((features['close'] / close_3 - 1) * 100) if close_3 > 0 else 0
            features['roc_5'] = ((features['close'] / close_5 - 1) * 100) if close_5 > 0 else 0
            features['roc_10'] = ((features['close'] / close_10 - 1) * 100) if close_10 > 0 else 0
            features['acceleration'] = features['roc_1'] - features['roc_3']
            
            # Range expansion
            current_range = features['high'] - features['low']
            if len(m5_list) >= 10:
                high_10 = max([b.get('high', 0) for b in m5_list[:10]])
                low_10 = min([b.get('low', 0) for b in m5_list[:10]])
                range_10 = high_10 - low_10
                features['range_expansion'] = (current_range / range_10) if range_10 > 0 else 1.0
            else:
                features['range_expansion'] = 1.0
            
            # ===================================================================
            # VOLUME FEATURES (12) - Calculate from historical bars
            # ===================================================================
            # Calculate volume moving averages from historical data
            if len(m5_list) >= 20:
                vol_5 = [b.get('volume', 0) for b in m5_list[:5]]
                vol_10 = [b.get('volume', 0) for b in m5_list[:10]]
                vol_20 = [b.get('volume', 0) for b in m5_list[:20]]
                features['vol_ma_5'] = np.mean(vol_5) if len(vol_5) > 0 else features['volume']
                features['vol_ma_10'] = np.mean(vol_10) if len(vol_10) > 0 else features['volume']
                features['vol_ma_20'] = np.mean(vol_20) if len(vol_20) > 0 else features['volume']
            else:
                features['vol_ma_5'] = features['volume']
                features['vol_ma_10'] = features['volume']
                features['vol_ma_20'] = features['volume']
            
            features['vol_ratio_5'] = features['volume'] / features['vol_ma_5'] if features['vol_ma_5'] > 0 else 1.0
            features['vol_ratio_10'] = features['volume'] / features['vol_ma_10'] if features['vol_ma_10'] > 0 else 1.0
            
            # Fix vol_ratio - calculate from vol_ma_20 (not /100)
            features['vol_ratio'] = features['volume'] / features['vol_ma_20'] if features['vol_ma_20'] > 0 else 1.0
            
            # Volume trend (increasing/decreasing)
            if len(m5_list) >= 3:
                vol_prev = m5_list[1].get('volume', features['volume'])
                features['vol_increasing'] = 1 if features['volume'] > vol_prev * 1.1 else 0
                features['vol_decreasing'] = 1 if features['volume'] < vol_prev * 0.9 else 0
            else:
                features['vol_increasing'] = 0
                features['vol_decreasing'] = 0
            
            features['vol_spike'] = 1 if features['vol_ratio_10'] > 2.0 else 0
            
            # Price-volume correlation (simplified)
            if len(m5_list) >= 10:
                prices = [b.get('close', 0) for b in m5_list[:10]]
                volumes = [b.get('volume', 0) for b in m5_list[:10]]
                if len(prices) == len(volumes) and len(prices) > 1:
                    features['price_vol_corr'] = np.corrcoef(prices, volumes)[0, 1] if not np.isnan(np.corrcoef(prices, volumes)[0, 1]) else 0
                else:
                    features['price_vol_corr'] = 0
            else:
                features['price_vol_corr'] = 0
            
            # OBV trend (simplified - based on price direction and volume)
            features['obv_trend'] = 1 if features['is_bullish'] and features['vol_increasing'] else (-1 if not features['is_bullish'] and features['vol_increasing'] else 0)
            
            # Buying/Selling pressure (based on close position in range and volume)
            close_position = ((features['close'] - features['low']) / (features['high'] - features['low'])) if (features['high'] - features['low']) > 0 else 0.5
            features['buying_pressure'] = close_position * (features['vol_ratio_10'] if features['vol_ratio_10'] > 1 else 1)
            features['selling_pressure'] = (1 - close_position) * (features['vol_ratio_10'] if features['vol_ratio_10'] > 1 else 1)
            
            # ===================================================================
            # TIME FEATURES (11)
            # ===================================================================
            now = datetime.now()
            hour = now.hour
            minute = now.minute
            day_of_week = now.weekday()
            
            features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
            features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
            features['minute_sin'] = np.sin(2 * np.pi * minute / 60)
            features['minute_cos'] = np.cos(2 * np.pi * minute / 60)
            features['ny_session'] = 1 if 13 <= hour < 21 else 0
            features['london_session'] = 1 if 7 <= hour < 15 else 0
            features['asian_session'] = 1 if hour < 7 or hour >= 21 else 0
            features['is_monday'] = 1 if day_of_week == 0 else 0
            features['is_friday'] = 1 if day_of_week == 4 else 0
            features['ny_open_hour'] = 1 if hour == 13 else 0
            features['ny_close_hour'] = 1 if hour == 20 else 0
            
            # ===================================================================
            # VOLATILITY (8)
            # ===================================================================
            features['atr_50'] = m5.get('atr_50', features['atr_20'])
            features['atr_ratio'] = features['atr_20'] / features['atr_50'] if features['atr_50'] > 0 else 1.0
            features['hvol_10'] = m5.get('hvol_10', 0.15)
            features['hvol_20'] = m5.get('hvol_20', 0.20)
            features['hvol_ratio'] = features['hvol_10'] / features['hvol_20'] if features['hvol_20'] > 0 else 1.0
            features['low_vol_regime'] = 1 if features['hvol_20'] < 0.15 else 0
            features['high_vol_regime'] = 1 if features['hvol_20'] > 0.30 else 0
            features['parkinson_vol'] = m5.get('parkinson_vol', 0)
            
            # ===================================================================
            # TREND (8)
            # ===================================================================
            features['ema_5'] = m5.get('ema_5', features['close'])
            features['ema_10'] = m5.get('ema_10', features['close'])
            features['ema_20'] = m5.get('ema_20', features['close'])
            features['sma5_above_sma20'] = 1 if features['sma_5'] > features['sma_20'] else 0
            features['ema5_above_ema20'] = 1 if features['ema_5'] > features['ema_20'] else 0
            features['price_vs_sma5'] = ((features['close'] / features['sma_5'] - 1) * 100) if features['sma_5'] > 0 else 0
            features['price_vs_sma50'] = ((features['close'] / features['sma_50'] - 1) * 100) if features['sma_50'] > 0 else 0
            features['trend_strength'] = abs(features['rsi'] - 50) / 50
            
            # ===================================================================
            # SUPPORT/RESISTANCE (7)
            # ===================================================================
            features['dist_to_resistance'] = m5.get('dist_to_resistance', 1.0)
            features['dist_to_support'] = m5.get('dist_to_support', 1.0)
            features['above_pivot'] = m5.get('above_pivot', 0)
            features['dist_to_pivot'] = m5.get('dist_to_pivot', 0.5)
            features['dist_to_r1'] = m5.get('dist_to_r1', 1.0)
            features['dist_to_s1'] = m5.get('dist_to_s1', 1.0)
            features['near_round_level'] = m5.get('near_round_level', 0)
            
            # ===================================================================
            # ICHIMOKU (8)
            # ===================================================================
            features['ichimoku_tenkan'] = m5.get('ichimoku_tenkan', features['close'])
            features['ichimoku_kijun'] = m5.get('ichimoku_kijun', features['close'])
            features['ichimoku_senkou_a'] = m5.get('ichimoku_senkou_a', features['close'])
            features['ichimoku_senkou_b'] = m5.get('ichimoku_senkou_b', features['close'])
            features['ichimoku_tk_cross'] = 1 if features['ichimoku_tenkan'] > features['ichimoku_kijun'] else 0
            features['ichimoku_price_vs_cloud'] = m5.get('ichimoku_price_vs_cloud', 0)
            features['ichimoku_cloud_thickness'] = abs(features['ichimoku_senkou_a'] - features['ichimoku_senkou_b'])
            features['ichimoku_cloud_color'] = 1 if features['ichimoku_senkou_a'] > features['ichimoku_senkou_b'] else 0
            
            # ===================================================================
            # FIBONACCI (9)
            # ===================================================================
            for level in ['0', '236', '382', '500', '618', '786', '100']:
                features[f'fib_{level}_dist'] = m5.get(f'fib_{level}_dist', 1.0)
            features['fib_nearest_level_dist'] = m5.get('fib_nearest_level_dist', 1.0)
            features['fib_near_key_level'] = m5.get('fib_near_key_level', 0)
            
            # ===================================================================
            # PIVOT POINTS (13)
            # ===================================================================
            features['pivot_pp'] = m5.get('pivot_pp', features['close'])
            features['pivot_r1'] = m5.get('pivot_r1', features['close'])
            features['pivot_r2'] = m5.get('pivot_r2', features['close'])
            features['pivot_r3'] = m5.get('pivot_r3', features['close'])
            features['pivot_s1'] = m5.get('pivot_s1', features['close'])
            features['pivot_s2'] = m5.get('pivot_s2', features['close'])
            features['pivot_s3'] = m5.get('pivot_s3', features['close'])
            features['pivot_pp_dist'] = abs(features['close'] - features['pivot_pp']) / features['close'] * 100 if features['close'] > 0 else 0
            features['pivot_r1_dist'] = abs(features['close'] - features['pivot_r1']) / features['close'] * 100 if features['close'] > 0 else 0
            features['pivot_s1_dist'] = abs(features['close'] - features['pivot_s1']) / features['close'] * 100 if features['close'] > 0 else 0
            features['pivot_above_pp'] = 1 if features['close'] > features['pivot_pp'] else 0
            features['pivot_between_r1_pp'] = 1 if features['pivot_pp'] < features['close'] < features['pivot_r1'] else 0
            features['pivot_between_pp_s1'] = 1 if features['pivot_s1'] < features['close'] < features['pivot_pp'] else 0
            
            # ===================================================================
            # PATTERNS (12)
            # ===================================================================
            features['pattern_doji'] = 1 if features['body_pct'] < 10 else 0
            features['pattern_hammer'] = m5.get('pattern_hammer', 0)
            features['pattern_shooting_star'] = m5.get('pattern_shooting_star', 0)
            features['pattern_bullish_engulfing'] = m5.get('pattern_bullish_engulfing', 0)
            features['pattern_bearish_engulfing'] = m5.get('pattern_bearish_engulfing', 0)
            features['pattern_three_white_soldiers'] = m5.get('pattern_three_white_soldiers', 0)
            features['pattern_three_black_crows'] = m5.get('pattern_three_black_crows', 0)
            features['pattern_morning_star'] = 0
            features['pattern_evening_star'] = 0
            features['pattern_bullish_strength'] = m5.get('pattern_bullish_strength', 0.5)
            features['pattern_bearish_strength'] = m5.get('pattern_bearish_strength', 0.5)
            features['pattern_net_signal'] = features['pattern_bullish_strength'] - features['pattern_bearish_strength']
            
            # ===================================================================
            # ADVANCED INDICATORS (4)
            # ===================================================================
            features['williams_r'] = m5.get('williams_r', -50)
            features['sar_value'] = m5.get('sar_value', features['close'])
            features['sar_trend'] = 1 if features['close'] > features['sma_20'] else 0
            features['sar_distance'] = abs(features['close'] - features['sma_20']) / features['close'] * 100 if features['close'] > 0 else 0
            
            # ===================================================================
            # RETURNS AND VOLATILITY (Required by HTF models)
            # ===================================================================
            # Returns: percentage change from previous close
            prev_close = m5.get('prev_close', features['close'])
            if prev_close > 0:
                features['returns'] = (features['close'] - prev_close) / prev_close * 100
            else:
                features['returns'] = 0.0
            
            # Volatility: normalized ATR (ATR / close * 100)
            features['volatility'] = (features['atr_20'] / features['close'] * 100) if features['close'] > 0 else 0.0
            
            # ===================================================================
            # DERIVED FEATURES FOR COMPREHENSIVE SCORING
            # These are calculated from the basic 131 features above
            # ===================================================================
            
            # Get multi-timeframe data
            m1_data = timeframes.get('m1', timeframes.get('M1', []))
            h1_data = timeframes.get('h1', timeframes.get('H1', []))
            h4_data = timeframes.get('h4', timeframes.get('H4', []))
            d1_data = timeframes.get('d1', timeframes.get('D1', []))
            
            # TREND ALIGNMENT - SWING TRADING (M15+ only, no M1/M5 noise)
            # Get trend from each timeframe (1.0 = bullish, 0.0 = bearish)
            # M1/M5 EXCLUDED - too noisy for swing trading decisions
            m15_data = timeframes.get('m15', timeframes.get('M15', []))
            m30_data = timeframes.get('m30', timeframes.get('M30', []))
            
            m15_trend = 1.0 if len(m15_data) > 0 and m15_data[0].get('close', 0) > m15_data[0].get('open', 0) else 0.5
            m30_trend = 1.0 if len(m30_data) > 0 and m30_data[0].get('close', 0) > m30_data[0].get('open', 0) else 0.5
            h1_trend = 1.0 if len(h1_data) > 0 and h1_data[0].get('close', 0) > h1_data[0].get('open', 0) else 0.5
            h4_trend = 1.0 if len(h4_data) > 0 and h4_data[0].get('close', 0) > h4_data[0].get('open', 0) else 0.5
            d1_trend = 1.0 if len(d1_data) > 0 and d1_data[0].get('close', 0) > d1_data[0].get('open', 0) else 0.5
            
            # Average trend across SWING timeframes only (M15, M30, H1, H4, D1)
            features['trend_alignment'] = (m15_trend + m30_trend + h1_trend + h4_trend + d1_trend) / 5.0
            
            # ACCUMULATION/DISTRIBUTION - Based on volume and price action
            # Accumulation: Price up + Volume up
            # Distribution: Price down + Volume up
            price_change = features['roc_1']  # 1-bar price change
            vol_change = features['vol_ratio_5'] - 1.0  # Volume vs MA
            
            if price_change > 0 and vol_change > 0.2:
                features['accumulation'] = min(1.0, vol_change)  # Buying pressure
                features['distribution'] = 0.0
            elif price_change < 0 and vol_change > 0.2:
                features['distribution'] = min(1.0, vol_change)  # Selling pressure
                features['accumulation'] = 0.0
            else:
                features['accumulation'] = 0.0
                features['distribution'] = 0.0
            
            # INSTITUTIONAL BARS - Bars with 2x+ average volume
            features['institutional_bars'] = 1.0 if features['vol_spike'] > 0 else 0.0
            
            # VOLUME INCREASING - Trend of volume
            features['volume_increasing'] = 1.0 if features['vol_ratio_10'] > 1.1 else 0.0
            
            # VOLUME DIVERGENCE - Price and volume moving opposite
            if (price_change > 0 and vol_change < -0.1) or (price_change < 0 and vol_change < -0.1):
                features['volume_divergence'] = 1.0
            else:
                features['volume_divergence'] = 0.0
            
            # MACD AGREEMENT ACROSS TIMEFRAMES
            # Check if MACD bullish/bearish on multiple timeframes
            macd_bullish = 1 if features['macd'] > features['macd_signal'] else 0
            features['macd_h1_h4_agree'] = macd_bullish  # Simplified - use M5 MACD as proxy
            features['macd_m1_h1_agree'] = macd_bullish
            
            # BID/ASK IMBALANCE - Use buying/selling pressure as proxy
            features['bid_ask_imbalance'] = features['buying_pressure'] - features['selling_pressure']
            
            # BID/ASK PRESSURE - Normalized buying/selling pressure (0.0-1.0)
            total_pressure = features['buying_pressure'] + features['selling_pressure']
            if total_pressure > 0:
                features['bid_pressure'] = features['buying_pressure'] / total_pressure
                features['ask_pressure'] = features['selling_pressure'] / total_pressure
            else:
                features['bid_pressure'] = 0.5
                features['ask_pressure'] = 0.5
            
            # Ensure all features are present and in correct order
            ordered_features = {}
            for name in self.feature_names:
                ordered_features[name] = features.get(name, 0)
            
            # Add derived features (not in original 131)
            ordered_features['trend_alignment'] = features.get('trend_alignment', 0.5)
            ordered_features['accumulation'] = features.get('accumulation', 0.0)
            ordered_features['distribution'] = features.get('distribution', 0.0)
            ordered_features['institutional_bars'] = features.get('institutional_bars', 0.0)
            ordered_features['volume_increasing'] = features.get('volume_increasing', 0.0)
            ordered_features['volume_divergence'] = features.get('volume_divergence', 0.0)
            ordered_features['macd_h1_h4_agree'] = features.get('macd_h1_h4_agree', 0.0)
            ordered_features['macd_m1_h1_agree'] = features.get('macd_m1_h1_agree', 0.0)
            ordered_features['bid_ask_imbalance'] = features.get('bid_ask_imbalance', 0.0)
            ordered_features['bid_pressure'] = features.get('bid_pressure', 0.5)
            ordered_features['ask_pressure'] = features.get('ask_pressure', 0.5)
            ordered_features['volume_ratio'] = features.get('vol_ratio', 1.0)
            
            # CRITICAL: Add multi-timeframe trend features (0.0-1.0 where 0.5=neutral)
            # Calculate from ACTUAL timeframe data (not same value for all!)
            m1_data = timeframes.get('m1', timeframes.get('M1', []))
            m5_data = timeframes.get('m5', timeframes.get('M5', []))
            m15_data = timeframes.get('m15', timeframes.get('M15', []))
            m30_data = timeframes.get('m30', timeframes.get('M30', []))
            h1_data = timeframes.get('h1', timeframes.get('H1', []))
            h4_data = timeframes.get('h4', timeframes.get('H4', []))
            d1_data = timeframes.get('d1', timeframes.get('D1', []))
            w1_data = timeframes.get('w1', timeframes.get('W1', []))  # Weekly data
            
            # ═══════════════════════════════════════════════════════════
            # CRITICAL: HTF TREND CALCULATION - USE COMPLETED BARS ONLY
            # 
            # For H1, H4, D1, W1: Use completed bars only (skip bars[0])
            # This prevents flip-flopping due to real-time price updates
            # on the current incomplete bar.
            # 
            # For M1, M5, M15, M30: Use current bar (more responsive)
            # These timeframes complete quickly so flip-flopping is less of an issue.
            # ═══════════════════════════════════════════════════════════
            
            # Lower timeframes: Use current bar (responsive)
            ordered_features['m1_trend'] = self._calculate_trend_from_bars(m1_data, use_completed_only=False)
            ordered_features['m5_trend'] = self._calculate_trend_from_bars(m5_data, use_completed_only=False)
            ordered_features['m15_trend'] = self._calculate_trend_from_bars(m15_data, use_completed_only=False)
            ordered_features['m30_trend'] = self._calculate_trend_from_bars(m30_data, use_completed_only=False)
            
            # Higher timeframes: Use COMPLETED bars only (stable, no flip-flopping)
            ordered_features['h1_trend'] = self._calculate_trend_from_bars(h1_data, use_completed_only=True)
            ordered_features['h4_trend'] = self._calculate_trend_from_bars(h4_data, use_completed_only=True)
            ordered_features['d1_trend'] = self._calculate_trend_from_bars(d1_data, use_completed_only=True)
            ordered_features['w1_trend'] = self._calculate_trend_from_bars(w1_data, use_completed_only=True)
            
            # HTF features for cohesive ML models (M15-D1 for consistency with decision logic)
            ordered_features['m15_momentum'] = self._calculate_momentum_from_bars(m15_data)
            ordered_features['m15_rsi'] = self._calculate_rsi_from_bars(m15_data)
            ordered_features['m30_momentum'] = self._calculate_momentum_from_bars(m30_data)
            ordered_features['m30_rsi'] = self._calculate_rsi_from_bars(m30_data)
            ordered_features['h1_momentum'] = self._calculate_momentum_from_bars(h1_data)
            ordered_features['h1_rsi'] = self._calculate_rsi_from_bars(h1_data)
            ordered_features['h4_momentum'] = self._calculate_momentum_from_bars(h4_data)
            ordered_features['h4_rsi'] = self._calculate_rsi_from_bars(h4_data)
            ordered_features['d1_momentum'] = self._calculate_momentum_from_bars(d1_data)
            ordered_features['d1_rsi'] = self._calculate_rsi_from_bars(d1_data)
            ordered_features['w1_momentum'] = self._calculate_momentum_from_bars(w1_data)  # Weekly momentum
            
            # ═══════════════════════════════════════════════════════════
            # HIERARCHICAL TIMEFRAME FEATURES (AI-powered bias cascade)
            # W1 → D1 → H4 → H1 (higher TF = more weight)
            # ═══════════════════════════════════════════════════════════
            
            w1_trend = ordered_features['w1_trend']
            d1_trend = ordered_features['d1_trend']
            h4_trend = ordered_features['h4_trend']
            h1_trend = ordered_features['h1_trend']
            
            # Hierarchical bias (weighted by timeframe importance)
            # W1: 40%, D1: 30%, H4: 20%, H1: 10%
            ordered_features['htf_bias'] = (w1_trend * 0.4 + d1_trend * 0.3 + h4_trend * 0.2 + h1_trend * 0.1)
            
            # Cascade confirmation (multiplicative - all must agree for high score)
            # Normalized to 0-1 range
            ordered_features['htf_cascade'] = (w1_trend * d1_trend * h4_trend * h1_trend) ** 0.25
            
            # Hierarchical alignment (how well lower TFs confirm higher TFs)
            # If W1 bullish (>0.5), check if D1/H4/H1 also bullish
            if w1_trend > 0.5:
                confirm_count = sum([d1_trend > 0.5, h4_trend > 0.5, h1_trend > 0.5])
            else:
                confirm_count = sum([d1_trend < 0.5, h4_trend < 0.5, h1_trend < 0.5])
            ordered_features['htf_confirmation'] = confirm_count / 3.0
            
            # Legacy alignment (for backward compatibility)
            ordered_features['htf_alignment'] = (ordered_features['h1_trend'] + ordered_features['h4_trend'] + ordered_features['d1_trend']) / 3.0
            ordered_features['htf_momentum'] = (ordered_features['h1_momentum'] + ordered_features['h4_momentum'] + ordered_features['d1_momentum']) / 3.0
            
            # CRITICAL: Calculate M15/H1/H4/D1 volatility for stop loss calculations
            # These are used by the unified trading system for dynamic stops
            # Timeframe-aligned stops: SCALP=M15/H1, DAY=H1/H4, SWING=H4/D1
            ordered_features['m15_volatility'] = self._calculate_volatility_from_bars(m15_data)
            ordered_features['h1_volatility'] = self._calculate_volatility_from_bars(h1_data)
            ordered_features['h4_volatility'] = self._calculate_volatility_from_bars(h4_data)
            ordered_features['d1_volatility'] = self._calculate_volatility_from_bars(d1_data)
            
            # ═══════════════════════════════════════════════════════════
            # NEW SWING TRADING INDICATORS (HTF-based, stable)
            # ═══════════════════════════════════════════════════════════
            
            # ADX - Trend Strength (0-100, >25 = trending, <20 = ranging)
            ordered_features['h1_adx'] = self._calculate_adx_from_bars(h1_data)
            ordered_features['h4_adx'] = self._calculate_adx_from_bars(h4_data)
            ordered_features['d1_adx'] = self._calculate_adx_from_bars(d1_data)
            ordered_features['htf_adx'] = (ordered_features['h1_adx'] + ordered_features['h4_adx'] + ordered_features['d1_adx']) / 3.0
            
            # HTF Volume Trend (-1 to 1, positive = volume increasing)
            ordered_features['h1_volume_trend'] = self._calculate_volume_trend_from_bars(h1_data)
            ordered_features['h4_volume_trend'] = self._calculate_volume_trend_from_bars(h4_data)
            ordered_features['d1_volume_trend'] = self._calculate_volume_trend_from_bars(d1_data)
            
            # HTF Volume Divergence (0 to 1, higher = more divergence = warning)
            ordered_features['h4_volume_divergence'] = self._calculate_htf_volume_divergence(h4_data)
            ordered_features['d1_volume_divergence'] = self._calculate_htf_volume_divergence(d1_data)
            
            # Market Structure (-1 to 1, positive = uptrend structure, negative = downtrend)
            ordered_features['h4_market_structure'] = self._calculate_market_structure(h4_data)
            ordered_features['d1_market_structure'] = self._calculate_market_structure(d1_data)
            
            # Support/Resistance Distance (from H4)
            current_price = features.get('close', 0)
            h4_sr = self._calculate_support_resistance_distance(h4_data, current_price)
            ordered_features['h4_dist_to_support'] = h4_sr[0]
            ordered_features['h4_dist_to_resistance'] = h4_sr[1]
            
            # D1 Support/Resistance (stronger levels)
            d1_sr = self._calculate_support_resistance_distance(d1_data, current_price)
            ordered_features['d1_dist_to_support'] = d1_sr[0]
            ordered_features['d1_dist_to_resistance'] = d1_sr[1]
            
            return ordered_features
            
        except Exception as e:
            print(f"Error in LiveFeatureEngineer: {e}")
            import traceback
            traceback.print_exc()
            # Return zeros for all features
            return {name: 0 for name in self.feature_names}
