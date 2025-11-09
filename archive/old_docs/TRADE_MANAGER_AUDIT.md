# 🔍 TRADE MANAGER AUDIT - HARDCODED VALUES FOUND

**Date**: November 20, 2025, 3:52 PM  
**Status**: PARTIALLY AI-DRIVEN (has hardcoded thresholds)

---

## ❌ HARDCODED VALUES FOUND:

### 1. **Asset Class Thresholds** (Lines 290-296):
```python
if any(pair in symbol_lower for pair in forex_pairs):
    base_threshold = 52.0  # ❌ HARDCODED
elif any(idx in symbol_lower for idx in indices):
    base_threshold = 58.0  # ❌ HARDCODED
elif any(comm in symbol_lower for comm in commodities):
    base_threshold = 60.0  # ❌ HARDCODED
```

**Problem**: These thresholds are FIXED and don't adapt to market conditions or performance.

**Should Be**: Using Adaptive Optimizer's `min_ml_confidence` which learns from trades.

---

### 2. **DCA Threshold** (ai_risk_manager.py Line 394):
```python
min_ml_confidence = 52.0  # ❌ HARDCODED
if ml_confidence < min_ml_confidence:
    return {'should_dca': False, ...}
```

**Problem**: Fixed 52% threshold for DCA decisions.

**Should Be**: Using Adaptive Optimizer's threshold.

---

## ✅ WHAT IS AI-DRIVEN:

### 1. **Quality Scoring System**:
- ✅ Multi-timeframe analysis (context.is_multi_timeframe_bullish())
- ✅ Confluence detection (context.has_strong_confluence())
- ✅ Institutional flow (context.is_institutional_activity())
- ✅ Volume divergence penalties (scaled 0.6-1.0 → 0-0.2)
- ✅ Regime alignment bonuses/penalties
- ✅ Trend alignment scoring

### 2. **Bypass Paths** (Lines 363-368):
- ✅ Path 1: ML > base + quality setup
- ✅ Path 2: ML > base+6 + R:R ≥ 2.0 + not ranging
- ✅ Path 3: ML > base+8 + R:R ≥ 1.5
- ✅ Path 4: ML > base+10 (high confidence)

### 3. **Adaptive Optimizer** (adaptive_optimizer.py):
- ✅ Starts at 50% confidence
- ✅ Adjusts based on win rate
- ✅ Increases selectivity if losing
- ✅ Decreases selectivity if winning
- ✅ Learns from trade performance

### 4. **FTMO Protection** (Lines 271, 274):
- ✅ $2000 daily limit buffer (NECESSARY safety)
- ✅ $3000 drawdown limit buffer (NECESSARY safety)

---

## 🔧 WHAT NEEDS FIXING:

### **Issue**: Trade Manager ignores Adaptive Optimizer

**Current Flow**:
1. Adaptive Optimizer sets `min_ml_confidence = 50%`
2. Trade Manager IGNORES it and uses hardcoded 52%/58%/60%
3. Result: Optimizer can't adapt!

**Should Be**:
1. Adaptive Optimizer sets `min_ml_confidence`
2. Trade Manager USES optimizer's threshold
3. Add asset class multiplier (Forex ×1.0, Indices ×1.15, Commodities ×1.2)
4. Result: AI adapts thresholds based on performance!

---

## SUMMARY:

**AI-Driven**: ✅ Quality scoring, bypass paths, penalties/bonuses  
**Hardcoded**: ❌ Base thresholds (52%, 58%, 60%)  
**Adaptive**: ✅ Optimizer exists but NOT USED by Trade Manager  

**Recommendation**: Make Trade Manager use Adaptive Optimizer's threshold instead of hardcoded values.
