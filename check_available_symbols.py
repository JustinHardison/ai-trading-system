#!/usr/bin/env python3
"""
Check what symbols are available in MT5 for trading
"""
import MetaTrader5 as mt5
from datetime import datetime

print("═══════════════════════════════════════════════════════════════════")
print("MT5 AVAILABLE SYMBOLS CHECK")
print("═══════════════════════════════════════════════════════════════════\n")

# Initialize MT5
if not mt5.initialize():
    print("❌ Failed to initialize MT5")
    print(f"Error: {mt5.last_error()}")
    mt5.shutdown()
    exit(1)

print("✅ MT5 Connected\n")

# Get all symbols
all_symbols = mt5.symbols_get()
print(f"Total symbols available: {len(all_symbols)}\n")

# Filter for US indices and interesting instruments
print("═══════════════════════════════════════════════════════════════════")
print("US INDICES & MAJOR INSTRUMENTS")
print("═══════════════════════════════════════════════════════════════════\n")

interesting = []
for symbol in all_symbols:
    name = symbol.name
    # Look for US indices, gold, oil
    if any(x in name.upper() for x in ['US30', 'US100', 'NAS', 'SPX', 'SP500', 'S&P', 'DOW', 'GOLD', 'XAU', 'OIL', 'WTI', 'GER', 'DAX']):
        interesting.append(symbol)

if not interesting:
    print("⚠️  No US indices found. Showing all available symbols...\n")
    interesting = all_symbols[:50]  # Show first 50

for symbol in sorted(interesting, key=lambda x: x.name):
    print(f"Symbol: {symbol.name}")
    print(f"  Description: {symbol.description}")
    print(f"  Visible: {symbol.visible}")
    print(f"  Trade Mode: {symbol.trade_mode}")
    print(f"  Point: {symbol.point}")
    print(f"  Digits: {symbol.digits}")
    print(f"  Spread: {symbol.spread}")
    print(f"  Volume Min: {symbol.volume_min}")
    print(f"  Volume Max: {symbol.volume_max}")
    print(f"  Volume Step: {symbol.volume_step}")
    print()

# Check specifically for FTMO US symbols with .sim suffix
print("\n═══════════════════════════════════════════════════════════════════")
print("FTMO .SIM SYMBOLS (Simulated Assets)")
print("═══════════════════════════════════════════════════════════════════\n")

sim_symbols = [s for s in all_symbols if '.sim' in s.name.lower()]
if sim_symbols:
    for symbol in sorted(sim_symbols, key=lambda x: x.name):
        print(f"✅ {symbol.name}: {symbol.description}")
else:
    print("❌ No .sim symbols found")
    print("   You may not be on FTMO US / OANDA account")

# Show current symbol
print("\n═══════════════════════════════════════════════════════════════════")
print("CURRENT SYMBOL INFO")
print("═══════════════════════════════════════════════════════════════════\n")

# Try to get current symbol (first visible symbol or US30)
current = None
for test_symbol in ['US30Z25.sim', 'US30.sim', 'US30', 'USTEC.sim', 'NAS100.sim']:
    sym = mt5.symbol_info(test_symbol)
    if sym:
        current = test_symbol
        break

if not current and len(all_symbols) > 0:
    current = all_symbols[0].name

if current:
    sym_info = mt5.symbol_info(current)
    print(f"Symbol: {current}")
    print(f"  Bid: {sym_info.bid}")
    print(f"  Ask: {sym_info.ask}")
    print(f"  Can Trade: {sym_info.trade_mode != 0}")
    print(f"  Min Lot: {sym_info.volume_min}")
    print(f"  Max Lot: {sym_info.volume_max}")
    print(f"  Step: {sym_info.volume_step}")

# Recommendations
print("\n═══════════════════════════════════════════════════════════════════")
print("RECOMMENDATIONS FOR MULTI-SYMBOL TRADING")
print("═══════════════════════════════════════════════════════════════════\n")

# Find tradeable index symbols
tradeable = [s for s in all_symbols if s.trade_mode != 0 and any(x in s.name.upper() for x in ['US', 'NAS', 'SPX', 'S&P', 'DOW'])]

if tradeable:
    print("Tradeable US Index Symbols Found:")
    for s in sorted(tradeable, key=lambda x: x.name)[:10]:
        print(f"  ✅ {s.name} - {s.description}")
else:
    print("❌ No tradeable US index symbols found")
    print("   Showing top 20 tradeable symbols instead:\n")
    tradeable_any = [s for s in all_symbols if s.trade_mode != 0][:20]
    for s in tradeable_any:
        print(f"  • {s.name} - {s.description}")

mt5.shutdown()
print("\n═══════════════════════════════════════════════════════════════════")
