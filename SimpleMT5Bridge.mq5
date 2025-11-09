//+------------------------------------------------------------------+
//|                                              SimpleMT5Bridge.mq5 |
//|                                   Simple File Bridge for Python  |
//+------------------------------------------------------------------+
#property copyright "AI Trading"
#property version   "2.00"
#property strict

#include <Trade\Trade.mqh>

// File paths - MUST match Python exactly
string COMMAND_FILE = "ai_command.txt";
string RESPONSE_FILE = "ai_response.txt";

CTrade trade;
int check_count = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   Print("==============================================");
   Print("SimpleMT5Bridge v2.0 Starting");
   Print("==============================================");
   Print("Files location: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH));
   Print("Command file: ", COMMAND_FILE);
   Print("Response file: ", RESPONSE_FILE);
   Print("==============================================");

   // Clean up old files
   FileDelete(COMMAND_FILE, FILE_COMMON);
   FileDelete(RESPONSE_FILE, FILE_COMMON);

   // Check every second
   EventSetTimer(1);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   FileDelete(COMMAND_FILE, FILE_COMMON);
   FileDelete(RESPONSE_FILE, FILE_COMMON);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   CheckForCommand();
}

//+------------------------------------------------------------------+
void OnTick()
{
   check_count++;
   if(check_count >= 10) {
      check_count = 0;
      CheckForCommand();
   }
}

//+------------------------------------------------------------------+
void CheckForCommand()
{
   // Try to open command file
   int file = FileOpen(COMMAND_FILE, FILE_READ|FILE_TXT|FILE_COMMON);

   if(file == INVALID_HANDLE) {
      // No command file - this is normal
      return;
   }

   // Read command
   string command = "";
   while(!FileIsEnding(file)) {
      command += FileReadString(file);
   }
   FileClose(file);

   // Delete command file immediately
   FileDelete(COMMAND_FILE, FILE_COMMON);

   if(StringLen(command) == 0) {
      return;
   }

   Print("Received command: ", command);

   // Process command and get response
   string response = ProcessCommand(command);

   // Write response
   int resp_file = FileOpen(RESPONSE_FILE, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(resp_file != INVALID_HANDLE) {
      FileWriteString(resp_file, response);
      FileClose(resp_file);
      Print("Sent response: ", StringSubstr(response, 0, 100), "...");
   }
}

//+------------------------------------------------------------------+
string ProcessCommand(string cmd)
{
   // Parse JSON manually (simple parsing)
   string response = "";

   // GET_ACCOUNT_INFO
   if(StringFind(cmd, "GET_ACCOUNT_INFO") >= 0 || StringFind(cmd, "get_account") >= 0) {
      response = StringFormat(
         "{\"success\":true,\"balance\":%.2f,\"equity\":%.2f,\"margin\":%.2f,\"margin_free\":%.2f,\"profit\":%.2f,\"login\":%d}",
         AccountInfoDouble(ACCOUNT_BALANCE),
         AccountInfoDouble(ACCOUNT_EQUITY),
         AccountInfoDouble(ACCOUNT_MARGIN),
         AccountInfoDouble(ACCOUNT_MARGIN_FREE),
         AccountInfoDouble(ACCOUNT_PROFIT),
         (int)AccountInfoInteger(ACCOUNT_LOGIN)
      );
   }

   // GET_BARS
   else if(StringFind(cmd, "GET_BARS") >= 0) {
      string symbol = ExtractValue(cmd, "symbol");
      string tf_str = ExtractValue(cmd, "timeframe");
      int count = (int)StringToInteger(ExtractValue(cmd, "count"));

      ENUM_TIMEFRAMES timeframe = StringToTimeframe(tf_str);

      MqlRates rates[];
      int copied = CopyRates(symbol, timeframe, 0, count, rates);

      if(copied > 0) {
         response = "{\"success\":true,\"symbol\":\"" + symbol + "\",\"count\":" + IntegerToString(copied) + ",\"bars\":[";

         for(int i = 0; i < copied; i++) {
            if(i > 0) response += ",";
            response += StringFormat(
               "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"volume\":%d}",
               (int)rates[i].time,
               rates[i].open,
               rates[i].high,
               rates[i].low,
               rates[i].close,
               (int)rates[i].tick_volume
            );
         }

         response += "]}";
      } else {
         response = "{\"success\":false,\"error\":\"Failed to copy rates\"}";
      }
   }

   // GET_POSITIONS
   else if(StringFind(cmd, "GET_POSITIONS") >= 0) {
      int total = PositionsTotal();
      response = "{\"success\":true,\"positions\":[";

      for(int i = 0; i < total; i++) {
         if(PositionSelectByTicket(PositionGetTicket(i))) {
            if(i > 0) response += ",";
            response += StringFormat(
               "{\"ticket\":%d,\"symbol\":\"%s\",\"type\":%d,\"volume\":%.2f,\"price_open\":%.5f,\"sl\":%.5f,\"tp\":%.5f,\"profit\":%.2f}",
               PositionGetInteger(POSITION_TICKET),
               PositionGetString(POSITION_SYMBOL),
               PositionGetInteger(POSITION_TYPE),
               PositionGetDouble(POSITION_VOLUME),
               PositionGetDouble(POSITION_PRICE_OPEN),
               PositionGetDouble(POSITION_SL),
               PositionGetDouble(POSITION_TP),
               PositionGetDouble(POSITION_PROFIT)
            );
         }
      }

      response += "]}";
   }

   // OPEN_POSITION
   else if(StringFind(cmd, "OPEN_POSITION") >= 0) {
      string symbol = ExtractValue(cmd, "symbol");
      string direction = ExtractValue(cmd, "direction");
      double volume = StringToDouble(ExtractValue(cmd, "volume"));
      double sl = StringToDouble(ExtractValue(cmd, "sl"));
      double tp = StringToDouble(ExtractValue(cmd, "tp"));

      bool result = false;
      if(direction == "BUY") {
         result = trade.Buy(volume, symbol, 0, sl, tp);
      } else {
         result = trade.Sell(volume, symbol, 0, sl, tp);
      }

      if(result) {
         response = StringFormat("{\"success\":true,\"ticket\":%d}", trade.ResultOrder());
      } else {
         response = StringFormat("{\"success\":false,\"error\":\"Trade failed: %d\"}", trade.ResultRetcode());
      }
   }

   else {
      response = "{\"success\":false,\"error\":\"Unknown command\"}";
   }

   return response;
}

//+------------------------------------------------------------------+
string ExtractValue(string json, string key)
{
   int start = StringFind(json, "\"" + key + "\"");
   if(start < 0) return "";

   start = StringFind(json, ":", start) + 1;
   int end_comma = StringFind(json, ",", start);
   int end_brace = StringFind(json, "}", start);

   int end = (end_comma > 0 && end_comma < end_brace) ? end_comma : end_brace;
   if(end < 0) end = StringLen(json);

   string value = StringSubstr(json, start, end - start);
   StringReplace(value, "\"", "");
   StringTrimLeft(value);
   StringTrimRight(value);

   return value;
}

//+------------------------------------------------------------------+
ENUM_TIMEFRAMES StringToTimeframe(string tf)
{
   if(tf == "M1") return PERIOD_M1;
   if(tf == "M5") return PERIOD_M5;
   if(tf == "M15") return PERIOD_M15;
   if(tf == "M30") return PERIOD_M30;
   if(tf == "H1") return PERIOD_H1;
   if(tf == "H4") return PERIOD_H4;
   if(tf == "D1") return PERIOD_D1;
   return PERIOD_H1;
}
