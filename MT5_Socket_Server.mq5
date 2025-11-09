//+------------------------------------------------------------------+
//|                                           MT5_Socket_Server.mq5 |
//|                                   Socket Server for AI Trading  |
//|                                   Uses file-based communication |
//+------------------------------------------------------------------+
#property copyright "AI Trading Bot"
#property link      ""
#property version   "1.15"
#property strict

#include <Trade\Trade.mqh>

// File-based communication
string command_file = "ai_command.txt";
string response_file = "ai_response.txt";
int check_interval_ms = 100; // Check every 100ms
datetime last_check_time = 0;
int last_tick_count = 0;

CTrade trade;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("========================================");
   Print("MT5 Socket Server v1.15 Starting...");
   Print("========================================");
   Print("Command file: ", command_file);
   Print("Response file: ", response_file);
   Print("");
   Print("FILES LOCATION:");
   Print(TerminalInfoString(TERMINAL_COMMONDATA_PATH));
   Print("");
   Print("Put Python files in:");
   Print(TerminalInfoString(TERMINAL_COMMONDATA_PATH), "\\Files\\");
   Print("");
   Print("Ready for Python connection!");
   Print("========================================");

   // Clean up any old files (using FILE_COMMON)
   FileDelete(command_file, FILE_COMMON);
   FileDelete(response_file, FILE_COMMON);

   // Set up timer to check for commands every second
   EventSetTimer(1);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("MT5 Server stopped");
   FileDelete(command_file, FILE_COMMON);
   FileDelete(response_file, FILE_COMMON);
}

//+------------------------------------------------------------------+
//| Expert tick function                                               |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check for commands on every tick
   last_tick_count++;

   if(last_tick_count >= 10)  // Check every 10 ticks
   {
      last_tick_count = 0;
      CheckForCommand();
   }
}

//+------------------------------------------------------------------+
//| Timer function - check for commands periodically                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckForCommand();
}

//+------------------------------------------------------------------+
//| Check for incoming command                                        |
//+------------------------------------------------------------------+
void CheckForCommand()
{
   static int check_count = 0;
   check_count++;

   // Log every 10th check to prove we're running
   if(check_count % 10 == 0)
   {
      Print("CheckForCommand called (", check_count, " times)");
   }

   // Check if command file exists (use FILE_COMMON to access system-wide files)
   // Use FILE_ANSI to read as binary, not TXT which stops at delimiters
   int file_handle = FileOpen(command_file, FILE_READ|FILE_ANSI|FILE_COMMON);

   if(file_handle != INVALID_HANDLE)
   {
      Print("Command file found! Reading...");

      // Read entire file content as one string
      // FileReadString with size parameter reads exact number of characters
      string command = "";

      while(!FileIsEnding(file_handle))
      {
         // Read one character at a time to get the whole file
         command += FileReadString(file_handle, 1);
      }

      FileClose(file_handle);

      // Delete command file FIRST (must use FILE_COMMON)
      FileDelete(command_file, FILE_COMMON);

      if(StringLen(command) > 0)
      {
         Print("Received command: ", command);

         // Process command
         string response = ProcessCommand(command);

         // Delete old response file if it exists (cleanup from previous command)
         FileDelete(response_file, FILE_COMMON);

         // Small delay to ensure delete completes
         Sleep(50);

         // Write NEW response
         int response_handle = FileOpen(response_file, FILE_WRITE|FILE_TXT|FILE_COMMON);
         if(response_handle != INVALID_HANDLE)
         {
            FileWriteString(response_handle, response);
            FileClose(response_handle);
            Print("Sent response: ", response);

            // DON'T delete response file - let Python read it
            // Python will delete it when done
         }
         else
         {
            Print("ERROR: Could not open response file for writing!");
         }
      }
   }
   else
   {
      // File doesn't exist yet - this is normal
   }
}

//+------------------------------------------------------------------+
//| Process incoming command                                           |
//+------------------------------------------------------------------+
string ProcessCommand(string command)
{
   string response = "";

   // Debug: log command length and content
   Print("Processing command, length: ", StringLen(command));
   Print("Command content: [", command, "]");

   // GET_TICK command
   if(StringFind(command, "get_tick") >= 0)
   {
      string symbol = ExtractSymbol(command);
      if(symbol == "") symbol = Symbol();

      MqlTick tick;
      if(SymbolInfoTick(symbol, tick))
      {
         response = StringFormat(
            "{\"success\":true,\"symbol\":\"%s\",\"bid\":%.5f,\"ask\":%.5f,\"time\":%d}",
            symbol, tick.bid, tick.ask, (int)tick.time
         );
      }
      else
      {
         response = "{\"success\":false,\"error\":\"Failed to get tick\"}";
      }
   }

   // GET_ACCOUNT_INFO command (Python sends uppercase)
   else if(StringFind(command, "GET_ACCOUNT_INFO") >= 0 || StringFind(command, "get_account") >= 0)
   {
      // Get MT5 broker server time
      MqlDateTime mt5_time;
      TimeCurrent(mt5_time);

      response = StringFormat(
         "{\"action\":\"GET_ACCOUNT_INFO\",\"status\":\"success\",\"account_info\":{\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"free_margin\":%.2f,\"profit\":%.2f,\"leverage\":%d,\"broker_time\":\"%04d-%02d-%02d %02d:%02d:%02d\",\"broker_weekday\":%d,\"broker_hour\":%d}}",
         AccountInfoDouble(ACCOUNT_BALANCE),
         AccountInfoDouble(ACCOUNT_EQUITY),
         AccountInfoDouble(ACCOUNT_MARGIN),
         AccountInfoDouble(ACCOUNT_MARGIN_FREE),
         AccountInfoDouble(ACCOUNT_PROFIT),
         (int)AccountInfoInteger(ACCOUNT_LEVERAGE),
         mt5_time.year, mt5_time.mon, mt5_time.day, mt5_time.hour, mt5_time.min, mt5_time.sec,
         mt5_time.day_of_week,  // 0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday
         mt5_time.hour
      );
   }

   // GET_POSITIONS command (Python sends uppercase)
   else if(StringFind(command, "GET_POSITIONS") >= 0 || StringFind(command, "get_positions") >= 0)
   {
      int total = PositionsTotal();
      string positions = "[";

      for(int i = 0; i < total; i++)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0)
         {
            if(i > 0) positions += ",";

            positions += StringFormat(
               "{\"ticket\":%I64u,\"symbol\":\"%s\",\"type\":\"%s\",\"volume\":%.2f,\"open_price\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"profit\":%.2f}",
               ticket,
               PositionGetString(POSITION_SYMBOL),
               PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "buy" : "sell",
               PositionGetDouble(POSITION_VOLUME),
               PositionGetDouble(POSITION_PRICE_OPEN),
               PositionGetDouble(POSITION_SL),
               PositionGetDouble(POSITION_TP),
               PositionGetDouble(POSITION_PROFIT)
            );
         }
      }

      positions += "]";
      response = StringFormat("{\"action\":\"GET_POSITIONS\",\"status\":\"success\",\"positions\":%s}", positions);
   }

   // OPEN_TRADE command (Python sends uppercase)
   else if(StringFind(command, "OPEN_TRADE") >= 0 || StringFind(command, "open_trade") >= 0)
   {
      string symbol = ExtractSymbol(command);
      string type_str = ExtractValue(command, "type");
      double volume = StringToDouble(ExtractValue(command, "volume"));
      double sl = StringToDouble(ExtractValue(command, "sl"));
      double tp = StringToDouble(ExtractValue(command, "tp"));

      ENUM_ORDER_TYPE order_type = (type_str == "buy") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;

      if(trade.PositionOpen(symbol, order_type, volume, 0, sl, tp, "AI Bot"))
      {
         ulong ticket = trade.ResultOrder();
         double price = trade.ResultPrice();

         response = StringFormat(
            "{\"success\":true,\"ticket\":%I64u,\"price\":%.5f}",
            ticket, price
         );
      }
      else
      {
         response = StringFormat(
            "{\"success\":false,\"error\":\"Order failed: %d\"}",
            GetLastError()
         );
      }
   }

   // CLOSE_TRADE command (Python sends uppercase)
   else if(StringFind(command, "CLOSE_TRADE") >= 0 || StringFind(command, "close_trade") >= 0)
   {
      ulong ticket = (ulong)StringToInteger(ExtractValue(command, "ticket"));

      if(trade.PositionClose(ticket))
      {
         response = "{\"success\":true,\"message\":\"Position closed\"}";
      }
      else
      {
         response = StringFormat(
            "{\"success\":false,\"error\":\"Close failed: %d\"}",
            GetLastError()
         );
      }
   }

   // GET_SYMBOLS command - Get all available trading symbols (Python sends uppercase)
   else if(StringFind(command, "GET_SYMBOLS") >= 0 || StringFind(command, "get_symbols") >= 0)
   {
      string symbols = "[";
      int total = SymbolsTotal(true);  // true = only symbols in Market Watch

      for(int i = 0; i < total; i++)
      {
         string symbol = SymbolName(i, true);
         if(i > 0) symbols += ",";
         symbols += "\"" + symbol + "\"";
      }

      symbols += "]";
      response = StringFormat("{\"success\":true,\"symbols\":%s,\"count\":%d}", symbols, total);
   }

   // GET_BARS / GET_RATES command - Get historical price data (Python sends uppercase)
   else if(StringFind(command, "GET_BARS") >= 0 || StringFind(command, "get_bars") >= 0 || StringFind(command, "GET_RATES") >= 0 || StringFind(command, "get_rates") >= 0)
   {
      string symbol = ExtractSymbol(command);
      string timeframe_str = ExtractValue(command, "timeframe");
      int count = (int)StringToInteger(ExtractValue(command, "count"));

      if(count <= 0) count = 100;
      if(count > 100) count = 100;  // Limit to 100 bars max for JSON size

      // Convert timeframe string to ENUM
      ENUM_TIMEFRAMES timeframe = PERIOD_H1;  // Default
      if(timeframe_str == "M1") timeframe = PERIOD_M1;
      else if(timeframe_str == "M5") timeframe = PERIOD_M5;
      else if(timeframe_str == "M15") timeframe = PERIOD_M15;
      else if(timeframe_str == "M30") timeframe = PERIOD_M30;
      else if(timeframe_str == "H1") timeframe = PERIOD_H1;
      else if(timeframe_str == "H4") timeframe = PERIOD_H4;
      else if(timeframe_str == "D1") timeframe = PERIOD_D1;

      MqlRates rates[];
      int copied = CopyRates(symbol, timeframe, 0, count, rates);

      if(copied > 0)
      {
         // Build JSON response with proper formatting
         response = StringFormat("{\"success\":true,\"symbol\":\"%s\",\"count\":%d,\"bars\":[", symbol, copied);

         for(int i = 0; i < copied; i++)
         {
            if(i > 0) response += ",";

            // Add each bar as a simple object
            string bar = StringFormat(
               "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%d}",
               (int)rates[i].time,
               rates[i].open,
               rates[i].high,
               rates[i].low,
               rates[i].close,
               (int)rates[i].tick_volume
            );
            response += bar;
         }

         response += "]}";
      }
      else
      {
         response = "{\"success\":false,\"error\":\"Failed to get rates for " + symbol + "\"}";
      }
   }

   // Unknown command
   else
   {
      response = "{\"success\":false,\"error\":\"Unknown command\"}";
   }

   return response;
}

//+------------------------------------------------------------------+
//| Extract symbol from JSON command                                   |
//+------------------------------------------------------------------+
string ExtractSymbol(string command)
{
   return ExtractValue(command, "symbol");
}

//+------------------------------------------------------------------+
//| Extract value from JSON (simple parsing)                          |
//+------------------------------------------------------------------+
string ExtractValue(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int start = StringFind(json, search);
   if(start < 0)
   {
      // Try without quotes (for numbers)
      search = "\"" + key + "\":";
      start = StringFind(json, search);
      if(start < 0) return "";
      start += StringLen(search);
      int end = StringFind(json, ",", start);
      if(end < 0) end = StringFind(json, "}", start);
      if(end < 0) return "";
      return StringSubstr(json, start, end - start);
   }

   start += StringLen(search);
   int end = StringFind(json, "\"", start);
   if(end < 0) return "";

   return StringSubstr(json, start, end - start);
}
//+------------------------------------------------------------------+
