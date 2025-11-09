# EA FIXES NEEDED

**Date:** Nov 30, 2025 12:32 AM

---

## 🐛 BUGS FOUND

### Bug #1: Scanning When Market Closed
**File:** `mql5/Experts/AI_Trading_EA_Ultimate.mq5`
**Line:** 184
**Problem:** EA scans every 60 seconds regardless of market hours
**Current Code:**
```mql5
if(currentTime - lastScanTime >= ScanIntervalSeconds)
{
    lastScanTime = currentTime;
    ScanAllSymbols();
}
```

**Fix:** Add market hours check BEFORE scanning
```mql5
// Check if market is open (Sunday 6PM - Friday 5PM ET)
MqlDateTime dt;
TimeToStruct(TimeCurrent(), dt);
int dayOfWeek = dt.day_of_week;  // 0=Sunday, 5=Friday, 6=Saturday
int hour = dt.hour;

bool marketOpen = false;

if(dayOfWeek == 6)  // Saturday
{
    marketOpen = false;
}
else if(dayOfWeek == 0)  // Sunday
{
    marketOpen = (hour >= 18);  // Opens at 6 PM
}
else if(dayOfWeek == 5)  // Friday
{
    marketOpen = (hour < 17);  // Closes at 5 PM
}
else  // Monday-Thursday
{
    marketOpen = true;
}

if(!marketOpen)
{
    // Don't waste time scanning when market is closed
    return;
}

if(currentTime - lastScanTime >= ScanIntervalSeconds)
{
    lastScanTime = currentTime;
    ScanAllSymbols();
}
```

---

### Bug #2: Scanning Every 60 Seconds Instead of Every Minute
**File:** `mql5/Experts/AI_Trading_EA_Ultimate.mq5`
**Line:** 25, 184
**Problem:** User wants to scan every M1 bar close, not every 60 seconds
**Current Code:**
```mql5
input int ScanIntervalSeconds = 60;  // Line 25

if(currentTime - lastScanTime >= ScanIntervalSeconds)  // Line 184
```

**Fix:** Check for new M1 bar instead of time interval
```mql5
// Remove ScanIntervalSeconds input parameter

// In OnTick():
static datetime lastM1BarTime = 0;

// Check for new M1 bar on ANY symbol
bool newBarDetected = false;
for(int i = 0; i < ArraySize(TradingSymbols); i++)
{
    datetime currentM1 = iTime(TradingSymbols[i], PERIOD_M1, 0);
    if(currentM1 != lastM1BarTime)
    {
        newBarDetected = true;
        lastM1BarTime = currentM1;
        break;
    }
}

if(newBarDetected)
{
    ScanAllSymbols();
}
```

---

### Bug #3: Max 3 Positions Instead of Total Risk %
**File:** Multiple files (API and EA)
**Problem:** System limits to 3 positions max, should limit by total risk %
**Current:** Max 3 positions
**Should Be:** Max 5% total portfolio risk

**Fix in API** (`api.py`):
```python
# Remove max_positions check

# Add total risk check
total_risk_pct = 0.0
for pos in open_positions:
    pos_risk = calculate_position_risk(pos)  # % of account
    total_risk_pct += pos_risk

if total_risk_pct >= 5.0:  # Max 5% total portfolio risk
    return {
        "action": "HOLD",
        "reason": f"Max portfolio risk reached: {total_risk_pct:.2f}%",
        "lots": 0.0
    }
```

**Calculate Position Risk:**
```python
def calculate_position_risk(position):
    """Calculate risk as % of account"""
    entry_price = position['price_open']
    stop_loss = position['sl']
    volume = position['volume']
    
    # Get contract specs
    contract_size = position.get('contract_size', 1.0)
    tick_value = position.get('tick_value', 0.01)
    tick_size = position.get('tick_size', 0.01)
    
    # Calculate risk distance
    risk_distance = abs(entry_price - stop_loss)
    
    # Calculate risk in dollars
    risk_dollars = (risk_distance / tick_size) * tick_value * contract_size * volume
    
    # Calculate risk as % of account
    account_balance = position.get('account_balance', 200000)
    risk_pct = (risk_dollars / account_balance) * 100
    
    return risk_pct
```

---

## 📊 MARKET HOURS CONFIRMATION

### US30, US100, US500 (Indices):
- **Sunday:** 6:00 PM ET - 11:59 PM ET
- **Monday-Thursday:** 12:00 AM ET - 11:59 PM ET (24 hours)
- **Friday:** 12:00 AM ET - 5:00 PM ET
- **Saturday:** CLOSED

### EURUSD, GBPUSD, USDJPY (Forex):
- **Sunday:** 5:00 PM ET - 11:59 PM ET
- **Monday-Thursday:** 12:00 AM ET - 11:59 PM ET (24 hours)
- **Friday:** 12:00 AM ET - 5:00 PM ET
- **Saturday:** CLOSED

### XAU (Gold):
- **Sunday:** 6:00 PM ET - 11:59 PM ET
- **Monday-Thursday:** 12:00 AM ET - 11:59 PM ET (24 hours)
- **Friday:** 12:00 AM ET - 5:00 PM ET
- **Saturday:** CLOSED

### USOIL (Crude Oil):
- **Sunday:** 6:00 PM ET - 11:59 PM ET
- **Monday-Thursday:** 12:00 AM ET - 11:59 PM ET (24 hours)
- **Friday:** 12:00 AM ET - 5:00 PM ET
- **Saturday:** CLOSED

**Note:** Most instruments trade 24/5 (Sunday 6PM - Friday 5PM ET)

---

## 🔧 IMPLEMENTATION PLAN

### 1. Fix EA Market Hours Check
- Add market hours check in `OnTick()` BEFORE scanning
- Return immediately if market closed
- Prevents wasted API calls

### 2. Change EA to Scan Every M1 Bar
- Remove `ScanIntervalSeconds` parameter
- Check for new M1 bar on any symbol
- Scan all symbols when new M1 bar detected

### 3. Fix API Max Positions Logic
- Remove hardcoded max 3 positions
- Calculate total portfolio risk %
- Limit to 5% total portfolio risk

### 4. Update Elite Position Sizer
- Consider total portfolio risk when sizing
- Reduce size if approaching 5% limit
- Ensure no single trade exceeds 1.5% risk

---

## ✅ EXPECTED BEHAVIOR AFTER FIXES

### Market Closed (Saturday or Sunday before 6PM):
```
EA: Market closed, not scanning
API: (no calls received)
Result: No wasted CPU/logs
```

### Market Open, New M1 Bar:
```
EA: New M1 bar detected on US30
EA: Scanning all 8 symbols
API: Receives 8 requests (one per symbol)
API: Analyzes each symbol
API: Returns decisions
EA: Executes decisions
```

### Portfolio at 4.5% Risk:
```
EA: New opportunity on EURUSD
API: Calculates position would add 0.8% risk
API: Total would be 5.3% (exceeds 5% limit)
API: Returns HOLD
EA: Does not open position
```

### Portfolio at 3.0% Risk:
```
EA: New opportunity on XAU
API: Calculates position would add 0.7% risk
API: Total would be 3.7% (within 5% limit)
API: Returns BUY with calculated lots
EA: Opens position
```

---

## 📝 SUMMARY

**3 Critical Fixes:**
1. ✅ Add market hours check in EA (stop scanning when closed)
2. ✅ Change EA to scan every M1 bar (not every 60 seconds)
3. ✅ Replace max 3 positions with max 5% total risk

**Result:**
- No more wasted scans when market closed
- Faster reaction time (M1 bars instead of 60 second intervals)
- Better risk management (total portfolio risk vs arbitrary position count)

---

END OF FIXES NEEDED
