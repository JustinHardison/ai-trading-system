# 📚 ML Model Training Instructions

**Date**: November 20, 2025, 2:15 PM  
**Method**: Export from MT5 → Train with Python

---

## STEP 1: EXPORT DATA FROM MT5 (5 minutes)

### **1. Open MetaEditor**:
- In MT5, press F4 or go to Tools → MetaQuotes Language Editor

### **2. Create New Script**:
- File → New → Script
- Name it: `Export_Training_Data`
- Click Finish

### **3. Copy the Script**:
- Open: `/Users/justinhardison/ai-trading-system/Export_Training_Data.mq5`
- Copy ALL the code
- Paste into MetaEditor
- Save (Ctrl+S)
- Compile (F7) - should show 0 errors

### **4. Run the Script**:
- In MT5, open any chart (doesn't matter which symbol)
- Drag `Export_Training_Data` from Navigator → Scripts onto the chart
- A dialog will appear:
  - **BarsToExport**: 5000 (default is fine)
  - **ExportPath**: /tmp/ (default is fine)
- Click OK

### **5. Wait for Export**:
- Script will export data for all symbols and timeframes
- Watch the Experts tab for progress
- Should see:
  ```
  📊 Exporting EURUSD...
    ✅ M1: 5000 bars → /tmp/EURUSD_M1_training.csv
    ✅ M5: 5000 bars → /tmp/EURUSD_M5_training.csv
    ✅ M15: 5000 bars → /tmp/EURUSD_M15_training.csv
    ... etc
  ```

### **6. Verify Export**:
- Should export 70 files total (10 symbols × 7 timeframes)
- Check: `ls -l /tmp/*_training.csv | wc -l` should show 70

---

## STEP 2: TRAIN MODELS (10-15 minutes)

### **After export completes, tell me and I'll run**:
```bash
python3 /Users/justinhardison/ai-trading-system/retrain_from_mt5_export.py
```

This will:
1. Load all exported CSV files
2. Extract 159 features from 7 timeframes
3. Train 3 ensemble models (forex, indices, commodities)
4. Save to `/Users/justinhardison/ai-trading-system/models/`

---

## STEP 3: RESTART API (1 minute)

### **After training completes, I'll run**:
```bash
pkill -f api.py
python3 api.py
```

---

## WHAT WILL BE EXPORTED

### **Symbols** (10 total):
- **Forex**: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD
- **Indices**: US100, US30, SPX500
- **Commodities**: XAUUSD, USOIL

### **Timeframes** (7 total):
- M1, M5, M15, M30, H1, H4, D1

### **Data per file**:
- 5000 bars
- Columns: timestamp, open, high, low, close, tick_volume, spread, real_volume

### **Total files**: 70 (10 symbols × 7 timeframes)

---

## BENEFITS OF THIS APPROACH

✅ **100% Broker Accurate**: Uses exact data from your MT5
✅ **All Timeframes**: Gets all 7 timeframes we need
✅ **All Symbols**: Gets all 10 symbols we trade
✅ **No API Issues**: No yfinance, no import errors
✅ **Fast**: Export takes 5 min, training takes 15 min
✅ **Reliable**: Direct from source

---

## EXPECTED RESULTS

After training completes:
- ✅ 3 new models with 159 features each
- ✅ Models trained on YOUR broker's data
- ✅ ML predictions will work properly
- ✅ New trades will open
- ✅ GENIUS AI will work with proper predictions

---

## NEXT STEPS

1. **You**: Run Export_Training_Data.mq5 in MT5
2. **You**: Tell me when export is complete
3. **Me**: Run training script
4. **Me**: Restart API
5. **Done**: System fully operational!

---

**Status**: ⏸️ **WAITING FOR YOU TO RUN EXPORT SCRIPT**

**Time Required**: 
- Export: 5 minutes
- Training: 15 minutes  
- Total: 20 minutes

**Result**: Fully trained models with 159 features from YOUR broker data!
