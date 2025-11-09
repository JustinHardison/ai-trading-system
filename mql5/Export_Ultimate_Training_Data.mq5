//+------------------------------------------------------------------+
//|                                Export_Ultimate_Training_Data.mq5 |
//|                                    Ultimate Data Export for ML   |
//|                          Exports ALL timeframes for hedge fund AI|
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "1.00"
#property description "Exports comprehensive multi-timeframe data for ML training"
#property script_show_inputs

//--- Input parameters
input int      BarsToExport = 50000;        // Number of bars to export (M5 basis)
input string   ExportPath = "ultimate_training_data.csv";  // Export filename

//--- Timeframes to export
enum TIMEFRAME_EXPORT
{
   TF_M5  = PERIOD_M5,
   TF_M15 = PERIOD_M15,
   TF_M30 = PERIOD_M30,
   TF_H1  = PERIOD_H1,
   TF_H4  = PERIOD_H4,
   TF_D1  = PERIOD_D1
};

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
   string symbol = _Symbol;
   
   Print("═══════════════════════════════════════════════════════════════════");
   Print("ULTIMATE TRAINING DATA EXPORT - HEDGE FUND SYSTEM");
   Print("═══════════════════════════════════════════════════════════════════");
   Print("Symbol: ", symbol);
   Print("Bars to export: ", BarsToExport);
   Print("═══════════════════════════════════════════════════════════════════");
   
   //--- Open file for writing
   int fileHandle = FileOpen(ExportPath, FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
   
   if(fileHandle == INVALID_HANDLE)
   {
      Print("ERROR: Cannot create file ", ExportPath);
      Print("Error code: ", GetLastError());
      return;
   }
   
   //--- Write comprehensive header
   string header = "timestamp,symbol,";
   
   // M5 data
   header += "m5_open,m5_high,m5_low,m5_close,m5_volume,m5_spread,";
   header += "m5_rsi,m5_macd,m5_macd_signal,m5_bb_upper,m5_bb_middle,m5_bb_lower,m5_atr,";
   
   // M15 data
   header += "m15_open,m15_high,m15_low,m15_close,m15_volume,";
   header += "m15_rsi,m15_macd,m15_macd_signal,m15_bb_upper,m15_bb_middle,m15_bb_lower,m15_atr,";
   
   // M30 data
   header += "m30_open,m30_high,m30_low,m30_close,m30_volume,";
   header += "m30_rsi,m30_macd,m30_macd_signal,m30_bb_upper,m30_bb_middle,m30_bb_lower,m30_atr,";
   
   // H1 data
   header += "h1_open,h1_high,h1_low,h1_close,h1_volume,";
   header += "h1_rsi,h1_macd,h1_macd_signal,h1_bb_upper,h1_bb_middle,h1_bb_lower,h1_atr,";
   
   // H4 data
   header += "h4_open,h4_high,h4_low,h4_close,h4_volume,";
   header += "h4_rsi,h4_macd,h4_macd_signal,h4_bb_upper,h4_bb_middle,h4_bb_lower,h4_atr,";
   
   // D1 data
   header += "d1_open,d1_high,d1_low,d1_close,d1_volume,";
   header += "d1_rsi,d1_macd,d1_macd_signal,d1_bb_upper,d1_bb_middle,d1_bb_lower,d1_atr,";
   
   // Target (next M5 close direction)
   header += "target";
   
   FileWrite(fileHandle, header);
   
   //--- Initialize indicators for all timeframes
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
   
   //--- Check all indicators loaded
   if(rsi_m5 == INVALID_HANDLE || macd_m5 == INVALID_HANDLE || bb_m5 == INVALID_HANDLE || atr_m5 == INVALID_HANDLE ||
      rsi_m15 == INVALID_HANDLE || macd_m15 == INVALID_HANDLE || bb_m15 == INVALID_HANDLE || atr_m15 == INVALID_HANDLE ||
      rsi_m30 == INVALID_HANDLE || macd_m30 == INVALID_HANDLE || bb_m30 == INVALID_HANDLE || atr_m30 == INVALID_HANDLE ||
      rsi_h1 == INVALID_HANDLE || macd_h1 == INVALID_HANDLE || bb_h1 == INVALID_HANDLE || atr_h1 == INVALID_HANDLE ||
      rsi_h4 == INVALID_HANDLE || macd_h4 == INVALID_HANDLE || bb_h4 == INVALID_HANDLE || atr_h4 == INVALID_HANDLE ||
      rsi_d1 == INVALID_HANDLE || macd_d1 == INVALID_HANDLE || bb_d1 == INVALID_HANDLE || atr_d1 == INVALID_HANDLE)
   {
      Print("ERROR: Failed to initialize indicators");
      FileClose(fileHandle);
      return;
   }
   
   Print("✅ All indicators initialized");
   
   //--- Arrays for indicator values
   double rsi_buffer[], macd_main[], macd_signal[], bb_upper[], bb_middle[], bb_lower[], atr_buffer[];
   
   //--- Export data bar by bar (M5 basis)
   int exported = 0;
   int errors = 0;
   
   for(int i = BarsToExport; i >= 1; i--)
   {
      //--- Get M5 bar time
      datetime bar_time = iTime(symbol, PERIOD_M5, i);
      if(bar_time == 0) continue;
      
      //--- Get M5 OHLCV
      MqlRates m5_rates[];
      if(CopyRates(symbol, PERIOD_M5, i, 1, m5_rates) != 1) continue;
      
      //--- Get M15 data (aligned to M5 time)
      MqlRates m15_rates[];
      int m15_shift = iBarShift(symbol, PERIOD_M15, bar_time);
      if(CopyRates(symbol, PERIOD_M15, m15_shift, 1, m15_rates) != 1) continue;
      
      //--- Get M30 data
      MqlRates m30_rates[];
      int m30_shift = iBarShift(symbol, PERIOD_M30, bar_time);
      if(CopyRates(symbol, PERIOD_M30, m30_shift, 1, m30_rates) != 1) continue;
      
      //--- Get H1 data
      MqlRates h1_rates[];
      int h1_shift = iBarShift(symbol, PERIOD_H1, bar_time);
      if(CopyRates(symbol, PERIOD_H1, h1_shift, 1, h1_rates) != 1) continue;
      
      //--- Get H4 data
      MqlRates h4_rates[];
      int h4_shift = iBarShift(symbol, PERIOD_H4, bar_time);
      if(CopyRates(symbol, PERIOD_H4, h4_shift, 1, h4_rates) != 1) continue;
      
      //--- Get D1 data
      MqlRates d1_rates[];
      int d1_shift = iBarShift(symbol, PERIOD_D1, bar_time);
      if(CopyRates(symbol, PERIOD_D1, d1_shift, 1, d1_rates) != 1) continue;
      
      //--- Get M5 indicators
      double m5_rsi_val = GetIndicatorValue(rsi_m5, 0, i);
      double m5_macd_main = GetIndicatorValue(macd_m5, 0, i);
      double m5_macd_sig = GetIndicatorValue(macd_m5, 1, i);
      double m5_bb_up = GetIndicatorValue(bb_m5, 0, i);
      double m5_bb_mid = GetIndicatorValue(bb_m5, 1, i);
      double m5_bb_low = GetIndicatorValue(bb_m5, 2, i);
      double m5_atr_val = GetIndicatorValue(atr_m5, 0, i);
      
      //--- Get M15 indicators
      double m15_rsi_val = GetIndicatorValue(rsi_m15, 0, m15_shift);
      double m15_macd_main = GetIndicatorValue(macd_m15, 0, m15_shift);
      double m15_macd_sig = GetIndicatorValue(macd_m15, 1, m15_shift);
      double m15_bb_up = GetIndicatorValue(bb_m15, 0, m15_shift);
      double m15_bb_mid = GetIndicatorValue(bb_m15, 1, m15_shift);
      double m15_bb_low = GetIndicatorValue(bb_m15, 2, m15_shift);
      double m15_atr_val = GetIndicatorValue(atr_m15, 0, m15_shift);
      
      //--- Get M30 indicators
      double m30_rsi_val = GetIndicatorValue(rsi_m30, 0, m30_shift);
      double m30_macd_main = GetIndicatorValue(macd_m30, 0, m30_shift);
      double m30_macd_sig = GetIndicatorValue(macd_m30, 1, m30_shift);
      double m30_bb_up = GetIndicatorValue(bb_m30, 0, m30_shift);
      double m30_bb_mid = GetIndicatorValue(bb_m30, 1, m30_shift);
      double m30_bb_low = GetIndicatorValue(bb_m30, 2, m30_shift);
      double m30_atr_val = GetIndicatorValue(atr_m30, 0, m30_shift);
      
      //--- Get H1 indicators
      double h1_rsi_val = GetIndicatorValue(rsi_h1, 0, h1_shift);
      double h1_macd_main = GetIndicatorValue(macd_h1, 0, h1_shift);
      double h1_macd_sig = GetIndicatorValue(macd_h1, 1, h1_shift);
      double h1_bb_up = GetIndicatorValue(bb_h1, 0, h1_shift);
      double h1_bb_mid = GetIndicatorValue(bb_h1, 1, h1_shift);
      double h1_bb_low = GetIndicatorValue(bb_h1, 2, h1_shift);
      double h1_atr_val = GetIndicatorValue(atr_h1, 0, h1_shift);
      
      //--- Get H4 indicators
      double h4_rsi_val = GetIndicatorValue(rsi_h4, 0, h4_shift);
      double h4_macd_main = GetIndicatorValue(macd_h4, 0, h4_shift);
      double h4_macd_sig = GetIndicatorValue(macd_h4, 1, h4_shift);
      double h4_bb_up = GetIndicatorValue(bb_h4, 0, h4_shift);
      double h4_bb_mid = GetIndicatorValue(bb_h4, 1, h4_shift);
      double h4_bb_low = GetIndicatorValue(bb_h4, 2, h4_shift);
      double h4_atr_val = GetIndicatorValue(atr_h4, 0, h4_shift);
      
      //--- Get D1 indicators
      double d1_rsi_val = GetIndicatorValue(rsi_d1, 0, d1_shift);
      double d1_macd_main = GetIndicatorValue(macd_d1, 0, d1_shift);
      double d1_macd_sig = GetIndicatorValue(macd_d1, 1, d1_shift);
      double d1_bb_up = GetIndicatorValue(bb_d1, 0, d1_shift);
      double d1_bb_mid = GetIndicatorValue(bb_d1, 1, d1_shift);
      double d1_bb_low = GetIndicatorValue(bb_d1, 2, d1_shift);
      double d1_atr_val = GetIndicatorValue(atr_d1, 0, d1_shift);
      
      //--- Calculate target (next M5 close direction)
      MqlRates next_m5[];
      int target = 0;  // 0 = SELL, 1 = BUY
      if(CopyRates(symbol, PERIOD_M5, i-1, 1, next_m5) == 1)
      {
         target = (next_m5[0].close > m5_rates[0].close) ? 1 : 0;
      }
      
      //--- Build CSV row
      string row = TimeToString(bar_time, TIME_DATE|TIME_SECONDS) + "," + symbol + ",";
      
      // M5 data
      row += DoubleToString(m5_rates[0].open, 5) + "," + 
             DoubleToString(m5_rates[0].high, 5) + "," + 
             DoubleToString(m5_rates[0].low, 5) + "," + 
             DoubleToString(m5_rates[0].close, 5) + "," + 
             IntegerToString(m5_rates[0].tick_volume) + "," + 
             IntegerToString(m5_rates[0].spread) + "," +
             DoubleToString(m5_rsi_val, 2) + "," +
             DoubleToString(m5_macd_main, 5) + "," +
             DoubleToString(m5_macd_sig, 5) + "," +
             DoubleToString(m5_bb_up, 5) + "," +
             DoubleToString(m5_bb_mid, 5) + "," +
             DoubleToString(m5_bb_low, 5) + "," +
             DoubleToString(m5_atr_val, 5) + ",";
      
      // M15 data
      row += DoubleToString(m15_rates[0].open, 5) + "," + 
             DoubleToString(m15_rates[0].high, 5) + "," + 
             DoubleToString(m15_rates[0].low, 5) + "," + 
             DoubleToString(m15_rates[0].close, 5) + "," + 
             IntegerToString(m15_rates[0].tick_volume) + "," +
             DoubleToString(m15_rsi_val, 2) + "," +
             DoubleToString(m15_macd_main, 5) + "," +
             DoubleToString(m15_macd_sig, 5) + "," +
             DoubleToString(m15_bb_up, 5) + "," +
             DoubleToString(m15_bb_mid, 5) + "," +
             DoubleToString(m15_bb_low, 5) + "," +
             DoubleToString(m15_atr_val, 5) + ",";
      
      // M30 data
      row += DoubleToString(m30_rates[0].open, 5) + "," + 
             DoubleToString(m30_rates[0].high, 5) + "," + 
             DoubleToString(m30_rates[0].low, 5) + "," + 
             DoubleToString(m30_rates[0].close, 5) + "," + 
             IntegerToString(m30_rates[0].tick_volume) + "," +
             DoubleToString(m30_rsi_val, 2) + "," +
             DoubleToString(m30_macd_main, 5) + "," +
             DoubleToString(m30_macd_sig, 5) + "," +
             DoubleToString(m30_bb_up, 5) + "," +
             DoubleToString(m30_bb_mid, 5) + "," +
             DoubleToString(m30_bb_low, 5) + "," +
             DoubleToString(m30_atr_val, 5) + ",";
      
      // H1 data
      row += DoubleToString(h1_rates[0].open, 5) + "," + 
             DoubleToString(h1_rates[0].high, 5) + "," + 
             DoubleToString(h1_rates[0].low, 5) + "," + 
             DoubleToString(h1_rates[0].close, 5) + "," + 
             IntegerToString(h1_rates[0].tick_volume) + "," +
             DoubleToString(h1_rsi_val, 2) + "," +
             DoubleToString(h1_macd_main, 5) + "," +
             DoubleToString(h1_macd_sig, 5) + "," +
             DoubleToString(h1_bb_up, 5) + "," +
             DoubleToString(h1_bb_mid, 5) + "," +
             DoubleToString(h1_bb_low, 5) + "," +
             DoubleToString(h1_atr_val, 5) + ",";
      
      // H4 data
      row += DoubleToString(h4_rates[0].open, 5) + "," + 
             DoubleToString(h4_rates[0].high, 5) + "," + 
             DoubleToString(h4_rates[0].low, 5) + "," + 
             DoubleToString(h4_rates[0].close, 5) + "," + 
             IntegerToString(h4_rates[0].tick_volume) + "," +
             DoubleToString(h4_rsi_val, 2) + "," +
             DoubleToString(h4_macd_main, 5) + "," +
             DoubleToString(h4_macd_sig, 5) + "," +
             DoubleToString(h4_bb_up, 5) + "," +
             DoubleToString(h4_bb_mid, 5) + "," +
             DoubleToString(h4_bb_low, 5) + "," +
             DoubleToString(h4_atr_val, 5) + ",";
      
      // D1 data
      row += DoubleToString(d1_rates[0].open, 5) + "," + 
             DoubleToString(d1_rates[0].high, 5) + "," + 
             DoubleToString(d1_rates[0].low, 5) + "," + 
             DoubleToString(d1_rates[0].close, 5) + "," + 
             IntegerToString(d1_rates[0].tick_volume) + "," +
             DoubleToString(d1_rsi_val, 2) + "," +
             DoubleToString(d1_macd_main, 5) + "," +
             DoubleToString(d1_macd_sig, 5) + "," +
             DoubleToString(d1_bb_up, 5) + "," +
             DoubleToString(d1_bb_mid, 5) + "," +
             DoubleToString(d1_bb_low, 5) + "," +
             DoubleToString(d1_atr_val, 5) + ",";
      
      // Target
      row += IntegerToString(target);
      
      //--- Write row
      FileWrite(fileHandle, row);
      exported++;
      
      //--- Progress update every 1000 bars
      if(exported % 1000 == 0)
      {
         Print("Progress: ", exported, " / ", BarsToExport, " bars exported (", 
               (exported * 100.0 / BarsToExport), "%)");
      }
   }
   
   //--- Close file
   FileClose(fileHandle);
   
   Print("═══════════════════════════════════════════════════════════════════");
   Print("✅ EXPORT COMPLETE");
   Print("═══════════════════════════════════════════════════════════════════");
   Print("Total bars exported: ", exported);
   Print("File: ", ExportPath);
   Print("Location: ", TerminalInfoString(TERMINAL_DATA_PATH), "\\MQL5\\Files\\", ExportPath);
   Print("═══════════════════════════════════════════════════════════════════");
   
   //--- Release indicator handles
   IndicatorRelease(rsi_m5);
   IndicatorRelease(macd_m5);
   IndicatorRelease(bb_m5);
   IndicatorRelease(atr_m5);
   IndicatorRelease(rsi_m15);
   IndicatorRelease(macd_m15);
   IndicatorRelease(bb_m15);
   IndicatorRelease(atr_m15);
   IndicatorRelease(rsi_m30);
   IndicatorRelease(macd_m30);
   IndicatorRelease(bb_m30);
   IndicatorRelease(atr_m30);
   IndicatorRelease(rsi_h1);
   IndicatorRelease(macd_h1);
   IndicatorRelease(bb_h1);
   IndicatorRelease(atr_h1);
   IndicatorRelease(rsi_h4);
   IndicatorRelease(macd_h4);
   IndicatorRelease(bb_h4);
   IndicatorRelease(atr_h4);
   IndicatorRelease(rsi_d1);
   IndicatorRelease(macd_d1);
   IndicatorRelease(bb_d1);
   IndicatorRelease(atr_d1);
}

//+------------------------------------------------------------------+
//| Helper function to get indicator value                           |
//+------------------------------------------------------------------+
double GetIndicatorValue(int handle, int buffer, int shift)
{
   double value[];
   ArraySetAsSeries(value, true);
   
   if(CopyBuffer(handle, buffer, shift, 1, value) != 1)
      return 0.0;
   
   return value[0];
}
//+------------------------------------------------------------------+
