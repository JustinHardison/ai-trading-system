#!/usr/bin/env python3
"""
Train all recommended symbols in parallel
Priority: US500, EURUSD, GBPUSD, USDJPY
"""
import subprocess
import sys
import os
import time
from datetime import datetime

# Recommended symbols (in priority order)
RECOMMENDED_SYMBOLS = [
    ('us500_m1_historical_data.csv', 'US500'),
    ('eurusd_m1_historical_data.csv', 'EURUSD'),
    ('gbpusd_m1_historical_data.csv', 'GBPUSD'),
    ('usdjpy_m1_historical_data.csv', 'USDJPY'),
]

def main():
    print("═══════════════════════════════════════════════════════════════════")
    print("TRAINING RECOMMENDED SYMBOLS")
    print("═══════════════════════════════════════════════════════════════════\n")
    
    # Check which files exist
    available = []
    for csv_file, symbol in RECOMMENDED_SYMBOLS:
        if os.path.exists(csv_file):
            available.append((csv_file, symbol))
            print(f"✅ {symbol}: {csv_file} found")
        else:
            print(f"❌ {symbol}: {csv_file} NOT FOUND")
    
    if not available:
        print("\n❌ No recommended symbol data files found!")
        print("   Make sure CSV files are in the current directory")
        return
    
    print(f"\n🚀 Starting training for {len(available)} symbols...")
    print("   This will run in parallel to save time\n")
    
    # Start all training processes
    processes = []
    for csv_file, symbol in available:
        filepath = os.path.abspath(csv_file)
        cmd = [sys.executable, 'train_from_real_mt5_csv.py', filepath, symbol]
        
        print(f"▶️  Starting {symbol} training...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        processes.append((symbol, proc))
        time.sleep(2)  # Stagger starts slightly
    
    print(f"\n✅ All {len(processes)} training processes started!")
    print("⏳ Waiting for completion (this may take 30-60 minutes)...\n")
    
    # Monitor progress
    completed = []
    failed = []
    
    while processes:
        for symbol, proc in processes[:]:
            retcode = proc.poll()
            if retcode is not None:
                # Process finished
                processes.remove((symbol, proc))
                
                if retcode == 0:
                    completed.append(symbol)
                    print(f"✅ {symbol} training COMPLETED")
                else:
                    failed.append(symbol)
                    print(f"❌ {symbol} training FAILED (code {retcode})")
        
        if processes:
            time.sleep(10)  # Check every 10 seconds
    
    # Summary
    print("\n" + "═"*70)
    print("TRAINING COMPLETE")
    print("═"*70)
    print(f"✅ Completed: {len(completed)} symbols")
    if completed:
        for s in completed:
            print(f"   • {s}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)} symbols")
        for s in failed:
            print(f"   • {s}")
    
    print("\n🧪 Ready for backtesting!")
    print("   Run: python3 backtest_all_symbols.py")

if __name__ == "__main__":
    main()
