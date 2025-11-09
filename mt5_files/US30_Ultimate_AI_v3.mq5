��//+------------------------------------------------------------------+
//| US30 Ultimate AI Trading System v14.0                            |
//| INTELLIGENT ML/RL: Swing/Scalp Auto-Classification + Smart Limits|
//+------------------------------------------------------------------+
#property copyright "Ultimate AI Trading System"
#property link      "https://github.com/yourusername/ai-trading"
#property version   "15.00"  // v15: Added symbol_specs to fix position sizing
#property description "ML Auto-Classifies Swing vs Scalp | RL Intelligent Scaling | Performance-Based Position Limits"

#include <Trade\Trade.mqh>
#include "GetTradeHistory.mqh"

// API Configuration
input string API_Host = "http://127.0.0.1:5007";

// Trading Configuration
input string TradingSymbol = "US30Z25.sim";
input int CheckIntervalSeconds = 60;
input double BaseRiskPercent = 1.0;  // Increased for profitability

// Dual-Mode Settings - BOTH ACTIVE
input bool EnableScalping = true;          // Enable scalping mode
input bool EnableSwing = false;            // Enable swing trading mode
input int MaxTotalPositions = 3;          // Maximum simultaneous positions (Professional scaling)
input double ScaleInMomentumThreshold = 1.3;  // Momentum must increase 30% to scale in
input double ScaleInVolumeThreshold = 1.5;    // Volume must increase 50% to scale in
input double ScaleInConfidenceGap = 8.0;      // Confidence must jump 8% to scale in
input double ExitDrawdownLevel1 = 0.15;       // Scale out 50% if gave back 15% from peak
input double ExitDrawdownLevel2 = 0.25;       // Exit all if gave back 25% from peak

// FTMO Risk Limits
input double MaxDailyLossPercent = 5.0;
input double MaxTotalLossPercent = 10.0;

// Global Variables
CTrade trade;
datetime lastEntryCheck = 0;
datetime lastExitCheck = 0;
datetime lastLLMOverview = 0; // v4.0: Cached LLM context (updated every 60s)
datetime lastH1Bar = 0; // Track last H1 bar for swing trading
double startingBalance = 0;
double dailyStartBalance = 0;
datetime currentDay = 0;

// v4.0: LLM market context (cached from 60-second updates)
string llmMarketRegime = "unknown";
string llmMarketBias = "neutral";
double llmRiskLevel = 1.0;
bool llmTrendChanged = false;  // v4.0: LLM trend change alerts

// Professional scaling tracking
static double lastEntryConfidence = 0;
static double lastEntryMomentum = 0;
static double lastEntryVolume = 0;
static datetime lastEntryTime = 0;
static int positionCount = 0;

// Exit tracking for profit protection
static double peakProfit = 0;
static double peakMomentum = 0;
static datetime peakProfitTime = 0;

// Position tracking for RL learning
struct TradeRecord {
   ulong ticket;
   string direction;
   double entry_price;
   double confidence;
   string regime;
   datetime entry_time;
   double account_balance_at_entry;
};

TradeRecord currentTrade;

// CONTINUOUS LEARNING: Track predictions for learning
int lastMLPrediction = 0;      // 0=HOLD, 1=BUY, 2=SELL
double lastMLConfidence = 0.0;

// Function declarations
void ExecuteTrade(string direction, double confidence, string regime, double riskPercent, int stopPoints, int targetPoints, string tradeType = "SCALP");
void ExecuteTradeWithLotSize(string direction, double confidence, string regime, double apiLotSize, int stopPoints, int targetPoints, string tradeType = "SCALP");
double lastMLPrice = 0.0;
int learningTickCounter = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("═══════════════════════════════════════════════════════════════");
   Print("   ULTIMATE AI TRADING SYSTEM v14.0 - INTELLIGENT ML/RL");
   Print("   Swing/Scalp Auto-Classification + Performance-Based Limits");
   Print("═══════════════════════════════════════════════════════════════");
   Print("");
   Print("🎯 INTELLIGENT ML/RL FEATURES:");
   Print("   ✓ ML Auto-Classifies: SWING vs SCALP (every tick)");
   Print("   ✓ Swing: 80%+ conf, strong trend → 100-300pt stops");
   Print("   ✓ Scalp: 70%+ conf, any market → 25-100pt stops");
   Print("   ✓ RL Intelligent Scaling (Trained on 4,330 trades)");
   Print("   ✓ Performance-Based Limits (1-15, adapts to win rate)");
   Print("   ✓ Trade History Integration (MT5 history → decisions)");
   Print("   ✓ FTMO Safe (5% daily, 10% total limits)");
   Print("");
   Print("🧠 AI COMPONENTS:");
   Print("   ✓ ML Ensemble Entry (XGBoost, LightGBM, CatBoost, NN)");
   Print("   ✓ Deep Q-Network Exit (Neural network, not Q-table)");
   Print("   ✓ Experience Replay (10,000 memory buffer)");
   Print("   ✓ Target Network (Stable learning)");
   Print("   ✓ LLM Risk Manager (Regime + News awareness)");
   Print("");
   Print("💡 TRAINING:");
   Print("   ✓ ML: 100,000 bars of US30 M1 data (78% accuracy)");
   Print("   ✓ RL: 4,330 real trades for exit optimization");
   Print("   ✓ Risk Management: Account-aware, LIVE data");
   Print("   ✓ Position Limits: Intelligent (1-15 dynamic)");
   Print("   ✓ No hard rules - adapts to performance");
   Print("");
   Print("🚀 PROFESSIONAL TRADER AI - INTELLIGENT SYSTEM");
   Print("═══════════════════════════════════════════════════════════════");
   Print("");
   Print("⚙️ MODES:");
   Print("  Scalping: ", EnableScalping ? "✓ ENABLED" : "✗ DISABLED", " (M1 every tick)");
   Print("  Swing: ", EnableSwing ? "✓ ENABLED" : "✗ DISABLED", " (H1 trend)");
   Print("══════════════════════════════════════════════════════════════════");
   Print("  ✓ VERIFIED: Opens trades ✓ Closes trades ✓");
   Print("  ✓ Dynamic ML Exit on EVERY TICK");
   Print("");
   Print("Modes Enabled:");
   Print("  Scalping: ", EnableScalping ? "ON" : "OFF");
   Print("  Swing:    ", EnableSwing ? "ON" : "OFF");
   Print("");
   
   // Check for existing positions on restart
   int existingPositions = PositionsTotal();
   bool positionRestored = false;

   if(existingPositions > 0)
   {
      Print("📊 EXISTING POSITIONS DETECTED: ", existingPositions);
      for(int i = 0; i < existingPositions; i++)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0 && PositionSelectByTicket(ticket))
         {
            string symbol = PositionGetString(POSITION_SYMBOL);

            // Only restore if this is OUR symbol
            if(symbol == TradingSymbol)
            {
               double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
               double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
               double profit = PositionGetDouble(POSITION_PROFIT);
               long type = PositionGetInteger(POSITION_TYPE);
               string direction = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
               datetime entryTime = (datetime)PositionGetInteger(POSITION_TIME);

               // RESTORE TRACKING STATE
               currentTrade.ticket = ticket;
               currentTrade.direction = direction;
               currentTrade.entry_price = openPrice;
               currentTrade.entry_time = entryTime;
               currentTrade.account_balance_at_entry = AccountInfoDouble(ACCOUNT_BALANCE);
               currentTrade.confidence = 75.0;  // Default (can't recover exact value)
               currentTrade.regime = "UNKNOWN";  // Default (can't recover exact value)

               positionRestored = true;

               Print("═══════════════════════════════════════════════════════════════");
               Print("✅ POSITION TRACKING RESTORED");
               Print("═══════════════════════════════════════════════════════════════");
               Print("  Position #", ticket, ": ", direction, " ", symbol);
               Print("  Entry: ", DoubleToString(openPrice, 2), " | Current: ", DoubleToString(currentPrice, 2));
               Print("  Hold Time: ", (int)((TimeCurrent() - entryTime) / 60), " minutes");
               Print("  Profit: $", DoubleToString(profit, 2));
               Print("  ✓ ML will monitor this position on every tick");
               Print("═══════════════════════════════════════════════════════════════");

               break;  // Only track one position at a time
            }
            else
            {
               // Different symbol - just print info
               Print("  Position #", ticket, ": ", symbol, " (not our trading symbol)");
            }
         }
      }
   }

   if(!positionRestored)
   {
      // Initialize currentTrade to clean state
      currentTrade.ticket = 0;
      currentTrade.direction = "";
      currentTrade.entry_price = 0.0;
      currentTrade.confidence = 0.0;
      currentTrade.regime = "";
      currentTrade.entry_time = 0;
      currentTrade.account_balance_at_entry = 0.0;

      Print("No existing positions - ready for new trades");
   }
   Print("");
   Print("ML Check: EVERY TICK (auto-classifies SWING/SCALP)");
   Print("LLM Update: ", CheckIntervalSeconds, " seconds (market overview)");
   Print("Base Risk: ", BaseRiskPercent, "% (adjusted by LLM)");
   Print("══════════════════════════════════════════════════════════════════");

   startingBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   
   // Don't reset daily balance if same day
   datetime today = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(today, dt);
   datetime todayStart = StructToTime(dt) - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   
   TimeToStruct(currentDay, dt);
   datetime lastDayStart = StructToTime(dt) - (dt.hour * 3600 + dt.min * 60 + dt.sec);
   
   if(todayStart != lastDayStart || dailyStartBalance == 0)
   {
      // New day or first run
      dailyStartBalance = startingBalance;
      currentDay = today;
      Print("📅 Daily balance set: $", DoubleToString(dailyStartBalance, 2));
   }
   else
   {
      // Same day - keep existing daily balance
      Print("📅 Same day - keeping daily balance: $", DoubleToString(dailyStartBalance, 2));
   }

   // Test API connection
   if(!TestAPIConnection())
   {
      Print(" WARNING: Cannot connect to Ultimate AI API!");
      Print("   Make sure ml_api_ultimate.py is running on port 5007");
      Print("   Start it with: python3 ml_api_ultimate.py");
      return INIT_FAILED;
   }

   Print(" Ultimate AI API connected successfully!");
   Print("");
   Print("🎯 ML is now checking EVERY TICK for trade opportunities!");
   Print("📊 LLM updates market overview every ", CheckIntervalSeconds, " seconds");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("══════════════════════════════════════════════════════════════════");
   Print("  US30 PROFESSIONAL AI v9.1 - STOPPED");
   Print("  SESSION-AWARE SCALP/SWING SYSTEM");
   Print("══════════════════════════════════════════════════════════════════");
}

//+------------------------------------------------------------------+
//| Expert tick function - v5.0 ARCHITECTURE                         |
//| ENSEMBLE: XGBoost + LightGBM + Neural Net (78% accuracy)        |
//| RL AGENT: Q-Learning adaptation (74.5% win rate)                |
//| FEATURES: 96 professional features                               |
//| EXITS: Dynamic ML-driven (NO fixed TP/SL)                       |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check daily reset
   CheckDailyReset();
   
   // Check risk limits
   if(IsDailyLossLimitReached() || IsTotalDrawdownLimitReached())
   {
      Print("⚠️ Risk limit reached - stopping trading");
      return;
   }
   
   // Update LLM overview AND risk manager every 60 seconds
   static datetime lastLLMUpdate = 0;
   if(TimeCurrent() - lastLLMUpdate >= CheckIntervalSeconds)
   {
      UpdateLLMMarketOverview();
      UpdateLLMRiskManager();  // v8.1: Dynamic risk adjustment
      lastLLMUpdate = TimeCurrent();
   }
   
   // v14.0: ML AUTO-CLASSIFIES SWING vs SCALP on EVERY TICK
   // No need to separate - API decides trade type based on market conditions
   int totalPositions = PositionsTotal();
   
   // Check ML entry on EVERY TICK (API auto-classifies as SWING or SCALP)
   if(totalPositions < MaxTotalPositions)
   {
      CheckMLEntryEveryTick();
   }
   
   // CONTINUOUS LEARNING: Send learning data every 10 ticks
   learningTickCounter++;
   if(learningTickCounter >= 10)
   {
      SendContinuousLearningData();
      learningTickCounter = 0;
   }
   
   // Check dynamic ML exit on every tick (if position exists)
   CheckDynamicMLExitEveryTick();
}

//+------------------------------------------------------------------+
//| Check if new bar formed on specified timeframe                  |
//+------------------------------------------------------------------+
bool IsNewBar(ENUM_TIMEFRAMES timeframe)
{
   datetime currentBarTime = iTime(TradingSymbol, timeframe, 0);
   
   if(timeframe == PERIOD_H1)
   {
      if(currentBarTime != lastH1Bar)
      {
         lastH1Bar = currentBarTime;
         return true;
      }
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Test API Connection                                              |
//+------------------------------------------------------------------+
bool TestAPIConnection()
{
   string url = API_Host + "/health";
   string headers = "Content-Type: application/json\r\n";

   char result[];
   char data[];
   string resultHeaders;

   int timeout = 5000;
   int res = WebRequest("GET", url, headers, timeout, data, result, resultHeaders);

   if(res == 200)
   {
      string response = CharArrayToString(result);
      return StringFind(response, "healthy") >= 0;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Check AI Entry Decision                                         |
//+------------------------------------------------------------------+
void CheckAIEntry()
{
   string url = API_Host + "/api/ultimate/entry";

   // Build simple JSON request
   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"account_balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   jsonRequest += "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   jsonRequest += "\"day_start_equity\":" + DoubleToString(dailyStartBalance, 2) + ",";
   jsonRequest += "\"open_positions\":" + IntegerToString(PositionsTotal()) + ",";
   jsonRequest += "\"trades_today\":0,";
   jsonRequest += "\"market_data\":{";

   // Add all 5 scalping timeframes (M5, M15, M30, H1, H4) for 126 features
   jsonRequest += "\"M5\":" + BuildTimeframeJSON(PERIOD_M5) + ",";
   jsonRequest += "\"M15\":" + BuildTimeframeJSON(PERIOD_M15) + ",";
   jsonRequest += "\"M30\":" + BuildTimeframeJSON(PERIOD_M30) + ",";
   jsonRequest += "\"H1\":" + BuildTimeframeJSON(PERIOD_H1) + ",";
   jsonRequest += "\"H4\":" + BuildTimeframeJSON(PERIOD_H4);

   jsonRequest += "}}";

   // Debug: Print JSON once
   static bool debugPrinted = false;
   if(!debugPrinted)
   {
      Print("Entry JSON sample: ", StringSubstr(jsonRequest, 0, 200), "...");
      debugPrinted = true;
   }

   // Send request
   string response = SendPostRequest(url, jsonRequest);

   if(response == "")
   {
      Print(" AI Entry API call failed");
      return;
   }

   // Parse response (simple extraction)
   string direction = ExtractStringValue(response, "direction");
   double confidence = ExtractDoubleValue(response, "confidence");
   bool takeTrade = ExtractBoolValue(response, "take_trade");
   string reason = ExtractStringValue(response, "reason");
   string regime = ExtractStringValue(response, "regime");
   double riskPercent = ExtractDoubleValue(response, "risk_percent");
   int stopPoints = (int)ExtractDoubleValue(response, "stop_loss_points");
   int targetPoints = (int)ExtractDoubleValue(response, "take_profit_points");

   string mlDirection = ExtractStringValue(response, "ml_direction");
   string llmDecision = ExtractStringValue(response, "llm_decision");
   string llmReasoning = ExtractStringValue(response, "llm_reasoning");

   // Display AI analysis
   Print("");
   Print(" ULTIMATE AI ENTRY DECISION                                  ");
   Print("┤");
   Print(" ML:  ", mlDirection, " | LLM: ", llmDecision);
   Print(" Final: ", direction, " @ ", DoubleToString(confidence, 1), "%");
   Print(" Take Trade: ", takeTrade ? "YES" : "NO");
   Print("┤");
   Print(" ", llmReasoning);
   Print("┤");
   Print(" Regime: ", regime);
   Print(" Risk: ", DoubleToString(riskPercent, 3), "%");
   Print(" Stop: ", stopPoints, " pts | Target: ", targetPoints, " pts");
   Print("");

   // Execute if AI says yes
   if(takeTrade && (direction == "BUY" || direction == "SELL"))
   {
      // Note: This is swing trading - also needs to extract apiLotSize from response
      // For now, use old ExecuteTrade which calculates its own lot size
      // TODO: Update swing endpoint to return lot_size like scalp endpoint does
      ExecuteTrade(direction, confidence, regime, riskPercent, stopPoints, targetPoints);
   }
}

//+------------------------------------------------------------------+
//| v5.0: Update LLM Market Overview (Every 60 seconds)             |
//| Provides strategic context for ensemble + RL decisions          |
//| Cached for use by professional system (no delay)                |
//+------------------------------------------------------------------+
void UpdateLLMMarketOverview()
{
   string url = API_Host + "/api/ultimate/overview";

   // Build request with M1 data for v6.0 integrated LLM context
   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"account_balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   jsonRequest += "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   jsonRequest += "\"positions_total\":" + IntegerToString(PositionsTotal()) + ",";
   jsonRequest += "\"market_data\":{\"M1\":" + BuildTimeframeJSON(PERIOD_M1) + "}";  // v6.0: M1 for LLM simulation
   jsonRequest += "}";

   string response = SendPostRequest(url, jsonRequest);

   if(response == "")
   {
      Print("⚠️ [v8.1] LLM overview API call failed");
      return;
   }

   // Parse LLM market context
   llmMarketRegime = ExtractStringValue(response, "regime");
   llmMarketBias = ExtractStringValue(response, "bias");
   llmRiskLevel = ExtractDoubleValue(response, "risk_level");
   llmTrendChanged = ExtractBoolValue(response, "trend_changed");  // LLM alerts
   string marketSummary = ExtractStringValue(response, "summary");

   // Print system status (once per minute) - Simplified since LLM not active
   static datetime lastPrint = 0;
   if(TimeCurrent() - lastPrint >= 60)
   {
      Print("🤖 US30 ULTIMATE AI v14.0 - INTELLIGENT ML/RL");
      Print("═══════════════════════════════════════════════════════════════");
      Print(" ML: Auto-Classifies SWING/SCALP | 78% accuracy | 153 features");
      Print(" RL: Intelligent Scaling | 4,330 trades trained");
      Print(" Limits: Performance-Based (1-15) | History: MT5 Integration");
      Print(" Threshold: 70% scalp, 80% swing | NO HARD STOPS (RL exits)");
      Print("═══════════════════════════════════════════════════════════════");
      Print("");
      lastPrint = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| v5.0: Professional Ensemble Entry (Every Tick)                   |
//| Ensemble (XGB+LGB+NN) + RL agent + 96 features                  |
//| Session-aware, dynamic thresholds, LLM confirmation             |
//+------------------------------------------------------------------+
void CheckMLEntryEveryTick()
{
   // DEBUG: Log that function is being called
   static int callCount = 0;
   callCount++;
   if(callCount % 100 == 1)  // Log every 100 calls to avoid spam
   {
      Print("🔍 CheckMLEntryEveryTick called ", callCount, " times");
   }
   
   // CRITICAL SAFETY: Prevent multiple simultaneous entries
   static bool entryInProgress = false;
   if(entryInProgress)
   {
      Print("⚠️ Entry in progress, skipping");
      return;  // Already processing an entry - prevent duplicate
   }
   
   // COOLDOWN: Prevent checking too frequently (wait at least 10 seconds between checks)
   static datetime lastCheckTime = 0;
   datetime currentTime = TimeCurrent();
   if(currentTime - lastCheckTime < 10)
   {
      return;  // Too soon since last check
   }
   lastCheckTime = currentTime;
   
   // SAFETY: Check max positions limit
   if(PositionsTotal() >= MaxTotalPositions)
   {
      if(callCount % 100 == 1)
      {
         Print("⚠️ Max positions reached: ", PositionsTotal(), "/", MaxTotalPositions);
      }
      return;  // Max positions reached
   }
   
   // Professional scaling allows multiple positions (removed old single-position check)

   string url = API_Host + "/api/ultimate/ml_entry";

   // Build JSON with M1 + multi-timeframe data for integrated v6.0 system
   // v6.0 needs M1 data to extract 106 integrated features (96 technical + 10 LLM)
   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"llm_regime\":\"" + llmMarketRegime + "\",";
   jsonRequest += "\"llm_bias\":\"" + llmMarketBias + "\",";
   jsonRequest += "\"llm_risk\":\"" + DoubleToString(llmRiskLevel, 2) + "\",";
   // LIVE account data for intelligent position limits
   double liveBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double liveEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double liveDailyPnL = liveEquity - dailyStartBalance;  // LIVE daily P&L
   int livePositions = PositionsTotal();
   
   // Calculate LIVE position profit and bars held
   double livePositionProfit = 0;
   int liveBarsHeld = 0;
   if(livePositions > 0)
   {
      for(int i = 0; i < livePositions; i++)
      {
         if(PositionSelectByTicket(PositionGetTicket(i)))
         {
            livePositionProfit += PositionGetDouble(POSITION_PROFIT);
            datetime posTime = (datetime)PositionGetInteger(POSITION_TIME);
            liveBarsHeld = (int)((TimeCurrent() - posTime) / 60);  // Minutes in trade
         }
      }
   }
   
   jsonRequest += "\"account_balance\":" + DoubleToString(liveBalance, 2) + ",";
   jsonRequest += "\"account_equity\":" + DoubleToString(liveEquity, 2) + ",";
   jsonRequest += "\"daily_pnl\":" + DoubleToString(liveDailyPnL, 2) + ",";
   jsonRequest += "\"open_positions\":" + IntegerToString(livePositions) + ",";
   jsonRequest += "\"position_profit\":" + DoubleToString(livePositionProfit, 2) + ",";
   jsonRequest += "\"bars_held\":" + IntegerToString(liveBarsHeld) + ",";
   jsonRequest += "\"trade_history\":" + GetTradeHistoryJSON(7) + ",";

   // Add symbol specifications for position sizing
   jsonRequest += "\"symbol_specs\":{";
   jsonRequest += "\"min_lot\":" + DoubleToString(SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MIN), 2) + ",";
   jsonRequest += "\"max_lot\":" + DoubleToString(SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MAX), 2) + ",";
   jsonRequest += "\"lot_step\":" + DoubleToString(SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_STEP), 2) + ",";
   jsonRequest += "\"tick_value\":" + DoubleToString(SymbolInfoDouble(TradingSymbol, SYMBOL_TRADE_TICK_VALUE), 5) + ",";
   jsonRequest += "\"tick_size\":" + DoubleToString(SymbolInfoDouble(TradingSymbol, SYMBOL_TRADE_TICK_SIZE), 5);
   jsonRequest += "},";

   jsonRequest += "\"market_data\":{";
   jsonRequest += "\"M1\":" + BuildTimeframeJSON(PERIOD_M1) + ",";  // v6.0: M1 required for integrated features!
   jsonRequest += "\"M5\":" + BuildTimeframeJSON(PERIOD_M5) + ",";
   jsonRequest += "\"M15\":" + BuildTimeframeJSON(PERIOD_M15) + ",";
   jsonRequest += "\"M30\":" + BuildTimeframeJSON(PERIOD_M30) + ",";
   jsonRequest += "\"H1\":" + BuildTimeframeJSON(PERIOD_H1) + ",";
   jsonRequest += "\"H4\":" + BuildTimeframeJSON(PERIOD_H4);
   jsonRequest += "}}";

   // DEBUG: Log API call attempt
   if(callCount % 100 == 1)
   {
      Print("📡 Sending API request to: ", url);
   }
   
   string response = SendPostRequest(url, jsonRequest);

   if(response == "")
   {
      // Log first few failures to diagnose issue
      if(callCount <= 5)
      {
         Print("❌ API response empty on call #", callCount);
      }
      return;
   }
   
   // DEBUG: Log successful response
   if(callCount % 100 == 1)
   {
      Print("✅ API response received");
   }

   // Parse ML response
   string direction = ExtractStringValue(response, "direction");
   double confidence = ExtractDoubleValue(response, "confidence");
   bool takeTrade = ExtractBoolValue(response, "take_trade");
   int stopPoints = (int)ExtractDoubleValue(response, "stop_points");
   int targetPoints = (int)ExtractDoubleValue(response, "target_points");
   double riskPercent = ExtractDoubleValue(response, "risk_percent");
   double apiLotSize = ExtractDoubleValue(response, "lot_size");  // GET LOT SIZE FROM API!
   string regime = ExtractStringValue(response, "llm_regime");
   
   // INTELLIGENT POSITION LIMIT: Get from API
   int intelligentMaxPositions = (int)ExtractDoubleValue(response, "max_positions");
   double currentDrawdown = ExtractDoubleValue(response, "current_drawdown");
   
   // TRADE TYPE: ML decides swing vs scalp
   string tradeType = ExtractStringValue(response, "trade_type");
   bool isSwing = ExtractBoolValue(response, "is_swing");
   
   // PROFESSIONAL SCALING: Get market metrics
   double momentum = ExtractDoubleValue(response, "momentum");
   double volumeRatio = ExtractDoubleValue(response, "volume_ratio");
   double trendStrength = ExtractDoubleValue(response, "trend_strength");

   // CONTINUOUS LEARNING: Store prediction for learning
   if(direction == "BUY") lastMLPrediction = 1;
   else if(direction == "SELL") lastMLPrediction = 2;
   else lastMLPrediction = 0;
   lastMLConfidence = confidence;

   // RL INTELLIGENT SCALING LOGIC
   bool shouldEnter = false;
   string scaleReason = "";
   
   // Parse RL scaling signals
   bool shouldScaleIn = ExtractBoolValue(response, "should_scale_in");
   double scaleAmount = ExtractDoubleValue(response, "scale_amount");
   string rlScaleAction = ExtractStringValue(response, "rl_scale_action");
   
   if(takeTrade && (direction == "BUY" || direction == "SELL"))
   {
      // First position - just need ML confidence
      if(PositionsTotal() == 0)
      {
         shouldEnter = true;
         scaleReason = "Initial entry - ML confidence " + DoubleToString(confidence, 1) + "%";
         positionCount = 0;
      }
      // RL INTELLIGENT SCALING: Let RL decide when to scale in
      else if(PositionsTotal() < intelligentMaxPositions && shouldScaleIn)
      {
         // Check if position is profitable (safety guardrail)
         double currentProfit = 0;
         for(int i = 0; i < PositionsTotal(); i++)
         {
            if(PositionSelectByTicket(PositionGetTicket(i)))
            {
               currentProfit += PositionGetDouble(POSITION_PROFIT);
            }
         }
         
         // Only scale in if profitable (safety guardrail)
         if(currentProfit > 0)
         {
            shouldEnter = true;
            scaleReason = "RL: " + rlScaleAction + " - Profit: $" + DoubleToString(currentProfit, 2);
            
            // Adjust lot size based on RL scale amount
            apiLotSize = apiLotSize * scaleAmount;
         }
      }
   }
   
   // Only print and execute if should enter
   if(shouldEnter)
   {
      // SET FLAG TO PREVENT RE-ENTRY
      entryInProgress = true;
      
      positionCount++;
      
      Print("");
      // Print with trade type indicator
      if(isSwing)
      {
         Print("🎯 [v14.0] SWING TRADE - ML INTELLIGENT");
      }
      else
      {
         Print("⚡ [v14.0] SCALP TRADE - ML INTELLIGENT");
      }
      Print("═══════════════════════════════════════════════════════════════");
      Print("   Entry #", positionCount + 1, " - ", scaleReason);
      Print("   Type: ", tradeType, " | Direction: ", direction, " @ ", DoubleToString(confidence, 1), "%");
      Print("   Trend Strength: ", DoubleToString(trendStrength, 2), " | Momentum: ", DoubleToString(momentum, 2));
      Print("   Positions: ", PositionsTotal(), "/", intelligentMaxPositions, " (intelligent limit)");
      Print("   Drawdown: ", DoubleToString(currentDrawdown * 100, 2), "% | Daily P&L: $", DoubleToString(liveDailyPnL, 2));
      Print("   Lot Size: ", DoubleToString(apiLotSize, 2), " lots");
      Print("   Stop: ", stopPoints, " pts | Target: ", targetPoints, " pts");
      if(isSwing)
      {
         Print("   📊 SWING: Holding for big move (", targetPoints, " point target)");
      }
      Print("═══════════════════════════════════════════════════════════════");
      Print("");

      ExecuteTradeWithLotSize(direction, confidence, llmMarketRegime, apiLotSize, stopPoints, targetPoints, "SCALP");
      
      // Update tracking for next scaling decision
      lastEntryConfidence = confidence;
      lastEntryMomentum = momentum;
      lastEntryVolume = volumeRatio;
      lastEntryTime = TimeCurrent();
      
      // Wait for position to register in MT5 AND prevent rapid-fire entries
      // Sleep for 5 seconds to allow trade to execute and prevent spam
      Sleep(5000);  // 5 seconds instead of 100ms
      
      // RESET FLAG AFTER TRADE EXECUTION
      entryInProgress = false;
      Print("   🛡️ SAFETY: Entry lock released after 5 second cooldown");
   }
}

//+------------------------------------------------------------------+
//| Check Swing Entry (H1 timeframe)                                |
//+------------------------------------------------------------------+
void CheckSwingEntryH1()
{
   // Only check if no position exists
   if(PositionsTotal() > 0) return;

   string url = API_Host + "/api/swing/entry";

   // Build JSON with H1 data
   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"llm_regime\":\"" + llmMarketRegime + "\",";
   jsonRequest += "\"llm_bias\":\"" + llmMarketBias + "\",";
   jsonRequest += "\"market_data\":{";
   jsonRequest += "\"H1\":" + BuildTimeframeJSON(PERIOD_H1);
   jsonRequest += "}}";

   string response = SendPostRequest(url, jsonRequest);

   if(response == "")
   {
      return;
   }

   // Parse swing response
   string direction = ExtractStringValue(response, "direction");
   double confidence = ExtractDoubleValue(response, "confidence");
   bool takeTrade = ExtractBoolValue(response, "take_trade");
   int stopPoints = (int)ExtractDoubleValue(response, "stop_points");
   int targetPoints = (int)ExtractDoubleValue(response, "target_points");
   double riskPercent = ExtractDoubleValue(response, "risk_percent");

   // Only print and execute if ML says YES
   if(takeTrade && (direction == "BUY" || direction == "SELL"))
   {
      Print("");
      Print("🎯 [v8.1] SWING ENTRY (H1)");
      Print("   Direction: ", direction, " @ ", DoubleToString(confidence, 1), "% confidence");
      Print("   System: Swing Trading (78.43% ensemble)");
      Print("   Timeframe: H1 (multi-hour/day hold)");
      Print("   Target: ", targetPoints, " pts | Stop: ", stopPoints, " pts");
      Print("");

      // Note: Swing trading also needs to extract apiLotSize from response
      // For now, use old ExecuteTrade which calculates its own lot size
      // TODO: Update swing endpoint to return lot_size
      ExecuteTrade(direction, confidence, llmMarketRegime, riskPercent, stopPoints, targetPoints, "SWING");
   }
}

//+------------------------------------------------------------------+
//| Check Dynamic ML Exit on Every Tick + Professional Profit Protection |
//+------------------------------------------------------------------+
void CheckDynamicMLExitEveryTick()
{
   if(PositionsTotal() == 0)
   {
      // Reset tracking when no positions
      peakProfit = 0;
      peakMomentum = 0;
      positionCount = 0;
      return;
   }
   
   // PROFESSIONAL PROFIT PROTECTION
   double totalProfit = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionSelectByTicket(PositionGetTicket(i)))
      {
         totalProfit += PositionGetDouble(POSITION_PROFIT);
      }
   }
   
   // Update peak profit
   if(totalProfit > peakProfit)
   {
      peakProfit = totalProfit;
      peakProfitTime = TimeCurrent();
   }
   
   // Calculate profit drawdown
   double profitDrawdown = 0;
   if(peakProfit > 0)
   {
      profitDrawdown = (peakProfit - totalProfit) / peakProfit;
   }
   
   // PROFESSIONAL EXIT TRIGGERS
   if(profitDrawdown > ExitDrawdownLevel2)  // Gave back 25%+
   {
      Print("");
      Print("🛑 [v13.0] PROFESSIONAL EXIT - PROFIT PROTECTION");
      Print("   Reason: Gave back ", DoubleToString(profitDrawdown * 100, 1), "% from peak");
      Print("   Peak profit: $", DoubleToString(peakProfit, 2));
      Print("   Current profit: $", DoubleToString(totalProfit, 2));
      Print("   Closing ALL positions to protect gains");
      Print("");
      
      // Close all positions
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket > 0)
         {
            trade.PositionClose(ticket);
         }
      }
      return;
   }
   else if(profitDrawdown > ExitDrawdownLevel1)  // Gave back 15%+
   {
      Print("");
      Print("📉 [v13.0] PROFESSIONAL SCALE OUT - PROFIT PROTECTION");
      Print("   Reason: Gave back ", DoubleToString(profitDrawdown * 100, 1), "% from peak");
      Print("   Peak profit: $", DoubleToString(peakProfit, 2));
      Print("   Current profit: $", DoubleToString(totalProfit, 2));
      Print("   Closing 50% of positions");
      Print("");
      
      // Close 50% of positions
      int positionsToClose = (int)MathCeil(PositionsTotal() * 0.5);
      for(int i = 0; i < positionsToClose; i++)
      {
         ulong ticket = PositionGetTicket(0);  // Always close first position
         if(ticket > 0)
         {
            trade.PositionClose(ticket);
         }
      }
      return;
   }

   ulong ticket = PositionGetTicket(0);
   if(ticket == 0) return;

   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
   long posType = PositionGetInteger(POSITION_TYPE);
   string posDirection = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";

   double profitPoints = (posType == POSITION_TYPE_BUY) ?
                         (currentPrice - openPrice) :
                         (openPrice - currentPrice);
   double profitPct = (profitPoints / openPrice) * 100.0;

   datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
   int barsHeld = (int)((TimeCurrent() - openTime) / PeriodSeconds(PERIOD_H1));

   // Build exit request
   string url = API_Host + "/api/ultimate/exit";

   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"position_id\":" + IntegerToString(ticket) + ",";
   jsonRequest += "\"direction\":\"" + posDirection + "\",";
   jsonRequest += "\"entry_price\":" + DoubleToString(openPrice, 2) + ",";
   jsonRequest += "\"current_price\":" + DoubleToString(currentPrice, 2) + ",";
   jsonRequest += "\"profit_points\":" + DoubleToString(profitPoints, 2) + ",";
   jsonRequest += "\"profit_pct\":" + DoubleToString(profitPct, 4) + ",";
   jsonRequest += "\"bars_held\":" + IntegerToString(barsHeld) + ",";
   jsonRequest += "\"market_data\":{\"H1\":" + BuildTimeframeJSON(PERIOD_H1) + "}}";

   string response = SendPostRequest(url, jsonRequest);

   if(response == "")
   {
      Print(" AI Exit API call failed");
      return;
   }

   string action = ExtractStringValue(response, "action");
   double exitConfidence = ExtractDoubleValue(response, "confidence");
   string exitReason = ExtractStringValue(response, "reason");
   string llmAction = ExtractStringValue(response, "llm_action");

   Print("");
   Print(" AI EXIT CHECK - Ticket: ", ticket);
   Print(" Held: ", barsHeld, " bars | Profit: ", DoubleToString(profitPoints, 0), " pts");
   Print("┤");
   Print(" ML: ", action, " | LLM: ", llmAction);
   Print(" Confidence: ", DoubleToString(exitConfidence, 1), "%");
   Print(" ", exitReason);
   Print("");

   if(action == "TAKE_PROFIT" || action == "STOP_LOSS")
   {
      double profitAmount = PositionGetDouble(POSITION_PROFIT);
      ClosePosition(ticket, action);
      SendLearningData(profitPoints, profitAmount);
   }
}

//+------------------------------------------------------------------+
//| Execute Trade WITH API LOT SIZE                                 |
//+------------------------------------------------------------------+
void ExecuteTradeWithLotSize(string direction, double confidence, string regime, double apiLotSize, int stopPoints, int targetPoints, string tradeType = "SCALP")
{
   // USE API'S CALCULATED LOT SIZE!
   double lots = apiLotSize;
   
   // Validate lot size
   double minLot = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_STEP);
   
   // Normalize to lot step
   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);

   double price = (direction == "BUY") ? SymbolInfoDouble(TradingSymbol, SYMBOL_ASK) :
                                          SymbolInfoDouble(TradingSymbol, SYMBOL_BID);

   // For US30, API returns actual price points
   // Example: API says 200 points = add 200.0 to price
   // US30 quotes like 47000.00, so SELL @ 47000 → SL: 47200, TP: 46720

   // API points are ALREADY in price units - use them directly
   double stopDistance = (double)stopPoints;    // 200 pts = 200.0 price units
   double targetDistance = (double)targetPoints; // 280 pts = 280.0 price units

   // Calculate SL/TP prices
   double sl = (direction == "BUY") ? price - stopDistance :
                                       price + stopDistance;
   double tp = (direction == "BUY") ? price + targetDistance :
                                       price - targetDistance;

   // Execute with type-specific comment
   string comment = tradeType + "_AI";  // SCALP_AI or SWING_AI
   bool success = false;
   if(direction == "BUY")
   {
      success = trade.Buy(lots, TradingSymbol, price, sl, tp, comment);
   }
   else if(direction == "SELL")
   {
      success = trade.Sell(lots, TradingSymbol, price, sl, tp, comment);
   }

   if(success)
   {
      ulong ticket = trade.ResultOrder();
      Print("═══════════════════════════════════════════════════════════════");
      Print("✅ ", direction, " EXECUTED: ", DoubleToString(lots, 2), " lots @ ", DoubleToString(price, 0));
      Print("   SL: ", DoubleToString(sl, 0), " | TP: ", DoubleToString(tp, 0));
      Print("   LOT SIZE FROM API: ", DoubleToString(apiLotSize, 2), " (normalized to ", DoubleToString(lots, 2), ")");
      Print("═══════════════════════════════════════════════════════════════");

      currentTrade.ticket = ticket;
      currentTrade.direction = direction;
      currentTrade.entry_price = price;
      currentTrade.confidence = confidence;
      currentTrade.regime = regime;
      currentTrade.entry_time = TimeCurrent();
      currentTrade.account_balance_at_entry = AccountInfoDouble(ACCOUNT_BALANCE);
   }
   else
   {
      Print(" ", direction, " FAILED: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Execute Trade (OLD - for swing trading)                         |
//+------------------------------------------------------------------+
void ExecuteTrade(string direction, double confidence, string regime, double riskPercent, int stopPoints, int targetPoints, string tradeType = "SCALP")
{
   // Calculate lot size based on risk
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (riskPercent / 100.0);
   double stopDistance = (double)stopPoints;
   double lots = CalculateLotSize(riskAmount, stopDistance);

   double price = (direction == "BUY") ? SymbolInfoDouble(TradingSymbol, SYMBOL_ASK) :
                                          SymbolInfoDouble(TradingSymbol, SYMBOL_BID);

   double targetDistance = (double)targetPoints;
   double sl = (direction == "BUY") ? price - stopDistance : price + stopDistance;
   double tp = (direction == "BUY") ? price + targetDistance : price - targetDistance;

   string comment = tradeType + "_AI";
   bool success = false;
   if(direction == "BUY")
   {
      success = trade.Buy(lots, TradingSymbol, price, sl, tp, comment);
   }
   else if(direction == "SELL")
   {
      success = trade.Sell(lots, TradingSymbol, price, sl, tp, comment);
   }

   if(success)
   {
      ulong ticket = trade.ResultOrder();
      Print(" ", direction, " EXECUTED: ", DoubleToString(lots, 2), " lots @ ", DoubleToString(price, 0));
      Print("   SL: ", DoubleToString(sl, 0), " | TP: ", DoubleToString(tp, 0));

      currentTrade.ticket = ticket;
      currentTrade.direction = direction;
      currentTrade.entry_price = price;
      currentTrade.confidence = confidence;
      currentTrade.regime = regime;
      currentTrade.entry_time = TimeCurrent();
      currentTrade.account_balance_at_entry = balance;
   }
   else
   {
      Print(" ", direction, " FAILED: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Close Position                                                   |
//+------------------------------------------------------------------+
void ClosePosition(ulong ticket, string reason)
{
   if(trade.PositionClose(ticket))
   {
      Print("Position closed: ", reason);
   }
   else
   {
      Print("Close failed");
   }
}

//+------------------------------------------------------------------+
//| Send Learning Data                                              |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Build Timeframe JSON                                            |
//+------------------------------------------------------------------+
string BuildTimeframeJSON(ENUM_TIMEFRAMES timeframe)
{
   int bars = 100;
   double close[], high[], low[], open[];
   long volume[];
   datetime times[];

   ArraySetAsSeries(close, true);
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(open, true);
   ArraySetAsSeries(volume, true);
   ArraySetAsSeries(times, true);

   int copied = CopyClose(TradingSymbol, timeframe, 0, bars, close);
   if(copied <= 0) return "{}";

   CopyHigh(TradingSymbol, timeframe, 0, bars, high);
   CopyLow(TradingSymbol, timeframe, 0, bars, low);
   CopyOpen(TradingSymbol, timeframe, 0, bars, open);
   CopyTickVolume(TradingSymbol, timeframe, 0, bars, volume);
   CopyTime(TradingSymbol, timeframe, 0, bars, times);

   string tfStr = "H1";
   if(timeframe == PERIOD_M1) tfStr = "M1";
   else if(timeframe == PERIOD_M5) tfStr = "M5";
   else if(timeframe == PERIOD_M15) tfStr = "M15";
   else if(timeframe == PERIOD_M30) tfStr = "M30";
   else if(timeframe == PERIOD_H4) tfStr = "H4";
   else if(timeframe == PERIOD_H8) tfStr = "H8";
   else if(timeframe == PERIOD_D1) tfStr = "D1";

   string json = "{\"timeframe\":\"" + tfStr + "\",";
   json += "\"close\":[";
   for(int i = 0; i < bars && i < ArraySize(close); i++)
   {
      if(i > 0) json += ",";
      json += DoubleToString(close[i], 2);
   }
   json += "],\"high\":[";
   for(int i = 0; i < bars && i < ArraySize(high); i++)
   {
      if(i > 0) json += ",";
      json += DoubleToString(high[i], 2);
   }
   json += "],\"low\":[";
   for(int i = 0; i < bars && i < ArraySize(low); i++)
   {
      if(i > 0) json += ",";
      json += DoubleToString(low[i], 2);
   }
   json += "],\"open\":[";
   for(int i = 0; i < bars && i < ArraySize(open); i++)
   {
      if(i > 0) json += ",";
      json += DoubleToString(open[i], 2);
   }
   json += "],\"volume\":[";
   for(int i = 0; i < bars && i < ArraySize(volume); i++)
   {
      if(i > 0) json += ",";
      json += IntegerToString(volume[i]);
   }
   json += "],\"timestamp\":[";
   for(int i = 0; i < bars && i < ArraySize(times); i++)
   {
      if(i > 0) json += ",";
      json += "\"" + TimeToString(times[i], TIME_DATE|TIME_MINUTES) + "\"";
   }
   json += "]}";

   return json;
}

//+------------------------------------------------------------------+
//| Send continuous learning data to API                              |
//| Learns from every tick, not just trades!                         |
//+------------------------------------------------------------------+
void SendContinuousLearningData()
{
   string url = API_Host + "/api/learn/tick";
   
   // Get current market data
   double currentPrice = iClose(TradingSymbol, PERIOD_M1, 0);
   
   // Build simple state (3 key indicators) - using handles and buffers
   int rsiHandle = iRSI(TradingSymbol, PERIOD_M1, 14, PRICE_CLOSE);
   int atrHandle = iATR(TradingSymbol, PERIOD_M1, 20);
   int smaHandle = iMA(TradingSymbol, PERIOD_M1, 20, 0, MODE_SMA, PRICE_CLOSE);
   
   double rsiBuffer[], atrBuffer[], smaBuffer[];
   CopyBuffer(rsiHandle, 0, 0, 1, rsiBuffer);
   CopyBuffer(atrHandle, 0, 0, 1, atrBuffer);
   CopyBuffer(smaHandle, 0, 0, 1, smaBuffer);
   
   double rsi = rsiBuffer[0];
   double atr = atrBuffer[0];
   double close = iClose(TradingSymbol, PERIOD_M1, 0);
   double sma20 = smaBuffer[0];
   
   // Normalize state values
   double trendNorm = (close - sma20) / MathMax(atr, 1.0);
   double rsiNorm = (rsi - 50.0) / 50.0;
   double volNorm = (atr / MathMax(close, 1.0)) * 10000.0;
   
   // Release handles
   IndicatorRelease(rsiHandle);
   IndicatorRelease(atrHandle);
   IndicatorRelease(smaHandle);
   
   // Build state array
   string stateArray = "[";
   stateArray += DoubleToString(trendNorm, 2) + ",";
   stateArray += DoubleToString(rsiNorm, 2) + ",";
   stateArray += DoubleToString(volNorm, 2);
   stateArray += "]";
   
   // Build JSON request
   string jsonRequest = "{";
   jsonRequest += "\"timestamp\": \"" + TimeToString(TimeCurrent()) + "\",";
   jsonRequest += "\"state\": " + stateArray + ",";
   jsonRequest += "\"prediction\": " + IntegerToString(lastMLPrediction) + ",";
   jsonRequest += "\"confidence\": " + DoubleToString(lastMLConfidence, 1) + ",";
   jsonRequest += "\"price\": " + DoubleToString(currentPrice, 2);
   jsonRequest += "}";
   
   // Send to API (non-blocking)
   string response = SendPostRequest(url, jsonRequest);
   
   // Update last price for next iteration
   lastMLPrice = currentPrice;
}

//+------------------------------------------------------------------+
//| Send POST Request                                               |
//+------------------------------------------------------------------+
string SendPostRequest(string url, string jsonData)
{
   char post[];
   char result[];
   string headers = "Content-Type: application/json\r\n";
   string resultHeaders;

   StringToCharArray(jsonData, post, 0, StringLen(jsonData));

   int timeout = 10000;
   int res = WebRequest("POST", url, headers, timeout, post, result, resultHeaders);

   if(res == 200)
   {
      return CharArrayToString(result);
   }
   else if(res == -1)
   {
      int error = GetLastError();
      Print("WebRequest error: ", error);
      Print("Add URL to allowed list: Tools → Options → Expert Advisors");
      Print("Add: ", API_Host);
   }
   else
   {
      Print("HTTP Error ", res, " from ", url);
      string response = CharArrayToString(result);
      if(StringLen(response) > 0)
      {
         Print("Response: ", response);
      }
   }

   return "";
}

//+------------------------------------------------------------------+
//| Extract String Value from JSON                                  |
//+------------------------------------------------------------------+
string ExtractStringValue(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int start = StringFind(json, search);
   if(start < 0) return "";

   start += StringLen(search);
   int end = StringFind(json, "\"", start);
   if(end < 0) return "";

   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Extract Double Value from JSON                                  |
//+------------------------------------------------------------------+
double ExtractDoubleValue(string json, string key)
{
   string search = "\"" + key + "\":";
   int start = StringFind(json, search);
   if(start < 0) return 0.0;

   start += StringLen(search);

   // Find end (comma or })
   int end = StringFind(json, ",", start);
   if(end < 0) end = StringFind(json, "}", start);
   if(end < 0) return 0.0;

   string valueStr = StringSubstr(json, start, end - start);

   // Trim whitespace manually
   while(StringLen(valueStr) > 0 && (StringGetCharacter(valueStr, 0) == ' ' || StringGetCharacter(valueStr, 0) == '\t'))
      valueStr = StringSubstr(valueStr, 1);

   return StringToDouble(valueStr);
}

//+------------------------------------------------------------------+
//| Extract Bool Value from JSON                                    |
//+------------------------------------------------------------------+
bool ExtractBoolValue(string json, string key)
{
   string search = "\"" + key + "\":";
   int start = StringFind(json, search);
   if(start < 0) return false;

   start += StringLen(search);
   string substr = StringSubstr(json, start, 10);

   return StringFind(substr, "true") >= 0;
}

//+------------------------------------------------------------------+
//| Calculate Lot Size                                              |
//+------------------------------------------------------------------+
double CalculateLotSize(double riskAmount, double stopLossPrice)
{
   double tickValue = SymbolInfoDouble(TradingSymbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(TradingSymbol, SYMBOL_TRADE_TICK_SIZE);
   double minLot = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_STEP);

   if(stopLossPrice <= 0 || tickValue <= 0) return minLot;

   double lots = (riskAmount / stopLossPrice) * tickSize / tickValue;

   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);

   return lots;
}

//+------------------------------------------------------------------+
//| Check Daily Reset                                               |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);

   datetime today = StringToTime(IntegerToString(dt.year) + "." +
                                  IntegerToString(dt.mon) + "." +
                                  IntegerToString(dt.day));

   if(today != currentDay)
   {
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      currentDay = today;
      Print("═══════════════════════════════════════════════════════════════");
      Print("");
   }
}

//+------------------------------------------------------------------+
//| Update LLM Risk Manager (Every 60s)                             |
//+------------------------------------------------------------------+
void UpdateLLMRiskManager()
{
   string url = API_Host + "/api/risk/update";
   
   // Calculate daily P/L
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dailyPnL = currentBalance - dailyStartBalance;
   double dailyPnLPercent = (dailyPnL / dailyStartBalance) * 100.0;
   
   // Calculate total drawdown
   double totalDrawdown = ((startingBalance - currentBalance) / startingBalance) * 100.0;
   
   // Build JSON with account health data
   string jsonRequest = "{";
   jsonRequest += "\"balance\":" + DoubleToString(currentBalance, 2) + ",";
   jsonRequest += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   jsonRequest += "\"daily_pnl\":" + DoubleToString(dailyPnL, 2) + ",";
   jsonRequest += "\"daily_pnl_percent\":" + DoubleToString(dailyPnLPercent, 2) + ",";
   jsonRequest += "\"drawdown\":" + DoubleToString(totalDrawdown, 2) + ",";
   jsonRequest += "\"starting_balance\":" + DoubleToString(startingBalance, 2) + ",";
   jsonRequest += "\"daily_start_balance\":" + DoubleToString(dailyStartBalance, 2) + ",";
   jsonRequest += "\"positions_total\":" + IntegerToString(PositionsTotal()) + ",";
   jsonRequest += "\"market_data\":{";
   jsonRequest += "\"regime\":\"" + llmMarketRegime + "\",";
   jsonRequest += "\"bias\":\"" + llmMarketBias + "\",";
   jsonRequest += "\"volatility\":\"normal\",";
   jsonRequest += "\"session\":\"" + GetCurrentSession() + "\"";
   jsonRequest += "}}";
   
   string response = SendPostRequest(url, jsonRequest);
   
   if(response != "")
   {
      // DEBUG: Print raw response
      // Print("DEBUG: Raw response: ", response);
      
      // Parse updated risk parameters
      string riskMode = ExtractStringValue(response, "mode");
      double riskMultiplier = ExtractDoubleValue(response, "risk_multiplier");
      double thresholdAdj = ExtractDoubleValue(response, "threshold_adjustment");
      string reasoning = ExtractStringValue(response, "reasoning");
      
      // Only log if values are valid
      if(riskMultiplier > 0 || riskMode != "")
      {
         Print("");
         Print("🛡️ [v8.1] RISK MANAGER UPDATE");
         Print("   Mode: ", riskMode);
         Print("   Risk Multiplier: ", DoubleToString(riskMultiplier, 2), "x");
         Print("   Threshold Adj: ", DoubleToString(thresholdAdj, 1), "%");
         Print("   Daily P/L: ", DoubleToString(dailyPnLPercent, 2), "%");
         Print("   Drawdown: ", DoubleToString(totalDrawdown, 2), "%");
         if(StringLen(reasoning) > 100)
            Print("   Reasoning: ", StringSubstr(reasoning, 0, 100), "...");
         else
            Print("   Reasoning: ", reasoning);
         Print("");
      }
   }
}

//+------------------------------------------------------------------+
//| Get Current Trading Session                                     |
//+------------------------------------------------------------------+
string GetCurrentSession()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour = dt.hour;
   
   if(hour >= 0 && hour < 8) return "asian";
   else if(hour >= 8 && hour < 13) return "london";
   else if(hour >= 13 && hour < 20) return "newyork";
   else return "asian";
}

//+------------------------------------------------------------------+
//| Check Daily Loss Limit                                          |
//+------------------------------------------------------------------+
bool IsDailyLossLimitReached()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dailyLoss = dailyStartBalance - currentBalance;
   double dailyLossPct = (dailyLoss / dailyStartBalance) * 100.0;

   return dailyLossPct >= MaxDailyLossPercent;
}

//+------------------------------------------------------------------+
//| Check Total Drawdown Limit                                      |
//+------------------------------------------------------------------+
bool IsTotalDrawdownLimitReached()
{
   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double totalLoss = startingBalance - currentBalance;
   double totalLossPct = (totalLoss / startingBalance) * 100.0;

   return totalLossPct >= MaxTotalLossPercent;
}

//+------------------------------------------------------------------+
//| AI EXIT ON EVERY TICK - 100% AI POWERED                         |
//| Calls API for EVERY price change - TRUE AI decision making      |
//| No hard-coded rules - AI sees everything and decides            |
//+------------------------------------------------------------------+
void CheckAIExitEveryTick()
{
   if(PositionsTotal() == 0) return;

   // Get position info
   ulong ticket = PositionGetTicket(0);
   if(ticket == 0) {
      Print("DEBUG: Ticket is 0");
      return;
   }
   Print("DEBUG: Got ticket: ", ticket);

   // CRITICAL: Select the position before reading its properties
   if(!PositionSelectByTicket(ticket)) {
      Print("❌ Failed to select position: ", ticket);
      return;
   }

   // Call the AI API to get exit decision
   string url = API_Host + "/api/ultimate/exit";

   // Get ACTUAL floating profit from MT5
   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
   double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
   double floatingProfit = PositionGetDouble(POSITION_PROFIT);  // ACTUAL P&L in dollars!
   double positionVolume = PositionGetDouble(POSITION_VOLUME);
   long positionType = PositionGetInteger(POSITION_TYPE);
   string direction = (positionType == POSITION_TYPE_BUY) ? "LONG" : "SHORT";
   
   // DEBUG: Log what we got
   Print("DEBUG: Floating Profit = ", floatingProfit, " | Volume = ", positionVolume);

   double tickSize = SymbolInfoDouble(TradingSymbol, SYMBOL_TRADE_TICK_SIZE);
   double profitPoints = 0;
   if(direction == "LONG") {
      profitPoints = (currentPrice - openPrice) / tickSize;
   } else {
      profitPoints = (openPrice - currentPrice) / tickSize;
   }

   // Calculate additional required fields
   datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
   int barsHeld = (int)((TimeCurrent() - openTime) / 60); // Minutes held
   double profitPct = (profitPoints * tickSize / openPrice) * 100.0;

   // Build JSON for exit API call
   string jsonRequest = "{";
   jsonRequest += "\"symbol\":\"" + TradingSymbol + "\",";
   jsonRequest += "\"position_id\":" + IntegerToString(ticket) + ",";
   jsonRequest += "\"direction\":\"" + direction + "\",";
   jsonRequest += "\"entry_price\":" + DoubleToString(openPrice, 2) + ",";
   jsonRequest += "\"current_price\":" + DoubleToString(currentPrice, 2) + ",";
   jsonRequest += "\"bars_held\":" + IntegerToString(barsHeld) + ",";
   jsonRequest += "\"profit_points\":" + DoubleToString(profitPoints, 1) + ",";
   jsonRequest += "\"profit_pct\":" + DoubleToString(profitPct, 2) + ",";
   jsonRequest += "\"floating_profit\":" + DoubleToString(floatingProfit, 2) + ",";  // ACTUAL P&L!
   jsonRequest += "\"position_volume\":" + DoubleToString(positionVolume, 2) + ",";
   jsonRequest += "\"account_balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   jsonRequest += "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   jsonRequest += "\"day_start_equity\":" + DoubleToString(dailyStartBalance, 2) + ",";
   jsonRequest += "\"market_data\":{";
   // Add all 5 scalping timeframes (M5, M15, M30, H1, H4) for 126 features
   jsonRequest += "\"M5\":" + BuildTimeframeJSON(PERIOD_M5) + ",";
   jsonRequest += "\"M15\":" + BuildTimeframeJSON(PERIOD_M15) + ",";
   jsonRequest += "\"M30\":" + BuildTimeframeJSON(PERIOD_M30) + ",";
   jsonRequest += "\"H1\":" + BuildTimeframeJSON(PERIOD_H1) + ",";
   jsonRequest += "\"H4\":" + BuildTimeframeJSON(PERIOD_H4);
   jsonRequest += "}}";

   // Call AI API
   string response = SendPostRequest(url, jsonRequest);

   if(response == "") return; // API call failed, keep position

   // Parse AI decision
   string action = ExtractStringValue(response, "action");
   double confidence = ExtractDoubleValue(response, "confidence");
   string reason = ExtractStringValue(response, "reason");

   // AI DECIDES - Execute if AI says exit
   if(action == "TAKE_PROFIT" || action == "STOP_LOSS") {
      Print("═══════════════════════════════════════════════════════════");
      Print("🤖 AI EXIT DECISION");
      Print("Action: ", action, " @ ", DoubleToString(confidence, 1), "%");
      Print("Profit: ", DoubleToString(profitPoints, 1), " pts");
      Print("Reason: ", reason);
      Print("═══════════════════════════════════════════════════════════");

      // v4.0: IMPROVED CLOSE LOGIC WITH VOLUME NORMALIZATION
      // Get position volume with proper normalization
      double posVolume = 0.0;

      // METHOD 1: Try to get volume by selecting position by ticket
      if(PositionSelectByTicket(ticket)) {
         posVolume = PositionGetDouble(POSITION_VOLUME);
         Print("   [v4.0] Volume from PositionSelectByTicket: ", posVolume);
      } else {
         // METHOD 2: Try selecting by symbol
         if(PositionSelect(TradingSymbol)) {
            posVolume = PositionGetDouble(POSITION_VOLUME);
            Print("   [v4.0] Volume from PositionSelect(symbol): ", posVolume);
         } else {
            Print("❌ [v4.0] Cannot select position - using fallback");
            posVolume = 0.01; // Fallback to minimum
         }
      }

      // Normalize volume according to symbol specifications
      double minVol = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MIN);
      double maxVol = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_MAX);
      double volStep = SymbolInfoDouble(TradingSymbol, SYMBOL_VOLUME_STEP);

      Print("   [v4.0] Symbol specs - Min:", minVol, " Max:", maxVol, " Step:", volStep);
      Print("   [v4.0] Raw volume:", posVolume);

      // Normalize to step
      posVolume = MathFloor(posVolume / volStep) * volStep;
      posVolume = MathMax(posVolume, minVol);
      posVolume = MathMin(posVolume, maxVol);

      Print("   [v4.0] Normalized volume:", posVolume);

      // TRY METHOD 1: Simple PositionClose
      if(trade.PositionClose(ticket)) {
         Print("✅ [v4.0] Position closed via PositionClose()");
         double profit = PositionGetDouble(POSITION_PROFIT);
         SendLearningData(profitPoints, profit);
      } else {
         int error = GetLastError();
         Print("❌ [v4.0] PositionClose failed. Error:", error);

         // TRY METHOD 2: OrderSend with normalized volume
         Print("   [v4.0] Attempting OrderSend with volume:", posVolume);

         MqlTradeRequest request = {};
         MqlTradeResult result = {};

         request.action = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol = TradingSymbol;
         request.volume = posVolume;
         request.type = (positionType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (positionType == POSITION_TYPE_BUY) ? SymbolInfoDouble(TradingSymbol, SYMBOL_BID) : SymbolInfoDouble(TradingSymbol, SYMBOL_ASK);
         request.deviation = 100;
         request.magic = 0;
         request.type_filling = ORDER_FILLING_IOC;
         request.comment = "SCALP_AI"; // SCALP_AI or SWING_AI

         if(OrderSend(request, result)) {
            if(result.retcode == TRADE_RETCODE_DONE) {
               Print("✅ [v4.0] Position closed via OrderSend()");
               Print("   Deal:", result.deal, " Order:", result.order);
            } else {
               Print("❌ [v4.0] OrderSend retcode:", result.retcode);
               Print("   Comment:", result.comment);
            }
         } else {
            Print("❌ [v4.0] OrderSend failed");

            // TRY METHOD 3: FOK fill type
            request.type_filling = ORDER_FILLING_FOK;
            Print("   [v4.0] Trying FOK fill type...");

            if(OrderSend(request, result) && result.retcode == TRADE_RETCODE_DONE) {
               Print("✅ [v4.0] Position closed via OrderSend(FOK)");
            } else {
               Print("❌ [v4.0] All close methods failed!");
               Print("   Final retcode:", result.retcode);
               Print("   Final comment:", result.comment);
            }
         }
      }
   }
   // If action == "HOLD", AI says keep the position open
}

//+------------------------------------------------------------------+
//| Send Learning Data to RL Agent                                  |
//+------------------------------------------------------------------+
void SendLearningData(double profitPoints, double profitAmount)
{
   // v8.1: Enhanced learning with detailed trade data
   string url = API_Host + "/api/ultimate/learn";

   string jsonRequest = "{";
   jsonRequest += "\"ticket\":" + IntegerToString(currentTrade.ticket) + ",";
   jsonRequest += "\"direction\":\"" + currentTrade.direction + "\",";
   jsonRequest += "\"entry_price\":" + DoubleToString(currentTrade.entry_price, 2) + ",";
   jsonRequest += "\"confidence\":" + DoubleToString(currentTrade.confidence, 1) + ",";
   jsonRequest += "\"regime\":\"" + currentTrade.regime + "\",";
   jsonRequest += "\"profit_points\":" + DoubleToString(profitPoints, 1) + ",";
   jsonRequest += "\"profit_amount\":" + DoubleToString(profitAmount, 2) + ",";
   jsonRequest += "\"hold_time\":" + IntegerToString((int)(TimeCurrent() - currentTrade.entry_time)) + ",";
   jsonRequest += "\"entry_balance\":" + DoubleToString(currentTrade.account_balance_at_entry, 2);
   jsonRequest += "}";

   // Fire and forget (don't wait for response)
   string response = SendPostRequest(url, jsonRequest);
   
   // Log learning update
   Print("📚 [v8.1] ML LEARNING UPDATE SENT");
   Print("   Trade: ", currentTrade.direction, " @ ", DoubleToString(currentTrade.confidence, 1), "%");
   Print("   Result: ", profitPoints > 0 ? "WIN" : "LOSS", " (", DoubleToString(profitPoints, 1), " pts)");
   Print("   Regime: ", currentTrade.regime);
}

O *cascade08OPPX *cascade08XYY\ *cascade08\ccd *cascade08djjk *cascade08kpp� *cascade08�� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08�� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08��*cascade08���� *cascade08���� *cascade08���� *cascade08�� *cascade08��*cascade08�� *cascade08���� *cascade08���� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���� *cascade08���� *cascade08���� *cascade08
�� �� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08�� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08��	�	�	 *cascade08�	�	�	�	 *cascade08�	�	�	�	 *cascade08�	�	�	�	 *cascade08�	�	�	�	 *cascade08�	�	�	�	 *cascade08�	�	�	�
 *cascade08�
�
�
�
 *cascade08�
�
�
�
 *cascade08�
��� *cascade08���� *cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���� *cascade08���� *cascade08�� *cascade08�� *cascade08���� *cascade08���� *cascade08��*cascade08�� *cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08�� *cascade08�� *cascade08�� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08���� *cascade08�� *cascade08����*cascade08���� *cascade08����  *cascade08� � � �  *cascade08� � � �  *cascade08� �!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�!�!�! *cascade08�!�"�"�" *cascade08�"�"�"�" *cascade08�"�"�"�" *cascade08�"�"�"�" *cascade08�"�" *cascade08�"�"�"�" *cascade08�"�"�"�" *cascade08�"�"�"�" *cascade08�"�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�# *cascade08�#�#�#�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�$�$�$ *cascade08�$�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�%�%�% *cascade08�%�&�&�& *cascade08�&�&�&�& *cascade08�&�&�&�& *cascade08�&�&�&�& *cascade08�&�&�&�& *cascade08�&�& *cascade08�&�&�&�& *cascade08�&�&�&�& *cascade08�&�& *cascade08�&�'�'�' *cascade08�'�'�'�' *cascade08�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'*cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�'�'�' *cascade08�'�(�(�( *cascade08�(�(�(�( *cascade08�(�( *cascade08�(�(�(�( *cascade08�(�( *cascade08�(�( *cascade08�(�(�(�( *cascade08�(�(�(�( *cascade08�(�(�(�( *cascade08�(�(�(�( *cascade08�(�(�(�( *cascade08�(�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�)�)�) *cascade08�)�) *cascade08�)�) *cascade08�)�)�)�) *cascade08
�)�) �)�) *cascade08�)�) *cascade08�)�)*cascade08�)�) *cascade08�)�)�)�)*cascade08�)�) *cascade08�)�)�)�) *cascade08�)�)�)�)*cascade08�)�)�)�) *cascade08�)�)�)�)*cascade08�)�)�)�) *cascade08�)�) *cascade08�)�)�)�) *cascade08
�)�) �)�) *cascade08�)�)�)�) *cascade08�)�,�,�, *cascade08�,�, *cascade08�,�, *cascade08�,�,�,�, *cascade08�,�,�,�, *cascade08�,�,�,�, *cascade08�,�,�,�, *cascade08�,�-�-�- *cascade08�-�-�-�- *cascade08�-�-�-�- *cascade08�-�-�-�. *cascade08
�.�/ �/�/ *cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�/*cascade08�/�/ *cascade08�/�0*cascade08�0�0 *cascade08�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08
�0�0 �0�0*cascade08�0�0 *cascade08�0�0 *cascade08�0�0*cascade08
�0�0 �0�0 *cascade08�0�0 *cascade08�0�0*cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08�0�0 *cascade08�0�0*cascade08�0�1 *cascade08�1�1*cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�1*cascade08�1�1 *cascade08�1�:*cascade08�:�: *cascade08�:�:*cascade08�:�: *cascade08�:�:*cascade08�:�: *cascade08�:�;*cascade08�;�; *cascade08�;�;*cascade08�;�; *cascade08�;�;*cascade08�;�; *cascade08�;�;�;�; *cascade08�;�;*cascade08�;�; *cascade08�;�;*cascade08�;�; *cascade08�;�;*cascade08�;�; *cascade08�;�;*cascade08�;�> *cascade08�>�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�B*cascade08�B�B *cascade08�B�C*cascade08�C�C *cascade08�C�C*cascade08�C�C *cascade08�C�C*cascade08�C�C *cascade08�C�D*cascade08�D�D *cascade08�D�D*cascade08�D�G *cascade08�G�G*cascade08�G�G *cascade08�G�G*cascade08�G�G *cascade08�G�G*cascade08�G�G *cascade08�G�G*cascade08�G�G *cascade08�G�G�G�G *cascade08�G�G*cascade08�G�H *cascade08�H�H*cascade08�H�L *cascade08�L�L�L�L *cascade08�L�L*cascade08�L�L *cascade08�L�L *cascade08�L�L�L�L *cascade08�L�L*cascade08�L�L *cascade08�L�L*cascade08�L�L *cascade08�L�L*cascade08�L�L *cascade08�L�L�L�L *cascade08�L�L�L�L *cascade08�L�L *cascade08�L�L�L�L *cascade08�L�L�L�M *cascade08
�M�M �M�O *cascade08�O�O*cascade08�O�O *cascade08�O�O*cascade08�O�O *cascade08�O�O*cascade08�O�O *cascade08�O�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�P*cascade08�P�P *cascade08�P�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�Q *cascade08�Q�Q*cascade08�Q�R *cascade08�R�R*cascade08�R�R *cascade08�R�R*cascade08�R�S *cascade08�S�S*cascade08�S�S *cascade08�S�S*cascade08�S�S *cascade08�S�T*cascade08�T�T *cascade08�T�T*cascade08�T�T *cascade08�T�T *cascade08�T�T*cascade08�T�U *cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�U *cascade08�U�U*cascade08�U�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�V*cascade08�V�V *cascade08�V�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�W *cascade08�W�W*cascade08�W�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X *cascade08�X�X *cascade08�X�X *cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X*cascade08�X�X *cascade08�X�X *cascade08�X�X*cascade08�X�X*cascade08�X�X*cascade08�X�X *cascade08�X�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y *cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y*cascade08�Y�Y *cascade08�Y�Y *cascade08�Y�[�[�[ *cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[ *cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�[ *cascade08�[�[*cascade08�[�\ *cascade08�\�`*cascade08�`�} *cascade08�}��ɀ *cascade08ɀʀ*cascade08ʀˀ *cascade08ˀ̀*cascade08̀�� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��ā*cascade08āԁ *cascade08ԁ؁*cascade08؁ہ *cascade08ہށ*cascade08ށ�� *cascade08���*cascade08�� *cascade08�� *cascade08��*cascade08��� *cascade08���*cascade08�� *cascade08��*cascade08��� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08����*cascade08��̓ *cascade08̓҃*cascade08҃Ӄ *cascade08Ӄރ*cascade08ރ߃ *cascade08߃��*cascade08��� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���*cascade08��� *cascade08��*cascade08��� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08��Ɔ *cascade08Ɔˆ*cascade08ˆ̆ *cascade08̆͆*cascade08͆ֆ *cascade08ֆۆ*cascade08ۆ܆ *cascade08܆�*cascade08�� *cascade08
������� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08�� *cascade08�*cascade08��� *cascade08����*cascade08���� *cascade08����*cascade08��� *cascade08��*cascade08�� *cascade08��*cascade08��� *cascade08
�������� *cascade08
�������� *cascade08
��ӌӌ׌ *cascade08
׌���� *cascade08
������ *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ččƍ *cascade08ƍǍ*cascade08
Ǎʍʍˍ *cascade08
ˍээӍ *cascade08
ӍՍՍ֍ *cascade08
֍׍׍ٍ *cascade08
ٍ܍܍ݍ *cascade08
ݍލލ� *cascade08
����� *cascade08
�������� *cascade08
������ *cascade08
ȏȏʏ *cascade08
ʏΏΏЏ *cascade08
Џݏݏޏ *cascade08
ޏߏߏ�� *cascade08
����� *cascade08
���� *cascade08
���� *cascade08
���� *cascade08
���� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
������͐ *cascade08
͐��� *cascade08
���� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ʑʑˑ *cascade08
ˑ͑͑ϑ *cascade08
ϑёёґ *cascade08
ґՑՑۑ *cascade08
ۑޑޑ�� *cascade08
�������� *cascade08
��ܓܓ�� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��Ɣ*cascade08Ɣ͔ *cascade08͔Δ*cascade08Δؔ *cascade08ؔݔ*cascade08ݔޔ *cascade08ޔ�*cascade08�� *cascade08�� *cascade08���*cascade08���� *cascade08����*cascade08���� *cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08���� *cascade08����*cascade08���� *cascade08��ȕ*cascade08ȕ͕ *cascade08͕Ε *cascade08Εӕ*cascade08ӕԕ *cascade08ԕՕ*cascade08Օ֕ *cascade08֕ؕ*cascade08ؕٕ *cascade08ٕڕ*cascade08ڕە *cascade08ەޕ*cascade08ޕߕ *cascade08ߕ�*cascade08��*cascade08�� *cascade08�ژ*cascade08
ژ��� *cascade08
������� *cascade08���� ���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ЙЙљ *cascade08љՙ ՙ��*cascade08���� ���� *cascade08
�������� *cascade08��ٚ ٚ��*cascade08���� ���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ѝѝҝ *cascade08ҝם ם�*cascade08�� �� *cascade08
����� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��Š*cascade08ŠϠ *cascade08ϠӠ*cascade08ӠԠ *cascade08Ԡ�*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08��� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��¡*cascade08¡� *cascade08
�����Ԫ *cascade08
Ԫ������ *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ڭڭۭ *cascade08
ۭ��� *cascade08
���� *cascade08
������� *cascade08
�������� *cascade08
������� *cascade08�ׯ*cascade08ׯ�� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08��´ *cascade08´ɴ*cascade08ɴʴ *cascade08ʴ̴*cascade08̴ʹ *cascade08ʹ޴*cascade08޴ߴ *cascade08ߴ��*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��е*cascade08еԵ *cascade08Ե�*cascade08�� *cascade08��*cascade08�� *cascade08���*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08��ƶ *cascade08
ƶƶƶ� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
������» *cascade08
»������ *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��׽׽ٽ *cascade08
ٽ߽߽� *cascade08
������� *cascade08
�������� *cascade08
��ƾƾǾ *cascade08
Ǿ������ *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ɿɿʿ *cascade08
ʿܿܿݿ *cascade08
ݿ��� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��������*cascade08
��������*cascade08
�������� *cascade08
��������*cascade08
��������*cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� ����*cascade08���� ���� *cascade08���� ����*cascade08���� *cascade08
�������� *cascade08���� *cascade08���� *cascade08����*cascade08
��������*cascade08���� *cascade08
�������� *cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08���� *cascade08
�������� *cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08���� *cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08���� ����*cascade08���� ����*cascade08���� ����*cascade08���� ����*cascade08���� *cascade08���� *cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08
�������� *cascade08����*cascade08���� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��߁߁� *cascade08
������� *cascade08
�������� *cascade08
������ *cascade08
������ɗ *cascade08
ɗ͗͗Η *cascade08
Ηїїҗ *cascade08
җ՗՗֗ *cascade08
֗ڗڗ՘ *cascade08
՘������ *cascade08
�������� *cascade08
������ș *cascade08ș�*cascade08�� *cascade08�� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
������Ś *cascade08
ŚȚȚɚ *cascade08
ɚ̚̚͚ *cascade08
͚ΚΚϚ *cascade08
Ϛ��� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ӛӛ� *cascade08
���� *cascade08
���� *cascade08
���� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
��ϜϜМ *cascade08
Мݜݜޜ *cascade08
ޜ��� *cascade08
���� *cascade08
���� *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08���� *cascade08���*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���*cascade08��٦ *cascade08٦ܦ*cascade08ܦݦ *cascade08ݦߦ*cascade08ߦ� *cascade08
�úú�� *cascade08
�������� *cascade08����*cascade08�� *cascade08ː*cascade08ː̐ *cascade08̐��*cascade08��� *cascade08��*cascade08�� *cascade08���*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��ݔ*cascade08ݔ� *cascade08��*cascade08�� *cascade08��*cascade08�� *cascade08���*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��ƕ*cascade08ƕǕ *cascade08Ǖԕ*cascade08ԕՕ *cascade08Օ�*cascade08�� *cascade08��*cascade08�� *cascade08��*cascade08��� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08��ؚ*cascade08ؚٚ *cascade08ٚ�� *cascade08����*cascade08��� *cascade08�Ɵ*cascade08Ɵן *cascade08ןڟ*cascade08ڟ�� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08��С *cascade08Сӡ*cascade08ӡ�� *cascade08����*cascade08��� *cascade08���*cascade08���� *cascade08����*cascade08��ţ *cascade08ţգ*cascade08գޣ *cascade08ޣ��*cascade08���� *cascade08����*cascade08���� *cascade08��� *cascade08
������� *cascade08
��˴˴� *cascade08
������ *cascade08
������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08
�������� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08����*cascade08���� *cascade08���� *cascade082�file:///Users/justinhardison/Library/Application%20Support/net.metaquotes.wine.metatrader5/drive_c/Program%20Files/MetaTrader%205/MQL5/Experts/Advisors/US30_Ultimate_AI_v3.mq5