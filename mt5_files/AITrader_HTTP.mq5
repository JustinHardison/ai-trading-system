//+------------------------------------------------------------------+
//|                                                AITrader_HTTP.mq5 |
//|                                       AI Trading System v2.0     |
//|                                       HTTP-Based Communication   |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "2.00"
#property strict

// API Configuration
input string API_URL = "http://localhost:8000";  // Backend API URL
input int    CHECK_INTERVAL = 3;                  // Check for commands every 3 seconds
input bool   ENABLE_LOGGING = true;              // Enable detailed logging

// Global variables
datetime lastCheck = 0;
int checkInterval = CHECK_INTERVAL;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("=== AI Trading System HTTP v2.0 Initialized ===");
    Print("API URL: ", API_URL);
    Print("Check Interval: ", checkInterval, " seconds");

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

    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    Print("=== AI Trading System HTTP Deinitialized ===");
    Print("Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
    // Check for commands every X seconds
    datetime currentTime = TimeCurrent();
    if(currentTime - lastCheck >= checkInterval)
    {
        lastCheck = currentTime;
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
        Print("✓ API Connection successful");
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
    // Expected format: {"commands": [{"action": "open_trade", "symbol": "EURUSD", ...}]}

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
        SendAccountInfo();
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
//| Send account info to API                                         |
//+------------------------------------------------------------------+
void SendAccountInfo()
{
    string json = "{";
    json += "\"balance\": " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
    json += "\"equity\": " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
    json += "\"margin\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
    json += "\"free_margin\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
    json += "\"margin_level\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
    json += "\"profit\": " + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
    json += "\"currency\": \"" + AccountInfoString(ACCOUNT_CURRENCY) + "\"";
    json += "}";

    SendToAPI("/api/mt5/account", json);
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
            json += "\"ticket\": " + IntegerToString(PositionGetInteger(POSITION_TICKET)) + ",";
            json += "\"symbol\": \"" + PositionGetString(POSITION_SYMBOL) + "\",";
            json += "\"type\": \"" + ((PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL") + "\",";
            json += "\"volume\": " + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
            json += "\"open_price\": " + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 5) + ",";
            json += "\"current_price\": " + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), 5) + ",";
            json += "\"sl\": " + DoubleToString(PositionGetDouble(POSITION_SL), 5) + ",";
            json += "\"tp\": " + DoubleToString(PositionGetDouble(POSITION_TP), 5) + ",";
            json += "\"profit\": " + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\"open_time\": \"" + TimeToString(PositionGetInteger(POSITION_TIME)) + "\"";
            json += "}";
        }
    }

    json += "]}";

    SendToAPI("/api/mt5/positions", json);
}

//+------------------------------------------------------------------+
//| Send trade result to API                                         |
//+------------------------------------------------------------------+
void SendTradeResult(bool success, ulong ticket, string message)
{
    string json = "{";
    json += "\"success\": " + (success ? "true" : "false") + ",";
    json += "\"ticket\": " + IntegerToString(ticket) + ",";
    json += "\"message\": \"" + message + "\"";
    json += "}";

    SendToAPI("/api/mt5/trade_result", json);
}

//+------------------------------------------------------------------+
//| Send JSON data to API                                            |
//+------------------------------------------------------------------+
void SendToAPI(string endpoint, string jsonData)
{
    string url = API_URL + endpoint;
    string headers = "Content-Type: application/json\r\n";

    char data[];
    StringToCharArray(jsonData, data, 0, StringLen(jsonData));

    char result[];
    string resultHeaders;

    int timeout = 5000;
    int res = WebRequest("POST", url, headers, timeout, data, result, resultHeaders);

    if(res == 200)
    {
        if(ENABLE_LOGGING)
            Print("✓ Data sent to API: ", endpoint);
    }
    else
    {
        Print("✗ Failed to send data. Code: ", res, " Error: ", GetLastError());
    }
}

//+------------------------------------------------------------------+
//| Extract value from simple JSON                                   |
//+------------------------------------------------------------------+
string ExtractJsonValue(string json, string key)
{
    string searchKey = "\"" + key + "\":";
    int start = StringFind(json, searchKey);
    if(start < 0) return "";

    start += StringLen(searchKey);

    // Skip whitespace and quotes
    while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '"'))
        start++;

    int end = start;
    bool inQuotes = false;

    // Find end of value
    while(end < StringLen(json))
    {
        ushort ch = StringGetCharacter(json, end);
        if(ch == '"') inQuotes = !inQuotes;
        if(!inQuotes && (ch == ',' || ch == '}')) break;
        end++;
    }

    string value = StringSubstr(json, start, end - start);
    StringReplace(value, "\"", "");
    StringTrimLeft(value);
    StringTrimRight(value);

    return value;
}
//+------------------------------------------------------------------+
