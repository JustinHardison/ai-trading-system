#!/usr/bin/env python3
"""
Train ML models for ALL MT5 symbols
Each symbol gets its own optimized model using existing training infrastructure
IMPORTANT: Does not modify EA - just adds more trained models
"""
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import os
import sys
import subprocess
import glob

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("═══════════════════════════════════════════════════════════════════")
print("MULTI-SYMBOL ML MODEL TRAINING")
print("═══════════════════════════════════════════════════════════════════\n")

def discover_symbols():
    """Discover all CSV files exported from MT5"""
    print("Discovering exported symbol data...")
    
    csv_files = glob.glob('*_m1_historical_data.csv')
    symbols = {}
    
    for csv_file in sorted(csv_files):
        # Extract symbol name from filename
        symbol_name = csv_file.replace('_m1_historical_data.csv', '').upper()
        
        # Check if file has data
        try:
            df = pd.read_csv(csv_file, nrows=10)
            if len(df) > 0:
                # Check if already trained
                model_exists = os.path.exists(f'models/{symbol_name.lower()}_ensemble_latest.pkl')
                
                symbols[symbol_name] = {
                    'file': csv_file,
                    'description': f'{symbol_name} Trading Instrument',
                    'skip': model_exists,
                    'reason': 'Model already exists' if model_exists else None
                }
                
                status = "✓ TRAINED" if model_exists else "○ NEEDS TRAINING"
                print(f"  {status} {symbol_name}: {csv_file}")
        except Exception as e:
            print(f"  ✗ SKIP {symbol_name}: Error reading file - {e}")
    
    return symbols

# Discover symbols dynamically
SYMBOLS = discover_symbols()

def load_and_prepare_data(filepath):
    """Load CSV and prepare for training"""
    print(f"Loading data from {filepath}...")

    df = pd.read_csv(filepath)
    print(f"  Loaded {len(df):,} bars")

    # Ensure required columns
    required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    if not all(col in df.columns for col in required):
        print(f"  ❌ Missing required columns. Got: {df.columns.tolist()}")
        return None

    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  ✅ Data prepared")

    return df

def train_symbol_model(symbol, config):
    """Train ML model for a specific symbol using existing train_from_real_mt5_csv.py"""
    print("\n" + "━"*70)
    print(f"TRAINING: {symbol} - {config['description']}")
    print("━"*70 + "\n")

    if config.get('skip'):
        print(f"⏭️  SKIPPED: {config.get('reason', 'No reason provided')}")
        return None

    # Check file exists
    filepath = os.path.join(os.path.dirname(__file__), config['file'])
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None

    print(f"Data file: {filepath}")
    print(f"Starting training using existing infrastructure...")
    print(f"(This will take 5-10 minutes per symbol)\n")

    try:
        # Use the existing training script via subprocess
        # Pass CSV file and symbol name as arguments
        result = subprocess.run(
            [sys.executable, 'train_from_real_mt5_csv.py', filepath, symbol],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=1200  # 20 minute timeout
        )

        # Show output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print(f"\n✅ {symbol} model trained successfully!")
            print(f"   Model saved in models/ directory")
            return True
        else:
            print(f"\n❌ {symbol} training failed with code {result.returncode}")
            return None

    except subprocess.TimeoutExpired:
        print(f"\n❌ {symbol} training timed out (>20 minutes)")
        return None
    except Exception as e:
        print(f"\n❌ Training error for {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None

# Main training loop
def main():
    results = {}

    print(f"Found {len(SYMBOLS)} symbols to process:\n")
    for symbol, config in SYMBOLS.items():
        status = "SKIP" if config.get('skip') else "TRAIN"
        print(f"  [{status}] {symbol}: {config['description']}")

    print("\n" + "═"*70)
    print("STARTING TRAINING")
    print("═"*70)

    trained_count = 0
    skipped_count = 0
    failed_count = 0

    for symbol, config in SYMBOLS.items():
        result = train_symbol_model(symbol, config)

        if config.get('skip'):
            skipped_count += 1
            results[symbol] = 'SKIPPED'
        elif result:
            trained_count += 1
            results[symbol] = 'SUCCESS'
        else:
            failed_count += 1
            results[symbol] = 'FAILED'

    # Summary
    print("\n" + "═"*70)
    print("TRAINING COMPLETE - SUMMARY")
    print("═"*70 + "\n")

    for symbol, status in results.items():
        emoji = "✅" if status == "SUCCESS" else ("⏭️ " if status == "SKIPPED" else "❌")
        print(f"{emoji} {symbol}: {status}")

    print(f"\nStatistics:")
    print(f"  ✅ Trained: {trained_count}")
    print(f"  ⏭️  Skipped: {skipped_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  📊 Total: {len(SYMBOLS)}")

    if trained_count > 0:
        print(f"\n🎉 Successfully trained {trained_count} new model(s)!")
        print(f"\nNext steps:")
        print(f"1. Test each model with backtesting")
        print(f"2. Update API to load all symbol models")
        print(f"3. Deploy multi-symbol EA")

    print("\n" + "═"*70)

if __name__ == "__main__":
    main()
