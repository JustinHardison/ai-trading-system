# TECHNICAL DEBT LOG

## 2025-11-28 - Critical Issues

### 1. Position State Tracker Data Loss on Restart ❌ CRITICAL
**Priority:** P0 - CRITICAL
**Impact:** All position tracking data lost on API restart
**Root Cause:** In-memory global variable `_tracker = None` in `position_state_tracker.py`
**Affected Features:**
- Peak profit tracking
- Add count (pyramiding)
- DCA count
- Entry time tracking
- Position age tracking

**Solution:** NOT NEEDED - MT5 already provides this data!
- EA sends `time` (entry time) in positions array
- EA sends `age_minutes` (calculated age) in positions array
- EA sends `recent_trades` (last 24 hours history)
- API just needs to USE this data instead of tracking separately

**Files to Fix:**
- `api.py` - Extract `time` and `age_minutes` from positions
- Remove dependency on `position_state_tracker.py` for basic data
- Use tracker only for peak_profit and add/dca counts

---

### 2. Partial Exits Not Working ❌ CRITICAL
**Priority:** P0 - CRITICAL
**Impact:** Cannot lock in profits, missing profit protection
**Root Cause:** EV Exit Manager returns early for tiny profits/losses before calculating continuation/reversal probabilities
**Code Location:** `src/ai/ev_exit_manager.py` lines 115-123

**Current Flow:**
```python
if profit_pct < 0.2:
    return {'action': 'HOLD'}  # ❌ RETURNS EARLY!
    # Never reaches continuation/reversal calculation
```

**Solution:** 
1. Calculate continuation/reversal for ALL positions
2. Apply tiny profit/loss thresholds AFTER EV calculation
3. OR: Only skip EV for profits < 0.1% (not 0.2%)

**Files to Fix:**
- `src/ai/ev_exit_manager.py`

---

### 3. Pyramiding Not Working ❌ HIGH
**Priority:** P1 - HIGH
**Impact:** Cannot add to winning positions
**Root Cause:** Missing position age and add_count from tracker
**Solution:** Use `age_minutes` from MT5 positions data

**Files to Fix:**
- `api.py` - Extract and use `age_minutes` from positions
- Check `age_minutes < 30` for pyramiding criteria

---

### 4. DCA Not Working ❌ HIGH
**Priority:** P1 - HIGH
**Impact:** Cannot add to losing positions when AI confident
**Root Cause:** Missing position age and dca_count from tracker
**Solution:** Use `age_minutes` from MT5 positions data

**Files to Fix:**
- `api.py` - Extract and use `age_minutes` from positions
- Check `age_minutes < 30` for DCA criteria
- Track dca_count in persistent storage OR derive from position history

---

### 5. Missing $1,682 Loss Event ⚠️ MEDIUM
**Priority:** P2 - MEDIUM
**Impact:** Unknown cause of large loss
**Time:** Between 04:48 AM and 08:14 AM on 2025-11-28
**Evidence:** No CLOSE decisions in API logs

**Possible Causes:**
1. Manual close in MT5
2. EA closed without API
3. Stop loss hit
4. FTMO protection

**Solution:** 
1. Check `recent_trades` array for closed positions
2. Log all position closes with reason
3. Add position reconciliation on each scan

**Files to Fix:**
- `api.py` - Add position reconciliation logic
- Log when positions disappear without API close decision

---

### 6. API Not Using MT5 Position Data ❌ HIGH
**Priority:** P1 - HIGH
**Impact:** Reinventing the wheel, data already available
**Root Cause:** API extracts only basic position data, ignores rich metadata

**MT5 Sends (but API ignores):**
- ✅ `ticket` - Unique position ID
- ✅ `time` - Entry timestamp
- ✅ `age_minutes` - Position age (calculated by EA)
- ✅ `recent_trades` - Last 24h of closed trades
- ❌ API only uses: symbol, profit, volume, type, price_open

**Solution:**
Extract ALL position data from MT5:
```python
pos_ticket = pos.get('ticket')
pos_time = pos.get('time')  # Unix timestamp
pos_age_minutes = pos.get('age_minutes')
```

**Files to Fix:**
- `api.py` lines 689-718 - Extract all position metadata
- Use this data for pyramiding/DCA age checks
- Use ticket for position tracking

---

### 7. Recent Trades Not Being Used ❌ MEDIUM
**Priority:** P2 - MEDIUM
**Impact:** Missing opportunity to learn from recent closes
**Root Cause:** EA sends `recent_trades` but API doesn't process it

**MT5 Sends:**
```json
"recent_trades": [
  {"ticket": 123, "profit": -500.00, "volume": 5.0},
  {"ticket": 124, "profit": 200.00, "volume": 3.0}
]
```

**Solution:**
1. Extract recent_trades from request
2. Log recent closes for analysis
3. Use for position reconciliation
4. Track win rate and profit factor

**Files to Fix:**
- `api.py` - Extract and log recent_trades
- Add trade history analysis

---

## Summary

**Critical Issues (P0):** 3
- Position data not extracted from MT5
- Partial exits not working
- Data loss on restart (SOLVED by using MT5 data)

**High Priority (P1):** 3
- Pyramiding not working
- DCA not working
- Not using MT5 position metadata

**Medium Priority (P2):** 2
- Missing loss event investigation
- Recent trades not used

**Total Technical Debt Items:** 7

---

## Next Actions

1. **IMMEDIATE:** Extract `time`, `age_minutes`, `ticket` from positions
2. **IMMEDIATE:** Fix partial exit logic flow
3. **TODAY:** Add position reconciliation using recent_trades
4. **TODAY:** Enable pyramiding/DCA using age_minutes
5. **THIS WEEK:** Investigate $1,682 loss event

---

END OF TECHNICAL DEBT LOG
