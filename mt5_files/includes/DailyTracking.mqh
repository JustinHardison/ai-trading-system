//+------------------------------------------------------------------+
//|                                              DailyTracking.mqh    |
//|                                   Daily P&L Tracking for FTMO      |
//|                            Tracks daily starting balance and P&L   |
//+------------------------------------------------------------------+

#property copyright "ApproveBot AI Trading System"
#property version   "1.00"

//+------------------------------------------------------------------+
//| Daily tracking variables                                          |
//+------------------------------------------------------------------+
double g_daily_starting_balance = 0;
datetime g_last_day_check = 0;
double g_daily_pnl = 0;
double g_daily_pnl_percent = 0;

//+------------------------------------------------------------------+
//| Initialize daily tracking (call in OnInit)                       |
//+------------------------------------------------------------------+
void InitDailyTracking()
{
   g_daily_starting_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_last_day_check = TimeCurrent();
   g_daily_pnl = 0;
   g_daily_pnl_percent = 0;

   Print("✅ Daily Tracking initialized - Starting balance: $",
         DoubleToString(g_daily_starting_balance, 2));
}

//+------------------------------------------------------------------+
//| Update daily tracking (call in OnTick)                           |
//+------------------------------------------------------------------+
void UpdateDailyTracking()
{
   datetime now = TimeCurrent();
   MqlDateTime dt_now, dt_last;

   TimeToStruct(now, dt_now);
   TimeToStruct(g_last_day_check, dt_last);

   // Check if new day started (00:00 server time)
   if(dt_now.day != dt_last.day || dt_now.mon != dt_last.mon || dt_now.year != dt_last.year)
   {
      // Reset for new day
      g_daily_starting_balance = AccountInfoDouble(ACCOUNT_BALANCE);
      g_last_day_check = now;
      g_daily_pnl = 0;
      g_daily_pnl_percent = 0;

      Print("🌅 NEW TRADING DAY - Starting balance: $",
            DoubleToString(g_daily_starting_balance, 2));
   }

   // Calculate current daily P&L
   double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Daily P&L includes closed + open positions
   g_daily_pnl = current_equity - g_daily_starting_balance;

   // Daily P&L percentage
   if(g_daily_starting_balance > 0)
      g_daily_pnl_percent = (g_daily_pnl / g_daily_starting_balance) * 100.0;
   else
      g_daily_pnl_percent = 0;
}

//+------------------------------------------------------------------+
//| Get daily P&L in dollars                                         |
//+------------------------------------------------------------------+
double GetDailyPnL()
{
   return g_daily_pnl;
}

//+------------------------------------------------------------------+
//| Get daily P&L percentage                                         |
//+------------------------------------------------------------------+
double GetDailyPnLPercent()
{
   return g_daily_pnl_percent;
}

//+------------------------------------------------------------------+
//| Check if FTMO daily loss limit reached                           |
//+------------------------------------------------------------------+
bool IsDailyLossLimitReached(double limit_percent = 5.0)
{
   // FTMO: 5% daily loss limit
   if(g_daily_pnl_percent < -limit_percent)
   {
      Print("🛑 DAILY LOSS LIMIT REACHED: ",
            DoubleToString(g_daily_pnl_percent, 2), "% (limit: -",
            DoubleToString(limit_percent, 1), "%)");
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if approaching daily loss limit                            |
//+------------------------------------------------------------------+
bool IsApproachingDailyLossLimit(double warning_percent = 4.0)
{
   // Warn at 4% loss (before 5% limit)
   if(g_daily_pnl_percent < -warning_percent)
   {
      Print("⚠️ APPROACHING DAILY LOSS LIMIT: ",
            DoubleToString(g_daily_pnl_percent, 2), "% (warning: -",
            DoubleToString(warning_percent, 1), "%)");
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Get daily tracking summary as JSON                               |
//+------------------------------------------------------------------+
string GetDailyTrackingJSON()
{
   string json = "{";
   json += "\"starting_balance\":" + DoubleToString(g_daily_starting_balance, 2) + ",";
   json += "\"daily_pnl\":" + DoubleToString(g_daily_pnl, 2) + ",";
   json += "\"daily_pnl_percent\":" + DoubleToString(g_daily_pnl_percent, 2) + ",";
   json += "\"limit_reached\":" + (IsDailyLossLimitReached() ? "true" : "false") + ",";
   json += "\"approaching_limit\":" + (IsApproachingDailyLossLimit() ? "true" : "false");
   json += "}";

   return json;
}

//+------------------------------------------------------------------+
