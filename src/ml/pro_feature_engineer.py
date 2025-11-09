"""
Professional Feature Engineering for US30 Scalping
100+ features including time-of-day, volume profile, market microstructure
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List


class ProFeatureEngineer:
    """
    Advanced feature engineering for professional scalping
    
    Feature Categories:
    1. Price Action (20 features)
    2. Volume Profile (15 features)
    3. Time-of-Day (10 features)
    4. Market Microstructure (15 features)
    5. Volatility Regimes (10 features)
    6. Momentum Indicators (20 features)
    7. Support/Resistance (10 features)
    8. Order Flow Proxies (10 features)
    
    Total: 110+ features
    """
    
    def __init__(self):
        self.support_resistance_levels = []
        
    def extract_all_features(
        self,
        df: pd.DataFrame,
        current_idx: int
    ) -> Dict[str, float]:
        """
        Extract all 110+ features for a given bar
        
        Args:
            df: OHLCV DataFrame
            current_idx: Index of current bar
            
        Returns:
            Dictionary of features
        """
        features = {}
        
        # Need at least 20 bars of history (REDUCED for instant trading!)
        if current_idx < 20:
            return {}
        
        # Get recent data (use what we have, minimum 20)
        lookback = min(100, current_idx)
        recent_df = df.iloc[current_idx-lookback:current_idx+1].copy()
        current_bar = df.iloc[current_idx]
        
        # 1. PRICE ACTION FEATURES (20)
        features.update(self._price_action_features(recent_df, current_bar))
        
        # 2. VOLUME PROFILE FEATURES (15)
        features.update(self._volume_profile_features(recent_df, current_bar))
        
        # 3. TIME-OF-DAY FEATURES (10)
        features.update(self._time_features(current_bar))
        
        # 4. MARKET MICROSTRUCTURE (15)
        features.update(self._microstructure_features(recent_df, current_bar))
        
        # 5. VOLATILITY REGIME (10)
        features.update(self._volatility_features(recent_df, current_bar))
        
        # 6. MOMENTUM INDICATORS (20)
        features.update(self._momentum_features(recent_df, current_bar))
        
        # 7. SUPPORT/RESISTANCE (10)
        features.update(self._support_resistance_features(recent_df, current_bar))
        
        # 8. ORDER FLOW PROXIES (10)
        features.update(self._order_flow_features(recent_df, current_bar))
        
        return features
    
    def _price_action_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Price action patterns and candle analysis"""
        features = {}
        
        if 'close' not in df.columns or 'open' not in df.columns:
            return features
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_price = df['open'].values
        
        # Candle body and wicks
        body = abs(close[-1] - open_price[-1])
        total_range = high[-1] - low[-1]
        upper_wick = high[-1] - max(close[-1], open_price[-1])
        lower_wick = min(close[-1], open_price[-1]) - low[-1]
        
        features['body_pct'] = body / total_range if total_range > 0 else 0
        features['upper_wick_pct'] = upper_wick / total_range if total_range > 0 else 0
        features['lower_wick_pct'] = lower_wick / total_range if total_range > 0 else 0
        features['is_bullish'] = 1 if close[-1] > open_price[-1] else 0
        
        # Price position in recent range
        recent_high = high[-20:].max()
        recent_low = low[-20:].min()
        features['price_position_20'] = (close[-1] - recent_low) / (recent_high - recent_low) if (recent_high - recent_low) > 0 else 0.5
        
        recent_high_50 = high[-50:].max()
        recent_low_50 = low[-50:].min()
        features['price_position_50'] = (close[-1] - recent_low_50) / (recent_high_50 - recent_low_50) if (recent_high_50 - recent_low_50) > 0 else 0.5
        
        # Consecutive candles
        features['consecutive_bull'] = sum(1 for i in range(-5, 0) if close[i] > close[i-1])
        features['consecutive_bear'] = sum(1 for i in range(-5, 0) if close[i] < close[i-1])
        
        # Gap analysis
        features['gap_up'] = 1 if open_price[-1] > close[-2] else 0
        features['gap_down'] = 1 if open_price[-1] < close[-2] else 0
        features['gap_size'] = abs(open_price[-1] - close[-2]) / close[-2] if close[-2] > 0 else 0
        
        # Higher highs / Lower lows
        features['higher_high'] = 1 if high[-1] > high[-2] else 0
        features['lower_low'] = 1 if low[-1] < low[-2] else 0
        
        # Price momentum (rate of change)
        features['roc_1'] = (close[-1] - close[-2]) / close[-2] if close[-2] > 0 else 0
        features['roc_3'] = (close[-1] - close[-4]) / close[-4] if close[-4] > 0 else 0
        features['roc_5'] = (close[-1] - close[-6]) / close[-6] if close[-6] > 0 else 0
        features['roc_10'] = (close[-1] - close[-11]) / close[-11] if close[-11] > 0 else 0
        
        # Acceleration
        features['acceleration'] = features['roc_1'] - features['roc_3']
        
        # Range expansion/contraction
        avg_range = (high[-10:] - low[-10:]).mean()
        features['range_expansion'] = total_range / avg_range if avg_range > 0 else 1.0
        
        return features
    
    def _volume_profile_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Volume analysis and profile"""
        features = {}
        
        volume = df['tick_volume'].values
        close = df['close'].values
        
        # Volume moving averages
        features['vol_ma_5'] = volume[-5:].mean()
        features['vol_ma_10'] = volume[-10:].mean()
        features['vol_ma_20'] = volume[-20:].mean()
        
        # Volume ratios
        features['vol_ratio_5'] = volume[-1] / features['vol_ma_5'] if features['vol_ma_5'] > 0 else 1.0
        features['vol_ratio_10'] = volume[-1] / features['vol_ma_10'] if features['vol_ma_10'] > 0 else 1.0
        
        # Volume trend
        features['vol_increasing'] = 1 if volume[-1] > volume[-2] > volume[-3] else 0
        features['vol_decreasing'] = 1 if volume[-1] < volume[-2] < volume[-3] else 0
        
        # Volume spike
        vol_std = volume[-20:].std()
        features['vol_spike'] = 1 if volume[-1] > features['vol_ma_20'] + 2 * vol_std else 0
        
        # Price-volume correlation
        price_change = close[-10:] - close[-11:-1]
        vol_change = volume[-10:] - volume[-11:-1]
        features['price_vol_corr'] = np.corrcoef(price_change, vol_change)[0, 1] if len(price_change) > 1 else 0
        
        # On-balance volume proxy
        obv = np.where(close[1:] > close[:-1], volume[1:], -volume[1:]).cumsum()
        features['obv_trend'] = (obv[-1] - obv[-11]) / abs(obv[-11]) if obv[-11] != 0 else 0
        
        # Volume-weighted price
        vwap_20 = (close[-20:] * volume[-20:]).sum() / volume[-20:].sum() if volume[-20:].sum() > 0 else close[-1]
        features['price_vs_vwap'] = (close[-1] - vwap_20) / vwap_20 if vwap_20 > 0 else 0
        
        # Accumulation/Distribution proxy
        if 'open' in df.columns:
            open_price = df['open'].values
            features['buying_pressure'] = sum(1 for i in range(-10, 0) if close[i] > open_price[i] and volume[i] > features['vol_ma_10'])
            features['selling_pressure'] = sum(1 for i in range(-10, 0) if close[i] < open_price[i] and volume[i] > features['vol_ma_10'])
        else:
            features['buying_pressure'] = 0
            features['selling_pressure'] = 0
        
        return features
    
    def _time_features(self, current_bar) -> Dict:
        """Time-of-day and session awareness"""
        features = {}
        
        bar_time = current_bar['time']
        
        # Hour of day (0-23)
        hour = bar_time.hour
        minute = bar_time.minute
        
        # Cyclical encoding (sine/cosine for continuity)
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        features['minute_sin'] = np.sin(2 * np.pi * minute / 60)
        features['minute_cos'] = np.cos(2 * np.pi * minute / 60)
        
        # Trading session flags
        features['ny_session'] = 1 if 9 <= hour < 16 else 0  # 9:30 AM - 4:00 PM EST
        features['london_session'] = 1 if 3 <= hour < 12 else 0  # 3:00 AM - 12:00 PM EST
        features['asian_session'] = 1 if 18 <= hour or hour < 3 else 0
        
        # Day of week (Monday=0, Friday=4)
        dow = bar_time.weekday()
        features['is_monday'] = 1 if dow == 0 else 0
        features['is_friday'] = 1 if dow == 4 else 0
        
        # First/Last hour of NY session
        features['ny_open_hour'] = 1 if hour == 9 else 0
        features['ny_close_hour'] = 1 if hour == 15 else 0
        
        return features
    
    def _microstructure_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Market microstructure and spread analysis"""
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Bid-ask spread proxy (high-low range)
        spread = high[-10:] - low[-10:]
        features['avg_spread'] = spread.mean()
        features['spread_volatility'] = spread.std()
        features['current_spread'] = high[-1] - low[-1]
        features['spread_ratio'] = features['current_spread'] / features['avg_spread'] if features['avg_spread'] > 0 else 1.0
        
        # Price impact proxy (how much price moves per unit volume)
        price_moves = abs(close[1:] - close[:-1])
        volume_moves = df['tick_volume'].values[1:]
        features['price_impact'] = (price_moves[-10:] / volume_moves[-10:]).mean() if len(volume_moves) > 0 and volume_moves[-10:].sum() > 0 else 0
        
        # Tick direction (up ticks vs down ticks)
        up_ticks = sum(1 for i in range(-10, 0) if close[i] > close[i-1])
        features['tick_direction'] = (up_ticks - 5) / 5  # Normalized -1 to 1
        
        # Price clustering (how often price ends at round numbers)
        features['round_number'] = 1 if close[-1] % 10 == 0 or close[-1] % 5 == 0 else 0
        
        # Volatility clustering
        returns = (close[1:] - close[:-1]) / close[:-1]
        features['vol_cluster'] = returns[-10:].std() / returns[-50:].std() if returns[-50:].std() > 0 else 1.0
        
        # Mean reversion indicator
        features['distance_from_mean'] = (close[-1] - close[-20:].mean()) / close[-20:].std() if close[-20:].std() > 0 else 0
        
        # Hurst exponent proxy (trend vs mean reversion)
        lags = [2, 4, 8, 16]
        rs_values = []
        for lag in lags:
            if len(close) > lag:
                subseries = close[-lag:]
                mean_val = subseries.mean()
                deviations = subseries - mean_val
                cumsum_dev = np.cumsum(deviations)
                r = cumsum_dev.max() - cumsum_dev.min()
                s = subseries.std()
                if s > 0:
                    rs_values.append(r / s)
        
        features['hurst_proxy'] = np.mean(rs_values) if rs_values else 0.5
        
        return features
    
    def _volatility_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Volatility regime detection"""
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # ATR (Average True Range)
        tr = high[-20:] - low[-20:]
        features['atr_20'] = tr.mean()
        features['atr_50'] = (high[-50:] - low[-50:]).mean()
        features['atr_ratio'] = features['atr_20'] / features['atr_50'] if features['atr_50'] > 0 else 1.0
        
        # Historical volatility
        returns = (close[1:] - close[:-1]) / close[:-1]
        features['hvol_10'] = returns[-10:].std() * np.sqrt(252 * 390)  # Annualized
        features['hvol_20'] = returns[-20:].std() * np.sqrt(252 * 390)
        features['hvol_ratio'] = features['hvol_10'] / features['hvol_20'] if features['hvol_20'] > 0 else 1.0
        
        # Volatility regime (low/medium/high)
        vol_percentile = (features['hvol_20'] - returns[-100:].std()) / returns[-100:].std() if returns[-100:].std() > 0 else 0
        features['low_vol_regime'] = 1 if vol_percentile < -0.5 else 0
        features['high_vol_regime'] = 1 if vol_percentile > 0.5 else 0
        
        # Parkinson volatility (uses high-low range)
        hl_ratio = np.log(high[-20:] / low[-20:])
        features['parkinson_vol'] = np.sqrt((hl_ratio ** 2).sum() / (4 * len(hl_ratio) * np.log(2)))
        
        return features
    
    def _momentum_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Momentum and trend indicators"""
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Moving averages
        features['sma_5'] = close[-5:].mean()
        features['sma_10'] = close[-10:].mean()
        features['sma_20'] = close[-20:].mean()
        features['sma_50'] = close[-50:].mean()
        
        # EMA
        features['ema_5'] = pd.Series(close).ewm(span=5).mean().iloc[-1]
        features['ema_10'] = pd.Series(close).ewm(span=10).mean().iloc[-1]
        features['ema_20'] = pd.Series(close).ewm(span=20).mean().iloc[-1]
        
        # MA crossovers
        features['sma5_above_sma20'] = 1 if features['sma_5'] > features['sma_20'] else 0
        features['ema5_above_ema20'] = 1 if features['ema_5'] > features['ema_20'] else 0
        
        # Price vs MAs
        features['price_vs_sma5'] = (close[-1] - features['sma_5']) / features['sma_5'] if features['sma_5'] > 0 else 0
        features['price_vs_sma20'] = (close[-1] - features['sma_20']) / features['sma_20'] if features['sma_20'] > 0 else 0
        features['price_vs_sma50'] = (close[-1] - features['sma_50']) / features['sma_50'] if features['sma_50'] > 0 else 0
        
        # RSI
        gains = np.maximum(close[1:] - close[:-1], 0)
        losses = np.maximum(close[:-1] - close[1:], 0)
        avg_gain = gains[-14:].mean()
        avg_loss = losses[-14:].mean()
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        features['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema_12 = pd.Series(close).ewm(span=12).mean().iloc[-1]
        ema_26 = pd.Series(close).ewm(span=26).mean().iloc[-1]
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = pd.Series([features['macd']]).ewm(span=9).mean().iloc[-1]
        features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # Stochastic
        lowest_low = low[-14:].min()
        highest_high = high[-14:].max()
        features['stoch_k'] = (close[-1] - lowest_low) / (highest_high - lowest_low) * 100 if (highest_high - lowest_low) > 0 else 50
        
        # ADX (trend strength)
        # Simplified version
        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        features['trend_strength'] = abs(up_move[-14:].sum() - down_move[-14:].sum()) / (up_move[-14:].sum() + down_move[-14:].sum()) if (up_move[-14:].sum() + down_move[-14:].sum()) > 0 else 0
        
        return features
    
    def _support_resistance_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Support and resistance levels"""
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Find recent swing highs/lows
        swing_highs = []
        swing_lows = []
        
        for i in range(-50, -2):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                swing_highs.append(high[i])
            if low[i] < low[i-1] and low[i] < low[i+1]:
                swing_lows.append(low[i])
        
        # Distance to nearest support/resistance
        if swing_highs:
            nearest_resistance = min(swing_highs, key=lambda x: abs(x - close[-1]))
            features['dist_to_resistance'] = (nearest_resistance - close[-1]) / close[-1]
        else:
            features['dist_to_resistance'] = 0
        
        if swing_lows:
            nearest_support = min(swing_lows, key=lambda x: abs(x - close[-1]))
            features['dist_to_support'] = (close[-1] - nearest_support) / close[-1]
        else:
            features['dist_to_support'] = 0
        
        # Pivot points
        pivot = (high[-2] + low[-2] + close[-2]) / 3
        r1 = 2 * pivot - low[-2]
        s1 = 2 * pivot - high[-2]
        
        features['above_pivot'] = 1 if close[-1] > pivot else 0
        features['dist_to_pivot'] = (close[-1] - pivot) / pivot if pivot > 0 else 0
        features['dist_to_r1'] = (r1 - close[-1]) / close[-1]
        features['dist_to_s1'] = (close[-1] - s1) / close[-1]
        
        # Price clustering at levels
        round_levels = [int(close[-1] / 10) * 10, int(close[-1] / 50) * 50, int(close[-1] / 100) * 100]
        features['near_round_level'] = min([abs(close[-1] - level) / close[-1] for level in round_levels])
        
        return features
        return features
    
    def _order_flow_features(self, df: pd.DataFrame, current_bar) -> Dict:
        """Order flow proxies (without actual order book data)"""
        features = {}
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_price = df['open'].values
        volume = df['tick_volume'].values
        
        # Delta volume proxy (buying vs selling pressure)
        delta = []
        for i in range(-10, 0):
            if close[i] > open_price[i]:
                delta.append(volume[i])  # Buying
            else:
                delta.append(-volume[i])  # Selling
        
        features['delta_volume'] = sum(delta)
        features['cumulative_delta'] = sum(delta) / sum(abs(d) for d in delta) if sum(abs(d) for d in delta) > 0 else 0
        
        # Tape reading proxies
        features['large_buy_orders'] = sum(1 for i in range(-10, 0) if close[i] > open_price[i] and volume[i] > volume[-20:].mean() * 1.5)
        features['large_sell_orders'] = sum(1 for i in range(-10, 0) if close[i] < open_price[i] and volume[i] > volume[-20:].mean() * 1.5)
        
        # Absorption (price doesn't move despite volume)
        price_change = abs(close[-1] - close[-6])
        volume_sum = volume[-5:].sum()
        features['absorption'] = volume_sum / price_change if price_change > 0 else 0
        
        # Momentum vs volume
        momentum = close[-1] - close[-6]
        features['momentum_per_volume'] = momentum / volume[-5:].mean() if volume[-5:].mean() > 0 else 0
        
        # Imbalance detection
        up_volume = sum(volume[i] for i in range(-10, 0) if close[i] > close[i-1])
        down_volume = sum(volume[i] for i in range(-10, 0) if close[i] < close[i-1])
        features['volume_imbalance'] = (up_volume - down_volume) / (up_volume + down_volume) if (up_volume + down_volume) > 0 else 0
        
        # Exhaustion signals
        features['buying_exhaustion'] = 1 if close[-1] > close[-2] and volume[-1] < volume[-2] else 0
        features['selling_exhaustion'] = 1 if close[-1] < close[-2] and volume[-1] < volume[-2] else 0
        
        return features
