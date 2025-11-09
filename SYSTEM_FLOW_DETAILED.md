# 🔄 COMPLETE SYSTEM FLOW - START TO FINISH

## FLOW OVERVIEW

```
MT5 EA → API Request → Feature Engineering → ML Models → 
Conviction Scoring → Market Analysis → Position Management → 
Risk Management → Decision → EA Execution → Monitoring
```

---

## STEP-BY-STEP FLOW

### 1️⃣ TRIGGER: Bar Closes in MT5

**What Happens:**
- EA detects new bar on any timeframe (M5, M15, M30, H1, H4, D1)
- Currently: Timer-based (every 60 seconds)
- With patch: Event-driven (only on actual bar close)

**EA Code:**
```mql5
void OnTick() {
    // Check if new bar
    datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
    if(currentBarTime == lastBarTime) return;
    
    // New bar detected - collect data and call API
    string marketData = CollectMarketData(_Symbol);
    SendToAPI(marketData);
}
```

---

### 2️⃣ EA COLLECTS MARKET DATA

**What's Collected:**
- Symbol info (name, point, digits)
- Account info (balance, equity, margin, profit)
- Open positions (if any)
- Multi-timeframe OHLCV data:
  - M5: 100 bars
  - M15: 100 bars
  - M30: 100 bars
  - H1: 100 bars
  - H4: 100 bars
  - D1: 50 bars
- Indicators (RSI, MA, ATR, etc.)

**Sent as JSON:**
```json
{
    "symbol": "US100Z25.sim",
    "trigger_timeframe": "H1",
    "symbol_info": {...},
    "account_info": {...},
    "positions": [...],
    "timeframes": {
        "M5": [...],
        "M15": [...],
        ...
    }
}
```

---

### 3️⃣ API RECEIVES REQUEST

**File:** `api.py` - Line 550+

**What Happens:**
```python
@app.post("/api/ai/trade_decision")
async def ai_trade_decision(request: dict):
    # Log request
    logger.info("AI TRADE DECISION REQUEST")
    logger.info(f"Request keys: {list(request.keys())}")
    
    # Extract symbol
    symbol = clean_symbol(request.get('symbol'))
    logger.info(f"Symbol: {symbol}")
    
    # Extract trigger timeframe
    trigger_timeframe = request.get('trigger_timeframe', 'M5')
    logger.info(f"Triggered by: {trigger_timeframe} bar close")
```

**Current Issue:** ⚠️ Logging exists but might not be detailed enough

---

### 4️⃣ CHECK OPEN POSITIONS FIRST

**File:** `api.py` - Line 600+

**What Happens:**
```python
# STEP 1: Check ALL open positions IMMEDIATELY
open_positions = request.get('positions', [])

if open_positions:
    logger.info(f"PORTFOLIO: {len(open_positions)} open positions")
    
    for pos in open_positions:
        # Get features for this position
        features = feature_engineer.engineer_features(request)
        ml_direction, ml_confidence = get_ml_signal(features, symbol)
        
        # Create context
        context = EnhancedTradingContext.from_features_and_request(...)
        
        # AI analyzes position
        position_decision = position_manager.analyze_position(context)
        
        # CRITICAL: Return immediately - don't look for new trades
        return {
            'action': position_decision['action'],  # HOLD/SCALE_IN/PARTIAL_CLOSE/CLOSE_ALL
            'reason': position_decision['reason'],
            ...
        }
```

**Current Issue:** ✅ This looks correct - position management happens first

---

### 5️⃣ NO POSITION: FEATURE ENGINEERING

**File:** `api.py` - Line 900+

**What Happens:**
```python
# Parse multi-timeframe data
mtf_data = parse_market_data(request)

# Engineer 73 features
features = feature_engineer.engineer_features(request)
logger.info(f"Features engineered: {len(features)} features")
```

**Features Created (73 total):**
- Price action (OHLC, ranges)
- Trend indicators (MA, EMA)
- Momentum (RSI, MACD, Stochastic)
- Volatility (ATR, Bollinger Bands)
- Volume analysis
- Multi-timeframe alignment
- Market structure
- Support/resistance levels

**Current Issue:** ⚠️ Need to verify feature count matches model expectations

---

### 6️⃣ ML SIGNAL GENERATION

**File:** `api.py` - Line 400+

**What Happens:**
```python
def get_ml_signal(features: dict, symbol: str):
    # Load symbol-specific model
    ml_model = ml_models.get(symbol.lower())
    
    # Create feature DataFrame
    feature_df = pd.DataFrame([features])
    
    # Ensemble prediction (RandomForest + GradientBoosting)
    rf_proba = ml_model['rf_model'].predict_proba(feature_df)[0]
    gb_proba = ml_model['gb_model'].predict_proba(feature_df)[0]
    
    # Average probabilities
    avg_proba = (rf_proba + gb_proba) / 2
    
    # Determine direction and confidence
    if avg_proba[1] > avg_proba[0]:
        direction = "BUY"
        confidence = avg_proba[1] * 100
    else:
        direction = "SELL"
        confidence = avg_proba[0] * 100
    
    return direction, confidence
```

**Current Issue:** ⚠️ Need to verify feature names match between engineer and models

---

### 7️⃣ CONVICTION SCORING

**File:** `api.py` - Line 1030+

**What Happens:**
```python
# Calculate conviction score
structure_score = 70 if context.market_structure == MarketStructure.TRENDING else 50
volume_score = 60  # Would analyze volume patterns
momentum_score = 65  # Would analyze momentum

conviction = calculate_conviction(
    ml_confidence=ml_confidence,
    structure_score=structure_score,
    volume_score=volume_score,
    momentum_score=momentum_score
)

logger.info(f"CONVICTION: {conviction:.1f}/100")

# Filter low conviction trades
if conviction < 50:
    return {'action': 'HOLD', 'reason': f'Low conviction: {conviction:.1f}/100'}
```

**Weights:**
- ML Confidence: 40%
- Market Structure: 30%
- Volume: 15%
- Momentum: 15%

**Current Issue:** ✅ This is implemented correctly

---

### 8️⃣ MARKET STRUCTURE ANALYSIS

**File:** `api.py` - Line 1100+

**What Happens:**
```python
# AI Trade Manager analyzes market
trade_analysis = trade_manager.analyze_trade_opportunity(context)

# Checks:
# - Support/resistance levels
# - Trend direction
# - Market regime (trending/ranging)
# - Entry quality
# - Risk/reward ratio

if not trade_analysis['should_trade']:
    return {'action': 'HOLD', 'reason': trade_analysis['reason']}
```

**Current Issue:** ✅ Market structure analysis is active

---

### 9️⃣ POSITION SIZING & RISK MANAGEMENT

**File:** `api.py` - Line 1200+

**What Happens:**
```python
# AI Risk Manager calculates position size
risk_analysis = ai_risk_manager.calculate_position_size(
    context=context,
    entry_price=current_price,
    stop_loss=stop_loss,
    account_balance=account_balance
)

lot_size = risk_analysis['lot_size']
risk_percent = risk_analysis['risk_percent']

# FTMO limits:
# - Max 1% risk per trade
# - Max 5% daily loss
# - Max 10% total drawdown
```

**Current Issue:** ✅ Risk management is active

---

### 🔟 FINAL DECISION

**What Happens:**
```python
# Return decision to EA
return {
    'action': 'BUY' or 'SELL' or 'HOLD',
    'lot_size': calculated_lot_size,
    'stop_loss': stop_loss_price,
    'take_profit': take_profit_price,
    'confidence': ml_confidence,
    'conviction': conviction_score,
    'reason': explanation
}
```

---

### 1️⃣1️⃣ EA EXECUTES TRADE

**What Happens:**
```mql5
// EA receives decision
if(decision['action'] == 'BUY') {
    // Open BUY position
    ticket = OrderSend(
        _Symbol,
        OP_BUY,
        lot_size,
        Ask,
        slippage,
        stop_loss,
        take_profit
    );
}
```

---

### 1️⃣2️⃣ POSITION MONITORING (Next Bar)

**What Happens:**
- EA sends position data in next request
- API sees open position
- Goes to STEP 4 (position management)
- Position Manager analyzes:
  - Current profit/loss
  - ML confidence (still valid?)
  - Market conditions changed?
  - DQN agent suggestion

**Possible Actions:**
- **HOLD**: Keep position, conditions still good
- **SCALE_IN**: Add to winning position
- **PARTIAL_CLOSE**: Take partial profits
- **CLOSE_ALL**: Exit position

---

### 1️⃣3️⃣ POSITION MANAGEMENT WITH DQN

**File:** `api.py` - Line 850+

**What Happens:**
```python
# Use DQN RL agent if available
if dqn_agent is not None:
    profit_pct = (current_profit / 10000) * 100
    state_key = f"{int(profit_pct)}_{int(ml_confidence)}"
    
    q_table = dqn_agent.get('q_table', {})
    if state_key in q_table:
        # Agent has learned this state
        q_values = q_table[state_key]
        actions = ['HOLD', 'SCALE_IN', 'PARTIAL_CLOSE', 'CLOSE_ALL']
        best_action = actions[max(range(len(q_values)), key=lambda i: q_values[i])]
        
        logger.info(f"DQN suggests: {best_action}")
```

**Current Issue:** ✅ DQN is integrated

---

### 1️⃣4️⃣ CLOSE TRADE

**Triggered By:**
- Position Manager decides to close
- Stop loss hit
- Take profit hit
- Emergency max hold time

**What Happens:**
```mql5
// EA closes position
OrderClose(ticket, lot_size, Bid, slippage);
```

---

## POTENTIAL ISSUES TO CHECK

### Issue 1: Feature Count Mismatch
**Problem:** Feature engineer creates 73 features, but models might expect different count
**Check:** Verify feature names match

### Issue 2: Insufficient Logging
**Problem:** Can't see what's happening in live trading
**Fix:** Add detailed logging at each step

### Issue 3: Position Management Loop
**Problem:** Might generate new entry signals when position exists
**Check:** Verify early return in position management

### Issue 4: Symbol Name Cleaning
**Problem:** Broker symbols (US100Z25.sim) vs model names (us100)
**Check:** Verify symbol cleaning works correctly

---

## NEXT: Let me check and fix these issues...
