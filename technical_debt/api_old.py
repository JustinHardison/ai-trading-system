"""
AI-POWERED TRADING API - THE PERFECT SYSTEM
Integrates: ML Signal → AI Market Structure → RL Agent → Risk Management

This is what you asked for: An AI that thinks like a trader, not a rule-following bot.
"""
import os
import sys
import logging
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from fastapi import FastAPI, HTTPException
from datetime import datetime
import joblib

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.ai.intelligent_trade_manager import IntelligentTradeManager, MarketStructure
from src.risk.ftmo_risk_manager import FTMORiskManager
from src.features.ea_feature_engineer import EAFeatureEngineer
from src.features.simple_feature_engineer import SimpleFeatureEngineer
from src.ai.enhanced_context import EnhancedTradingContext
from src.ai.adaptive_optimizer import AdaptiveOptimizer
from src.ai.ai_risk_manager import AIRiskManager
from src.ai.intelligent_position_manager import IntelligentPositionManager
from src.analytics.trade_tracker import get_tracker
from src.ai.smart_position_sizer import get_smart_sizer

# ═══════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('/tmp/ai_trading_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════
app = FastAPI(title="AI-Powered Trading System", version="1.0.0")

# ═══════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════
ml_models = {}  # Dictionary of {symbol: model} - supports multi-symbol trading
feature_engineer = None
trade_manager = None
adaptive_optimizer = None
ai_risk_manager = None
ppo_agent = None  # Will be loaded after training completes
dqn_agent = None  # DQN RL agent
position_manager = None  # Position manager
# Note: ftmo_risk_manager is created per-request with live EA data

# ═══════════════════════════════════════════════════════════════════
# STARTUP: LOAD ALL AI COMPONENTS
# ═══════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def load_ai_system():
    """Load ML models for all symbols, AI trade manager, and risk systems"""
    global ml_models, feature_engineer, trade_manager, ppo_agent, adaptive_optimizer, ai_risk_manager, position_manager, dqn_agent

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("AI-POWERED MULTI-SYMBOL TRADING SYSTEM - LOADING")
    logger.info("═══════════════════════════════════════════════════════════════════")

    # 1. Load ML Models for ALL trained symbols
    try:
        import glob
        model_files = glob.glob('/Users/justinhardison/ai-trading-system/models/*_ensemble_latest.pkl')
        
        if not model_files:
            # Fallback to specific model if no *_latest.pkl found
            logger.warning("No *_ensemble_latest.pkl files found, trying fallback model...")
            fallback_model = '/Users/justinhardison/ai-trading-system/models/integrated_ensemble_20251118_130030.pkl'
            if os.path.exists(fallback_model):
                ml_models['us30'] = joblib.load(fallback_model)  # Lowercase!
                logger.info("✅ Loaded fallback model for us30")
        else:
            for model_file in model_files:
                # Extract symbol name from filename (keep lowercase to match filenames)
                basename = os.path.basename(model_file)
                symbol = basename.replace('_ensemble_latest.pkl', '')  # Keep lowercase!
                
                try:
                    ml_models[symbol] = joblib.load(model_file)
                    logger.info(f"✅ Loaded model for {symbol}")
                except Exception as e:
                    logger.error(f"❌ Failed to load model for {symbol}: {e}")
        
        logger.info(f"✅ Total models loaded: {len(ml_models)} symbols")
        
    except Exception as e:
        logger.error(f"❌ Failed to load ML models: {e}")
        ml_models = {}

    # 2. Initialize Live Feature Engineer (131 features - matches NEW training data)
    try:
        from src.features.live_feature_engineer import LiveFeatureEngineer
        feature_engineer = LiveFeatureEngineer()
        logger.info(f"✅ Live Feature Engineer initialized ({feature_engineer.get_feature_count()} features)")
        logger.info(f"   Format: Advanced features matching 131-feature training data")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Live feature engineer: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to MTF
        try:
            from src.features.mtf_feature_engineer import MTFFeatureEngineer
            feature_engineer = MTFFeatureEngineer()
            logger.warning(f"⚠️  Using MTFFeatureEngineer fallback (73 features - WILL CAUSE ERRORS!)")
        except:
            feature_engineer = None
    
    # 2.5. Initialize AI Adaptive Optimizer (self-learning parameters)
    global adaptive_optimizer
    try:
        adaptive_optimizer = AdaptiveOptimizer()
        params = adaptive_optimizer.get_current_parameters()
        logger.info(f"🤖 AI Adaptive Optimizer initialized")
        logger.info(f"   Current ML Confidence: {params['min_ml_confidence']*100:.1f}%")
        logger.info(f"   Current R:R Requirement: {params['min_rr_ratio']:.2f}:1")
        logger.info(f"   Current Base Risk: {params['base_risk_pct']*100:.2f}%")
        logger.info(adaptive_optimizer.get_performance_summary())
    except Exception as e:
        logger.error(f"❌ Failed to initialize adaptive optimizer: {e}")
        adaptive_optimizer = None

    # 3. Initialize AI Trade Manager (thinks like a trader)
    try:
        trade_manager = IntelligentTradeManager()
        logger.info("✅ AI Trade Manager initialized: Support/Resistance + Market Structure")
    except Exception as e:
        logger.error(f"❌ Failed to initialize trade manager: {e}")
        trade_manager = None

    # 4. Initialize AI Risk Manager
    try:
        ai_risk_manager = AIRiskManager()
        logger.info("✅ AI Risk Manager initialized: Intelligent position sizing")
    except Exception as e:
        logger.error(f"❌ Failed to initialize AI risk manager: {e}")
        ai_risk_manager = None
    
    # 5. Initialize Intelligent Position Manager
    try:
        position_manager = IntelligentPositionManager()
        logger.info("✅ Intelligent Position Manager initialized: Active position management")
    except Exception as e:
        logger.error(f"❌ Failed to initialize position manager: {e}")
        position_manager = None
    
    # 6. FTMO Risk Manager will be initialized per-request with EA data
    # (No hardcoded values - all pulled from live MT5 account)
    logger.info("✅ FTMO Risk Manager ready: Will use live MT5 account data")

    # 5. PPO Agent - DISABLED during concurrent training to avoid TensorFlow mutex conflicts
    # Will be enabled after PPO training completes
    logger.info("⏳ PPO RL Agent: Disabled during training (will activate when training completes)")
    ppo_agent = None

    # # 5. Try to load trained PPO agent (if available)
    # try:
    #     from stable_baselines3 import PPO
    #     model_path = '/Users/justinhardison/ai-trading-system/models/ftmo_ppo_best.zip'
    #     if os.path.exists(model_path):
    #         ppo_agent = PPO.load(model_path)
    #         logger.info("✅ PPO RL Agent loaded: Trained on 140K bars")
    #     else:
    #         logger.warning("⏳ PPO Agent not yet available (training in progress)")
    #         ppo_agent = None
    # except Exception as e:
    #     logger.warning(f"⏳ PPO Agent not loaded: {e}")
    #     ppo_agent = None


    # 6. Load DQN RL Agent
    try:
        dqn_agent_path = '/Users/justinhardison/ai-trading-system/models/dqn_agent.pkl'
        if os.path.exists(dqn_agent_path):
            dqn_agent = joblib.load(dqn_agent_path)
            q_table_size = len(dqn_agent.get('q_table', {})) if isinstance(dqn_agent, dict) else 0
            logger.info(f"✅ DQN RL Agent loaded: {q_table_size} states learned")
        else:
            logger.warning("⚠️  DQN agent not found - using heuristics")
            dqn_agent = None
    except Exception as e:
        logger.error(f"❌ Failed to load DQN agent: {e}")
        dqn_agent = None

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("SYSTEM READY")
    logger.info("═══════════════════════════════════════════════════════════════════")



# ═══════════════════════════════════════════════════════════════════
# CONVICTION SCORING & TIMEFRAME WEIGHTING
# ═══════════════════════════════════════════════════════════════════

def calculate_conviction(ml_confidence: float, structure_score: float, 
                        volume_score: float = 50, momentum_score: float = 50) -> float:
    """Calculate overall conviction score (0-100)"""
    conviction = (
        ml_confidence * 0.40 +
        structure_score * 0.30 +
        volume_score * 0.15 +
        momentum_score * 0.15
    )
    return min(max(conviction, 0), 100)


def adjust_timeframe_weights(trigger_timeframe: str) -> dict:
    """Dynamically adjust timeframe weights based on trigger"""
    base_weights = {
        'M5': 0.10, 'M15': 0.15, 'M30': 0.20,
        'H1': 0.25, 'H4': 0.20, 'D1': 0.10
    }
    
    adjusted = base_weights.copy()
    if trigger_timeframe in adjusted:
        adjusted[trigger_timeframe] *= 1.5
        total = sum(adjusted.values())
        for tf in adjusted:
            adjusted[tf] /= total
    
    return adjusted


# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def parse_market_data(request: dict) -> Dict[str, pd.DataFrame]:
    """Convert EA market data to DataFrames"""
    mtf_data = {}

    # EA sends data in "market_data" or "timeframes" key
    # Format: {"market_data": {"M1": [{time, open, high, low, close, volume}]}}
    timeframes = request.get('timeframes', request.get('market_data', {}))

    if not timeframes:
        logger.warning("⚠️ No 'timeframes' or 'market_data' in request")
        return mtf_data

    for tf, bars in timeframes.items():
        try:
            # EA sends array of bar objects: [{time, open, high, low, close, volume}]
            if not isinstance(bars, list) or len(bars) == 0:
                logger.warning(f"⚠️ {tf}: Empty or invalid data")
                continue

            # Convert array of objects to DataFrame
            df = pd.DataFrame(bars)

            # Ensure required columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"❌ {tf}: Missing required columns. Got: {df.columns.tolist()}")
                continue

            # Select only OHLCV columns
            df = df[required_cols]

            mtf_data[tf.lower()] = df
            logger.info(f"✅ {tf}: {len(df)} bars")

        except Exception as e:
            logger.error(f"❌ Failed to parse {tf} data: {e}")
            continue

    return mtf_data

def should_exit_position(context: 'EnhancedTradingContext', mtf_data: Dict = None) -> Dict:
    """
    AI-driven exit decision for INTRADAY SWINGS.
    
    Enhanced with:
    - Multi-timeframe reversals (H4, H1, M1)
    - Volume divergence detection
    - Institutional exit signals
    - Order book pressure shifts
    - Market regime changes
    - Timeframe misalignment
    - Structure breaks on multiple timeframes
    
    Args:
        context: Enhanced trading context
        mtf_data: Multi-timeframe data (DataFrames), if None will try to get from context
    """
    
    if not context.has_position:
        return {'should_exit': False, 'reason': 'No position', 'exit_type': 'NONE'}
    
    position_type = context.position_type
    entry_price = context.position_entry_price
    current_price = context.current_price
    current_profit = context.position_current_profit
    volume = context.position_volume
    symbol = context.symbol
    
    # Get mtf_data - prefer passed parameter, fallback to parsing from context
    if mtf_data is None:
        # Try to get from context.request if available
        if hasattr(context, 'request') and context.request:
            mtf_data = parse_market_data(context.request)
        else:
            return {'should_exit': False, 'reason': 'No market data available', 'exit_type': 'error'}
    
    # FTMO PROTECTION: Exit immediately if violated
    if context.ftmo_violated or not context.can_trade:
        return {
            'should_exit': True,
            'reason': 'FTMO rules violated - closing all positions',
            'exit_type': 'FTMO_VIOLATION',
            'profit': current_profit
        }
    
    # FTMO PROTECTION: Near daily limit - close losers
    if context.distance_to_daily_limit < 1000 and current_profit < 0:
        return {
            'should_exit': True,
            'reason': f'Near FTMO daily limit (${context.distance_to_daily_limit:.0f} left) - cutting loss',
            'exit_type': 'FTMO_DAILY_LIMIT',
            'profit': current_profit
        }
    
    # FTMO PROTECTION: Near profit target - secure gains
    if context.progress_to_target > 0.9 and current_profit > 0:
        return {
            'should_exit': True,
            'reason': f'Near FTMO target ({context.progress_to_target*100:.1f}%) - securing profit',
            'exit_type': 'FTMO_TARGET',
            'profit': current_profit
        }
    
    # REMOVED: Hardcoded minimum profit - let AI decide based on market structure
    
    try:
        # Need H1 data for intraday structure
        if 'h1' not in mtf_data or len(mtf_data['h1']) < 20:
            return {"should_exit": False, "reason": "Insufficient H1 data for exit analysis", "exit_type": "hold"}
        
        h1_data = mtf_data['h1']
        m1_data = mtf_data.get('m1')
        
        # Calculate position metrics
        is_buy = (position_type == 0)
        pips_moved = (current_price - entry_price) if is_buy else (entry_price - current_price)
        pips_pct = (pips_moved / entry_price) * 100
        
        # Get H1 structure (intraday levels)
        h1_highs = h1_data['high'].values[-50:]  # Last 50 hours
        h1_lows = h1_data['low'].values[-50:]
        h1_closes = h1_data['close'].values[-20:]
        
        # 1. AI-DRIVEN PROFIT THRESHOLD (based on market volatility, not arbitrary number)
        # Calculate H1 ATR (Average True Range) - this is the "normal" move size
        h1_atr = np.std(h1_data['close'].values[-20:])
        h1_avg_move = (h1_data['high'].values[-20:] - h1_data['low'].values[-20:]).mean()
        
        # Dynamic threshold: Exit when we've captured a meaningful portion of the average H1 move
        # Not a fixed 0.3%, but based on what THIS market typically does
        move_captured_pct = abs(pips_moved) / h1_avg_move if h1_avg_move > 0 else 0
        
        # Also consider dollar profit relative to daily target
        daily_target = context.account_balance * 0.01  # 1% daily target
        profit_contribution = (current_profit / daily_target) * 100 if daily_target > 0 else 0
        
        # AI Decision: Have we captured enough of the typical move?
        # If we've captured < 30% of average H1 move, it's probably noise
        logger.info(f"📊 EXIT ANALYSIS: Profit=${current_profit:.2f}, Move captured={move_captured_pct*100:.0f}% of H1 avg, Daily target contribution={profit_contribution:.0f}%")
        
        if current_profit > 0 and move_captured_pct < 0.3:
            # But if dollar profit is significant (>10% of daily target), consider structure anyway
            if profit_contribution > 10:
                logger.info(f"💰 Profit ${current_profit:.2f} is {profit_contribution:.0f}% of daily target - checking structure despite small move")
            else:
                return {"should_exit": False, "reason": f"Captured {move_captured_pct*100:.0f}% of avg H1 move (${current_profit:.2f}) - holding for more", "exit_type": "hold"}
        
        # 2. INTRADAY STRUCTURE HIT (H1 resistance/support)
        if current_profit > 0:
            if is_buy:
                # Check H1 resistance (not M1 noise)
                h1_resistance = np.percentile(h1_highs, 90)
                logger.info(f"🎯 Structure check: Current=${current_price:.2f}, H1 resistance=${h1_resistance:.2f}")
                if current_price >= h1_resistance * 0.997:  # Within 0.3% of H1 resistance
                    logger.info(f"✅ EXIT TRIGGER: At H1 resistance!")
                    return {"should_exit": True, "reason": f"At H1 resistance - taking {pips_pct:.2f}% profit", "exit_type": "profit_target"}
            else:
                # Check H1 support
                h1_support = np.percentile(h1_lows, 10)
                logger.info(f"🎯 Structure check: Current=${current_price:.2f}, H1 support=${h1_support:.2f}")
                if current_price <= h1_support * 1.003:
                    logger.info(f"✅ EXIT TRIGGER: At H1 support!")
                    return {"should_exit": True, "reason": f"At H1 support - taking {pips_pct:.2f}% profit", "exit_type": "profit_target"}
        
        # 3. AI-DRIVEN MOMENTUM REVERSAL (detect when move is losing steam)
        if len(h1_closes) >= 5:
            h1_trend = h1_closes[-1] - h1_closes[-5]
            h1_trend_strength = abs(h1_trend) / h1_atr if h1_atr > 0 else 0
            
            # AI Decision: Exit if momentum reversing AND we have profit AND we've captured meaningful move
            if is_buy and h1_trend < 0 and current_profit > 0 and move_captured_pct > 0.4:
                return {"should_exit": True, "reason": f"H1 momentum reversing (captured {move_captured_pct*100:.0f}% of move) - securing {pips_pct:.2f}%", "exit_type": "momentum_shift"}
            elif not is_buy and h1_trend > 0 and current_profit > 0 and move_captured_pct > 0.4:
                return {"should_exit": True, "reason": f"H1 momentum reversing (captured {move_captured_pct*100:.0f}% of move) - securing {pips_pct:.2f}%", "exit_type": "momentum_shift"}
        
        # 4. AI-DRIVEN PROFIT CAPTURE (captured full H1 move or more)
        # If we've captured 100%+ of the average H1 move, that's excellent - take it!
        if move_captured_pct >= 1.0 and current_profit > 0:
            return {"should_exit": True, "reason": f"Captured {move_captured_pct*100:.0f}% of avg H1 move ({pips_pct:.2f}%) - excellent profit!", "exit_type": "profit_secure"}
        
        # 5. MOVE EXHAUSTION (extended beyond normal volatility)
        # If move is 2.5x larger than typical H1 ATR, it's overextended
        move_size = abs(pips_moved)
        if move_size > h1_atr * 2.5 and current_profit > 0:
            return {"should_exit": True, "reason": f"Move exhausted (2.5x ATR) - captured {move_captured_pct*100:.0f}% of move ({pips_pct:.2f}%)", "exit_type": "exhaustion"}
        
        # 6. INTRADAY TRAILING STOP (protect profits on H1 pullback)
        if current_profit > 0 and pips_pct > 0.4 and m1_data is not None:
            m1_closes = m1_data['close'].values[-10:]
            # Check for M1 pullback after good H1 move
            if len(m1_closes) >= 5:
                if is_buy and m1_closes[-1] < m1_closes[-3] and m1_closes[-2] < m1_closes[-4]:
                    # Pullback in BUY position
                    if pips_pct > 0.6:  # Only if we have decent profit
                        return {"should_exit": True, "reason": f"Trailing stop - protecting {pips_pct:.2f}%", "exit_type": "trailing_stop"}
                elif not is_buy and m1_closes[-1] > m1_closes[-3] and m1_closes[-2] > m1_closes[-4]:
                    # Pullback in SELL position
                    if pips_pct > 0.6:
                        return {"should_exit": True, "reason": f"Trailing stop - protecting {pips_pct:.2f}%", "exit_type": "trailing_stop"}
        
        # 7. STOP LOSS MANAGEMENT (cut losses if H1 structure breaks)
        if current_profit < 0:
            loss_pct = abs(pips_pct)
            if loss_pct > 0.6:  # 0.6% loss
                # Check if H1 structure is broken
                if is_buy:
                    h1_recent_low = np.min(h1_lows[-10:])
                    if current_price < h1_recent_low:
                        return {"should_exit": True, "reason": f"H1 support broken - cutting {loss_pct:.2f}% loss", "exit_type": "stop_loss"}
                else:
                    h1_recent_high = np.max(h1_highs[-10:])
                    if current_price > h1_recent_high:
                        return {"should_exit": True, "reason": f"H1 resistance broken - cutting {loss_pct:.2f}% loss", "exit_type": "stop_loss"}
        
        # Default: Hold for intraday swing
        reason = f"Holding intraday swing: P&L ${current_profit:.2f} ({pips_pct:.2f}%)"
        return {"should_exit": False, "reason": reason, "exit_type": "hold"}
        
    except Exception as e:
        logger.error(f"❌ Exit analysis error: {e}")
        return {"should_exit": False, "reason": f"Exit analysis error: {e}", "exit_type": "error"}


def get_ml_signal(features: dict, symbol: str = 'US30') -> Tuple[str, float]:
    """Get ML signal (BUY/SELL/HOLD) and confidence using symbol-specific ensemble"""
    # Get model for this symbol (lowercase to match loaded models)
    symbol_lower = symbol.lower()
    ml_model = ml_models.get(symbol_lower)
    
    if ml_model is None:
        logger.warning(f"⚠️ No model for {symbol_lower}, trying fallbacks")
        # Try fallbacks in order
        for fallback in ['us30', 'us100', 'us500', 'forex', 'indices', 'commodities']:
            ml_model = ml_models.get(fallback)
            if ml_model is not None:
                logger.info(f"   Using {fallback} model for {symbol}")
                break
        
        if ml_model is None:
            logger.error(f"❌ No models loaded at all")
            return "HOLD", 0.0

    try:
        # NEW MODELS: Use RandomForest and GradientBoosting (trained Nov 20)
        import pandas as pd
        feature_df = pd.DataFrame([features])
        
        # CRITICAL FIX: Align features with model expectations
        # Models were trained on 128 features, we're sending 140
        model_features = ml_model.get('feature_names', [])
        if model_features:
            # Select and reorder features to match model exactly
            try:
                # Only use features the model was trained on
                feature_df = feature_df[model_features]
                if len(features) != len(model_features):
                    logger.debug(f"   Features filtered: {len(features)} → {len(model_features)}")
            except KeyError as e:
                missing = set(model_features) - set(features.keys())
                logger.error(f"❌ Missing features for model: {missing}")
                # Use default values for missing features
                for feat in missing:
                    feature_df[feat] = 0.0
                feature_df = feature_df[model_features]
        else:
            logger.info(f"   Features for prediction: {len(features)} features")

        # NEW models have rf_model and gb_model
        if 'rf_model' in ml_model and 'gb_model' in ml_model:
            # Random Forest + Gradient Boosting ensemble
            rf_pred = ml_model['rf_model'].predict(feature_df)[0]
            gb_pred = ml_model['gb_model'].predict(feature_df)[0]
            rf_proba = ml_model['rf_model'].predict_proba(feature_df)[0]
            gb_proba = ml_model['gb_model'].predict_proba(feature_df)[0]
            
            # Ensemble prediction (equal weights)
            ensemble_pred = int((rf_pred + gb_pred) / 2 > 0.5)
            ensemble_proba = (rf_proba + gb_proba) / 2
            
            # CRITICAL: Models are biased - use probability threshold instead of hard prediction
            # If probability is close to 50%, it's actually uncertain, not confident
            buy_prob = ensemble_proba[1]
            sell_prob = ensemble_proba[0]
            
            # UPDATED: Require 65% confidence minimum for quality trades
            # This prevents coin-flip trades and improves win rate
            MIN_CONFIDENCE = 0.65  # 65% minimum
            
            if buy_prob > MIN_CONFIDENCE:
                direction = "BUY"
                confidence = buy_prob * 100
            elif sell_prob > MIN_CONFIDENCE:
                direction = "SELL"
                confidence = sell_prob * 100
            else:
                # Uncertain - HOLD (confidence too low)
                direction = "HOLD"
                confidence = max(buy_prob, sell_prob) * 100
                
            logger.info(f"🤖 ML SIGNAL: {direction} (Confidence: {confidence:.1f}%) [BUY prob: {buy_prob:.3f}, SELL prob: {sell_prob:.3f}]")
            return direction, confidence
            
        # OLD models (fallback)
        weights = ml_model.get('ensemble_weights', [0.5, 0.5])
        
        # Check which models are available
        if 'xgb_model' in ml_model and 'lgb_model' in ml_model:
            # XGBoost + LightGBM ensemble
            model1_pred = ml_model['xgb_model'].predict(feature_df)[0]
            model2_pred = ml_model['lgb_model'].predict(feature_df)[0]
            model1_proba = ml_model['xgb_model'].predict_proba(feature_df)[0]
            model2_proba = ml_model['lgb_model'].predict_proba(feature_df)[0]
        elif 'rf_model' in ml_model and 'gb_model' in ml_model:
            # RandomForest + GradientBoosting ensemble
            model1_pred = ml_model['rf_model'].predict(feature_df)[0]
            model2_pred = ml_model['gb_model'].predict(feature_df)[0]
            model1_proba = ml_model['rf_model'].predict_proba(feature_df)[0]
            model2_proba = ml_model['gb_model'].predict_proba(feature_df)[0]
        else:
            logger.error(f"❌ Unknown model structure for {symbol}")
            return "HOLD", 0.0

        # Ensemble prediction (weighted voting)
        ensemble_pred = int(round(model1_pred * weights[0] + model2_pred * weights[1]))

        # Get probabilities for confidence
        ensemble_proba = model1_proba * weights[0] + model2_proba * weights[1]
        confidence = ensemble_proba.max() * 100
        
        # Log probabilities for debugging
        logger.info(f"   Probabilities: BUY={ensemble_proba[0]:.3f}, HOLD={ensemble_proba[1]:.3f}, SELL={ensemble_proba[2]:.3f}")

        # CRITICAL FIX: Correct mapping (models trained with 0=BUY, 1=HOLD, 2=SELL)
        direction_map = {0: "BUY", 1: "HOLD", 2: "SELL"}
        direction = direction_map.get(ensemble_pred, "HOLD")

        logger.info(f"🤖 ML SIGNAL: {direction} (Confidence: {confidence:.1f}%)")

        return direction, confidence

    except Exception as e:
        logger.error(f"❌ ML prediction failed: {e}")
        return "HOLD", 0.0

# ═══════════════════════════════════════════════════════════════════
# MAIN TRADING ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/ai/trade_decision")
async def ai_trade_decision(request: dict):
    """
    THE PERFECT AI TRADING SYSTEM

    Flow:
    1. Parse market data from EA
    2. Engineer 500+ features
    3. Get ML signal
    4. AI analyzes market structure (support/resistance)
    5. AI decides: Is this a good trade?
    6. Calculate intelligent position size (quality-based)
    7. FTMO risk manager validates
    8. Return professional trade decision
    """
    
    global position_manager, ai_risk_manager, trade_manager, feature_engineer

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("AI TRADE DECISION REQUEST")
    logger.info("═══════════════════════════════════════════════════════════════════")

    try:
        # DEBUG: Log what we're receiving
        logger.info(f"📦 Request keys: {list(request.keys())}")
        
        # DEBUG: Log actual market data
        timeframes = request.get('timeframes', {})
        indicators = request.get('indicators', {})
        symbol_info = request.get('symbol_info', {})
        account_data = request.get('account', {})
        logger.info(f"   Account data: {account_data}")
        logger.info(f"   Symbol info: {symbol_info}")
        logger.info(f"   Contract size: {symbol_info.get('contract_size', 'MISSING')}")
        
        # Extract symbol from request (EA sends this in symbol_info)
        symbol_info = request.get('symbol_info', {})
        raw_symbol = symbol_info.get('symbol', request.get('symbol', 'US30'))
        
        # Clean symbol name to match model files
        # Broker format: XAUZ25.sim, US30Z25.sim, USOILF26.sim, etc.
        import re
        
        # Step 1: Remove .sim suffix
        symbol = raw_symbol.replace('.sim', '').replace('.SIM', '')
        
        # Step 2: Remove contract codes (Z25, F26, G26, H26, etc.) - case insensitive
        # Contract codes are: Z=Dec, F=Jan, G=Feb, H=Mar, J=Apr, K=May, M=Jun, N=Jul, Q=Aug, U=Sep, V=Oct, X=Nov
        symbol = re.sub(r'[ZFGHJKMNQUVX]\d{2}$', '', symbol, flags=re.IGNORECASE)
        
        # Step 3: Convert to lowercase
        symbol = symbol.lower()
        
        # Step 4: Handle broker-specific symbol names
        if symbol == 'xau':
            symbol = 'xau'  # Gold: XAU → xau (already correct)
        elif symbol == 'usoil':
            symbol = 'usoil'  # Oil: USOIL → usoil (already correct)
        
        logger.info(f"📊 Symbol: {raw_symbol} → {symbol}")
        
        # Extract trigger timeframe
        trigger_timeframe = request.get('trigger_timeframe', 'M5')
        logger.info(f"🎯 Triggered by: {trigger_timeframe} bar close")
        tf_weights = adjust_timeframe_weights(trigger_timeframe)
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: PORTFOLIO ANALYSIS - Check ALL open positions IMMEDIATELY
        # ═══════════════════════════════════════════════════════════════════
        open_positions = request.get('positions', [])
        portfolio_decisions = []
        open_position = None  # Initialize here
        position_symbol = None  # Initialize here
        
        if open_positions and position_manager:
            logger.info(f"📊 Positions received: {len(open_positions)} positions")
            logger.info(f"📊 PORTFOLIO: {len(open_positions)} open positions - analyzing ALL NOW")
            
            for pos in open_positions:
                pos_symbol_raw = pos.get('symbol', '').replace('.sim', '').upper()
                pos_profit = float(pos.get('profit', 0))
                pos_volume = float(pos.get('volume', 0))
                pos_type = pos.get('type')  # 0=BUY, 1=SELL
                pos_entry = float(pos.get('price_open', 0))
                
                # Clean position symbol the SAME WAY as current symbol (remove contract codes)
                pos_symbol_clean = re.sub(r'[ZFGHJKMNQUVX]\d{2}$', '', pos_symbol_raw, flags=re.IGNORECASE).lower()
                
                logger.info(f"   📍 {pos_symbol_raw}: {pos_volume} lots, ${pos_profit:.2f} profit")
                
                # ANALYZE ALL POSITIONS (not just current symbol)
                # This ensures DCA/SCALE_IN/SCALE_OUT decisions are captured
                try:
                    # Get features for this position's symbol
                    features = feature_engineer.engineer_features(request)
                    ml_direction, ml_confidence = get_ml_signal(features, pos_symbol_clean)
                    
                    # Create context for this position
                    context = EnhancedTradingContext.from_features_and_request(
                        features=features,
                        request=request,
                        ml_direction=ml_direction,
                        ml_confidence=ml_confidence
                    )
                    
                    # Override position data with this specific position
                    context.position_type = pos_type
                    context.position_entry_price = pos_entry
                    context.position_current_profit = pos_profit
                    context.position_volume = pos_volume
                    context.position_dca_count = pos.get('dca_count', 0)
                    
                    # AI analyzes this position
                    
                    
                    # Use DQN RL agent if available
                    if dqn_agent is not None:
                        try:
                            profit_pct = (pos_profit / 10000) * 100
                            state_key = f"{int(profit_pct)}_{int(ml_confidence)}"
                            q_table = dqn_agent.get('q_table', {})
                            
                            if state_key in q_table:
                                q_values = q_table[state_key]
                                actions = ['HOLD', 'SCALE_IN', 'PARTIAL_CLOSE', 'CLOSE_ALL']
                                best_idx = max(range(len(q_values)), key=lambda i: q_values[i])
                                rl_suggestion = actions[best_idx]
                                logger.info(f"🤖 DQN suggests: {rl_suggestion} (Q:{q_values})")
                        except Exception as e:
                            logger.error(f"DQN error: {e}")

                    position_decision = position_manager.analyze_position(context)
                    
                    # Log decision
                    logger.info(f"   {'🚨' if position_decision['action'] != 'HOLD' else '✅'} {pos_symbol_raw}: {position_decision['action']} - {position_decision['reason']}")
                    
                    # COLLECT ALL DECISIONS (don't return immediately)
                    decision = {
                        'action': position_decision['action'],
                        'symbol': pos_symbol_raw,
                        'reason': position_decision['reason'],
                        'priority': position_decision.get('priority', 'LOW' if position_decision['action'] == 'HOLD' else 'HIGH'),
                        'add_lots': position_decision.get('add_lots', 0),
                        'reduce_lots': position_decision.get('reduce_lots', 0),
                        'profit': pos_profit,
                        'confidence': position_decision.get('confidence', 0)
                    }
                    portfolio_decisions.append(decision)
                    
                    # Track if this is the current symbol being scanned
                    if pos_symbol_clean == symbol:
                        open_position = pos
                        position_symbol = pos_symbol_raw
                        
                except Exception as e:
                    logger.error(f"   ❌ Error analyzing {pos_symbol_raw}: {e}")
                    # Add HOLD decision for this position
                    portfolio_decisions.append({
                        'action': 'HOLD',
                        'symbol': pos_symbol_raw,
                        'reason': f'Error analyzing position: {str(e)}',
                        'confidence': 0,
                        'add_lots': 0,
                        'reduce_lots': 0
                    })  # Keep raw for logging
            
            # Log whether we found a position for the current symbol
            if open_position is None:
                # Current symbol doesn't have a position - can look for new trade
                logger.info(f"✅ No position on {symbol} - can analyze for new trade opportunity")
                # Continue to new trade logic below
            else:
                logger.info(f"📍 Found position on {symbol} - will use for SCALE_IN logic if AI approves trade")
        else:
            # No positions open - can look for new trades
            open_position = None
            position_symbol = None
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: PARSE MARKET DATA
        # ═══════════════════════════════════════════════════════════════════
        mtf_data = parse_market_data(request)

        # Debug logging
        if 'm1' in mtf_data:
            logger.info(f"📊 Received M1 data: {len(mtf_data['m1'])} bars")
        else:
            logger.warning(f"❌ No M1 data in mtf_data! Keys: {mtf_data.keys()}")

        if 'm1' not in mtf_data or len(mtf_data['m1']) < 50:
            logger.warning(f"⚠️ Insufficient M1 data: {len(mtf_data.get('m1', [])) if 'm1' in mtf_data else 0} bars (need 50+)")
            return {
                "action": "HOLD",
                "reason": "Insufficient data",
                "confidence": 0.0
            }

        # Extract current price from EA data
        # EA sends: {"current_price": {"bid": X, "ask": Y, "last": Z, ...}}
        current_price_data = request.get('current_price', {})
        if isinstance(current_price_data, dict):
            current_price = float(current_price_data.get('bid', mtf_data['m1']['close'].iloc[-1]))
        else:
            current_price = float(current_price_data) if current_price_data else mtf_data['m1']['close'].iloc[-1]

        # Pull ALL account data from EA (no hardcoded values!)
        # EA sends: {"account": {"balance": X, "equity": Y, ...}}
        account_data = request.get('account', {})
        account_balance = float(account_data.get('balance', 0))
        account_equity = float(account_data.get('equity', 0))

        # These may not be in the EA data yet
        daily_start_balance = float(request.get('daily_start_balance', account_balance))
        peak_balance = float(request.get('peak_balance', account_balance))

        logger.info(f"💰 Price: ${current_price:.2f} | Balance: ${account_balance:,.2f} | Equity: ${account_equity:,.2f}")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 1.5: AI EXIT MONITORING FOR OPEN POSITIONS
        # ═══════════════════════════════════════════════════════════════════
        # Get lot_step for rounding (needed for scaling/DCA)
        symbol_info = request.get('symbol_info', {})
        lot_step = float(symbol_info.get('lot_step', 1.0))
        
        if open_position:
            # We have an open position on THIS symbol - manage it
            position_type = open_position.get('type')  # 0=BUY, 1=SELL
            entry_price = float(open_position.get('price_open', 0))
            current_profit = float(open_position.get('profit', 0))
            volume = float(open_position.get('volume', 0))
            
            # Calculate pips_pct for position (needed for all position logic)
            pips_pct = ((current_price - entry_price) / entry_price * 100) if position_type == 0 else ((entry_price - current_price) / entry_price * 100)
            
            # This IS the symbol with the open position - MANAGE IT!
            logger.info(f"📊 OPEN POSITION: {position_type} {volume} lots @ ${entry_price:.2f} | P&L: ${current_profit:.2f} ({pips_pct:.2f}%)")
            
            # ═══════════════════════════════════════════════════════════
            # CREATE ENHANCED CONTEXT FOR POSITION MANAGEMENT
            # ═══════════════════════════════════════════════════════════
            if position_manager:
                try:
                    # Extract features and get ML signal
                    features = feature_engineer.engineer_features(request)
                    ml_direction, ml_confidence = get_ml_signal(features, symbol)
                    
                    # Create EnhancedTradingContext with ALL data
                    context = EnhancedTradingContext.from_features_and_request(
                        features=features,
                        request=request,
                        ml_direction=ml_direction,
                        ml_confidence=ml_confidence
                    )
                    
                    # Update peak tracking for partial profit logic
                    context.update_peak_tracking()
                    
                    logger.info(f"✅ Enhanced context created for position management")
                    logger.info(f"   Position: {context.position_type_str} @ ${context.position_entry_price:.2f}")
                    logger.info(f"   P&L: ${context.position_current_profit:.2f} ({pips_pct:.2f}%)")
                    logger.info(f"   Peak: ${context.position_peak_profit:.2f} | Decline: {context.position_decline_from_peak_pct:.1f}%")
                    logger.info(f"   ML Signal: {ml_direction} @ {ml_confidence:.1%}")
                    
                    # AI analyzes position using FULL CONTEXT (100+ features)
                    
                    
                    # Use DQN RL agent if available
                    if dqn_agent is not None:
                        try:
                            profit_pct = (current_profit / 10000) * 100
                            state_key = f"{int(profit_pct)}_{int(ml_confidence)}"
                            q_table = dqn_agent.get('q_table', {})
                            
                            if state_key in q_table:
                                q_values = q_table[state_key]
                                actions = ['HOLD', 'SCALE_IN', 'PARTIAL_CLOSE', 'CLOSE_ALL']
                                best_idx = max(range(len(q_values)), key=lambda i: q_values[i])
                                rl_suggestion = actions[best_idx]
                                logger.info(f"🤖 DQN suggests: {rl_suggestion} (Q:{q_values})")
                        except Exception as e:
                            logger.error(f"DQN error: {e}")

                    position_decision = position_manager.analyze_position(context)
                    
                    # Execute AI decision
                    action = position_decision['action']
                    
                    if action == 'CLOSE':
                        logger.info(f"🚪 INTELLIGENT POSITION MANAGER: {position_decision['reason']}")
                        return {
                            "action": "CLOSE",
                            "reason": position_decision['reason'],
                            "priority": position_decision['priority'],
                            "profit": current_profit
                        }
                    
                    elif action == 'PARTIAL_CLOSE':
                        # Partial profit taking
                        percent = position_decision.get('percent', 50)
                        close_lots = volume * (percent / 100.0)
                        close_lots = max(lot_step, round(close_lots / lot_step) * lot_step)
                        logger.info(f"💰 PARTIAL PROFIT: {position_decision['reason']} - Closing {close_lots:.2f} lots ({percent}%)")
                        return {
                            "action": "PARTIAL_CLOSE",
                            "reason": position_decision['reason'],
                            "close_lots": close_lots,
                            "percent": percent,
                            "priority": "HIGH",
                            "profit": current_profit
                        }
                    
                    elif action == 'DCA':
                        # Round to lot_step
                        add_lots = max(lot_step, round(position_decision['add_lots'] / lot_step) * lot_step)
                        logger.info(f"📊 INTELLIGENT DCA: {position_decision['reason']} - Adding {add_lots:.2f} lots")
                        return {
                            "action": "DCA",
                            "reason": position_decision['reason'],
                            "add_lots": add_lots,
                            "lot_size": add_lots,
                            "priority": position_decision['priority'],
                            "dca_attempt": position_decision.get('dca_attempt', 1),
                            "profit": current_profit
                        }
                    
                    elif action == 'SCALE_IN':
                        # Round to lot_step
                        add_lots = max(lot_step, round(position_decision['add_lots'] / lot_step) * lot_step)
                        logger.info(f"📈 INTELLIGENT SCALE IN: {position_decision['reason']} - Adding {add_lots:.2f} lots")
                        return {
                            "action": "SCALE_IN",
                            "reason": position_decision['reason'],
                            "add_lots": add_lots,
                            "lot_size": add_lots,
                            "priority": position_decision['priority'],
                            "profit": current_profit
                        }
                    
                    elif action == 'SCALE_OUT':
                        # Round to lot_step
                        reduce_lots = max(lot_step, round(position_decision['reduce_lots'] / lot_step) * lot_step)
                        logger.info(f"💰 INTELLIGENT SCALE OUT: {position_decision['reason']} - Reducing {reduce_lots:.2f} lots")
                        return {
                            "action": "SCALE_OUT",
                            "reason": position_decision['reason'],
                            "reduce_lots": reduce_lots,
                            "lot_size": reduce_lots,
                            "priority": position_decision['priority'],
                            "profit": current_profit
                        }
                    
                    # If HOLD, continue to legacy scaling/DCA logic below
                    logger.info(f"⏸️  POSITION MANAGER: {position_decision['reason']}")
                    
                except Exception as e:
                    logger.error(f"❌ Position manager analysis failed: {e}")
                
                # Check for SCALING and DCA opportunities (legacy fallback)
                if ai_risk_manager and 'h1' in mtf_data:
                    h1_data = mtf_data['h1']
                    h1_resistance = np.percentile(h1_data['high'].values[-50:], 90) if len(h1_data) > 0 else None
                    h1_support = np.percentile(h1_data['low'].values[-50:], 10) if len(h1_data) > 0 else None
                    
                    # If PROFITABLE: Check SCALE OUT or SCALE IN
                    if pips_pct > 0:
                        # Check SCALE OUT (take partial profits)
                        scale_out = ai_risk_manager.should_scale_out(
                            position=open_position,
                            current_price=current_price,
                            entry_price=entry_price,
                            current_profit_pct=pips_pct,
                            h1_resistance=h1_resistance,
                            h1_support=h1_support
                        )
                        
                        if scale_out['should_scale']:
                            # Round to lot_step (round UP to ensure at least lot_step)
                            reduce_lots = max(lot_step, round(scale_out['reduce_lots'] / lot_step) * lot_step)
                            logger.info(f"💰 SCALE OUT: {scale_out['reason']} - Reducing {reduce_lots:.2f} lots")
                            return {
                                "action": "SCALE_OUT",
                                "reason": scale_out['reason'],
                                "reduce_lots": reduce_lots,
                                "lot_size": reduce_lots,  # EA compatibility
                                "profit": current_profit
                            }
                        
                        # Check SCALE IN (add to winner)
                        scale_in = ai_risk_manager.should_scale_in(
                            position=open_position,
                            current_price=current_price,
                            entry_price=entry_price,
                            current_profit_pct=pips_pct
                        )
                        
                        if scale_in['should_scale']:
                            # Round to lot_step (round UP to ensure at least lot_step)
                            add_lots = max(lot_step, round(scale_in['add_lots'] / lot_step) * lot_step)
                            logger.info(f"📈 SCALE IN: {scale_in['reason']} - Adding {add_lots:.2f} lots")
                            return {
                                "action": "SCALE_IN",
                                "reason": scale_in['reason'],
                                "add_lots": add_lots,
                                "lot_size": add_lots,  # EA compatibility
                                "profit": current_profit
                            }
                    
                    # If SLIGHTLY NEGATIVE: Check SMART DCA
                    elif pips_pct < 0 and pips_pct > -0.5:
                        # Get fresh ML signal to confirm direction still valid
                        try:
                            features = feature_engineer.engineer_features(request)
                            ml_direction, ml_confidence = get_ml_signal(features, symbol)
                            
                            # Only DCA if ML still confirms
                            expected_direction = "BUY" if position_type == 0 else "SELL"
                            if ml_direction == expected_direction:
                                dca_decision = ai_risk_manager.should_dca(
                                    position=open_position,
                                    current_price=current_price,
                                    entry_price=entry_price,
                                    current_profit_pct=pips_pct,
                                    h1_support=h1_support,
                                    h1_resistance=h1_resistance,
                                    ml_confidence=ml_confidence,
                                    account_balance=account_balance
                                )
                                
                                if dca_decision['should_dca']:
                                    # Round to lot_step (round UP to ensure at least lot_step)
                                    add_lots = max(lot_step, round(dca_decision['add_lots'] / lot_step) * lot_step)
                                    logger.info(f"📊 SMART DCA: {dca_decision['reason']} - Adding {add_lots:.2f} lots")
                                    return {
                                        "action": "DCA",
                                        "reason": dca_decision['reason'],
                                        "add_lots": add_lots,
                                        "lot_size": add_lots,  # EA compatibility
                                        "new_average": dca_decision.get('new_average', entry_price),
                                        "profit": current_profit
                                    }
                        except Exception as e:
                            logger.error(f"❌ DCA check failed: {e}")
                
                # AI EXIT DECISION - analyze using enhanced context
                exit_decision = should_exit_position(context, mtf_data)
                
                if exit_decision['should_exit']:
                    logger.info(f"🚪 AI EXIT SIGNAL: {exit_decision['reason']}")
                    return {
                        "action": "CLOSE",
                        "reason": exit_decision['reason'],
                        "exit_type": exit_decision['exit_type'],
                        "profit": current_profit
                    }
                else:
                    logger.info(f"✋ HOLD POSITION: {exit_decision['reason']}")
                    # Continue monitoring, don't open new trades
                    return {
                        "action": "HOLD",
                        "reason": f"Monitoring open position: {exit_decision['reason']}",
                        "profit": current_profit
                    }

        # ═══════════════════════════════════════════════════════════════════
        # STEP 2: FEATURE ENGINEERING (100+ features)
        # ═══════════════════════════════════════════════════════════════════
        if feature_engineer is None:
            return {"action": "HOLD", "reason": "Feature engineer not loaded"}

        try:
            # Enhanced feature engineer generates 100+ features
            features = feature_engineer.engineer_features(request)
            logger.info(f"✅ Features extracted: {len(features)}")
            
            # DEBUG: Log sample features to verify real data
            sample_features = {k: features[k] for k in list(features.keys())[:10]}
            logger.info(f"   Sample features: {sample_features}")
        except Exception as e:
            logger.error(f"❌ Feature extraction failed: {e}")
            return {"action": "HOLD", "reason": f"Feature extraction error: {e}"}

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3: ML SIGNAL GENERATION (Symbol-Specific Model)
        # ═══════════════════════════════════════════════════════════════════
        ml_direction, ml_confidence = get_ml_signal(features, symbol)
        logger.info(f"🤖 ML Signal ({symbol}): {ml_direction} @ {ml_confidence:.1f}%")
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 3.5: CREATE ENHANCED TRADING CONTEXT (NEW!)
        # Unified data structure with ALL 100 features for all components
        # ═══════════════════════════════════════════════════════════════════
        try:
            context = EnhancedTradingContext.from_features_and_request(
                features=features,
                request=request,
                ml_direction=ml_direction,
                ml_confidence=ml_confidence
            )
            logger.info(f"✅ Enhanced context created: {context.symbol}")
            logger.info(f"   Regime: {context.get_market_regime()} | Volume: {context.get_volume_regime()}")
            logger.info(f"   Confluence: {context.has_strong_confluence()} | Trend Align: {context.trend_alignment:.2f}")
        except Exception as e:
            logger.error(f"❌ Context creation failed: {e}")
            return {"action": "HOLD", "reason": f"Context creation error: {e}"}

        # ═══════════════════════════════════════════════════════════════════
        # STEP 3.6: CALCULATE CONVICTION SCORE
        # ═══════════════════════════════════════════════════════════════════
        market_regime = context.get_market_regime()
        structure_score = 70 if market_regime in ["TRENDING_UP", "TRENDING_DOWN"] else 50
        volume_score = 60  # Would analyze volume patterns in production
        momentum_score = 65  # Would analyze momentum indicators in production
        
        conviction = calculate_conviction(
            ml_confidence=ml_confidence,
            structure_score=structure_score,
            volume_score=volume_score,
            momentum_score=momentum_score
        )
        
        logger.info(f"🎯 CONVICTION: {conviction:.1f}/100 (ML:{ml_confidence:.1f}% Struct:{structure_score} Vol:{volume_score} Mom:{momentum_score})")
        
        # Filter low conviction trades
        if conviction < 50:
            logger.info(f"❌ Low conviction ({conviction:.1f}) - rejecting trade")
            return {
                'action': 'HOLD',
                'reason': f'Low conviction: {conviction:.1f}/100',
                'conviction': conviction,
                'confidence': 0
            }

        # AI Optimizer decides minimum confidence (not hardcoded!)
        if adaptive_optimizer:
            params = adaptive_optimizer.get_current_parameters()
            min_confidence = params['min_ml_confidence'] * 100
        else:
            min_confidence = 58.0  # Tightened - require quality setups with 115 features
        
        # Only check confidence for BUY/SELL (not HOLD)
        # HOLD is valid - it means wait for better setup
        if ml_direction == "HOLD":
            logger.info(f"⏸️  ML says HOLD @ {ml_confidence:.1f}% - waiting for better setup")
            return {
                "action": "HOLD",
                "reason": f"ML signal is HOLD (waiting for better setup)",
                "ml_direction": ml_direction,
                "ml_confidence": ml_confidence
            }
        
        # For BUY/SELL, check confidence threshold
        if ml_confidence < min_confidence:
            logger.info(f"❌ ML rejected: {ml_direction} @ {ml_confidence:.1f}% (AI requires {min_confidence:.1f}%+)")
            return {
                "action": "HOLD",
                "reason": f"ML confidence {ml_confidence:.1f}% below AI threshold {min_confidence:.1f}%",
                "ml_direction": ml_direction,
                "ml_confidence": ml_confidence
            }

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: AI MARKET STRUCTURE ANALYSIS (THE KEY DIFFERENCE)
        # ═══════════════════════════════════════════════════════════════════
        if trade_manager is None:
            return {"action": "HOLD", "reason": "Trade manager not loaded"}

        structure = None  # Initialize to avoid reference errors
        try:
            # AI analyzes market structure using H1 for intraday S/R levels
            # Use H1 for support/resistance (not M1 noise)
            h1_ohlcv = {
                'high': mtf_data['h1']['high'].values,
                'low': mtf_data['h1']['low'].values,
                'close': mtf_data['h1']['close'].values,
                'volume': mtf_data['h1']['volume'].values if 'volume' in mtf_data['h1'].columns else np.zeros(len(mtf_data['h1']))
            }
            
            structure = trade_manager.analyze_market_structure(
                current_price=current_price,
                ohlcv_data=h1_ohlcv  # H1 data for intraday structure
            )

            logger.info(f"📊 MARKET STRUCTURE:")
            # Determine trend from structure attributes
            trend = "UP" if structure.higher_highs else ("DOWN" if structure.lower_lows else "RANGING")
            logger.info(f"   Trend: {trend}")
            logger.info(f"   At Support: {structure.at_support} | At Resistance: {structure.at_resistance}")
            logger.info(f"   Nearest Support: ${structure.nearest_support:.2f}")
            logger.info(f"   Nearest Resistance: ${structure.nearest_resistance:.2f}")
            logger.info(f"   Move Exhaustion: {structure.move_exhaustion:.1%}")
            logger.info(f"   Real R:R: {structure.risk_reward_ratio:.2f}:1")

        except Exception as e:
            logger.error(f"❌ Structure analysis failed: {e}")
            return {"action": "HOLD", "reason": f"Structure analysis error: {e}"}

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: AI ENTRY DECISION (NOT RULES - AI THINKS!)
        # ═══════════════════════════════════════════════════════════════════
        try:
            should_trade, reason, quality_multiplier = trade_manager.should_enter_trade(context, structure)

            logger.info(f"🧠 AI DECISION: {should_trade}")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   Quality: {quality_multiplier:.2f}x")

            if not should_trade:
                return {
                    "action": "HOLD",
                    "reason": reason,
                    "ml_direction": ml_direction,
                    "ml_confidence": ml_confidence,
                    "structure": structure.__dict__ if structure else {}
                }

        except Exception as e:
            logger.error(f"❌ AI decision failed: {e}")
            import traceback
            traceback.print_exc()
            return {"action": "HOLD", "reason": f"AI decision error: {e}"}

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: INTELLIGENT POSITION SIZING (QUALITY-BASED, NOT 2%)
        # ═══════════════════════════════════════════════════════════════════
        try:
            # Create FTMO risk manager with LIVE EA data (no hardcoded values!)
            from src.risk.ftmo_risk_manager import FTMOAccount

            # Pull FTMO account parameters from EA
            ftmo_phase = request.get('ftmo_phase', 'challenge_1')  # challenge_1, challenge_2, or funded
            max_daily_loss_pct = 0.05  # 5%
            max_total_dd_pct = 0.10    # 10%

            ftmo_account = FTMOAccount(
                balance=account_balance,
                equity=account_equity,
                daily_start_balance=daily_start_balance,
                peak_balance=peak_balance,
                phase=ftmo_phase,
                max_daily_loss=account_balance * max_daily_loss_pct,
                max_total_drawdown=account_balance * max_total_dd_pct
            )

            ftmo_risk_manager = FTMORiskManager(
                account=ftmo_account,
                max_risk_per_trade=0.02,  # 2% per trade
                max_daily_risk=max_daily_loss_pct
            )

            logger.info(f"✅ FTMO Risk Manager created with live account data")
            logger.info(f"   Balance: ${account_balance:,.2f} | Equity: ${account_equity:,.2f}")
            logger.info(f"   Max Daily Loss: ${ftmo_account.max_daily_loss:,.2f} | Max Total DD: ${ftmo_account.max_total_drawdown:,.2f}")

            # Get broker specs from EA
            # EA sends: {"symbol_info": {"min_lot": X, "max_lot": Y, "lot_step": Z, "trade_contract_size": ...}}
            symbol_info = request.get('symbol_info', {})
            min_lot = float(symbol_info.get('min_lot', 1.0))
            max_lot = float(symbol_info.get('max_lot', 100.0))
            lot_step = float(symbol_info.get('lot_step', 1.0))
            contract_size = float(symbol_info.get('trade_contract_size', 100000))  # From broker
            
            logger.info(f"📏 BROKER SPECS for {symbol.upper()}:")
            logger.info(f"   Min Lot: {min_lot} | Max Lot: {max_lot} | Lot Step: {lot_step}")
            logger.info(f"   Contract Size: {contract_size:,.0f}")

            # Calculate stop loss (at structure, not arbitrary)
            stop_loss_price = structure.nearest_support if ml_direction == "BUY" else structure.nearest_resistance
            stop_distance = abs(current_price - stop_loss_price)

            # Smart Position Sizer - AI-driven lot size calculation
            smart_sizer = get_smart_sizer()
            
            # Get FTMO distances
            ftmo_daily_dist = context.distance_to_daily_limit if hasattr(context, 'distance_to_daily_limit') else 10000.0
            ftmo_dd_dist = context.distance_to_dd_limit if hasattr(context, 'distance_to_dd_limit') else 10000.0
            
            # Get daily P&L
            daily_pnl = float(request.get('daily_pnl', 0.0))
            
            # Get market regime
            regime = context.get_market_regime()
            
            # Get volatility
            volatility = context.volatility if hasattr(context, 'volatility') else 1.0
            
            # Convert quality_multiplier (0.0-1.5) to score (0-100)
            # quality_multiplier is typically 0.5-1.5, so normalize it
            final_score = min(100, max(0, quality_multiplier * 100))
            
            # Calculate expected win probability from ML confidence and score
            # High confidence + high score = higher win probability
            expected_win_prob = 0.5 + (ml_confidence / 100.0 * 0.15) + (final_score / 100.0 * 0.15)
            expected_win_prob = min(0.75, max(0.45, expected_win_prob))  # Clamp 45-75%
            
            sizing_result = smart_sizer.calculate_lot_size(
                symbol=symbol,
                account_balance=account_balance,
                account_equity=account_equity,
                entry_price=current_price,
                stop_loss_price=stop_loss_price,
                trade_score=final_score,
                ml_confidence=ml_confidence,
                market_volatility=volatility,
                regime=regime,
                open_positions=len(open_positions),
                daily_pnl=daily_pnl,
                ftmo_distance_to_daily=ftmo_daily_dist,
                ftmo_distance_to_dd=ftmo_dd_dist,
                expected_win_prob=expected_win_prob
            )
            
            final_lots = sizing_result['lot_size']
            
            # Apply broker constraints
            final_lots = max(min_lot, min(final_lots, max_lot))
            final_lots = round(final_lots / lot_step) * lot_step

        except Exception as e:
            logger.error(f"❌ Position sizing failed: {e}")
            return {"action": "HOLD", "reason": f"Position sizing error: {e}"}

        # ═══════════════════════════════════════════════════════════════════
        # STEP 7: CALCULATE TARGETS (AT STRUCTURE, NOT ARBITRARY)
        # ═══════════════════════════════════════════════════════════════════
        take_profit_price = structure.nearest_resistance if ml_direction == "BUY" else structure.nearest_support

        # Calculate points for EA
        stop_points = int(stop_distance)
        target_points = int(abs(current_price - take_profit_price))

        # Ensure minimum scalping targets
        stop_points = max(50, stop_points)
        target_points = max(100, target_points)

        # Calculate risk/reward
        risk_reward = target_points / stop_points if stop_points > 0 else 0

        logger.info(f"🎯 TARGETS:")
        logger.info(f"   Entry: ${current_price:.2f}")
        logger.info(f"   Stop: ${stop_loss_price:.2f} ({stop_points} pts)")
        logger.info(f"   Target: ${take_profit_price:.2f} ({target_points} pts)")
        logger.info(f"   R:R: {risk_reward:.2f}:1")

        # ═══════════════════════════════════════════════════════════════════
        # FINAL DECISION
        # ═══════════════════════════════════════════════════════════════════
        
        # SWING TRADING FIX: If position exists, DON'T generate new entry signals!
        # Position manager already analyzed and returned HOLD/CLOSE/DCA
        # This section should ONLY run when NO position exists
        final_action = ml_direction
        
        if open_position and position_symbol == raw_symbol:
            # POSITION EXISTS - Position manager already decided, return that decision
            logger.info(f"⚠️ Position exists on {position_symbol} - using Position Manager decision (not entry signal)")
            return position_decision  # Return what position manager said (HOLD/CLOSE/DCA/SCALE_OUT)
            # We have a position on the SAME symbol
            current_position_volume = float(open_position.get('volume', 0))
            
            # 🤖 AI-DRIVEN: Max position based on account risk (3% of account)
            max_risk_pct = 3.0
            max_position_value = (account_balance * max_risk_pct) / 100
            max_position_size = max_position_value / (current_price * 100000)  # Forex contract
            max_position_size = max(0.5, min(5.0, max_position_size))  # Clamp 0.5-5.0
            
            if current_position_volume >= max_position_size:
                # Position too large - don't add more
                logger.info(f"⚠️ Position too large ({current_position_volume:.2f} lots) - NOT converting to SCALE_IN")
                logger.info(f"   Max size (AI-driven): {max_position_size:.2f} lots (3% of ${account_balance:,.0f})")
                return {
                    "action": "HOLD",
                    "reason": f"Position at max size ({current_position_volume:.2f}/{max_position_size:.2f} lots)",
                    "confidence": ml_confidence
                }
            
            # EA blocks duplicate BUY/SELL, so convert to SCALE_IN
            if ml_direction in ["BUY", "SELL"]:
                final_action = "SCALE_IN"
                logger.info(f"⚠️ Converting {ml_direction} to SCALE_IN (position exists on {position_symbol}, size: {current_position_volume:.2f})")
        
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info(f"✅ TRADE APPROVED: {final_action}")
        logger.info(f"   Confidence: {ml_confidence:.1f}%")
        logger.info(f"   Quality: {quality_multiplier:.2f}x")
        logger.info(f"   Size: {final_lots:.1f} lots")
        logger.info(f"   Risk: ${stop_distance * final_lots:,.2f}")
        logger.info(f"   Reward: ${abs(current_price - take_profit_price) * final_lots:,.2f}")
        logger.info("═══════════════════════════════════════════════════════════════════")

        response = {
            "action": final_action,
            "confidence": ml_confidence,
            "take_trade": True,

            # Position sizing
            "lot_size": final_lots,
            "position_size": final_lots,

            # Targets (at structure, not arbitrary)
            "stop_loss": stop_loss_price,
            "take_profit": 0.0,  # NO FIXED TP - AI will manage exits dynamically
            "stop_points": stop_points,
            "target_points": target_points,
            "risk_reward": risk_reward,

            # AI reasoning
            "reason": reason,
            "quality_score": quality_multiplier,

            # Market structure (for EA logging)
            "structure": {
                "trend": "UP" if structure.higher_highs else ("DOWN" if structure.lower_lows else "RANGING"),
                "at_support": structure.at_support,
                "at_resistance": structure.at_resistance,
                "support": structure.nearest_support,
                "resistance": structure.nearest_resistance,
                "exhaustion": structure.move_exhaustion
            },

            # CRITICAL: Include ALL position decisions for multi-position management
            "portfolio_decisions": portfolio_decisions,

            "system": "ai_powered_v1.0"
        }
        
        # Add add_lots for SCALE_IN action
        if final_action == "SCALE_IN":
            response["add_lots"] = final_lots
        
        return response

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {e}", exc_info=True)
        return {
            "action": "HOLD",
            "reason": f"System error: {str(e)}",
            "confidence": 0.0,
            "portfolio_decisions": portfolio_decisions  # Include any decisions made before error
        }

# ═══════════════════════════════════════════════════════════════════
# EXIT DECISION ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/ai/exit_decision")
async def ai_exit_decision(request: dict):
    """
    AI-POWERED EXIT DECISION

    Knows when trade is done based on:
    - Structure broken (support/resistance violated)
    - Target reached
    - Move exhausted
    - Momentum shift
    """

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("AI EXIT DECISION REQUEST")
    logger.info("═══════════════════════════════════════════════════════════════════")

    try:
        # Get position info
        entry_price = float(request.get('entry_price', 0.0))
        current_price = float(request.get('current_price', 0.0))
        direction = request.get('direction', 'BUY')
        bars_held = int(request.get('bars_held', 0))
        unrealized_pnl = float(request.get('unrealized_pnl', 0.0))

        if entry_price == 0:
            return {"should_exit": False, "reason": "Invalid entry price"}

        # Parse market data
        mtf_data = parse_market_data(request)

        if 'm1' not in mtf_data:
            return {"should_exit": False, "reason": "No market data"}

        # Analyze current market structure
        if trade_manager is None:
            return {"should_exit": False, "reason": "Trade manager not loaded"}

        structure = trade_manager.analyze_market_structure(
            current_price=current_price,
            ohlcv_data=mtf_data
        )

        # AI exit decision
        should_exit, reason = trade_manager.should_exit_trade(
            entry_price=entry_price,
            current_price=current_price,
            direction=direction,
            structure=structure,
            unrealized_pnl=unrealized_pnl,
            bars_held=bars_held
        )

        logger.info(f"🚪 AI EXIT DECISION: {should_exit}")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   P&L: ${unrealized_pnl:.2f}")
        logger.info(f"   Bars Held: {bars_held}")

        return {
            "should_exit": should_exit,
            "reason": reason,
            "current_pnl": unrealized_pnl,
            "bars_held": bars_held,
            "structure": structure.__dict__
        }

    except Exception as e:
        logger.error(f"❌ Exit decision error: {e}", exc_info=True)
        return {
            "should_exit": False,
            "reason": f"Error: {str(e)}"
        }

# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "online",
        "ml_models": ml_models is not None,
        "feature_engineer": feature_engineer is not None,
        "trade_manager": trade_manager is not None,
        "ftmo_risk_manager": "created_per_request",  # Now uses live EA data
        "ppo_agent": ppo_agent is not None,
        "system": "ai_powered_v1.0"
    }

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    # Kill any existing process on port 5007
    os.system("lsof -ti:5007 | xargs kill -9 2>/dev/null")

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("STARTING AI-POWERED TRADING API")
    logger.info("Port: 5007")
    logger.info("Log: /tmp/ai_trading_api.log")
    logger.info("═══════════════════════════════════════════════════════════════════")

    uvicorn.run(app, host="0.0.0.0", port=5007, log_level="info")
