//+------------------------------------------------------------------+
//|                                         AI_MultiSymbol_EA.mq5 |
//|              Multi-Symbol AI Trading - Indices + Forex + Commodities |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "2.00"
#property description "Multi-Symbol AI Trading: US30, US100, US500, EURUSD, GBPUSD, USDJPY, XAU, USOIL"

//--- Input Parameters
input string   API_URL = "http://localhost:5007/api/ai/trade_decision";
input double   FixedLotSize = 0.0;  // 0 = AI decides size
input int      MagicNumber = 123456;
input int      MaxBarsHeld = 200;
input bool     EnableTrading = true;
input bool     VerboseLogging = true;

//--- Symbols to trade (Indices + Forex + Commodities)
string TradingSymbols[] = {
    "US30Z25.sim",    // Dow Jones
    "US100Z25.sim",   // Nasdaq
    "US500Z25.sim",   // S&P 500
    "EURUSD",         // Euro/Dollar
    "GBPUSD",         // Pound/Dollar
    "USDJPY",         // Dollar/Yen
    "XAUUSD",         // Gold
    "USOIL"           // Oil
};
int SymbolCount = 8;

//--- Tracking per symbol
datetime lastBarTime[];
int positionBarsHeld[];

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("MULTI-SYMBOL AI TRADING SYSTEM v2.00 - INITIALIZATION");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("API Endpoint: ", API_URL);
    Print("Trading Symbols: ", SymbolCount, " symbols");

    // Initialize arrays
    ArrayResize(lastBarTime, SymbolCount);
    ArrayResize(positionBarsHeld, SymbolCount);

    for(int i = 0; i < SymbolCount; i++)
    {
        lastBarTime[i] = 0;
        positionBarsHeld[i] = 0;

        // Ensure symbol is selected in Market Watch
        if(!SymbolSelect(TradingSymbols[i], true))
        {
            Print("⚠️  Failed to select symbol: ", TradingSymbols[i]);
        }
        else
        {
            Print("  ✅ ", TradingSymbols[i], " - ", SymbolInfoString(TradingSymbols[i], SYMBOL_DESCRIPTION));
        }
    }

    Print("Magic Number: ", MagicNumber);
    Print("Trading: ", EnableTrading ? "ENABLED" : "DISABLED (Monitor Mode)");
    Print("═══════════════════════════════════════════════════════════════════");

    // Verify API connection
    if(!TestAPIConnection())
    {
        Print("❌ WARNING: Cannot reach AI API");
        Print("   Start API: cd ~/ai-trading-system && python3 api.py");
    }
    else
    {
        Print("✅ AI API Connection Verified");
        Print("✅ Trading: 3 Indices + 3 Forex + 2 Commodities");
        Print("   Indices: US30, US100, US500");
        Print("   Forex: EURUSD, GBPUSD, USDJPY");
        Print("   Commodities: XAUUSD, USOIL");
    }

    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("Multi-Symbol AI Trading EA Stopped - Reason: ", reason);
    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    // Process each symbol independently
    for(int i = 0; i < SymbolCount; i++)
    {
        string symbol = TradingSymbols[i];

        // Check for new bar on this symbol
        datetime currentBarTime = iTime(symbol, PERIOD_M1, 0);
        if(currentBarTime == lastBarTime[i])
            continue;  // No new bar for this symbol

        lastBarTime[i] = currentBarTime;

        // Update position tracking for this symbol
        if(HasPositionForSymbol(symbol))
        {
            positionBarsHeld[i]++;

            // Check max hold time
            if(positionBarsHeld[i] >= MaxBarsHeld)
            {
                Print("⏰ [", symbol, "] MAX HOLD TIME REACHED - Closing position");
                ClosePositionsForSymbol(symbol);
                positionBarsHeld[i] = 0;
            }
        }
        else
        {
            positionBarsHeld[i] = 0;

            // Only trade if enabled and no open position for THIS symbol
            if(EnableTrading && !HasPositionForSymbol(symbol))
            {
                ProcessSymbol(symbol);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Process trading decision for a symbol                             |
//+------------------------------------------------------------------+
void ProcessSymbol(string symbol)
{
    if(VerboseLogging)
        Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    Print("🔍 [", symbol, "] Analyzing...");

    // Collect market data for this symbol
    string marketData = CollectMarketData(symbol);
    if(marketData == "")
    {
        Print("❌ [", symbol, "] Failed to collect market data");
        return;
    }

    // Send to AI API
    string aiDecision = SendToAPI(marketData);
    if(aiDecision == "")
    {
        Print("❌ [", symbol, "] API Request Failed");
        return;
    }

    // Parse AI decision
    string action = ExtractJSONValue(aiDecision, "action");
    double lotSize = StringToDouble(ExtractJSONValue(aiDecision, "lot_size"));
    string reason = ExtractJSONValue(aiDecision, "reason");

    if(VerboseLogging)
    {
        Print("🧠 [", symbol, "] AI Decision: ", action);
        Print("   Reason: ", reason);
        if(lotSize > 0)
            Print("   Lot Size: ", lotSize);
    }

    // Execute trade if approved
    if(action == "BUY" && lotSize > 0)
    {
        ExecuteTrade(symbol, ORDER_TYPE_BUY, lotSize);
    }
    else if(action == "SELL" && lotSize > 0)
    {
        ExecuteTrade(symbol, ORDER_TYPE_SELL, lotSize);
    }
}

//+------------------------------------------------------------------+
//| Collect market data for symbol                                   |
//+------------------------------------------------------------------+
string CollectMarketData(string symbol)
{
    string json = "{";

    // Current symbol
    json += "\"symbol\": \"" + symbol + "\",";

    // Current price
    double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
    double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
    json += "\"current_price\": {\"bid\": " + DoubleToString(bid, _Digits) + ", \"ask\": " + DoubleToString(ask, _Digits) + "},";

    // Account info
    json += "\"account\": {";
    json += "\"balance\": " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
    json += "\"equity\": " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
    json += "\"margin\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2);
    json += "},";

    // Multi-timeframe data
    json += "\"timeframes\": {";
    json += CollectTimeframeData(symbol, "m1", PERIOD_M1) + ",";
    json += CollectTimeframeData(symbol, "m5", PERIOD_M5) + ",";
    json += CollectTimeframeData(symbol, "m15", PERIOD_M15) + ",";
    json += CollectTimeframeData(symbol, "m30", PERIOD_M30) + ",";
    json += CollectTimeframeData(symbol, "h1", PERIOD_H1) + ",";
    json += CollectTimeframeData(symbol, "h4", PERIOD_H4) + ",";
    json += CollectTimeframeData(symbol, "d1", PERIOD_D1);
    json += "}";

    json += "}";
    return json;
}

//+------------------------------------------------------------------+
//| Collect data for specific timeframe                              |
//+------------------------------------------------------------------+
string CollectTimeframeData(string symbol, string tfName, ENUM_TIMEFRAMES period)
{
    int bars = 50;
    string json = "\"" + tfName + "\": [";

    for(int i = bars - 1; i >= 0; i--)
    {
        double open = iOpen(symbol, period, i);
        double high = iHigh(symbol, period, i);
        double low = iLow(symbol, period, i);
        double close = iClose(symbol, period, i);
        long volume = iVolume(symbol, period, i);

        if(i < bars - 1) json += ",";
        json += "{";
        json += "\"open\": " + DoubleToString(open, _Digits) + ",";
        json += "\"high\": " + DoubleToString(high, _Digits) + ",";
        json += "\"low\": " + DoubleToString(low, _Digits) + ",";
        json += "\"close\": " + DoubleToString(close, _Digits) + ",";
        json += "\"volume\": " + IntegerToString(volume);
        json += "}";
    }

    json += "]";
    return json;
}

//+------------------------------------------------------------------+
//| Send data to API                                                  |
//+------------------------------------------------------------------+
string SendToAPI(string jsonData)
{
    char post[], result[];
    string headers = "Content-Type: application/json\r\n";

    StringToCharArray(jsonData, post, 0, StringLen(jsonData));

    int res = WebRequest("POST", API_URL, headers, 5000, post, result, headers);

    if(res == -1)
    {
        int error = GetLastError();
        Print("❌ API Request Failed - Error: ", error);
        return "";
    }

    return CharArrayToString(result);
}

//+------------------------------------------------------------------+
//| Execute trade                                                     |
//+------------------------------------------------------------------+
void ExecuteTrade(string symbol, ENUM_ORDER_TYPE orderType, double lots)
{
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);

    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lots;
    request.type = orderType;
    request.price = (orderType == ORDER_TYPE_BUY) ?
                    SymbolInfoDouble(symbol, SYMBOL_ASK) :
                    SymbolInfoDouble(symbol, SYMBOL_BID);
    request.deviation = 10;
    request.magic = MagicNumber;
    request.comment = "AI Multi-Symbol";

    if(OrderSend(request, result))
    {
        Print("✅ [", symbol, "] TRADE EXECUTED: ", EnumToString(orderType), " ", lots, " lots @ ", request.price);
    }
    else
    {
        Print("❌ [", symbol, "] Trade failed - Error: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Check if position exists for symbol                              |
//+------------------------------------------------------------------+
bool HasPositionForSymbol(string symbol)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol &&
               PositionGetInteger(POSITION_MAGIC) == MagicNumber)
            {
                return true;
            }
        }
    }
    return false;
}

//+------------------------------------------------------------------+
//| Close positions for symbol                                       |
//+------------------------------------------------------------------+
void ClosePositionsForSymbol(string symbol)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol &&
               PositionGetInteger(POSITION_MAGIC) == MagicNumber)
            {
                MqlTradeRequest request;
                MqlTradeResult result;
                ZeroMemory(request);
                ZeroMemory(result);

                request.action = TRADE_ACTION_DEAL;
                request.position = ticket;
                request.symbol = symbol;
                request.volume = PositionGetDouble(POSITION_VOLUME);
                request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
                request.price = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ?
                                SymbolInfoDouble(symbol, SYMBOL_BID) :
                                SymbolInfoDouble(symbol, SYMBOL_ASK);
                request.deviation = 10;
                request.magic = MagicNumber;

                OrderSend(request, result);
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Extract JSON value                                                |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key)
{
    string searchKey = "\"" + key + "\":";
    int start = StringFind(json, searchKey);
    if(start == -1) return "";

    start += StringLen(searchKey);
    while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '\t'))
        start++;

    bool isString = false;
    if(StringGetCharacter(json, start) == '"')
    {
        isString = true;
        start++;
    }

    int end = start;
    if(isString)
    {
        end = StringFind(json, "\"", start);
    }
    else
    {
        while(end < StringLen(json))
        {
            ushort c = StringGetCharacter(json, end);
            if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r')
                break;
            end++;
        }
    }

    return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Test API connection                                               |
//+------------------------------------------------------------------+
bool TestAPIConnection()
{
    char post[], result[];
    string headers = "Content-Type: application/json\r\n";
    string testData = "{\"test\": true}";

    StringToCharArray(testData, post, 0, StringLen(testData));
    int res = WebRequest("POST", API_URL, headers, 3000, post, result, headers);

    return (res != -1);
}
//+------------------------------------------------------------------+
