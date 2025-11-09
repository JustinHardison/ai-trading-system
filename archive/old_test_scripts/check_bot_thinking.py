import requests
import json

print("=" * 80)
print("CHECKING BOT'S CURRENT THINKING")
print("=" * 80)
print()

# Check API health
try:
    response = requests.get("http://localhost:5007/health", timeout=2)
    if response.status_code == 200:
        print("✅ API is running")
    else:
        print("❌ API issue")
except:
    print("❌ API not responding")
    exit()

print()
print("Reading recent API decisions...")
print()

# Read last few log entries
with open('/Users/justinhardison/ai-trading-system/api.log', 'r') as f:
    lines = f.readlines()
    
# Find recent entry signals
entry_signals = []
for line in reversed(lines[-200:]):
    if 'SCALP ENTRY' in line or 'SWING ENTRY' in line:
        entry_signals.append(line.strip())
        if len(entry_signals) >= 5:
            break

if entry_signals:
    print("Last 5 ML decisions:")
    print("-" * 80)
    for signal in reversed(entry_signals):
        # Extract key info
        if 'BUY' in signal or 'SELL' in signal:
            parts = signal.split('|')
            for part in parts:
                if 'ENTRY' in part or '@' in part or 'Threshold' in part or 'Take' in part:
                    print(f"  {part.strip()}")
        print()
else:
    print("No recent entry signals found")

print()
print("=" * 80)
print("WHY NO TRADES?")
print("=" * 80)
print()
print("Possible reasons:")
print("1. ML confidence < 80% (sniper mode - very selective)")
print("2. Market conditions not ideal (ranging, low volume)")
print("3. LLM risk manager says STOP (high risk detected)")
print("4. No clear setup (waiting for high-probability entry)")
print()
print("This is GOOD - the AI is being selective, not gambling!")
print()
