//+------------------------------------------------------------------+
//| Event-Driven Bar Detection Patch for EA                          |
//| Add this code to the EA to detect which timeframe bar closed     |
//+------------------------------------------------------------------+

// Add these global variables at the top
datetime lastBarM5 = 0;
datetime lastBarM15 = 0;
datetime lastBarM30 = 0;
datetime lastBarH1 = 0;
datetime lastBarH4 = 0;
datetime lastBarD1 = 0;

//+------------------------------------------------------------------+
//| Check if new bar on any timeframe                                |
//+------------------------------------------------------------------+
string CheckNewBars(string symbol)
{
    string triggerTimeframe = "";
    
    // Check each timeframe for new bar
    datetime currentM5 = iTime(symbol, PERIOD_M5, 0);
    datetime currentM15 = iTime(symbol, PERIOD_M15, 0);
    datetime currentM30 = iTime(symbol, PERIOD_M30, 0);
    datetime currentH1 = iTime(symbol, PERIOD_H1, 0);
    datetime currentH4 = iTime(symbol, PERIOD_H4, 0);
    datetime currentD1 = iTime(symbol, PERIOD_D1, 0);
    
    // Priority: Higher timeframes trigger first
    if(currentD1 != lastBarD1 && lastBarD1 != 0)
    {
        triggerTimeframe = "D1";
        lastBarD1 = currentD1;
    }
    else if(currentH4 != lastBarH4 && lastBarH4 != 0)
    {
        triggerTimeframe = "H4";
        lastBarH4 = currentH4;
    }
    else if(currentH1 != lastBarH1 && lastBarH1 != 0)
    {
        triggerTimeframe = "H1";
        lastBarH1 = currentH1;
    }
    else if(currentM30 != lastBarM30 && lastBarM30 != 0)
    {
        triggerTimeframe = "M30";
        lastBarM30 = currentM30;
    }
    else if(currentM15 != lastBarM15 && lastBarM15 != 0)
    {
        triggerTimeframe = "M15";
        lastBarM15 = currentM15;
    }
    else if(currentM5 != lastBarM5 && lastBarM5 != 0)
    {
        triggerTimeframe = "M5";
        lastBarM5 = currentM5;
    }
    
    // Initialize on first run
    if(lastBarM5 == 0) lastBarM5 = currentM5;
    if(lastBarM15 == 0) lastBarM15 = currentM15;
    if(lastBarM30 == 0) lastBarM30 = currentM30;
    if(lastBarH1 == 0) lastBarH1 = currentH1;
    if(lastBarH4 == 0) lastBarH4 = currentH4;
    if(lastBarD1 == 0) lastBarD1 = currentD1;
    
    return triggerTimeframe;
}

//+------------------------------------------------------------------+
//| Modified CollectMarketData to include trigger timeframe          |
//+------------------------------------------------------------------+
// REPLACE the existing CollectMarketData function with this:

string CollectMarketData(string symbol, string triggerTimeframe = "")
{
    string json = "{";
    
    // Symbol info
    json += "\"symbol\":\"" + symbol + "\",";
    
    // Add trigger timeframe if provided
    if(triggerTimeframe != "")
    {
        json += "\"trigger_timeframe\":\"" + triggerTimeframe + "\",";
    }
    
    // ... rest of existing CollectMarketData code ...
    
    return json;
}

//+------------------------------------------------------------------+
//| Modified OnTick to use event-driven detection                    |
//+------------------------------------------------------------------+
// REPLACE the OnTick function with this:

void OnTick()
{
    if(MultiSymbolMode)
    {
        // Multi-symbol mode: Check each symbol for new bars
        for(int i = 0; i < ArraySize(TradingSymbols); i++)
        {
            string sym = TradingSymbols[i];
            
            // Check if any timeframe has a new bar
            string trigger = CheckNewBars(sym);
            
            if(trigger != "")
            {
                // New bar detected - call API
                if(VerboseLogging)
                {
                    Print("🎯 ", sym, ": New ", trigger, " bar - triggering AI scan");
                }
                
                // Collect data with trigger timeframe
                string marketData = CollectMarketData(sym, trigger);
                
                // Send to AI
                ProcessAIDecision(sym, marketData);
            }
        }
    }
    else
    {
        // Single symbol mode with event-driven detection
        string trigger = CheckNewBars(_Symbol);
        
        if(trigger != "")
        {
            if(VerboseLogging)
            {
                Print("🎯 New ", trigger, " bar - triggering AI scan");
            }
            
            // Update position tracking
            if(PositionsTotal() > 0)
            {
                positionBarsHeld++;
                
                if(positionBarsHeld >= MaxBarsHeld)
                {
                    Print("🚨 EMERGENCY: MAX HOLD TIME REACHED");
                    CloseAllPositions(_Symbol);
                    positionBarsHeld = 0;
                    return;
                }
            }
            else
            {
                positionBarsHeld = 0;
            }
            
            if(!EnableTrading)
                return;
            
            // Collect data with trigger timeframe
            string marketData = CollectMarketData(_Symbol, trigger);
            
            // Send to AI
            ProcessAIDecision(_Symbol, marketData);
        }
    }
}

//+------------------------------------------------------------------+
//| INSTRUCTIONS:                                                     |
//| 1. Add the global variables to the top of your EA                |
//| 2. Add the CheckNewBars() function                               |
//| 3. Modify CollectMarketData() to accept trigger_timeframe param  |
//| 4. Replace OnTick() with the event-driven version                |
//+------------------------------------------------------------------+
