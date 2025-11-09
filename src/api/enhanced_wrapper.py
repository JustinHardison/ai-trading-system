"""
Enhanced API Wrapper - Adds new features to existing endpoint
Usage: Import this and call enhance_request() before ML prediction
"""
from src.features.feature_engineer import FeatureEngineer
from src.features.regime_detector import RegimeDetector
import pandas as pd

# Global instances
_feature_engineer = FeatureEngineer()
_regime_detector = RegimeDetector(lookback_bars=100)


def enhance_request(raw_data: dict) -> dict:
    """
    Enhance raw MT5 data with engineered features

    Args:
        raw_data: Raw data from EA

    Returns:
        Dictionary with added features
    """
    # Engineer features
    engineered = _feature_engineer.engineer_all_features(raw_data)

    # Add regime features if market data available
    if 'market_data' in raw_data and 'M1' in raw_data['market_data']:
        m1_data = raw_data['market_data']['M1']
        if 'close' in m1_data:
            df = pd.DataFrame(m1_data)
            regime_features = _regime_detector.get_all_features(df)
            engineered.update(regime_features)

            # Get regime multiplier for position sizing
            engineered['regime_multiplier'] = _regime_detector.get_position_sizing_multiplier(df)

    return engineered


def get_regime_info(raw_data: dict) -> dict:
    """Get regime classification and strategy params"""
    if 'market_data' not in raw_data or 'M1' not in raw_data['market_data']:
        return {'regime': 'unknown', 'multiplier': 1.0}

    m1_data = raw_data['market_data']['M1']
    if 'close' not in m1_data:
        return {'regime': 'unknown', 'multiplier': 1.0}

    df = pd.DataFrame(m1_data)
    multiplier = _regime_detector.get_position_sizing_multiplier(df)
    features = _regime_detector.get_all_features(df)

    # Classify regime
    if features.get('is_high_volatility', 0) and features.get('is_trending', 0):
        regime = 'high_vol_trending'
    elif features.get('is_low_volatility', 0) and features.get('is_ranging', 0):
        regime = 'low_vol_ranging'
    else:
        regime = 'normal'

    return {
        'regime': regime,
        'multiplier': multiplier,
        'volatility': features.get('volatility_regime', 1),
        'trend': features.get('trend_regime', 0),
        'is_trending': features.get('is_trending', 0),
        'adx': features.get('adx', 0)
    }
