//+------------------------------------------------------------------+
//|                                        DrawdownTracking.mqh       |
//|                             Max Drawdown Tracking for FTMO        |
//|                          Tracks peak balance and current drawdown |
//+------------------------------------------------------------------+

#property copyright "ApproveBot AI Trading System"
#property version   "1.00"

//+------------------------------------------------------------------+
//| Drawdown tracking variables                                       |
//+------------------------------------------------------------------+
double g_peak_balance = 0;
double g_current_drawdown = 0;
double g_current_drawdown_percent = 0;
double g_max_drawdown = 0;
double g_max_drawdown_percent = 0;

//+------------------------------------------------------------------+
//| Initialize drawdown tracking (call in OnInit)                    |
//+------------------------------------------------------------------+
void InitDrawdownTracking()
{
   g_peak_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   g_current_drawdown = 0;
   g_current_drawdown_percent = 0;
   g_max_drawdown = 0;
   g_max_drawdown_percent = 0;

   Print("✅ Drawdown Tracking initialized - Peak balance: $",
         DoubleToString(g_peak_balance, 2));
}

//+------------------------------------------------------------------+
//| Update drawdown tracking (call in OnTick)                        |
//+------------------------------------------------------------------+
void UpdateDrawdownTracking()
{
   double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Update peak balance if new high
   if(current_equity > g_peak_balance)
   {
      g_peak_balance = current_equity;
      g_current_drawdown = 0;
      g_current_drawdown_percent = 0;

      Print("📈 NEW PEAK BALANCE: $", DoubleToString(g_peak_balance, 2));
   }
   else
   {
      // Calculate current drawdown from peak
      g_current_drawdown = g_peak_balance - current_equity;

      if(g_peak_balance > 0)
         g_current_drawdown_percent = (g_current_drawdown / g_peak_balance) * 100.0;
      else
         g_current_drawdown_percent = 0;

      // Update max drawdown if current is worse
      if(g_current_drawdown > g_max_drawdown)
      {
         g_max_drawdown = g_current_drawdown;
         g_max_drawdown_percent = g_current_drawdown_percent;

         Print("⚠️ NEW MAX DRAWDOWN: $", DoubleToString(g_max_drawdown, 2),
               " (", DoubleToString(g_max_drawdown_percent, 2), "%)");
      }
   }
}

//+------------------------------------------------------------------+
//| Get current drawdown in dollars                                  |
//+------------------------------------------------------------------+
double GetCurrentDrawdown()
{
   return g_current_drawdown;
}

//+------------------------------------------------------------------+
//| Get current drawdown percentage                                  |
//+------------------------------------------------------------------+
double GetCurrentDrawdownPercent()
{
   return g_current_drawdown_percent;
}

//+------------------------------------------------------------------+
//| Get max drawdown percentage                                      |
//+------------------------------------------------------------------+
double GetMaxDrawdownPercent()
{
   return g_max_drawdown_percent;
}

//+------------------------------------------------------------------+
//| Check if FTMO max drawdown limit reached                         |
//+------------------------------------------------------------------+
bool IsMaxDrawdownReached(double limit_percent = 10.0)
{
   // FTMO: 10% max drawdown limit
   if(g_current_drawdown_percent >= limit_percent)
   {
      Print("🛑 MAX DRAWDOWN LIMIT REACHED: ",
            DoubleToString(g_current_drawdown_percent, 2), "% (limit: ",
            DoubleToString(limit_percent, 1), "%)");
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if approaching max drawdown limit                          |
//+------------------------------------------------------------------+
bool IsApproachingMaxDrawdown(double warning_percent = 8.0)
{
   // Warn at 8% drawdown (before 10% limit)
   if(g_current_drawdown_percent >= warning_percent)
   {
      Print("⚠️ APPROACHING MAX DRAWDOWN LIMIT: ",
            DoubleToString(g_current_drawdown_percent, 2), "% (warning: ",
            DoubleToString(warning_percent, 1), "%)");
      return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check if in severe drawdown (>5%)                                |
//+------------------------------------------------------------------+
bool IsInSevereDrawdown(double threshold_percent = 5.0)
{
   return (g_current_drawdown_percent >= threshold_percent);
}

//+------------------------------------------------------------------+
//| Get drawdown tracking summary as JSON                            |
//+------------------------------------------------------------------+
string GetDrawdownTrackingJSON()
{
   string json = "{";
   json += "\"peak_balance\":" + DoubleToString(g_peak_balance, 2) + ",";
   json += "\"current_drawdown\":" + DoubleToString(g_current_drawdown, 2) + ",";
   json += "\"current_drawdown_percent\":" + DoubleToString(g_current_drawdown_percent, 2) + ",";
   json += "\"max_drawdown\":" + DoubleToString(g_max_drawdown, 2) + ",";
   json += "\"max_drawdown_percent\":" + DoubleToString(g_max_drawdown_percent, 2) + ",";
   json += "\"limit_reached\":" + (IsMaxDrawdownReached() ? "true" : "false") + ",";
   json += "\"approaching_limit\":" + (IsApproachingMaxDrawdown() ? "true" : "false") + ",";
   json += "\"severe_drawdown\":" + (IsInSevereDrawdown() ? "true" : "false");
   json += "}";

   return json;
}

//+------------------------------------------------------------------+
