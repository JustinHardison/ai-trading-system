//+------------------------------------------------------------------+
//|                                     ExportAllSymbolsData.mq5 |
//|              Export historical data for ALL FTMO symbols        |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "1.00"
#property script_show_inputs

//--- Input parameters
input int BarsToExport = 100000;  // Number of bars to export per symbol
input ENUM_TIMEFRAMES ExportTimeframe = PERIOD_M1;  // Timeframe to export

//--- Will be populated dynamically from MT5
string Symbols[];

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("EXPORTING HISTORICAL DATA FOR ALL TRADEABLE MT5 SYMBOLS");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("Timeframe: ", EnumToString(ExportTimeframe));
    Print("Bars to export: ", BarsToExport);
    Print("");

    // Dynamically discover ALL tradeable symbols from MT5
    Print("Scanning MT5 for tradeable symbols...");
    DiscoverTradeableSymbols();
    
    Print("Total symbols found: ", ArraySize(Symbols));
    Print("");

    string exportPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\";
    Print("Export path: ", exportPath);
    Print("");

    // Export each symbol
    for(int i = 0; i < ArraySize(Symbols); i++)
    {
        string symbol = Symbols[i];

        Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        Print("[", i+1, "/", ArraySize(Symbols), "] Processing: ", symbol);
        Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        // Ensure symbol is selected
        if(!SymbolSelect(symbol, true))
        {
            Print("❌ Failed to select symbol: ", symbol);
            continue;
        }

        // Get symbol info
        Print("Symbol: ", symbol);
        Print("Description: ", SymbolInfoString(symbol, SYMBOL_DESCRIPTION));
        Print("Current price: ", SymbolInfoDouble(symbol, SYMBOL_BID));

        // Export the data
        if(ExportSymbolData(symbol, ExportTimeframe, BarsToExport))
        {
            Print("✅ Successfully exported ", symbol);
        }
        else
        {
            Print("❌ Failed to export ", symbol);
        }

        Print("");
    }

    Print("═══════════════════════════════════════════════════════════════════");
    Print("EXPORT COMPLETE");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");
    Print("Files saved to: ", exportPath);
    Print("");
    Print("Next steps:");
    Print("1. Copy CSV files from MT5 Files folder to ~/ai-trading-system/");
    Print("2. Train ML models for each symbol");
    Print("3. Test each symbol individually");
    Print("4. Deploy multi-symbol trading");
    Print("");
    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Export data for a single symbol                                  |
//+------------------------------------------------------------------+
bool ExportSymbolData(string symbol, ENUM_TIMEFRAMES timeframe, int bars)
{
    // Create filename: symbol_timeframe_historical_data.csv
    string tfString = "";
    switch(timeframe)
    {
        case PERIOD_M1: tfString = "m1"; break;
        case PERIOD_M5: tfString = "m5"; break;
        case PERIOD_M15: tfString = "m15"; break;
        case PERIOD_M30: tfString = "m30"; break;
        case PERIOD_H1: tfString = "h1"; break;
        case PERIOD_H4: tfString = "h4"; break;
        case PERIOD_D1: tfString = "d1"; break;
        default: tfString = "m1"; break;
    }

    // Clean symbol name for filename (remove .sim and contract month)
    string cleanSymbol = symbol;
    StringReplace(cleanSymbol, ".sim", "");
    StringReplace(cleanSymbol, "Z25", "");
    StringReplace(cleanSymbol, "G26", "");
    StringReplace(cleanSymbol, "F26", "");
    StringToLower(cleanSymbol);

    string filename = cleanSymbol + "_" + tfString + "_historical_data.csv";

    Print("Creating file: ", filename);

    // Open file for writing
    int fileHandle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
    if(fileHandle == INVALID_HANDLE)
    {
        Print("❌ Error opening file: ", GetLastError());
        return false;
    }

    // Write header
    FileWrite(fileHandle, "timestamp", "open", "high", "low", "close", "volume",
              "tick_volume", "spread", "real_volume");

    // Get available bars
    int available = Bars(symbol, timeframe);
    if(available <= 0)
    {
        Print("❌ No bars available for ", symbol);
        FileClose(fileHandle);
        return false;
    }

    int barsToGet = MathMin(bars, available);
    Print("Available bars: ", available);
    Print("Exporting: ", barsToGet, " bars");

    // Copy price data
    MqlRates rates[];
    ArraySetAsSeries(rates, true);

    int copied = CopyRates(symbol, timeframe, 0, barsToGet, rates);
    if(copied <= 0)
    {
        Print("❌ Failed to copy rates: ", GetLastError());
        FileClose(fileHandle);
        return false;
    }

    Print("Copied ", copied, " bars, writing to file...");

    // Write data (newest to oldest for training)
    int written = 0;
    for(int i = copied - 1; i >= 0; i--)  // Reverse order: oldest to newest
    {
        datetime time = rates[i].time;
        double open = rates[i].open;
        double high = rates[i].high;
        double low = rates[i].low;
        double close = rates[i].close;
        long tick_volume = rates[i].tick_volume;
        int spread = rates[i].spread;
        long real_volume = rates[i].real_volume;

        // Write row
        FileWrite(fileHandle,
                  TimeToString(time, TIME_DATE|TIME_MINUTES),
                  DoubleToString(open, _Digits),
                  DoubleToString(high, _Digits),
                  DoubleToString(low, _Digits),
                  DoubleToString(close, _Digits),
                  tick_volume,
                  tick_volume,
                  spread,
                  real_volume);

        written++;

        // Progress indicator
        if(written % 10000 == 0)
        {
            Print("  Progress: ", written, " / ", copied, " bars (",
                  (written * 100 / copied), "%)");
        }
    }

    FileClose(fileHandle);

    Print("✅ Wrote ", written, " bars to ", filename);
    Print("File size: ", FileSize(fileHandle), " bytes");

    return true;
}

//+------------------------------------------------------------------+
//| Discover all tradeable symbols from MT5                          |
//+------------------------------------------------------------------+
void DiscoverTradeableSymbols()
{
    int totalSymbols = SymbolsTotal(false);  // false = ALL symbols
    int count = 0;
    
    Print("  Scanning ", totalSymbols, " symbols in MT5...");
    
    for(int i = 0; i < totalSymbols; i++)
    {
        string symbolName = SymbolName(i, false);
        
        // Select the symbol to get its properties
        if(!SymbolSelect(symbolName, true))
            continue;
            
        // Check if symbol is tradeable
        int tradeMode = (int)SymbolInfoInteger(symbolName, SYMBOL_TRADE_MODE);
        if(tradeMode == SYMBOL_TRADE_MODE_DISABLED)
            continue;
            
        // Check if symbol has data
        int bars = Bars(symbolName, ExportTimeframe);
        if(bars < 100)
            continue;
            
        // Add to our list
        ArrayResize(Symbols, count + 1);
        Symbols[count] = symbolName;
        count++;
        
        // Show progress every 100 symbols
        if(count % 10 == 0)
            Print("  Found ", count, " tradeable symbols so far...");
    }
    
    Print("✅ Discovered ", count, " tradeable symbols with sufficient data");
    
    // Show the symbols we found
    if(count > 0 && count <= 20)
    {
        Print("\nSymbols to export:");
        for(int i = 0; i < count; i++)
        {
            Print("  ", (i+1), ". ", Symbols[i]);
        }
    }
    else if(count > 20)
    {
        Print("\nFirst 20 symbols to export:");
        for(int i = 0; i < 20; i++)
        {
            Print("  ", (i+1), ". ", Symbols[i]);
        }
        Print("  ... and ", (count - 20), " more");
    }
}
//+------------------------------------------------------------------+
