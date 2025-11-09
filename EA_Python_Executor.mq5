//+------------------------------------------------------------------+
//| EA_Python_Executor.mq5                                           |
//| Pure Executor - Zero Logic, Maximum Data Collection              |
//| Python API makes ALL decisions, EA just executes                 |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property version   "4.00"
#property description "Dumb executor - Smart data collector"
#property strict

//+------------------------------------------------------------------+
//| INPUTS - ONLY Configuration, NO Trading Logic                    |
//+------------------------------------------------------------------+
input string API_URL = "http://127.0.0.1:5007/api/ultimate/ml_entry";
input string SYMBOL = "US30Z25.sim";
input bool CHECK_EVERY_TICK = true;     // Check Python on EVERY tick (ultra responsive)
input int CHECK_INTERVAL_SECONDS = 10;  // Fallback: if CHECK_EVERY_TICK=false, check every X seconds
input int BARS_TO_SEND = 100;           // Bars of each timeframe to send
input bool ENABLE_LOGGING = true;
input int MAGIC_NUMBER = 234000;

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES                                                 |
//+------------------------------------------------------------------+
datetime g_last_check = 0;
int g_request_count = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("═══════════════════════════════════════════════════════════════");
   Print("  EA PYTHON EXECUTOR v4.0 - Pure Data Collector");
   Print("═══════════════════════════════════════════════════════════════");
   Print("Symbol: ", SYMBOL);
   Print("API URL: ", API_URL);

   if(CHECK_EVERY_TICK)
   {
      Print("⚡ Mode: EVERY TICK (Maximum Responsiveness)");
      Print("   Python API consulted on EVERY price update");
   }
   else
   {
      Print("⏱️  Mode: Interval-Based (", CHECK_INTERVAL_SECONDS, " seconds)");
   }

   Print("Bars to Send: ", BARS_TO_SEND, " per timeframe");
   Print("");
   Print("📊 This EA has ZERO trading logic");
   Print("🧠 Python API makes ALL decisions");
   Print("⚙️  EA only executes what Python commands");
   Print("═══════════════════════════════════════════════════════════════");

   // Note: WebRequest availability checked during first connection attempt
   // If WebRequest is not enabled, TestAPIConnection() will fail and warn user

   // Test connection
   if(TestAPIConnection())
   {
      Print("✅ API connection successful");
   }
   else
   {
      Print("⚠️  WARNING: Cannot connect to Python API");
      Print("Make sure ml_api_integrated.py is running on port 5007");
   }

   Print("═══════════════════════════════════════════════════════════════");
   Print("✅ EA Ready - Waiting for Python's commands");
   Print("═══════════════════════════════════════════════════════════════\n");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // EVERY TICK MODE: Check Python on every price update
   if(CHECK_EVERY_TICK)
   {
      g_request_count++;
      CollectDataAndAskPython();
   }
   else
   {
      // INTERVAL MODE: Check at regular time intervals
      datetime current_time = TimeCurrent();

      if(current_time - g_last_check >= CHECK_INTERVAL_SECONDS)
      {
         g_last_check = current_time;
         g_request_count++;
         CollectDataAndAskPython();
      }
   }
}

//+------------------------------------------------------------------+
//| Test API Connection                                              |
//+------------------------------------------------------------------+
bool TestAPIConnection()
{
   string url = StringSubstr(API_URL, 0, StringFind(API_URL, "/api"));
   string headers = "Content-Type: application/json\r\n";
   char data[];
   char result[];
   string result_headers;

   int res = WebRequest("GET", url, headers, 5000, data, result, result_headers);

   return (res == 200);
}

//+------------------------------------------------------------------+
//| Main Function - Collect Everything and Ask Python               |
//+------------------------------------------------------------------+
void CollectDataAndAskPython()
{
   // Smart logging: if every tick, log every 100 ticks; if interval, log every 6 calls
   int log_interval = CHECK_EVERY_TICK ? 100 : 6;

   if(ENABLE_LOGGING && g_request_count % log_interval == 0)
      Print("📡 Sending data to Python API (Request #", g_request_count, ")");

   // Build comprehensive JSON with ALL MT5 data
   string json_request = BuildComprehensiveRequest();

   // Send to Python API
   string response = SendToPythonAPI(json_request);

   if(response == "")
   {
      if(ENABLE_LOGGING)
         Print("⚠️  No response from Python API");
      return;
   }

   // Parse Python's decisions and execute
   ExecutePythonDecisions(response);
}

//+------------------------------------------------------------------+
//| Build Comprehensive Request - ALL MT5 Data                       |
//+------------------------------------------------------------------+
string BuildComprehensiveRequest()
{
   string json = "{";

   // 1. BASIC REQUEST INFO
   json += "\"symbol\":\"" + SYMBOL + "\",";
   json += "\"timeframe\":\"M1\",";
   json += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",";
   json += "\"server_time\":" + IntegerToString(TimeCurrent()) + ",";

   // 2. ACCOUNT INFORMATION (Complete)
   json += "\"account\":{";
   json += "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   json += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   json += "\"margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
   json += "\"free_margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
   json += "\"margin_level\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
   json += "\"profit\":" + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
   json += "\"currency\":\"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",";
   json += "\"leverage\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE));
   json += "},";

   // 3. DAILY TRACKING
   json += "\"daily_pnl\":" + DoubleToString(CalculateDailyPnL(), 2) + ",";
   json += "\"drawdown\":" + DoubleToString(CalculateDrawdown(), 2) + ",";

   // 4. CURRENT POSITIONS (All details)
   json += "\"current_positions\":" + IntegerToString(PositionsTotal()) + ",";
   json += "\"open_positions\":" + CollectOpenPositions() + ",";

   // 5. TRADE HISTORY (Today's closed trades)
   json += "\"trade_history\":" + CollectTradeHistory() + ",";

   // 6. MARKET DATA (Multi-timeframe bars)
   json += "\"market_data\":{";
   json += "\"M1\":" + CollectBars(PERIOD_M1, BARS_TO_SEND) + ",";
   json += "\"M5\":" + CollectBars(PERIOD_M5, BARS_TO_SEND) + ",";
   json += "\"M15\":" + CollectBars(PERIOD_M15, BARS_TO_SEND) + ",";
   json += "\"M30\":" + CollectBars(PERIOD_M30, BARS_TO_SEND) + ",";
   json += "\"H1\":" + CollectBars(PERIOD_H1, BARS_TO_SEND) + ",";
   json += "\"H4\":" + CollectBars(PERIOD_H4, BARS_TO_SEND) + ",";
   json += "\"D1\":" + CollectBars(PERIOD_D1, BARS_TO_SEND);
   json += "},";

   // 7. CURRENT MARKET CONDITIONS
   json += "\"current_tick\":{";
   MqlTick tick;
   if(SymbolInfoTick(SYMBOL, tick))
   {
      json += "\"bid\":" + DoubleToString(tick.bid, 5) + ",";
      json += "\"ask\":" + DoubleToString(tick.ask, 5) + ",";
      json += "\"spread\":" + DoubleToString(tick.ask - tick.bid, 5) + ",";
      json += "\"volume\":" + IntegerToString(tick.volume);
   }
   json += "},";

   // 8. SYMBOL INFO (Broker specifications)
   json += "\"symbol_info\":{";
   json += "\"digits\":" + IntegerToString(SymbolInfoInteger(SYMBOL, SYMBOL_DIGITS)) + ",";
   json += "\"point\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_POINT), 10) + ",";
   json += "\"tick_size\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_TRADE_TICK_SIZE), 5) + ",";
   json += "\"tick_value\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_TRADE_TICK_VALUE), 5) + ",";
   json += "\"contract_size\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_TRADE_CONTRACT_SIZE), 2) + ",";
   json += "\"volume_min\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_VOLUME_MIN), 2) + ",";
   json += "\"volume_max\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_VOLUME_MAX), 2) + ",";
   json += "\"volume_step\":" + DoubleToString(SymbolInfoDouble(SYMBOL, SYMBOL_VOLUME_STEP), 2) + ",";
   json += "\"spread_current\":" + IntegerToString(SymbolInfoInteger(SYMBOL, SYMBOL_SPREAD));
   json += "},";

   // 9. MARKET HOURS
   json += "\"is_market_open\":" + (SymbolInfoInteger(SYMBOL, SYMBOL_TRADE_MODE) == SYMBOL_TRADE_MODE_FULL ? "true" : "false") + ",";

   // 10. EA STATUS
   json += "\"ea_info\":{";
   json += "\"requests_sent\":" + IntegerToString(g_request_count) + ",";
   json += "\"magic_number\":" + IntegerToString(MAGIC_NUMBER);
   json += "}";

   json += "}";

   return json;
}

//+------------------------------------------------------------------+
//| Collect Open Positions (Complete Details)                        |
//+------------------------------------------------------------------+
string CollectOpenPositions()
{
   string json = "[";

   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket))
      {
         if(i > 0) json += ",";

         string pos_symbol = PositionGetString(POSITION_SYMBOL);
         long pos_magic = PositionGetInteger(POSITION_MAGIC);

         // Only include positions from this EA
         if(pos_symbol == SYMBOL && (pos_magic == MAGIC_NUMBER || pos_magic == 0))
         {
            long pos_type = PositionGetInteger(POSITION_TYPE);
            datetime pos_time = (datetime)PositionGetInteger(POSITION_TIME);

            // Calculate bars held
            int bars_held = Bars(SYMBOL, PERIOD_M1, pos_time, TimeCurrent());

            // Calculate profit in points
            double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
            double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
            double point_value = SymbolInfoDouble(SYMBOL, SYMBOL_POINT);

            double profit_points = 0;
            if(pos_type == POSITION_TYPE_BUY)
               profit_points = (current_price - entry_price) / point_value;
            else
               profit_points = (entry_price - current_price) / point_value;

            json += "{";
            json += "\"ticket\":" + IntegerToString(ticket) + ",";
            json += "\"symbol\":\"" + pos_symbol + "\",";
            json += "\"direction\":\"" + (pos_type == POSITION_TYPE_BUY ? "BUY" : "SELL") + "\",";
            json += "\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
            json += "\"entry_price\":" + DoubleToString(entry_price, 5) + ",";
            json += "\"current_price\":" + DoubleToString(current_price, 5) + ",";
            json += "\"profit\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\"profit_points\":" + DoubleToString(profit_points, 1) + ",";
            json += "\"sl\":" + DoubleToString(PositionGetDouble(POSITION_SL), 5) + ",";
            json += "\"tp\":" + DoubleToString(PositionGetDouble(POSITION_TP), 5) + ",";
            json += "\"swap\":" + DoubleToString(PositionGetDouble(POSITION_SWAP), 2) + ",";
            json += "\"commission\":0.0,";  // Commission retrieved from deal history, not position
            json += "\"comment\":\"" + PositionGetString(POSITION_COMMENT) + "\",";
            json += "\"time_open\":\"" + TimeToString(pos_time, TIME_DATE|TIME_SECONDS) + "\",";
            json += "\"bars_held\":" + IntegerToString(bars_held) + ",";
            json += "\"magic\":" + IntegerToString(pos_magic);
            json += "}";
         }
      }
   }

   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Collect Trade History (Today's closed trades)                    |
//+------------------------------------------------------------------+
string CollectTradeHistory()
{
   string json = "[";

   // Get today's start
   datetime today_start = iTime(SYMBOL, PERIOD_D1, 0);

   // Select history for today
   if(HistorySelect(today_start, TimeCurrent()))
   {
      int total_deals = HistoryDealsTotal();
      int count = 0;

      for(int i = 0; i < total_deals; i++)
      {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket > 0)
         {
            // Only include deals from this EA's symbol
            string deal_symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
            long deal_magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);

            if(deal_symbol == SYMBOL && (deal_magic == MAGIC_NUMBER || deal_magic == 0))
            {
               long deal_entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);

               // Only include actual entry/exit (not balance operations)
               if(deal_entry == DEAL_ENTRY_IN || deal_entry == DEAL_ENTRY_OUT)
               {
                  if(count > 0) json += ",";

                  long deal_type = HistoryDealGetInteger(ticket, DEAL_TYPE);
                  datetime deal_time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);

                  json += "{";
                  json += "\"ticket\":" + IntegerToString(ticket) + ",";
                  json += "\"position_id\":" + IntegerToString(HistoryDealGetInteger(ticket, DEAL_POSITION_ID)) + ",";
                  json += "\"time\":" + IntegerToString(deal_time) + ",";
                  json += "\"time_str\":\"" + TimeToString(deal_time, TIME_DATE|TIME_SECONDS) + "\",";
                  json += "\"type\":\"" + (deal_type == DEAL_TYPE_BUY ? "BUY" : deal_type == DEAL_TYPE_SELL ? "SELL" : "OTHER") + "\",";
                  json += "\"entry\":\"" + (deal_entry == DEAL_ENTRY_IN ? "IN" : "OUT") + "\",";
                  json += "\"volume\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_VOLUME), 2) + ",";
                  json += "\"price\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PRICE), 5) + ",";
                  json += "\"profit\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PROFIT), 2) + ",";
                  json += "\"commission\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_COMMISSION), 2) + ",";
                  json += "\"swap\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_SWAP), 2) + ",";
                  json += "\"comment\":\"" + HistoryDealGetString(ticket, DEAL_COMMENT) + "\"";
                  json += "}";

                  count++;
               }
            }
         }
      }
   }

   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Collect Bars for Timeframe                                       |
//+------------------------------------------------------------------+
string CollectBars(ENUM_TIMEFRAMES timeframe, int count)
{
   string json = "{";

   // Arrays for bar data
   double open[], high[], low[], close[];
   long volume[];
   datetime time[];

   // Get bars
   int copied_open = CopyOpen(SYMBOL, timeframe, 0, count, open);
   int copied_high = CopyHigh(SYMBOL, timeframe, 0, count, high);
   int copied_low = CopyLow(SYMBOL, timeframe, 0, count, low);
   int copied_close = CopyClose(SYMBOL, timeframe, 0, count, close);
   int copied_volume = CopyTickVolume(SYMBOL, timeframe, 0, count, volume);
   int copied_time = CopyTime(SYMBOL, timeframe, 0, count, time);

   if(copied_open > 0)
   {
      // Build JSON arrays
      json += "\"timestamp\":[";
      for(int i = 0; i < copied_time; i++)
      {
         if(i > 0) json += ",";
         json += "\"" + TimeToString(time[i], TIME_DATE|TIME_SECONDS) + "\"";
      }
      json += "],";

      json += "\"open\":[";
      for(int i = 0; i < copied_open; i++)
      {
         if(i > 0) json += ",";
         json += DoubleToString(open[i], 5);
      }
      json += "],";

      json += "\"high\":[";
      for(int i = 0; i < copied_high; i++)
      {
         if(i > 0) json += ",";
         json += DoubleToString(high[i], 5);
      }
      json += "],";

      json += "\"low\":[";
      for(int i = 0; i < copied_low; i++)
      {
         if(i > 0) json += ",";
         json += DoubleToString(low[i], 5);
      }
      json += "],";

      json += "\"close\":[";
      for(int i = 0; i < copied_close; i++)
      {
         if(i > 0) json += ",";
         json += DoubleToString(close[i], 5);
      }
      json += "],";

      json += "\"volume\":[";
      for(int i = 0; i < copied_volume; i++)
      {
         if(i > 0) json += ",";
         json += IntegerToString(volume[i]);
      }
      json += "]";
   }

   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| Calculate Daily P&L                                              |
//+------------------------------------------------------------------+
double CalculateDailyPnL()
{
   double daily_pnl = 0.0;
   datetime today_start = iTime(SYMBOL, PERIOD_D1, 0);

   if(HistorySelect(today_start, TimeCurrent()))
   {
      int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         ulong ticket = HistoryDealGetTicket(i);
         if(ticket > 0)
         {
            string deal_symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
            if(deal_symbol == SYMBOL)
            {
               daily_pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT);
               daily_pnl += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
               daily_pnl += HistoryDealGetDouble(ticket, DEAL_SWAP);
            }
         }
      }
   }

   return daily_pnl;
}

//+------------------------------------------------------------------+
//| Calculate Drawdown                                               |
//+------------------------------------------------------------------+
double CalculateDrawdown()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   return balance - equity;
}

//+------------------------------------------------------------------+
//| Send Request to Python API                                       |
//+------------------------------------------------------------------+
string SendToPythonAPI(string json_data)
{
   char data[];
   char result[];
   string result_headers;
   string headers = "Content-Type: application/json\r\n";

   // Convert string to char array
   StringToCharArray(json_data, data, 0, StringLen(json_data));

   // Send POST request
   int timeout = 10000;  // 10 seconds
   int res = WebRequest("POST", API_URL, headers, timeout, data, result, result_headers);

   if(res == 200)
   {
      // Success - convert response
      return CharArrayToString(result);
   }
   else if(res == -1)
   {
      int error = GetLastError();
      if(ENABLE_LOGGING && g_request_count % 60 == 0)  // Log error every 10 minutes
         Print("⚠️  WebRequest error: ", error);
      return "";
   }
   else
   {
      if(ENABLE_LOGGING)
         Print("⚠️  API returned code: ", res);
      return "";
   }
}

//+------------------------------------------------------------------+
//| Execute Python's Decisions - ONLY Function That Takes Action     |
//+------------------------------------------------------------------+
void ExecutePythonDecisions(string json_response)
{
   // Parse Python's response
   string direction = ExtractJSONValue(json_response, "direction");
   bool take_trade = (ExtractJSONValue(json_response, "take_trade") == "true");
   double lots = StringToDouble(ExtractJSONValue(json_response, "lots"));
   double confidence = StringToDouble(ExtractJSONValue(json_response, "confidence"));
   int stop_points = (int)StringToInteger(ExtractJSONValue(json_response, "stop_points"));
   int target_points = (int)StringToInteger(ExtractJSONValue(json_response, "target_points"));

   // Log Python's decision (less frequent in tick mode)
   int log_interval = CHECK_EVERY_TICK ? 100 : 6;

   if(ENABLE_LOGGING && g_request_count % log_interval == 0)
   {
      Print("🧠 Python Decision: ", direction, " @ ", DoubleToString(confidence, 1), "% conf");
      if(take_trade)
         Print("   ✅ ENTRY: ", lots, " lots | SL:", stop_points, " pts | TP:", target_points, " pts");
      else
         Print("   ⏸️  HOLD: Conditions not met");
   }

   // ALWAYS log actual trades (regardless of mode)
   bool should_log_trade = (take_trade && (direction == "BUY" || direction == "SELL") && lots > 0);

   // ENTRY LOGIC - Execute if Python says so
   if(take_trade && (direction == "BUY" || direction == "SELL") && lots > 0)
   {
      ExecuteEntry(direction, lots, stop_points, target_points);
   }

   // EXIT LOGIC - Check each open position
   int total_positions = PositionsTotal();
   for(int i = total_positions - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionSelectByTicket(ticket))
      {
         string pos_symbol = PositionGetString(POSITION_SYMBOL);
         long pos_magic = PositionGetInteger(POSITION_MAGIC);

         if(pos_symbol == SYMBOL && (pos_magic == MAGIC_NUMBER || pos_magic == 0))
         {
            // Look for exit decision for this ticket in Python's response
            string exit_action = ExtractJSONValue(json_response, "exit_action");

            if(exit_action == "CLOSE_ALL")
            {
               ExecuteClose(ticket, 1.0);  // Close 100%
            }
            else if(exit_action == "SCALE_OUT_50")
            {
               ExecuteClose(ticket, 0.5);  // Close 50%
            }
            else if(exit_action == "SCALE_OUT_25")
            {
               ExecuteClose(ticket, 0.25);  // Close 25%
            }
            // "HOLD" or empty = do nothing
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Execute Entry Order                                              |
//+------------------------------------------------------------------+
void ExecuteEntry(string direction, double lots, int stop_points, int target_points)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   // Get current prices
   MqlTick tick;
   if(!SymbolInfoTick(SYMBOL, tick))
   {
      Print("❌ Failed to get tick data");
      return;
   }

   // Calculate SL/TP prices
   double point = SymbolInfoDouble(SYMBOL, SYMBOL_POINT);
   double sl_price = 0, tp_price = 0;

   if(direction == "BUY")
   {
      request.type = ORDER_TYPE_BUY;
      request.price = tick.ask;
      if(stop_points > 0)
         sl_price = tick.ask - stop_points * point;
      if(target_points > 0)
         tp_price = tick.ask + target_points * point;
   }
   else  // SELL
   {
      request.type = ORDER_TYPE_SELL;
      request.price = tick.bid;
      if(stop_points > 0)
         sl_price = tick.bid + stop_points * point;
      if(target_points > 0)
         tp_price = tick.bid - target_points * point;
   }

   // Prepare request
   request.action = TRADE_ACTION_DEAL;
   request.symbol = SYMBOL;
   request.volume = lots;
   request.sl = sl_price;
   request.tp = tp_price;
   request.deviation = 20;
   request.magic = MAGIC_NUMBER;
   request.comment = "Python AI";
   request.type_filling = ORDER_FILLING_IOC;

   // Execute
   if(OrderSend(request, result))
   {
      if(result.retcode == TRADE_RETCODE_DONE)
      {
         Print("✅ ENTRY EXECUTED: ", direction, " ", lots, " lots @ ", request.price);
         Print("   Ticket: ", result.order, " | SL: ", sl_price, " | TP: ", tp_price);
      }
      else
      {
         Print("❌ Entry failed: ", result.retcode, " - ", result.comment);
      }
   }
   else
   {
      Print("❌ OrderSend error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Execute Close/Scale Order                                        |
//+------------------------------------------------------------------+
void ExecuteClose(ulong ticket, double fraction)
{
   if(!PositionSelectByTicket(ticket))
   {
      Print("❌ Position not found: ", ticket);
      return;
   }

   MqlTradeRequest request = {};
   MqlTradeResult result = {};

   string symbol = PositionGetString(POSITION_SYMBOL);
   long pos_type = PositionGetInteger(POSITION_TYPE);
   double volume = PositionGetDouble(POSITION_VOLUME);
   double close_volume = NormalizeDouble(volume * fraction, 2);

   // Get current price
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
      return;

   // Prepare request
   request.action = TRADE_ACTION_DEAL;
   request.position = ticket;
   request.symbol = symbol;
   request.volume = close_volume;
   request.type = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   request.price = (request.type == ORDER_TYPE_SELL) ? tick.bid : tick.ask;
   request.deviation = 20;
   request.magic = MAGIC_NUMBER;
   request.type_filling = ORDER_FILLING_IOC;

   // Execute
   if(OrderSend(request, result))
   {
      if(result.retcode == TRADE_RETCODE_DONE)
      {
         int pct = (int)(fraction * 100);
         Print("✅ EXIT EXECUTED: Closed ", pct, "% of position ", ticket);
         Print("   Volume: ", close_volume, " lots");
      }
      else
      {
         Print("❌ Exit failed: ", result.retcode, " - ", result.comment);
      }
   }
   else
   {
      Print("❌ OrderSend error: ", GetLastError());
   }
}

//+------------------------------------------------------------------+
//| Simple JSON Value Extractor                                      |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key)
{
   string search_key = "\"" + key + "\":";
   int pos = StringFind(json, search_key);

   if(pos == -1)
      return "";

   pos += StringLen(search_key);

   // Skip whitespace
   while(pos < StringLen(json) && (StringGetCharacter(json, pos) == ' ' || StringGetCharacter(json, pos) == '\t'))
      pos++;

   // Check if value is string (starts with quote)
   bool is_string = (StringGetCharacter(json, pos) == '"');

   if(is_string)
   {
      pos++;  // Skip opening quote
      int end_pos = StringFind(json, "\"", pos);
      if(end_pos == -1)
         return "";
      return StringSubstr(json, pos, end_pos - pos);
   }
   else
   {
      // Numeric or boolean
      int end_pos = pos;
      while(end_pos < StringLen(json))
      {
         ushort ch = StringGetCharacter(json, end_pos);
         if(ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r')
            break;
         end_pos++;
      }
      return StringSubstr(json, pos, end_pos - pos);
   }
}

//+------------------------------------------------------------------+
