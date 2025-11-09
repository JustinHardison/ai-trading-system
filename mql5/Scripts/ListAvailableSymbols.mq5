//+------------------------------------------------------------------+
//|                                      ListAvailableSymbols.mq5 |
//|                           Query MT5 for all available symbols |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "1.00"
#property script_show_inputs

//+------------------------------------------------------------------+
//| Script program start function                                    |
//+------------------------------------------------------------------+
void OnStart()
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("MT5 AVAILABLE SYMBOLS REPORT");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");

    // Get ALL symbols (not just selected ones)
    // false = get ALL symbols in Market Watch + available in platform
    // true = only get selected symbols
    int totalSymbols = SymbolsTotal(false);
    Print("Total symbols in MT5: ", totalSymbols);
    Print("");

    // Look for US indices and major instruments
    Print("═══════════════════════════════════════════════════════════════════");
    Print("US INDICES & MAJOR INSTRUMENTS");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");

    string interestedSymbols[];
    int count = 0;

    for(int i = 0; i < totalSymbols; i++)
    {
        string symbolName = SymbolName(i, false);  // false = get ALL symbols
        string upper = symbolName;
        StringToUpper(upper);

        // Check if it's a US index or major instrument
        if(StringFind(upper, "US30") >= 0 ||
           StringFind(upper, "US100") >= 0 ||
           StringFind(upper, "NAS") >= 0 ||
           StringFind(upper, "SPX") >= 0 ||
           StringFind(upper, "SP500") >= 0 ||
           StringFind(upper, "S&P") >= 0 ||
           StringFind(upper, "DOW") >= 0 ||
           StringFind(upper, "GOLD") >= 0 ||
           StringFind(upper, "XAU") >= 0 ||
           StringFind(upper, "OIL") >= 0 ||
           StringFind(upper, "WTI") >= 0 ||
           StringFind(upper, "GER") >= 0 ||
           StringFind(upper, "DAX") >= 0)
        {
            ArrayResize(interestedSymbols, count + 1);
            interestedSymbols[count] = symbolName;
            count++;
        }
    }

    if(count == 0)
    {
        Print("⚠️  No US indices found in specific search");
        Print("    Showing ALL available symbols instead:");
        Print("");

        // Show all symbols if no specific ones found
        for(int i = 0; i < MathMin(totalSymbols, 100); i++)
        {
            string symbolName = SymbolName(i, false);  // false = ALL symbols
            PrintSymbolInfo(symbolName);
        }
    }
    else
    {
        // Print detailed info for interested symbols
        for(int i = 0; i < count; i++)
        {
            PrintSymbolInfo(interestedSymbols[i]);
        }
    }

    // Check for .sim symbols (FTMO simulated)
    Print("");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("FTMO .SIM SYMBOLS (Simulated Assets)");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");

    int simCount = 0;
    for(int i = 0; i < totalSymbols; i++)
    {
        string symbolName = SymbolName(i, false);  // false = ALL symbols
        if(StringFind(symbolName, ".sim") >= 0 || StringFind(symbolName, ".SIM") >= 0)
        {
            Print("✅ ", symbolName, ": ", SymbolInfoString(symbolName, SYMBOL_DESCRIPTION));
            simCount++;
        }
    }

    if(simCount == 0)
    {
        Print("❌ No .sim symbols found");
        Print("   You may not be on FTMO US / OANDA account");
    }

    // Current symbol detailed info
    Print("");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("CURRENT CHART SYMBOL: ", _Symbol);
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");
    PrintSymbolInfo(_Symbol);

    // Recommendations
    Print("");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("RECOMMENDATION FOR MULTI-SYMBOL TRADING");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("");

    if(count > 0)
    {
        Print("Found ", count, " tradeable index symbols:");
        for(int i = 0; i < count; i++)
        {
            bool isTradeable = (SymbolInfoInteger(interestedSymbols[i], SYMBOL_TRADE_MODE) != SYMBOL_TRADE_MODE_DISABLED);
            string status = isTradeable ? "✅ TRADEABLE" : "❌ NOT TRADEABLE";
            Print("  ", status, " - ", interestedSymbols[i]);
        }
    }
    else
    {
        Print("❌ No suitable US index symbols found for multi-symbol trading");
    }

    Print("");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("Report complete. Check the Experts log for full details.");
    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Print detailed symbol information                                 |
//+------------------------------------------------------------------+
void PrintSymbolInfo(string symbolName)
{
    // Select the symbol first
    SymbolSelect(symbolName, true);

    string description = SymbolInfoString(symbolName, SYMBOL_DESCRIPTION);
    bool visible = SymbolInfoInteger(symbolName, SYMBOL_VISIBLE);
    int tradeMode = (int)SymbolInfoInteger(symbolName, SYMBOL_TRADE_MODE);
    double point = SymbolInfoDouble(symbolName, SYMBOL_POINT);
    int digits = (int)SymbolInfoInteger(symbolName, SYMBOL_DIGITS);
    int spread = (int)SymbolInfoInteger(symbolName, SYMBOL_SPREAD);
    double volumeMin = SymbolInfoDouble(symbolName, SYMBOL_VOLUME_MIN);
    double volumeMax = SymbolInfoDouble(symbolName, SYMBOL_VOLUME_MAX);
    double volumeStep = SymbolInfoDouble(symbolName, SYMBOL_VOLUME_STEP);
    double bid = SymbolInfoDouble(symbolName, SYMBOL_BID);
    double ask = SymbolInfoDouble(symbolName, SYMBOL_ASK);

    string tradeModeStr;
    switch(tradeMode)
    {
        case SYMBOL_TRADE_MODE_DISABLED: tradeModeStr = "DISABLED"; break;
        case SYMBOL_TRADE_MODE_LONGONLY: tradeModeStr = "LONG ONLY"; break;
        case SYMBOL_TRADE_MODE_SHORTONLY: tradeModeStr = "SHORT ONLY"; break;
        case SYMBOL_TRADE_MODE_CLOSEONLY: tradeModeStr = "CLOSE ONLY"; break;
        case SYMBOL_TRADE_MODE_FULL: tradeModeStr = "FULL"; break;
        default: tradeModeStr = "UNKNOWN"; break;
    }

    Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Print("Symbol: ", symbolName);
    Print("  Description: ", description);
    Print("  Visible: ", visible ? "Yes" : "No");
    Print("  Trade Mode: ", tradeModeStr);
    Print("  Current Bid: ", bid);
    Print("  Current Ask: ", ask);
    Print("  Point: ", point);
    Print("  Digits: ", digits);
    Print("  Spread: ", spread, " points");
    Print("  Volume Min: ", volumeMin);
    Print("  Volume Max: ", volumeMax);
    Print("  Volume Step: ", volumeStep);
    Print("");
}
//+------------------------------------------------------------------+
