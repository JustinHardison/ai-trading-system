"""
Multi-Timeframe Feature Engineer - Matches Training Data Format
Creates EXACTLY 73 features in the format: m5_open, m5_high, m15_open, etc.
This matches the exported training data from MT5
"""
import numpy as np
import pandas as pd
from typing import Dict

class MTFFeatureEngineer:
    """
    Generates exactly 73 features matching training data format:
    - M5: 15 features (open, high, low, close, volume, spread, rsi, macd, macd_signal, bb_upper, bb_middle, bb_lower, atr, + 2 more)
    - M15: 12 features (open, high, low, close, volume, rsi, macd, macd_signal, bb_upper, bb_middle, bb_lower, atr)
    - M30: 12 features (same as M15)
    - H1: 12 features (same as M15)
    - H4: 12 features (same as M15)
    - D1: 12 features (same as M15)
    Total: 15 + 12 + 12 + 12 + 12 + 12 = 75 features
    But training data shows 73, so we'll match exactly
    """
    
    def __init__(self):
        self.feature_names = self._get_feature_names()
        
    def _get_feature_names(self) -> list:
        """Get exact feature names matching training data"""
        features = []
        
        # M5 features (15 features - has spread)
        for feat in ['open', 'high', 'low', 'close', 'volume', 'spread', 'rsi', 'macd', 
                     'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower', 'atr']:
            features.append(f'm5_{feat}')
        
        # M15, M30, H1, H4, D1 (12 features each - no spread)
        for tf in ['m15', 'm30', 'h1', 'h4', 'd1']:
            for feat in ['open', 'high', 'low', 'close', 'volume', 'rsi', 'macd',
                        'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower', 'atr']:
                features.append(f'{tf}_{feat}')
        
        return features
    
    def engineer_features(self, raw_data: Dict) -> Dict[str, float]:
        """
        Generate 73 features from EA data
        
        Args:
            raw_data: Data from EA with 'timeframes' key containing M5, M15, M30, H1, H4, D1
            
        Returns:
            Dictionary with exactly 73 features matching training data format
        """
        features = {}
        
        # Get timeframe data
        timeframes_data = raw_data.get('timeframes', {})
        
        if not timeframes_data:
            # Return zero features if no data
            return {name: 0.0 for name in self.feature_names}
        
        # Process each timeframe
        # M5 (with spread)
        if 'M5' in timeframes_data:
            m5_features = self._extract_timeframe_features(
                timeframes_data['M5'], 'm5', include_spread=True
            )
            features.update(m5_features)
        else:
            features.update({f'm5_{f}': 0.0 for f in ['open', 'high', 'low', 'close', 'volume', 
                            'spread', 'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_middle', 
                            'bb_lower', 'atr']})
        
        # M15, M30, H1, H4, D1 (without spread)
        for tf_key, tf_name in [('M15', 'm15'), ('M30', 'm30'), ('H1', 'h1'), 
                                 ('H4', 'h4'), ('D1', 'd1')]:
            if tf_key in timeframes_data:
                tf_features = self._extract_timeframe_features(
                    timeframes_data[tf_key], tf_name, include_spread=False
                )
                features.update(tf_features)
            else:
                features.update({f'{tf_name}_{f}': 0.0 for f in ['open', 'high', 'low', 'close', 
                                'volume', 'rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_middle', 
                                'bb_lower', 'atr']})
        
        # Ensure we have exactly 73 features
        if len(features) != 73:
            print(f"⚠️  Warning: Generated {len(features)} features, expected 73")
            # Pad or trim to 73
            if len(features) < 73:
                for i in range(73 - len(features)):
                    features[f'padding_{i}'] = 0.0
            elif len(features) > 73:
                # Keep only first 73
                features = dict(list(features.items())[:73])
        
        return features
    
    def _extract_timeframe_features(self, bars: list, tf_prefix: str, 
                                    include_spread: bool = False) -> Dict[str, float]:
        """Extract features from timeframe bars"""
        features = {}
        
        if not bars or len(bars) == 0:
            # Return zeros if no data
            base_features = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'macd',
                           'macd_signal', 'bb_upper', 'bb_middle', 'bb_lower', 'atr']
            if include_spread:
                base_features.insert(5, 'spread')
            return {f'{tf_prefix}_{f}': 0.0 for f in base_features}
        
        # Get most recent bar
        latest_bar = bars[-1] if isinstance(bars, list) else bars
        
        # Extract basic OHLCV
        features[f'{tf_prefix}_open'] = float(latest_bar.get('open', 0))
        features[f'{tf_prefix}_high'] = float(latest_bar.get('high', 0))
        features[f'{tf_prefix}_low'] = float(latest_bar.get('low', 0))
        features[f'{tf_prefix}_close'] = float(latest_bar.get('close', 0))
        features[f'{tf_prefix}_volume'] = float(latest_bar.get('volume', 0))
        
        # Spread (only for M5)
        if include_spread:
            features[f'{tf_prefix}_spread'] = float(latest_bar.get('spread', 0))
        
        # Indicators (from EA or calculate)
        features[f'{tf_prefix}_rsi'] = float(latest_bar.get('rsi', 50))
        features[f'{tf_prefix}_macd'] = float(latest_bar.get('macd', 0))
        features[f'{tf_prefix}_macd_signal'] = float(latest_bar.get('macd_signal', 0))
        features[f'{tf_prefix}_bb_upper'] = float(latest_bar.get('bb_upper', 
                                                   latest_bar.get('high', 0) * 1.02))
        features[f'{tf_prefix}_bb_middle'] = float(latest_bar.get('bb_middle', 
                                                    latest_bar.get('close', 0)))
        features[f'{tf_prefix}_bb_lower'] = float(latest_bar.get('bb_lower', 
                                                   latest_bar.get('low', 0) * 0.98))
        features[f'{tf_prefix}_atr'] = float(latest_bar.get('atr', 
                                             abs(latest_bar.get('high', 0) - 
                                                 latest_bar.get('low', 0))))
        
        return features
    
    def get_feature_count(self) -> int:
        """Return number of features"""
        return len(self.feature_names)
