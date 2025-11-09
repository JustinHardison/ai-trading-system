#!/usr/bin/env python3
"""
Train ML models for multiple symbols using train_from_real_mt5_csv.py as template
Each symbol gets its own model
"""
import subprocess
import sys
import os

print("═══════════════════════════════════════════════════════════════════")
print("MULTI-SYMBOL ML MODEL TRAINING")
print("═══════════════════════════════════════════════════════════════════\n")

# Symbols to train (skip US30 - already trained)
SYMBOLS_TO_TRAIN = [
    ('US100', 'us100_m1_historical_data.csv', 'Nasdaq 100'),
    ('XAU', 'xau_m1_historical_data.csv', 'Gold'),
    ('USOIL', 'usoil_m1_historical_data.csv', 'Crude Oil')
]

def train_symbol(symbol, csv_file, description):
    """Train a model for one symbol by modifying the CSV path in train script"""
    print(f"\n{'━'*70}")
    print(f"TRAINING: {symbol} - {description}")
    print(f"{'━'*70}\n")

    csv_path = os.path.join(os.path.dirname(__file__), csv_file)
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return False

    print(f"Data file: {csv_path}")
    print(f"Starting training...")
    print(f"(This will take 5-10 minutes per symbol)\n")

    # Run the existing training script with modified CSV path
    # We'll use subprocess and set environment variable for the CSV path
    env = os.environ.copy()
    env['TRAINING_CSV_PATH'] = csv_path
    env['TRAINING_SYMBOL'] = symbol

    try:
        result = subprocess.run(
            [sys.executable, 'train_from_real_mt5_csv.py'],
            cwd=os.path.dirname(__file__),
            env=env,
            capture_output=False,
            text=True,
            timeout=1200  # 20 minute timeout
        )

        if result.returncode == 0:
            print(f"\n✅ {symbol} model trained successfully!")
            return True
        else:
            print(f"\n❌ {symbol} training failed with code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        print(f"\n❌ {symbol} training timed out (>20 minutes)")
        return False
    except Exception as e:
        print(f"\n❌ {symbol} training error: {e}")
        return False

def main():
    print(f"Will train {len(SYMBOLS_TO_TRAIN)} symbols:\n")
    for symbol, csv, desc in SYMBOLS_TO_TRAIN:
        print(f"  • {symbol}: {desc}")

    print(f"\n⏭️  Skipping US30 (already trained)")
    print(f"\n{'═'*70}")
    print("STARTING TRAINING")
    print(f"{'═'*70}")

    results = {}
    for symbol, csv, desc in SYMBOLS_TO_TRAIN:
        success = train_symbol(symbol, csv, desc)
        results[symbol] = 'SUCCESS' if success else 'FAILED'

    # Summary
    print(f"\n{'═'*70}")
    print("TRAINING COMPLETE - SUMMARY")
    print(f"{'═'*70}\n")

    for symbol, status in results.items():
        emoji = "✅" if status == "SUCCESS" else "❌"
        print(f"{emoji} {symbol}: {status}")

    success_count = sum(1 for s in results.values() if s == "SUCCESS")
    fail_count = sum(1 for s in results.values() if s == "FAILED")

    print(f"\nStatistics:")
    print(f"  ✅ Trained: {success_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"  📊 Total: {len(results)}")

    if success_count > 0:
        print(f"\n🎉 Successfully trained {success_count} new model(s)!")
        print(f"\nNext steps:")
        print(f"1. Update API to load all symbol models")
        print(f"2. Test each model with backtesting")
        print(f"3. Deploy multi-symbol EA")

    print(f"\n{'═'*70}")

if __name__ == "__main__":
    main()
