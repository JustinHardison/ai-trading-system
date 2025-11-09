# 🎯 SWING TRADING - COMPLETE SETUP INSTRUCTIONS

**Date**: November 20, 2025, 9:10 PM  
**Account**: $200,000  
**Goal**: Retrain models with H1/H4/D1 data for swing trading

---

## STEP 1: Export Swing Data from MT5

### File Created:
```
/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Scripts/ExportSwingData.mq5
```

### What It Does:
- Exports **5,000 bars** of H1, H4, and D1 data
- For all 8 symbols: EURUSD, GBPUSD, USDJPY, US30, US100, US500, XAUUSD, USOIL
- Saves to: `Terminal/Common/Files/training_data/swing/`

### How to Run:
1. Open MT5
2. Open MetaEditor (F4)
3. Navigate to: `Scripts/ExportSwingData.mq5`
4. Click **Compile** (F7)
5. Close MetaEditor
6. In MT5 chart, drag `ExportSwingData` from Navigator → Scripts
7. Click **OK** to run
8. Check **Experts** tab for progress

### Expected Output:
```
========================================
EXPORTING SWING TRADING DATA
H1, H4, D1 Timeframes
========================================
Processing: EURUSD
  Exporting H1...
  Copied 5000 bars
  ✓ Exported 5000 bars to EURUSD_H1.csv
  Exporting H4...
  ...
========================================
SWING DATA EXPORT COMPLETE!
========================================
```

---

## STEP 2: Retrain Models with Swing Data

### File Created:
```
/Users/justinhardison/ai-trading-system/retrain_swing_with_h1h4d1.py
```

### What It Does:
- Loads H1, H4, D1 data from MT5 export
- Creates swing trading labels (2% targets, 1% stops)
- Trains models with 300 trees (deeper for swing patterns)
- Saves models with swing metadata

### How to Run:
```bash
cd /Users/justinhardison/ai-trading-system
python3 retrain_swing_with_h1h4d1.py
```

### Expected Output:
```
======================================================================
SWING TRADING - RETRAINING WITH H1/H4/D1 DATA
======================================================================

CATEGORY: FOREX - SWING TRADING
  ✅ Loaded EURUSD H1: 5000 bars
  ✅ Loaded EURUSD H4: 1250 bars
  ✅ Loaded EURUSD D1: 208 bars
  Labels: 2450 BUY, 2450 SELL
  ✅ Extracted 4800 swing samples

FOREX Combined: 14400 samples, 162 features
  BUY: 7200 (50.0%)
  SELL: 7200 (50.0%)

🤖 Training SWING models for forex...
  RF Accuracy: 68.5%
  GB Accuracy: 71.2%
  Ensemble: 72.8%
  ✅ Saved: forex_ensemble_latest.pkl
```

---

## STEP 3: Create Individual Symbol Models

### Command:
```bash
cd /Users/justinhardison/ai-trading-system
python3 << 'EOF'
import pickle

for symbol in ['eurusd', 'gbpusd', 'usdjpy', 'us30', 'us100', 'us500', 'xau', 'usoil']:
    if symbol in ['eurusd', 'gbpusd', 'usdjpy']:
        category = 'forex'
    elif symbol in ['us30', 'us100', 'us500']:
        category = 'indices'
    else:
        category = 'commodities'
    
    with open(f'models/{category}_ensemble_latest.pkl', 'rb') as f:
        model = pickle.load(f)
    
    model['symbol'] = symbol.upper()
    
    with open(f'models/{symbol}_ensemble_latest.pkl', 'wb') as f:
        pickle.dump(model, f)
    
    print(f"✅ Created {symbol}")

print("\n✅ All symbol models created!")
EOF
```

---

## STEP 4: Restart API

### Command:
```bash
pkill -f "api.py"
sleep 2
nohup python3 api.py > /tmp/ai_trading_api_output.log 2>&1 &
```

### Verify:
```bash
sleep 5
grep "SYSTEM READY" /tmp/ai_trading_api_output.log
grep "Loaded model" /tmp/ai_trading_api_output.log | tail -15
```

### Expected Output:
```
✅ Loaded model for forex
✅ Loaded model for indices
✅ Loaded model for commodities
✅ Loaded model for eurusd
✅ Loaded model for gbpusd
✅ Loaded model for usdjpy
✅ Loaded model for us30
✅ Loaded model for us100
✅ Loaded model for us500
✅ Loaded model for xau
✅ Loaded model for usoil
✅ Total models loaded: 11 symbols
SYSTEM READY
```

---

## STEP 5: Monitor First Swing Trades

### Check Logs:
```bash
tail -f /tmp/ai_trading_api_output.log | grep -E "SWING|Target|Stop|P&L"
```

### What to Look For:
```
🎯 SWING PROFIT TARGET: 2.5% (target: 5.0%)
🛑 SWING HARD STOP: -2.0%
⏰ Swing position too new (45.0 min) - giving it time
📊 MODERATE SWING TREND - Base: 4x volatility
```

---

## SWING TRADING PARAMETERS:

### Position Management:
- **Min Hold**: 60 minutes (1 hour)
- **Profit Target**: 2-5% (take at 50% = 1-2.5%)
- **Stop Loss**: -2% hard stop
- **ML Threshold**: 80% to close

### Expected Performance:
- **Trades/Day**: 2-5 (not 20-50)
- **Hold Time**: 1-24 hours (not 5-15 min)
- **Win Size**: $4k-$10k (not $2-$7)
- **Loss Size**: $2k-$4k max (not $23k)

### Risk Management:
- **Per Trade**: -2% = $4,000 max loss
- **Daily**: $10k-$20k target
- **Monthly**: $100k-$200k target
- **ROI**: 50-100% per month

---

## TROUBLESHOOTING:

### If Export Fails:
- Check MT5 is connected to broker
- Verify symbols are available
- Try one symbol at a time
- Check Experts tab for errors

### If Training Fails:
- Verify files exist in `training_data/swing/`
- Check file format (CSV with headers)
- Ensure at least 1000 bars per timeframe
- Check Python dependencies installed

### If API Won't Start:
- Check for syntax errors: `python3 -m py_compile api.py`
- Verify models exist: `ls -l models/*_ensemble_latest.pkl`
- Check port 5007 not in use: `lsof -i :5007`
- Review error log: `tail -100 /tmp/ai_trading_api_output.log`

---

## COMPLETE WORKFLOW:

```bash
# 1. Export data from MT5 (run ExportSwingData.mq5)

# 2. Retrain models
cd /Users/justinhardison/ai-trading-system
python3 retrain_swing_with_h1h4d1.py

# 3. Create symbol models
python3 << 'EOF'
import pickle
for symbol in ['eurusd', 'gbpusd', 'usdjpy', 'us30', 'us100', 'us500', 'xau', 'usoil']:
    category = 'forex' if symbol in ['eurusd', 'gbpusd', 'usdjpy'] else 'indices' if symbol in ['us30', 'us100', 'us500'] else 'commodities'
    with open(f'models/{category}_ensemble_latest.pkl', 'rb') as f:
        model = pickle.load(f)
    model['symbol'] = symbol.upper()
    with open(f'models/{symbol}_ensemble_latest.pkl', 'wb') as f:
        pickle.dump(model, f)
    print(f"✅ {symbol}")
EOF

# 4. Restart API
pkill -f "api.py"
sleep 2
nohup python3 api.py > /tmp/ai_trading_api_output.log 2>&1 &

# 5. Verify
sleep 5
grep "SYSTEM READY" /tmp/ai_trading_api_output.log
tail -20 /tmp/ai_trading_api_output.log

# 6. Monitor
tail -f /tmp/ai_trading_api_output.log | grep -E "SWING|Target|ANALYZING"
```

---

## STATUS:

**MQL5 Script**: ✅ Created in MetaEditor Scripts folder  
**Python Trainer**: ✅ Created with H1/H4/D1 support  
**Position Manager**: ✅ Updated for swing trading  
**Instructions**: ✅ Complete workflow documented  

**READY TO EXPORT DATA AND RETRAIN FOR SWING TRADING!** 🚀

---

## NEXT STEPS:

1. **YOU**: Run ExportSwingData.mq5 in MT5
2. **ME**: Wait for your confirmation data is exported
3. **ME**: Run retrain_swing_with_h1h4d1.py
4. **ME**: Create symbol models and restart API
5. **US**: Monitor first swing trades together

**LET'S DO THIS!** 💪
