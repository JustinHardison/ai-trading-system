//+------------------------------------------------------------------+
//| Order Book Data Collection Function                              |
//| Add this to AI_Trading_EA_Ultimate.mq5                           |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Get Order Book (Market Depth) data as JSON                       |
//+------------------------------------------------------------------+
string GetOrderBookData(string symbol, int digits)
{
    MqlBookInfo book[];
    string json = "{";
    
    // Get market depth
    if(MarketBookGet(symbol, book))
    {
        // Count bids and asks
        int bidCount = 0;
        int askCount = 0;
        double totalBidVolume = 0;
        double totalAskVolume = 0;
        
        for(int i = 0; i < ArraySize(book); i++)
        {
            if(book[i].type == BOOK_TYPE_BUY)
            {
                bidCount++;
                totalBidVolume += book[i].volume;
            }
            else if(book[i].type == BOOK_TYPE_SELL)
            {
                askCount++;
                totalAskVolume += book[i].volume;
            }
        }
        
        // Bids array
        json += "\"bids\": [";
        int bidIdx = 0;
        for(int i = 0; i < ArraySize(book) && bidIdx < 10; i++)  // Top 10 levels
        {
            if(book[i].type == BOOK_TYPE_BUY)
            {
                if(bidIdx > 0) json += ",";
                json += "{";
                json += "\"price\": " + DoubleToString(book[i].price, digits) + ",";
                json += "\"volume\": " + IntegerToString(book[i].volume);
                json += "}";
                bidIdx++;
            }
        }
        json += "],";
        
        // Asks array
        json += "\"asks\": [";
        int askIdx = 0;
        for(int i = 0; i < ArraySize(book) && askIdx < 10; i++)  // Top 10 levels
        {
            if(book[i].type == BOOK_TYPE_SELL)
            {
                if(askIdx > 0) json += ",";
                json += "{";
                json += "\"price\": " + DoubleToString(book[i].price, digits) + ",";
                json += "\"volume\": " + IntegerToString(book[i].volume);
                json += "}";
                askIdx++;
            }
        }
        json += "],";
        
        // Summary statistics
        json += "\"summary\": {";
        json += "\"total_bid_volume\": " + IntegerToString((int)totalBidVolume) + ",";
        json += "\"total_ask_volume\": " + IntegerToString((int)totalAskVolume) + ",";
        json += "\"bid_levels\": " + IntegerToString(bidCount) + ",";
        json += "\"ask_levels\": " + IntegerToString(askCount) + ",";
        
        // Order imbalance
        double imbalance = 0;
        if(totalBidVolume + totalAskVolume > 0)
            imbalance = (totalBidVolume - totalAskVolume) / (totalBidVolume + totalAskVolume);
        json += "\"order_imbalance\": " + DoubleToString(imbalance, 4);
        
        json += "}";
    }
    else
    {
        // No market depth available
        json += "\"bids\": [],";
        json += "\"asks\": [],";
        json += "\"summary\": {";
        json += "\"total_bid_volume\": 0,";
        json += "\"total_ask_volume\": 0,";
        json += "\"bid_levels\": 0,";
        json += "\"ask_levels\": 0,";
        json += "\"order_imbalance\": 0.0";
        json += "}";
    }
    
    json += "}";
    return json;
}

//+------------------------------------------------------------------+
//| INTEGRATION INSTRUCTIONS                                          |
//+------------------------------------------------------------------+
/*
1. Add this function to AI_Trading_EA_Ultimate.mq5 at the end (before last })

2. In CollectMarketData() function, add after SECTION 8:

    //=== SECTION 9: ORDER BOOK DATA ===
    json += "\"order_book\": " + GetOrderBookData(symbol, digits) + ",";

3. Subscribe to market depth in OnInit():
   
   for(int i = 0; i < ArraySize(TradingSymbols); i++)
   {
       if(!MarketBookAdd(TradingSymbols[i]))
       {
           Print("⚠️  Failed to subscribe to market depth for ", TradingSymbols[i]);
       }
   }

4. Unsubscribe in OnDeinit():

   for(int i = 0; i < ArraySize(TradingSymbols); i++)
   {
       MarketBookRelease(TradingSymbols[i]);
   }

This adds:
- Top 10 bid levels with price/volume
- Top 10 ask levels with price/volume
- Total bid/ask volumes
- Order imbalance ratio
- Number of levels

Total new fields: ~45 (10 bids × 2 + 10 asks × 2 + 5 summary)
*/
