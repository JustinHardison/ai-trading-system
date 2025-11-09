//+------------------------------------------------------------------+
//|                                          Export_Training_Data.mq5 |
//|                                                                    |
//| Exports historical data for ALL symbols and timeframes            |
//| for ML model training with 159 features                           |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "1.00"
#property script_show_inputs

// Input parameters
input int BarsToExport = 5000;  // Number of bars to export per symbol
input string ExportPath = "/tmp/";  // Export path

// All symbols we trade
string symbols[] = {
    // Forex
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    // Indices  
    "US100", "US30", "SPX500",
    // Commodities
    "XAUUSD", "USOIL"
};

// All timeframes we use (7 timeframes)
ENUM_TIMEFRAMES timeframes[] = {
    PERIOD_M1,   // M1
    PERIOD_M5,   // M5
    PERIOD_M15,  // M15
    PERIOD_M30,  // M30
    PERIOD_H1,   // H1
    PERIOD_H4,   // H4
    PERIOD_D1    // D1
};

string timeframe_names[] = {
    "M1", "M5", "M15", "M30", "H1", "H4", "D1"
};

//+------------------------------------------------------------------+
//| Script program start function                                     |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("========================================");
    Print("EXPORTING TRAINING DATA");
    Print("========================================");
    Print("Bars per symbol: ", BarsToExport);
    Print("Symbols: ", ArraySize(symbols));
    Print("Timeframes: ", ArraySize(timeframes));
    Print("Export path: ", ExportPath);
    Print("");
    
    int total_exported = 0;
    int failed_exports = 0;
    
    // Export data for each symbol
    for(int s = 0; s < ArraySize(symbols); s++)
    {
        string symbol = symbols[s];
        
        // Check if symbol exists
        if(!SymbolSelect(symbol, true))
        {
            Print("⚠️ Symbol ", symbol, " not available - skipping");
            failed_exports++;
            continue;
        }
        
        Print("📊 Exporting ", symbol, "...");
        
        // Export each timeframe for this symbol
        for(int t = 0; t < ArraySize(timeframes); t++)
        {
            ENUM_TIMEFRAMES tf = timeframes[t];
            string tf_name = timeframe_names[t];
            
            if(ExportSymbolTimeframe(symbol, tf, tf_name))
            {
                total_exported++;
            }
            else
            {
                failed_exports++;
            }
        }
        
        Print("");
    }
    
    Print("========================================");
    Print("EXPORT COMPLETE!");
    Print("========================================");
    Print("✅ Successfully exported: ", total_exported, " files");
    Print("❌ Failed exports: ", failed_exports);
    Print("");
    Print("📁 Files saved to: ", ExportPath);
    Print("");
    Print("🔄 Next step: Run Python training script");
    Print("   python3 retrain_from_mt5_export.py");
}

//+------------------------------------------------------------------+
//| Export data for one symbol and timeframe                          |
//+------------------------------------------------------------------+
bool ExportSymbolTimeframe(string symbol, ENUM_TIMEFRAMES timeframe, string tf_name)
{
    // Create filename
    string filename = ExportPath + symbol + "_" + tf_name + "_training.csv";
    
    // Copy rates
    MqlRates rates[];
    int copied = CopyRates(symbol, timeframe, 0, BarsToExport, rates);
    
    if(copied <= 0)
    {
        Print("  ❌ ", tf_name, ": Failed to copy rates (", GetLastError(), ")");
        return false;
    }
    
    // Open file for writing
    int file_handle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    
    if(file_handle == INVALID_HANDLE)
    {
        Print("  ❌ ", tf_name, ": Failed to create file (", GetLastError(), ")");
        return false;
    }
    
    // Write header
    FileWrite(file_handle, "timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume");
    
    // Write data
    for(int i = 0; i < copied; i++)
    {
        FileWrite(file_handle,
                  TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS),
                  DoubleToString(rates[i].open, 5),
                  DoubleToString(rates[i].high, 5),
                  DoubleToString(rates[i].low, 5),
                  DoubleToString(rates[i].close, 5),
                  IntegerToString(rates[i].tick_volume),
                  IntegerToString(rates[i].spread),
                  IntegerToString(rates[i].real_volume)
        );
    }
    
    FileClose(file_handle);
    
    Print("  ✅ ", tf_name, ": ", copied, " bars → ", filename);
    
    return true;
}
//+------------------------------------------------------------------+
