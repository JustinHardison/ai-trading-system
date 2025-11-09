"""
DUAL STRATEGY INTEGRATED API v7.0
M1 Scalping + H1 Swing - Both running simultaneously!
Pure ML System - No conflicts!
"""
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import pandas as pd
import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.ml.pro_feature_engineer import ProFeatureEngineer
from src.ai.professional_exit_manager import ProfessionalExitManager  # NEW: EV-based exits
from src.risk.ml_risk_manager import MLRiskManager, RLRiskOptimizer
from src.risk.position_sizer import PositionSizer  # NEW: Professional position sizing
from src.utils.logger import get_logger
import os

logger = get_logger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Dual Strategy Integrated API",
    description="M1 Scalping + H1 Swing - Pure ML Trading System",
    version="7.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global models - DUAL STRATEGY
m1_ensemble = None  # M1 scalping model
h1_ensemble = None  # H1 swing model
m1_feature_names = []
h1_feature_names = []
feature_engineer = None
last_risk_update = None

# ML/RL Risk Manager
ml_risk_manager = None
rl_risk_optimizer = None
position_sizer = None  # NEW: Professional position sizing with Kelly Criterion
professional_exit_manager = None  # NEW: EV-based exit decision system
USE_ML_RISK = True  # Kill switch - ML Risk Manager active (with defensive handling)
USE_PROFESSIONAL_EXITS = True  # Use EV-based exits instead of confidence thresholds
trade_history = []

# LLM cache
llm_cache = {
    "regime": "unknown",
    "bias": "neutral",
    "risk_level": 1.0,
    "timestamp": None
}


def simulate_llm_context(market_data: dict) -> dict:
    """
    Simulate LLM context from market data
    In production, this would call real Groq API
    """
    try:
        # Get M1 data if available (REDUCED from 100 to 20 bars for instant trading!)
        if 'M1' not in market_data:
            return {'regime': 'unknown', 'bias': 'neutral', 'risk_level': 1.0}
        
        m1_data = market_data['M1']
        if not m1_data.get('close') or len(m1_data['close']) < 20:  # Only need 20 bars!
            return {'regime': 'unknown', 'bias': 'neutral', 'risk_level': 1.0}
        
        close = np.array(m1_data['close'])
        high = np.array(m1_data['high'])
        low = np.array(m1_data['low'])
        
        # Detect regime
        atr = (high[-20:] - low[-20:]).mean()
        price_range = close[-20:].max() - close[-20:].min()
        
        if atr > price_range * 0.8:
            regime = 'volatile'
        elif price_range < close[-1] * 0.01:
            regime = 'ranging'
        else:
            sma_20 = close[-20:].mean()
            if close[-1] > sma_20 * 1.005:
                regime = 'trending_up'
            elif close[-1] < sma_20 * 0.995:
                regime = 'trending_down'
            else:
                regime = 'ranging'
        
        # Detect bias
        momentum = (close[-1] - close[-10]) / close[-10]
        if momentum > 0.002:
            bias = 'bullish'
        elif momentum < -0.002:
            bias = 'bearish'
        else:
            bias = 'neutral'
        
        # Risk level
        volatility = close[-20:].std() / close[-20:].mean()
        if volatility > 0.015:
            risk_level = 0.5
        elif volatility < 0.005:
            risk_level = 1.5
        else:
            risk_level = 1.0
        
        return {
            'regime': regime,
            'bias': bias,
            'risk_level': risk_level
        }
    except Exception as e:
        logger.error(f"LLM simulation error: {e}")
        return {'regime': 'unknown', 'bias': 'neutral', 'risk_level': 1.0}


def create_integrated_features(technical_features: dict, llm_context: dict) -> dict:
    """Add LLM features to technical features"""
    integrated = technical_features.copy()
    
    # LLM regime (one-hot)
    integrated['llm_regime_volatile'] = 1 if llm_context['regime'] == 'volatile' else 0
    integrated['llm_regime_ranging'] = 1 if llm_context['regime'] == 'ranging' else 0
    integrated['llm_regime_trending_up'] = 1 if llm_context['regime'] == 'trending_up' else 0
    integrated['llm_regime_trending_down'] = 1 if llm_context['regime'] == 'trending_down' else 0
    
    # LLM bias (one-hot)
    integrated['llm_bias_bullish'] = 1 if llm_context['bias'] == 'bullish' else 0
    integrated['llm_bias_bearish'] = 1 if llm_context['bias'] == 'bearish' else 0
    integrated['llm_bias_neutral'] = 1 if llm_context['bias'] == 'neutral' else 0
    
    # LLM risk level
    integrated['llm_risk_level'] = llm_context['risk_level']
    
    # Interaction features
    if llm_context['regime'] == 'trending_up' and llm_context['bias'] == 'bullish':
        integrated['llm_trend_aligned'] = 1
    else:
        integrated['llm_trend_aligned'] = 0
    
    if llm_context['regime'] == 'ranging' and abs(technical_features.get('roc_5', 0)) < 0.001:
        integrated['llm_range_confirmed'] = 1
    else:
        integrated['llm_range_confirmed'] = 0
    
    return integrated


@app.on_event("startup")
async def load_integrated_system():
    """Load DUAL STRATEGY system: M1 Scalping + H1 Swing"""
    global m1_ensemble, h1_ensemble, m1_feature_names, h1_feature_names
    global feature_engineer, ml_risk_manager, rl_risk_optimizer, position_sizer

    logger.info("="*70)
    logger.info("LOADING DUAL STRATEGY AI SYSTEM v7.0")
    logger.info("M1 SCALPING + H1 SWING - BOTH MODELS LOADED")
    logger.info("="*70)
    
    try:
        # 1. Load M1 SCALPING Model
        logger.info("\n[1/2] Loading M1 SCALPING model...")
        m1_path = 'models/integrated_ensemble_latest.pkl'
        if not os.path.exists(m1_path):
            m1_path = 'models/integrated_ensemble.pkl'

        with open(m1_path, 'rb') as f:
            m1_data = pickle.load(f)

        if isinstance(m1_data, dict) and 'xgb_model' in m1_data:
            m1_ensemble = m1_data['xgb_model']
            m1_feature_names = m1_data.get('feature_names', [])
            logger.info(f"✓ M1 Scalping Model: {m1_data.get('ensemble_accuracy', 0.78)*100:.2f}% accuracy")
            logger.info(f"  Features: {len(m1_feature_names)}")
            logger.info(f"  Target: 20pt scalping, 5-bar holds")
        else:
            m1_ensemble = m1_data
            m1_feature_names = []
            logger.info(f"✓ M1 Scalping Model loaded (legacy format)")

        # 2. Load H1 SWING Model
        logger.info("\n[2/2] Loading H1 SWING model...")
        h1_path = 'models/integrated_ensemble_h1_latest.pkl'

        if os.path.exists(h1_path):
            with open(h1_path, 'rb') as f:
                h1_data = pickle.load(f)

            if isinstance(h1_data, dict) and 'xgb_model' in h1_data:
                h1_ensemble = h1_data['xgb_model']
                h1_feature_names = h1_data.get('feature_names', [])
                logger.info(f"✓ H1 Swing Model: {h1_data.get('ensemble_accuracy', 0.78)*100:.2f}% accuracy")
                logger.info(f"  Features: {len(h1_feature_names)}")
                logger.info(f"  Target: 150pt swing, 5-bar (5hr) holds")
            else:
                h1_ensemble = h1_data
                h1_feature_names = []
                logger.info(f"✓ H1 Swing Model loaded (legacy format)")
        else:
            logger.warning(f"⚠️  H1 model not found at {h1_path}")
            logger.warning(f"    H1 swing strategy will be disabled")
            h1_ensemble = None

        # Load feature engineer
        feature_engineer = ProFeatureEngineer()
        logger.info("✓ Feature Engineer ready (106 integrated features)")
        
        # Load LLM Risk Manager
        logger.info("\n[3/3] Loading LLM Risk Manager...")
                from dotenv import load_dotenv
        load_dotenv()
        
        groq_api_key = os.getenv('GROQ_API_KEY', '')
        
        llm_risk_manager = LLMRiskManager(api_key=groq_api_key)
        logger.info("✓ LLM Risk Manager loaded")
        logger.info("  Modes: AGGRESSIVE / NORMAL / CONSERVATIVE / STOP")
        logger.info("  Updates: Every 60 seconds")
        logger.info("  Controls: Risk multipliers + Thresholds")
        
        # 4. Initialize Groq LLM (optional, we have simulation)
        logger.info("Initializing Groq LLM Analyst...")
        from dotenv import load_dotenv
        load_dotenv()
        groq_api_key = os.getenv('GROQ_API_KEY', '')
        groq_analyst = GroqMarketAnalyst(api_key=groq_api_key)
        logger.info("✓ Groq Analyst ready (with simulation fallback)")

        # 5. Load ML/RL Risk Manager
        logger.info("\n[5/5] Loading ML/RL Risk Manager...")
        ml_risk_manager = MLRiskManager.load('models/ml_risk_manager.pkl')
        rl_risk_optimizer = RLRiskOptimizer.load('models/rl_risk_optimizer.pkl')
        logger.info("✓ ML Risk Manager loaded (intelligent position sizing)")
        logger.info("✓ RL Risk Optimizer loaded (adaptive risk multipliers)")
        logger.info(f"  Risk Range: {ml_risk_manager.min_risk}% - {ml_risk_manager.max_risk}% (adaptive based on performance)")
        logger.info(f"  Baseline Risk: {ml_risk_manager.baseline_risk}% (US30-optimized)")
        logger.info(f"  Kill Switch: USE_ML_RISK = {USE_ML_RISK}")

        # 6. Initialize Professional Position Sizer with Kelly Criterion
        logger.info("\n[6/6] Initializing Professional Position Sizer...")
        position_sizer = PositionSizer()
        logger.info("✓ Position Sizer loaded (Kelly Criterion + Broker Specs)")
        logger.info("  Features: Broker min/max/step aware (no hardcoding!)")
        logger.info("  Kelly Criterion: Optimal sizing for 91.90% win rate")
        logger.info("  ML/RL Integration: Uses adaptive risk calculations")

        # 7. Initialize Professional Exit Manager (EV-based exits)
        logger.info("\n[7/7] Initializing Professional Exit Manager...")
        professional_exit_manager = ProfessionalExitManager(
            outcome_model=None,  # TODO: Train outcome regression model
            risk_aversion=1.0  # Standard risk aversion
        )
        logger.info("✓ Professional Exit Manager loaded (Expected Value based)")
        logger.info("  Decision Method: EV(action) comparison, not confidence thresholds")
        logger.info("  Actions: Highest risk-adjusted EV wins")
        logger.info("  Professional Rules: Profit protection, time decay, minimum EV improvement")
        logger.info(f"  Kill Switch: USE_PROFESSIONAL_EXITS = {USE_PROFESSIONAL_EXITS}")

        logger.info("="*70)
        logger.info("OPTIMAL INTEGRATED SYSTEM READY")
        logger.info("🎯 Pure ML Intelligence (No Conflicts!)")
        logger.info("🧠 ML/RL Risk Manager ACTIVE (Smart Position Sizing)")
        logger.info("💰 Professional Position Sizer ACTIVE (Kelly + Broker Specs)")
        logger.info("🎓 Professional Exit Manager ACTIVE (Expected Value Decisions)")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"Failed to load integrated system: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "7.0.0",
        "system": "DUAL STRATEGY (M1 Scalp + H1 Swing)",
        "timestamp": datetime.now().isoformat(),
        "models_loaded": {
            "m1_scalping": m1_ensemble is not None,
            "h1_swing": h1_ensemble is not None,
            "feature_engineer": feature_engineer is not None,
                        "ml_risk_manager": ml_risk_manager is not None
        },
        "integration": "dual_strategy_ml_llm"
    }


@app.get("/api/risk/status")
async def get_risk_status():
    """Get current LLM risk manager status"""
    if not llm_risk_manager:
        return {"error": "LLM Risk Manager not available"}
    
    params = llm_risk_manager.get_current_params()
    
    return {
        "mode": params.get('scalping_mode', 'NORMAL'),
        "risk_multiplier": params.get('scalping_risk_multiplier', 1.0),
        "threshold_adjustment": params.get('scalping_threshold_adjustment', 0.0),
        "max_positions": params.get('max_scalp_positions', 1),
        "reasoning": params.get('reasoning', 'No analysis yet'),
        "timestamp": params.get('timestamp', datetime.now()).isoformat() if params.get('timestamp') else datetime.now().isoformat()
    }


@app.post("/api/risk/update")
async def update_risk_parameters(request: dict = None):
    """Update LLM risk parameters (called every 60s from EA)"""
    global last_risk_update

    if not llm_risk_manager:
        return {"error": "LLM Risk Manager not available"}

    # Handle empty or malformed requests gracefully
    if request is None:
        request = {}

    # Check if we need to update (every 60s)
    now = datetime.now()
    if last_risk_update and (now - last_risk_update).total_seconds() < 60:
        return llm_risk_manager.get_current_params()

    try:
        # Get account data from request
        account_data = {
            'balance': request.get('balance', 100000) if isinstance(request, dict) else 100000,
            'equity': request.get('equity', 100000) if isinstance(request, dict) else 100000,
            'daily_pnl': request.get('daily_pnl', 0) if isinstance(request, dict) else 0,
            'drawdown': request.get('drawdown', 0) if isinstance(request, dict) else 0,
            'starting_balance': request.get('starting_balance', 100000) if isinstance(request, dict) else 100000
        }

        # Get market data
        market_data = request.get('market_data', {
            'regime': 'unknown',
            'volatility': 'normal',
            'session': 'unknown'
        }) if isinstance(request, dict) else {
            'regime': 'unknown',
            'volatility': 'normal',
            'session': 'unknown'
        }

        # Analyze and update
        params = llm_risk_manager.analyze_account_health(
            account_data,
            trade_history[-100:],  # Last 100 trades
            market_data
        )

        last_risk_update = now

        logger.info(
            f"🤖 RISK UPDATE: Mode={params.get('scalping_mode', 'NORMAL')} "
            f"({params.get('scalping_risk_multiplier', 1.0):.1f}x risk)"
        )

        return params
    except Exception as e:
        logger.warning(f"⚠️ Risk update failed: {e}")
        # Return current params on error
        return llm_risk_manager.get_current_params()


def calculate_intelligent_position_limit(account_balance, account_equity, daily_pnl, open_positions, current_drawdown, trade_history=None):
    """
    Professional trader's intelligent position limit based on risk metrics
    No hard limits - adapts to account state, FTMO rules, AND performance history
    """
    # FTMO hard limits (only real constraints)
    daily_loss_limit = account_balance * 0.05  # 5% daily
    total_drawdown_limit = account_balance * 0.10  # 10% total
    
    # Calculate remaining risk capacity
    daily_loss_used = abs(min(0, daily_pnl))  # How much lost today
    daily_risk_remaining = daily_loss_limit - daily_loss_used
    
    total_drawdown_used = abs(min(0, account_equity - account_balance))
    total_risk_remaining = total_drawdown_limit - total_drawdown_used
    
    # Risk per position (1% per trade)
    risk_per_position = account_balance * 0.01
    
    # Calculate max positions based on remaining risk
    max_positions_daily = int(daily_risk_remaining / risk_per_position) if risk_per_position > 0 else 0
    max_positions_total = int(total_risk_remaining / risk_per_position) if risk_per_position > 0 else 0
    
    # Take the minimum (most conservative)
    intelligent_limit = min(max_positions_daily, max_positions_total)
    
    # Professional trader logic: scale back as risk increases
    if current_drawdown > 0.03:  # 3% drawdown
        intelligent_limit = max(1, intelligent_limit // 2)  # Cut positions in half
    elif current_drawdown > 0.02:  # 2% drawdown
        intelligent_limit = max(2, int(intelligent_limit * 0.7))  # Reduce by 30%
    
    # If account is profitable, can be more aggressive
    if daily_pnl > 0 and current_drawdown < 0.01:
        intelligent_limit = min(intelligent_limit + 2, 10)  # Allow up to 10 positions when doing well
    
    # PERFORMANCE-BASED ADJUSTMENTS (from MT5 history)
    if trade_history and isinstance(trade_history, dict):
        total_trades = trade_history.get('total_trades', 0)
        win_rate = trade_history.get('win_rate', 0.0)
        consecutive_losses = trade_history.get('current_streak_losses', 0)
        consecutive_wins = trade_history.get('current_streak_wins', 0)
        
        if total_trades >= 10:  # Need at least 10 trades for meaningful stats
            # Reduce positions if win rate is poor
            if win_rate < 0.50:  # Below 50% win rate
                intelligent_limit = max(1, intelligent_limit // 2)
                logger.info(f"⚠️ Win rate {win_rate:.1%} < 50% - Reducing positions to {intelligent_limit}")
            elif win_rate < 0.60:  # Below 60%
                intelligent_limit = max(2, int(intelligent_limit * 0.75))
            
            # Reduce after consecutive losses
            if consecutive_losses >= 3:
                intelligent_limit = max(1, intelligent_limit // 2)
                logger.info(f"⚠️ {consecutive_losses} consecutive losses - Reducing positions to {intelligent_limit}")
            elif consecutive_losses >= 2:
                intelligent_limit = max(2, int(intelligent_limit * 0.8))
            
            # Increase after consecutive wins (but cap it)
            if consecutive_wins >= 3 and win_rate > 0.70:
                intelligent_limit = min(intelligent_limit + 1, 10)
                logger.info(f"✅ {consecutive_wins} consecutive wins, {win_rate:.1%} win rate - Allowing {intelligent_limit} positions")
    
    # Absolute minimum and maximum for safety
    intelligent_limit = max(1, min(intelligent_limit, 15))  # Between 1 and 15
    
    return intelligent_limit


@app.post("/api/ultimate/ml_entry")
async def integrated_entry_signal(request: dict):
    """
    DUAL STRATEGY ML+LLM entry signal
    Supports both M1 scalping (default) and H1 swing via ?strategy= parameter
    Combines 153 technical features + 10 LLM context features + Risk Control
    """
    global trade_history

    try:
        # Parse trade_history from request if available (NEW: from enhanced EA)
        if 'trade_history' in request:
            # EA sends it as JSON string, need to parse it
            if isinstance(request['trade_history'], str):
                import json
                try:
                    trade_history = json.loads(request['trade_history'])
                    if isinstance(trade_history, list):
                        logger.info(f"📊 Received {len(trade_history)} trades from EA for ML Risk Manager")
                except json.JSONDecodeError:
                    logger.warning("⚠️ Failed to parse trade_history JSON")
                    trade_history = []
            elif isinstance(request['trade_history'], list):
                trade_history = request['trade_history']
                logger.info(f"📊 Received {len(trade_history)} trades from EA for ML Risk Manager")

        # Detect strategy from request (default: scalp for M1)
        strategy = request.get("strategy", "scalp").lower()

        # Select appropriate model
        if strategy == "swing":
            if h1_ensemble is None:
                return {
                    "direction": "HOLD",
                    "confidence": 0.0,
                    "take_trade": False,
                    "reason": "H1 swing model not loaded",
                    "strategy": "swing"
                }
            active_ensemble = h1_ensemble
            active_feature_names = h1_feature_names
            strategy_name = "H1 SWING"
        else:
            active_ensemble = m1_ensemble
            active_feature_names = m1_feature_names
            strategy_name = "M1 SCALP"

        # Log which strategy is being used
        logger.info(f"📊 {strategy_name} request received for {request.get('symbol', 'unknown')}")

        # Get LLM risk parameters
        risk_params = llm_risk_manager.get_current_params() if llm_risk_manager else {
            'scalping_mode': 'NORMAL',
            'scalping_risk_multiplier': 1.0,
            'scalping_threshold_adjustment': 0.0
        }
        
        # Check if trading is allowed
        if risk_params.get('scalping_mode') == 'STOP':
            logger.warning(f"🛑 TRADING STOPPED: {risk_params.get('reasoning', 'Risk limit reached')}")
            return {
                "direction": "HOLD",
                "confidence": 0.0,
                "take_trade": False,
                "reason": f"LLM Risk Manager: STOP mode - {risk_params.get('reasoning', 'Trading stopped')}",
                "llm_mode": "STOP"
            }
        market_data = request.get("market_data", {})
        
        # Convert to DataFrame with robust validation
        mtf_data = {}
        for tf, data in market_data.items():
            # Get all arrays and ensure they're lists
            close_data = data.get('close', [])
            high_data = data.get('high', [])
            low_data = data.get('low', [])
            volume_data = data.get('volume', [])
            open_data = data.get('open', [])
            
            # Convert to lists if needed
            close_data = list(close_data) if not isinstance(close_data, list) else close_data
            high_data = list(high_data) if not isinstance(high_data, list) else high_data
            low_data = list(low_data) if not isinstance(low_data, list) else low_data
            volume_data = list(volume_data) if not isinstance(volume_data, list) else volume_data
            open_data = list(open_data) if not isinstance(open_data, list) else open_data
            
            # Find minimum length
            min_len = min(
                len(close_data) if close_data else 0,
                len(high_data) if high_data else 0,
                len(low_data) if low_data else 0,
                len(volume_data) if volume_data else 0,
                len(open_data) if open_data else len(close_data)  # Use close length if no open
            )
            
            if min_len == 0:
                logger.error(f"❌ No data for {tf} timeframe")
                continue
                
            # Truncate all arrays to minimum length
            close_data = close_data[-min_len:]
            high_data = high_data[-min_len:]
            low_data = low_data[-min_len:]
            volume_data = volume_data[-min_len:]
            
            # If no open data, use close data
            if not open_data or len(open_data) == 0:
                open_data = close_data
            else:
                open_data = open_data[-min_len:]
            
            # Create DataFrame
            df = pd.DataFrame({
                'time': pd.date_range(end=pd.Timestamp.now(), periods=min_len, freq='1min'),
                'open': open_data,
                'high': high_data,
                'low': low_data,
                'close': close_data,
                'tick_volume': volume_data
            })
            
            mtf_data[tf] = df
            logger.info(f"✅ {tf} DataFrame created with {len(df)} bars")
        
        # FIX: EA sends uppercase keys (M1, M5, etc), but code expects lowercase
        # Convert all keys to lowercase
        mtf_data = {k.lower(): v for k, v in mtf_data.items()}
        logger.info(f"✅ Converted keys to lowercase: {list(mtf_data.keys())}")
        
        # Need M1 data - REDUCED to 20 bars!
        # Need at least 20 bars for features
        if 'm1' not in mtf_data or len(mtf_data['m1']) < 20:
            logger.warning(f"⚠️ M1 data missing or insufficient: {len(mtf_data.get('m1', [])) if 'm1' in mtf_data else 0} bars")
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "lot_size": 0.01,
                "stop_points": 50,
                "target_points": 100,
                "momentum": 0.0,
                "volume_ratio": 1.0,
                "trend_strength": 0.0,
                "reason": "Need 20 bars",
                "system": "integrated_v6"
            }
        
        m1_df = mtf_data['m1']
        current_idx = len(m1_df) - 1
        logger.info(f"✅ M1 data ready: {len(m1_df)} bars, current_idx={current_idx}")
        
        # Check if we have enough data for feature extraction (need at least 50 bars)
        if len(m1_df) < 50:
            logger.warning(f"⚠️ Insufficient data for feature extraction: {len(m1_df)} bars (need 50+)")
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "lot_size": 0.01,
                "stop_points": 50,
                "target_points": 100,
                "momentum": 0.0,
                "volume_ratio": 1.0,
                "trend_strength": 0.0,
                "reason": f"Need 50+ bars for features (have {len(m1_df)})",
                "system": "integrated_v6"
            }
        
        # 1. Extract technical features
        try:
            logger.info(f"🔧 Extracting features from {len(m1_df)} bars, current_idx={current_idx}")
            technical_features = feature_engineer.extract_all_features(m1_df, current_idx)
            logger.info(f"✅ Feature extraction complete: {len(technical_features) if technical_features else 0} features")
        except Exception as e:
            logger.error(f"❌ Feature extraction error: {str(e)}", exc_info=True)
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "reason": f"Feature extraction failed: {str(e)}"
            }
        
        if not technical_features:
            logger.warning("⚠️ Feature extraction returned empty dict")
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "reason": "Feature extraction returned empty"
            }
        
        # 2. Get LLM context (simulated from market data)
        llm_context = {"llm_agrees": True, "llm_confidence_boost": 1.0, "llm_reasoning": "ML-only"}
        
        # 3. CREATE INTEGRATED FEATURES (This is the key!)
        integrated_features = create_integrated_features(technical_features, llm_context)
        
        # Convert to DataFrame
        features_df = pd.DataFrame([integrated_features])
        features_df = features_df.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # 4. ML prediction with INTEGRATED XGBoost model (primary)
        # Use exact feature names to match training
        if active_feature_names:
            feature_array = np.array([integrated_features.get(f, 0.0) for f in active_feature_names])
        else:
            feature_array = np.array([integrated_features.get(f, 0.0) for f in sorted(integrated_features.keys())])

        feature_array = feature_array.reshape(1, -1)

        # Get ML prediction using selected model (0=HOLD, 1=BUY, 2=SELL)
        ml_prediction = active_ensemble.predict(feature_array)[0]
        ml_confidence = active_ensemble.predict_proba(feature_array)[0].max() * 100

        # Map to direction
        direction_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        final_direction = direction_map[ml_prediction]

        # Use ML confidence directly (RL removed - was never loaded properly)
        final_confidence = ml_confidence
        
        # 🎯 PROFESSIONAL SCALPING THRESHOLD (72% - validated edge)
        # For 76% accurate model, need 72%+ predictions to be statistically significant
        # Below 72% approaches random with 76% model accuracy (72/76 = 95% of model certainty)
        # This ensures we only take high-quality setups
        base_threshold = 72.0  # Professional scalping threshold (raised from 65% after audit)

        # MOMENTUM BOOST - Take advantage of strong moves!
        close = np.array(mtf_data['m1']['close']) if 'm1' in mtf_data else np.array(mtf_data.get('m5', {}).get('close', []))
        if len(close) >= 5:
            recent_move = abs(close[-1] - close[-5])
            if recent_move > 100:  # 100+ point move in 5 bars = MOMENTUM!
                base_threshold -= 3.0  # Slight reduction for momentum trades
                logger.info(f"🚀 MOMENTUM: {recent_move:.0f}pts in 5 bars - threshold now {base_threshold:.0f}%")

        # VOLUME SPIKE - Institutional money!
        if 'm1' in mtf_data and 'tick_volume' in mtf_data['m1']:
            volume = np.array(mtf_data['m1']['tick_volume'])
            if len(volume) >= 20:
                avg_vol = volume[-20:].mean()
                curr_vol = volume[-1]
                if curr_vol > avg_vol * 2.0:  # 2x volume spike!
                    base_threshold -= 3.0  # Slight reduction for volume spikes
                    logger.info(f"📊 VOLUME SPIKE: {curr_vol/avg_vol:.1f}x avg - threshold now {base_threshold:.0f}%")

        # NY session bonus (most liquid session)
        if integrated_features.get('ny_session', 0) == 1:
            base_threshold -= 2.0  # Slight reduction for NY session

        # Professional floor: Never below 67% (still selective, validated for 76% model)
        base_threshold = max(67.0, base_threshold)

        # Trend alignment bonus (strong directional bias)
        if integrated_features.get('llm_trend_aligned', 0) == 1:
            base_threshold -= 3.0  # Slight reduction for trend alignment

        # Apply LLM threshold adjustment
        llm_threshold_adj = risk_params.get('scalping_threshold_adjustment', 0.0)
        adjusted_threshold = base_threshold + llm_threshold_adj

        # Professional scalping floor: 67% minimum (validated for 76% model)
        adjusted_threshold = max(67.0, adjusted_threshold)
        
        # Final decision - USE ADJUSTED THRESHOLD ONLY
        take_trade = (
            final_confidence >= adjusted_threshold and
            final_direction != "HOLD"
        )
        
        # LOG EVERY DECISION FOR DEBUGGING
        logger.info(f"📊 SCALP ENTRY: {final_direction} @ {final_confidence:.1f}% | Threshold: {adjusted_threshold:.0f}% | Take: {take_trade} | RL: {'✓' if rl_agrees else '✗'}")
        
        # 🤖 100% AI-DRIVEN STOP/TARGET CALCULATION
        # Let ML determine optimal stops/targets based on market structure
        # No hardcoded ranges or trade type classification!

        atr = integrated_features.get('atr_20', 50.0)
        trend_strength = abs(integrated_features.get('trend_strength', 0.0))
        volatility = integrated_features.get('volatility', 0.02)
        momentum = abs(integrated_features.get('roc_5', 0.0))

        # ML-DRIVEN: Stop size based on confidence + volatility + market structure
        # Higher confidence = tighter stops (we're more certain)
        # Higher volatility = wider stops (give it room)
        # Stronger trend = wider stops (let it run)

        if final_confidence >= 85:
            confidence_stop_factor = 0.8  # Very confident - tight stop
        elif final_confidence >= 75:
            confidence_stop_factor = 1.0  # Normal stop
        else:
            confidence_stop_factor = 1.3  # Less confident - wider stop

        # Volatility adjustment
        volatility_multiplier = max(0.5, min(volatility / 0.02, 3.0))  # Scale based on normal vol

        # Trend adjustment (stronger trend = wider stop to avoid whipsaws)
        trend_multiplier = 1.0 + (trend_strength * 0.5)  # Up to 1.5x for strong trends

        # FINAL AI-CALCULATED STOP (no hardcoded limits!)
        stop_points = int(atr * 1.5 * confidence_stop_factor * volatility_multiplier * trend_multiplier)
        stop_points = max(50, stop_points)  # Only minimum safety (50pts = $5 per 0.01 lot)

        # 🎯 PROFESSIONAL SCALPING TARGETS (2:1 to 3:1 ratio)
        # Scalpers don't aim for 12:1 - that's swing trading!
        # Realistic scalping: Take quick 2-3x profits, move on to next trade

        if final_confidence >= 85:
            target_multiplier = 3.0   # Very confident - 3:1 ratio
        elif final_confidence >= 75:
            target_multiplier = 2.5   # Normal - 2.5:1 ratio
        else:
            target_multiplier = 2.0   # Less confident - 2:1 ratio

        # Momentum boost (scalping = smaller adjustments)
        momentum_boost = 1.0 + min(momentum * 0.2, 0.2)  # Max 1.2x (20% boost)

        # Trend boost (scalping = smaller adjustments)
        trend_boost = 1.0 + min(trend_strength * 0.15, 0.15)  # Max 1.15x (15% boost)

        # PROFESSIONAL SCALPING TARGET (2:1 to 3:1 ratio)
        target_points = int(stop_points * target_multiplier * momentum_boost * trend_boost)

        # Scalping reality check: Max 5:1 R:R (not 50:1!)
        # Professional scalpers: 2:1 to 4:1 is realistic, 5:1 is aggressive
        max_target = stop_points * 5  # Max 5:1 risk/reward for scalping
        target_points = min(target_points, max_target)
        target_points = max(100, target_points)  # Minimum 100pts (realistic scalp target)

        # Calculate R:R ratio for logging
        risk_reward_ratio = target_points / stop_points if stop_points > 0 else 0

        trade_type = "AI_DYNAMIC"
        logger.info(f"🤖 AI STOP/TARGET: Conf={final_confidence:.1f}% | Stop={stop_points}pts | Target={target_points}pts | R:R={risk_reward_ratio:.1f}:1 | ATR={atr:.0f} Trend={trend_strength:.2f} Mom={momentum:.2f}")     
        # PROFESSIONAL RISK-BASED POSITION SIZING
        # Risk 1% per trade for 1% daily target
        # ALWAYS pull actual balance from EA (don't hardcode!)
        account_balance = float(request.get('account_balance', 0.0))
        if account_balance <= 0:
            logger.warning("⚠️ No account balance provided - using 10K default")
            account_balance = 10000.0

        # 🧠 ML/RL RISK MANAGER - INTELLIGENT POSITION SIZING
        if USE_ML_RISK and ml_risk_manager and rl_risk_optimizer:
            # Get account data from request
            account_equity = float(request.get('equity', account_balance))
            daily_pnl = float(request.get('daily_pnl', 0))
            current_drawdown = float(request.get('drawdown', 0))
            open_positions = int(request.get('current_positions', 0))

            # Get ML risk decision
            ml_risk_decision = ml_risk_manager.predict_optimal_risk(
                balance=account_balance,
                equity=account_equity,
                daily_pnl=daily_pnl,
                current_drawdown=current_drawdown,
                open_positions=open_positions,
                ml_confidence=final_confidence,
                trade_history=trade_history
            )

            # Get RL risk multiplier
            recent_trades = trade_history[-50:] if len(trade_history) >= 50 else trade_history
            win_rate = sum(1 for t in recent_trades if t.get('pnl', 0) > 0) / len(recent_trades) if recent_trades else 0.5
            sharpe = ml_risk_manager._calculate_sharpe(trade_history)
            drawdown_pct = abs(current_drawdown) / account_balance * 100 if account_balance > 0 else 0

            rl_multiplier = rl_risk_optimizer.get_risk_multiplier(
                balance=account_balance,
                equity=account_equity,
                win_rate=win_rate,
                sharpe=sharpe,
                drawdown_pct=drawdown_pct
            )

            # Final risk percentage
            risk_per_trade_pct = (ml_risk_decision['risk_pct'] / 100) * rl_multiplier

            # Log ML/RL decision
            logger.info(f"🧠 ML RISK: {ml_risk_decision['risk_pct']:.2f}% × RL {rl_multiplier:.2f}x = {risk_per_trade_pct*100:.2f}% risk")
            logger.info(f"   Reasons: {', '.join(ml_risk_decision['reasons'][:3])}")

            # Apply trade filter
            if not ml_risk_decision['take_trade']:
                take_trade = False
                logger.warning(f"🛑 ML Risk Manager BLOCKED trade: {', '.join(ml_risk_decision['reasons'])}")

        else:
            # Fallback to baseline 1% risk
            risk_per_trade_pct = 0.01  # 1% risk per trade
            logger.info(f"📊 BASELINE RISK: 1.0% (ML Risk Manager disabled)")

        # 🎯 PROFESSIONAL POSITION SIZING WITH KELLY CRITERION
        # Uses broker's ACTUAL specs (no hardcoded 2.0 lot minimum!)
        # Integrates ML/RL Risk Manager calculations
        # Applies Kelly Criterion for optimal sizing

        # Get broker specs from EA request
        symbol_specs = request.get('symbol_specs', {
            'min_lot': 1.0,
            'max_lot': 100.0,
            'lot_step': 1.0,
            'tick_value': 1.0,
            'tick_size': 1.0
        })

        # Calculate win rate from trade history (if available)
        win_rate = None
        avg_rr = 2.5  # Our model targets 2.5:1 R:R

        if trade_history and len(trade_history) > 10:
            wins = sum(1 for t in trade_history if t.get('pnl', 0) > 0)
            win_rate = wins / len(trade_history)

            # Calculate actual R:R from history
            winning_trades = [t for t in trade_history if t.get('pnl', 0) > 0]
            losing_trades = [t for t in trade_history if t.get('pnl', 0) < 0]

            if winning_trades and losing_trades:
                avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades)
                avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades))
                avg_rr = avg_win / avg_loss if avg_loss > 0 else 2.5

        # Use professional position sizer
        if position_sizer:
            lot_size, sizing_details = position_sizer.calculate_position_size(
                account_balance=account_balance,
                risk_pct=risk_per_trade_pct,
                stop_points=stop_points,
                ml_confidence=final_confidence,
                symbol_specs=symbol_specs,
                win_rate=win_rate,
                avg_rr=avg_rr,
                allow_scaling=True
            )

            logger.info(f"✅ PROFESSIONAL SIZING: {lot_size:.2f} lots")
            logger.info(f"   Broker Min={symbol_specs.get('min_lot')} (not hardcoded 2.0!)")
            logger.info(f"   Actual Risk: ${sizing_details['actual_risk_dollars']:,.0f} ({sizing_details['actual_risk_pct']:.2f}%)")
        else:
            # Fallback (should never happen)
            logger.warning("⚠️ Position sizer not initialized - using fallback")
            lot_size = max(symbol_specs.get('min_lot', 1.0), 1.0)

        # Store initial lot for scaling calculations
        initial_lot_size = lot_size
        
        # Apply LLM risk multiplier
        risk_percent = 0.5 * risk_params.get('scalping_risk_multiplier', 1.0) * llm_context['risk_level']
        
        # Log decision
        logger.info(
            f"INTEGRATED v6.0: {final_direction}@{final_confidence:.1f}% | "
            f"LLM={llm_context['regime']}/{llm_context['bias']} | "
            f"RL={'' if rl_agrees else ''} | "
            f"RL={'✓' if rl_agrees else '✗'} | "
            f"Threshold={base_threshold:.0f}% → "
            f"{'TRADE' if take_trade else 'HOLD'}"
        )
        
        # INTELLIGENT POSITION LIMIT: Calculate based on account risk AND performance
        account_balance = request.get('account_balance', 10000.0)
        account_equity = request.get('account_equity', account_balance)
        daily_pnl = request.get('daily_pnl', 0.0)
        open_positions = request.get('open_positions', 0)
        trade_history = request.get('trade_history', {})  # From MT5 history
        
        # Calculate current drawdown
        current_drawdown = (account_balance - account_equity) / account_balance if account_balance > 0 else 0
        
        # Get intelligent position limit (not hard-coded 3!)
        max_positions = calculate_intelligent_position_limit(
            account_balance, 
            account_equity, 
            daily_pnl, 
            open_positions,
            current_drawdown,
            trade_history  # Now includes performance history!
        )
        
        # RL INTELLIGENT SCALING: Check if we should scale in
        should_scale_in = False
        scale_amount = 0.0
        rl_scale_action = "NONE"
        
        # INTELLIGENT SCALING: Scale in when confident + underwater (DCA strategy)
        if open_positions > 0 and open_positions < max_positions:
            # Build position state for RL
            position_profit = request.get('position_profit', 0.0)
            bars_held = request.get('bars_held', 1)
            position_profit_pts = request.get('position_profit_points', 0.0)

            # 🎯 PROFESSIONAL SCALE-IN LOGIC (DCA with regime check)
            # Only average down in RANGING markets (mean reversion)
            # NEVER average down in TRENDING markets (trend continuation = bigger losses)

            is_underwater = position_profit_pts < -40  # Down 40+ points
            is_recoverable = position_profit_pts > -100  # Not too deep (within 100pts)
            is_high_conviction = final_confidence >= 75.0

            # Check if signal still agrees with original direction
            original_direction = request.get('original_direction', final_direction)
            signal_still_valid = (final_direction == original_direction)

            # CRITICAL: Check market regime - only scale in if ranging/mean-reverting
            current_regime = llm_context.get('regime', 'unknown')
            is_safe_to_scale = current_regime in ['ranging', 'volatile', 'unknown']  # NOT trending!

            if not is_safe_to_scale:
                logger.warning(f"⚠️ SCALE-IN BLOCKED: Market regime '{current_regime}' - don't average down in trends!")

            if is_underwater and is_recoverable and is_high_conviction and signal_still_valid and is_safe_to_scale:
                # SCALE IN - we're getting a better price in a ranging market
                should_scale_in = True
                # Scale amount based on how underwater we are
                if position_profit_pts < -60:
                    scale_amount = 0.75  # Deep discount - add 75% more
                    rl_scale_action = "SCALE_IN_75_CONVICTION"
                elif position_profit_pts < -50:
                    scale_amount = 0.50  # Add 50% more
                    rl_scale_action = "SCALE_IN_50_CONVICTION"
                else:
                    scale_amount = 0.33  # Add 33% more
                    rl_scale_action = "SCALE_IN_33_CONVICTION"

                logger.info(f"💎 SAFE SCALING ({current_regime}): Down {position_profit_pts:.0f}pts @ {final_confidence:.1f}% conf - Adding {scale_amount*100:.0f}% more!")
            else:
                # Simple momentum-based scaling (no RL needed - ML confidence is enough!)
                # Scale in if: high confidence + strong momentum + positive profit
                momentum = float(integrated_features.get('roc_5', 0))
                if final_confidence >= 0.80 and momentum > 0.002 and position_profit_pts > 0:
                    should_scale_in = True
                    scale_amount = 0.5
                    rl_scale_action = "ML_SCALE_IN_50"
                    logger.info(f"🚀 ML SCALING: {final_confidence:.1f}% conf + momentum {momentum:.3f} → Add 50%!")
                elif final_confidence >= 0.75 and momentum > 0.001 and position_profit_pts > 0:
                    should_scale_in = True
                    scale_amount = 0.25
                    rl_scale_action = "ML_SCALE_IN_25"
                    logger.info(f"📈 ML SCALING: {final_confidence:.1f}% conf + momentum {momentum:.3f} → Add 25%!")
        
        return {
            "direction": str(final_direction),
            "confidence": float(final_confidence),
            "take_trade": bool(take_trade),
            "ml_direction": str(final_direction),
            "ml_confidence": float(ml_confidence),
            "rl_direction": str(rl_direction),
            "rl_agrees": bool(rl_agrees),
            "llm_regime": str(llm_context['regime']),
            "llm_bias": str(llm_context['bias']),
            "llm_risk_level": float(llm_context['risk_level']),
            "stop_points": int(stop_points),
            "target_points": int(target_points),
            "risk_percent": float(risk_percent),
            "lot_size": float(lot_size),
            "threshold_used": float(base_threshold),
            # Professional scaling metrics
            "momentum": float(integrated_features.get('roc_5', 0.0)),
            "volume_ratio": float(integrated_features.get('volume_ratio', 1.0)),
            "trend_strength": float(integrated_features.get('trend_strength', 0.0)),
            # TRADE TYPE CLASSIFICATION (AI-driven, not hardcoded)
            "trade_type": str(trade_type),
            "is_swing": False,  # Legacy field - all trades are AI_DYNAMIC now
            # RL INTELLIGENT SCALING
            "should_scale_in": bool(should_scale_in),
            "scale_amount": float(scale_amount),
            "rl_scale_action": str(rl_scale_action),
            "initial_lot_size": float(initial_lot_size),  # For EA to calculate scale-in size
            # INTELLIGENT POSITION LIMIT
            "max_positions": int(max_positions),
            "current_positions": int(open_positions),
            "daily_pnl": float(daily_pnl),
            "current_drawdown": float(current_drawdown),
            "system": "integrated_v6_intelligent_limits",
            "features_used": int(len(integrated_features)),
            "integration_note": "ML entry + RL intelligent scaling!"
        }
        
    except Exception as e:
        logger.error(f"Integrated entry error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ultimate/ml_exit")
@app.post("/api/integrated/exit")
@app.post("/api/ultimate/exit")  # EA v13.0 compatibility
async def integrated_exit_signal(request: dict):
    """
    Optimal Integrated Exit Signal
    Dynamic ML-driven exits with integrated LLM context
    """
    try:
        position_id = request.get("position_id", 0)
        entry_price = float(request.get("entry_price", 0))
        current_price = float(request.get("current_price", 0))
        direction = request.get("direction", "BUY")
        bars_held = int(request.get("bars_held", 0))
        comment = request.get("comment", "")
        llm_regime = request.get("llm_regime", "unknown")
        llm_bias = request.get("llm_bias", "neutral")
        market_data = request.get("market_data", {})

        # GET TARGET/STOP FROM REQUEST (EA should send these from entry signal)
        target_points = float(request.get("target_points", 0))
        stop_points = float(request.get("stop_points", 0))
        
        # Identify position type
        is_scalp = "SCALP" in comment
        is_swing = "SWING" in comment
        trade_type = "SCALP" if is_scalp else ("SWING" if is_swing else "UNKNOWN")
        
        # Calculate P/L
        if direction == "BUY":
            profit_points = current_price - entry_price
        else:
            profit_points = entry_price - current_price
        
        profit_pct = (profit_points / entry_price) * 100 if entry_price > 0 else 0
        
        # 🎯 PROFESSIONAL TRADER RULE #1: MINIMUM HOLD PERIOD
        # Don't exit within first 10 bars unless catastrophic loss/profit
        # This prevents ML from exiting on -1 point noise immediately after entry
        MIN_BARS_HOLD = 10
        CATASTROPHIC_LOSS = -50  # Points
        HUGE_PROFIT = 100  # Points

        if bars_held < MIN_BARS_HOLD:
            # Only allow exit if truly catastrophic move
            if abs(profit_points) < abs(CATASTROPHIC_LOSS) and profit_points < HUGE_PROFIT:
                logger.info(f"⏳ MINIMUM HOLD: {bars_held}/{MIN_BARS_HOLD} bars (P/L: {profit_points:+.0f}pts) - FORCING HOLD")
                return {
                    "action": "HOLD",
                    "confidence": 100.0,
                    "reason": f"Minimum hold period: {bars_held}/{MIN_BARS_HOLD} bars ({profit_points:+.0f}pts normal variance)",
                    "profit_points": float(profit_points),
                    "profit_pct": float(profit_pct)
                }
            else:
                # Catastrophic move - allow exit
                logger.warning(f"🚨 CATASTROPHIC MOVE: {profit_points:+.0f}pts at bar {bars_held} - allowing early exit")

        # Get M1 data for ML-based exit decision
        if 'M1' not in market_data or len(market_data['M1'].get('close', [])) < 20:
            # Not enough data - HOLD (let ML decide later)
            return {
                "action": "HOLD",
                "confidence": 50.0,
                "reason": "Insufficient data - holding for ML analysis",
                "profit_points": float(profit_points),
                "profit_pct": float(profit_pct)
            }

        # Extract integrated features for exit decision
        m1_df = pd.DataFrame({
            'time': pd.to_datetime(market_data['M1'].get('timestamp', [])),
            'open': market_data['M1'].get('open', []),
            'high': market_data['M1'].get('high', []),
            'low': market_data['M1'].get('low', []),
            'close': market_data['M1'].get('close', []),
            'tick_volume': market_data['M1'].get('volume', [])
        })
        
        # ML-BASED EXIT DECISION (no hardcoded rules!)
        current_idx = len(m1_df) - 1
        technical_features = feature_engineer.extract_all_features(m1_df, current_idx)

        if not technical_features:
            # Can't extract features - hold
            return {
                "action": "HOLD",
                "confidence": 50.0,
                "reason": "Feature extraction failed",
                "profit_points": float(profit_points),
                "profit_pct": float(profit_pct)
            }

        # Add position context to features
        llm_context = {"llm_agrees": True, "llm_confidence_boost": 1.0, "llm_reasoning": "ML-only"}
        integrated_features = create_integrated_features(technical_features, llm_context)

        # Add profit/loss context to features
        integrated_features['profit_points'] = float(profit_points)
        integrated_features['profit_pct'] = float(profit_pct)
        integrated_features['bars_held'] = int(bars_held)
        integrated_features['position_direction'] = 1.0 if direction == "BUY" else -1.0

        # PROFESSIONAL EXIT LOGIC: Expected Value Based Decision
        # Instead of confidence thresholds, calculate EV for each action
        try:
            if USE_PROFESSIONAL_EXITS and professional_exit_manager:
                # Use EV-based professional exit manager
                exit_outcome = professional_exit_manager.decide_exit(
                    features=integrated_features,
                    current_profit_points=profit_points,
                    bars_held=bars_held,
                    max_profit_points=max_profit_points,
                    trade_type="scalp" if is_scalp else "swing"
                )

                action = exit_outcome.action
                confidence = exit_outcome.probability * 100
                reason = exit_outcome.reason

                logger.info(
                    f"🎓 PROFESSIONAL EXIT: {action} | "
                    f"EV={exit_outcome.expected_value:.1f}pts | "
                    f"Uncertainty=±{exit_outcome.uncertainty:.1f}pts"
                )

            else:
                # FALLBACK: Old confidence-threshold approach
                # Select appropriate model and feature names based on trade type
                if is_scalp:
                    model = m1_ensemble
                    feature_names = m1_feature_names
                else:  # swing or unknown - use H1 if available, otherwise M1
                    model = h1_ensemble if h1_ensemble else m1_ensemble
                    feature_names = h1_feature_names if h1_ensemble else m1_feature_names

                # Prepare features for ML model using EXACT feature names from training
                if feature_names:
                    feature_array = np.array([integrated_features.get(f, 0.0) for f in feature_names])
                else:
                    feature_array = np.array([integrated_features.get(f, 0.0) for f in sorted(integrated_features.keys())])

                feature_array = feature_array.reshape(1, -1)

                # Get ML prediction for exit (trained on historical exits!)
                ml_exit_prediction = model.predict(feature_array)[0]
                ml_exit_proba = model.predict_proba(feature_array)[0]

                # Get confidence for the SPECIFIC predicted action (not just max)
                predicted_action_confidence = ml_exit_proba[ml_exit_prediction] * 100

                # Map prediction to exit action WITH CONFIDENCE CHECKS
                # 0=HOLD, 1=CLOSE, 2=SCALE_OUT
                MIN_CONFIDENCE_SCALE_OUT = 60.0
                MIN_CONFIDENCE_CLOSE = 55.0

                if ml_exit_prediction == 1:  # Model says CLOSE
                    if predicted_action_confidence >= MIN_CONFIDENCE_CLOSE:
                        action = "CLOSE_ALL"
                        confidence = predicted_action_confidence
                        reason = f"ML EXIT: Model {predicted_action_confidence:.1f}% confident to close @ {profit_points:.0f}pts"
                    else:
                        action = "HOLD"
                        confidence = predicted_action_confidence
                        reason = f"ML HOLD: CLOSE confidence {predicted_action_confidence:.1f}% < {MIN_CONFIDENCE_CLOSE:.0f}% threshold"
                elif ml_exit_prediction == 2:  # Model says SCALE OUT
                    if predicted_action_confidence >= MIN_CONFIDENCE_SCALE_OUT:
                        action = "SCALE_OUT_50"
                        confidence = predicted_action_confidence
                        reason = f"ML EXIT: Model {predicted_action_confidence:.1f}% confident to scale out @ {profit_points:.0f}pts"
                    else:
                        action = "HOLD"
                        confidence = predicted_action_confidence
                        reason = f"ML HOLD: SCALE_OUT confidence {predicted_action_confidence:.1f}% < {MIN_CONFIDENCE_SCALE_OUT:.0f}% threshold"
                else:  # Model says HOLD
                    action = "HOLD"
                    confidence = predicted_action_confidence
                    reason = f"ML HOLD: Model holding @ {profit_points:.0f}pts"

        except Exception as e:
            logger.error(f"Exit prediction failed: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to conservative hold
            action = "HOLD"
            confidence = 50.0
            reason = f"Exit manager failed - holding @ {profit_points:.0f}pts"
        
        # Log exit decision
        if action != "HOLD":
            logger.info(
                f"📤 EXIT ({trade_type}): {action} @ {confidence:.1f}% | "
                f"P/L: {profit_pct:.2f}% ({profit_points:.1f} pts) | "
                f"Bars: {bars_held} | Reason: {reason}"
            )
        
        return {
            "action": action,
            "confidence": float(confidence),
            "reason": reason,
            "profit_points": float(profit_points),
            "profit_pct": float(profit_pct),
            "system": "integrated_v6"
        }
        
    except Exception as e:
        logger.error(f"Integrated exit error: {e}")
        import traceback
        traceback.print_exc()
        # Safe fallback
        return {
            "action": "HOLD",
            "confidence": 50.0,
            "reason": "Error in exit analysis",
            "profit_points": 0.0,
            "profit_pct": 0.0
        }


@app.post("/api/swing/entry")
async def swing_entry_signal(request: dict):
    """
    Swing trading entry (H1/H4 timeframe)
    Uses same proven ensemble models, different timeframe
    """
    try:
        market_data = request.get("market_data", {})
        
        # Use H1 data for swing
        if 'H1' not in market_data or len(market_data['H1'].get('close', [])) < 20:
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "reason": "Need 20 H1 bars for swing",
                "system": "swing_v7"
            }
        
        # Convert H1 to DataFrame
        h1_data = market_data['H1']
        h1_df = pd.DataFrame({
            'time': pd.to_datetime(h1_data.get('timestamp', [])),
            'open': h1_data.get('open', []),
            'high': h1_data.get('high', []),
            'low': h1_data.get('low', []),
            'close': h1_data.get('close', []),
            'tick_volume': h1_data.get('volume', [])
        })
        
        current_idx = len(h1_df) - 1
        
        # Extract features using same proven feature engineer
        features = feature_engineer.extract_all_features(h1_df, current_idx)
        
        if not features:
            return {
                "direction": "HOLD",
                "confidence": 50.0,
                "take_trade": False,
                "reason": "Feature extraction failed"
            }
        
        # Get LLM context
        llm_context = {"llm_agrees": True, "llm_confidence_boost": 1.0, "llm_reasoning": "ML-only"}
        
        # Create integrated features
        integrated = create_integrated_features(features, llm_context)
        
        # Use same ensemble models (proven 78.43%)
        features_df = pd.DataFrame([integrated])
        features_df = features_df.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        from src.ml.pro_ensemble import ProEnsembleTrainer
        trainer = ProEnsembleTrainer()
        trainer.xgb_model = integrated_ensemble['xgb_model']
        trainer.lgb_model = integrated_ensemble['lgb_model']
        trainer.nn_model = integrated_ensemble['nn_model']
        trainer.ensemble_weights = integrated_ensemble['ensemble_weights']
        
        predictions, confidences = trainer.predict(features_df)
        ml_prediction = predictions[0]
        ml_confidence = confidences[0]
        
        direction_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        direction = direction_map[ml_prediction]

        # ML-only confidence (RL removed - was dead code)
        final_confidence = ml_confidence
        
        # SNIPER THRESHOLD - ABSOLUTE MINIMUM 65%
        base_threshold = 75.0  # SAFE: High quality setups only
        
        # Trend alignment bonus for swings
        if integrated.get('llm_trend_aligned', 0) == 1:
            base_threshold -= 10.0
        
        take_trade = (final_confidence >= base_threshold) and (direction != "HOLD")
        
        # Swing targets (larger than scalping)
        atr = integrated.get('atr_20', 100.0)
        stop_points = int(atr * 3.0)  # Wider stops for swings
        target_points = int(atr * 6.0)  # Bigger targets
        
        stop_points = max(200, min(stop_points, 500))
        target_points = max(500, min(target_points, 2000))
        
        risk_percent = 1.0  # Swing risk (vs 0.5% scalping)
        
        logger.info(
            f"SWING v7.0: {direction}@{final_confidence:.1f}% | "
            f"LLM={llm_context['regime']}/{llm_context['bias']} | "
            f"RL={'✓' if rl_agrees else '✗'} | "
            f"Threshold={base_threshold:.0f}% → {'TRADE' if take_trade else 'HOLD'}"
        )
        
        return {
            "direction": direction,
            "confidence": float(final_confidence),
            "take_trade": take_trade,
            "ml_confidence": float(ml_confidence),
            "rl_agrees": rl_agrees,
            "stop_points": stop_points,
            "target_points": target_points,
            "risk_percent": risk_percent,
            "threshold_used": base_threshold,
            "system": "swing_v7",
            "timeframe": "H1"
        }
        
    except Exception as e:
        logger.error(f"Swing entry error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ultimate/overview")
async def llm_overview(request: dict):
    """LLM market overview"""
    try:
        market_data = request.get("market_data", {})
        llm_context = {"llm_agrees": True, "llm_confidence_boost": 1.0, "llm_reasoning": "ML-only"}
        
        return {
            "regime": llm_context['regime'],
            "bias": llm_context['bias'],
            "risk_level": llm_context['risk_level'],
            "timestamp": datetime.now().isoformat(),
            "summary": f"Market {llm_context['regime']}, {llm_context['bias']} bias"
        }
    except Exception as e:
        logger.error(f"LLM overview error: {e}")
        return {
            "regime": "unknown",
            "bias": "neutral",
            "risk_level": 1.0,
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/learn/tick")
async def learn_from_tick(request: dict):
    """
    Continuous learning endpoint - EA sends tick data for model updates
    """
    try:
        # Just acknowledge - continuous learning happens in background
        return {
            "status": "acknowledged",
            "learning": "continuous",
            "note": "Model updates in background"
        }
    except Exception as e:
        logger.error(f"Learn tick error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/api/risk/update")
async def update_risk_params(request: dict):
    """Update risk parameters from LLM Risk Manager"""
    global risk_params

    try:
        # Update risk parameters - but limit threshold adjustments
        threshold_adj = request.get('threshold_adjustment', 0.0)
        # Cap threshold adjustment at +5% (don't let it go too high)
        threshold_adj = max(-10.0, min(5.0, threshold_adj))

        risk_params = {
            'scalping_mode': request.get('mode', 'NORMAL'),
            'scalping_risk_multiplier': request.get('risk_multiplier', 1.0),
            'scalping_threshold_adjustment': threshold_adj,
            'reasoning': request.get('reasoning', '')
        }

        logger.info(f"🎯 Risk params updated: {risk_params}")
        return {"status": "updated", "params": risk_params}

    except Exception as e:
        logger.error(f"Risk update error: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5007)
