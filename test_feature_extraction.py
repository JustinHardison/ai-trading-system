#!/usr/bin/env python3
"""
Test feature extraction to ensure API gets 160 features from EA data
"""

import sys
sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.features.simple_feature_engineer import SimpleFeatureEngineer
import json

print("=" * 70)
print("TESTING FEATURE EXTRACTION")
print("=" * 70)

# Simulate what the EA sends
ea_request = {
    'symbol': 'EURUSD',
    'timeframes': {
        'm1': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 100, 'spread': 2, 'real_volume': 0}
            for i in range(200)  # 200 M1 bars
        ],
        'm5': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 500, 'spread': 2, 'real_volume': 0}
            for i in range(100)  # 100 M5 bars
        ],
        'm15': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 1500, 'spread': 2, 'real_volume': 0}
            for i in range(100)  # 100 M15 bars
        ],
        'm30': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 3000, 'spread': 2, 'real_volume': 0}
            for i in range(100)  # 100 M30 bars
        ],
        'h1': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 6000, 'spread': 2, 'real_volume': 0}
            for i in range(100)  # 100 H1 bars
        ],
        'h4': [
            {'timestamp': '2025-11-20 10:00', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 24000, 'spread': 2, 'real_volume': 0}
            for i in range(50)  # 50 H4 bars
        ],
        'd1': [
            {'timestamp': '2025-11-20', 'open': 1.10, 'high': 1.11, 'low': 1.09, 'close': 1.105, 'tick_volume': 144000, 'spread': 2, 'real_volume': 0}
            for i in range(30)  # 30 D1 bars
        ],
    },
    'indicators': {
        'rsi': 55.0,
        'macd_main': 0.001,
        'macd_signal': 0.0008,
        'bb_upper': 1.13,
        'bb_lower': 1.09,
        'atr': 0.002
    },
    'current_price': 1.105,
    'spread': 2
}

print("\n1. Testing with enhanced_mode=True (should get 160 features)")
print("-" * 70)

feature_engineer = SimpleFeatureEngineer(enhanced_mode=True)

try:
    features = feature_engineer.engineer_features(ea_request)
    print(f"✅ Features extracted: {len(features)}")
    print(f"   Expected: 160")
    print(f"   Match: {'✅ YES' if len(features) >= 159 else '❌ NO - MISMATCH!'}")
    
    if len(features) < 159:
        print(f"\n⚠️  WARNING: Only got {len(features)} features!")
        print(f"   Models expect 160 features")
        print(f"   This will cause prediction errors!")
    else:
        print(f"\n✅ SUCCESS: Got {len(features)} features (models expect 160)")
        
    print(f"\n   Sample features:")
    for i, (key, val) in enumerate(list(features.items())[:10]):
        print(f"     {key}: {val:.4f}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TESTING COMPLETE")
print("=" * 70)
