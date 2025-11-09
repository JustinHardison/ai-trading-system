//+------------------------------------------------------------------+
//|                                       AITrader_HTTP_ML_Risk.mq5 |
//|                                       AI Trading System v3.0     |
//|                         HTTP-Based with ML/RL Risk Management    |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "3.00"
#property strict

// Include tracking modules
#include <includes/GetTradeHistory.mqh>
#include <includes/DailyTracking.mqh>
#include <includes/DrawdownTracking.mqh>

// API Configuration
input string API_URL = "http://localhost:5007";  // Backend API URL (port 5007 for integrated API)
input int    CHECK_INTERVAL = 3;                 // Check for commands every 3 seconds
input bool   ENABLE_LOGGING = true;             // Enable detailed logging
input int    MAX_TRADE_HISTORY = 50;            // Number of trades to send to ML Risk Manager

// Global variables
datetime lastCheck = 0;
int checkInterval = CHECK_INTERVAL;
TradeData g_trade_history[];

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("═══════════════════════════════════════════════════════════════");
    Print("  AI Trading System HTTP v3.0 with ML/RL Risk Management");
    Print("═══════════════════════════════════════════════════════════════");
    Print("API URL: ", API_URL);
    Print("Check Interval: ", checkInterval, " seconds");
    Print("Max Trade History: ", MAX_TRADE_HISTORY, " trades");

    // Initialize tracking modules
    Print("\n[Initializing Tracking Modules]");
    InitDailyTracking();
    InitDrawdownTracking();

    // Load initial trade history
    if(GetTradeHistory(g_trade_history, MAX_TRADE_HISTORY))
    {
        Print("✅ Loaded ", ArraySize(g_trade_history), " trades from history");

        if(ArraySize(g_trade_history) > 0)
        {
            double win_rate = CalculateWinRate(g_trade_history);
            int streak = CalculateStreak(g_trade_history);
            double pf = CalculateProfitFactor(g_trade_history);

            Print("📊 Historical Performance:");
            Print("   Win Rate: ", DoubleToString(win_rate * 100, 1), "%");
            Print("   Current Streak: ", streak, (streak > 0 ? " wins" : " losses"));
            Print("   Profit Factor: ", DoubleToString(pf, 2));
        }
    }

    // Enable web requests for this URL
    if(!TerminalInfoInteger(TERMINAL_WEBREQUEST_ENABLED))
    {
        Print("ERROR: WebRequest is disabled in terminal settings!");
        Print("Go to Tools -> Options -> Expert Advisors");
        Print("Check 'Allow WebRequest for listed URL' and add: ", API_URL);
        return INIT_FAILED;
    }

    // Test connection
    if(!TestConnection())
    {
        Print("WARNING: Cannot connect to API server. Will retry...");
    }
    else
    {
        Print("✅ API Connection established");
    }

    Print("═══════════════════════════════════════════════════════════════");
    Print("  System Ready - ML/RL Risk Manager Active");
    Print("═══════════════════════════════════════════════════════════════\n");

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("=== AI Trading System HTTP v3.0 Deinitialized ===");
    Print("Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Update tracking modules every tick
    UpdateDailyTracking();
    UpdateDrawdownTracking();

    // Check for commands every X seconds
    datetime currentTime = TimeCurrent();
    if(currentTime - lastCheck >= checkInterval)
    {
        lastCheck = currentTime;

        // Refresh trade history periodically (every 60 seconds)
        static datetime lastHistoryUpdate = 0;
        if(currentTime - lastHistoryUpdate >= 60)
        {
            GetTradeHistory(g_trade_history, MAX_TRADE_HISTORY);
            lastHistoryUpdate = currentTime;
        }

        CheckForCommands();
    }
}

//+------------------------------------------------------------------+
//| Test API connection                                              |
//+------------------------------------------------------------------+
bool TestConnection()
{
    string url = API_URL + "/";
    string headers = "Content-Type: application/json\r\n";
    char data[];
    char result[];
    string resultHeaders;

    int timeout = 5000; // 5 seconds
    int res = WebRequest("GET", url, headers, timeout, data, result, resultHeaders);

    if(res == 200)
    {
        return true;
    }
    else
    {
        Print("✗ API Connection failed. Code: ", res);
        return false;
    }
}

//+------------------------------------------------------------------+
//| Check for pending commands from API                              |
//+------------------------------------------------------------------+
void CheckForCommands()
{
    string url = API_URL + "/api/mt5/commands";
    string headers = "Content-Type: application/json\r\n";
    char data[];
    char result[];
    string resultHeaders;

    int timeout = 5000;
    int res = WebRequest("GET", url, headers, timeout, data, result, resultHeaders);

    if(res == 200)
    {
        string response = CharArrayToString(result);
        ProcessCommands(response);
    }
    else if(res == -1)
    {
        if(ENABLE_LOGGING)
            Print("WebRequest error: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Process commands from API                                        |
//+------------------------------------------------------------------+
void ProcessCommands(string jsonResponse)
{
    // Parse JSON and execute commands
    if(StringFind(jsonResponse, "open_trade") >= 0)
    {
        ExecuteOpenTrade(jsonResponse);
    }
    else if(StringFind(jsonResponse, "close_trade") >= 0)
    {
        ExecuteCloseTrade(jsonResponse);
    }
    else if(StringFind(jsonResponse, "get_account_info") >= 0)
    {
        SendEnhancedAccountInfo();
    }
    else if(StringFind(jsonResponse, "get_positions") >= 0)
    {
        SendOpenPositions();
    }
}

//+------------------------------------------------------------------+
//| Execute open trade command                                       |
//+------------------------------------------------------------------+
void ExecuteOpenTrade(string jsonCommand)
{
    // Parse command
    string symbol = ExtractJsonValue(jsonCommand, "symbol");
    string orderType = ExtractJsonValue(jsonCommand, "order_type");
    double lots = StringToDouble(ExtractJsonValue(jsonCommand, "lots"));
    double sl = StringToDouble(ExtractJsonValue(jsonCommand, "sl"));
    double tp = StringToDouble(ExtractJsonValue(jsonCommand, "tp"));
    string comment = ExtractJsonValue(jsonCommand, "comment");

    if(ENABLE_LOGGING)
        Print("Opening trade: ", symbol, " ", orderType, " ", lots, " lots");

    // Prepare request
    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lots;
    request.type = (orderType == "BUY") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
    request.price = (orderType == "BUY") ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
    request.sl = sl;
    request.tp = tp;
    request.deviation = 10;
    request.magic = 123456;
    request.comment = comment;
    request.type_filling = ORDER_FILLING_IOC;

    // Execute order
    if(OrderSend(request, result))
    {
        if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
        {
            Print("✓ Trade opened successfully. Ticket: ", result.order);
            SendTradeResult(true, result.order, "Trade opened successfully");

            // Refresh trade history after new trade
            GetTradeHistory(g_trade_history, MAX_TRADE_HISTORY);
        }
        else
        {
            Print("✗ Trade failed. Return code: ", result.retcode);
            SendTradeResult(false, 0, "Trade failed: " + IntegerToString(result.retcode));
        }
    }
    else
    {
        Print("✗ OrderSend error: ", GetLastError());
        SendTradeResult(false, 0, "OrderSend error: " + IntegerToString(GetLastError()));
    }
}

//+------------------------------------------------------------------+
//| Execute close trade command                                      |
//+------------------------------------------------------------------+
void ExecuteCloseTrade(string jsonCommand)
{
    ulong ticket = StringToInteger(ExtractJsonValue(jsonCommand, "ticket"));

    if(ENABLE_LOGGING)
        Print("Closing trade: Ticket #", ticket);

    if(!PositionSelectByTicket(ticket))
    {
        Print("✗ Position not found: ", ticket);
        SendTradeResult(false, 0, "Position not found");
        return;
    }

    MqlTradeRequest request = {};
    MqlTradeResult result = {};

    request.action = TRADE_ACTION_DEAL;
    request.position = ticket;
    request.symbol = PositionGetString(POSITION_SYMBOL);
    request.volume = PositionGetDouble(POSITION_VOLUME);
    request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
    request.price = (request.type == ORDER_TYPE_SELL) ? SymbolInfoDouble(request.symbol, SYMBOL_BID) : SymbolInfoDouble(request.symbol, SYMBOL_ASK);
    request.deviation = 10;
    request.magic = 123456;
    request.type_filling = ORDER_FILLING_IOC;

    if(OrderSend(request, result))
    {
        if(result.retcode == TRADE_RETCODE_DONE)
        {
            Print("✓ Trade closed successfully. Ticket: ", ticket);
            SendTradeResult(true, ticket, "Trade closed successfully");

            // Refresh trade history after closing trade
            GetTradeHistory(g_trade_history, MAX_TRADE_HISTORY);
        }
        else
        {
            Print("✗ Close failed. Return code: ", result.retcode);
            SendTradeResult(false, ticket, "Close failed: " + IntegerToString(result.retcode));
        }
    }
    else
    {
        Print("✗ OrderSend error: ", GetLastError());
        SendTradeResult(false, ticket, "OrderSend error: " + IntegerToString(GetLastError()));
    }
}

//+------------------------------------------------------------------+
//| Send ENHANCED account info with ML/RL Risk data                 |
//+------------------------------------------------------------------+
void SendEnhancedAccountInfo()
{
    // Basic account info
    string json = "{";
    json += "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
    json += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
    json += "\"margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
    json += "\"free_margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
    json += "\"margin_level\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
    json += "\"profit\":" + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
    json += "\"currency\":\"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",";

    // Daily tracking data
    json += "\"daily_pnl\":" + DoubleToString(GetDailyPnL(), 2) + ",";
    json += "\"daily_pnl_percent\":" + DoubleToString(GetDailyPnLPercent(), 2) + ",";
    json += "\"daily_limit_reached\":" + (IsDailyLossLimitReached() ? "true" : "false") + ",";

    // Drawdown tracking data
    json += "\"current_drawdown\":" + DoubleToString(GetCurrentDrawdown(), 2) + ",";
    json += "\"current_drawdown_percent\":" + DoubleToString(GetCurrentDrawdownPercent(), 2) + ",";
    json += "\"max_drawdown_percent\":" + DoubleToString(GetMaxDrawdownPercent(), 2) + ",";
    json += "\"drawdown_limit_reached\":" + (IsMaxDrawdownReached() ? "true" : "false") + ",";

    // Open positions count
    json += "\"open_positions\":" + IntegerToString(PositionsTotal()) + ",";

    // Trade history data (critical for ML Risk Manager)
    json += "\"trade_history\":" + TradeHistoryToJSON(g_trade_history, MAX_TRADE_HISTORY);

    json += "}";

    SendToAPI("/api/mt5/account_enhanced", json);

    // Log summary every 10 calls
    static int call_count = 0;
    call_count++;

    if(call_count % 10 == 0 && ENABLE_LOGGING)
    {
        Print("📊 ML/RL Risk Data:");
        Print("   Daily P&L: $", DoubleToString(GetDailyPnL(), 2), " (", DoubleToString(GetDailyPnLPercent(), 2), "%)");
        Print("   Drawdown: $", DoubleToString(GetCurrentDrawdown(), 2), " (", DoubleToString(GetCurrentDrawdownPercent(), 2), "%)");
        Print("   Trade History: ", ArraySize(g_trade_history), " trades");
    }
}

//+------------------------------------------------------------------+
//| Send open positions to API                                       |
//+------------------------------------------------------------------+
void SendOpenPositions()
{
    string json = "{\"positions\": [";

    int total = PositionsTotal();
    for(int i = 0; i < total; i++)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(i > 0) json += ",";

            json += "{";
            json += "\"ticket\":" + IntegerToString(PositionGetInteger(POSITION_TICKET)) + ",";
            json += "\"symbol\":\"" + PositionGetString(POSITION_SYMBOL) + "\",";
            json += "\"type\":\"" + ((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL") + "\",";
            json += "\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
            json += "\"open_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 5) + ",";
            json += "\"current_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), 5) + ",";
            json += "\"sl\":" + DoubleToString(PositionGetDouble(POSITION_SL), 5) + ",";
            json += "\"tp\":" + DoubleToString(PositionGetDouble(POSITION_TP), 5) + ",";
            json += "\"profit\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\"open_time\":\"" + TimeToString(PositionGetInteger(POSITION_TIME)) + "\"";
            json += "}";
        }
    }

    json += "]}";

    SendToAPI("/api/mt5/positions", json);
}

//+------------------------------------------------------------------+
//| Send trade execution result to API                               |
//+------------------------------------------------------------------+
void SendTradeResult(bool success, ulong ticket, string message)
{
    string json = "{";
    json += "\"success\":" + (success ? "true" : "false") + ",";
    json += "\"ticket\":" + IntegerToString(ticket) + ",";
    json += "\"message\":\"" + message + "\"";
    json += "}";

    SendToAPI("/api/mt5/trade_result", json);
}

//+------------------------------------------------------------------+
//| Send data to API via HTTP POST                                   |
//+------------------------------------------------------------------+
void SendToAPI(string endpoint, string jsonData)
{
    string url = API_URL + endpoint;
    string headers = "Content-Type: application/json\r\n";

    char data[];
    char result[];
    string resultHeaders;

    StringToCharArray(jsonData, data, 0, StringLen(jsonData));

    int timeout = 5000;
    int res = WebRequest("POST", url, headers, timeout, data, result, resultHeaders);

    if(res != 200 && ENABLE_LOGGING)
    {
        Print("API POST failed. Code: ", res, " URL: ", endpoint);
    }
}

//+------------------------------------------------------------------+
//| Extract value from JSON string (simple parser)                   |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
    string searchKey = "\"" + key + "\":";
    int pos = StringFind(json, searchKey);

    if(pos == -1)
    {
        searchKey = "\"" + key + "\" :";  // Try with space
        pos = StringFind(json, searchKey);
    }

    if(pos == -1)
        return "";

    pos += StringLen(searchKey);

    // Skip whitespace
    while(pos < StringLen(json) && (StringGetCharacter(json, pos) == ' ' || StringGetCharacter(json, pos) == '\t'))
        pos++;

    // Check if value is a string (starts with quote)
    bool isString = (StringGetCharacter(json, pos) == '"');

    if(isString)
    {
        pos++; // Skip opening quote
        int endPos = StringFind(json, "\"", pos);
        if(endPos == -1)
            return "";
        return StringSubstr(json, pos, endPos - pos);
    }
    else
    {
        // Numeric or boolean value
        int endPos = pos;
        while(endPos < StringLen(json))
        {
            ushort ch = StringGetCharacter(json, endPos);
            if(ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r')
                break;
            endPos++;
        }
        return StringSubstr(json, pos, endPos - pos);
    }
}

//+------------------------------------------------------------------+
