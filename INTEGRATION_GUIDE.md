# ELITE POSITION SIZER - INTEGRATION GUIDE

## ✅ COMPLETED: Phase 1 - New Components Added

### Files Created:
1. **`src/ai/portfolio_state.py`** - Portfolio correlation & performance tracking
2. **`src/ai/elite_position_sizer.py`** - Elite hedge fund position sizing
3. **`api.py`** - Imports and initialization added (lines 33-35, 71-74, 185-198)

### What Was Added:
- ✅ Portfolio correlation matrix (forex, indices, commodities)
- ✅ Diversification factor calculation
- ✅ Recent performance tracking (win rate, Sharpe)
- ✅ Performance multiplier (0.7x-1.3x based on recent results)
- ✅ CVaR (tail risk) calculation
- ✅ Dynamic risk budgeting
- ✅ Regime-based allocation
- ✅ Symbol-specific limits (USOIL max 10 lots!)
- ✅ Notional exposure caps
- ✅ Portfolio concentration limits

### Flag to Switch:
```python
# In api.py line 74:
USE_ELITE_SIZER = True  # ✅ Set to True to use elite sizer
```

---

## 🔄 Phase 2 - Integration (NEXT STEP)

### Option A: Modify Unified System (Recommended)

**File:** `src/ai/unified_trading_system.py`

**Change line 218-240** from:
```python
position_info = self.position_sizer.calculate_position_size(...)
```

**To:**
```python
# Check if elite sizer should be used
from api import USE_ELITE_SIZER, elite_sizer, portfolio_state

if USE_ELITE_SIZER and elite_sizer:
    # Use elite sizer
    position_info = elite_sizer.calculate_position_size(
        account_balance=account_balance,
        ml_confidence=ml_confidence * 100,  # Convert to 0-100
        market_score=market_score,
        entry_price=current_price,
        stop_loss=stop_loss,
        target_price=take_profit,
        tick_value=tick_value,
        tick_size=tick_size,
        contract_size=contract_size,
        symbol=context.symbol,
        direction=direction,
        regime=context.get_market_regime(),
        volatility=context.volatility if hasattr(context, 'volatility') else 0.5,
        current_atr=context.atr if hasattr(context, 'atr') else 0.0,
        open_positions=context.open_positions if hasattr(context, 'open_positions') else [],
        ftmo_distance_to_daily=ftmo_daily_dist,
        ftmo_distance_to_dd=ftmo_dd_dist,
        max_lot_broker=max_lot_broker,
        min_lot=min_lot,
        lot_step=lot_step
    )
else:
    # Use old sizer (fallback)
    position_info = self.position_sizer.calculate_position_size(...)
```

---

### Option B: Wrapper Function (Safer)

**File:** `api.py` (add after line 1348)

```python
# After unified system calculates lot_size
if USE_ELITE_SIZER and elite_sizer:
    logger.info("🏆 Recalculating with ELITE SIZER...")
    
    # Get regime from context
    regime = context.get_market_regime()
    
    # Recalculate with elite sizer
    elite_result = elite_sizer.calculate_position_size(
        account_balance=account_balance,
        ml_confidence=ml_confidence,
        market_score=market_analysis['total_score'],
        entry_price=current_price,
        stop_loss=stop_loss_price,
        target_price=take_profit_price,
        tick_value=tick_value,
        tick_size=symbol_info.get('tick_size', 0.01),
        contract_size=contract_size,
        symbol=symbol,
        direction=ml_direction,
        regime=regime,
        volatility=context.volatility if hasattr(context, 'volatility') else 0.5,
        current_atr=context.atr if hasattr(context, 'atr') else 0.0,
        open_positions=open_positions,
        ftmo_distance_to_daily=ftmo_distance_to_daily,
        ftmo_distance_to_dd=ftmo_distance_to_dd,
        max_lot_broker=symbol_info.get('max_lot', 50.0),
        min_lot=symbol_info.get('min_lot', 1.0),
        lot_step=symbol_info.get('lot_step', 1.0)
    )
    
    # Override lot size
    final_lots = elite_result['lot_size']
    logger.info(f"   Elite sizer: {final_lots:.2f} lots (was {entry_decision['lot_size']:.2f})")
```

---

## 🎯 Phase 3 - Testing (AFTER Integration)

### Test Plan:

**1. Test with Elite Sizer OFF:**
```python
USE_ELITE_SIZER = False
# Should work exactly as before (no breaking changes)
```

**2. Test with Elite Sizer ON:**
```python
USE_ELITE_SIZER = True
# Should see:
# - "🏆 ELITE POSITION SIZING" in logs
# - Portfolio correlation calculations
# - Diversification factors
# - Performance multipliers
# - CVaR tail risk
# - USOIL capped at 10 lots (not 50!)
```

**3. Verify Logs:**
```bash
tail -f /tmp/ai_trading_api.log | grep -E "ELITE|Portfolio|Diversification|Performance|CVaR"
```

**Expected Output:**
```
🏆 ELITE POSITION SIZING - USOILF26
   Account: $180,791
   ML: 75.0% | Market Score: 68
   Regime: TRENDING | Volatility: 1.20%
   R:R: 3.00:1 | Expected Return: 1.75
   📈 Trending market: 1.2x multiplier
   Portfolio Correlation: 0.35 (lower = better diversification)
   Diversification Factor: 0.82x
   Recent Performance: WR=60.0%, Avg=$150, Sharpe=0.85
   Performance Multiplier: 1.30x
   CVaR (95%): 0.00150 (vs stop: 0.00100)
   Base Trade Risk: $396
   Adjusted Risk: $378
   Risk per lot (CVaR): $15.00
   Base size: 25.2 lots
   
   📊 CONSTRAINTS:
      Symbol max: 10.0 lots (OIL)  ← ✅ CAPPED!
      Notional max: 18.0 lots ($18,079)
      FTMO max: 120.0 lots
      Concentration max: 25.2 lots
   
   ✅ FINAL SIZE: 10.00 lots  ← ✅ NOT 50!
   💰 FINAL RISK: $150
```

---

## 🔧 Phase 4 - Fine Tuning (OPTIONAL)

### Adjust Parameters:

**In `elite_position_sizer.py`:**
```python
# Line 23-24: Risk parameters
self.base_risk_pct = 0.011  # 1.1% of account per trade
self.max_concentration = 0.30  # Max 30% of daily budget

# Line 27-32: Symbol limits
self.symbol_limits = {
    'FOREX': {'max_lots': 10.0, 'max_notional_pct': 0.20},
    'GOLD': {'max_lots': 25.0, 'max_notional_pct': 0.15},
    'INDICES': {'max_lots': 10.0, 'max_notional_pct': 0.10},
    'OIL': {'max_lots': 10.0, 'max_notional_pct': 0.10},  ← Adjust here
}
```

**In `portfolio_state.py`:**
```python
# Line 24-39: Correlation matrix
self.correlation_matrix = {
    ('eurusd', 'gbpusd'): 0.7,  ← Adjust correlations
    ...
}
```

---

## 📊 Benefits vs Old System

### Old System:
- ❌ 50 lots on USOIL = $955 loss
- ❌ No portfolio correlation
- ❌ No performance feedback
- ❌ Fixed risk % regardless of recent results
- ❌ No tail risk consideration

### Elite System:
- ✅ 10 lots max on USOIL = $200 max loss
- ✅ Sizes down if correlated with existing positions
- ✅ Sizes down if recent performance poor
- ✅ Sizes up if recent performance good
- ✅ Uses CVaR (tail risk) not just stop distance
- ✅ Regime-aware (sizes up in trends)
- ✅ Notional exposure caps
- ✅ Portfolio concentration limits

---

## 🚀 Rollback Plan

If elite sizer causes issues:

**1. Immediate:**
```python
USE_ELITE_SIZER = False  # Back to old system
```

**2. Remove (if needed):**
```python
# In api.py, comment out lines 33-35, 71-74, 185-198
# Old system will work exactly as before
```

**3. Delete files (if needed):**
```bash
rm src/ai/elite_position_sizer.py
rm src/ai/portfolio_state.py
```

---

## ✅ SAFETY GUARANTEES

1. **No Breaking Changes** - Old system still works if `USE_ELITE_SIZER = False`
2. **Parallel Implementation** - Elite sizer runs alongside, doesn't replace
3. **Easy Rollback** - Single flag to switch back
4. **Backward Compatible** - All old code paths preserved
5. **Tested Separately** - Can test elite sizer without affecting production

---

## 📝 NEXT STEPS

**Choose Integration Method:**
- [ ] Option A: Modify unified_trading_system.py (cleaner)
- [ ] Option B: Add wrapper in api.py (safer)

**Then:**
1. Restart API
2. Watch logs for "🏆 ELITE POSITION SIZING"
3. Verify USOIL capped at 10 lots
4. Monitor for 1 hour
5. If good, leave enabled
6. If issues, set `USE_ELITE_SIZER = False`

---

END OF INTEGRATION GUIDE
