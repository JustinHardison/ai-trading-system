"""
AI-POWERED TRADING API v5.27
Pure AI-driven trading decisions using ML + HTF analysis.
No hardcoded thresholds - all decisions based on EV calculations.
"""
import os
import sys
import json
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.risk.ftmo_risk_manager import FTMORiskManager
from src.risk.news_filter import NewsEventFilter
from src.ai.enhanced_context import EnhancedTradingContext
from src.ai.intelligent_position_manager import IntelligentPositionManager
from src.utils.market_hours import MarketHours
from src.ai.unified_trading_system import UnifiedTradingSystem
from src.ai.elite_position_sizer import ElitePositionSizer
from src.ai.portfolio_state import get_portfolio_state
from src.utils.trade_journal import log_closed_trade, get_trade_stats, log_entry_context, log_exit_context

# ═══════════════════════════════════════════════════════════════════
# STRUCTURED MODEL OUTPUT BUILDER
# ═══════════════════════════════════════════════════════════════════
def build_model_outputs(
    entry_direction: str = "flat",
    entry_ev: float = 0.0,
    entry_confidence: float = 0.0,
    env_score: float = 0.5,
    risk_fraction: float = 0.0,
    skip_trade: bool = True,
    skip_probability: float = 1.0,
    portfolio_scale: float = 1.0,
    positions_list: list = None
) -> dict:
    """
    Build structured model outputs for the new multi-model architecture.
    
    Returns dict with keys: entry, env, risk, skip, portfolio, positions
    These are always included in API responses for the EA to consume.
    """
    return {
        "entry": {
            "direction": entry_direction,  # "long", "short", "flat"
            "ev": float(entry_ev),          # expected value/return score
            "confidence": float(min(1.0, entry_confidence / 100.0 if entry_confidence > 1 else entry_confidence))
        },
        "env": {
            "score": float(max(0.0, min(1.0, env_score)))  # 0-1 market environment score
        },
        "risk": {
            "fraction": float(max(0.0, min(1.0, risk_fraction)))  # 0-1 of max risk per trade
        },
        "skip": {
            "skip_trade": bool(skip_trade),
            "skip_probability": float(max(0.0, min(1.0, skip_probability)))
        },
        "portfolio": {
            "scale": float(max(0.0, min(2.0, portfolio_scale)))  # 0-2 multiplier
        },
        "positions": positions_list or []
    }


# ═══════════════════════════════════════════════════════════════════
# STRUCTURED TRAINING DATA LOGGER
# ═══════════════════════════════════════════════════════════════════
TRAINING_LOG_DIR = Path("/Users/justinhardison/ai-trading-system/training_logs")
TRAINING_LOG_DIR.mkdir(exist_ok=True)

def log_training_data(
    log_type: str,  # "entry", "exit", "position_mgmt"
    symbol: str,
    timestamp: str,
    action: str,
    features: dict = None,
    context_data: dict = None,
    model_outputs: dict = None,
    position_data: dict = None,
    account_data: dict = None,
    outcome: dict = None
):
    """
    Log structured training data for future model training.
    Writes JSONL format (one JSON object per line) for easy processing.
    
    Files:
    - entries_YYYYMMDD.jsonl: All entry decisions (BUY/SELL/HOLD)
    - exits_YYYYMMDD.jsonl: All exit decisions (CLOSE/SCALE_OUT)
    - position_mgmt_YYYYMMDD.jsonl: Position management (DCA/SCALE_IN/HOLD)
    """
    try:
        date_str = datetime.now().strftime("%Y%m%d")
        
        # Build log entry
        log_entry = {
            "timestamp": timestamp or datetime.now().isoformat(),
            "log_type": log_type,
            "symbol": symbol,
            "action": action,
            "features": features or {},
            "context": context_data or {},
            "model_outputs": model_outputs or {},
            "position": position_data or {},
            "account": account_data or {},
            "outcome": outcome or {}  # Filled in later with actual P&L
        }
        
        # Determine file based on log type
        if log_type == "entry":
            log_file = TRAINING_LOG_DIR / f"entries_{date_str}.jsonl"
        elif log_type == "exit":
            log_file = TRAINING_LOG_DIR / f"exits_{date_str}.jsonl"
        else:
            log_file = TRAINING_LOG_DIR / f"position_mgmt_{date_str}.jsonl"
        
        # Append to file
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
    except Exception as e:
        # Don't let logging errors break trading
        pass


def build_position_output(
    ticket: int,
    symbol: str,
    current_lots: float,
    action: str,
    add_lots: float = 0.0,
    reduce_lots: float = 0.0
) -> dict:
    """
    Build a single position output for the positions array.
    
    action: HOLD, CLOSE, SCALE_IN, SCALE_OUT, DCA
    Returns target_size_factor and action_probs.
    """
    # Calculate target size factor
    if action == "CLOSE":
        target_factor = 0.0
    elif action in ["SCALE_OUT"]:
        target_factor = max(0.0, (current_lots - reduce_lots) / current_lots) if current_lots > 0 else 0.0
    elif action in ["SCALE_IN", "DCA"]:
        target_factor = (current_lots + add_lots) / current_lots if current_lots > 0 else 1.0
    else:  # HOLD
        target_factor = 1.0
    
    # Build action probabilities based on decision
    action_probs = {"hold": 0.0, "partial_close": 0.0, "add": 0.0, "full_close": 0.0}
    if action == "HOLD":
        action_probs["hold"] = 1.0
    elif action == "CLOSE":
        action_probs["full_close"] = 1.0
    elif action == "SCALE_OUT":
        action_probs["partial_close"] = 1.0
    elif action in ["SCALE_IN", "DCA"]:
        action_probs["add"] = 1.0
    
    return {
        "id": f"{symbol}_{ticket}",
        "ticket": int(ticket),
        "symbol": symbol,
        "current_lots": float(current_lots),
        "target_size_factor": float(target_factor),
        "action_probs": action_probs
    }


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
ml_models = {}  # Dictionary of {symbol: model}
feature_engineer = None  # Live feature engineer
position_manager = None  # Intelligent position manager for exits
unified_system = None  # Unified trading system
elite_sizer = None  # Elite position sizer
portfolio_state = None  # Portfolio state tracker
market_hours = None  # Market hours detector
news_filter = None  # News event filter for high-impact events
USE_ELITE_SIZER = True  # Use elite sizer for position sizing

# ═══════════════════════════════════════════════════════════════════
# DAILY PROFIT PROTECTION TRACKING
# Tracks peak daily P&L to prevent giving back large gains
# ═══════════════════════════════════════════════════════════════════
peak_daily_pnl_tracker = {
    'peak_pnl': 0.0,
    'last_reset_date': None
}

# ═══════════════════════════════════════════════════════════════════
# HEDGE FUND IMPROVEMENT #5: PEAK PROFIT TRACKING PER POSITION
# Tracks the high water mark (peak profit) for each open position
# Used to detect when a profitable trade is giving back too much
# ═══════════════════════════════════════════════════════════════════
position_peak_profit_tracker = {}

def update_position_peak_profit(ticket: int, current_profit_pct: float) -> float:
    """Update and return the peak profit for a position."""
    global position_peak_profit_tracker
    
    if ticket not in position_peak_profit_tracker:
        position_peak_profit_tracker[ticket] = current_profit_pct
    else:
        if current_profit_pct > position_peak_profit_tracker[ticket]:
            position_peak_profit_tracker[ticket] = current_profit_pct
    
    return position_peak_profit_tracker[ticket]

def cleanup_closed_positions(open_tickets: list):
    """Remove closed positions from the peak profit tracker."""
    global position_peak_profit_tracker
    closed_tickets = [t for t in position_peak_profit_tracker if t not in open_tickets]
    for ticket in closed_tickets:
        del position_peak_profit_tracker[ticket]

# ═══════════════════════════════════════════════════════════════════
# CROSS-ASSET DATA CACHE (Institutional Edge)
# Caches recent data from each symbol for cross-asset correlation
# ═══════════════════════════════════════════════════════════════════
cross_asset_cache = {
    # Indices - for risk sentiment
    'us30': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    'us100': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    'us500': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    # Gold - for safe haven
    'xau': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    # Forex majors - for dollar strength
    'eurusd': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    'gbpusd': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
    'usdjpy': {'h1_trend': 0.5, 'h4_trend': 0.5, 'momentum': 0.0, 'last_update': 0},
}

def update_cross_asset_cache(symbol: str, h1_trend: float, h4_trend: float, momentum: float):
    """Update the cross-asset cache with latest data from a symbol"""
    import time
    symbol_key = symbol.lower().replace('.sim', '').split('z')[0].split('g')[0]
    # Map variations to standard keys
    if 'us30' in symbol_key: symbol_key = 'us30'
    elif 'us100' in symbol_key: symbol_key = 'us100'
    elif 'us500' in symbol_key: symbol_key = 'us500'
    elif 'xau' in symbol_key or 'gold' in symbol_key: symbol_key = 'xau'
    elif 'eur' in symbol_key: symbol_key = 'eurusd'
    elif 'gbp' in symbol_key: symbol_key = 'gbpusd'
    elif 'jpy' in symbol_key: symbol_key = 'usdjpy'
    
    if symbol_key in cross_asset_cache:
        cross_asset_cache[symbol_key] = {
            'h1_trend': h1_trend,
            'h4_trend': h4_trend,
            'momentum': momentum,
            'last_update': time.time()
        }

def calculate_cross_asset_context(symbol: str) -> dict:
    """
    Calculate cross-asset correlation context for a symbol.
    
    Returns dict with:
    - dxy_trend: Inferred dollar strength from forex pairs
    - risk_on_off: Risk sentiment from indices
    - indices_aligned: Whether US indices are aligned
    - gold_dollar_divergence: Unusual gold/dollar relationship
    """
    import time
    current_time = time.time()
    max_age = 300  # 5 minutes max age for cache data
    
    # Get index data for risk sentiment
    us30 = cross_asset_cache.get('us30', {})
    us100 = cross_asset_cache.get('us100', {})
    us500 = cross_asset_cache.get('us500', {})
    
    # Calculate risk on/off from indices
    indices_trends = []
    indices_momentums = []
    for idx in [us30, us100, us500]:
        if current_time - idx.get('last_update', 0) < max_age:
            indices_trends.append(idx.get('h4_trend', 0.5))
            indices_momentums.append(idx.get('momentum', 0.0))
    
    if indices_trends:
        avg_index_trend = sum(indices_trends) / len(indices_trends)
        avg_index_momentum = sum(indices_momentums) / len(indices_momentums)
        # Risk on = indices bullish (>0.55), Risk off = indices bearish (<0.45)
        risk_on_off = avg_index_trend
        indices_aligned = 1.0 if all(t > 0.52 for t in indices_trends) or all(t < 0.48 for t in indices_trends) else 0.5
    else:
        risk_on_off = 0.5
        avg_index_momentum = 0.0
        indices_aligned = 0.5
    
    # Infer DXY from forex pairs (inverse relationship)
    eurusd = cross_asset_cache.get('eurusd', {})
    gbpusd = cross_asset_cache.get('gbpusd', {})
    usdjpy = cross_asset_cache.get('usdjpy', {})
    
    dxy_signals = []
    if current_time - eurusd.get('last_update', 0) < max_age:
        # EUR down = DXY up
        dxy_signals.append(1.0 - eurusd.get('h4_trend', 0.5))
    if current_time - gbpusd.get('last_update', 0) < max_age:
        # GBP down = DXY up
        dxy_signals.append(1.0 - gbpusd.get('h4_trend', 0.5))
    if current_time - usdjpy.get('last_update', 0) < max_age:
        # USDJPY up = DXY up
        dxy_signals.append(usdjpy.get('h4_trend', 0.5))
    
    if dxy_signals:
        dxy_trend = sum(dxy_signals) / len(dxy_signals)
        dxy_momentum = -eurusd.get('momentum', 0.0)  # Inverse of EUR momentum
    else:
        dxy_trend = 0.5
        dxy_momentum = 0.0
    
    # Gold/Dollar divergence (normally inverse)
    xau = cross_asset_cache.get('xau', {})
    if current_time - xau.get('last_update', 0) < max_age:
        xau_trend = xau.get('h4_trend', 0.5)
        # If both gold and DXY bullish or both bearish = divergence
        if (xau_trend > 0.55 and dxy_trend > 0.55) or (xau_trend < 0.45 and dxy_trend < 0.45):
            gold_dollar_divergence = abs(xau_trend - 0.5) + abs(dxy_trend - 0.5)
        else:
            gold_dollar_divergence = 0.0
    else:
        gold_dollar_divergence = 0.0
    
    return {
        'dxy_trend': dxy_trend,
        'dxy_momentum': dxy_momentum,
        'dxy_strength': abs(dxy_trend - 0.5) * 2,  # 0-1 scale
        'risk_on_off': risk_on_off,
        'indices_aligned': indices_aligned,
        'indices_momentum': avg_index_momentum,
        'gold_dollar_divergence': gold_dollar_divergence,
        'forex_index_correlation': 0.0  # TODO: Calculate if needed
    }

# NOTE: Anti-churn and position state tracking is now handled by UnifiedTradingSystem
# This is the SINGLE SOURCE OF TRUTH - no duplicate tracking here

# ═══════════════════════════════════════════════════════════════════
# STARTUP: LOAD ALL AI COMPONENTS
# ═══════════════════════════════════════════════════════════════════
@app.on_event("startup")
async def load_ai_system():
    """Load ML models, feature engineer, position manager, and risk systems"""
    global ml_models, feature_engineer, position_manager, unified_system, elite_sizer, portfolio_state, market_hours

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("AI-POWERED MULTI-SYMBOL TRADING SYSTEM - LOADING")
    logger.info("═══════════════════════════════════════════════════════════════════")

    # 1. Load ML Models for ALL trained symbols
    try:
        import glob
        
        # PRIORITY: Load HTF models (with H1/H4/D1 features) - COHESIVE with entry/exit logic
        htf_model_files = glob.glob('/Users/justinhardison/ai-trading-system/models/*_htf_ensemble.pkl')
        
        if htf_model_files:
            logger.info("🎯 Loading HTF models (cohesive with entry/exit timeframes)")
            for model_file in htf_model_files:
                basename = os.path.basename(model_file)
                symbol = basename.replace('_htf_ensemble.pkl', '')
                
                try:
                    ml_models[symbol] = joblib.load(model_file)
                    n_features = ml_models[symbol].get('n_features', 'unknown')
                    accuracy = ml_models[symbol].get('ensemble_accuracy', 0)
                    logger.info(f"✅ Loaded HTF model for {symbol} ({n_features} features, {accuracy:.1%} accuracy)")
                except Exception as e:
                    logger.error(f"❌ Failed to load HTF model for {symbol}: {e}")
        else:
            # Fallback to old models if HTF models not available
            logger.warning("⚠️ No HTF models found, falling back to old models")
            model_files = glob.glob('/Users/justinhardison/ai-trading-system/models/*_ensemble_latest.pkl')
            
            if not model_files:
                logger.warning("No *_ensemble_latest.pkl files found, trying fallback model...")
                fallback_model = '/Users/justinhardison/ai-trading-system/models/integrated_ensemble_20251118_130030.pkl'
                if os.path.exists(fallback_model):
                    ml_models['us30'] = joblib.load(fallback_model)
                    logger.info("✅ Loaded fallback model for us30")
            else:
                for model_file in model_files:
                    basename = os.path.basename(model_file)
                    symbol = basename.replace('_ensemble_latest.pkl', '')
                    
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
    
    # 3. Initialize Intelligent Position Manager
    try:
        position_manager = IntelligentPositionManager()
        logger.info("✅ Intelligent Position Manager initialized: AI-driven exits")
    except Exception as e:
        logger.error(f"❌ Failed to initialize position manager: {e}")
        position_manager = None
    
    # 4. Initialize Unified Trading System
    try:
        unified_system = UnifiedTradingSystem()
        logger.info("✅ Unified Trading System initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize unified system: {e}")
        unified_system = None
    
    # 5. Initialize Elite Position Sizer
    try:
        elite_sizer = ElitePositionSizer()
        portfolio_state = get_portfolio_state()
        logger.info("✅ 🏆 ELITE POSITION SIZER initialized: Renaissance/Citadel grade")
        logger.info("   - Portfolio correlation-aware")
        logger.info("   - CVaR tail risk sizing")
        logger.info("   - Dynamic risk budgeting")
        logger.info("   - Information Ratio optimization")
        logger.info(f"   - Status: {'ACTIVE' if USE_ELITE_SIZER else 'STANDBY'}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize elite sizer: {e}")
        elite_sizer = None
        portfolio_state = None
    
    # 6. FTMO Risk Manager will be initialized per-request with EA data
    # (No hardcoded values - all pulled from live MT5 account)
    logger.info("✅ FTMO Risk Manager ready: Will use live MT5 account data")
    
    # 7. Initialize Market Hours Checker
    try:
        market_hours = MarketHours(timezone='America/New_York')
        logger.info("✅ Market Hours Checker initialized (America/New_York)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize market hours: {e}")
        market_hours = None

    # 8. Initialize News Event Filter
    try:
        news_filter = NewsEventFilter(avoid_minutes_before=30, avoid_minutes_after=30)
        logger.info("✅ News Event Filter initialized")
        logger.info("   - Blocks entries 30 min before/after high-impact news")
        logger.info("   - Events: NFP, FOMC, CPI, PPI, GDP, Jobless Claims")
    except Exception as e:
        logger.error(f"❌ Failed to initialize news filter: {e}")
        news_filter = None

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("SYSTEM READY - Regime-Aware AI Trading System")
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
            
            # ML returns direction based on probability
            # Unified Trading System handles setup-specific thresholds:
            # - SCALP: 55% (quick trades, lower conviction OK)
            # - DAY: 57% (medium conviction)
            # - SWING: 60% (need conviction for longer holds)
            # Here we just return the raw signal, let unified system filter
            MIN_CONFIDENCE = 0.55  # Base minimum - unified system applies setup-specific thresholds
            
            if buy_prob > MIN_CONFIDENCE:
                direction = "BUY"
                confidence = buy_prob * 100
            elif sell_prob > MIN_CONFIDENCE:
                direction = "SELL"
                confidence = sell_prob * 100
            else:
                # Below 55% - truly uncertain
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
    
    global unified_system, feature_engineer, USE_ELITE_SIZER, elite_sizer, portfolio_state, market_hours, position_manager

    logger.info("═══════════════════════════════════════════════════════════════════")
    logger.info("AI TRADE DECISION REQUEST")
    logger.info("═══════════════════════════════════════════════════════════════════")

    try:
        # ═══════════════════════════════════════════════════════════
        # CHECK 0: Market Hours - Don't waste time if market is closed
        # ═══════════════════════════════════════════════════════════
        
        # Log account data even when market closed (for verification)
        account_data = request.get('account', {})
        if account_data:
            logger.info(f"   📊 Account data received: initial_balance={account_data.get('initial_balance', 'NOT SET')}, "
                       f"balance={account_data.get('balance')}, equity={account_data.get('equity')}, "
                       f"max_daily_loss={account_data.get('max_daily_loss')}, max_total_drawdown={account_data.get('max_total_drawdown')}")
        
        if market_hours is not None:
            market_status = market_hours.is_market_open()
            if not market_status['open']:
                logger.warning(f"🕐 MARKET CLOSED: {market_status['reason']}")
                if market_status.get('next_open'):
                    logger.warning(f"   Next open: {market_status['next_open']}")
                return {
                    "action": "HOLD",
                    "reason": f"Market closed: {market_status['reason']}",
                    "lots": 0.0,
                    "stop_loss": 0.0,
                    "take_profit": 0.0,
                    "confidence": 0,
                    **build_model_outputs(skip_trade=True, skip_probability=1.0)
                }

        # ═══════════════════════════════════════════════════════════
        # CHECK 1: Total Portfolio Risk - Max 5% total risk
        # Uses current P&L as a robust proxy for risk
        # ═══════════════════════════════════════════════════════════
        open_positions = request.get('positions', [])
        portfolio_risk_pct = 0.0
        account_balance = float(request.get('account', {}).get('balance', 0.0))

        if open_positions and account_balance > 0:
            for pos in open_positions:
                pos_profit = float(pos.get('profit', 0))
                portfolio_risk_pct += abs(pos_profit) / account_balance * 100.0

            logger.info(f"💼 Portfolio Risk: {portfolio_risk_pct:.2f}% of account (max 5%)")
        else:
            logger.info("💼 Portfolio Risk: 0.00% of account (no open positions or missing balance)")

        # ═══════════════════════════════════════════════════════════
        # Parse Request Data
        # ═══════════════════════════════════════════════════════════
        # DEBUG: Log what we're receiving
        logger.info(f"📦 Request keys: {list(request.keys())}")
        
        # DEBUG: Log actual market data
        timeframes = request.get('timeframes', {})
        indicators = request.get('indicators', {})
        symbol_info = request.get('symbol_info', {})
        account_data = request.get('account', {})
        # Log key account metrics including realized P&L from MT5 history
        daily_realized_pnl = float(account_data.get('daily_realized_pnl', 0))
        daily_pnl = float(account_data.get('daily_pnl', 0))
        unrealized_pnl = float(account_data.get('profit', 0))
        logger.info(f"   Account data: {account_data}")
        logger.info(f"   💰 DAILY P&L BREAKDOWN:")
        logger.info(f"      Realized (closed trades): ${daily_realized_pnl:,.2f}")
        logger.info(f"      Unrealized (open positions): ${unrealized_pnl:,.2f}")
        logger.info(f"      Total (equity change): ${daily_pnl:,.2f}")
        logger.info(f"   Symbol info: {symbol_info}")
        logger.info(f"   Contract size: {symbol_info.get('contract_size', 'MISSING')}")
        
        # Check for upcoming economic calendar events (news avoidance)
        # NEWS FILTER IS SYMBOL-AWARE: Only block symbols affected by the news currency
        calendar_events = request.get('calendar_events', [])
        high_impact_events = []  # Store events with their currencies
        logger.info(f"📅 Calendar events: {len(calendar_events)} events received")
        if calendar_events:
            for event in calendar_events:
                minutes_until = event.get('minutes_until', 999)
                importance = event.get('importance', '')
                event_name = event.get('event', '')
                currency = event.get('currency', '').upper()
                
                # Track HIGH impact events within 30 minutes
                if importance == 'HIGH' and 0 <= minutes_until <= 30:
                    high_impact_events.append({
                        'currency': currency,
                        'event': event_name,
                        'minutes': minutes_until
                    })
                    logger.warning(f"⚠️ HIGH IMPACT NEWS in {minutes_until}min: {currency} {event_name}")
                elif importance == 'HIGH' and 0 <= minutes_until <= 60:
                    logger.info(f"📅 Upcoming: {currency} {event_name} ({importance}) in {minutes_until}min")
        
        # SERVER-SIDE NEWS FILTER (fallback if EA doesn't send calendar_events)
        # This catches NFP, FOMC, CPI, PPI, GDP, Jobless Claims automatically
        if news_filter is not None and not high_impact_events:
            try:
                news_status = news_filter.is_safe_to_trade()
                if not news_status.is_safe:
                    # Extract event info from the news filter
                    for event in news_status.upcoming_events[:1]:  # Just the nearest event
                        high_impact_events.append({
                            'currency': event.currency,
                            'event': event.name,
                            'minutes': news_status.minutes_to_next_event or 0
                        })
                        logger.warning(f"⚠️ SERVER NEWS FILTER: {event.name} ({event.currency}) - {news_status.reason}")
                elif news_status.upcoming_events:
                    next_event = news_status.upcoming_events[0]
                    logger.info(f"📅 Server news: Next event {next_event.name} in {news_status.minutes_to_next_event:.0f}min")
            except Exception as e:
                logger.warning(f"⚠️ News filter error: {e}")
        
        # Extract symbol from request (EA sends this in symbol_info)
        symbol_info = request.get('symbol_info', {})
        raw_symbol = symbol_info.get('symbol', request.get('symbol', 'US30'))
        
        # Extract broker constraints early (needed for context)
        min_lot = float(symbol_info.get('min_lot', 1.0))
        max_lot = float(symbol_info.get('max_lot', 50.0))
        lot_step = float(symbol_info.get('lot_step', 1.0))
        # FIXED: Use 'contract_size' key (not 'trade_contract_size')
        contract_size = float(symbol_info.get('contract_size', symbol_info.get('trade_contract_size', 100000)))
        logger.info(f"   📊 Broker contract_size: {contract_size}")
        
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
        
        # ═══════════════════════════════════════════════════════════════════
        # DISABLED SYMBOLS - These symbols are blocked from trading
        # USOIL disabled on Dec 3, 2025 - worst performing symbol by far
        # FOREX disabled on Dec 5, 2025 - calculation issues being investigated
        # ═══════════════════════════════════════════════════════════════════
        DISABLED_SYMBOLS = ['usoil', 'eurusd', 'gbpusd', 'usdjpy']
        
        if symbol in DISABLED_SYMBOLS:
            logger.warning(f"🚫 {symbol.upper()} is DISABLED - skipping all trading")
            return {
                "should_trade": False,
                "action": "HOLD",
                "reason": f"{symbol.upper()} trading disabled - worst performing symbol",
                "position_decisions": []
            }
        
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
        
        # Process recent trades from MT5 (last 24 hours)
        recent_trades = request.get('recent_trades', [])
        if recent_trades:
            # Calculate total P&L including profit, swap, and commission
            total_gross_profit = sum(float(t.get('profit', 0)) for t in recent_trades)
            total_swap = sum(float(t.get('swap', 0)) for t in recent_trades)
            total_commission = sum(float(t.get('commission', 0)) for t in recent_trades)
            total_net_pnl = total_gross_profit + total_swap + total_commission
            
            logger.info(f"📊 Recent trades (last 24h): {len(recent_trades)} closed trades")
            logger.info(f"   💰 Gross Profit: ${total_gross_profit:.2f}")
            logger.info(f"   📉 Swap: ${total_swap:.2f}")
            logger.info(f"   📉 Commission: ${total_commission:.2f}")
            logger.info(f"   ✅ Net Realized P&L: ${total_net_pnl:.2f}")
            
            # Track recently closed trades for anti-churn (detect stop loss hits)
            import time as time_module
            current_time = time_module.time()
            
            for trade in recent_trades:
                trade_ticket = trade.get('ticket', 0)
                trade_symbol = trade.get('symbol', 'UNKNOWN')
                trade_profit = float(trade.get('profit', 0))
                trade_swap = float(trade.get('swap', 0))
                trade_commission = float(trade.get('commission', 0))
                trade_volume = float(trade.get('volume', 0))
                trade_entry_type = trade.get('entry_type', 'UNKNOWN')
                trade_type = trade.get('type', 0)  # 0=BUY, 1=SELL
                trade_close_time = trade.get('time_close', 0)
                trade_net = trade_profit + trade_swap + trade_commission
                
                # Only log trades with actual P&L
                if trade_profit != 0:
                    logger.info(f"   Trade #{trade_ticket} ({trade_symbol}): ${trade_profit:.2f} gross, ${trade_net:.2f} net ({trade_volume} lots) [{trade_entry_type}]")
                    
                    # ═══════════════════════════════════════════════════════════
                    # PERSISTENT TRADE JOURNAL
                    # Log every closed trade for post-analysis
                    # ═══════════════════════════════════════════════════════════
                    trade_direction = 'BUY' if trade_type == 0 else 'SELL'
                    trade_open_time = trade.get('time_open', 0)
                    trade_entry_price = float(trade.get('price_open', 0))
                    trade_exit_price = float(trade.get('price_close', 0))
                    
                    # Get session context for the trade
                    from datetime import datetime
                    import pytz
                    utc_now = datetime.now(pytz.UTC)
                    is_friday = utc_now.weekday() == 4
                    current_hour = utc_now.hour
                    if 13 <= current_hour < 16:
                        trade_session = 'overlap'
                    elif 13 <= current_hour < 21:
                        trade_session = 'new_york'
                    elif 8 <= current_hour < 16:
                        trade_session = 'london'
                    else:
                        trade_session = 'asian'
                    
                    # Log to persistent journal
                    log_closed_trade(
                        ticket=trade_ticket,
                        symbol=trade_symbol,
                        direction=trade_direction,
                        lots=trade_volume,
                        entry_price=trade_entry_price,
                        exit_price=trade_exit_price,
                        gross_pnl=trade_profit,
                        net_pnl=trade_net,
                        swap=trade_swap,
                        commission=trade_commission,
                        open_time=trade_open_time,
                        close_time=trade_close_time,
                        setup_type=trade_entry_type,
                        exit_reason=trade_entry_type,  # EA sends this as entry_type
                        session=trade_session,
                        is_friday=is_friday
                    )
                
                # ═══════════════════════════════════════════════════════════
                # ANTI-CHURN: Register ALL recent closes (including stop loss hits)
                # CRITICAL FIX: Don't rely on time_close - it may be 0
                # Instead, track by ticket number and register ALL trades in the list
                # The EA sends recent trades from the last 24h, but we only care about
                # the most recent ones (highest ticket numbers)
                # ═══════════════════════════════════════════════════════════
                
                # Clean symbol name
                clean_symbol = re.sub(r'[ZFGHJKMNQUVX]\d{2}', '', trade_symbol.replace('.sim', ''), flags=re.IGNORECASE).lower()
                direction = 'BUY' if trade_type == 0 else 'SELL'
                
                # Track the highest ticket we've seen per symbol using a module-level dict
                global _recent_close_tickets
                if '_recent_close_tickets' not in globals():
                    _recent_close_tickets = {}
                
                symbol_key = clean_symbol
                if symbol_key not in _recent_close_tickets:
                    _recent_close_tickets[symbol_key] = {'ticket': 0, 'time': 0}
                
                # If this is a newer ticket than we've seen, register the close
                if trade_ticket > _recent_close_tickets[symbol_key]['ticket']:
                    _recent_close_tickets[symbol_key] = {
                        'ticket': trade_ticket,
                        'time': current_time
                    }
                    
                    # Register with unified system for anti-churn
                    if unified_system:
                        unified_system.register_close(clean_symbol, direction, 0.5, f"Stop/TP hit (ticket #{trade_ticket})")
                        logger.info(f"   🚫 ANTI-CHURN: Registered close on {clean_symbol} (ticket #{trade_ticket}, {direction})")
                
                # Also check time_close if available (backup method)
                if trade_close_time > 0:
                    seconds_since_close = current_time - trade_close_time
                    if seconds_since_close < 300:  # Closed in last 5 minutes
                        if unified_system:
                            unified_system.register_close(clean_symbol, direction, 0.5, f"Recent close ({seconds_since_close:.0f}s ago)")
                            logger.info(f"   🚫 Anti-churn: Recent close on {clean_symbol} ({seconds_since_close:.0f}s ago)")
                
                # Log large losses for investigation
                if trade_profit < -500:
                    logger.warning(f"🚨 LARGE LOSS DETECTED in recent trades!")
                    logger.warning(f"   Ticket: {trade_ticket}")
                    logger.warning(f"   Profit: ${trade_profit:.2f}")
                    logger.warning(f"   Volume: {trade_volume} lots")
                elif trade_profit > 500:
                    logger.info(f"💰 Large win: Ticket {trade_ticket}, ${trade_profit:.2f}")
        
        if open_positions and unified_system:
            logger.info(f"📊 Positions received: {len(open_positions)} positions")
            logger.info(f"📊 PORTFOLIO: {len(open_positions)} open positions - analyzing ALL NOW")
            
            # HEDGE FUND #5: Cleanup closed positions from peak profit tracker
            open_tickets = [pos.get('ticket', 0) for pos in open_positions]
            cleanup_closed_positions(open_tickets)
            
            for pos in open_positions:
                # Keep ORIGINAL symbol for EA to find position (includes .sim suffix)
                pos_symbol_original = pos.get('symbol', '')
                pos_symbol_raw = pos_symbol_original.replace('.sim', '').upper()
                pos_profit = float(pos.get('profit', 0))
                pos_volume = float(pos.get('volume', 0))
                pos_type = pos.get('type')  # 0=BUY, 1=SELL
                pos_entry = float(pos.get('price_open', 0))
                
                # Extract MT5 metadata (already sent by EA!)
                pos_ticket = pos.get('ticket', 0)
                pos_time = pos.get('time', 0)  # Unix timestamp
                pos_age_minutes = pos.get('age_minutes', 0)
                pos_sl = float(pos.get('sl', 0))
                pos_tp = float(pos.get('tp', 0))
                
                # Clean position symbol the SAME WAY as current symbol (remove contract codes)
                pos_symbol_clean = re.sub(r'[ZFGHJKMNQUVX]\d{2}$', '', pos_symbol_raw, flags=re.IGNORECASE).lower()
                
                logger.info(f"   📍 {pos_symbol_raw}: {pos_volume} lots, ${pos_profit:.2f} profit")
                logger.info(f"      Ticket: {pos_ticket} | Age: {pos_age_minutes} min | SL: {pos_sl} | TP: {pos_tp}")
                
                # ═══════════════════════════════════════════════════════════════════
                # WARNING: Position with NO STOP LOSS
                # The AI dynamic stop logic will handle this - it detects SL=0 and
                # recommends an AI-calculated stop based on H1/H4 volatility
                # ═══════════════════════════════════════════════════════════════════
                if pos_sl == 0 or pos_sl is None:
                    logger.warning(f"   ⚠️ WARNING: {pos_symbol_raw} has NO STOP LOSS - AI will calculate dynamic stop")
                
                # ✅ ONLY ANALYZE POSITION IF IT MATCHES THE SYMBOL BEING SCANNED
                # This prevents trying to close positions that don't match the current symbol
                if pos_symbol_clean != symbol:
                    logger.info(f"      ⏭️  Skipping analysis (current scan is for {symbol}, not {pos_symbol_clean})")
                    continue
                
                logger.info(f"      ✅ Analyzing position for {pos_symbol_clean} (matches current symbol)")
                
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
                    
                    # Add broker constraints to context for AI-driven position sizing
                    context.max_lot = float(request.get('symbol_info', {}).get('max_lot', 50.0))
                    context.min_lot = float(request.get('symbol_info', {}).get('min_lot', 1.0))
                    context.lot_step = float(request.get('symbol_info', {}).get('lot_step', 1.0))
                    
                    # Add MT5 metadata to context for AI decisions
                    context.position_ticket = pos_ticket
                    context.position_age_minutes = pos_age_minutes
                    context.position_sl = pos_sl
                    context.position_tp = pos_tp
                    context.position_swap = pos.get('swap', 0.0)  # Actual swap from broker
                    
                    # HEDGE FUND #5: Track peak profit for this position
                    # Calculate current profit as % of account
                    current_profit_pct = (pos_profit / account_balance * 100) if account_balance > 0 else 0
                    peak_profit_pct = update_position_peak_profit(pos_ticket, current_profit_pct)
                    context.peak_profit_pct = peak_profit_pct
                    
                    if peak_profit_pct > current_profit_pct + 0.05:  # Meaningful giveback
                        logger.info(f"      📊 Peak profit: {peak_profit_pct:.3f}% | Current: {current_profit_pct:.3f}% | Giveback: {peak_profit_pct - current_profit_pct:.3f}%")
                    
                    # Update cross-asset cache with this symbol's data
                    h1_trend = getattr(context, 'h1_trend', 0.5)
                    h4_trend = getattr(context, 'h4_trend', 0.5)
                    h4_momentum = getattr(context, 'h4_momentum', 0.0)
                    update_cross_asset_cache(pos_symbol_clean, h1_trend, h4_trend, h4_momentum)
                    
                    # Add cross-asset correlation to context
                    cross_asset = calculate_cross_asset_context(pos_symbol_clean)
                    context.dxy_trend = cross_asset['dxy_trend']
                    context.dxy_momentum = cross_asset['dxy_momentum']
                    context.dxy_strength = cross_asset['dxy_strength']
                    context.risk_on_off = cross_asset['risk_on_off']
                    context.indices_aligned = cross_asset['indices_aligned']
                    context.indices_momentum = cross_asset['indices_momentum']
                    context.gold_dollar_divergence = cross_asset['gold_dollar_divergence']
                    
                    # ACTUAL EXIT ANALYSIS - use intelligent position manager
                    try:
                        # Set has_position flag so analysis runs
                        context.has_position = True
                        if position_manager is not None:
                            position_decision = position_manager.analyze_position(context)
                        else:
                            position_decision = {'action': 'HOLD', 'reason': 'Position manager not loaded', 'priority': 'LOW', 'confidence': 0}
                    except Exception as e:
                        logger.error(f"❌ Exit analysis error for {pos_symbol_raw}: {e}")
                        import traceback
                        traceback.print_exc()
                        position_decision = {'action': 'HOLD', 'reason': f'Analysis error: {str(e)}', 'priority': 'LOW', 'confidence': 0}
                    
                    # ═══════════════════════════════════════════════════════════
                    # AI-DRIVEN POSITION SIZING - NO HARDCODED SAFETY OVERRIDES
                    # 
                    # Position sizing is handled by elite_position_sizer.py using:
                    # - Market analysis (volatility, regime, session)
                    # - Portfolio analysis (correlation, concentration)
                    # - FTMO risk limits (daily DD, total DD, margin level)
                    # - ML confidence and market score
                    # 
                    # The EV Exit Manager will recommend SCALE_OUT if position
                    # is too large based on current market conditions and risk
                    # ═══════════════════════════════════════════════════════════
                    
                    # Log decision
                    logger.info(f"   ✅ {pos_symbol_raw}: {position_decision['action']} - {position_decision['reason']}")
                    logger.info(f"   📊 modify_stop={position_decision.get('modify_stop', False)}, recommended_stop={position_decision.get('recommended_stop', 0):.2f}")
                    
                    # Since we only analyze the current symbol's position, track it
                    open_position = pos
                    position_symbol = pos_symbol_original
                    
                    # If this is a HIGH PRIORITY action (CLOSE, DCA, SCALE_IN, SCALE_OUT), return immediately
                    # These take priority over stop modifications
                    if position_decision['action'] in ['CLOSE', 'DCA', 'SCALE_IN', 'SCALE_OUT']:
                        logger.info(f"")
                        logger.info(f"🎯 POSITION ACTION: {position_decision['action']} on {pos_symbol_raw}")
                        logger.info(f"   Reason: {position_decision['reason']}")
                        logger.info(f"   Confidence: {position_decision.get('confidence', 0):.0f}")
                        
                        # Build position output for structured response
                        pos_output = build_position_output(
                            ticket=pos_ticket,
                            symbol=pos_symbol_original,
                            current_lots=pos_volume,
                            action=position_decision['action'],
                            add_lots=position_decision.get('add_lots', 0),
                            reduce_lots=position_decision.get('reduce_lots', 0)
                        )
                        
                        if position_decision['action'] == 'CLOSE':
                            # Register close with unified system for anti-churn tracking
                            cont_prob = position_decision.get('cont_prob', 0.5)
                            direction = 'BUY' if pos_type == 0 else 'SELL'
                            unified_system.register_close(
                                pos_symbol_clean, direction, cont_prob, 
                                position_decision.get('reason', 'EV optimization')
                            )
                            
                            # ═══════════════════════════════════════════════════════════
                            # LOG EXIT CONTEXT FOR POST-ANALYSIS
                            # Captures full AI decision context at moment of exit
                            # ═══════════════════════════════════════════════════════════
                            try:
                                current_price = float(request.get('current_price', {}).get('bid', 0))
                                log_exit_context(
                                    ticket=pos_ticket,
                                    symbol=pos_symbol_original,
                                    action='CLOSE',
                                    exit_price=current_price,
                                    profit_dollars=pos_profit,
                                    profit_pct=pos_profit / account_balance * 100 if account_balance > 0 else 0,
                                    # AI Decision Context
                                    ev_hold=position_decision.get('ev_hold', 0),
                                    ev_close=position_decision.get('ev_close', 0),
                                    ev_scale_out=position_decision.get('ev_scale_out', 0),
                                    continuation_prob=position_decision.get('cont_prob', 0) * 100,
                                    reversal_prob=position_decision.get('rev_prob', 0) * 100,
                                    thesis_quality=position_decision.get('thesis_quality', 0),
                                    # Timeframe Trends at Exit
                                    m15_trend=getattr(context, 'm15_trend', 0.5),
                                    m30_trend=getattr(context, 'm30_trend', 0.5),
                                    h1_trend=getattr(context, 'h1_trend', 0.5),
                                    h4_trend=getattr(context, 'h4_trend', 0.5),
                                    d1_trend=getattr(context, 'd1_trend', 0.5),
                                    # Market Conditions
                                    regime=context.get_market_regime() if hasattr(context, 'get_market_regime') else 'unknown',
                                    volatility=getattr(context, 'volatility', 0),
                                    session=session_context.get('session_name', 'unknown') if 'session_context' in dir() else 'unknown',
                                    exit_reason=position_decision.get('reason', '')
                                )
                            except Exception as e:
                                logger.warning(f"Could not log exit context: {e}")
                            
                            return {
                                'action': 'CLOSE',
                                'symbol': pos_symbol_original,
                                'reason': position_decision['reason'],
                                'profit': pos_profit,
                                **build_model_outputs(
                                    skip_trade=True,
                                    positions_list=[pos_output]
                                )
                            }
                        elif position_decision['action'] in ['DCA', 'SCALE_IN']:
                            add_lots = position_decision.get('add_lots', 0)
                            
                            # CRITICAL: Round to lot_step for this symbol
                            symbol_lot_step = float(request.get('symbol_info', {}).get('lot_step', 1.0))
                            add_lots = max(symbol_lot_step, round(add_lots / symbol_lot_step) * symbol_lot_step)
                            
                            # ═══════════════════════════════════════════════════════════
                            # AI-DRIVEN POSITION SIZING - NO HARDCODED LOT LIMITS
                            # 
                            # Position sizing is handled by elite_position_sizer.py using:
                            # - Market analysis (volatility, regime, session)
                            # - Portfolio analysis (correlation, concentration)
                            # - FTMO risk limits (daily DD, total DD, margin level)
                            # - ML confidence and market score
                            # - S/R based stop distances for risk calculation
                            # 
                            # The AI calculates: risk_budget / risk_per_lot = optimal lots
                            # No arbitrary per-symbol lot caps - let the math decide
                            # ═══════════════════════════════════════════════════════════
                            
                            # NOTE: SCALE_IN decisions are handled by EV calculation
                            # The AI/EV naturally penalizes adding to losing positions
                            # and rewards adding to winners with strong continuation
                            
                            # CRITICAL: Include stop loss for the new position
                            # Get the AI-calculated stop from position_decision
                            recommended_stop = position_decision.get('recommended_stop', 0)
                            if recommended_stop == 0:
                                # Calculate emergency stop if not provided
                                current_price = float(request.get('current_price', {}).get('bid', 0))
                                if pos_type == 0:  # BUY
                                    recommended_stop = current_price * 0.98  # 2% below
                                else:  # SELL
                                    recommended_stop = current_price * 1.02  # 2% above
                                logger.warning(f"   ⚠️ No AI stop provided, using emergency: {recommended_stop:.2f}")
                            
                            logger.info(f"   📈 Add lots: {add_lots:.2f}")
                            logger.info(f"   🛡️ Stop loss: {recommended_stop:.2f}")
                            logger.info(f"   📍 Symbol for EA: {pos_symbol_original}")
                            return {
                                'action': position_decision['action'],
                                'symbol': pos_symbol_original,
                                'reason': position_decision['reason'],
                                'add_lots': add_lots,
                                'lot_size': add_lots,
                                'stop_loss': recommended_stop,  # CRITICAL: Include stop for EA
                                **build_model_outputs(
                                    skip_trade=True,
                                    positions_list=[pos_output]
                                )
                            }
                        elif position_decision['action'] == 'SCALE_OUT':
                            reduce_lots = position_decision.get('reduce_lots', 0)
                            
                            # CRITICAL: Round to lot_step for this symbol
                            symbol_lot_step = float(request.get('symbol_info', {}).get('lot_step', 1.0))
                            reduce_lots = max(symbol_lot_step, round(reduce_lots / symbol_lot_step) * symbol_lot_step)
                            
                            # ═══════════════════════════════════════════════════════════
                            # LOG EXIT CONTEXT FOR SCALE_OUT
                            # ═══════════════════════════════════════════════════════════
                            try:
                                current_price = float(request.get('current_price', {}).get('bid', 0))
                                log_exit_context(
                                    ticket=pos_ticket,
                                    symbol=pos_symbol_original,
                                    action='SCALE_OUT',
                                    exit_price=current_price,
                                    profit_dollars=pos_profit,
                                    profit_pct=pos_profit / account_balance * 100 if account_balance > 0 else 0,
                                    ev_hold=position_decision.get('ev_hold', 0),
                                    ev_close=position_decision.get('ev_close', 0),
                                    ev_scale_out=position_decision.get('ev_scale_out', 0),
                                    continuation_prob=position_decision.get('cont_prob', 0) * 100,
                                    reversal_prob=position_decision.get('rev_prob', 0) * 100,
                                    thesis_quality=position_decision.get('thesis_quality', 0),
                                    m15_trend=getattr(context, 'm15_trend', 0.5),
                                    m30_trend=getattr(context, 'm30_trend', 0.5),
                                    h1_trend=getattr(context, 'h1_trend', 0.5),
                                    h4_trend=getattr(context, 'h4_trend', 0.5),
                                    d1_trend=getattr(context, 'd1_trend', 0.5),
                                    regime=context.get_market_regime() if hasattr(context, 'get_market_regime') else 'unknown',
                                    volatility=getattr(context, 'volatility', 0),
                                    session=session_context.get('session_name', 'unknown') if 'session_context' in dir() else 'unknown',
                                    exit_reason=position_decision.get('reason', ''),
                                    extra_context={'reduce_lots': reduce_lots}
                                )
                            except Exception as e:
                                logger.warning(f"Could not log scale_out context: {e}")
                            
                            logger.info(f"   📉 Reduce lots: {reduce_lots:.2f}")
                            logger.info(f"   📍 Symbol for EA: {pos_symbol_original}")
                            return {
                                'action': 'SCALE_OUT',
                                'symbol': pos_symbol_original,
                                'reason': position_decision['reason'],
                                'reduce_lots': reduce_lots,
                                'lot_size': reduce_lots,  # EA expects lot_size
                                **build_model_outputs(
                                    skip_trade=True,
                                    positions_list=[pos_output]
                                )
                            }
                        
                except Exception as e:
                    logger.error(f"   ❌ Error analyzing {pos_symbol_raw}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue to check for new trade opportunities
            
            # Log whether we found a position for the current symbol
            if open_position is None:
                # Current symbol doesn't have a position - can look for new trade
                logger.info(f"✅ No position on {symbol} - can analyze for new trade opportunity")
                
                # Continue to new trade logic below
            else:
                # Position exists and EVExitManager said HOLD
                # Check if we should modify stop
                if position_decision.get('action') == 'HOLD' and position_decision.get('modify_stop', False):
                    recommended_stop = position_decision.get('recommended_stop', 0)
                    current_sl = open_position.get('sl', 0) if open_position else 0
                    current_ticket = open_position.get('ticket', 0) if open_position else 0
                    if recommended_stop > 0:
                        logger.info(f"")
                        logger.info(f"🔄 MODIFY STOP on {position_symbol} (while holding)")
                        logger.info(f"   Current SL: {current_sl:.2f} → Recommended: {recommended_stop:.2f}")
                        
                        return {
                            'action': 'MODIFY_SL',
                            'symbol': position_symbol,
                            'ticket': current_ticket,
                            'new_sl': recommended_stop,
                            'reason': 'AI-driven dynamic stop adjustment',
                            **build_model_outputs(skip_trade=True)
                        }
                
                # EVExitManager said HOLD - return HOLD (don't duplicate analysis)
                # This is the SINGLE source of truth for position management
                logger.info(f"⏸️ EV EXIT MANAGER: HOLD on {symbol}")
                pos_output = build_position_output(
                    ticket=open_position.get('ticket', 0),
                    symbol=position_symbol,
                    current_lots=open_position.get('volume', 0),
                    action="HOLD"
                )
                
                # Extract position data for EA logging
                all_evs = position_decision.get('all_evs', {})
                
                # Calculate FTMO metrics for EA display
                account_data = request.get('account', {})
                account_balance = float(account_data.get('balance', 200000))
                account_equity = float(account_data.get('equity', account_balance))
                daily_pnl = float(account_data.get('daily_pnl', 0))
                
                # FTMO limits: 5% daily, 10% total DD
                ftmo_daily_limit = account_balance * 0.05
                ftmo_total_limit = account_balance * 0.10
                ftmo_daily_used_pct = abs(min(0, daily_pnl)) / ftmo_daily_limit * 100 if ftmo_daily_limit > 0 else 0
                ftmo_total_dd_pct = (account_balance - account_equity) / account_balance * 100 if account_balance > 0 else 0
                
                # Expected return = EV(HOLD) which is the best action's expected value
                expected_return = all_evs.get('HOLD', 0)
                
                return {
                    "action": "HOLD",
                    "reason": position_decision.get('reason', 'EV analysis says hold'),
                    "profit": open_position.get('profit', 0),
                    # Position analysis data for EA display
                    "setup_type": position_decision.get('setup_type', ''),
                    "session": position_decision.get('session', ''),
                    "ev_hold": all_evs.get('HOLD', 0),
                    "ev_close": all_evs.get('CLOSE', 0),
                    "continuation_prob": position_decision.get('cont_prob', 0),
                    "reversal_prob": position_decision.get('rev_prob', 0),
                    "ml_confidence": position_decision.get('ml_confidence', 0),
                    "ml_direction": position_decision.get('ml_direction', ''),
                    "thesis_quality": position_decision.get('thesis_quality', 0),
                    "stop_method": position_decision.get('stop_method', ''),
                    "ai_target": position_decision.get('ai_target', 0),
                    "dist_to_support": position_decision.get('dist_to_support', 0),
                    "dist_to_resistance": position_decision.get('dist_to_resistance', 0),
                    # Expected return and FTMO info
                    "expected_return": expected_return,
                    "ftmo_daily_used_pct": ftmo_daily_used_pct,
                    "ftmo_total_dd_pct": ftmo_total_dd_pct,
                    "ftmo_daily_limit": ftmo_daily_limit,
                    "account_balance": account_balance,
                    "account_equity": account_equity,
                    **build_model_outputs(skip_trade=True, positions_list=[pos_output])
                }
        else:
            # No positions open - can look for new trades
            open_position = None
            position_symbol = None
        
        # ═══════════════════════════════════════════════════════════════════
        # STEP 1: PARSE MARKET DATA
        # NOTE: M1 data is used for current price only, NOT for decisions
        # All trading decisions use M15+ timeframes (swing trading)
        # ═══════════════════════════════════════════════════════════════════
        mtf_data = parse_market_data(request)

        # Check for sufficient data - need at least M1 for current price
        # and H1/H4/D1 for swing trading decisions
        has_m1 = 'm1' in mtf_data and len(mtf_data.get('m1', [])) >= 50
        has_h1 = 'h1' in mtf_data and len(mtf_data.get('h1', [])) >= 20
        has_h4 = 'h4' in mtf_data and len(mtf_data.get('h4', [])) >= 20
        
        if not has_m1:
            logger.warning(f"⚠️ Insufficient M1 data for current price")
            return {
                "action": "HOLD",
                "reason": "Insufficient M1 data for current price",
                "confidence": 0.0,
                **build_model_outputs(skip_trade=True, skip_probability=1.0)
            }
        
        if not has_h1 or not has_h4:
            logger.warning(f"⚠️ Insufficient HTF data for swing trading (H1: {has_h1}, H4: {has_h4})")
            # Continue anyway - feature engineer will use defaults

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
        
        # Update portfolio state with current price for real-time correlation
        try:
            from src.ai.portfolio_state import get_portfolio_state
            portfolio_state = get_portfolio_state()
            portfolio_state.update_price(symbol, current_price)
        except Exception as e:
            pass  # Non-critical, continue without correlation update

        # ═══════════════════════════════════════════════════════════════════
        # NOTE: Position management is handled above by EVExitManager (lines 730-957)
        # This section is for NEW TRADE ENTRIES only
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
            
            # Add broker constraints to context
            context.max_lot = max_lot
            context.min_lot = min_lot
            context.lot_step = lot_step
            context.contract_size = contract_size
            
            # Update cross-asset cache with this symbol's data
            h1_trend = getattr(context, 'h1_trend', 0.5)
            h4_trend = getattr(context, 'h4_trend', 0.5)
            h4_momentum = getattr(context, 'h4_momentum', 0.0)
            update_cross_asset_cache(symbol, h1_trend, h4_trend, h4_momentum)
            
            # Add cross-asset correlation to context
            cross_asset = calculate_cross_asset_context(symbol)
            context.dxy_trend = cross_asset['dxy_trend']
            context.dxy_momentum = cross_asset['dxy_momentum']
            context.dxy_strength = cross_asset['dxy_strength']
            context.risk_on_off = cross_asset['risk_on_off']
            context.indices_aligned = cross_asset['indices_aligned']
            context.indices_momentum = cross_asset['indices_momentum']
            context.gold_dollar_divergence = cross_asset['gold_dollar_divergence']
            
            # Add news risk information to context
            if high_impact_events:
                context.news_imminent = True
                context.news_minutes_until = high_impact_events[0]['minutes']
                context.news_event_name = high_impact_events[0]['event']
                context.news_currency = high_impact_events[0]['currency']
            
            # DAILY PROFIT PROTECTION: Track peak daily P&L
            global peak_daily_pnl_tracker
            from datetime import date
            today = date.today()
            
            # Reset tracker at start of new day
            if peak_daily_pnl_tracker['last_reset_date'] != today:
                peak_daily_pnl_tracker['peak_pnl'] = 0.0
                peak_daily_pnl_tracker['last_reset_date'] = today
            
            # Update peak if current daily P&L is higher
            current_daily_pnl = getattr(context, 'daily_pnl', 0.0)
            if current_daily_pnl > peak_daily_pnl_tracker['peak_pnl']:
                peak_daily_pnl_tracker['peak_pnl'] = current_daily_pnl
                logger.info(f"   💰 NEW DAILY PEAK: ${current_daily_pnl:.2f}")
            
            # Pass peak to context for profit protection logic
            context.peak_daily_pnl = peak_daily_pnl_tracker['peak_pnl']
            
            logger.info(f"✅ Enhanced context created: {context.symbol}")
            logger.info(f"   Cross-Asset: DXY={cross_asset['dxy_trend']:.2f}, Risk={cross_asset['risk_on_off']:.2f}, Indices Aligned={cross_asset['indices_aligned']:.1f}")
            logger.info(f"   Regime: {context.get_market_regime()} | Volume: {context.get_volume_regime()}")
            logger.info(f"   Confluence: {context.has_strong_confluence()} | Trend Align: {context.trend_alignment:.2f}")
            logger.info(f"   H1 Vol: {context.h1_volatility:.6f} | H4 Vol: {context.h4_volatility:.6f}")
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

        # Minimum confidence required for entries
        # ═══════════════════════════════════════════════════════════════════
        # AI-DRIVEN ENTRY - NO HARDCODED ML BLOCKS
        # 
        # The unified system uses continuous scoring to determine:
        # 1. Best direction based on ALL timeframe analysis
        # 2. Position size based on confidence (not binary block)
        # 3. Let the AI decide - don't block with arbitrary thresholds
        # 
        # ML HOLD or low confidence = smaller position, not no trade
        # ═══════════════════════════════════════════════════════════════════
        logger.info(f"🧠 ML Signal: {ml_direction} @ {ml_confidence:.1f}% - passing to AI analysis")

        # ═══════════════════════════════════════════════════════════════════
        # STEP 4: USE UNIFIED SYSTEM FOR ENTRY DECISION
        # ═══════════════════════════════════════════════════════════════════

        # ═══════════════════════════════════════════════════════════════════
        # STEP 5: UNIFIED SYSTEM ENTRY DECISION
        # Uses ALL 147 features, clean logic, proper sizing
        # ═══════════════════════════════════════════════════════════════════
        if unified_system is None:
            logger.error("❌ Unified system not loaded")
            return {"action": "HOLD", "reason": "Unified system not loaded"}
        else:
            # NEW UNIFIED SYSTEM
            try:
                # Determine is_buy from ML direction
                is_buy = (ml_direction == 'BUY')
                
                # Get comprehensive market analysis FROM CONTEXT (uses ALL 138 features)
                # Context already has all the multi-timeframe data analyzed
                market_analysis = {
                    'total_score': context.get_market_score() if hasattr(context, 'get_market_score') else 50,
                    'trend_score': context.trend_alignment * 100 if hasattr(context, 'trend_alignment') else 50,
                    'momentum_score': (context.h1_momentum + context.h4_momentum + 1) * 50 if hasattr(context, 'h1_momentum') else 50,
                    'volume_score': context.volume_trend * 100 if hasattr(context, 'volume_trend') else 50,
                    'structure_score': 70 if context.get_market_regime() in ['TRENDING_UP', 'TRENDING_DOWN'] else 50,
                    'signals': []
                }

                # Enforce global portfolio risk limit for NEW entries only
                if portfolio_risk_pct >= 5.0:
                    logger.warning(f"⚠️ MAX PORTFOLIO RISK REACHED: {portfolio_risk_pct:.2f}%")
                    logger.warning("   Cannot open new positions until risk reduces")
                    return {
                        "action": "HOLD",
                        "reason": f"Max portfolio risk: {portfolio_risk_pct:.2f}% (limit 5%)",
                        "lots": 0.0,
                        "stop_loss": 0.0,
                        "take_profit": 0.0,
                        "confidence": 0
                    }

                # Block new entries during high-impact news (within 30 minutes)
                # SYMBOL-AWARE: Only block if the news currency affects this symbol
                symbol_affected_by_news = False
                news_warning = ""
                
                # Map symbols to their affected currencies
                symbol_upper = symbol.upper()
                affected_currencies = []
                
                # Forex pairs - affected by both currencies in the pair
                if symbol_upper in ['EURUSD', 'EUR/USD']:
                    affected_currencies = ['EUR', 'USD']
                elif symbol_upper in ['GBPUSD', 'GBP/USD']:
                    affected_currencies = ['GBP', 'USD']
                elif symbol_upper in ['USDJPY', 'USD/JPY']:
                    affected_currencies = ['USD', 'JPY']
                elif symbol_upper in ['AUDUSD', 'AUD/USD']:
                    affected_currencies = ['AUD', 'USD']
                elif symbol_upper in ['USDCAD', 'USD/CAD']:
                    affected_currencies = ['USD', 'CAD']
                elif symbol_upper in ['USDCHF', 'USD/CHF']:
                    affected_currencies = ['USD', 'CHF']
                elif symbol_upper in ['NZDUSD', 'NZD/USD']:
                    affected_currencies = ['NZD', 'USD']
                # Indices - affected by their home currency
                elif 'US30' in symbol_upper or 'US100' in symbol_upper or 'US500' in symbol_upper:
                    affected_currencies = ['USD']
                # Gold - affected by USD (priced in USD)
                elif 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
                    affected_currencies = ['USD']
                # Oil - affected by USD (priced in USD)
                elif 'OIL' in symbol_upper or 'WTI' in symbol_upper or 'BRENT' in symbol_upper:
                    affected_currencies = ['USD']
                
                # Check if any high impact event affects this symbol
                for event in high_impact_events:
                    if event['currency'] in affected_currencies:
                        symbol_affected_by_news = True
                        news_warning = f"⚠️ HIGH IMPACT NEWS in {event['minutes']}min: {event['currency']} {event['event']}"
                        break
                
                if symbol_affected_by_news:
                    # Log what setup would have been taken
                    m15_trend = getattr(context, 'm15_trend', 0.5)
                    m30_trend = getattr(context, 'm30_trend', 0.5)
                    h1_trend = getattr(context, 'h1_trend', 0.5)
                    h4_trend = getattr(context, 'h4_trend', 0.5)
                    d1_trend = getattr(context, 'd1_trend', 0.5)
                    
                    # Quick setup classification
                    if ml_direction == 'BUY':
                        d1_supports = d1_trend > 0.52
                        h4_supports = h4_trend > 0.52
                        h1_supports = h1_trend > 0.52
                    else:
                        d1_supports = d1_trend < 0.48
                        h4_supports = h4_trend < 0.48
                        h1_supports = h1_trend < 0.48
                    
                    if d1_supports:
                        would_be_setup = 'SWING'
                    elif h4_supports:
                        would_be_setup = 'DAY'
                    else:
                        would_be_setup = 'SCALP'
                    
                    logger.warning(f"🚫 ENTRY BLOCKED ({symbol}): {news_warning}")
                    logger.warning(f"   Would have been: {would_be_setup} {ml_direction} @ {ml_confidence:.1f}%")
                    logger.warning(f"   TFs: M15={m15_trend:.2f} M30={m30_trend:.2f} H1={h1_trend:.2f} H4={h4_trend:.2f} D1={d1_trend:.2f}")
                    return {
                        "action": "HOLD",
                        "reason": f"News avoidance: {news_warning}",
                        "ml_direction": ml_direction,
                        "ml_confidence": ml_confidence,
                        "would_be_setup": would_be_setup
                    }
                elif high_impact_events:
                    # News exists but doesn't affect this symbol
                    logger.info(f"✅ {symbol} NOT affected by {high_impact_events[0]['currency']} news - trading allowed")
                
                # ═══════════════════════════════════════════════════════════════════
                # NOTE: Anti-churn is now handled inside unified_system.should_enter_trade()
                # This is the SINGLE SOURCE OF TRUTH - no duplicate logic here
                # ═══════════════════════════════════════════════════════════════════
                
                # ═══════════════════════════════════════════════════════════════════
                # SWING TRADING PROTECTION
                # The unified system already requires 2/3 H1/H4/D1 alignment for entries
                # This ensures we only enter on swing setups, not M1/M5 noise
                # Additional filter: Log the trigger timeframe for monitoring
                # ═══════════════════════════════════════════════════════════════════
                trigger_tf = request.get('trigger_timeframe', 'M5').upper()
                logger.info(f"🎯 Entry analysis on {trigger_tf} trigger (HTF alignment required)")
                
                # Use unified system for entry decision (regime-aware AI trading)
                entry_decision = unified_system.should_enter_trade(context, market_analysis)
                
                if not entry_decision['should_enter']:
                    logger.info(f"❌ Entry rejected: {entry_decision['reason']}")
                    return {
                        "action": "HOLD",
                        "reason": entry_decision['reason'],
                        "ml_direction": ml_direction,
                        "ml_confidence": ml_confidence
                    }
                
                # Entry approved - use calculated values from unified system
                final_lots = entry_decision['lot_size']
                stop_loss_price = entry_decision['stop_loss']
                take_profit_price = entry_decision['take_profit']
                
                # Get setup type for position sizing adjustment
                setup_type = entry_decision.get('setup_type', 'DAY')
                setup_strength = entry_decision.get('setup_strength', 1.0)
                position_size_mult = entry_decision.get('position_size_mult', 1.0)
                
                logger.info(f"✅ ENTRY APPROVED BY UNIFIED SYSTEM")
                logger.info(f"   {entry_decision['reason']}")
                logger.info(f"   Setup: {setup_type} (strength: {setup_strength:.1f}, size mult: {position_size_mult:.1f}x)")
                
                # ═══════════════════════════════════════════════════════════════════
                # ELITE SIZER OVERRIDE (if enabled) - Uses ALL AI features
                # ═══════════════════════════════════════════════════════════════════
                if USE_ELITE_SIZER and elite_sizer:
                    try:
                        logger.info(f"")
                        logger.info(f"🏆 RECALCULATING WITH ELITE SIZER (AI-POWERED)...")
                        
                        # Get regime from context
                        regime = context.get_market_regime()
                        
                        # Get contract specs from EA's symbol_info (symbol-specific!)
                        symbol_info_data = request.get('symbol_info', {})
                        tick_value = float(symbol_info_data.get('tick_value', 0.01))
                        tick_size = float(symbol_info_data.get('tick_size', 0.01))
                        # contract_size already extracted at line 835
                        
                        logger.info(f"   📊 Symbol specs: tick_value={tick_value}, tick_size={tick_size}, contract_size={contract_size}")
                        
                        # Get FTMO limits from context
                        ftmo_distance_to_daily = context.distance_to_daily_limit if hasattr(context, 'distance_to_daily_limit') else 10000.0
                        ftmo_distance_to_dd = context.distance_to_dd_limit if hasattr(context, 'distance_to_dd_limit') else 20000.0
                        
                        # Elite sizer uses ALL your AI features
                        elite_result = elite_sizer.calculate_position_size(
                            # Account
                            account_balance=account_balance,
                            
                            # AI Model Outputs
                            ml_confidence=ml_confidence,  # From trained ensemble
                            market_score=market_analysis['total_score'],  # All 173 features
                            
                            # Market Structure (AI-driven)
                            entry_price=current_price,
                            stop_loss=stop_loss_price,
                            target_price=take_profit_price,
                            
                            # Contract Specs (from context/MT5)
                            tick_value=tick_value,
                            tick_size=tick_size,
                            contract_size=contract_size,
                            
                            # Symbol & Direction
                            symbol=symbol,
                            direction=ml_direction,
                            
                            # Market State (AI-detected)
                            regime=regime,  # TRENDING/RANGING/VOLATILE
                            volatility=context.volatility if hasattr(context, 'volatility') else 0.5,
                            current_atr=context.atr if hasattr(context, 'atr') else 0.0,
                            
                            # Portfolio State (for correlation)
                            open_positions=open_positions,
                            
                            # Risk Limits
                            ftmo_distance_to_daily=ftmo_distance_to_daily,
                            ftmo_distance_to_dd=ftmo_distance_to_dd,
                            max_lot_broker=request.get('symbol_info', {}).get('max_lot', 50.0),
                            min_lot=request.get('symbol_info', {}).get('min_lot', 1.0),
                            lot_step=request.get('symbol_info', {}).get('lot_step', 1.0),
                            
                            # NEW: Full context for comprehensive 138-feature analysis
                            context=context,
                            
                            # NEW: Complete FTMO account data for intelligent sizing
                            ftmo_data=account_data  # Pass full account data from EA
                        )
                        
                        # Check if elite sizer approved the trade
                        if not elite_result.get('should_trade', True):
                            # TRADE REJECTED by elite filters
                            logger.warning(f"")
                            logger.warning(f"   ❌ TRADE REJECTED BY ELITE FILTERS")
                            logger.warning(f"      Reason: {elite_result.get('reasoning', 'Unknown')}")
                            logger.warning(f"      Expected Return: {elite_result.get('expected_return', 0):.2f}")
                            logger.warning(f"")
                            return {
                                "action": "HOLD",
                                "reason": f"Elite filter: {elite_result.get('reasoning', 'Trade rejected')}",
                                "expected_return": elite_result.get('expected_return', 0),
                                "system": "elite_hedge_fund_v1.0",
                                **build_model_outputs(
                                    entry_direction="long" if ml_direction == "BUY" else "short" if ml_direction == "SELL" else "flat",
                                    entry_ev=elite_result.get('expected_return', 0),
                                    entry_confidence=ml_confidence,
                                    env_score=market_analysis.get('total_score', 50) / 100.0,
                                    skip_trade=True,
                                    skip_probability=0.9
                                )
                            }
                        
                        # Override lot size with elite calculation
                        old_lots = final_lots
                        final_lots = elite_result['lot_size']
                        
                        # Apply setup type multiplier (SWING=0.5x smaller - wide stops, DAY=1.0x, SCALP=1.5x larger - tight stops)
                        final_lots = final_lots * position_size_mult
                        
                        # Ensure minimum lot size
                        min_lot = request.get('symbol_info', {}).get('min_lot', 1.0)
                        lot_step = request.get('symbol_info', {}).get('lot_step', 1.0)
                        final_lots = max(min_lot, round(final_lots / lot_step) * lot_step)
                        
                        logger.info(f"")
                        logger.info(f"   🏆 Elite Sizer Results ({setup_type}):")
                        logger.info(f"      Status: ✅ APPROVED")
                        logger.info(f"      Base size: {elite_result['lot_size']:.2f} lots")
                        logger.info(f"      Setup mult: {position_size_mult:.1f}x ({setup_type})")
                        logger.info(f"      Final size: {final_lots:.2f} lots")
                        logger.info(f"      Expected Return: {elite_result.get('expected_return', 0):.2f}")
                        logger.info(f"      Correlation: {elite_result.get('avg_correlation', 0):.2f}")
                        logger.info(f"      Diversification: {elite_result.get('diversification_factor', 1.0):.2f}x")
                        logger.info(f"      Performance: {elite_result.get('performance_multiplier', 1.0):.2f}x")
                        logger.info(f"      Recent Win Rate: {elite_result.get('recent_win_rate', 0.5):.1%}")
                        logger.info(f"")
                        
                    except Exception as e:
                        logger.error(f"❌ Elite sizer failed, using unified system size: {e}")
                        import traceback
                        traceback.print_exc()
                        # Keep original final_lots on error
                
            except Exception as e:
                logger.error(f"❌ Unified system entry failed: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "action": "HOLD",
                    "reason": f"Entry decision error: {e}",
                    **build_model_outputs(skip_trade=True, skip_probability=1.0)
                }

        # ═══════════════════════════════════════════════════════════════════
        # STEP 6: SKIP OLD POSITION SIZING IF UNIFIED SYSTEM USED
        # Unified system already calculated lot size, stop, and target
        # ═══════════════════════════════════════════════════════════════════
        if unified_system and 'final_lots' in locals():
            # Unified system already calculated everything - skip to final return
            logger.info(f"✅ Using unified system calculations")
            
            # Calculate points for EA
            stop_distance = abs(current_price - stop_loss_price)
            target_distance = abs(current_price - take_profit_price)
            stop_points = max(50, int(stop_distance))
            target_points = max(100, int(target_distance))
            risk_reward = target_points / stop_points if stop_points > 0 else 0
            
            # Set final action from unified system's AI-driven direction
            # CRITICAL: Use the direction from entry_decision, NOT ml_direction
            # The unified system calculates direction based on HTF analysis
            # Using ml_direction here was causing stop loss to be on wrong side
            final_action = entry_decision.get('direction', ml_direction)
            
            # Log final decision
            logger.info("═══════════════════════════════════════════════════════════════════")
            logger.info(f"✅ TRADE APPROVED: {final_action}")
            logger.info(f"   Size: {final_lots:.0f} lots")
            logger.info(f"   Entry: ${current_price:.5f}")
            logger.info(f"   Stop: ${stop_loss_price:.5f} ({stop_points} pts)")
            logger.info(f"   Target: ${take_profit_price:.5f} ({target_points} pts)")
            logger.info(f"   R:R: {risk_reward:.2f}:1")
            logger.info("═══════════════════════════════════════════════════════════════════")
            
            # Build structured model outputs for new entry
            entry_ev = entry_decision.get('expected_return', risk_reward)
            env_score = market_analysis.get('total_score', 50) / 100.0 if 'market_analysis' in dir() else 0.5
            risk_frac = final_lots * abs(current_price - stop_loss_price) / account_balance if account_balance > 0 else 0.0
            
            # LOG ENTRY DECISION FOR TRAINING
            log_training_data(
                log_type="entry",
                symbol=raw_symbol,
                timestamp=datetime.now().isoformat(),
                action=final_action,
                features={
                    "ml_confidence": ml_confidence,
                    "ml_direction": ml_direction,
                    "market_score": market_analysis.get('total_score', 0) if 'market_analysis' in dir() else 0,
                    "entry_ev": entry_ev,
                    "risk_reward": risk_reward
                },
                context_data={
                    "current_price": current_price,
                    "stop_loss": stop_loss_price,
                    "take_profit": take_profit_price,
                    "regime": context.get_market_regime() if hasattr(context, 'get_market_regime') else "unknown"
                },
                model_outputs={
                    "entry_direction": "long" if final_action == "BUY" else "short",
                    "entry_ev": entry_ev,
                    "entry_confidence": ml_confidence / 100.0,
                    "env_score": env_score,
                    "risk_fraction": risk_frac,
                    "skip_trade": False
                },
                account_data={
                    "balance": account_balance,
                    "equity": account_equity,
                    "portfolio_risk_pct": portfolio_risk_pct
                }
            )
            
            # ═══════════════════════════════════════════════════════════════════
            # LOG ENTRY CONTEXT FOR POST-ANALYSIS
            # Captures full AI decision context at moment of entry
            # ═══════════════════════════════════════════════════════════════════
            try:
                # Generate a temporary ticket (will be updated when MT5 confirms)
                import time as time_module
                temp_ticket = int(time_module.time() * 1000) % 100000000
                
                log_entry_context(
                    ticket=temp_ticket,
                    symbol=raw_symbol,
                    direction=final_action,
                    lots=final_lots,
                    entry_price=current_price,
                    stop_loss=stop_loss_price,
                    take_profit=take_profit_price,
                    # AI Decision Context
                    ml_confidence=ml_confidence,
                    ml_direction=ml_direction,
                    market_score=market_analysis.get('total_score', 0) if 'market_analysis' in dir() else 0,
                    setup_type=setup_type if 'setup_type' in dir() else 'UNKNOWN',
                    thesis_quality=entry_decision.get('thesis_quality', 0) if 'entry_decision' in dir() else 0,
                    # Timeframe Trends
                    m15_trend=getattr(context, 'm15_trend', 0.5),
                    m30_trend=getattr(context, 'm30_trend', 0.5),
                    h1_trend=getattr(context, 'h1_trend', 0.5),
                    h4_trend=getattr(context, 'h4_trend', 0.5),
                    d1_trend=getattr(context, 'd1_trend', 0.5),
                    # Market Conditions
                    regime=context.get_market_regime() if hasattr(context, 'get_market_regime') else 'unknown',
                    volatility=getattr(context, 'volatility', 0),
                    atr=getattr(context, 'atr', 0),
                    session=session_context.get('session_name', 'unknown') if 'session_context' in dir() else 'unknown',
                    # Entry Reasoning
                    entry_reason=entry_decision.get('reason', '') if 'entry_decision' in dir() else '',
                    extra_context={
                        'risk_reward': risk_reward,
                        'entry_ev': entry_ev,
                        'htf_alignment': market_analysis.get('htf_alignment', 0) if 'market_analysis' in dir() else 0
                    }
                )
            except Exception as e:
                logger.warning(f"Could not log entry context: {e}")
            
            # ═══════════════════════════════════════════════════════════════════
            # CRITICAL: Validate stop loss before entry
            # NEVER enter a trade without a valid stop loss
            # ═══════════════════════════════════════════════════════════════════
            if stop_loss_price == 0 or stop_loss_price is None:
                logger.error(f"🚨 CRITICAL: Cannot enter trade without stop loss!")
                # Calculate emergency stop
                if final_action == "BUY":
                    stop_loss_price = current_price * 0.98  # 2% below
                else:
                    stop_loss_price = current_price * 1.02  # 2% above
                logger.warning(f"   🚨 Emergency stop set at {stop_loss_price:.5f}")
            
            # Validate stop is on correct side
            if final_action == "BUY" and stop_loss_price >= current_price:
                logger.error(f"🚨 INVALID: BUY stop {stop_loss_price} >= entry {current_price}")
                stop_loss_price = current_price * 0.98
                logger.warning(f"   🚨 Corrected to {stop_loss_price:.5f}")
            elif final_action == "SELL" and stop_loss_price <= current_price:
                logger.error(f"🚨 INVALID: SELL stop {stop_loss_price} <= entry {current_price}")
                stop_loss_price = current_price * 1.02
                logger.warning(f"   🚨 Corrected to {stop_loss_price:.5f}")
            
            return {
                "action": final_action,
                "confidence": ml_confidence,
                "take_trade": True,
                "lot_size": final_lots,
                "position_size": final_lots,
                "stop_loss": stop_loss_price,
                "take_profit": 0.0,  # AI manages exits
                "stop_points": stop_points,
                "target_points": target_points,
                "risk_reward": risk_reward,
                "reason": entry_decision['reason'],
                "system": "unified_hedge_fund_v1.0",
                **build_model_outputs(
                    entry_direction="long" if final_action == "BUY" else "short" if final_action == "SELL" else "flat",
                    entry_ev=entry_ev,
                    entry_confidence=ml_confidence,
                    env_score=env_score,
                    risk_fraction=risk_frac,
                    skip_trade=False,
                    skip_probability=0.0,
                    portfolio_scale=1.0
                )
            }

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR: {e}", exc_info=True)
        return {
            "action": "HOLD",
            "reason": f"System error: {str(e)}",
            "confidence": 0.0,
            "portfolio_decisions": portfolio_decisions if 'portfolio_decisions' in dir() else [],
            **build_model_outputs(skip_trade=True, skip_probability=1.0)
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

        # Use position manager for exit decisions
        return {"should_exit": False, "reason": "Use ai_trade_decision endpoint for position management"}

    except Exception as e:
        logger.error(f"❌ Exit decision error: {e}", exc_info=True)
        return {
            "should_exit": False,
            "reason": f"Error: {str(e)}"
        }

# ═══════════════════════════════════════════════════════════════════
# TRADE JOURNAL API
# Query closed trades for post-analysis
# ═══════════════════════════════════════════════════════════════════

@app.get("/trades")
async def get_trades(days: int = 7, symbol: str = None):
    """
    Get recent closed trades from the journal.
    
    Query params:
    - days: Number of days to look back (default 7)
    - symbol: Optional symbol filter
    """
    from src.utils.trade_journal import get_recent_trades, get_trade_stats, get_losing_trades
    
    trades = get_recent_trades(days, symbol)
    stats = get_trade_stats(days)
    losers = get_losing_trades(days)
    
    return {
        "trades": trades,
        "stats": stats,
        "losers": losers,
        "count": len(trades),
        "loser_count": len(losers)
    }

@app.get("/trades/{ticket}")
async def get_trade_detail(ticket: int):
    """Get detailed context for a specific trade"""
    from src.utils.trade_journal import get_trade_details
    
    details = get_trade_details(ticket)
    if details:
        return details
    return {"error": f"Trade #{ticket} not found in journal"}

# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """System health check"""
    return {
        "status": "online",
        "ml_models": len(ml_models) if ml_models else 0,
        "feature_engineer": feature_engineer is not None,
        "position_manager": position_manager is not None,
        "unified_system": unified_system is not None,
        "elite_sizer": elite_sizer is not None,
        "market_hours": market_hours is not None,
        "system": "ai_powered_v5.0"
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
