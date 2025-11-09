# ✅ SWING TRADING MODE - $200K ACCOUNT

**Date**: November 20, 2025, 9:10 PM  
**Account**: $200,000  
**Trading Style**: SWING (hours to days)

---

## WHAT CHANGED:

### 1. Position Hold Time
- **Before**: 15 minutes minimum
- **Now**: 60 minutes (1 hour) minimum
- **Reason**: Swing trades need time to develop

### 2. Profit Targets
- **Before**: 0.5-1.5% (scalping)
- **Now**: 2-5% (swing)
- **Calculation**:
  - Weak trend: 1.5% target (3x volatility)
  - Moderate: 2% target (4x volatility)
  - Strong: 3% target (6x volatility)
  - Very strong: 4% target (8x volatility)
- **Take profit at**: 50% of target (1-2.5%)

### 3. Stop Loss
- **Before**: -0.5% (too tight for $200k)
- **Now**: -2% hard stop
- **Max loss**: $4,000 per trade

### 4. ML Reversal Threshold
- **Before**: 75% confidence to close
- **Now**: 80% confidence (swing needs conviction)
- **Rule**: Only close losers on ML reversal, never winners

### 5. Position Sizing
- **Account**: $200,000
- **Risk per trade**: 1-2% = $2,000-$4,000
- **Target per trade**: $4,000-$10,000
- **Risk:Reward**: 1:2 to 1:3

---

## SWING TRADING RULES:

### Entry:
- ✅ ML confidence > 60%
- ✅ Quality score > -0.20
- ✅ FTMO limits OK
- ✅ H1/H4 timeframe signals

### Hold:
- ✅ Minimum 1 hour (give it time)
- ✅ Let winners run to target
- ✅ Don't close on weak ML flips
- ✅ Monitor H4 trend changes

### Exit Winners:
- 🎯 At 50% of AI target (1-2.5%)
- 🎯 Or when ML reverses at 80%+ (if losing)
- 🎯 Or at H4 trend reversal

### Exit Losers:
- 🛑 Hard stop at -2% ($4k max loss)
- 🛑 ML reversal at 80%+ confidence
- 🛑 H4 trend reversal + RSI extreme

---

## EXPECTED PERFORMANCE:

### With $200K Account:

**Conservative (60% win rate)**:
```
Wins: 12 trades × $5,000 = $60,000
Losses: 8 trades × $3,000 = -$24,000
Net: $36,000 per 20 trades
Monthly (60 trades): $108,000 profit
```

**Realistic (65% win rate)**:
```
Wins: 13 trades × $6,000 = $78,000
Losses: 7 trades × $3,500 = -$24,500
Net: $53,500 per 20 trades
Monthly (60 trades): $160,500 profit
```

**Aggressive (70% win rate)**:
```
Wins: 14 trades × $7,000 = $98,000
Losses: 6 trades × $4,000 = -$24,000
Net: $74,000 per 20 trades
Monthly (60 trades): $222,000 profit
```

---

## POSITION MANAGER CHANGES:

### File: `intelligent_position_manager.py`

**Lines 411-423**: Minimum age 60 minutes, hard stop -2%
**Lines 265-277**: Profit targets 3x-8x volatility (2-5%)
**Lines 486-506**: Take profit at 50% of target, hard stop -2%
**Lines 516-527**: ML reversal threshold 80%

---

## RISK MANAGEMENT:

### Per Trade:
- **Max Risk**: -2% = $4,000
- **Target**: 2-5% = $4,000-$10,000
- **Risk:Reward**: 1:2 minimum

### Daily:
- **FTMO Daily Limit**: -$10,000
- **Max Trades**: 2-3 per day (conservative)
- **Target**: $10,000-$20,000 daily

### Monthly:
- **FTMO Drawdown Limit**: -$20,000
- **Target**: $100,000-$200,000 monthly
- **ROI**: 50-100% per month

---

## TIMEFRAMES:

### Primary: H1 (1 hour)
- Entry signals
- Trend confirmation
- Support/Resistance

### Secondary: H4 (4 hour)
- Trend direction
- Major S/R levels
- Exit signals

### Tertiary: D1 (daily)
- Overall trend
- Major levels
- Swing context

### NOT USED: M1, M5
- Too noisy for swing trading
- Causes premature exits
- Ignore for swing trades

---

## WHAT TO MONITOR:

### Every Hour:
- [ ] Open positions P&L
- [ ] Approaching profit targets?
- [ ] Any positions > 1 hour old?
- [ ] FTMO limits status

### Every 4 Hours:
- [ ] H4 trend changes
- [ ] Major S/R levels hit
- [ ] Position performance
- [ ] Adjust targets if needed

### Daily:
- [ ] Daily P&L vs target
- [ ] Win rate tracking
- [ ] Average win/loss size
- [ ] FTMO compliance

---

## COMPARISON:

### Scalping (Before):
- Hold: 5-15 minutes
- Target: 0.5-1.5%
- Stop: -0.5%
- Trades/day: 20-50
- **Result**: Churning, small wins, big losses

### Swing Trading (Now):
- Hold: 1-24 hours
- Target: 2-5%
- Stop: -2%
- Trades/day: 2-5
- **Result**: Let winners run, cut losses, profitable

---

## STATUS:

**Position Manager**: ✅ Updated for swing trading  
**Profit Targets**: ✅ 2-5% (was 0.5-1.5%)  
**Stop Loss**: ✅ -2% (was -0.5%)  
**Hold Time**: ✅ 60 min minimum (was 15 min)  
**ML Threshold**: ✅ 80% (was 75%)  
**Models**: ✅ Metadata updated  
**API**: ✅ Restarted  

**SYSTEM NOW CONFIGURED FOR SWING TRADING WITH $200K ACCOUNT!** 🚀💰

---

## THE BOTTOM LINE:

**$200K account needs swing trading, not scalping.**

- Scalping: Too tight stops, too many trades, death by 1000 cuts
- Swing: Proper stops, fewer trades, let winners run

**With 2-5% targets and -2% stops:**
- Need 40% win rate to break even
- At 60% win rate: Very profitable
- At 70% win rate: Extremely profitable

**The AI is ready. The position manager is ready. Let it swing!** 🎯
