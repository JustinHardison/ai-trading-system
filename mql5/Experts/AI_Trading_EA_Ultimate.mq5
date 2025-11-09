//+------------------------------------------------------------------+
//|                                      AI_Trading_EA_Ultimate.mq5 |
//|                     Ultimate AI Trading System - FTMO Optimized |
//|                                       Multi-Layer AI Integration |
//+------------------------------------------------------------------+
#property copyright "AI Trading System"
#property link      "https://localhost:5007"
#property version   "5.27"
#property description "Ultimate AI Trading EA - Full Position Management"
#property description "Multi-Layer: ML + Structure Analysis + RL + Risk Management"
#property description "FTMO Bulletproof: 5% Daily / 10% Total DD Protection"
#property description "v5.27: Added broker close-only mode detection"

//--- Include Trade Library
#include <Trade\Trade.mqh>

//--- Input Parameters
input string   API_URL = "http://127.0.0.1:5007/api/ai/trade_decision";
input double   FixedLotSize = 0.0;  // 0 = AI decides size
input int      MagicNumber = 123456;
input int      MaxBarsHeld = 200;   // Max hold time in bars
input bool     EnableTrading = true;
input bool     VerboseLogging = true;
input bool     MultiSymbolMode = true;  // Trade multiple symbols from one EA

// ═══════════════════════════════════════════════════════════════════
// FTMO CONFIGURATION - CRITICAL: Set these correctly!
// 
// FTMO_InitialBalance: The balance when your challenge/account started
// This value is used to calculate:
//   - Max Daily Loss = 5% of this value
//   - Max Total Loss = 10% of this value
// 
// IMPORTANT: This must match your FTMO account starting balance!
// For $200K account: 200000.0
// For $100K account: 100000.0
// For $50K account: 50000.0
// ═══════════════════════════════════════════════════════════════════
input double   FTMO_InitialBalance = 200000.0;  // FTMO starting balance (NEVER changes)

//--- Global Variables
datetime lastBarTime = 0;
int positionBarsHeld = 0;
string currentDirection = "NONE";
datetime lastM1BarTime = 0;  // Track M1 bar for scanning

//--- Trade Object
CTrade trade;

//--- FTMO Tracking Variables
double g_initial_balance = 0.0;      // CRITICAL: Balance when challenge started (NEVER changes)
double g_daily_start_balance = 0.0;  // Balance at CE(S)T midnight
double g_daily_realized_pnl = 0.0;   // Closed trades P&L today
double g_peak_balance = 0.0;         // Highest balance ever reached
datetime g_last_cest_day = 0;        // Track CE(S)T day for daily reset

// Multi-symbol trading symbols - ACTIVE SYMBOLS ONLY
// Updated Dec 17, 2025: Rolled to H26 (March 2026) contracts
string TradingSymbols[] = {
    // US INDICES (dedicated models per symbol) - H26 contracts
    "US30H26.sim",      // Dow Jones - US30 model (trained) ✅
    "US100H26.sim",     // Nasdaq 100 - US100 model (trained) ✅
    "US500H26.sim",     // S&P 500 - US500 model (trained) ✅
    
    // GOLD (best performing commodity)
    "XAUG26.sim"        // Gold - XAU model (trained) ✅
    
    // DISABLED SYMBOLS (removed from scanning):
    // EURUSD, GBPUSD, USDJPY - Forex disabled Dec 5, 2025
    // USOILF26 - Oil disabled Dec 3, 2025 (worst performer)
};

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
    Print("═══════════════════════════════════════════════════════════════════");
    Print("ULTIMATE AI MULTI-SYMBOL TRADING SYSTEM v5.27");
    Print("═══════════════════════════════════════════════════════════════════");
    Print("API Endpoint: ", API_URL);
    Print("Chart Symbol: ", _Symbol);
    Print("Magic Number: ", MagicNumber);
    Print("Trading: ", EnableTrading ? "ENABLED" : "DISABLED (Monitor Mode)");
    Print("Multi-Symbol Mode: ", MultiSymbolMode ? "ENABLED" : "DISABLED");
    if(MultiSymbolMode)
    {
        Print("Trading ", ArraySize(TradingSymbols), " Symbols (3 Indices + 1 Gold)");
        Print("Scan Trigger: Every M1 bar close (event-driven)");
        Print("DISABLED: Forex (EURUSD, GBPUSD, USDJPY) + Oil (USOIL)");
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // FTMO INITIALIZATION - CRITICAL
    // 
    // FTMO Rules (from ftmo.com):
    // - Max Daily Loss: 5% of INITIAL BALANCE (not current balance)
    // - Max Total Loss: 10% of INITIAL BALANCE (equity cannot drop below 90%)
    // - Daily loss resets at midnight CE(S)T (6 PM EST / 5 PM EDT)
    // ═══════════════════════════════════════════════════════════════════
    
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    
    // INITIAL BALANCE - From input parameter (persists across EA restarts)
    // This is the balance when the challenge/account was created
    // Set via FTMO_InitialBalance input parameter
    g_initial_balance = FTMO_InitialBalance;  // Always use input parameter
    
    // Initialize daily tracking if first time
    if(g_daily_start_balance == 0.0)
    {
        g_peak_balance = MathMax(balance, g_initial_balance);
        g_daily_start_balance = balance;
        g_daily_realized_pnl = 0.0;
    }
    
    // Update peak balance if current is higher
    if(balance > g_peak_balance)
    {
        g_peak_balance = balance;
    }
    
    Print("🔒 FTMO Initial Balance (from input): $", DoubleToString(g_initial_balance, 2));
    
    // ═══════════════════════════════════════════════════════════════════
    // FTMO RULES - EXACT FORMULAS FROM FTMO.COM
    // ═══════════════════════════════════════════════════════════════════
    
    // RULE 1: MAXIMUM DAILY LOSS (5% Rule)
    // Formula: Min Equity Today = Balance at midnight CE(S)T - (5% of initial balance)
    // The 5% is ALWAYS based on initial balance, not current
    double fivePercentOfInitial = g_initial_balance * 0.05;  // Always $10K for $200K
    double minEquityToday = g_daily_start_balance - fivePercentOfInitial;
    
    // RULE 2: MAXIMUM LOSS (10% Rule)
    // Formula: Equity cannot drop below 90% of INITIAL balance
    // This is ABSOLUTE - doesn't matter if you made profits before
    double minEquityAllowed = g_initial_balance * 0.90;  // $180K for $200K account
    double totalDDLimit = g_initial_balance * 0.10;  // $20K for $200K account
    
    Print("═══════════════════════════════════════════════════════════════════");
    Print("💰 FTMO RISK TRACKING (EXACT FTMO FORMULAS):");
    Print("   Initial Balance: $", DoubleToString(g_initial_balance, 2), " (NEVER changes)");
    Print("   Balance at Midnight: $", DoubleToString(g_daily_start_balance, 2));
    Print("   Current Balance: $", DoubleToString(balance, 2));
    Print("   Current Equity: $", DoubleToString(equity, 2));
    Print("   ─────────────────────────────────────────────────────────────");
    Print("   DAILY LOSS RULE (5%):");
    Print("      5% of Initial: $", DoubleToString(fivePercentOfInitial, 2));
    Print("      Min Equity Today: $", DoubleToString(minEquityToday, 2), " (midnight bal - 5%)");
    Print("      Room Left Today: $", DoubleToString(equity - minEquityToday, 2));
    Print("   ─────────────────────────────────────────────────────────────");
    Print("   TOTAL LOSS RULE (10%):");
    Print("      Min Equity Ever: $", DoubleToString(minEquityAllowed, 2), " (90% of initial)");
    Print("      Room Left Total: $", DoubleToString(equity - minEquityAllowed, 2));
    Print("   ─────────────────────────────────────────────────────────────");
    Print("   Daily Reset: Midnight CE(S)T (6 PM EST / 5 PM EDT)");
    Print("═══════════════════════════════════════════════════════════════════");

    // Verify connection to API
    if(!TestAPIConnection())
    {
        Print("❌ WARNING: Cannot reach AI API - Check if Python API is running");
        Print("   Start API: cd ~/ai-trading-system && python3 api.py");
    }
    else
    {
        Print("✅ AI API Connection Verified");
        Print("✅ 16 ML Models | 115 Features (100 market + 15 FTMO)");
    }
    
    // Validate and subscribe to market depth for all symbols
    if(MultiSymbolMode)
    {
        Print("📊 Validating symbols and subscribing to market depth...");
        for(int i = 0; i < ArraySize(TradingSymbols); i++)
        {
            string sym = TradingSymbols[i];
            
            // Check if symbol exists
            if(!SymbolSelect(sym, true))
            {
                Print("⚠️  Symbol ", sym, " not found in Market Watch - attempting to add...");
                if(!SymbolSelect(sym, true))
                {
                    Print("❌ Failed to add ", sym, " to Market Watch - symbol may not exist");
                    continue;
                }
            }
            
            // Try to get some data to verify symbol works
            MqlRates test_rates[];
            int copied = CopyRates(sym, PERIOD_M1, 0, 1, test_rates);
            if(copied <= 0)
            {
                int error = GetLastError();
                Print("❌ Symbol ", sym, " cannot load data (Error: ", error, ")");
                Print("   This symbol will be skipped during scanning");
                Print("   Possible fixes:");
                Print("   1. Check symbol name is correct");
                Print("   2. Load historical data by opening a chart");
                Print("   3. Symbol might not be available in your broker");
            }
            else
            {
                Print("✅ Symbol ", sym, " validated successfully");
            }
            
            if(MarketBookAdd(TradingSymbols[i]))
            {
                Print("  ✅ ", TradingSymbols[i], ": Market depth subscribed");
            }
            else
            {
                Print("  ⚠️  ", TradingSymbols[i], ": Market depth not available");
            }
        }
    }
    
    // Set timer for backup scanning (every 60 seconds)
    EventSetTimer(60);
    Print("✅ Timer set for 60-second backup scanning");
    
    // Do initial scan immediately
    Print("🚀 Running initial scan...");
    ScanAllSymbols("INIT");

    return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Trade Transaction Handler - Track realized P&L for FTMO          |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
    // Track realized P&L when a position closes
    if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
    {
        // Get deal info
        ulong dealTicket = trans.deal;
        if(dealTicket > 0)
        {
            if(HistoryDealSelect(dealTicket))
            {
                ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
                
                // Only track closing deals (DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT)
                if(dealEntry == DEAL_ENTRY_OUT || dealEntry == DEAL_ENTRY_INOUT)
                {
                    double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT);
                    double commission = HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);
                    double swap = HistoryDealGetDouble(dealTicket, DEAL_SWAP);
                    
                    // Total realized P&L includes profit, commission, and swap
                    double totalPnL = profit + commission + swap;
                    
                    TrackRealizedPnL(totalPnL);
                }
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    // Kill timer
    EventKillTimer();
    
    // Unsubscribe from market depth
    if(MultiSymbolMode)
    {
        for(int i = 0; i < ArraySize(TradingSymbols); i++)
        {
            MarketBookRelease(TradingSymbols[i]);
        }
    }
    
    Print("═══════════════════════════════════════════════════════════════════");
    Print("AI Trading EA Stopped - Reason: ", reason);
    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Expert timer function (for multi-symbol mode)                     |
//+------------------------------------------------------------------+
void OnTimer()
{
    if(MultiSymbolMode && EnableTrading)
    {
        Print("⏰ TIMER FIRED - Scanning all symbols...");
        ScanAllSymbols("TIMER");
    }
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
    if(MultiSymbolMode)
    {
        // ═══════════════════════════════════════════════════════════
        // CHECK MARKET HOURS FIRST - Don't waste time when closed
        // ═══════════════════════════════════════════════════════════
        MqlDateTime dt;
        TimeToStruct(TimeCurrent(), dt);
        int dayOfWeek = dt.day_of_week;  // 0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday
        int hour = dt.hour;
        
        bool marketOpen = false;
        
        if(dayOfWeek == 6)  // Saturday
        {
            marketOpen = false;
        }
        else if(dayOfWeek == 0)  // Sunday
        {
            marketOpen = (hour >= 18);  // Opens at 6 PM ET
        }
        else if(dayOfWeek == 5)  // Friday
        {
            marketOpen = (hour < 17);  // Closes at 5 PM ET
        }
        else  // Monday-Thursday
        {
            marketOpen = true;  // 24 hours
        }
        
        if(!marketOpen)
        {
            // Market closed - don't waste time scanning
            return;
        }
        
        // ═══════════════════════════════════════════════════════════
        // TICK-BASED SCANNING FOR POSITIONS AT RISK
        // Scan every tick if any position has significant loss
        // Otherwise scan on new M1 bar (normal mode)
        // ═══════════════════════════════════════════════════════════
        
        bool urgentScanNeeded = false;
        double totalFloatingLoss = 0;
        double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        
        // Check all positions for urgent situations
        for(int i = 0; i < PositionsTotal(); i++)
        {
            if(PositionSelectByTicket(PositionGetTicket(i)))
            {
                double profit = PositionGetDouble(POSITION_PROFIT);
                double volume = PositionGetDouble(POSITION_VOLUME);
                
                // Calculate profit/loss as % of account
                double profitPct = (profit / accountBalance) * 100.0;
                
                // URGENT: Position losing more than 0.3% of account
                if(profitPct < -0.3)
                {
                    urgentScanNeeded = true;
                    totalFloatingLoss += profit;
                }
                
                // URGENT: Large profitable position (> $500) - protect gains
                // These can turn into losses quickly in volatile markets
                if(profit > 500)
                {
                    urgentScanNeeded = true;
                }
            }
        }
        
        // Also urgent if total floating loss > 1% of account
        if((totalFloatingLoss / accountBalance) * 100.0 < -1.0)
        {
            urgentScanNeeded = true;
        }
        
        // ═══════════════════════════════════════════════════════════
        // TICK-BASED SCANNING FOR OPEN POSITIONS
        // Indices and commodities move FAST - need frequent monitoring
        // 
        // When we have open positions:
        //   - Scan every 3 seconds (not every tick to avoid API overload)
        //   - This allows AI to react quickly to reversals
        // 
        // When no positions:
        //   - Scan on M1 bar close (entry decisions don't need tick speed)
        // ═══════════════════════════════════════════════════════════
        
        bool hasOpenPositions = (PositionsTotal() > 0);
        datetime currentM1 = iTime(_Symbol, PERIOD_M1, 0);
        static datetime lastPositionScan = 0;
        datetime now = TimeCurrent();
        
        bool shouldScan = false;
        string scanReason = "";
        
        if(urgentScanNeeded)
        {
            // URGENT: Position at significant risk - scan every 5 seconds
            if(now - lastPositionScan >= 5)
            {
                shouldScan = true;
                scanReason = "URGENT (risk)";
                lastPositionScan = now;
            }
        }
        else if(hasOpenPositions)
        {
            // OPEN POSITIONS: Scan every 10 seconds for monitoring
            // (faster than M1 bar but not so fast it slows MT5)
            if(now - lastPositionScan >= 10)
            {
                shouldScan = true;
                scanReason = "POSITION MONITOR";
                lastPositionScan = now;
            }
        }
        else if(currentM1 != lastM1BarTime)
        {
            // NO POSITIONS: Scan on M1 bar close for new entries
            shouldScan = true;
            scanReason = "M1 BAR";
            lastM1BarTime = currentM1;
        }
        
        if(shouldScan)
        {
            if(VerboseLogging && scanReason != "M1 BAR")
            {
                Print("🔄 ", scanReason, " scan triggered");
            }
            ScanAllSymbols(scanReason);
        }
    }
    else
    {
        // Single symbol mode: Original logic
        datetime currentBarTime = iTime(_Symbol, PERIOD_M1, 0);
        if(currentBarTime == lastBarTime)
            return;

        lastBarTime = currentBarTime;

        // Update position tracking
        if(PositionsTotal() > 0)
        {
            positionBarsHeld++;

            // DISABLED: Let AI decide when to exit, not time-based
            // if(positionBarsHeld >= MaxBarsHeld)
            // {
            //     Print("⏰ MAX HOLD TIME REACHED (", MaxBarsHeld, " bars) - Closing position");
            //     CloseAllPositions(_Symbol);
            //     positionBarsHeld = 0;
            //     return;
            // }
        }
        else
        {
            positionBarsHeld = 0;
        }

        // Only trade if enabled
        if(!EnableTrading)
            return;

        // Collect comprehensive market data (AI handles position management)
        string marketData = CollectMarketData(_Symbol);

        if(VerboseLogging)
        {
            Print("═══════════════════════════════════════════════════════════════════");
            Print("📊 SENDING DATA TO AI SYSTEM...");
        }

        // Get AI decision
        string aiResponse = SendToAPI(marketData);

        if(aiResponse == "")
        {
            Print("❌ No response from AI API");
            return;
        }

        // Parse and execute AI decision
        ExecuteAIDecision(aiResponse, _Symbol);
    }
}

//+------------------------------------------------------------------+
//| Scan all symbols and trade opportunities                         |
//+------------------------------------------------------------------+
void ScanAllSymbols(string triggerType = "M1")
{
    if(!EnableTrading)
        return;
        
    Print("═══════════════════════════════════════════════════════════════════");
    Print("🔍 SCANNING ", ArraySize(TradingSymbols), " SYMBOLS [", triggerType, "]...");
    Print("═══════════════════════════════════════════════════════════════════");
    
    for(int i = 0; i < ArraySize(TradingSymbols); i++)
    {
        string symbol = TradingSymbols[i];
        
        // Collect market data for this symbol (even if we have a position - AI needs to monitor exits!)
        string marketData = CollectMarketData(symbol, triggerType);
        
        if(marketData == "")
        {
            if(VerboseLogging)
                Print("❌ ", symbol, ": Failed to collect market data");
            continue;
        }
        
        // Get AI decision (silent unless error)
        string aiResponse = SendToAPI(marketData);
        
        if(aiResponse == "")
        {
            Print("❌ ", symbol, ": No response from AI");
            continue;
        }
        
        // Parse and execute AI decision
        ExecuteAIDecision(aiResponse, symbol);
    }
    
    // Scan complete (silent unless VerboseLogging)
    if(VerboseLogging)
        Print("✅ Scan complete - ", ArraySize(TradingSymbols), " symbols analyzed");
}

//+------------------------------------------------------------------+
//| Check if we have a position on a symbol                          |
//| NOTE: Checks ANY position on symbol (not just our magic number)  |
//| This prevents error 10044 on FIFO/netting accounts               |
//+------------------------------------------------------------------+
bool HasPositionOnSymbol(string symbol)
{
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            // Check ANY position on this symbol (FIFO accounts can't have multiple positions)
            if(PositionGetString(POSITION_SYMBOL) == symbol)
            {
                return true;
            }
        }
    }
    return false;
}

//+------------------------------------------------------------------+
//| Collect comprehensive market data (214+ fields)                  |
//+------------------------------------------------------------------+
string CollectMarketData(string symbol, string triggerType = "M5")
{
    // Get symbol digits
    int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
    double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
    
    string json = "{";
    
    // Tell API what triggered this scan (for logging/analysis)
    json += "\"trigger_timeframe\": \"" + triggerType + "\",";

    //=== SECTION 1: CURRENT PRICE DATA ===
    json += "\"current_price\": {";
    json += "\"bid\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_BID), digits) + ",";
    json += "\"ask\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_ASK), digits) + ",";
    json += "\"last\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_LAST), digits) + ",";
    json += "\"spread\": " + IntegerToString((int)SymbolInfoInteger(symbol, SYMBOL_SPREAD)) + ",";
    json += "\"spread_points\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_ASK) - SymbolInfoDouble(symbol, SYMBOL_BID), digits);
    json += "},";

    //=== SECTION 2: ACCOUNT INFORMATION ===
    // ═══════════════════════════════════════════════════════════════════
    // FTMO RULES (from ftmo.com):
    // - Max Daily Loss: 5% of INITIAL BALANCE (not current balance)
    // - Max Total Loss: 10% of INITIAL BALANCE (equity cannot drop below 90%)
    // - Daily loss resets at midnight CE(S)T (6 PM EST / 5 PM EDT)
    // - Includes floating P&L, commissions, and swaps
    // ═══════════════════════════════════════════════════════════════════
    
    // Update FTMO tracking before sending
    UpdateFTMOTracking();
    
    json += "\"account\": {";
    json += "\"balance\": " + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
    json += "\"equity\": " + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
    json += "\"margin\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
    json += "\"free_margin\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";
    json += "\"margin_level\": " + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
    json += "\"profit\": " + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
    json += "\"currency\": \"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",";
    
    // FTMO-specific data - CRITICAL: All calculations based on INITIAL BALANCE
    json += "\"initial_balance\": " + DoubleToString(g_initial_balance, 2) + ",";  // NEVER changes
    json += "\"daily_pnl\": " + DoubleToString(GetDailyPnL(), 2) + ",";
    json += "\"daily_realized_pnl\": " + DoubleToString(GetDailyRealizedPnL(), 2) + ",";
    json += "\"daily_start_balance\": " + DoubleToString(g_daily_start_balance, 2) + ",";
    json += "\"max_daily_loss\": " + DoubleToString(g_initial_balance * 0.05, 2) + ",";  // 5% of INITIAL
    json += "\"max_total_drawdown\": " + DoubleToString(g_initial_balance * 0.10, 2) + ",";  // 10% of INITIAL
    json += "\"peak_balance\": " + DoubleToString(g_peak_balance, 2);
    json += "},";

    //=== SECTION 3: SYMBOL SPECIFICATIONS ===
    json += "\"symbol_info\": {";
    json += "\"symbol\": \"" + symbol + "\",";  // CRITICAL: Send actual symbol being traded
    json += "\"digits\": " + IntegerToString(digits) + ",";
    json += "\"point\": " + DoubleToString(point, digits) + ",";
    json += "\"contract_size\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE), 2) + ",";
    json += "\"tick_value\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE), 2) + ",";
    json += "\"tick_size\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE), digits) + ",";
    json += "\"min_lot\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN), 2) + ",";
    json += "\"max_lot\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX), 2) + ",";
    json += "\"lot_step\": " + DoubleToString(SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP), 2);
    json += "},";

    //=== SECTION 4: MULTI-TIMEFRAME OHLCV DATA ===
    json += "\"timeframes\": {";

    // M1 (50 bars)
    json += "\"m1\": " + GetTimeframeData(symbol, digits, PERIOD_M1, 50) + ",";

    // M5 (50 bars)
    json += "\"m5\": " + GetTimeframeData(symbol, digits, PERIOD_M5, 50) + ",";

    // M15 (50 bars)
    json += "\"m15\": " + GetTimeframeData(symbol, digits, PERIOD_M15, 50) + ",";

    // M30 (50 bars)
    json += "\"m30\": " + GetTimeframeData(symbol, digits, PERIOD_M30, 50) + ",";

    // H1 (50 bars)
    json += "\"h1\": " + GetTimeframeData(symbol, digits, PERIOD_H1, 50) + ",";

    // H4 (50 bars)
    json += "\"h4\": " + GetTimeframeData(symbol, digits, PERIOD_H4, 50) + ",";

    // D1 (50 bars)
    json += "\"d1\": " + GetTimeframeData(symbol, digits, PERIOD_D1, 50) + ",";
    
    // W1 (20 bars) - Weekly for bias confirmation
    json += "\"w1\": " + GetTimeframeData(symbol, digits, PERIOD_W1, 20);

    json += "},";

    //=== SECTION 5: TECHNICAL INDICATORS (M1) ===
    json += "\"indicators\": {";

    // ATR (14, 20, 50) - with error handling
    int atr14Handle = iATR(symbol, PERIOD_M1, 14);
    int atr20Handle = iATR(symbol, PERIOD_M1, 20);
    int atr50Handle = iATR(symbol, PERIOD_M1, 50);
    double atr14[], atr20[], atr50[];
    ArraySetAsSeries(atr14, true);
    ArraySetAsSeries(atr20, true);
    ArraySetAsSeries(atr50, true);
    
    double atr14Val = 0, atr20Val = 0, atr50Val = 0;
    if(atr14Handle != INVALID_HANDLE && CopyBuffer(atr14Handle, 0, 0, 1, atr14) > 0) atr14Val = atr14[0];
    if(atr20Handle != INVALID_HANDLE && CopyBuffer(atr20Handle, 0, 0, 1, atr20) > 0) atr20Val = atr20[0];
    if(atr50Handle != INVALID_HANDLE && CopyBuffer(atr50Handle, 0, 0, 1, atr50) > 0) atr50Val = atr50[0];
    
    json += "\"atr_14\": " + DoubleToString(atr14Val, digits) + ",";
    json += "\"atr_20\": " + DoubleToString(atr20Val, digits) + ",";
    json += "\"atr_50\": " + DoubleToString(atr50Val, digits) + ",";

    // RSI (14) - with error handling
    int rsiHandle = iRSI(symbol, PERIOD_M1, 14, PRICE_CLOSE);
    double rsi[];
    ArraySetAsSeries(rsi, true);
    double rsiVal = 50.0;  // Default neutral
    if(rsiHandle != INVALID_HANDLE && CopyBuffer(rsiHandle, 0, 0, 1, rsi) > 0) rsiVal = rsi[0];
    json += "\"rsi_14\": " + DoubleToString(rsiVal, 2) + ",";

    // MACD (12, 26, 9) - with error handling
    int macdHandle = iMACD(symbol, PERIOD_M1, 12, 26, 9, PRICE_CLOSE);
    double macdMain[], macdSignal[];
    ArraySetAsSeries(macdMain, true);
    ArraySetAsSeries(macdSignal, true);
    double macdMainVal = 0, macdSignalVal = 0;
    if(macdHandle != INVALID_HANDLE) {
        if(CopyBuffer(macdHandle, 0, 0, 1, macdMain) > 0) macdMainVal = macdMain[0];
        if(CopyBuffer(macdHandle, 1, 0, 1, macdSignal) > 0) macdSignalVal = macdSignal[0];
    }
    json += "\"macd_main\": " + DoubleToString(macdMainVal, digits) + ",";
    json += "\"macd_signal\": " + DoubleToString(macdSignalVal, digits) + ",";

    // Bollinger Bands (20, 2.0) - with error handling
    int bbHandle = iBands(symbol, PERIOD_M1, 20, 0, 2.0, PRICE_CLOSE);
    double bbUpper[], bbMiddle[], bbLower[];
    ArraySetAsSeries(bbUpper, true);
    ArraySetAsSeries(bbMiddle, true);
    ArraySetAsSeries(bbLower, true);
    double bbUpperVal = 0, bbMiddleVal = 0, bbLowerVal = 0;
    if(bbHandle != INVALID_HANDLE) {
        if(CopyBuffer(bbHandle, 0, 0, 1, bbUpper) > 0) bbUpperVal = bbUpper[0];
        if(CopyBuffer(bbHandle, 1, 0, 1, bbMiddle) > 0) bbMiddleVal = bbMiddle[0];
        if(CopyBuffer(bbHandle, 2, 0, 1, bbLower) > 0) bbLowerVal = bbLower[0];
    }
    json += "\"bb_upper\": " + DoubleToString(bbUpperVal, digits) + ",";
    json += "\"bb_middle\": " + DoubleToString(bbMiddleVal, digits) + ",";
    json += "\"bb_lower\": " + DoubleToString(bbLowerVal, digits) + ",";

    // Moving Averages - with error handling
    int sma20Handle = iMA(symbol, PERIOD_M1, 20, 0, MODE_SMA, PRICE_CLOSE);
    int sma50Handle = iMA(symbol, PERIOD_M1, 50, 0, MODE_SMA, PRICE_CLOSE);
    int ema20Handle = iMA(symbol, PERIOD_M1, 20, 0, MODE_EMA, PRICE_CLOSE);
    double sma20[], sma50[], ema20[];
    ArraySetAsSeries(sma20, true);
    ArraySetAsSeries(sma50, true);
    ArraySetAsSeries(ema20, true);
    double sma20Val = 0, sma50Val = 0, ema20Val = 0;
    if(sma20Handle != INVALID_HANDLE && CopyBuffer(sma20Handle, 0, 0, 1, sma20) > 0) sma20Val = sma20[0];
    if(sma50Handle != INVALID_HANDLE && CopyBuffer(sma50Handle, 0, 0, 1, sma50) > 0) sma50Val = sma50[0];
    if(ema20Handle != INVALID_HANDLE && CopyBuffer(ema20Handle, 0, 0, 1, ema20) > 0) ema20Val = ema20[0];
    json += "\"sma_20\": " + DoubleToString(sma20Val, digits) + ",";
    json += "\"sma_50\": " + DoubleToString(sma50Val, digits) + ",";
    json += "\"ema_20\": " + DoubleToString(ema20Val, digits);

    json += "},";

    //=== SECTION 6: OPEN POSITIONS ===
    json += "\"positions\": [";
    for(int i = 0; i < PositionsTotal(); i++)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(i > 0) json += ",";
            json += "{";
            json += "\"symbol\": \"" + PositionGetString(POSITION_SYMBOL) + "\",";
            json += "\"ticket\": " + IntegerToString(PositionGetInteger(POSITION_TICKET)) + ",";
            json += "\"type\": " + IntegerToString(PositionGetInteger(POSITION_TYPE)) + ",";
            json += "\"volume\": " + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
            json += "\"price_open\": " + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + ",";
            json += "\"price_current\": " + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), digits) + ",";
            json += "\"sl\": " + DoubleToString(PositionGetDouble(POSITION_SL), digits) + ",";
            json += "\"tp\": " + DoubleToString(PositionGetDouble(POSITION_TP), digits) + ",";
            json += "\"profit\": " + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\"swap\": " + DoubleToString(PositionGetDouble(POSITION_SWAP), 2) + ",";
            json += "\"time\": " + IntegerToString(PositionGetInteger(POSITION_TIME)) + ",";
            
            // Calculate position age in minutes
            datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
            int ageMinutes = (int)((TimeCurrent() - openTime) / 60);
            json += "\"age_minutes\": " + IntegerToString(ageMinutes);
            json += "}";
        }
    }
    json += "],";

    //=== SECTION 7: RECENT TRADE HISTORY ===
    // Only include EXIT deals (DEAL_ENTRY_OUT) with actual profit/loss
    // Increased limit to 50 to capture all recent closed trades
    json += "\"recent_trades\": [";
    HistorySelect(TimeCurrent() - 86400, TimeCurrent());  // Last 24 hours
    int historyDeals = HistoryDealsTotal();
    int count = 0;
    for(int i = historyDeals - 1; i >= 0 && count < 50; i--)
    {
        ulong ticket = HistoryDealGetTicket(i);
        if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == MagicNumber)
        {
            // Only include exit deals (deals that close positions and have profit/loss)
            ENUM_DEAL_ENTRY dealEntry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
            double dealProfit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
            
            // Skip entry deals (they have $0 profit) - only count exit deals
            if(dealEntry == DEAL_ENTRY_IN && dealProfit == 0)
                continue;
            
            if(count > 0) json += ",";
            json += "{";
            json += "\"ticket\": " + IntegerToString((long)ticket) + ",";
            json += "\"profit\": " + DoubleToString(dealProfit, 2) + ",";
            json += "\"swap\": " + DoubleToString(HistoryDealGetDouble(ticket, DEAL_SWAP), 2) + ",";
            json += "\"commission\": " + DoubleToString(HistoryDealGetDouble(ticket, DEAL_COMMISSION), 2) + ",";
            json += "\"symbol\": \"" + HistoryDealGetString(ticket, DEAL_SYMBOL) + "\",";
            json += "\"volume\": " + DoubleToString(HistoryDealGetDouble(ticket, DEAL_VOLUME), 2) + ",";
            json += "\"entry_type\": \"" + (dealEntry == DEAL_ENTRY_OUT ? "OUT" : (dealEntry == DEAL_ENTRY_INOUT ? "INOUT" : "IN")) + "\"";
            json += "}";
            count++;
        }
    }
    json += "],";

    //=== SECTION 8: ORDER BOOK DATA (Market Depth) ===
    json += "\"order_book\": " + GetOrderBookData(symbol, digits) + ",";

    //=== SECTION 9: ECONOMIC CALENDAR (High/Medium Impact Events) ===
    json += "\"calendar_events\": " + GetCalendarEvents(symbol) + ",";

    //=== SECTION 10: TIMING & METADATA ===
    json += "\"metadata\": {";
    json += "\"timestamp\": \"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",";
    json += "\"server_time\": " + IntegerToString(TimeCurrent()) + ",";
    json += "\"bars_held\": " + IntegerToString(positionBarsHeld) + ",";
    json += "\"magic_number\": " + IntegerToString(MagicNumber);
    json += "}";

    json += "}";

    return json;
}

//+------------------------------------------------------------------+
//| Get timeframe OHLCV data as JSON array                          |
//+------------------------------------------------------------------+
string GetTimeframeData(string symbol, int digits, ENUM_TIMEFRAMES timeframe, int bars)
{
    MqlRates rates[];
    ArraySetAsSeries(rates, true);
    int copied = CopyRates(symbol, timeframe, 0, bars, rates);
    
    // Check if data was copied successfully
    if(copied <= 0)
    {
        if(VerboseLogging)
        {
            Print("⚠️  Failed to get ", EnumToString(timeframe), " data for ", symbol, " (Error: ", GetLastError(), ")");
        }
        return "[]";  // Return empty array
    }

    string json = "[";
    for(int i = 0; i < copied; i++)
    {
        if(i > 0) json += ",";
        json += "{";
        json += "\"time\": " + IntegerToString(rates[i].time) + ",";
        json += "\"open\": " + DoubleToString(rates[i].open, digits) + ",";
        json += "\"high\": " + DoubleToString(rates[i].high, digits) + ",";
        json += "\"low\": " + DoubleToString(rates[i].low, digits) + ",";
        json += "\"close\": " + DoubleToString(rates[i].close, digits) + ",";
        json += "\"volume\": " + IntegerToString(rates[i].tick_volume);
        json += "}";
    }
    json += "]";

    return json;
}

//+------------------------------------------------------------------+
//| Send data to AI API and get response                            |
//+------------------------------------------------------------------+
string SendToAPI(string jsonData)
{
    char post[], result[];
    string headers = "Content-Type: application/json\r\n";

    StringToCharArray(jsonData, post, 0, StringLen(jsonData));

    int timeout = 5000;  // 5 seconds
    int res = WebRequest("POST", API_URL, headers, timeout, post, result, headers);

    if(res == -1)
    {
        Print("❌ API Request Failed - Error: ", GetLastError());
        return "";
    }

    string response = CharArrayToString(result);

    // Response received silently (reduce log spam)

    return response;
}

//+------------------------------------------------------------------+
//| Parse and execute AI decision                                    |
//+------------------------------------------------------------------+
void ExecuteAIDecision(string response, string symbol)
{
    // ═══════════════════════════════════════════════════════════════════
    // STEP 1: PROCESS PORTFOLIO DECISIONS (Multi-Position Management)
    // ═══════════════════════════════════════════════════════════════════
    
    // Check if response contains portfolio_decisions array
    if(StringFind(response, "\"portfolio_decisions\"") >= 0)
    {
        Print("📊 Processing portfolio decisions for all positions...");
        
        // Extract portfolio_decisions array
        int start = StringFind(response, "\"portfolio_decisions\":[");
        if(start >= 0)
        {
            start += 24; // Move past "portfolio_decisions":[
            int end = StringFind(response, "]", start);
            
            if(end > start)
            {
                string portfolioData = StringSubstr(response, start, end - start);
                
                // Split by decision objects (simple parser)
                int decisionCount = 0;
                int pos = 0;
                
                while(pos < StringLen(portfolioData))
                {
                    int objStart = StringFind(portfolioData, "{", pos);
                    if(objStart < 0) break;
                    
                    int objEnd = StringFind(portfolioData, "}", objStart);
                    if(objEnd < 0) break;
                    
                    string decisionObj = StringSubstr(portfolioData, objStart, objEnd - objStart + 1);
                    
                    // Extract decision fields
                    string decSymbol = ExtractJSONValue(decisionObj, "symbol");
                    string decAction = ExtractJSONValue(decisionObj, "action");
                    double addLots = StringToDouble(ExtractJSONValue(decisionObj, "add_lots"));
                    double reduceLots = StringToDouble(ExtractJSONValue(decisionObj, "reduce_lots"));
                    
                    StringTrimLeft(decSymbol);
                    StringTrimRight(decSymbol);
                    StringTrimLeft(decAction);
                    StringTrimRight(decAction);
                    StringToUpper(decAction);
                    
                    // Execute decision for this symbol
                    if(decAction == "SCALE_IN" && addLots > 0)
                    {
                        ExecuteScaleIn(decSymbol, addLots);
                        decisionCount++;
                    }
                    else if(decAction == "SCALE_OUT" && reduceLots > 0)
                    {
                        ExecuteScaleOut(decSymbol, reduceLots);
                        decisionCount++;
                    }
                    else if(decAction == "CLOSE")
                    {
                        ClosePosition(decSymbol);
                        decisionCount++;
                    }
                    // HOLD = do nothing
                    
                    pos = objEnd + 1;
                }
                
                if(decisionCount > 0)
                {
                    Print("✅ Processed ", decisionCount, " portfolio decisions");
                }
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // STEP 2: PROCESS MAIN ACTION (New Trades)
    // ═══════════════════════════════════════════════════════════════════
    
    // Parse JSON response
    string action = ExtractJSONValue(response, "action");
    StringTrimLeft(action);
    StringTrimRight(action);
    StringToUpper(action);  // Convert to uppercase for comparison
    
    // Get symbol from response (for position actions like SCALE_IN/SCALE_OUT)
    string responseSymbol = ExtractJSONValue(response, "symbol");
    StringTrimLeft(responseSymbol);
    StringTrimRight(responseSymbol);
    // Use response symbol if provided, otherwise use the scanned symbol
    if(StringLen(responseSymbol) > 0)
        symbol = responseSymbol;
    
    double lotSize = StringToDouble(ExtractJSONValue(response, "lot_size"));
    double addLots = StringToDouble(ExtractJSONValue(response, "add_lots"));
    double reduceLots = StringToDouble(ExtractJSONValue(response, "reduce_lots"));
    double newSL = StringToDouble(ExtractJSONValue(response, "new_sl"));
    double stopLoss = StringToDouble(ExtractJSONValue(response, "stop_loss"));
    double takeProfit = StringToDouble(ExtractJSONValue(response, "take_profit"));
    string reason = ExtractJSONValue(response, "reason");
    double quality = StringToDouble(ExtractJSONValue(response, "quality_score"));
    
    // For SCALE_IN/DCA, use add_lots; for SCALE_OUT use reduce_lots
    if(addLots > 0 && lotSize == 0)
        lotSize = addLots;
    if(reduceLots > 0 && lotSize == 0)
        lotSize = reduceLots;

    // Override lot size if fixed
    if(FixedLotSize > 0)
        lotSize = FixedLotSize;

    // Display AI decision (clean, matches API)
    if(VerboseLogging)
    {
        Print("═══════════════════════════════════════════════════════════════════");
        Print("🤖 AI DECISION:");
        Print("   Action: ", action);
        Print("   Reason: ", reason);
        if(lotSize > 0)
        {
            Print("   Lot Size: ", lotSize);
            if(addLots > 0) Print("   Add Lots: ", addLots);
            if(reduceLots > 0) Print("   Reduce Lots: ", reduceLots);
            Print("   Stop Loss: ", stopLoss);
            Print("   Take Profit: ", takeProfit);
        }
        if(newSL > 0) Print("   New SL: ", newSL);
        Print("═══════════════════════════════════════════════════════════════════");
    }
    
    // Execute trade
    if(action == "BUY" && lotSize > 0)
    {
        // Don't open new position if we already have one
        if(HasPositionOnSymbol(symbol))
        {
            Print("⏭️  Already have position on ", symbol, " - skipping BUY");
        }
        else
        {
            double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
            Print("📈 EXECUTING BUY ORDER...");

            if(ExecuteTrade(symbol, ORDER_TYPE_BUY, lotSize, ask, stopLoss, takeProfit))
            {
                Print("✅ BUY ORDER EXECUTED SUCCESSFULLY");
                currentDirection = "BUY";
                positionBarsHeld = 0;
            }
        }
    }
    else if(action == "SELL" && lotSize > 0)
    {
        // Don't open new position if we already have one
        if(HasPositionOnSymbol(symbol))
        {
            Print("⏭️  Already have position on ", symbol, " - skipping SELL");
        }
        else
        {
            double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
            Print("📉 EXECUTING SELL ORDER...");

            if(ExecuteTrade(symbol, ORDER_TYPE_SELL, lotSize, bid, stopLoss, takeProfit))
            {
                Print("✅ SELL ORDER EXECUTED SUCCESSFULLY");
                currentDirection = "SELL";
                positionBarsHeld = 0;
            }
        }
    }
    else if(action == "HOLD")
    {
        // Already logged above, no duplicate message
    }
    else if(action == "CLOSE")
    {
        Print("🚪 AI EXIT SIGNAL - Closing position on ", symbol);
        CloseAllPositions(symbol);
    }
    else if(action == "DCA" && lotSize > 0)
    {
        Print("📊 SMART DCA - Adding ", lotSize, " lots to position on ", symbol);
        Print("DEBUG: Checking if has position on ", symbol);
        if(HasPositionOnSymbol(symbol))
        {
            Print("DEBUG: Position found, looking for symbol in positions");
            // Get current position type
            for(int i = PositionsTotal() - 1; i >= 0; i--)
            {
                string posSymbol = PositionGetSymbol(i);
                Print("DEBUG: Checking position ", i, " symbol: ", posSymbol);
                if(posSymbol == symbol)
                {
                    Print("DEBUG: Symbol matched! Getting position type");
                    long posType = PositionGetInteger(POSITION_TYPE);
                    ENUM_ORDER_TYPE orderType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
                    double price = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
                    
                    // Use stop loss from API, or existing position's SL if not provided
                    double dcaSL = stopLoss;
                    if(dcaSL == 0)
                    {
                        dcaSL = PositionGetDouble(POSITION_SL);
                        Print("   Using existing position SL: ", dcaSL);
                    }
                    
                    Print("DEBUG: Executing DCA trade - Type: ", orderType, " Lots: ", lotSize, " Price: ", price, " SL: ", dcaSL);
                    if(ExecuteTrade(symbol, orderType, lotSize, price, dcaSL, 0))
                    {
                        Print("✅ DCA ORDER EXECUTED - Added ", lotSize, " lots with SL: ", dcaSL);
                    }
                    else
                    {
                        Print("❌ DCA ORDER FAILED");
                    }
                    break;
                }
            }
        }
        else
        {
            Print("DEBUG: No position found on ", symbol, " - cannot DCA");
        }
    }
    else if(action == "SCALE_IN" && lotSize > 0)
    {
        Print("📈 SCALE IN - Adding ", lotSize, " lots to position on ", symbol);
        
        // Find position by ticket
        bool positionFound = false;
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0 && PositionSelectByTicket(ticket))
            {
                string posSymbol = PositionGetString(POSITION_SYMBOL);
                if(posSymbol == symbol)
                {
                    positionFound = true;
                    long posType = PositionGetInteger(POSITION_TYPE);
                    double posVolume = PositionGetDouble(POSITION_VOLUME);
                    ENUM_ORDER_TYPE orderType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
                    double price = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_ASK) : SymbolInfoDouble(symbol, SYMBOL_BID);
                    
                    // Use stop loss from API, or existing position's SL if not provided
                    double scaleSL = stopLoss;
                    if(scaleSL == 0)
                    {
                        scaleSL = PositionGetDouble(POSITION_SL);
                        Print("   Using existing position SL: ", scaleSL);
                    }
                    
                    Print("   Found ticket #", ticket, " | ", posSymbol, " | ", posVolume, " lots | ", (posType == POSITION_TYPE_BUY ? "BUY" : "SELL"));
                    Print("   Adding ", lotSize, " lots at price ", price, " with SL: ", scaleSL);
                    
                    if(ExecuteTrade(symbol, orderType, lotSize, price, scaleSL, 0))
                    {
                        Print("✅ SCALE IN EXECUTED - Added ", lotSize, " lots to ticket #", ticket, " with SL: ", scaleSL);
                    }
                    else
                    {
                        Print("❌ SCALE IN FAILED - Error: ", GetLastError());
                    }
                    break;
                }
            }
        }
        
        if(!positionFound)
        {
            Print("   ❌ No position found on ", symbol);
            Print("   Available positions:");
            for(int i = 0; i < PositionsTotal(); i++)
            {
                ulong t = PositionGetTicket(i);
                if(t > 0 && PositionSelectByTicket(t))
                    Print("      #", t, " ", PositionGetString(POSITION_SYMBOL));
            }
        }
    }
    else if(action == "SCALE_OUT" && lotSize > 0)
    {
        Print("💰 SCALE OUT - Reducing position by ", lotSize, " lots on ", symbol);
        
        // Find position by ticket
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0 && PositionSelectByTicket(ticket))
            {
                string posSymbol = PositionGetString(POSITION_SYMBOL);
                if(posSymbol == symbol)
                {
                    long posType = PositionGetInteger(POSITION_TYPE);
                    double posVolume = PositionGetDouble(POSITION_VOLUME);
                    ENUM_ORDER_TYPE closeType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
                    double price = (posType == POSITION_TYPE_BUY) ? SymbolInfoDouble(symbol, SYMBOL_BID) : SymbolInfoDouble(symbol, SYMBOL_ASK);
                    
                    // Normalize lot size to broker requirements
                    double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
                    double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
                    double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
                    
                    // Round to lot step (floor to avoid exceeding position)
                    double normalizedLots = MathFloor(lotSize / lotStep) * lotStep;
                    
                    // Clamp to min/max
                    if(normalizedLots < minLot) normalizedLots = minLot;
                    if(normalizedLots > maxLot) normalizedLots = maxLot;
                    if(normalizedLots > posVolume) normalizedLots = posVolume;  // Can't close more than we have
                    
                    Print("   Found ticket #", ticket, " | ", posVolume, " lots | Closing ", normalizedLots, " lots (normalized from ", lotSize, ")");
                    
                    MqlTradeRequest request;
                    MqlTradeResult result;
                    ZeroMemory(request);
                    ZeroMemory(result);
                    
                    request.action = TRADE_ACTION_DEAL;
                    request.symbol = symbol;
                    request.volume = normalizedLots;
                    request.type = closeType;
                    request.price = price;
                    request.position = ticket;
                    request.deviation = 10;
                    request.magic = MagicNumber;
                    request.comment = "Scale Out";
                    
                    if(OrderSend(request, result))
                    {
                        Print("✅ SCALE OUT EXECUTED - Reduced ticket #", ticket, " by ", lotSize, " lots");
                    }
                    else
                    {
                        Print("❌ Scale out failed: ", GetLastError());
                    }
                    break;
                }
            }
        }
    }
    else if(action == "MODIFY_SL" && newSL > 0)
    {
        Print("🔄 MODIFY STOP LOSS - New SL: ", newSL, " on ", symbol);
        
        // Find position by ticket
        for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if(ticket > 0 && PositionSelectByTicket(ticket))
            {
                string posSymbol = PositionGetString(POSITION_SYMBOL);
                if(posSymbol == symbol)
                {
                    double currentSL = PositionGetDouble(POSITION_SL);
                    double currentTP = PositionGetDouble(POSITION_TP);
                    
                    Print("   Found ticket #", ticket, " | Current SL: ", currentSL, " → New SL: ", newSL);
                    
                    MqlTradeRequest request;
                    MqlTradeResult result;
                    ZeroMemory(request);
                    ZeroMemory(result);
                    
                    request.action = TRADE_ACTION_SLTP;
                    request.symbol = symbol;
                    request.position = ticket;
                    request.sl = newSL;
                    request.tp = currentTP;
                    
                    if(OrderSend(request, result))
                    {
                        Print("✅ STOP LOSS MODIFIED - Ticket #", ticket, " SL: ", newSL);
                    }
                    else
                    {
                        Print("❌ Modify SL failed: ", GetLastError());
                    }
                    break;
                }
            }
        }
    }

    Print("═══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Check if symbol allows new positions (not close-only mode)       |
//+------------------------------------------------------------------+
bool CanOpenNewPosition(string symbol)
{
    ENUM_SYMBOL_TRADE_MODE tradeMode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE);
    
    // SYMBOL_TRADE_MODE_DISABLED = 0 - Trade disabled
    // SYMBOL_TRADE_MODE_LONGONLY = 1 - Only buy orders allowed
    // SYMBOL_TRADE_MODE_SHORTONLY = 2 - Only sell orders allowed
    // SYMBOL_TRADE_MODE_CLOSEONLY = 3 - Only close operations allowed
    // SYMBOL_TRADE_MODE_FULL = 4 - No trade restrictions
    
    if(tradeMode == SYMBOL_TRADE_MODE_CLOSEONLY)
    {
        Print("⚠️ ", symbol, " is in CLOSE-ONLY mode - broker restriction");
        return false;
    }
    
    if(tradeMode == SYMBOL_TRADE_MODE_DISABLED)
    {
        Print("⚠️ ", symbol, " trading is DISABLED by broker");
        return false;
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Execute trade with error handling                                |
//+------------------------------------------------------------------+
bool ExecuteTrade(string symbol, ENUM_ORDER_TYPE orderType, double lots, double price, double sl, double tp)
{
    // Check if symbol allows new positions
    if(!CanOpenNewPosition(symbol))
    {
        return false;
    }
    
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    // Normalize lot size to broker requirements
    double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
    double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
    double lotStep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
    
    // Round to lot step
    lots = MathFloor(lots / lotStep) * lotStep;
    
    // Clamp to min/max
    if(lots < minLot) lots = minLot;
    if(lots > maxLot) lots = maxLot;
    
    Print("   Normalized lots: ", lots, " (min=", minLot, ", max=", maxLot, ", step=", lotStep, ")");

    request.action = TRADE_ACTION_DEAL;
    request.symbol = symbol;
    request.volume = lots;
    request.type = orderType;
    request.price = price;
    request.sl = sl;
    request.tp = tp;
    request.deviation = 10;
    request.magic = MagicNumber;
    request.comment = "AI Trade";

    if(!OrderSend(request, result))
    {
        Print("❌ OrderSend Failed - Error: ", GetLastError());
        Print("   Result Code: ", result.retcode);
        Print("   Result: ", result.comment);
        return false;
    }

    if(result.retcode != TRADE_RETCODE_DONE)
    {
        Print("❌ Trade Not Executed - Code: ", result.retcode);
        return false;
    }

    return true;
}

//+------------------------------------------------------------------+
//| Close all positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions(string symbol)
{
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol &&
               PositionGetInteger(POSITION_MAGIC) == MagicNumber)
            {
                MqlTradeRequest request;
                MqlTradeResult result;
                ZeroMemory(request);
                ZeroMemory(result);

                request.action = TRADE_ACTION_DEAL;
                request.position = ticket;
                request.symbol = symbol;
                request.volume = PositionGetDouble(POSITION_VOLUME);
                request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
                request.price = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ?
                                SymbolInfoDouble(symbol, SYMBOL_BID) :
                                SymbolInfoDouble(symbol, SYMBOL_ASK);
                request.deviation = 10;
                request.magic = MagicNumber;

                if(!OrderSend(request, result))
                {
                    Print("❌ Failed to close position - Error: ", GetLastError());
                }
            }
        }
    }

    positionBarsHeld = 0;
    currentDirection = "NONE";
}

//+------------------------------------------------------------------+
//| Extract value from JSON string (simple parser)                   |
//+------------------------------------------------------------------+
string ExtractJSONValue(string json, string key)
{
    string searchKey = "\"" + key + "\":";
    int start = StringFind(json, searchKey);
    if(start == -1) return "";

    start += StringLen(searchKey);

    // Skip whitespace
    while(start < StringLen(json) && (StringGetCharacter(json, start) == ' ' || StringGetCharacter(json, start) == '\t'))
        start++;

    // Check if value is string
    bool isString = false;
    if(StringGetCharacter(json, start) == '"')
    {
        isString = true;
        start++;
    }

    int end = start;
    if(isString)
    {
        end = StringFind(json, "\"", start);
    }
    else
    {
        // Find end of number/boolean
        while(end < StringLen(json))
        {
            ushort c = StringGetCharacter(json, end);
            if(c == ',' || c == '}' || c == ']' || c == ' ' || c == '\n' || c == '\r')
                break;
            end++;
        }
    }

    return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Get Order Book (Market Depth) data as JSON                       |
//+------------------------------------------------------------------+
string GetOrderBookData(string symbol, int digits)
{
    MqlBookInfo book[];
    string json = "{";
    
    if(MarketBookGet(symbol, book))
    {
        long totalBidVolume = 0;
        long totalAskVolume = 0;
        
        // Bids
        json += "\"bids\": [";
        int bidIdx = 0;
        for(int i = 0; i < ArraySize(book) && bidIdx < 10; i++)
        {
            if(book[i].type == BOOK_TYPE_BUY)
            {
                if(bidIdx > 0) json += ",";
                json += "{\"price\": " + DoubleToString(book[i].price, digits) + ",";
                json += "\"volume\": " + IntegerToString(book[i].volume) + "}";
                totalBidVolume += book[i].volume;
                bidIdx++;
            }
        }
        json += "],";
        
        // Asks
        json += "\"asks\": [";
        int askIdx = 0;
        for(int i = 0; i < ArraySize(book) && askIdx < 10; i++)
        {
            if(book[i].type == BOOK_TYPE_SELL)
            {
                if(askIdx > 0) json += ",";
                json += "{\"price\": " + DoubleToString(book[i].price, digits) + ",";
                json += "\"volume\": " + IntegerToString(book[i].volume) + "}";
                totalAskVolume += book[i].volume;
                askIdx++;
            }
        }
        json += "],";
        
        // Summary
        double imbalance = 0;
        if(totalBidVolume + totalAskVolume > 0)
            imbalance = (double)(totalBidVolume - totalAskVolume) / (double)(totalBidVolume + totalAskVolume);
            
        json += "\"imbalance\": " + DoubleToString(imbalance, 4);
    }
    else
    {
        json += "\"bids\": [],\"asks\": [],\"imbalance\": 0.0";
    }
    
    json += "}";
    return json;
}

//+------------------------------------------------------------------+
//| Test API connection                                               |
//+------------------------------------------------------------------+
bool TestAPIConnection()
{
    char post[], result[];
    string headers = "Content-Type: application/json\r\n";
    string testData = "{\"test\": true}";

    StringToCharArray(testData, post, 0, StringLen(testData));

    int res = WebRequest("POST", API_URL, headers, 3000, post, result, headers);

    return (res != -1);
}

//+------------------------------------------------------------------+
//| Get daily start balance (resets at midnight)                      |
//+------------------------------------------------------------------+
double GetDailyStartBalance()
{
    datetime current_time = TimeCurrent();
    MqlDateTime dt;
    TimeToStruct(current_time, dt);
    
    // Check if it's a new day
    datetime current_day = StringToTime(StringFormat("%04d.%02d.%02d 00:00:00", dt.year, dt.mon, dt.day));
    
    if(current_day != g_last_cest_day)
    {
        // New day - store current balance as start
        g_daily_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
        g_last_cest_day = current_day;
        Print("🌅 New trading day - Start balance: $", DoubleToString(g_daily_start_balance, 2));
    }
    
    // If not initialized yet, use current balance
    if(g_daily_start_balance == 0.0)
    {
        g_daily_start_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    }
    
    return g_daily_start_balance;
}

//+------------------------------------------------------------------+
//| Get today's total P&L (equity - start balance)                   |
//+------------------------------------------------------------------+
double GetDailyPnL()
{
    double start_balance = GetDailyStartBalance();
    double current_equity = AccountInfoDouble(ACCOUNT_EQUITY);
    return current_equity - start_balance;
}

//+------------------------------------------------------------------+
//| Get realized P&L from closed trades today                        |
//+------------------------------------------------------------------+
double GetDailyRealizedPnL()
{
    double realized_pnl = 0.0;
    
    // Get today's start time (midnight)
    MqlDateTime dt;
    TimeCurrent(dt);
    dt.hour = 0;
    dt.min = 0;
    dt.sec = 0;
    datetime today_start = StructToTime(dt);
    
    // Select history from today
    if(HistorySelect(today_start, TimeCurrent()))
    {
        int total_deals = HistoryDealsTotal();
        for(int i = 0; i < total_deals; i++)
        {
            ulong ticket = HistoryDealGetTicket(i);
            if(ticket > 0)
            {
                // Only count exit deals (DEAL_ENTRY_OUT or DEAL_ENTRY_INOUT)
                ENUM_DEAL_ENTRY entry_type = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
                if(entry_type == DEAL_ENTRY_OUT || entry_type == DEAL_ENTRY_INOUT)
                {
                    double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
                    double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
                    double swap = HistoryDealGetDouble(ticket, DEAL_SWAP);
                    realized_pnl += profit + commission + swap;
                }
            }
        }
    }
    
    return realized_pnl;
}

//+------------------------------------------------------------------+
//| Get peak balance (highest balance ever achieved)                 |
//+------------------------------------------------------------------+
double GetPeakBalance()
{
    double current_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    
    // Initialize if needed
    if(g_peak_balance == 0.0)
    {
        g_peak_balance = current_balance;
    }
    
    // Update if new peak
    if(current_balance > g_peak_balance)
    {
        g_peak_balance = current_balance;
        Print("🏆 New peak balance: $", DoubleToString(g_peak_balance, 2));
    }
    
    return g_peak_balance;
}

//+------------------------------------------------------------------+
//| Execute Scale In - Add lots to existing position                 |
//+------------------------------------------------------------------+
void ExecuteScaleIn(string symbol, double lots, double stopLoss = 0)
{
    Print("🚨 SCALE_IN: Adding ", DoubleToString(lots, 2), " lots to ", symbol, " SL: ", stopLoss);
    
    // Find existing position for this symbol
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol)
            {
                // Get position direction
                ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
                
                // Get current price
                double current_price = (pos_type == POSITION_TYPE_BUY) ? 
                    SymbolInfoDouble(symbol, SYMBOL_ASK) : 
                    SymbolInfoDouble(symbol, SYMBOL_BID);
                
                // If no stop loss provided, use existing position's SL
                if(stopLoss == 0)
                {
                    stopLoss = PositionGetDouble(POSITION_SL);
                    Print("   Using existing position SL: ", stopLoss);
                }
                
                // Open additional position in same direction WITH stop loss
                trade.SetExpertMagicNumber(MagicNumber);
                
                bool result = false;
                if(pos_type == POSITION_TYPE_BUY)
                {
                    result = trade.Buy(lots, symbol, current_price, stopLoss, 0, "AI Scale In");
                }
                else
                {
                    result = trade.Sell(lots, symbol, current_price, stopLoss, 0, "AI Scale In");
                }
                
                if(result)
                {
                    Print("✅ Successfully added ", DoubleToString(lots, 2), " lots to ", symbol, " with SL: ", stopLoss);
                }
                else
                {
                    Print("❌ Failed to add lots to ", symbol, " - Error: ", GetLastError());
                }
                
                return;
            }
        }
    }
    
    Print("⚠️ No existing position found for ", symbol, " - cannot scale in");
}

//+------------------------------------------------------------------+
//| Execute Scale Out - Reduce lots from existing position           |
//+------------------------------------------------------------------+
void ExecuteScaleOut(string symbol, double lots)
{
    Print("💰 SCALE_OUT: Reducing ", DoubleToString(lots, 2), " lots from ", symbol);
    
    // Find existing position for this symbol
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol)
            {
                ulong ticket = PositionGetTicket(i);
                double current_volume = PositionGetDouble(POSITION_VOLUME);
                
                // Don't close more than we have
                double close_volume = MathMin(lots, current_volume);
                
                trade.SetExpertMagicNumber(MagicNumber);
                
                bool result = trade.PositionClosePartial(ticket, close_volume);
                
                if(result)
                {
                    Print("✅ Successfully reduced ", DoubleToString(close_volume, 2), " lots from ", symbol);
                }
                else
                {
                    Print("❌ Failed to reduce lots from ", symbol, " - Error: ", GetLastError());
                }
                
                return;
            }
        }
    }
    
    Print("⚠️ No existing position found for ", symbol, " - cannot scale out");
}

//+------------------------------------------------------------------+
//| Close Position - Close entire position for symbol                |
//+------------------------------------------------------------------+
void ClosePosition(string symbol)
{
    Print("❌ CLOSE: Closing position on ", symbol);
    
    // Find and close position for this symbol
    for(int i = PositionsTotal() - 1; i >= 0; i--)
    {
        if(PositionSelectByTicket(PositionGetTicket(i)))
        {
            if(PositionGetString(POSITION_SYMBOL) == symbol)
            {
                ulong ticket = PositionGetTicket(i);
                
                trade.SetExpertMagicNumber(MagicNumber);
                
                bool result = trade.PositionClose(ticket);
                
                if(result)
                {
                    Print("✅ Successfully closed position on ", symbol);
                }
                else
                {
                    Print("❌ Failed to close position on ", symbol, " - Error: ", GetLastError());
                }
                
                return;
            }
        }
    }
    
    Print("⚠️ No existing position found for ", symbol, " - cannot close");
}

//+------------------------------------------------------------------+
//| Get upcoming economic calendar events (high/medium impact)       |
//+------------------------------------------------------------------+
string GetCalendarEvents(string symbol)
{
    string json = "[";
    
    // Determine relevant currencies based on symbol
    string currencies[];
    int numCurrencies = 0;
    
    // Extract base symbol without suffix
    string baseSymbol = symbol;
    int dotPos = StringFind(symbol, ".");
    if(dotPos > 0) baseSymbol = StringSubstr(symbol, 0, dotPos);
    StringToUpper(baseSymbol);
    
    // Map symbols to currencies
    if(StringFind(baseSymbol, "EUR") >= 0) { ArrayResize(currencies, numCurrencies + 1); currencies[numCurrencies++] = "EUR"; }
    if(StringFind(baseSymbol, "USD") >= 0 || StringFind(baseSymbol, "US30") >= 0 || 
       StringFind(baseSymbol, "US100") >= 0 || StringFind(baseSymbol, "US500") >= 0 ||
       StringFind(baseSymbol, "USOIL") >= 0) { ArrayResize(currencies, numCurrencies + 1); currencies[numCurrencies++] = "USD"; }
    if(StringFind(baseSymbol, "GBP") >= 0) { ArrayResize(currencies, numCurrencies + 1); currencies[numCurrencies++] = "GBP"; }
    if(StringFind(baseSymbol, "JPY") >= 0) { ArrayResize(currencies, numCurrencies + 1); currencies[numCurrencies++] = "JPY"; }
    if(StringFind(baseSymbol, "XAU") >= 0) { ArrayResize(currencies, numCurrencies + 1); currencies[numCurrencies++] = "USD"; }  // Gold affected by USD
    
    // Get events for next 4 hours
    datetime fromTime = TimeCurrent();
    datetime toTime = fromTime + 4 * 3600;  // 4 hours ahead
    
    int eventCount = 0;
    
    for(int c = 0; c < numCurrencies && eventCount < 10; c++)
    {
        MqlCalendarValue values[];
        
        // Get calendar events for this currency
        if(CalendarValueHistory(values, fromTime, toTime, NULL, currencies[c]))
        {
            for(int i = 0; i < ArraySize(values) && eventCount < 10; i++)
            {
                MqlCalendarEvent event;
                if(CalendarEventById(values[i].event_id, event))
                {
                    // Only include HIGH and MEDIUM importance events
                    if(event.importance == CALENDAR_IMPORTANCE_HIGH || 
                       event.importance == CALENDAR_IMPORTANCE_MODERATE)
                    {
                        if(eventCount > 0) json += ",";
                        
                        // Calculate minutes until event
                        int minutesUntil = (int)((values[i].time - TimeCurrent()) / 60);
                        
                        json += "{";
                        json += "\"currency\": \"" + currencies[c] + "\",";
                        json += "\"event\": \"" + event.name + "\",";
                        json += "\"importance\": \"" + (event.importance == CALENDAR_IMPORTANCE_HIGH ? "HIGH" : "MEDIUM") + "\",";
                        json += "\"time\": " + IntegerToString(values[i].time) + ",";
                        json += "\"minutes_until\": " + IntegerToString(minutesUntil);
                        json += "}";
                        
                        eventCount++;
                    }
                }
            }
        }
    }
    
    json += "]";
    return json;
}

//+------------------------------------------------------------------+
//| FTMO Tracking Functions - CRITICAL for compliance                |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Update FTMO tracking variables                                    |
//| Called before each API request to ensure accurate data           |
//+------------------------------------------------------------------+
void UpdateFTMOTracking()
{
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    
    // ALWAYS use input parameter for initial balance (persists across restarts)
    g_initial_balance = FTMO_InitialBalance;
    
    // Initialize daily tracking if first time
    if(g_daily_start_balance == 0.0)
    {
        g_peak_balance = MathMax(balance, g_initial_balance);
        g_daily_start_balance = balance;
        g_daily_realized_pnl = 0.0;
    }
    
    // Update peak balance (highest ever)
    if(balance > g_peak_balance)
    {
        g_peak_balance = balance;
    }
    
    // ═══════════════════════════════════════════════════════════════════
    // CHECK FOR CE(S)T DAY CHANGE - Daily loss resets at midnight CE(S)T
    // 
    // CE(S)T = Central European (Summer) Time
    // CET = UTC+1 (winter), CEST = UTC+2 (summer)
    // 
    // For EST (UTC-5): Midnight CET = 6 PM EST (winter) / 6 PM EDT (summer)
    // For your local time: Use FTMO timezone converter
    // ═══════════════════════════════════════════════════════════════════
    
    datetime currentTime = TimeCurrent();  // Broker server time
    
    // Get current CE(S)T day
    // Assuming broker is on CET/CEST (common for FTMO brokers)
    // If broker is on different timezone, adjust accordingly
    MqlDateTime dt;
    TimeToStruct(currentTime, dt);
    
    // Create a date-only value for comparison (ignore time)
    datetime currentCESTDay = StringToTime(IntegerToString(dt.year) + "." + 
                                            IntegerToString(dt.mon) + "." + 
                                            IntegerToString(dt.day));
    
    // Check if we've crossed midnight CE(S)T
    if(g_last_cest_day == 0)
    {
        // First time - initialize
        g_last_cest_day = currentCESTDay;
    }
    else if(currentCESTDay != g_last_cest_day)
    {
        // NEW DAY - Reset daily tracking
        Print("═══════════════════════════════════════════════════════════════════");
        Print("🔄 FTMO DAILY RESET - Midnight CE(S)T crossed");
        Print("   Previous day start balance: $", DoubleToString(g_daily_start_balance, 2));
        Print("   Previous day realized P&L: $", DoubleToString(g_daily_realized_pnl, 2));
        Print("   New day start balance: $", DoubleToString(balance, 2));
        Print("═══════════════════════════════════════════════════════════════════");
        
        g_last_cest_day = currentCESTDay;
        g_daily_start_balance = balance;
        g_daily_realized_pnl = 0.0;
    }
}

//+------------------------------------------------------------------+
//| Track realized P&L when trade closes                              |
//| Call this from OnTradeTransaction when a position closes          |
//+------------------------------------------------------------------+
void TrackRealizedPnL(double profit)
{
    g_daily_realized_pnl += profit;
    Print("📊 Trade closed: P&L $", DoubleToString(profit, 2), 
          " | Daily realized: $", DoubleToString(g_daily_realized_pnl, 2));
}

//+------------------------------------------------------------------+
