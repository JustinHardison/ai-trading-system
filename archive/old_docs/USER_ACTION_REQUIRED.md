# ⚠️  USER ACTION REQUIRED - DATA EXPORT

## 📋 WHAT YOU NEED TO DO:

The autonomous rebuild is running but needs training data for all 8 symbols.

### STEP 1: Open MetaTrader 5

### STEP 2: Run the Export Script
1. In MT5, go to: **Tools → Options → Expert Advisors**
2. Enable "Allow automated trading"
3. Go to: **Navigator → Scripts**
4. Find: **Export_ALL_Symbols**
5. Drag it onto ANY chart
6. Click "OK" to start export

The script will export ALL 8 symbols automatically:
- US30Z25.sim
- US100Z25.sim
- US500Z25.sim
- EURUSD.sim
- GBPUSD.sim
- USDJPY.sim
- XAUG26.sim
- USOILF26.sim

### STEP 3: Copy the CSV Files
After export completes, copy ALL CSV files from:
```
C:\Program Files\MetaTrader 5\MQL5\Files\
```

To:
```
/Users/justinhardison/ai-trading-system/data/
```

Files to copy:
- us30_training_data.csv
- us100_training_data.csv
- us500_training_data.csv
- eurusd_training_data.csv
- gbpusd_training_data.csv
- usdjpy_training_data.csv
- xau_training_data.csv
- usoil_training_data.csv

### STEP 4: Wait
Once files are copied, the autonomous rebuild will:
1. Detect the files
2. Train symbol-specific models for EACH symbol
3. Fix feature mismatch
4. Integrate RL agent
5. Implement conviction scoring
6. Clean dead code
7. Complete the rebuild

## ⏱️ ESTIMATED TIME:
- Export: 5-10 minutes per symbol (40-80 minutes total)
- Training: 3-5 minutes per symbol (24-40 minutes total)
- **Total: ~1-2 hours**

## 🔍 MONITORING:
Watch the rebuild progress:
```bash
tail -f /tmp/complete_rebuild.log
```

## ✅ WHEN COMPLETE:
The system will have:
- ✅ 8 symbol-specific models (not copies!)
- ✅ Correct feature matching (73 features)
- ✅ RL agent integrated
- ✅ Conviction scoring implemented
- ✅ Dead code cleaned
- ✅ Ready for production

---

**The rebuild is waiting for your data export. Once you copy the files, it will continue automatically.**

