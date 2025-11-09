#!/usr/bin/env python3
"""Test if volume features are being calculated correctly"""

import sys
sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.features.live_feature_engineer import LiveFeatureEngineer
import json

# Create a minimal test request
test_request = {
    'symbol_info': {'symbol': 'TEST'},
    'current_price': {'bid': 100.0},
    'timeframes': {
        'm5': [
            {'time': i, 'open': 100 + i*0.1, 'high': 101 + i*0.1, 'low': 99 + i*0.1, 'close': 100.5 + i*0.1, 'volume': 100 + i*10}
            for i in range(50)
        ]
    },
    'indicators': {
        'rsi': 50, 'macd': 0, 'macd_signal': 0, 'stoch_k': 50, 'stoch_d': 50,
        'sma_20': 100, 'sma_50': 100, 'bb_upper': 102, 'bb_middle': 100, 'bb_lower': 98
    }
}

# Engineer features
engineer = LiveFeatureEngineer()
features = engineer.engineer_features(test_request)

# Check volume features
print("\n" + "="*60)
print("VOLUME FEATURES TEST")
print("="*60)
print(f"Total features: {len(features)}")
print(f"\nVolume Features:")
print(f"  accumulation: {features.get('accumulation', 'MISSING')}")
print(f"  distribution: {features.get('distribution', 'MISSING')}")
print(f"  bid_pressure: {features.get('bid_pressure', 'MISSING')}")
print(f"  ask_pressure: {features.get('ask_pressure', 'MISSING')}")
print(f"  volume_ratio: {features.get('volume_ratio', 'MISSING')}")
print(f"  institutional_bars: {features.get('institutional_bars', 'MISSING')}")
print(f"  volume_increasing: {features.get('volume_increasing', 'MISSING')}")
print(f"  buying_pressure: {features.get('buying_pressure', 'MISSING')}")
print(f"  selling_pressure: {features.get('selling_pressure', 'MISSING')}")

print(f"\n✅ TEST RESULT:")
if features.get('bid_pressure') != 'MISSING' and features.get('ask_pressure') != 'MISSING':
    print("  ✅ bid_pressure and ask_pressure ARE being calculated!")
    print(f"  ✅ bid_pressure = {features['bid_pressure']:.3f}")
    print(f"  ✅ ask_pressure = {features['ask_pressure']:.3f}")
else:
    print("  ❌ bid_pressure and ask_pressure are MISSING!")

print("="*60 + "\n")
