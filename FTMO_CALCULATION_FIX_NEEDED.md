# 🚨 FTMO CALCULATION - FIX NEEDED

**Date**: November 23, 2025, 7:56 PM  
**Status**: ❌ INCORRECT CALCULATION

---

## 📊 REAL vs CALCULATED

### Real Account Data (from MetriX):
- **Balance**: $194,884.06
- **Equity**: $195,159.09
- **Today's Profit**: $664.13
- **Max Daily Loss**: -$10,000
- **Today's Permitted Loss**: $10,664.13
- **Max Loss**: -$20,000
- **Max Permitted Loss**: $15,159.09

### What API is Calculating:
- **Balance**: $194,882.84 ✅ (close)
- **Equity**: $195,165.40 ✅ (close)
- **Daily P&L**: $822.31 ❌ WRONG (should be $664.13)
- **Daily Limit Left**: $9,717 ❌ WRONG (should be $10,664.13)
- **DD Limit Left**: $19,488 ❌ WRONG (should be $15,159.09)

---

## 🔍 THE PROBLEM

### What EA Sends:
```python
'account': {
    'balance': 194882.84,
    'equity': 195165.4,
    'margin': 33689.19,
    'free_margin': 161193.65,
    'margin_level': 579.31,
    'profit': 282.56,  # This is OPEN positions profit only!
    'currency': 'USD'
}
```

### What's Missing:
- ❌ `daily_pnl` (today's total profit/loss)
- ❌ `daily_start_balance` (balance at start of day)
- ❌ `max_daily_loss` (FTMO daily limit)
- ❌ `max_total_drawdown` (FTMO total DD limit)
- ❌ `peak_balance` (for DD calculation)
- ❌ `daily_closed_pnl` (closed trades today)

### What API is Doing (WRONG):
```python
# Approximating from positions - NOT ACCURATE!
closed_pnl = sum(recent_trades profit)  # Doesn't know which are "today"
open_pnl = sum(positions profit)  # This is correct
daily_pnl = closed_pnl + open_pnl  # WRONG - includes old trades

# Guessing limits - NOT ACCURATE!
max_daily_loss = daily_start_balance * 0.05  # But we don't know start balance!
max_total_drawdown = account_balance * 0.10  # Wrong base!
```

---

## ✅ THE FIX

### Option 1: EA Sends FTMO Data (BEST)

**EA should send:**
```python
'account': {
    'balance': 194882.84,
    'equity': 195165.4,
    'profit': 282.56,
    # ADD THESE:
    'daily_pnl': 664.13,  # Today's total P&L
    'daily_start_balance': 194220.0,  # Balance at start of today
    'max_daily_loss': 10000.0,  # FTMO 5% daily limit
    'max_total_drawdown': 20000.0,  # FTMO 10% total limit
    'peak_balance': 200000.0,  # Highest balance ever
    'daily_closed_pnl': 382.0,  # Closed trades today only
}
```

**Then API can calculate correctly:**
```python
daily_pnl = account_data.get('daily_pnl', 0)  # Use EA's value
max_daily_loss = account_data.get('max_daily_loss', 10000)  # Use EA's value
max_total_drawdown = account_data.get('max_total_drawdown', 20000)  # Use EA's value
peak_balance = account_data.get('peak_balance', account_balance)  # Use EA's value

# Calculate distances
daily_loss = max(0.0, -daily_pnl)
distance_to_daily_limit = max(0.0, max_daily_loss - daily_loss)

total_drawdown = max(0.0, peak_balance - account_equity)
distance_to_dd_limit = max(0.0, max_total_drawdown - total_drawdown)
```

### Option 2: API Tracks State (WORKAROUND)

**Store daily start balance:**
```python
# At midnight, store current balance as start_of_day
if is_new_day():
    daily_start_balance = account_balance
    store_to_file(daily_start_balance)

# Calculate daily P&L
daily_pnl = account_equity - daily_start_balance
```

**Problem**: Requires state management, file I/O, timezone handling

---

## 🎯 RECOMMENDED FIX

### Update EA to Send FTMO Data

**In EA (MQL5):**
```mql5
// Get FTMO data
double daily_pnl = AccountInfoDouble(ACCOUNT_PROFIT);  // Today's profit
double daily_start_balance = GetDailyStartBalance();  // Store at midnight
double max_daily_loss = 10000.0;  // FTMO Challenge 1
double max_total_drawdown = 20000.0;  // FTMO Challenge 1
double peak_balance = GetPeakBalance();  // Track highest balance

// Add to JSON request
account_obj.Set("daily_pnl", daily_pnl);
account_obj.Set("daily_start_balance", daily_start_balance);
account_obj.Set("max_daily_loss", max_daily_loss);
account_obj.Set("max_total_drawdown", max_total_drawdown);
account_obj.Set("peak_balance", peak_balance);
```

**Then API will have accurate FTMO data!**

---

## 📊 CURRENT IMPACT

### What's Working:
- ✅ Balance/Equity correct
- ✅ Open position profit correct
- ✅ FTMO protection logic in place
- ✅ Will close positions if limits hit

### What's Wrong:
- ❌ Daily P&L calculation off by ~$158 ($822 vs $664)
- ❌ Daily limit calculation wrong
- ❌ DD limit calculation wrong
- ❌ May not trigger protection at correct thresholds

### Risk Level:
- **LOW** - Protection is still active
- **MEDIUM** - Thresholds are approximate, not exact
- **HIGH** - Could violate FTMO without knowing

---

## ⚠️ TEMPORARY WORKAROUND

Until EA is updated, use conservative estimates:

```python
# Assume worst case for safety
max_daily_loss = 10000.0  # Fixed FTMO limit
max_total_drawdown = 20000.0  # Fixed FTMO limit

# Use equity change as proxy for daily P&L
# (Not perfect but safer than current calculation)
daily_pnl = account_equity - 194220.0  # Approximate start balance

# Calculate conservatively
daily_loss = max(0.0, -daily_pnl)
distance_to_daily_limit = max(0.0, max_daily_loss - daily_loss)

# For DD, use equity vs initial balance
initial_balance = 200000.0  # FTMO starting balance
total_drawdown = max(0.0, initial_balance - account_equity)
distance_to_dd_limit = max(0.0, max_total_drawdown - total_drawdown)
```

---

## ✅ ACTION ITEMS

### Immediate:
1. ✅ Identified the problem
2. ⏳ Implement temporary workaround
3. ⏳ Update EA to send FTMO data

### Short-Term:
1. EA sends daily_pnl, max_daily_loss, max_total_drawdown, peak_balance
2. API uses EA's values instead of calculating
3. Test with real account data
4. Verify accuracy against MetriX

### Long-Term:
1. EA tracks daily start balance (resets at midnight)
2. EA tracks peak balance (updates on new highs)
3. EA sends all FTMO-specific data
4. API just uses what EA sends (no calculation)

---

## 🎯 BOTTOM LINE

**FTMO Monitoring**: ⚠️ ACTIVE BUT INACCURATE

**Current State:**
- Protection logic: ✅ IN PLACE
- Calculation: ❌ APPROXIMATE
- Risk: ⚠️ MEDIUM

**What's Needed:**
- EA must send FTMO-specific data
- API should use EA's values, not calculate
- Then accuracy will be 100%

**Until Then:**
- System will protect account
- But thresholds may be off
- Monitor manually via MetriX

---

**Last Updated**: November 23, 2025, 7:56 PM  
**Status**: FIX NEEDED - EA must send FTMO data
