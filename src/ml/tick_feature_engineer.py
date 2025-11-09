"""
Tick-by-Tick Feature Engineering for US30 Scalping
Optimized for sub-second predictions on every price change
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime


class TickFeatureEngineer:
    """
    Ultra-fast feature engineering for tick-by-tick trading
    
    Features designed for 1-5 minute scalping:
    - Price momentum (last 10, 20, 50 ticks)
    - Volume surge detection
    - Spread analysis
    - Tick velocity
    - Micro support/resistance
    """
    
    def __init__(self):
        self.tick_history = []  # Store last 100 ticks for velocity calc
        self.max_history = 100
        
    def extract_tick_features(
        self,
        current_price: float,
        bid: float,
        ask: float,
        volume: float,
        m1_bars: pd.DataFrame,
        m5_bars: pd.DataFrame = None
    ) -> Dict[str, float]:
        """
        Extract features from current tick + recent M1/M5 bars
        
        Args:
            current_price: Current price
            bid: Current bid
            ask: Current ask
            volume: Current tick volume
            m1_bars: Last 50+ M1 bars
            m5_bars: Last 20+ M5 bars (optional)
            
        Returns:
            Feature dictionary
        """
        features = {}
        
        # ============================================================
        # TICK-LEVEL FEATURES (Instant)
        # ============================================================
        
        # Spread
        spread = ask - bid
        features['spread'] = spread
        features['spread_pct'] = (spread / current_price) * 100 if current_price > 0 else 0
        
        # Mid price
        mid_price = (bid + ask) / 2
        features['mid_price'] = mid_price
        
        # ============================================================
        # M1 MOMENTUM FEATURES (Last 50 bars)
        # ============================================================
        
        if len(m1_bars) >= 50:
            close = m1_bars['close'].values
            high = m1_bars['high'].values
            low = m1_bars['low'].values
            vol = m1_bars['tick_volume'].values if 'tick_volume' in m1_bars.columns else m1_bars['volume'].values
            
            # Price position in recent range
            recent_high = high[-20:].max()
            recent_low = low[-20:].min()
            range_size = recent_high - recent_low
            
            if range_size > 0:
                features['price_position'] = (current_price - recent_low) / range_size
            else:
                features['price_position'] = 0.5
            
            # Momentum indicators (fast)
            features['momentum_5'] = (close[-1] - close[-6]) / close[-6] if close[-6] > 0 else 0
            features['momentum_10'] = (close[-1] - close[-11]) / close[-11] if close[-11] > 0 else 0
            features['momentum_20'] = (close[-1] - close[-21]) / close[-21] if close[-21] > 0 else 0
            
            # Rate of change
            features['roc_3'] = (close[-1] - close[-4]) / close[-4] if close[-4] > 0 else 0
            features['roc_5'] = (close[-1] - close[-6]) / close[-6] if close[-6] > 0 else 0
            
            # Simple moving averages (fast)
            features['sma_5'] = close[-5:].mean()
            features['sma_10'] = close[-10:].mean()
            features['sma_20'] = close[-20:].mean()
            
            # Price vs SMAs
            features['price_vs_sma5'] = (current_price - features['sma_5']) / features['sma_5']
            features['price_vs_sma10'] = (current_price - features['sma_10']) / features['sma_10']
            features['price_vs_sma20'] = (current_price - features['sma_20']) / features['sma_20']
            
            # Volatility (ATR-like)
            tr = high[-20:] - low[-20:]
            features['atr_20'] = tr.mean()
            features['atr_pct'] = (features['atr_20'] / current_price) * 100
            
            # Volume analysis
            features['volume_ma_10'] = vol[-10:].mean()
            features['volume_ratio'] = vol[-1] / features['volume_ma_10'] if features['volume_ma_10'] > 0 else 1.0
            
            # Candle patterns (last 3 bars)
            features['bullish_candles'] = sum(1 for i in range(-3, 0) if close[i] > close[i-1])
            features['bearish_candles'] = sum(1 for i in range(-3, 0) if close[i] < close[i-1])
            
            # Body size (strength of last candle)
            last_body = abs(close[-1] - m1_bars['open'].values[-1])
            last_range = high[-1] - low[-1]
            features['body_ratio'] = last_body / last_range if last_range > 0 else 0
            
            # Trend strength (linear regression slope)
            x = np.arange(20)
            slope, _ = np.polyfit(x, close[-20:], 1)
            features['trend_slope'] = slope / current_price if current_price > 0 else 0
            
        else:
            # Not enough data - use defaults
            for key in ['price_position', 'momentum_5', 'momentum_10', 'momentum_20',
                       'roc_3', 'roc_5', 'sma_5', 'sma_10', 'sma_20',
                       'price_vs_sma5', 'price_vs_sma10', 'price_vs_sma20',
                       'atr_20', 'atr_pct', 'volume_ma_10', 'volume_ratio',
                       'bullish_candles', 'bearish_candles', 'body_ratio', 'trend_slope']:
                features[key] = 0.0
        
        # ============================================================
        # M5 CONTEXT FEATURES (Optional - for trend confirmation)
        # ============================================================
        
        if m5_bars is not None and len(m5_bars) >= 20:
            close_m5 = m5_bars['close'].values
            
            # M5 trend
            features['m5_momentum'] = (close_m5[-1] - close_m5[-6]) / close_m5[-6] if close_m5[-6] > 0 else 0
            features['m5_sma_20'] = close_m5[-20:].mean()
            features['m5_price_vs_sma'] = (current_price - features['m5_sma_20']) / features['m5_sma_20']
            
            # M5 volatility
            high_m5 = m5_bars['high'].values
            low_m5 = m5_bars['low'].values
            tr_m5 = high_m5[-10:] - low_m5[-10:]
            features['m5_atr'] = tr_m5.mean()
            
        else:
            features['m5_momentum'] = 0.0
            features['m5_sma_20'] = current_price
            features['m5_price_vs_sma'] = 0.0
            features['m5_atr'] = 0.0
        
        return features
    
    def extract_exit_features(
        self,
        entry_price: float,
        current_price: float,
        direction: str,
        bars_held: int,
        m1_bars: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Extract features for exit decision
        
        Args:
            entry_price: Entry price
            current_price: Current price
            direction: 'BUY' or 'SELL'
            bars_held: Number of M1 bars held
            m1_bars: Recent M1 bars
            
        Returns:
            Feature dictionary
        """
        features = {}
        
        # Profit/loss
        if direction == 'BUY':
            profit_points = current_price - entry_price
        else:  # SELL
            profit_points = entry_price - current_price
        
        profit_pct = (profit_points / entry_price) * 100 if entry_price > 0 else 0
        
        features['profit_points'] = profit_points
        features['profit_pct'] = profit_pct
        features['bars_held'] = bars_held
        
        # Time-based features
        features['held_under_3_bars'] = 1 if bars_held < 3 else 0
        features['held_3_to_10_bars'] = 1 if 3 <= bars_held < 10 else 0
        features['held_over_10_bars'] = 1 if bars_held >= 10 else 0
        
        # Momentum since entry
        if len(m1_bars) >= max(5, bars_held + 1):
            close = m1_bars['close'].values
            
            # How much has price moved since entry
            features['move_since_entry'] = (current_price - entry_price) / entry_price
            
            # Is momentum continuing?
            recent_momentum = (close[-1] - close[-min(5, len(close)-1)]) / close[-min(5, len(close)-1)]
            features['recent_momentum'] = recent_momentum
            
            # Is price reversing?
            if direction == 'BUY':
                features['is_reversing'] = 1 if recent_momentum < -0.0005 else 0
            else:
                features['is_reversing'] = 1 if recent_momentum > 0.0005 else 0
            
            # Volatility
            high = m1_bars['high'].values
            low = m1_bars['low'].values
            recent_range = (high[-5:].max() - low[-5:].min()) / entry_price
            features['recent_volatility'] = recent_range
            
        else:
            features['move_since_entry'] = 0.0
            features['recent_momentum'] = 0.0
            features['is_reversing'] = 0
            features['recent_volatility'] = 0.0
        
        return features
