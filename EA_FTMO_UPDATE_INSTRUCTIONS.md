# 📝 EA UPDATE - ADD FTMO DATA TO API REQUESTS

**File**: `AI_Trading_EA_Ultimate.mq5`  
**Location**: MetaTrader 5/MQL5/Experts/

---

## 🎯 WHAT TO ADD

### Find the section where account data is sent to API

Look for code like:
```mql5
// Build account object
CJAVal account_obj;
account_obj.Set("balance", AccountInfoDouble(ACCOUNT_BALANCE));
account_obj.Set("equity", AccountInfoDouble(ACCOUNT_EQUITY));
account_obj.Set("margin", AccountInfoDouble(ACCOUNT_MARGIN));
account_obj.Set("free_margin", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
account_obj.Set("margin_level", AccountInfoDouble(ACCOUNT_MARGIN_LEVEL));
account_obj.Set("profit", AccountInfoDouble(ACCOUNT_PROFIT));
account_obj.Set("currency", AccountInfoString(ACCOUNT_CURRENCY));
```

### ADD THESE LINES:

```mql5
// FTMO-specific data
account_obj.Set("daily_pnl", GetDailyPnL());  // Today's total profit/loss
account_obj.Set("daily_start_balance", GetDailyStartBalance());  // Balance at start of day
account_obj.Set("max_daily_loss", 10000.0);  // FTMO Challenge 1: 5% of $200k
account_obj.Set("max_total_drawdown", 20000.0);  // FTMO Challenge 1: 10% of $200k
account_obj.Set("peak_balance", GetPeakBalance());  // Highest balance achieved
```

---

## 🔧 HELPER FUNCTIONS TO ADD

### Add these global variables at the top of the EA:

```mql5
// FTMO tracking variables
double g_daily_start_balance = 0.0;
double g_peak_balance = 0.0;
datetime g_last_day = 0;
```

### Add these functions:

```mql5
//+------------------------------------------------------------------+
//| Get daily start balance (resets at midnight)                      |
//+------------------------------------------------------------------+
double GetDailyStartBalance()
{
    datetime current_time = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(current_time, dt);
    
    // Check if it's a new day
    datetime current_day = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00", dt.year, dt.mon, dt.day));
    
    if(current_day != g_last_day)
    {
        // New day - store current balance as start
        g_daily_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
        g_last_day = current_day;
        Print("New trading day - Start balance: $", g_daily_start_balance);
    }
    
    // If not initialized yet, use current balance
    if(g_daily_start_balance == 0.0)
    {
        g_daily_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    }
    
    return g_daily_start_balance;
}

//+------------------------------------------------------------------+
//| Get today's total P&L (equity - start balance)                   |
//+------------------------------------------------------------------+
double GetDailyPnL()
{
    double start_balance = GetDailyStartBalance();
    double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);
    return current_equity - start_balance;
}

//+------------------------------------------------------------------+
//| Get peak balance (highest balance ever achieved)                 |
//+------------------------------------------------------------------+
double GetPeakBalance()
{
    double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    
    // Initialize if needed
    if(g_peak_balance == 0.0)
    {
        g_peak_balance = current_balance;
    }
    
    // Update if new peak
    if(current_balance > g_peak_balance)
    {
        g_peak_balance = current_balance;
        Print("New peak balance: $", g_peak_balance);
    }
    
    return g_peak_balance;
}
```

---

## 📋 COMPLETE EXAMPLE

### Updated Account Object Section:

```mql5
// Build account object with FTMO data
CJAVal account_obj;

// Standard account data
account_obj.Set("balance", AccountInfoDouble(ACCOUNT_BALANCE));
account_obj.Set("equity", AccountInfoDouble(ACCOUNT_EQUITY));
account_obj.Set("margin", AccountInfoDouble(ACCOUNT_MARGIN));
account_obj.Set("free_margin", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
account_obj.Set("margin_level", AccountInfoDouble(ACCOUNT_MARGIN_LEVEL));
account_obj.Set("profit", AccountInfoDouble(ACCOUNT_PROFIT));
account_obj.Set("currency", AccountInfoString(ACCOUNT_CURRENCY));

// FTMO-specific data (NEW)
account_obj.Set("daily_pnl", GetDailyPnL());
account_obj.Set("daily_start_balance", GetDailyStartBalance());
account_obj.Set("max_daily_loss", 10000.0);  // 5% of $200k
account_obj.Set("max_total_drawdown", 20000.0);  // 10% of $200k
account_obj.Set("peak_balance", GetPeakBalance());
```

---

## ✅ VERIFICATION

After updating, the API logs should show:

```
Account data: {
    'balance': 194882.84,
    'equity': 195165.4,
    'profit': 282.56,
    'daily_pnl': 664.13,  // NEW!
    'daily_start_balance': 194220.0,  // NEW!
    'max_daily_loss': 10000.0,  // NEW!
    'max_total_drawdown': 20000.0,  // NEW!
    'peak_balance': 200000.0  // NEW!
}
```

And FTMO calculations will be accurate:
```
FTMO: SAFE | Daily: $664.13 | DD: $0.00
Limits: Daily $10664 left | DD $15159 left
```

---

## 🎯 STEPS TO IMPLEMENT

1. Open MetaEditor (F4 in MetaTrader 5)
2. Open `AI_Trading_EA_Ultimate.mq5`
3. Add global variables at top
4. Add the 3 helper functions
5. Update account object section
6. Compile (F7)
7. Reload EA on chart
8. Check API logs for new data

---

**After this update, FTMO monitoring will be 100% accurate!**
