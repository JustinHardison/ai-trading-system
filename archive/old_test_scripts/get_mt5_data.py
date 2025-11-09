"""
Get historical data directly from MT5
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

print("=" * 80)
print("CONNECTING TO MT5 AND GETTING HISTORICAL DATA")
print("=" * 80)

# Initialize MT5
if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    quit()

print("✅ Connected to MT5")

# Get account info
account_info = mt5.account_info()
if account_info:
    print(f"   Account: {account_info.login}")
    print(f"   Server: {account_info.server}")

# Symbol to get data for
symbol = "US30Z25.sim"

# Get historical data
print(f"\n📊 Fetching historical data for {symbol}...")

# Get last 3 months of M1 data
utc_to = datetime.now()
utc_from = utc_to - timedelta(days=90)

rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, utc_from, utc_to)

if rates is None:
    print(f"❌ Failed to get data: {mt5.last_error()}")
    mt5.shutdown()
    quit()

# Convert to DataFrame
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

print(f"✅ Got {len(df)} bars of data")
print(f"   Period: {df['time'].min()} to {df['time'].max()}")
print(f"   Columns: {list(df.columns)}")

# Save to CSV
output_file = '/Users/justinhardison/ai-trading-system/us30_historical_data.csv'
df.to_csv(output_file, index=False)

print(f"\n💾 Saved to: {output_file}")
print(f"   Size: {len(df)} rows")

# Show sample
print("\n📋 Sample data:")
print(df.head(10))

mt5.shutdown()

print("\n" + "=" * 80)
print("✅ DATA READY FOR TRAINING!")
print("=" * 80)
print("\nRun this to train:")
print("python3 train_from_mt5_data.py")
