#!/usr/bin/env python3
"""
Analyze trade history from API logs
"""
import re
from datetime import datetime
from collections import defaultdict

print("="*80)
print("ANALYZING TRADE HISTORY FROM LOGS")
print("="*80)

# Read API logs
with open('/tmp/ai_trading_api.log', 'r') as f:
    logs = f.readlines()

# Parse balance changes
balances = []
equities = []
profits = []
timestamps = []

for line in logs:
    # Extract balance
    balance_match = re.search(r'Balance: \$([0-9,]+\.\d+)', line)
    if balance_match:
        balance = float(balance_match.group(1).replace(',', ''))
        balances.append(balance)
    
    # Extract equity
    equity_match = re.search(r'Equity: \$([0-9,]+\.\d+)', line)
    if equity_match:
        equity = float(equity_match.group(1).replace(',', ''))
        equities.append(equity)
    
    # Extract timestamp
    time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
    if time_match and balance_match:
        timestamps.append(time_match.group(1))

print(f"\n📊 DATA POINTS COLLECTED:")
print(f"   Balance readings: {len(balances)}")
print(f"   Equity readings: {len(equities)}")

if len(balances) > 1:
    starting_balance = balances[0]
    current_balance = balances[-1]
    balance_change = current_balance - starting_balance
    
    print(f"\n💰 BALANCE ANALYSIS:")
    print(f"   Starting: ${starting_balance:,.2f}")
    print(f"   Current: ${current_balance:,.2f}")
    print(f"   Change: ${balance_change:,.2f} ({balance_change/starting_balance*100:.2f}%)")

if len(equities) > 1:
    # Calculate equity fluctuations
    equity_changes = []
    for i in range(1, len(equities)):
        change = equities[i] - equities[i-1]
        if abs(change) > 0.01:  # Ignore tiny fluctuations
            equity_changes.append(change)
    
    if equity_changes:
        positive_changes = [c for c in equity_changes if c > 0]
        negative_changes = [c for c in equity_changes if c < 0]
        
        print(f"\n📈 EQUITY FLUCTUATIONS:")
        print(f"   Total changes: {len(equity_changes)}")
        print(f"   Positive: {len(positive_changes)} | Negative: {len(negative_changes)}")
        
        if positive_changes:
            avg_win = sum(positive_changes) / len(positive_changes)
            max_win = max(positive_changes)
            print(f"   Avg Win: ${avg_win:.2f} | Max Win: ${max_win:.2f}")
        
        if negative_changes:
            avg_loss = sum(negative_changes) / len(negative_changes)
            max_loss = min(negative_changes)
            print(f"   Avg Loss: ${avg_loss:.2f} | Max Loss: ${max_loss:.2f}")

# Look for trade decisions in logs
print(f"\n🤖 AI DECISIONS:")
entry_count = 0
dca_count = 0
close_count = 0
hold_count = 0

for line in logs[-10000:]:  # Last 10k lines
    if 'ENTRY APPROVED' in line or 'Entry approved' in line:
        entry_count += 1
    elif 'AI DECISION: DCA' in line or 'INTELLIGENT DCA' in line:
        dca_count += 1
    elif 'AI DECISION: CLOSE' in line or 'EXIT SIGNAL' in line:
        close_count += 1
    elif 'AI DECISION: HOLD' in line or 'HOLD -' in line:
        hold_count += 1

print(f"   Entries: {entry_count}")
print(f"   DCAs: {dca_count}")
print(f"   Closes: {close_count}")
print(f"   Holds: {hold_count}")

# Look for profit/loss patterns
print(f"\n📊 POSITION P&L PATTERNS:")
pnl_values = []
for line in logs[-5000:]:
    pnl_match = re.search(r'P&L: \$([+-]?[0-9,]+\.\d+)', line)
    if pnl_match:
        pnl = float(pnl_match.group(1).replace(',', ''))
        pnl_values.append(pnl)

if pnl_values:
    positive_pnl = [p for p in pnl_values if p > 0]
    negative_pnl = [p for p in pnl_values if p < 0]
    
    print(f"   Positive P&L readings: {len(positive_pnl)}")
    print(f"   Negative P&L readings: {len(negative_pnl)}")
    
    if positive_pnl:
        print(f"   Avg positive: ${sum(positive_pnl)/len(positive_pnl):.2f}")
        print(f"   Max positive: ${max(positive_pnl):.2f}")
    
    if negative_pnl:
        print(f"   Avg negative: ${sum(negative_pnl)/len(negative_pnl):.2f}")
        print(f"   Max negative: ${min(negative_pnl):.2f}")

print("\n" + "="*80)
print("✅ ANALYSIS COMPLETE")
print("="*80)
