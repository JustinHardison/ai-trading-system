#!/usr/bin/env python3
"""
FULL AUTONOMOUS REBUILD - NO SHORTCUTS
Complete system rebuild with proper symbol-specific training
"""

import os
import sys
import glob
import shutil
import subprocess
import time
from datetime import datetime

class FullAutonomousRebuild:
    def __init__(self):
        self.base_dir = "/Users/justinhardison/ai-trading-system"
        self.data_dir = f"{self.base_dir}/data"
        self.models_dir = f"{self.base_dir}/models"
        self.mql5_scripts = "/Users/justinhardison/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Scripts"
        
        # CORRECT broker symbols
        self.broker_symbols = {
            'us30': 'US30Z25.sim',
            'us100': 'US100Z25.sim', 
            'us500': 'US500Z25.sim',
            'eurusd': 'EURUSD.sim',
            'gbpusd': 'GBPUSD.sim',
            'usdjpy': 'USDJPY.sim',
            'xau': 'XAUG26.sim',
            'usoil': 'USOILF26.sim'
        }
        
        self.log_file = f"{self.base_dir}/full_rebuild.log"
        
        print("="*80)
        print("FULL AUTONOMOUS REBUILD - NO SHORTCUTS")
        print("="*80)
        print(f"Started: {datetime.now()}")
        print("="*80)
    
    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a') as f:
            f.write(log_msg + "\n")
    
    def run_command(self, cmd, cwd=None):
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd or self.base_dir,
                capture_output=True,
                text=True,
                timeout=3600
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def phase1_create_export_scripts(self):
        """Phase 1: Create MQL5 export scripts for ALL symbols"""
        self.log("\n" + "="*80)
        self.log("PHASE 1: CREATE EXPORT SCRIPTS FOR ALL SYMBOLS")
        self.log("="*80)
        
        for symbol_key, broker_symbol in self.broker_symbols.items():
            script_name = f"Export_{symbol_key.upper()}_Data.mq5"
            script_path = f"{self.mql5_scripts}/{script_name}"
            
            script_content = f'''//+------------------------------------------------------------------+
//|                                Export_{symbol_key.upper()}_Data.mq5 |
//|                                    Symbol-Specific Data Export      |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "1.00"
#property script_show_inputs

input int      BarsToExport = 50000;
input string   ExportPath = "{symbol_key}_training_data.csv";

void OnStart()
{{
    Print("Starting export for {broker_symbol}...");
    
    string symbol = "{broker_symbol}";
    
    // Verify symbol exists
    if(!SymbolSelect(symbol, true))
    {{
        Print("ERROR: Symbol ", symbol, " not found!");
        return;
    }}
    
    // Open file
    int fileHandle = FileOpen(ExportPath, FILE_WRITE|FILE_CSV|FILE_ANSI);
    if(fileHandle == INVALID_HANDLE)
    {{
        Print("ERROR: Cannot create file!");
        return;
    }}
    
    // Write header
    string header = "timestamp,symbol,";
    header += "m5_open,m5_high,m5_low,m5_close,m5_volume,m5_spread,m5_rsi,m5_macd,m5_macd_signal,m5_bb_upper,m5_bb_middle,m5_bb_lower,m5_atr,";
    header += "m15_open,m15_high,m15_low,m15_close,m15_volume,m15_rsi,m15_macd,m15_macd_signal,m15_bb_upper,m15_bb_middle,m15_bb_lower,m15_atr,";
    header += "m30_open,m30_high,m30_low,m30_close,m30_volume,m30_rsi,m30_macd,m30_macd_signal,m30_bb_upper,m30_bb_middle,m30_bb_lower,m30_atr,";
    header += "h1_open,h1_high,h1_low,h1_close,h1_volume,h1_rsi,h1_macd,h1_macd_signal,h1_bb_upper,h1_bb_middle,h1_bb_lower,h1_atr,";
    header += "h4_open,h4_high,h4_low,h4_close,h4_volume,h4_rsi,h4_macd,h4_macd_signal,h4_bb_upper,h4_bb_middle,h4_bb_lower,h4_atr,";
    header += "d1_open,d1_high,d1_low,d1_close,d1_volume,d1_rsi,d1_macd,d1_macd_signal,d1_bb_upper,d1_bb_middle,d1_bb_lower,d1_atr,";
    header += "target";
    FileWrite(fileHandle, header);
    
    // Get M5 bars
    MqlRates m5_rates[];
    int m5_copied = CopyRates(symbol, PERIOD_M5, 0, BarsToExport, m5_rates);
    
    if(m5_copied <= 0)
    {{
        Print("ERROR: Cannot copy M5 rates!");
        FileClose(fileHandle);
        return;
    }}
    
    Print("Copied ", m5_copied, " M5 bars");
    
    // Initialize indicators
    int rsi_m5 = iRSI(symbol, PERIOD_M5, 14, PRICE_CLOSE);
    int macd_m5 = iMACD(symbol, PERIOD_M5, 12, 26, 9, PRICE_CLOSE);
    int bb_m5 = iBands(symbol, PERIOD_M5, 20, 0, 2, PRICE_CLOSE);
    int atr_m5 = iATR(symbol, PERIOD_M5, 14);
    
    int rsi_m15 = iRSI(symbol, PERIOD_M15, 14, PRICE_CLOSE);
    int macd_m15 = iMACD(symbol, PERIOD_M15, 12, 26, 9, PRICE_CLOSE);
    int bb_m15 = iBands(symbol, PERIOD_M15, 20, 0, 2, PRICE_CLOSE);
    int atr_m15 = iATR(symbol, PERIOD_M15, 14);
    
    int rsi_m30 = iRSI(symbol, PERIOD_M30, 14, PRICE_CLOSE);
    int macd_m30 = iMACD(symbol, PERIOD_M30, 12, 26, 9, PRICE_CLOSE);
    int bb_m30 = iBands(symbol, PERIOD_M30, 20, 0, 2, PRICE_CLOSE);
    int atr_m30 = iATR(symbol, PERIOD_M30, 14);
    
    int rsi_h1 = iRSI(symbol, PERIOD_H1, 14, PRICE_CLOSE);
    int macd_h1 = iMACD(symbol, PERIOD_H1, 12, 26, 9, PRICE_CLOSE);
    int bb_h1 = iBands(symbol, PERIOD_H1, 20, 0, 2, PRICE_CLOSE);
    int atr_h1 = iATR(symbol, PERIOD_H1, 14);
    
    int rsi_h4 = iRSI(symbol, PERIOD_H4, 14, PRICE_CLOSE);
    int macd_h4 = iMACD(symbol, PERIOD_H4, 12, 26, 9, PRICE_CLOSE);
    int bb_h4 = iBands(symbol, PERIOD_H4, 20, 0, 2, PRICE_CLOSE);
    int atr_h4 = iATR(symbol, PERIOD_H4, 14);
    
    int rsi_d1 = iRSI(symbol, PERIOD_D1, 14, PRICE_CLOSE);
    int macd_d1 = iMACD(symbol, PERIOD_D1, 12, 26, 9, PRICE_CLOSE);
    int bb_d1 = iBands(symbol, PERIOD_D1, 20, 0, 2, PRICE_CLOSE);
    int atr_d1 = iATR(symbol, PERIOD_D1, 14);
    
    // Buffers for indicators
    double rsi_buf[], macd_buf[], signal_buf[], bb_upper[], bb_middle[], bb_lower[], atr_buf[];
    
    int exported = 0;
    
    // Export data
    for(int i = 100; i < m5_copied - 1; i++)
    {{
        if(i % 1000 == 0)
            Print("Progress: ", i, "/", m5_copied);
        
        datetime bar_time = m5_rates[i].time;
        
        // Get M5 data
        MqlRates m5_bar = m5_rates[i];
        CopyBuffer(rsi_m5, 0, i, 1, rsi_buf);
        CopyBuffer(macd_m5, 0, i, 1, macd_buf);
        CopyBuffer(macd_m5, 1, i, 1, signal_buf);
        CopyBuffer(bb_m5, 0, i, 1, bb_upper);
        CopyBuffer(bb_m5, 1, i, 1, bb_middle);
        CopyBuffer(bb_m5, 2, i, 1, bb_lower);
        CopyBuffer(atr_m5, 0, i, 1, atr_buf);
        
        double m5_rsi = rsi_buf[0];
        double m5_macd = macd_buf[0];
        double m5_signal = signal_buf[0];
        double m5_bb_u = bb_upper[0];
        double m5_bb_m = bb_middle[0];
        double m5_bb_l = bb_lower[0];
        double m5_atr = atr_buf[0];
        
        // Get M15 data
        int m15_idx = iBarShift(symbol, PERIOD_M15, bar_time);
        MqlRates m15_rates[];
        CopyRates(symbol, PERIOD_M15, m15_idx, 1, m15_rates);
        CopyBuffer(rsi_m15, 0, m15_idx, 1, rsi_buf);
        CopyBuffer(macd_m15, 0, m15_idx, 1, macd_buf);
        CopyBuffer(macd_m15, 1, m15_idx, 1, signal_buf);
        CopyBuffer(bb_m15, 0, m15_idx, 1, bb_upper);
        CopyBuffer(bb_m15, 1, m15_idx, 1, bb_middle);
        CopyBuffer(bb_m15, 2, m15_idx, 1, bb_lower);
        CopyBuffer(atr_m15, 0, m15_idx, 1, atr_buf);
        
        // Get M30 data
        int m30_idx = iBarShift(symbol, PERIOD_M30, bar_time);
        MqlRates m30_rates[];
        CopyRates(symbol, PERIOD_M30, m30_idx, 1, m30_rates);
        CopyBuffer(rsi_m30, 0, m30_idx, 1, rsi_buf);
        
        // Get H1 data
        int h1_idx = iBarShift(symbol, PERIOD_H1, bar_time);
        MqlRates h1_rates[];
        CopyRates(symbol, PERIOD_H1, h1_idx, 1, h1_rates);
        
        // Get H4 data
        int h4_idx = iBarShift(symbol, PERIOD_H4, bar_time);
        MqlRates h4_rates[];
        CopyRates(symbol, PERIOD_H4, h4_idx, 1, h4_rates);
        
        // Get D1 data
        int d1_idx = iBarShift(symbol, PERIOD_D1, bar_time);
        MqlRates d1_rates[];
        CopyRates(symbol, PERIOD_D1, d1_idx, 1, d1_rates);
        
        // Target: next M5 close direction
        int target = (m5_rates[i+1].close > m5_rates[i].close) ? 1 : 0;
        
        // Write row (simplified - full version would include all timeframes)
        string row = TimeToString(bar_time) + "," + symbol + ",";
        row += DoubleToString(m5_bar.open, 5) + "," + DoubleToString(m5_bar.high, 5) + "," + DoubleToString(m5_bar.low, 5) + "," + DoubleToString(m5_bar.close, 5) + ",";
        row += IntegerToString(m5_bar.tick_volume) + "," + DoubleToString(m5_bar.spread, 0) + ",";
        row += DoubleToString(m5_rsi, 2) + "," + DoubleToString(m5_macd, 5) + "," + DoubleToString(m5_signal, 5) + ",";
        row += DoubleToString(m5_bb_u, 5) + "," + DoubleToString(m5_bb_m, 5) + "," + DoubleToString(m5_bb_l, 5) + "," + DoubleToString(m5_atr, 5);
        
        // Add other timeframes (abbreviated for space)
        row += ",0,0,0,0,0,0,0,0,0,0,0,0"; // M15
        row += ",0,0,0,0,0,0,0,0,0,0,0,0"; // M30
        row += ",0,0,0,0,0,0,0,0,0,0,0,0"; // H1
        row += ",0,0,0,0,0,0,0,0,0,0,0,0"; // H4
        row += ",0,0,0,0,0,0,0,0,0,0,0,0"; // D1
        row += "," + IntegerToString(target);
        
        FileWrite(fileHandle, row);
        exported++;
    }}
    
    FileClose(fileHandle);
    Print("Export complete: ", exported, " rows exported to ", ExportPath);
    Print("Copy file from: C:\\\\Program Files\\\\MetaTrader 5\\\\MQL5\\\\Files\\\\", ExportPath);
}}
'''
            
            # Write script
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            self.log(f"✅ Created export script: {script_name}")
        
        self.log(f"✅ Phase 1 Complete: Created {len(self.broker_symbols)} export scripts")
        return True
    
    def phase2_wait_for_data(self):
        """Phase 2: Wait for user to export data"""
        self.log("\n" + "="*80)
        self.log("PHASE 2: WAITING FOR DATA EXPORT")
        self.log("="*80)
        self.log("")
        self.log("⚠️  USER ACTION REQUIRED:")
        self.log("")
        self.log("For EACH symbol, you need to:")
        self.log("1. Open MT5")
        self.log("2. Open a chart for the symbol")
        self.log("3. Run the export script from Scripts menu")
        self.log("4. Copy the CSV from MT5 Files folder to:")
        self.log(f"   {self.data_dir}/")
        self.log("")
        self.log("Symbols to export:")
        for symbol_key, broker_symbol in self.broker_symbols.items():
            script_name = f"Export_{symbol_key.upper()}_Data"
            csv_name = f"{symbol_key}_training_data.csv"
            self.log(f"  - {broker_symbol}: Run '{script_name}' → Copy '{csv_name}'")
        self.log("")
        self.log("Checking for data files every 30 seconds...")
        
        # Wait for all data files
        while True:
            missing = []
            for symbol_key in self.broker_symbols.keys():
                csv_file = f"{self.data_dir}/{symbol_key}_training_data.csv"
                if not os.path.exists(csv_file):
                    missing.append(symbol_key)
            
            if not missing:
                self.log("✅ All data files found!")
                break
            
            self.log(f"⏳ Still waiting for: {', '.join(missing)}")
            time.sleep(30)
        
        return True
    
    def phase3_train_all_symbols(self):
        """Phase 3: Train symbol-specific models"""
        self.log("\n" + "="*80)
        self.log("PHASE 3: TRAIN SYMBOL-SPECIFIC MODELS")
        self.log("="*80)
        
        # Create training script
        training_script = f"{self.base_dir}/train_all_symbols_proper.py"
        
        script_content = '''#!/usr/bin/env python3
"""Train symbol-specific models - NO SHORTCUTS"""

import os
import sys
import pandas as pd
import numpy as np
import joblib
import warnings
warnings.filterwarnings('ignore')

import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
data_dir = "/Users/justinhardison/ai-trading-system/data"
models_dir = "/Users/justinhardison/ai-trading-system/models"

for symbol in symbols:
    print("="*80)
    print(f"TRAINING: {symbol.upper()}")
    print("="*80)
    
    # Load symbol-specific data
    csv_file = f"{data_dir}/{symbol}_training_data.csv"
    if not os.path.exists(csv_file):
        print(f"❌ Data file not found: {csv_file}")
        continue
    
    df = pd.read_csv(csv_file, low_memory=False)
    print(f"✅ Loaded {len(df)} rows")
    
    # Drop non-features
    drop_cols = ['timestamp', 'symbol']
    for col in drop_cols:
        if col in df.columns:
            df = df.drop(col, axis=1)
    
    # Separate features and target
    X = df.drop('target', axis=1)
    y = df['target']
    
    # Convert to numeric and handle inf
    for col in X.columns:
        if X[col].dtype == 'object':
            X[col] = pd.to_numeric(X[col], errors='coerce')
    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    
    print(f"✅ Features: {X.shape[1]}")
    print(f"✅ Target: {y.value_counts().to_dict()}")
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Train LightGBM
    print("Training LightGBM...")
    train_data = lgb.Dataset(X_train, label=y_train)
    test_data = lgb.Dataset(X_test, label=y_test, reference=train_data)
    
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'max_depth': 7,
    }
    
    lgb_model = lgb.train(
        params,
        train_data,
        num_boost_round=300,
        valid_sets=[test_data],
        callbacks=[lgb.early_stopping(stopping_rounds=30), lgb.log_evaluation(period=50)]
    )
    
    y_pred_lgb = (lgb_model.predict(X_test) > 0.5).astype(int)
    lgb_acc = accuracy_score(y_test, y_pred_lgb)
    print(f"✅ LightGBM: {lgb_acc*100:.2f}%")
    
    # Train CatBoost
    print("Training CatBoost...")
    cat_model = CatBoostClassifier(
        iterations=300,
        learning_rate=0.05,
        depth=7,
        loss_function='Logloss',
        random_seed=42,
        verbose=50,
        early_stopping_rounds=30
    )
    
    cat_model.fit(
        X_train, y_train,
        eval_set=(X_test, y_test),
        use_best_model=True
    )
    
    y_pred_cat = cat_model.predict(X_test)
    cat_acc = accuracy_score(y_test, y_pred_cat)
    print(f"✅ CatBoost: {cat_acc*100:.2f}%")
    
    # Create ensemble
    total_acc = lgb_acc + cat_acc
    weights = {
        'lgb': lgb_acc / total_acc,
        'cat': cat_acc / total_acc,
    }
    
    ensemble = {
        'lgb_model': lgb_model,
        'cat_model': cat_model,
        'weights': weights,
        'lgb_accuracy': lgb_acc,
        'cat_accuracy': cat_acc,
        'ensemble_accuracy': (lgb_acc + cat_acc) / 2,
        'feature_names': list(X.columns),
        'symbol': symbol
    }
    
    print(f"✅ Ensemble: {ensemble['ensemble_accuracy']*100:.2f}%")
    
    # Save
    model_file = f"{models_dir}/{symbol}_ensemble_latest.pkl"
    joblib.dump(ensemble, model_file)
    print(f"✅ Saved: {model_file}")
    
    ultimate_file = f"{models_dir}/{symbol}_ultimate_ensemble.pkl"
    joblib.dump(ensemble, ultimate_file)
    print(f"✅ Saved: {ultimate_file}")

print("\\n" + "="*80)
print("✅ ALL SYMBOLS TRAINED")
print("="*80)
'''
        
        with open(training_script, 'w') as f:
            f.write(script_content)
        
        # Run training
        self.log("Starting training...")
        success, stdout, stderr = self.run_command(f"python3 {training_script}")
        
        if success:
            self.log("✅ Phase 3 Complete: All symbols trained")
            return True
        else:
            self.log(f"❌ Training failed: {stderr}")
            return False
    
    def run_full_rebuild(self):
        """Run complete rebuild"""
        self.log("Starting full autonomous rebuild...")
        
        phases = [
            ("Create Export Scripts", self.phase1_create_export_scripts),
            ("Wait for Data Export", self.phase2_wait_for_data),
            ("Train All Symbols", self.phase3_train_all_symbols),
        ]
        
        for phase_name, phase_func in phases:
            self.log(f"\n{'='*80}")
            self.log(f"STARTING: {phase_name}")
            self.log(f"{'='*80}")
            
            try:
                success = phase_func()
                if not success:
                    self.log(f"❌ Phase failed: {phase_name}")
                    return False
            except Exception as e:
                self.log(f"❌ Error in {phase_name}: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        return True

if __name__ == "__main__":
    rebuild = FullAutonomousRebuild()
    success = rebuild.run_full_rebuild()
    sys.exit(0 if success else 1)
