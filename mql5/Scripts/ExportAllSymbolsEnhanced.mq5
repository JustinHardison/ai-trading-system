//+------------------------------------------------------------------+
//|                                   ExportAllSymbolsEnhanced.mq5   |
//|                      Enhanced Symbol Discovery & Data Export     |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "2.00"
#property script_show_inputs

//--- Input Parameters
input int      BarsToExport = 100000;        // Number of bars to export
input ENUM_TIMEFRAMES ExportTimeframe = PERIOD_M1;  // Timeframe to export
input bool     ExportAllAvailable = true;    // Export ALL available symbols
input bool     IncludeSimSymbols = true;     // Include .sim symbols
input bool     VerboseLogging = true;        // Detailed logging

//--- Global Variables
string Symbols[];
int TotalSymbolsFound = 0;
int TotalSymbolsExported = 0;

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("ENHANCED SYMBOL DISCOVERY & DATA EXPORT");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("Timeframe: ", EnumToString(ExportTimeframe));
    Print("Bars to export: ", BarsToExport);
    Print("Export all available: ", ExportAllAvailable ? "YES" : "NO");
    Print("Include .sim symbols: ", IncludeSimSymbols ? "YES" : "NO");
    Print("");

    // Discover ALL symbols
    Print("🔍 PHASE 1: DISCOVERING SYMBOLS...");
    DiscoverAllSymbols();
    
    Print("\n📊 PHASE 2: EXPORTING DATA...");
    ExportAllSymbolData();
    
    Print("\n═══════════════════════════════════════════════════════════════════");
    Print("✅ EXPORT COMPLETE");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("Total symbols found: ", TotalSymbolsFound);
    Print("Total symbols exported: ", TotalSymbolsExported);
    Print("Failed exports: ", TotalSymbolsFound - TotalSymbolsExported);
    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Discover ALL available symbols (enhanced)                        |
//+------------------------------------------------------------------+
void DiscoverAllSymbols()
{
    int count = 0;
    
    // Method 1: Get ALL symbols (not just selected)
    int totalSymbols = SymbolsTotal(false);  // false = ALL symbols in terminal
    
    Print("  Scanning ", totalSymbols, " symbols in MT5 terminal...\n");
    
    for(int i = 0; i < totalSymbols; i++)
    {
        string symbolName = SymbolName(i, false);
        
        // Select symbol to access its properties
        if(!SymbolSelect(symbolName, true))
        {
            if(VerboseLogging)
                Print("  ⏭️  ", symbolName, ": Cannot select");
            continue;
        }
        
        // Check if symbol is visible (available for trading)
        bool isVisible = (bool)SymbolInfoInteger(symbolName, SYMBOL_VISIBLE);
        
        // Check trade mode
        ENUM_SYMBOL_TRADE_MODE tradeMode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbolName, SYMBOL_TRADE_MODE);
        
        // Filter criteria
        bool isSimSymbol = (StringFind(symbolName, ".sim") >= 0);
        bool shouldInclude = false;
        
        // Decide if we should include this symbol
        if(ExportAllAvailable)
        {
            // Include if tradeable OR if it's a .sim symbol we want
            if(tradeMode != SYMBOL_TRADE_MODE_DISABLED)
                shouldInclude = true;
            else if(IncludeSimSymbols && isSimSymbol)
                shouldInclude = true;
        }
        else
        {
            // Only include if visible in Market Watch
            if(isVisible && tradeMode != SYMBOL_TRADE_MODE_DISABLED)
                shouldInclude = true;
        }
        
        if(!shouldInclude)
        {
            if(VerboseLogging)
                Print("  ⏭️  ", symbolName, ": Filtered out (trade mode: ", EnumToString(tradeMode), ")");
            continue;
        }
        
        // Check if symbol has sufficient data
        int bars = Bars(symbolName, ExportTimeframe);
        if(bars < 100)
        {
            if(VerboseLogging)
                Print("  ⏭️  ", symbolName, ": Insufficient data (", bars, " bars)");
            continue;
        }
        
        // Add to export list
        ArrayResize(Symbols, count + 1);
        Symbols[count] = symbolName;
        count++;
        
        if(VerboseLogging || count % 10 == 0)
            Print("  ✅ ", symbolName, ": ", bars, " bars available");
    }
    
    TotalSymbolsFound = count;
    
    Print("\n✅ Found ", count, " tradeable symbols with sufficient data\n");
    
    // Display symbols
    if(count > 0)
    {
        Print("SYMBOLS TO EXPORT:");
        Print("─────────────────────────────────────────────────────────────");
        
        int displayLimit = 50;  // Show first 50
        for(int i = 0; i < MathMin(count, displayLimit); i++)
        {
            int bars = Bars(Symbols[i], ExportTimeframe);
            string symbolType = GetSymbolType(Symbols[i]);
            Print("  ", (i+1), ". ", Symbols[i], " (", symbolType, ") - ", bars, " bars");
        }
        
        if(count > displayLimit)
            Print("  ... and ", (count - displayLimit), " more symbols");
            
        Print("─────────────────────────────────────────────────────────────\n");
    }
}

//+------------------------------------------------------------------+
//| Get symbol type for categorization                               |
//+------------------------------------------------------------------+
string GetSymbolType(string symbol)
{
    if(StringFind(symbol, "US30") >= 0 || StringFind(symbol, "US100") >= 0 || 
       StringFind(symbol, "US500") >= 0 || StringFind(symbol, "NAS") >= 0 ||
       StringFind(symbol, "SPX") >= 0 || StringFind(symbol, "DOW") >= 0)
        return "US Index";
        
    if(StringFind(symbol, "GER") >= 0 || StringFind(symbol, "DAX") >= 0 ||
       StringFind(symbol, "UK100") >= 0 || StringFind(symbol, "FTSE") >= 0 ||
       StringFind(symbol, "FRA") >= 0 || StringFind(symbol, "CAC") >= 0)
        return "EU Index";
        
    if(StringFind(symbol, "XAU") >= 0 || StringFind(symbol, "GOLD") >= 0)
        return "Gold";
        
    if(StringFind(symbol, "XAG") >= 0 || StringFind(symbol, "SILVER") >= 0)
        return "Silver";
        
    if(StringFind(symbol, "OIL") >= 0 || StringFind(symbol, "WTI") >= 0 || 
       StringFind(symbol, "BRENT") >= 0)
        return "Energy";
        
    if(StringFind(symbol, "USD") >= 0 || StringFind(symbol, "EUR") >= 0 ||
       StringFind(symbol, "GBP") >= 0 || StringFind(symbol, "JPY") >= 0)
        return "Forex";
        
    return "Other";
}

//+------------------------------------------------------------------+
//| Export data for all discovered symbols                           |
//+------------------------------------------------------------------+
void ExportAllSymbolData()
{
    string exportPath = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\";
    
    for(int i = 0; i < ArraySize(Symbols); i++)
    {
        string symbol = Symbols[i];
        
        Print("─────────────────────────────────────────────────────────────");
        Print("Exporting ", (i+1), "/", ArraySize(Symbols), ": ", symbol);
        
        if(ExportSymbolData(symbol, exportPath))
        {
            TotalSymbolsExported++;
            Print("✅ ", symbol, " exported successfully");
        }
        else
        {
            Print("❌ ", symbol, " export failed");
        }
    }
}

//+------------------------------------------------------------------+
//| Export single symbol data                                        |
//+------------------------------------------------------------------+
bool ExportSymbolData(string symbol, string path)
{
    // Create filename
    string filename = StringToLower(symbol);
    StringReplace(filename, ".sim", "");
    StringReplace(filename, "z25", "");
    StringReplace(filename, "f26", "");
    filename = filename + "_m1_historical_data.csv";
    
    // Open file
    int fileHandle = FileOpen(filename, FILE_WRITE|FILE_CSV|FILE_ANSI);
    
    if(fileHandle == INVALID_HANDLE)
    {
        Print("  ❌ Failed to create file: ", filename);
        return false;
    }
    
    // Write header
    FileWrite(fileHandle, "timestamp", "open", "high", "low", "close", "volume");
    
    // Get data
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    
    int copied = CopyRates(symbol, ExportTimeframe, 0, BarsToExport, rates);
    
    if(copied <= 0)
    {
        Print("  ❌ No data copied for ", symbol);
        FileClose(fileHandle);
        return false;
    }
    
    // Write data
    int written = 0;
    for(int i = copied - 1; i >= 0; i--)
    {
        FileWrite(fileHandle,
                 TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS),
                 DoubleToString(rates[i].open, _Digits),
                 DoubleToString(rates[i].high, _Digits),
                 DoubleToString(rates[i].low, _Digits),
                 DoubleToString(rates[i].close, _Digits),
                 IntegerToString(rates[i].tick_volume));
        written++;
    }
    
    FileClose(fileHandle);
    
    Print("  📊 Exported ", written, " bars to: ", filename);
    
    return true;
}

//+------------------------------------------------------------------+
//| Convert string to lowercase                                      |
//+------------------------------------------------------------------+
string StringToLower(string str)
{
    string result = str;
    StringToLower(result);
    return result;
}
//+------------------------------------------------------------------+
