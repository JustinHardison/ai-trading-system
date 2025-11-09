#!/usr/bin/env python3
"""
Check if ML models are working correctly with live data
"""

import time
import subprocess

print("=" * 70)
print("MONITORING LIVE TRADING - ML MODEL VERIFICATION")
print("=" * 70)
print("\nWaiting for trading requests from EA...")
print("(Press Ctrl+C to stop)\n")

last_position = 0

try:
    while True:
        # Get latest log entries
        result = subprocess.run(
            ['tail', '-100', '/tmp/ai_trading_api_output.log'],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.split('\n')
        
        # Look for recent activity
        for line in lines[-20:]:
            if 'Features extracted:' in line:
                features = line.split('Features extracted:')[1].strip()
                print(f"✅ Features: {features}")
            elif 'ML SIGNAL' in line and 'BUY prob' in line:
                print(f"🤖 {line.split('|')[-1].strip()}")
            elif '📊 Symbol:' in line:
                symbol_info = line.split('📊 Symbol:')[1].strip()
                print(f"\n📊 {symbol_info}")
            elif 'Enhanced features:' in line:
                print(f"✅ {line.split('|')[-1].strip()}")
            elif 'ERROR' in line and 'ML prediction failed' in line:
                print(f"❌ {line.split('|')[-1].strip()}")
        
        time.sleep(5)
        
except KeyboardInterrupt:
    print("\n\n" + "=" * 70)
    print("MONITORING STOPPED")
    print("=" * 70)
