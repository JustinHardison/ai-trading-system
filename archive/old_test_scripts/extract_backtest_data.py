"""
Extract data from MT5 backtest results
"""
import os
from pathlib import Path

# Common MT5 tester locations
tester_paths = [
    "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Tester",
    "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/justinhardison/Application Data/MetaQuotes/Terminal",
]

print("=" * 80)
print("SEARCHING FOR BACKTEST DATA")
print("=" * 80)

for base_path in tester_paths:
    if not Path(base_path).exists():
        continue
    
    print(f"\n📁 Checking: {base_path}")
    
    # Find all files
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith(('.csv', '.htm', '.html', '.xml', '.hst')):
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path)
                print(f"   Found: {file} ({size} bytes)")
                print(f"   Path: {full_path}")

print("\n" + "=" * 80)
print("INSTRUCTIONS:")
print("=" * 80)
print("\nIf no files found, export manually:")
print("1. In MT5 Strategy Tester, after backtest completes")
print("2. Right-click on 'Results' tab → 'Save as Report'")
print("3. Save as HTML or XML")
print("4. Or right-click chart → 'Save as' → CSV")
