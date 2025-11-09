import re
from datetime import datetime, timedelta

print("=" * 80)
print("DIAGNOSING: WHY NO TRADES ALL NIGHT")
print("=" * 80)
print()

# Read last 10000 lines
with open('/Users/justinhardison/ai-trading-system/api.log', 'r') as f:
    lines = f.readlines()[-10000:]

# Find all confidence levels
confidences = []
timestamps = []
for line in lines:
    if 'SCALP ENTRY' in line:
        # Extract confidence
        match = re.search(r'@(\d+\.\d+)%', line)
        if match:
            conf = float(match.group(1))
            confidences.append(conf)
            
            # Extract timestamp
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if ts_match:
                timestamps.append(ts_match.group(1))

if confidences:
    print(f"📊 ANALYSIS OF LAST {len(confidences)} SIGNALS:")
    print("-" * 80)
    print(f"Average confidence: {sum(confidences)/len(confidences):.1f}%")
    print(f"Max confidence: {max(confidences):.1f}%")
    print(f"Min confidence: {min(confidences):.1f}%")
    print()
    
    # Count by range
    above_80 = len([c for c in confidences if c >= 80])
    range_75_80 = len([c for c in confidences if 75 <= c < 80])
    range_70_75 = len([c for c in confidences if 70 <= c < 75])
    range_65_70 = len([c for c in confidences if 65 <= c < 70])
    below_65 = len([c for c in confidences if c < 65])
    
    print(f"Confidence Distribution:")
    print(f"  ≥ 80% (WOULD TRADE): {above_80} ({above_80/len(confidences)*100:.1f}%)")
    print(f"  75-79%: {range_75_80} ({range_75_80/len(confidences)*100:.1f}%)")
    print(f"  70-74%: {range_70_75} ({range_70_75/len(confidences)*100:.1f}%)")
    print(f"  65-69%: {range_65_70} ({range_65_70/len(confidences)*100:.1f}%)")
    print(f"  < 65%: {below_65} ({below_65/len(confidences)*100:.1f}%)")
    print()
    
    if timestamps:
        print(f"Time range: {timestamps[0]} to {timestamps[-1]}")
    print()
    
    # Diagnosis
    print("=" * 80)
    print("🔍 DIAGNOSIS:")
    print("=" * 80)
    
    if above_80 == 0:
        print("❌ PROBLEM: No signals reached 80% threshold")
        print()
        print("Possible causes:")
        print("1. Market conditions: Choppy/ranging (low confidence setups)")
        print("2. Time of day: Asian session (low volume, unclear direction)")
        print("3. Threshold too high: 80% is VERY selective (sniper mode)")
        print()
        print("RECOMMENDATION:")
        if max(confidences) >= 75:
            print(f"  • Max confidence was {max(confidences):.1f}%")
            print(f"  • Consider lowering threshold to 75% for more trades")
            print(f"  • OR wait for London/NY session (higher volume)")
        else:
            print(f"  • Max confidence only {max(confidences):.1f}%")
            print(f"  • Market is very unclear right now")
            print(f"  • System is correctly waiting for better setups")
    else:
        print(f"✅ {above_80} signals reached 80%+ threshold")
        print("   But no trades taken - check EA execution!")
else:
    print("❌ NO SIGNALS FOUND IN LOG")
    print("   EA may not be sending data to API")

print()
