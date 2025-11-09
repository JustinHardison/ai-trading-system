#!/usr/bin/env python3
"""
Check MT5 Trades - Quick script to see today's trading activity
"""
import sys
sys.path.insert(0, '/Users/justinhardison/ai-trading-system')

from src.brokers.mt5_connector import MT5Connector
from datetime import datetime, timedelta

print("="*80)
print("MT5 TRADE HISTORY CHECK")
print("="*80)

# Connect to MT5
connector = MT5Connector()
success, message = connector.connect()

if not success:
    print(f"❌ Failed to connect: {message}")
    sys.exit(1)

print(f"✅ {message}\n")

# Get account info
import MetaTrader5 as mt5
account_info = mt5.account_info()
if account_info:
    print(f"Account: {account_info.login}")
    print(f"Server: {account_info.server}")
    print(f"Balance: ${account_info.balance:,.2f}")
    print(f"Equity: ${account_info.equity:,.2f}")
    print(f"Profit: ${account_info.profit:,.2f}")
    print(f"Margin: ${account_info.margin:,.2f}")
    print(f"Free Margin: ${account_info.margin_free:,.2f}")

print("\n" + "="*80)
print("TODAY'S DEALS (Actual Executions)")
print("="*80)

# Get today's deals
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
deals = mt5.history_deals_get(today_start, datetime.now())

if deals is None or len(deals) == 0:
    print("\n❌ No deals found today")
else:
    print(f"\n✅ Found {len(deals)} deals today:\n")

    total_profit = 0
    wins = 0
    losses = 0

    for deal in deals:
        deal_time = datetime.fromtimestamp(deal.time)
        deal_type = "BUY" if deal.type == 0 else "SELL"
        profit_emoji = "🟢" if deal.profit > 0 else "🔴" if deal.profit < 0 else "⚪"

        print(f"{profit_emoji} [{deal_time.strftime('%H:%M:%S')}] {deal_type} {deal.volume} lots @ {deal.price}")
        print(f"   Position #{deal.position_id} | Profit: ${deal.profit:.2f} | Commission: ${deal.commission:.2f}")
        print()

        total_profit += deal.profit
        if deal.profit > 0:
            wins += 1
        elif deal.profit < 0:
            losses += 1

    print(f"📊 Summary:")
    print(f"   Total Deals: {len(deals)}")
    print(f"   Wins: {wins} | Losses: {losses}")
    if wins + losses > 0:
        win_rate = wins / (wins + losses) * 100
        print(f"   Win Rate: {win_rate:.1f}%")
    print(f"   Total Profit: ${total_profit:.2f}")

print("\n" + "="*80)
print("CURRENTLY OPEN POSITIONS")
print("="*80)

positions = mt5.positions_get()

if positions is None or len(positions) == 0:
    print("\n❌ No open positions")
else:
    print(f"\n✅ {len(positions)} open position(s):\n")

    for pos in positions:
        pos_type = "BUY" if pos.type == 0 else "SELL"
        profit_emoji = "🟢" if pos.profit > 0 else "🔴"
        pos_time = datetime.fromtimestamp(pos.time)

        print(f"{profit_emoji} Position #{pos.ticket}")
        print(f"   {pos_type} {pos.volume} lots of {pos.symbol}")
        print(f"   Entry: {pos.price_open} | Current: {pos.price_current}")
        print(f"   Profit: ${pos.profit:.2f}")
        print(f"   Opened: {pos_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Comment: {pos.comment}")
        print()

print("\n" + "="*80)
print("LAST 20 CLOSED TRADES")
print("="*80)

# Get last week's history
from_date = datetime.now() - timedelta(days=7)
history_deals = mt5.history_deals_get(from_date, datetime.now())

if history_deals and len(history_deals) > 0:
    # Get exit deals only (entry=1 means exit)
    exit_deals = [d for d in history_deals if d.entry == 1]

    print(f"\n✅ Last {min(20, len(exit_deals))} closed trades:\n")

    for deal in exit_deals[-20:]:
        deal_time = datetime.fromtimestamp(deal.time)
        deal_type = "CLOSED BUY" if deal.type == 1 else "CLOSED SELL"
        profit_emoji = "🟢" if deal.profit > 0 else "🔴"

        print(f"{profit_emoji} [{deal_time.strftime('%m/%d %H:%M')}] {deal_type}")
        print(f"   Position #{deal.position_id} | {deal.volume} lots @ {deal.price}")
        print(f"   P&L: ${deal.profit:.2f} | Comment: {deal.comment}")
        print()

mt5.shutdown()

print("="*80)
print("✅ DONE")
print("="*80)
