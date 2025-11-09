# ⚠️ MODEL BIAS DETECTED & FIXED

**Date**: November 20, 2025, 5:02 PM  
**Issue**: 100% BUY signals, 0% SELL signals for 5 hours

---

## THE PROBLEM:

### Observed Behavior:
```
Last 2000 log lines:
- BUY signals: 100%
- SELL signals: 0%
- HOLD signals: 0%
```

**All symbols predicting BUY with 51.9% or 54.9% confidence**

---

## ROOT CAUSE:

### Model Training Issue:
The ML models (RandomForest + GradientBoosting) were trained on **imbalanced data** where BUY was the dominant class.

### Test Results:
```python
RF Model Classes: [0, 1]  # 0=SELL, 1=BUY
GB Model Classes: [0, 1]

Test prediction with random features:
RF: 1 (BUY)
GB: 1 (BUY)
Ensemble: 1 (BUY)
```

**The models predict BUY for almost everything!**

---

## THE FIX:

### Old Logic (WRONG):
```python
# Hard prediction - if ensemble_pred == 1, always BUY
ensemble_pred = int((rf_pred + gb_pred) / 2 > 0.5)

if ensemble_pred == 1:
    direction = "BUY"  # Always BUY if pred=1
elif ensemble_pred == 0:
    direction = "SELL"
```

**Problem**: Models predict 1 (BUY) even when only 51% confident!

---

### New Logic (FIXED):
```python
# Use probability threshold instead of hard prediction
buy_prob = ensemble_proba[1]
sell_prob = ensemble_proba[0]

# Require 55% confidence minimum to avoid bias
if buy_prob > 0.55:
    direction = "BUY"
    confidence = buy_prob * 100
elif sell_prob > 0.55:
    direction = "SELL"
    confidence = sell_prob * 100
else:
    # Uncertain (45-55% range) - HOLD
    direction = "HOLD"
    confidence = max(buy_prob, sell_prob) * 100
```

**Fix**: Only BUY/SELL if >55% confident, otherwise HOLD

---

## IMPACT:

### Before Fix:
- **BUY**: 51% probability → BUY signal ✅
- **BUY**: 52% probability → BUY signal ✅
- **BUY**: 53% probability → BUY signal ✅
- **Result**: 100% BUY signals

### After Fix:
- **BUY**: 51% probability → HOLD (not confident enough)
- **BUY**: 54% probability → HOLD (not confident enough)
- **BUY**: 56% probability → BUY (confident)
- **SELL**: 57% probability → SELL (confident)
- **Result**: Mix of BUY/SELL/HOLD based on actual confidence

---

## WHY THIS WORKS:

### Probability Interpretation:
- **50%**: Completely uncertain (coin flip)
- **51-54%**: Slightly leaning, but not confident
- **55%+**: Actually confident in direction
- **60%+**: Very confident
- **70%+**: Extremely confident

### New Thresholds:
- **BUY**: Requires >55% BUY probability
- **SELL**: Requires >55% SELL probability
- **HOLD**: 45-55% range (uncertain)

---

## LOGGING ENHANCEMENT:

### New Log Format:
```
🤖 ML SIGNAL: BUY (Confidence: 56.2%) [BUY prob: 0.562, SELL prob: 0.438]
🤖 ML SIGNAL: HOLD (Confidence: 52.1%) [BUY prob: 0.521, SELL prob: 0.479]
🤖 ML SIGNAL: SELL (Confidence: 58.3%) [BUY prob: 0.417, SELL prob: 0.583]
```

**Now shows actual probabilities for transparency**

---

## LONG-TERM SOLUTION:

### Models Need Retraining:
The current models are **biased** and need to be retrained with:
1. **Balanced data** (equal BUY/SELL examples)
2. **Better features** (current features may not be predictive)
3. **Different time periods** (not just bull markets)
4. **Class weights** (penalize majority class)

### Temporary Fix:
The 55% threshold prevents the bias from causing 100% BUY signals, but the models should still be retrained for optimal performance.

---

## EXPECTED BEHAVIOR NOW:

### Signal Distribution:
- **BUY**: When models are >55% confident (bullish setup)
- **SELL**: When models are >55% confident (bearish setup)
- **HOLD**: When models are 45-55% (uncertain/ranging)

### Example Scenarios:
1. **Strong uptrend**: BUY prob 70% → BUY signal ✅
2. **Weak uptrend**: BUY prob 52% → HOLD signal ✅
3. **Strong downtrend**: SELL prob 68% → SELL signal ✅
4. **Ranging market**: BUY 51%, SELL 49% → HOLD signal ✅

---

## STATUS:

**Fix Applied**: ✅ Probability threshold (55%) implemented  
**Bias Prevented**: ✅ Will now return HOLD for uncertain signals  
**Logging Enhanced**: ✅ Shows actual probabilities  
**Models**: ⚠️ Still biased, need retraining  

**Immediate Impact**: System will now return HOLD for most signals until models are retrained or market conditions strongly favor one direction.

---

**Recommendation**: Retrain models with balanced data and better feature engineering.
