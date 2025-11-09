#!/usr/bin/env python3
"""Test MT5 connection by creating command and reading response"""
import json
import time
from pathlib import Path

# MT5 Common Files directory (FILE_COMMON location)
mt5_files_dir = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
mt5_files_dir.mkdir(parents=True, exist_ok=True)

command_file = mt5_files_dir / "ai_command.txt"
response_file = mt5_files_dir / "ai_response.txt"

# Create command
command = {
    "action": "GET_ACCOUNT_INFO",
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
}

# Write command
with open(command_file, "w") as f:
    json.dump(command, f, indent=2)

print("✓ Created ai_command.txt")
print("Waiting for MT5 EA to create ai_response.txt...")
print("(Check MT5 Experts tab for EA activity)")

# Wait for response
for i in range(30):
    time.sleep(1)
    if response_file.exists():
        with open(response_file, 'r', encoding='utf-16') as f:
            response = json.load(f)
        print(f"\n✓ MT5 CONNECTED!")
        print(f"Balance: ${response.get('balance', 0):,.2f}")
        print(f"Equity: ${response.get('equity', 0):,.2f}")
        break
    else:
        print(f"Waiting... {i+1}/30", end="\r")
else:
    print("\n✗ MT5 EA is not responding")
    print("Make sure:")
    print("1. MT5 is running")
    print("2. EA is attached to chart")
    print("3. EA has AutoTrading enabled (green button)")
    print("4. EA has file permissions in Tools > Options > Expert Advisors")
