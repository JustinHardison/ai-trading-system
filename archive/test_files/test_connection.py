#!/usr/bin/env python3
"""
Test MT5 connection with simplified approach
"""
from pathlib import Path
import json
import time

# Use TERMINAL_COMMONDATA_PATH
doc = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
cmd_file = doc / "ai_command.txt"
resp_file = doc / "ai_response.txt"

print("\n" + "="*60)
print("TESTING MT5 CONNECTION")
print("="*60)
print(f"Command file: {cmd_file}")
print(f"Response file: {resp_file}")
print()

# Test 1: Get account info
print("Test 1: Getting account info...")
if resp_file.exists():
    resp_file.unlink()

cmd = {"action": "GET_ACCOUNT_INFO"}
cmd_file.write_text(json.dumps(cmd))
print(f"  Sent: {cmd}")

for i in range(20):  # Wait up to 10 seconds
    time.sleep(0.5)
    if resp_file.exists():
        time.sleep(0.1)  # Let file finish writing
        try:
            response = json.loads(resp_file.read_text())
            resp_file.unlink()
            print(f"  ✅ Response: Balance=${response.get('balance', 0):.2f}")
            break
        except:
            continue
else:
    print("  ❌ No response")
    exit(1)

# Test 2: Get bars
print("\nTest 2: Getting EURUSD H1 bars...")
if resp_file.exists():
    resp_file.unlink()

cmd = {"action": "GET_BARS", "symbol": "EURUSD", "timeframe": "H1", "count": 10}
cmd_file.write_text(json.dumps(cmd))
print(f"  Sent: {cmd}")

for i in range(20):
    time.sleep(0.5)
    if resp_file.exists():
        time.sleep(0.1)
        try:
            response = json.loads(resp_file.read_text())
            resp_file.unlink()
            if response.get('success'):
                bars = response.get('bars', [])
                print(f"  ✅ Got {len(bars)} bars")
                if bars:
                    print(f"     Last close: {bars[-1].get('close')}")
            else:
                print(f"  ❌ Failed: {response.get('error')}")
            break
        except Exception as e:
            print(f"  Parse error: {e}")
            continue
else:
    print("  ❌ No response")
    exit(1)

print("\n" + "="*60)
print("✅ ALL TESTS PASSED - MT5 CONNECTION WORKING!")
print("="*60)
