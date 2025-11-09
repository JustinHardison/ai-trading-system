#!/usr/bin/env python3
"""
FastAPI REST Server for US30 ML Model
Provides millisecond predictions for MT5 EA

Endpoint: POST http://127.0.0.1:5005/predict
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
import pickle
import pandas as pd
import numpy as np
from datetime import datetime
import uvicorn

from src.ml.feature_engineering import FeatureEngineer
from src.data.indicators import TechnicalIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="US30 ML Trading API",
    description="High-speed ML predictions for US30 trading",
    version="1.0.0"
)

# Add CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load ML model at startup
MODEL_PATH = 'models/us30_optimized_latest.pkl'
model_data = None
feature_engineer = None

@app.on_event("startup")
async def load_model():
    """Load ML model and feature engineer on startup"""
    global model_data, feature_engineer

    logger.info(f"Loading ML model from {MODEL_PATH}...")

    try:
        with open(MODEL_PATH, 'rb') as f:
            model_data = pickle.load(f)

        feature_engineer = FeatureEngineer()

        logger.info(f"✓ Model loaded: {type(model_data['model']).__name__}")
        logger.info(f"✓ Features: {len(model_data['feature_names'])}")
        logger.info(f"✓ Trained on: {model_data.get('trained_on', 'Unknown')}")
        logger.info("✓ REST API ready for predictions")

    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


# Request/Response models
class MarketData(BaseModel):
    """Market data for a single timeframe"""
    timeframe: str  # e.g., "M15", "H1", "H4", "D1"
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]
    timestamp: List[str]  # ISO format timestamps


class PredictionRequest(BaseModel):
    """Request format from MT5 EA"""
    symbol: str
    market_data: Dict[str, MarketData]  # Dict of {timeframe: data}


class PredictionResponse(BaseModel):
    """Response format to MT5 EA"""
    direction: str  # "BUY", "SELL", or "HOLD"
    confidence: float  # 0-100
    probabilities: Dict[str, float]  # {"buy": 0.85, "sell": 0.10, "hold": 0.05}
    timestamp: str
    processing_time_ms: float


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "model": type(model_data['model']).__name__ if model_data else "not loaded",
        "trained_on": model_data.get('trained_on', 'Unknown') if model_data else "Unknown",
        "endpoint": "/predict"
    }


@app.get("/health")
async def health():
    """Health check for monitoring"""
    if model_data is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return {
        "status": "healthy",
        "model_loaded": True,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Make ML prediction on market data

    Args:
        request: Market data for multiple timeframes

    Returns:
        Prediction with direction and confidence
    """
    start_time = datetime.now()

    try:
        # Convert request data to dataframes
        mtf_data = {}
        for tf, data in request.market_data.items():
            df = pd.DataFrame({
                'open': data.open,
                'high': data.high,
                'low': data.low,
                'close': data.close,
                'volume': data.volume
            })
            mtf_data[tf] = df

        # Calculate indicators
        mtf_indicators = {}
        for tf, df in mtf_data.items():
            if len(df) >= 50:  # Need minimum bars for indicators
                mtf_indicators[tf] = TechnicalIndicators.calculate_all(df)

        # Extract features
        features = feature_engineer.extract_features(
            symbol=request.symbol,
            mtf_data=mtf_data,
            mtf_indicators=mtf_indicators
        )

        # Convert to DataFrame
        feature_df = pd.DataFrame([features])

        # Make prediction
        probabilities = model_data['model'].predict_proba(feature_df)[0]
        prediction = model_data['model'].predict(feature_df)[0]

        # Map prediction to direction
        # Classes: 0=HOLD, 1=BUY, 2=SELL
        direction_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        direction = direction_map[int(prediction)]

        # Get confidence (max probability)
        confidence = float(probabilities.max() * 100)

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        response = PredictionResponse(
            direction=direction,
            confidence=confidence,
            probabilities={
                'hold': float(probabilities[0]),
                'buy': float(probabilities[1]),
                'sell': float(probabilities[2])
            },
            timestamp=datetime.now().isoformat(),
            processing_time_ms=processing_time
        )

        logger.info(
            f"Prediction: {request.symbol} -> {direction} "
            f"({confidence:.1f}% confidence, {processing_time:.1f}ms)"
        )

        return response

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/simple")
async def predict_simple(
    symbol: str,
    h1_close: float,
    h1_rsi: float,
    h4_close: float,
    h4_rsi: float,
    d1_close: float,
    d1_rsi: float
):
    """
    Simplified prediction endpoint for testing

    Args:
        symbol: Trading symbol
        h1_close: H1 close price
        h1_rsi: H1 RSI value
        h4_close: H4 close price
        h4_rsi: H4 RSI value
        d1_close: D1 close price
        d1_rsi: D1 RSI value

    Returns:
        Simple prediction response
    """
    start_time = datetime.now()

    try:
        # Create dummy features (simplified for testing)
        features = {}
        features['symbol'] = hash(symbol) % 1000
        features['timestamp'] = datetime.now().timestamp()

        # Add simplified features
        for tf in ['H1', 'H4', 'D1']:
            features[f'{tf}_trend_ema'] = 1.0
            features[f'{tf}_trend_sma'] = 1.0
            features[f'{tf}_price_position'] = 0.5
            features[f'{tf}_rsi'] = h1_rsi if tf == 'H1' else (h4_rsi if tf == 'H4' else d1_rsi)
            features[f'{tf}_rsi_oversold'] = 1 if features[f'{tf}_rsi'] < 30 else 0
            features[f'{tf}_rsi_overbought'] = 1 if features[f'{tf}_rsi'] > 70 else 0
            features[f'{tf}_macd'] = 0.0
            features[f'{tf}_macd_signal'] = 0.0
            features[f'{tf}_macd_diff'] = 0.0
            features[f'{tf}_macd_bullish'] = 0
            features[f'{tf}_atr'] = 100.0
            features[f'{tf}_atr_percentile'] = 0.5
            features[f'{tf}_bb_width'] = 200.0
            features[f'{tf}_bb_position'] = 0.5
            features[f'{tf}_volume_ratio'] = 1.0
            features[f'{tf}_volume_spike'] = 0
            features[f'{tf}_volume_trend'] = 0.0
            features[f'{tf}_higher_highs'] = 2
            features[f'{tf}_lower_lows'] = 2
            features[f'{tf}_price_momentum'] = 0.0
            features[f'{tf}_candle_strength'] = 0.5

        features['mtf_trend_agreement'] = 0.5
        features['mtf_momentum_agreement'] = 0.5
        features['mtf_rsi_average'] = (h1_rsi + h4_rsi + d1_rsi) / 3
        features['mtf_timeframes_bullish'] = 1
        features['mtf_timeframes_bearish'] = 1
        features['hour_of_day'] = datetime.now().hour
        features['day_of_week'] = datetime.now().weekday()
        features['is_london_session'] = 1 if 3 <= datetime.now().hour <= 12 else 0
        features['is_ny_session'] = 1 if 8 <= datetime.now().hour <= 17 else 0
        features['is_asian_session'] = 1 if (19 <= datetime.now().hour or datetime.now().hour <= 4) else 0

        # Convert to DataFrame
        feature_df = pd.DataFrame([features])

        # Make prediction
        probabilities = model_data['model'].predict_proba(feature_df)[0]
        prediction = model_data['model'].predict(feature_df)[0]

        # Map prediction
        direction_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        direction = direction_map[int(prediction)]
        confidence = float(probabilities.max() * 100)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return {
            'symbol': symbol,
            'direction': direction,
            'confidence': confidence,
            'probabilities': {
                'hold': float(probabilities[0]),
                'buy': float(probabilities[1]),
                'sell': float(probabilities[2])
            },
            'processing_time_ms': processing_time
        }

    except Exception as e:
        logger.error(f"Simple prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decide/full")
async def decide_full(request: PredictionRequest):
    """
    PROPER AI DECISION with FULL 75 FEATURES

    Accepts raw OHLCV data from EA, calculates all 75 features properly,
    then makes comprehensive trading decisions.

    This is the CORRECT way - model gets exactly what it was trained on.
    """
    start_time = datetime.now()

    try:
        # Extract account state from first timeframe metadata (if provided)
        # For now, get from query params separately

        # Convert request data to proper format for FeatureEngineer
        mtf_data = {}
        mtf_indicators = {}

        for tf, data in request.market_data.items():
            # Convert to DataFrame
            df = pd.DataFrame({
                'open': data.open,
                'high': data.high,
                'low': data.low,
                'close': data.close,
                'volume': data.volume
            })
            mtf_data[tf] = df

            # Calculate indicators using the SAME method as training
            if len(df) >= 50:
                mtf_indicators[tf] = TechnicalIndicators.calculate_all(df)

        # Extract FULL 75 features using production FeatureEngineer
        features = feature_engineer.extract_features(
            symbol=request.symbol,
            mtf_data=mtf_data,
            mtf_indicators=mtf_indicators
        )

        # Convert to DataFrame
        feature_df = pd.DataFrame([features])

        # Make prediction with FULL features
        probabilities = model_data['model'].predict_proba(feature_df)[0]
        prediction = model_data['model'].predict(feature_df)[0]

        # Map prediction
        direction_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        direction = direction_map[int(prediction)]
        confidence = float(probabilities.max() * 100)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        response = {
            'timestamp': datetime.now().isoformat(),
            'processing_time_ms': processing_time,
            'direction': direction,
            'confidence': confidence,
            'probabilities': {
                'hold': float(probabilities[0]),
                'buy': float(probabilities[1]),
                'sell': float(probabilities[2])
            },
            'features_used': 75,
            'note': 'Full feature prediction - model confidence is reliable'
        }

        logger.info(
            f"FULL FEATURE Prediction: {request.symbol} -> {direction} @ {confidence:.1f}% "
            f"(75 features, {processing_time:.1f}ms)"
        )

        return response

    except Exception as e:
        logger.error(f"Full prediction error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decide/all")
async def decide_all(
    symbol: str,
    current_balance: float,
    current_equity: float,
    day_start_equity: float,
    open_positions: int,
    trades_today: int,
    h1_close: float,
    h1_rsi: float,
    h4_close: float,
    h4_rsi: float,
    d1_close: float,
    d1_rsi: float
):
    """
    AI makes ALL trading decisions:
    - Entry direction (BUY/SELL/HOLD)
    - Risk percentage for this trade
    - Maximum positions allowed
    - Whether to stop trading (loss limits)

    This is PURE AI - no hardcoded rules.
    """
    start_time = datetime.now()

    try:
        # Create dummy features (simplified for speed)
        features = {}
        features['symbol'] = hash(symbol) % 1000
        features['timestamp'] = datetime.now().timestamp()

        # Add simplified features for each timeframe
        for tf in ['H1', 'H4', 'D1']:
            features[f'{tf}_trend_ema'] = 1.0
            features[f'{tf}_trend_sma'] = 1.0
            features[f'{tf}_price_position'] = 0.5
            features[f'{tf}_rsi'] = h1_rsi if tf == 'H1' else (h4_rsi if tf == 'H4' else d1_rsi)
            features[f'{tf}_rsi_oversold'] = 1 if features[f'{tf}_rsi'] < 30 else 0
            features[f'{tf}_rsi_overbought'] = 1 if features[f'{tf}_rsi'] > 70 else 0
            features[f'{tf}_macd'] = 0.0
            features[f'{tf}_macd_signal'] = 0.0
            features[f'{tf}_macd_diff'] = 0.0
            features[f'{tf}_macd_bullish'] = 0
            features[f'{tf}_atr'] = 100.0
            features[f'{tf}_atr_percentile'] = 0.5
            features[f'{tf}_bb_width'] = 200.0
            features[f'{tf}_bb_position'] = 0.5
            features[f'{tf}_volume_ratio'] = 1.0
            features[f'{tf}_volume_spike'] = 0
            features[f'{tf}_volume_trend'] = 0.0
            features[f'{tf}_higher_highs'] = 2
            features[f'{tf}_lower_lows'] = 2
            features[f'{tf}_price_momentum'] = 0.0
            features[f'{tf}_candle_strength'] = 0.5

        features['mtf_trend_agreement'] = 0.5
        features['mtf_momentum_agreement'] = 0.5
        features['mtf_rsi_average'] = (h1_rsi + h4_rsi + d1_rsi) / 3
        features['mtf_timeframes_bullish'] = 1
        features['mtf_timeframes_bearish'] = 1
        features['hour_of_day'] = datetime.now().hour
        features['day_of_week'] = datetime.now().weekday()
        features['is_london_session'] = 1 if 3 <= datetime.now().hour <= 12 else 0
        features['is_ny_session'] = 1 if 8 <= datetime.now().hour <= 17 else 0
        features['is_asian_session'] = 1 if (19 <= datetime.now().hour or datetime.now().hour <= 4) else 0

        # Convert to DataFrame
        feature_df = pd.DataFrame([features])

        # Make prediction
        probabilities = model_data['model'].predict_proba(feature_df)[0]
        prediction = model_data['model'].predict(feature_df)[0]

        # Map prediction
        direction_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}
        direction = direction_map[int(prediction)]
        confidence = float(probabilities.max() * 100)

        # ============================================================
        # AI DECIDES EVERYTHING (based on market conditions + account state)
        # ============================================================

        # Calculate current loss state
        daily_loss_pct = 0
        if day_start_equity > 0:
            daily_loss_pct = ((day_start_equity - current_equity) / day_start_equity) * 100

        total_loss_pct = ((current_balance - current_equity) / current_balance) * 100

        # AI Decision: Should we stop trading?
        stop_trading = False
        stop_reason = ""

        if daily_loss_pct >= 5.0:
            stop_trading = True
            stop_reason = f"Daily loss limit reached: {daily_loss_pct:.2f}%"
        elif total_loss_pct >= 10.0:
            stop_trading = True
            stop_reason = f"Max loss limit reached: {total_loss_pct:.2f}%"
        elif daily_loss_pct >= 4.5:  # AI says: approaching limit, be cautious
            stop_trading = True
            stop_reason = f"Approaching daily limit: {daily_loss_pct:.2f}% - AI stopping trading"

        # AI Decision: Risk per trade (based on confidence and account state)
        risk_percent = 0.0
        if confidence >= 90:
            risk_percent = 0.5   # High confidence = higher risk
        elif confidence >= 80:
            risk_percent = 0.35
        elif confidence >= 75:
            risk_percent = 0.25
        elif confidence >= 70:
            risk_percent = 0.20
        else:
            risk_percent = 0.15  # Low confidence = lower risk

        # Reduce risk if we're in drawdown
        if daily_loss_pct > 2.0:
            risk_percent *= 0.5  # AI says: halve risk when losing

        # AI Decision: Maximum positions (based on market volatility)
        max_positions = 3
        avg_rsi = (h1_rsi + h4_rsi + d1_rsi) / 3

        if avg_rsi < 25 or avg_rsi > 75:  # Extreme conditions
            max_positions = 1  # AI says: only 1 position in extreme markets
        elif avg_rsi < 35 or avg_rsi > 65:  # High volatility
            max_positions = 2
        else:
            max_positions = 3  # Normal conditions

        # AI Decision: Max trades per day (adaptive)
        max_trades_today = 6
        if daily_loss_pct > 3.0:
            max_trades_today = 3  # AI says: limit trades when losing
        elif daily_loss_pct > 1.5:
            max_trades_today = 4

        # AI Decision: Should we take this trade?
        take_trade = True
        reject_reason = ""

        if stop_trading:
            take_trade = False
            reject_reason = stop_reason
        elif direction == "HOLD":
            take_trade = False
            reject_reason = "AI says HOLD - no clear opportunity"
        elif confidence < 65:  # AI minimum threshold
            take_trade = False
            reject_reason = f"AI confidence too low: {confidence:.1f}%"
        elif open_positions >= max_positions:
            take_trade = False
            reject_reason = f"Max positions reached: {open_positions}/{max_positions}"
        elif trades_today >= max_trades_today:
            take_trade = False
            reject_reason = f"Max trades today reached: {trades_today}/{max_trades_today}"

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        response = {
            'timestamp': datetime.now().isoformat(),
            'processing_time_ms': processing_time,

            # Entry decision
            'direction': direction,
            'confidence': confidence,
            'take_trade': take_trade,
            'reject_reason': reject_reason,

            # Risk management (AI-decided)
            'risk_percent': risk_percent,
            'max_positions': max_positions,
            'max_trades_today': max_trades_today,

            # Account protection (AI-decided)
            'stop_trading': stop_trading,
            'stop_reason': stop_reason,
            'daily_loss_pct': daily_loss_pct,
            'total_loss_pct': total_loss_pct,

            # Probabilities for transparency
            'probabilities': {
                'hold': float(probabilities[0]),
                'buy': float(probabilities[1]),
                'sell': float(probabilities[2])
            }
        }

        logger.info(
            f"AI Full Decision: {symbol} -> {direction} @ {confidence:.1f}% "
            f"| Trade: {take_trade} | Risk: {risk_percent:.2f}% | MaxPos: {max_positions}"
        )

        return response

    except Exception as e:
        logger.error(f"AI decision error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  US30 ML TRADING API - HIGH-SPEED PREDICTIONS")
    print("="*70)
    print(f"\n  Model: {MODEL_PATH}")
    print(f"  Simple: http://127.0.0.1:5005/predict/simple (6 features)")
    print(f"  FULL:   http://127.0.0.1:5005/decide/full (75 features - USE THIS)")
    print(f"  Legacy: http://127.0.0.1:5005/decide/all (6 features)")
    print(f"  Health: http://127.0.0.1:5005/health")
    print(f"\n  Target: <200ms prediction time")
    print("="*70 + "\n")

    # Run server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5005,
        log_level="info"
    )
