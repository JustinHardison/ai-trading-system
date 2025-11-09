//+------------------------------------------------------------------+
//|                                            GetTradeHistory.mqh    |
//|                                  Trade History Extraction for ML  |
//|                         Extracts last 50-100 trades for analysis  |
//+------------------------------------------------------------------+

#property copyright "ApproveBot AI Trading System"
#property version   "1.00"

//+------------------------------------------------------------------+
//| Structure to hold trade data                                      |
//+------------------------------------------------------------------+
struct TradeData
{
   datetime time_open;
   datetime time_close;
   string   symbol;
   int      type;           // DEAL_TYPE_BUY or DEAL_TYPE_SELL
   double   volume;
   double   price_open;
   double   price_close;
   double   profit;
   double   commission;
   double   swap;
   double   profit_points;
   long     ticket;
   int      duration_bars;
};

//+------------------------------------------------------------------+
//| Get last N closed trades from account history                    |
//+------------------------------------------------------------------+
bool GetTradeHistory(TradeData &trades[], int max_trades = 50)
{
   // Clear array
   ArrayResize(trades, 0);

   // Select history for last 30 days (enough for ML analysis)
   datetime now = TimeCurrent();
   datetime from = now - (30 * 24 * 60 * 60);  // 30 days ago

   if(!HistorySelect(from, now))
   {
      Print("❌ Failed to select history");
      return false;
   }

   int total_deals = HistoryDealsTotal();

   if(total_deals == 0)
   {
      Print("⚠️ No trade history found (new account)");
      return true;  // Not an error, just empty
   }

   // Temporary storage for deals
   struct DealRecord
   {
      long     ticket;
      datetime time;
      string   symbol;
      int      type;
      double   volume;
      double   price;
      double   profit;
      double   commission;
      double   swap;
      long     position_id;
   };

   DealRecord deals[];
   ArrayResize(deals, 0);

   // Extract all deals
   for(int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      // Only process BUY/SELL deals (skip balance operations)
      long deal_type = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(deal_type != DEAL_TYPE_BUY && deal_type != DEAL_TYPE_SELL)
         continue;

      // Only process market exits (not balance operations or transfers)
      long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
         continue;

      // Extract deal data
      int idx = ArraySize(deals);
      ArrayResize(deals, idx + 1);

      deals[idx].ticket = (long)ticket;
      deals[idx].time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
      deals[idx].symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
      deals[idx].type = (int)deal_type;
      deals[idx].volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      deals[idx].price = HistoryDealGetDouble(ticket, DEAL_PRICE);
      deals[idx].profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      deals[idx].commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      deals[idx].swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
      deals[idx].position_id = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
   }

   // Group deals by position_id to reconstruct complete trades
   long position_ids[];
   ArrayResize(position_ids, 0);

   // Get unique position IDs
   for(int i = 0; i < ArraySize(deals); i++)
   {
      long pos_id = deals[i].position_id;
      bool found = false;

      for(int j = 0; j < ArraySize(position_ids); j++)
      {
         if(position_ids[j] == pos_id)
         {
            found = true;
            break;
         }
      }

      if(!found)
      {
         int idx = ArraySize(position_ids);
         ArrayResize(position_ids, idx + 1);
         position_ids[idx] = pos_id;
      }
   }

   // Reconstruct complete trades (entry + exit)
   ArrayResize(trades, 0);

   for(int i = 0; i < ArraySize(position_ids); i++)
   {
      long pos_id = position_ids[i];

      // Find entry and exit deals for this position
      DealRecord entry_deal, exit_deal;
      bool has_entry = false, has_exit = false;

      for(int j = 0; j < ArraySize(deals); j++)
      {
         if(deals[j].position_id == pos_id)
         {
            long entry_type = HistoryDealGetInteger((ulong)deals[j].ticket, DEAL_ENTRY);

            if(entry_type == DEAL_ENTRY_IN)
            {
               entry_deal = deals[j];
               has_entry = true;
            }
            else if(entry_type == DEAL_ENTRY_OUT || entry_type == DEAL_ENTRY_OUT_BY)
            {
               exit_deal = deals[j];
               has_exit = true;
            }
         }
      }

      // Only add complete trades (both entry and exit)
      if(has_entry && has_exit)
      {
         int idx = ArraySize(trades);
         ArrayResize(trades, idx + 1);

         trades[idx].time_open = entry_deal.time;
         trades[idx].time_close = exit_deal.time;
         trades[idx].symbol = entry_deal.symbol;
         trades[idx].type = entry_deal.type;
         trades[idx].volume = entry_deal.volume;
         trades[idx].price_open = entry_deal.price;
         trades[idx].price_close = exit_deal.price;
         trades[idx].profit = exit_deal.profit;
         trades[idx].commission = exit_deal.commission;
         trades[idx].swap = exit_deal.swap;
         trades[idx].ticket = entry_deal.ticket;

         // Calculate profit in points
         double point = SymbolInfoDouble(entry_deal.symbol, SYMBOL_POINT);
         if(point > 0)
         {
            if(entry_deal.type == DEAL_TYPE_BUY)
               trades[idx].profit_points = (exit_deal.price - entry_deal.price) / point;
            else
               trades[idx].profit_points = (entry_deal.price - exit_deal.price) / point;
         }

         // Calculate duration in bars (approximate)
         int duration_seconds = (int)(exit_deal.time - entry_deal.time);
         trades[idx].duration_bars = duration_seconds / 60;  // Assuming M1 timeframe
      }
   }

   // Sort by close time (most recent first)
   for(int i = 0; i < ArraySize(trades) - 1; i++)
   {
      for(int j = i + 1; j < ArraySize(trades); j++)
      {
         if(trades[j].time_close > trades[i].time_close)
         {
            TradeData temp = trades[i];
            trades[i] = trades[j];
            trades[j] = temp;
         }
      }
   }

   // Limit to max_trades
   if(ArraySize(trades) > max_trades)
      ArrayResize(trades, max_trades);

   Print("✅ Extracted ", ArraySize(trades), " complete trades from history");

   return true;
}

//+------------------------------------------------------------------+
//| Calculate win rate from trade history                            |
//+------------------------------------------------------------------+
double CalculateWinRate(TradeData &trades[])
{
   if(ArraySize(trades) == 0)
      return 0.5;  // Neutral if no history

   int wins = 0;
   for(int i = 0; i < ArraySize(trades); i++)
   {
      if(trades[i].profit > 0)
         wins++;
   }

   return (double)wins / ArraySize(trades);
}

//+------------------------------------------------------------------+
//| Calculate current win/loss streak                                |
//+------------------------------------------------------------------+
int CalculateStreak(TradeData &trades[])
{
   if(ArraySize(trades) == 0)
      return 0;

   int streak = 0;

   for(int i = 0; i < ArraySize(trades); i++)
   {
      if(trades[i].profit > 0)
      {
         if(streak >= 0)
            streak++;
         else
            break;
      }
      else if(trades[i].profit < 0)
      {
         if(streak <= 0)
            streak--;
         else
            break;
      }
      else
      {
         break;  // Break even trade
      }
   }

   return streak;
}

//+------------------------------------------------------------------+
//| Calculate profit factor                                          |
//+------------------------------------------------------------------+
double CalculateProfitFactor(TradeData &trades[])
{
   if(ArraySize(trades) == 0)
      return 1.0;

   double gross_profit = 0;
   double gross_loss = 0;

   for(int i = 0; i < ArraySize(trades); i++)
   {
      if(trades[i].profit > 0)
         gross_profit += trades[i].profit;
      else
         gross_loss += MathAbs(trades[i].profit);
   }

   if(gross_loss == 0)
      return 3.0;  // All wins

   return gross_profit / gross_loss;
}

//+------------------------------------------------------------------+
//| Calculate average win and average loss                           |
//+------------------------------------------------------------------+
void CalculateAvgWinLoss(TradeData &trades[], double &avg_win, double &avg_loss)
{
   avg_win = 0;
   avg_loss = 0;

   if(ArraySize(trades) == 0)
      return;

   int win_count = 0;
   int loss_count = 0;
   double total_wins = 0;
   double total_losses = 0;

   for(int i = 0; i < ArraySize(trades); i++)
   {
      if(trades[i].profit > 0)
      {
         total_wins += trades[i].profit;
         win_count++;
      }
      else if(trades[i].profit < 0)
      {
         total_losses += MathAbs(trades[i].profit);
         loss_count++;
      }
   }

   if(win_count > 0)
      avg_win = total_wins / win_count;

   if(loss_count > 0)
      avg_loss = total_losses / loss_count;
}

//+------------------------------------------------------------------+
//| Format trade history as JSON string                              |
//+------------------------------------------------------------------+
string TradeHistoryToJSON(TradeData &trades[], int max_recent = 50)
{
   string json = "[";

   int count = MathMin(ArraySize(trades), max_recent);

   for(int i = 0; i < count; i++)
   {
      if(i > 0) json += ",";

      json += "{";
      json += "\"time_open\":\"" + TimeToString(trades[i].time_open, TIME_DATE|TIME_MINUTES) + "\",";
      json += "\"time_close\":\"" + TimeToString(trades[i].time_close, TIME_DATE|TIME_MINUTES) + "\",";
      json += "\"symbol\":\"" + trades[i].symbol + "\",";
      json += "\"type\":" + IntegerToString(trades[i].type) + ",";
      json += "\"volume\":" + DoubleToString(trades[i].volume, 2) + ",";
      json += "\"price_open\":" + DoubleToString(trades[i].price_open, 5) + ",";
      json += "\"price_close\":" + DoubleToString(trades[i].price_close, 5) + ",";
      json += "\"pnl\":" + DoubleToString(trades[i].profit, 2) + ",";
      json += "\"profit_points\":" + DoubleToString(trades[i].profit_points, 1) + ",";
      json += "\"duration_bars\":" + IntegerToString(trades[i].duration_bars) + ",";
      json += "\"ticket\":" + IntegerToString(trades[i].ticket);
      json += "}";
   }

   json += "]";

   return json;
}

//+------------------------------------------------------------------+
