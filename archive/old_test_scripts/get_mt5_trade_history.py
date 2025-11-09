#!/usr/bin/env python3
"""
Get MT5 Trade History - See actual trades taken
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

print("="*80)
print("CONNECTING TO MT5 TO GET TRADE HISTORY")
print("="*80)

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
    print(f"   Balance: ${account_info.balance:,.2f}")
    print(f"   Equity: ${account_info.equity:,.2f}")
    print(f"   Profit: ${account_info.profit:,.2f}")

print("\n" + "="*80)
print("TRADE HISTORY - TODAY")
print("="*80)

# Get today's deals (actual executions)
today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
deals = mt5.history_deals_get(today_start, datetime.now())

if deals is None or len(deals) == 0:
    print("❌ No deals found today")
else:
    print(f"\n✅ Found {len(deals)} deals today\n")

    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')

    # Show each deal
    for idx, deal in df_deals.iterrows():
        deal_type = "BUY" if deal['type'] == 0 else "SELL"
        print(f"[{deal['time']}] {deal_type} {deal['volume']} lots @ {deal['price']}")
        print(f"   Profit: ${deal['profit']:.2f} | Commission: ${deal['commission']:.2f}")
        print(f"   Order: #{deal['order']} | Position: #{deal['position_id']}")
        print()

print("\n" + "="*80)
print("CLOSED POSITIONS - TODAY")
print("="*80)

# Get today's closed positions (completed trades)
history_orders = mt5.history_orders_get(today_start, datetime.now())

if history_orders is None or len(history_orders) == 0:
    print("❌ No closed positions found today")
else:
    print(f"\n✅ Found {len(history_orders)} orders today\n")

    df_orders = pd.DataFrame(list(history_orders), columns=history_orders[0]._asdict().keys())
    df_orders['time_setup'] = pd.to_datetime(df_orders['time_setup'], unit='s')
    df_orders['time_done'] = pd.to_datetime(df_orders['time_done'], unit='s')

    # Show summary
    print(df_orders[['time_setup', 'symbol', 'type', 'volume_current', 'price_current', 'state']].to_string())

print("\n" + "="*80)
print("OPEN POSITIONS - RIGHT NOW")
print("="*80)

# Get current open positions
positions = mt5.positions_get()

if positions is None or len(positions) == 0:
    print("❌ No open positions currently")
else:
    print(f"\n✅ {len(positions)} open position(s)\n")

    for pos in positions:
        pos_type = "BUY" if pos.type == 0 else "SELL"
        profit_color = "🟢" if pos.profit > 0 else "🔴"

        print(f"{profit_color} Position #{pos.ticket}")
        print(f"   {pos_type} {pos.volume} lots of {pos.symbol}")
        print(f"   Entry: {pos.price_open} | Current: {pos.price_current}")
        print(f"   Profit: ${pos.profit:.2f} ({pos.profit/pos.volume:.1f} pts/lot)")
        print(f"   Time: {datetime.fromtimestamp(pos.time)}")
        print()

print("\n" + "="*80)
print("TODAY'S TRADING SUMMARY")
print("="*80)

if deals is not None and len(deals) > 0:
    total_profit = df_deals['profit'].sum()
    total_commission = df_deals['commission'].sum()
    net_profit = total_profit + total_commission

    winning_deals = df_deals[df_deals['profit'] > 0]
    losing_deals = df_deals[df_deals['profit'] < 0]

    print(f"\n📊 Total Deals: {len(deals)}")
    print(f"   Wins: {len(winning_deals)} | Losses: {len(losing_deals)}")
    if len(deals) > 0:
        win_rate = len(winning_deals) / len(deals) * 100
        print(f"   Win Rate: {win_rate:.1f}%")

    print(f"\n💰 P&L:")
    print(f"   Gross Profit: ${total_profit:.2f}")
    print(f"   Commission: ${total_commission:.2f}")
    print(f"   Net Profit: ${net_profit:.2f}")

    if len(winning_deals) > 0:
        avg_win = winning_deals['profit'].mean()
        print(f"   Avg Win: ${avg_win:.2f}")

    if len(losing_deals) > 0:
        avg_loss = losing_deals['profit'].mean()
        print(f"   Avg Loss: ${avg_loss:.2f}")

print("\n" + "="*80)
print("LAST 10 CLOSED TRADES")
print("="*80)

# Get last 10 closed positions from history
from_date = datetime.now() - timedelta(days=7)
history_deals = mt5.history_deals_get(from_date, datetime.now())

if history_deals and len(history_deals) > 0:
    df_hist = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
    df_hist['time'] = pd.to_datetime(df_hist['time'], unit='s')

    # Filter out IN/OUT pairs and get unique position IDs
    closed_positions = df_hist[df_hist['entry'] == 1]  # Exit deals only

    print(f"\n✅ Last {min(10, len(closed_positions))} closed trades:\n")

    for idx, deal in closed_positions.tail(10).iterrows():
        deal_type = "BUY" if deal['type'] == 1 else "SELL"  # Reversed for exit
        profit_emoji = "🟢" if deal['profit'] > 0 else "🔴"

        print(f"{profit_emoji} [{deal['time']}] Closed {deal_type}")
        print(f"   Position #{deal['position_id']} | {deal['volume']} lots @ {deal['price']}")
        print(f"   P&L: ${deal['profit']:.2f}")
        print()

mt5.shutdown()

print("\n" + "="*80)
print("✅ DONE - Trade history retrieved")
print("="*80)
