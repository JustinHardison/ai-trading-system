"""
Enhanced Multi-Timeframe Feature Engineer
Generates 100+ features from ALL MT5 data (M1, H1, H4 + indicators + volume + order book)
Backward compatible - can still generate 27 features if needed
"""
import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class SimpleFeatureEngineer:
    """Enhanced feature engineer - uses all 1,750+ data points from MT5"""
    
    def __init__(self, enhanced_mode=True):
        """
        Args:
            enhanced_mode: If True, generate 100+ features. If False, generate 27 (backward compatible)
        """
        self.enhanced_mode = enhanced_mode
        self.feature_names = [
            'returns', 'log_returns', 'sma_5', 'price_to_sma_5', 'sma_10', 
            'price_to_sma_10', 'sma_20', 'price_to_sma_20', 'sma_50', 
            'price_to_sma_50', 'sma_100', 'price_to_sma_100', 'volatility_10', 
            'volatility_20', 'rsi', 'macd', 'macd_signal', 'bb_upper', 
            'bb_lower', 'bb_position', 'volume_sma_20', 'volume_ratio', 
            'momentum_5', 'momentum_10', 'momentum_20', 'high_low_ratio', 
            'close_position'
        ]
        logger.info(f"✨ Feature Engineer initialized (Enhanced: {enhanced_mode})")
        
    def engineer_features(self, raw_data: Dict) -> Dict[str, float]:
        """
        Generate features from EA data.
        
        If enhanced_mode=True: 100+ features from all timeframes
        If enhanced_mode=False: 27 features from M1 only (backward compatible)
        
        Args:
            raw_data: Complete data from EA including 'timeframes' key
            
        Returns:
            Dictionary with features
        """
        if self.enhanced_mode:
            return self._engineer_enhanced_features(raw_data)
        else:
            return self._engineer_simple_features(raw_data)
    
    def _engineer_simple_features(self, raw_data: Dict) -> Dict[str, float]:
        """Original 27 features from M1 only (backward compatible)."""
        # Get M1 timeframe data
        timeframes = raw_data.get('timeframes', {})
        if not timeframes or 'm1' not in timeframes:
            return self._get_default_features()
            
        # Convert to DataFrame
        m1_data = timeframes['m1']
        if not isinstance(m1_data, list) or len(m1_data) < 100:
            return self._get_default_features()
            
        df = pd.DataFrame(m1_data)
        
        # Ensure required columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return self._get_default_features()
        
        try:
            features = {}
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values
            
            # 1-2: Returns
            features['returns'] = (close[-1] - close[-2]) / close[-2] if len(close) > 1 else 0.0
            features['log_returns'] = np.log(close[-1] / close[-2]) if len(close) > 1 and close[-2] > 0 else 0.0
            
            # 3-12: SMAs and price ratios
            features['sma_5'] = np.mean(close[-5:]) if len(close) >= 5 else close[-1]
            features['price_to_sma_5'] = close[-1] / features['sma_5'] if features['sma_5'] > 0 else 1.0
            
            features['sma_10'] = np.mean(close[-10:]) if len(close) >= 10 else close[-1]
            features['price_to_sma_10'] = close[-1] / features['sma_10'] if features['sma_10'] > 0 else 1.0
            
            features['sma_20'] = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
            features['price_to_sma_20'] = close[-1] / features['sma_20'] if features['sma_20'] > 0 else 1.0
            
            features['sma_50'] = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
            features['price_to_sma_50'] = close[-1] / features['sma_50'] if features['sma_50'] > 0 else 1.0
            
            features['sma_100'] = np.mean(close[-100:]) if len(close) >= 100 else close[-1]
            features['price_to_sma_100'] = close[-1] / features['sma_100'] if features['sma_100'] > 0 else 1.0
            
            # 13-14: Volatility
            features['volatility_10'] = np.std(close[-10:]) if len(close) >= 10 else 0.0
            features['volatility_20'] = np.std(close[-20:]) if len(close) >= 20 else 0.0
            
            # 15: RSI
            features['rsi'] = self._calculate_rsi(close, period=14)
            
            # 16-17: MACD
            macd, signal = self._calculate_macd(close)
            features['macd'] = macd
            features['macd_signal'] = signal
            
            # 18-20: Bollinger Bands
            bb_upper, bb_lower, bb_position = self._calculate_bollinger_bands(close, period=20)
            features['bb_upper'] = bb_upper
            features['bb_lower'] = bb_lower
            features['bb_position'] = bb_position
            
            # 21-22: Volume
            features['volume_sma_20'] = np.mean(volume[-20:]) if len(volume) >= 20 else volume[-1]
            features['volume_ratio'] = volume[-1] / features['volume_sma_20'] if features['volume_sma_20'] > 0 else 1.0
            
            # 23-25: Momentum
            features['momentum_5'] = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 and close[-5] > 0 else 0.0
            features['momentum_10'] = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 and close[-10] > 0 else 0.0
            features['momentum_20'] = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 and close[-20] > 0 else 0.0
            
            # 26: High/Low ratio
            features['high_low_ratio'] = high[-1] / low[-1] if low[-1] > 0 else 1.0
            
            # 27: Close position (where close is within the bar range)
            bar_range = high[-1] - low[-1]
            features['close_position'] = (close[-1] - low[-1]) / bar_range if bar_range > 0 else 0.5
            
            return features
            
        except Exception as e:
            print(f"Error calculating features: {e}")
            return self._get_default_features()
    
    def _calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
            
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate MACD"""
        if len(prices) < slow:
            return 0.0, 0.0
        
        # Simple EMA calculation
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        macd_line = ema_fast - ema_slow
        
        # Signal line (EMA of MACD)
        signal_line = macd_line  # Simplified
        
        return macd_line, signal_line
    
    def _ema(self, prices, period):
        """Calculate EMA"""
        if len(prices) < period:
            return np.mean(prices)
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def _calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return prices[-1], prices[-1], 0.5
        
        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        # Position within bands (0 = at lower, 1 = at upper)
        if upper > lower:
            position = (prices[-1] - lower) / (upper - lower)
        else:
            position = 0.5
        
        return upper, lower, position
    
    def _get_default_features(self) -> Dict[str, float]:
        """Return all 27 features with default values"""
        return {name: 0.0 for name in self.feature_names}

    def _engineer_enhanced_features(self, raw_data: Dict) -> Dict[str, float]:
        """
        Enhanced feature extraction using ALL MT5 data.
        Generates 159+ features from ALL 7 timeframes (M1, M5, M15, M30, H1, H4, D1) + indicators + volume + order book.
        """
        features = {}
        
        try:
            # Start with original 27 features from M1
            features.update(self._engineer_simple_features(raw_data))
            
            # Add ALL timeframe features (M5, M15, M30, H1, H4, D1)
            # Each timeframe contributes 15 features
            features.update(self._extract_timeframe_features(raw_data, 'm5', 'M5'))
            features.update(self._extract_timeframe_features(raw_data, 'm15', 'M15'))
            features.update(self._extract_timeframe_features(raw_data, 'm30', 'M30'))
            features.update(self._extract_timeframe_features(raw_data, 'h1', 'H1'))
            features.update(self._extract_timeframe_features(raw_data, 'h4', 'H4'))
            features.update(self._extract_timeframe_features(raw_data, 'd1', 'D1'))
            
            # Add MT5 indicators directly
            features.update(self._extract_mt5_indicators(raw_data))
            
            # Add timeframe alignment (now includes ALL 7 timeframes)
            features.update(self._extract_alignment(raw_data))
            
            # Add volume intelligence
            features.update(self._extract_volume(raw_data))
            
            # Add order book
            features.update(self._extract_orderbook(raw_data))
            
            # Add dummy feature to reach 160 (models expect 160)
            if len(features) == 159:
                features['dummy_160'] = 0.0
            
            logger.info(f"✅ Enhanced features: {len(features)} (7 timeframes)")
            return features
            
        except Exception as e:
            logger.error(f"Enhanced extraction failed: {e}, falling back to simple")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._engineer_simple_features(raw_data)
    
    def _extract_timeframe_features(self, raw_data: Dict, tf_key: str, tf_name: str) -> Dict[str, float]:
        """
        Generic method to extract 15 features from any timeframe.
        
        Args:
            raw_data: Complete data from EA
            tf_key: Timeframe key in data (e.g., 'm5', 'h1', 'd1')
            tf_name: Timeframe name for feature prefix (e.g., 'M5', 'H1', 'D1')
        
        Returns:
            Dictionary with 15 features prefixed with timeframe name
        """
        tf_data = raw_data.get('timeframes', {}).get(tf_key, raw_data.get('market_data', {}).get(tf_key.upper(), []))
        if not tf_data or len(tf_data) < 50:
            # Return default features if no data
            prefix = tf_name.lower()
            return {
                f'{prefix}_returns': 0.0,
                f'{prefix}_volatility': 0.0,
                f'{prefix}_sma_20': 0.0,
                f'{prefix}_sma_50': 0.0,
                f'{prefix}_price_to_sma': 1.0,
                f'{prefix}_rsi': 50.0,
                f'{prefix}_macd': 0.0,
                f'{prefix}_macd_signal': 0.0,
                f'{prefix}_bb_position': 0.5,
                f'{prefix}_momentum': 0.0,
                f'{prefix}_hl_ratio': 0.0,
                f'{prefix}_trend': 0.0,
                f'{prefix}_range': 0.0,
                f'{prefix}_close_pos': 0.5,
                f'{prefix}_strength': 0.0
            }
        
        df = pd.DataFrame(tf_data)
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        
        prefix = tf_name.lower()
        return {
            f'{prefix}_returns': (c[-1]-c[-2])/c[-2] if len(c)>1 else 0.0,
            f'{prefix}_volatility': np.std(c[-20:])/np.mean(c[-20:]) if len(c)>=20 else 0.0,
            f'{prefix}_sma_20': np.mean(c[-20:]) if len(c)>=20 else c[-1],
            f'{prefix}_sma_50': np.mean(c[-50:]) if len(c)>=50 else c[-1],
            f'{prefix}_price_to_sma': c[-1]/np.mean(c[-20:]) if len(c)>=20 and np.mean(c[-20:])>0 else 1.0,
            f'{prefix}_rsi': self._calculate_rsi(c, 14),
            f'{prefix}_macd': self._calculate_macd(c)[0],
            f'{prefix}_macd_signal': self._calculate_macd(c)[1],
            f'{prefix}_bb_position': self._calculate_bollinger_bands(c, 20)[2],
            f'{prefix}_momentum': (c[-1]-c[-5])/c[-5] if len(c)>=5 else 0.0,
            f'{prefix}_hl_ratio': (h[-1]-l[-1])/c[-1] if c[-1]>0 else 0.0,
            f'{prefix}_trend': 1.0 if (len(c)>=20 and c[-1]>np.mean(c[-20:])) else 0.0,
            f'{prefix}_range': np.mean(h[-14:]-l[-14:])/c[-1] if len(h)>=14 and c[-1]>0 else 0.0,
            f'{prefix}_close_pos': (c[-1]-l[-1])/(h[-1]-l[-1]) if (h[-1]-l[-1])>0 else 0.5,
            f'{prefix}_strength': abs(c[-1]-c[-10])/c[-10] if len(c)>=10 and c[-10]>0 else 0.0
        }
    
    def _extract_h1_features(self, raw_data: Dict) -> Dict[str, float]:
        """Extract 15 features from H1 timeframe."""
        tf_data = raw_data.get('timeframes', {}).get('h1', [])
        if not tf_data or len(tf_data) < 50:
            return {f'h1_{i}': 0.0 for i in range(15)}
        
        df = pd.DataFrame(tf_data)
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        
        return {
            'h1_returns': (c[-1]-c[-2])/c[-2] if len(c)>1 else 0.0,
            'h1_volatility': np.std(c[-20:])/np.mean(c[-20:]) if len(c)>=20 else 0.0,
            'h1_sma_20': np.mean(c[-20:]) if len(c)>=20 else c[-1],
            'h1_sma_50': np.mean(c[-50:]) if len(c)>=50 else c[-1],
            'h1_price_to_sma': c[-1]/np.mean(c[-20:]) if len(c)>=20 and np.mean(c[-20:])>0 else 1.0,
            'h1_rsi': self._calculate_rsi(c, 14),
            'h1_macd': self._calculate_macd(c)[0],
            'h1_macd_signal': self._calculate_macd(c)[1],
            'h1_bb_position': self._calculate_bollinger_bands(c, 20)[2],
            'h1_momentum': (c[-1]-c[-5])/c[-5] if len(c)>=5 else 0.0,
            'h1_hl_ratio': (h[-1]-l[-1])/c[-1] if c[-1]>0 else 0.0,
            'h1_trend': 1.0 if (len(c)>=20 and c[-1]>np.mean(c[-20:])) else 0.0,
            'h1_range': np.mean(h[-14:]-l[-14:])/c[-1] if len(h)>=14 and c[-1]>0 else 0.0,
            'h1_close_pos': (c[-1]-l[-1])/(h[-1]-l[-1]) if (h[-1]-l[-1])>0 else 0.5,
            'h1_strength': abs(c[-1]-c[-10])/c[-10] if len(c)>=10 and c[-10]>0 else 0.0
        }
    
    def _extract_h4_features(self, raw_data: Dict) -> Dict[str, float]:
        """Extract 15 features from H4 timeframe."""
        tf_data = raw_data.get('timeframes', {}).get('h4', [])
        if not tf_data or len(tf_data) < 50:
            return {f'h4_{i}': 0.0 for i in range(15)}
        
        df = pd.DataFrame(tf_data)
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        
        return {
            'h4_returns': (c[-1]-c[-2])/c[-2] if len(c)>1 else 0.0,
            'h4_volatility': np.std(c[-20:])/np.mean(c[-20:]) if len(c)>=20 else 0.0,
            'h4_sma_20': np.mean(c[-20:]) if len(c)>=20 else c[-1],
            'h4_sma_50': np.mean(c[-50:]) if len(c)>=50 else c[-1],
            'h4_price_to_sma': c[-1]/np.mean(c[-20:]) if len(c)>=20 and np.mean(c[-20:])>0 else 1.0,
            'h4_rsi': self._calculate_rsi(c, 14),
            'h4_macd': self._calculate_macd(c)[0],
            'h4_macd_signal': self._calculate_macd(c)[1],
            'h4_bb_position': self._calculate_bollinger_bands(c, 20)[2],
            'h4_momentum': (c[-1]-c[-5])/c[-5] if len(c)>=5 else 0.0,
            'h4_hl_ratio': (h[-1]-l[-1])/c[-1] if c[-1]>0 else 0.0,
            'h4_trend': 1.0 if (len(c)>=20 and c[-1]>np.mean(c[-20:])) else 0.0,
            'h4_range': np.mean(h[-14:]-l[-14:])/c[-1] if len(h)>=14 and c[-1]>0 else 0.0,
            'h4_close_pos': (c[-1]-l[-1])/(h[-1]-l[-1]) if (h[-1]-l[-1])>0 else 0.5,
            'h4_strength': abs(c[-1]-c[-10])/c[-10] if len(c)>=10 and c[-10]>0 else 0.0
        }
    
    def _extract_mt5_indicators(self, raw_data: Dict) -> Dict[str, float]:
        """Use MT5 indicators directly (13 features)."""
        ind = raw_data.get('indicators', {})
        # current_price can be float or dict
        cp_raw = raw_data.get('current_price', 0.0)
        if isinstance(cp_raw, dict):
            cp = cp_raw.get('bid', 0.0)
        else:
            cp = float(cp_raw) if cp_raw else 0.0
        
        return {
            'mt5_rsi': ind.get('rsi', 50.0),
            'mt5_macd_main': ind.get('macd_main', 0.0),
            'mt5_macd_signal': ind.get('macd_signal', 0.0),
            'mt5_bb_upper': ind.get('bb_upper', cp * 1.01) if cp > 0 else 0.0,
            'mt5_bb_lower': ind.get('bb_lower', cp * 0.99) if cp > 0 else 0.0,
            'mt5_bb_position': (cp - ind.get('bb_lower', cp * 0.99)) / (ind.get('bb_upper', cp * 1.01) - ind.get('bb_lower', cp * 0.99)) if cp > 0 and ind.get('bb_upper', 0) > ind.get('bb_lower', 0) else 0.5,
            'mt5_atr': ind.get('atr', 0.0),
            'mt5_adx': ind.get('adx', 0.0),
            'mt5_cci': ind.get('cci', 0.0),
            'mt5_stoch_main': ind.get('stoch_main', 50.0),
            'mt5_stoch_signal': ind.get('stoch_signal', 50.0),
            'mt5_williams': ind.get('williams', -50.0),
            'mt5_momentum': ind.get('momentum', 0.0),
            'mt5_roc': ind.get('roc', 0.0),
            'mt5_obv': ind.get('obv', 0.0),
        }
    
    def _extract_alignment(self, raw_data: Dict) -> Dict[str, float]:
        """Timeframe alignment features (15 features)."""
        tf = raw_data.get('timeframes', {})
        m1 = pd.DataFrame(tf.get('m1', [])) if tf.get('m1') else None
        h1 = pd.DataFrame(tf.get('h1', [])) if tf.get('h1') else None
        h4 = pd.DataFrame(tf.get('h4', [])) if tf.get('h4') else None
        
        if m1 is None or h1 is None or h4 is None or len(m1)<20 or len(h1)<20 or len(h4)<20:
            return {f'align_{i}': 0.0 for i in range(15)}
        
        m1_rsi = self._calculate_rsi(m1['close'].values, 14)
        h1_rsi = self._calculate_rsi(h1['close'].values, 14)
        h4_rsi = self._calculate_rsi(h4['close'].values, 14)
        m1_macd = self._calculate_macd(m1['close'].values)[0]
        h1_macd = self._calculate_macd(h1['close'].values)[0]
        h4_macd = self._calculate_macd(h4['close'].values)[0]
        m1_c = m1['close'].values[-1]
        h1_c = h1['close'].values[-1]
        h4_c = h4['close'].values[-1]
        m1_sma = np.mean(m1['close'].values[-20:])
        h1_sma = np.mean(h1['close'].values[-20:])
        h4_sma = np.mean(h4['close'].values[-20:])
        
        return {
            'align_0': m1_rsi - h1_rsi,
            'align_1': h1_rsi - h4_rsi,
            'align_2': 1.0 if (m1_rsi<30 and h1_rsi<30 and h4_rsi<30) else 0.0,
            'align_3': 1.0 if (m1_rsi>70 and h1_rsi>70 and h4_rsi>70) else 0.0,
            'align_4': 1.0 if (m1_macd*h1_macd>0) else 0.0,
            'align_5': 1.0 if (h1_macd*h4_macd>0) else 0.0,
            'align_6': 1.0 if (m1_macd>0 and h1_macd>0 and h4_macd>0) else 0.0,
            'align_7': 1.0 if (m1_macd<0 and h1_macd<0 and h4_macd<0) else 0.0,
            'align_8': 1.0 if m1_c>m1_sma else 0.0,
            'align_9': 1.0 if h1_c>h1_sma else 0.0,
            'align_10': 1.0 if h4_c>h4_sma else 0.0,
            'align_11': (float(m1_c>m1_sma)+float(h1_c>h1_sma)+float(h4_c>h4_sma))/3.0,
            'align_12': np.std(m1['close'].values[-20:])/np.mean(m1['close'].values[-20:]) if len(m1)>=20 else 0.0,
            'align_13': np.std(h1['close'].values[-20:])/np.mean(h1['close'].values[-20:]) if len(h1)>=20 else 0.0,
            'align_14': 1.0 if (len(m1)>=20 and len(h1)>=20 and np.std(m1['close'].values[-20:])>np.std(h1['close'].values[-20:])) else 0.0
        }
    
    def _extract_volume(self, raw_data: Dict) -> Dict[str, float]:
        """Volume intelligence (10 features)."""
        tf = raw_data.get('timeframes', {})
        m1 = pd.DataFrame(tf.get('m1', [])) if tf.get('m1') else None
        h1 = pd.DataFrame(tf.get('h1', [])) if tf.get('h1') else None
        
        if m1 is None or len(m1)<20:
            return {f'vol_{i}': 0.0 for i in range(10)}
        
        m1_vol = m1.get('volume', pd.Series([1]*len(m1))).values
        m1_close = m1['close'].values
        m1_vol_avg = np.mean(m1_vol[-20:]) if len(m1_vol)>=20 else 1.0
        
        return {
            'vol_0': m1_vol[-1]/m1_vol_avg if m1_vol_avg>0 else 1.0,
            'vol_1': 1.0 if (len(m1_vol)>1 and m1_vol[-1]>m1_vol[-2]) else 0.0,
            'vol_2': 1.0 if (len(m1_vol)>=3 and m1_vol[-1]>m1_vol[-2]>m1_vol[-3]) else 0.0,
            'vol_3': 1.0 if (len(m1_close)>=5 and m1_close[-1]>m1_close[-5] and m1_vol[-1]<np.mean(m1_vol[-5:])) else 0.0,
            'vol_4': np.sum(m1_vol[-10:]>m1_vol_avg*2.0)/10.0 if len(m1_vol)>=10 else 0.0,
            'vol_5': (np.mean(m1_vol[-5:])/np.mean(m1_vol[-20:])) if (len(m1_vol)>=20 and np.mean(m1_vol[-20:])>0) else 1.0,
            'vol_6': np.std(m1_vol[-20:])/m1_vol_avg if (len(m1_vol)>=20 and m1_vol_avg>0) else 0.0,
            'vol_7': 1.0 if (len(m1_vol)>1 and len(m1_close)>1 and m1_vol[-1]>m1_vol_avg*1.5 and m1_close[-1]>m1_close[-2]) else 0.0,
            'vol_8': 1.0 if (len(m1_vol)>1 and len(m1_close)>1 and m1_vol[-1]>m1_vol_avg*1.5 and m1_close[-1]<m1_close[-2]) else 0.0,
            'vol_9': m1_vol[-1]/m1_vol_avg if m1_vol_avg>0 else 1.0
        }
    
    def _extract_orderbook(self, raw_data: Dict) -> Dict[str, float]:
        """Order book analysis (5 features)."""
        ob = raw_data.get('order_book', {})
        bids = ob.get('bids', [])
        asks = ob.get('asks', [])
        
        if not bids or not asks:
            return {f'ob_{i}': 0.0 for i in range(5)}
        

        total_bid = sum([b.get('volume', 0) for b in bids])
        total_ask = sum([a.get('volume', 0) for a in asks])
        total = total_bid + total_ask
        large_count = sum(1 for b in bids if b.get('volume', 0) > total/len(bids+asks)*2) + sum(1 for a in asks if a.get('volume', 0) > total/len(bids+asks)*2) if len(bids+asks)>0 else 0
        
        return {
            'ob_0': total_bid/total if total>0 else 0.5,
            'ob_1': total_ask/total if total>0 else 0.5,
            'ob_2': (total_bid-total_ask)/total if total>0 else 0.0,
            'ob_3': large_count/len(bids+asks) if len(bids+asks)>0 else 0.0,
            'ob_4': len(bids+asks)/10.0 if len(bids+asks)<10 else 1.0
        }
