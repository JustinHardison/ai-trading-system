#!/usr/bin/env python3
"""
FastAPI Server for AI Trading System
Provides REST API + WebSocket for real-time monitoring and control
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import json
from datetime import datetime
import threading
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from autonomous_trader import AutonomousTrader
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Log if GROQ API key is available on startup
if os.getenv("GROQ_API_KEY"):
    logger.info("✓ GROQ_API_KEY loaded from environment")
else:
    logger.warning("⚠️  GROQ_API_KEY not found in environment")

# Initialize FastAPI
app = FastAPI(title="AI Trading System API", version="2.0")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Netlify domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class TradingState:
    def __init__(self):
        self.trader: Optional[AutonomousTrader] = None
        self.is_running: bool = False
        self.trader_thread: Optional[threading.Thread] = None
        self.status: Dict = {
            "enabled": False,
            "mt5_connected": False,
            "current_activity": "Idle",
            "balance": 0.0,
            "equity": 0.0,
            "current_profit_pct": 0.0,
            "target_profit_pct": 10.0,
            "open_positions": [],
            "pacing_status": "INITIALIZING",
            "confidence_threshold": 75.0,
            "daily_profit": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "last_trade": None,
            "news_filter_active": False,
            "consistency_safe": True,
            "circuit_breaker_ok": True,
            "last_updated": datetime.now().isoformat()
        }
        self.settings: Dict = {
            "phase": 1,
            "starting_balance": 100000.0,
            "scan_interval": 180,
            "min_confidence": 75.0,
            "auto_stop_at_target": True,
            "max_profit_before_stop": 15.0
        }
        self.active_websockets: List[WebSocket] = []

state = TradingState()

# Pydantic models
class SettingsUpdate(BaseModel):
    phase: Optional[int] = None
    starting_balance: Optional[float] = None
    scan_interval: Optional[int] = None
    min_confidence: Optional[float] = None
    auto_stop_at_target: Optional[bool] = None
    max_profit_before_stop: Optional[float] = None

class TraderControl(BaseModel):
    action: str  # "start", "stop", "pause"

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to websocket: {e}")

manager = ConnectionManager()

# API Endpoints

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "online",
        "service": "AI Trading System",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def get_status():
    """Get current trading system status"""
    return state.status

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    return state.settings

@app.post("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update trading settings"""
    if state.is_running:
        raise HTTPException(400, "Cannot change settings while trader is running")

    # Update settings
    if settings.phase is not None:
        state.settings["phase"] = settings.phase
    if settings.starting_balance is not None:
        state.settings["starting_balance"] = settings.starting_balance
    if settings.scan_interval is not None:
        state.settings["scan_interval"] = settings.scan_interval
    if settings.min_confidence is not None:
        state.settings["min_confidence"] = settings.min_confidence
    if settings.auto_stop_at_target is not None:
        state.settings["auto_stop_at_target"] = settings.auto_stop_at_target
    if settings.max_profit_before_stop is not None:
        state.settings["max_profit_before_stop"] = settings.max_profit_before_stop

    logger.info(f"Settings updated: {state.settings}")

    # Broadcast to all connected clients
    await manager.broadcast({
        "type": "settings_updated",
        "data": state.settings
    })

    return {"status": "success", "settings": state.settings}

@app.post("/api/control")
async def control_trader(control: TraderControl):
    """Start/Stop trading system"""

    if control.action == "start":
        if state.is_running:
            raise HTTPException(400, "Trader already running")

        # Fetch current balance from MT5
        from src.execution.trade_executor import TradeExecutor
        executor = TradeExecutor()
        account_info = executor.get_account_info()

        if not account_info:
            raise HTTPException(500, "Failed to connect to MT5 - cannot start trader")

        # Use ACTUAL balance from MT5 as starting balance
        actual_balance = account_info['balance']
        logger.info(f"Starting trader with MT5 balance: ${actual_balance:,.2f}")

        # Start trader in background thread
        def run_trader():
            try:
                import os
                groq_key = os.getenv("GROQ_API_KEY")
                logger.info(f"Starting trader with GROQ API key: {'SET' if groq_key else 'NOT SET'}")

                state.trader = AutonomousTrader(
                    phase=state.settings["phase"],
                    starting_balance=actual_balance,  # Use MT5 balance, not hardcoded value
                    groq_api_key=groq_key  # Pass GROQ API key for LLM portfolio manager
                )
                state.is_running = True
                state.status["enabled"] = True

                # Run trading loop
                state.trader.run(scan_interval_seconds=state.settings["scan_interval"])

            except Exception as e:
                logger.error(f"Trader error: {e}", exc_info=True)
                state.is_running = False
                state.status["enabled"] = False

        state.trader_thread = threading.Thread(target=run_trader, daemon=True)
        state.trader_thread.start()

        logger.info("Trading system started")

        await manager.broadcast({
            "type": "trader_started",
            "data": {"status": "running"}
        })

        return {"status": "started"}

    elif control.action == "stop":
        if not state.is_running:
            raise HTTPException(400, "Trader not running")

        # Stop trader
        if state.trader:
            state.trader.shutdown()

        state.is_running = False
        state.status["enabled"] = False

        logger.info("Trading system stopped")

        await manager.broadcast({
            "type": "trader_stopped",
            "data": {"status": "stopped"}
        })

        return {"status": "stopped"}

    else:
        raise HTTPException(400, f"Unknown action: {control.action}")

@app.get("/api/positions")
async def get_positions():
    """Get open positions"""
    if not state.trader or not state.trader.trade_executor:
        return {"positions": []}

    positions = state.trader.trade_executor.get_open_positions()
    return {"positions": positions or []}

@app.get("/api/metrics")
async def get_metrics():
    """Get performance metrics"""
    # TODO: Implement metrics tracking
    return {
        "total_trades": state.status.get("total_trades", 0),
        "win_rate": state.status.get("win_rate", 0.0),
        "profit_pct": state.status.get("current_profit_pct", 0.0),
        "sharpe_ratio": 0.0,  # TODO: Calculate
        "max_drawdown": 0.0,  # TODO: Calculate,
    }

@app.get("/api/analysis")
async def get_ai_analysis():
    """Get comprehensive AI market analysis"""
    try:
        if not state.trader or not state.is_running:
            return {
                "status": "idle",
                "last_updated": datetime.now().isoformat(),
                "message": "AI trader is not currently running. Start the trader to see real-time analysis."
            }

        # Get ML opportunities from trader
        signals = []
        if hasattr(state.trader, 'ml_opportunities_queue'):
            with state.trader.opportunities_lock:
                for opp in list(state.trader.ml_opportunities_queue)[:10]:  # Top 10 opportunities
                    signals.append({
                        "symbol": opp.symbol,
                        "direction": opp.direction,
                        "confidence": opp.confidence,
                        "reason": f"{opp.direction} signal detected - {opp.confidence:.1f}% confidence"
                    })

        # Build analysis response
        analysis = {
            "status": "scanning" if state.is_running else "idle",
            "last_updated": datetime.now().isoformat(),
            "signals": signals,
            "ml_insights": {
                "symbols_scanned": len(signals),
                "scan_duration": "3s",  # TODO: Track actual scan time
                "next_scan": f"{state.settings.get('scan_interval', 180)}s"
            }
        }

        return analysis

    except Exception as e:
        logger.error(f"Error in AI analysis: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "last_updated": datetime.now().isoformat()
        }

@app.get("/api/symbols/analysis")
async def get_symbol_analysis():
    """Get AI analysis for all symbols in market watch"""
    try:
        import symbol_config
        from src.execution.trade_executor import TradeExecutor

        # Get all symbols from MT5 (works even when trader not running)
        executor = state.trader.trade_executor if (state.trader and state.is_running) else standalone_executor
        all_symbols = executor.get_market_watch_symbols()

        if not all_symbols:
            return {"symbols": [], "message": "No symbols in market watch"}

        # Analyze each symbol
        symbols_analysis = []

        for symbol in all_symbols:
            try:
                # Get symbol tier and configuration
                tier = symbol_config.get_symbol_tier(symbol)
                scan_interval = symbol_config.get_scan_interval(symbol)

                # Check if symbol is in opportunities queue
                has_opportunity = False
                confidence = 0.0
                direction = None
                fast_track_eligible = False

                if hasattr(state.trader, 'ml_opportunities_queue'):
                    with state.trader.opportunities_lock:
                        for opp in state.trader.ml_opportunities_queue:
                            if opp.symbol == symbol:
                                has_opportunity = True
                                confidence = opp.confidence
                                direction = opp.direction
                                fast_track_eligible = symbol_config.should_fast_track(symbol, confidence)
                                break

                # Determine AI decision
                if has_opportunity:
                    if fast_track_eligible:
                        decision = "FAST-TRACK"
                        decision_reason = f"{confidence:.1f}% confidence - Ultra-high quality signal"
                    elif confidence >= 75:
                        decision = "TRADE"
                        decision_reason = f"{confidence:.1f}% confidence - High quality signal"
                    else:
                        decision = "MONITOR"
                        decision_reason = f"{confidence:.1f}% confidence - Below threshold"
                else:
                    decision = "NO_SIGNAL"
                    decision_reason = "No ML opportunity detected"

                symbols_analysis.append({
                    "symbol": symbol,
                    "tier": tier,
                    "scan_interval": scan_interval,
                    "decision": decision,
                    "decision_reason": decision_reason,
                    "has_opportunity": has_opportunity,
                    "confidence": confidence if has_opportunity else None,
                    "direction": direction,
                    "fast_track_eligible": fast_track_eligible
                })

            except Exception as e:
                logger.warning(f"Error analyzing {symbol}: {e}")
                symbols_analysis.append({
                    "symbol": symbol,
                    "tier": "UNKNOWN",
                    "scan_interval": 180,
                    "decision": "ERROR",
                    "decision_reason": str(e),
                    "has_opportunity": False,
                    "confidence": None,
                    "direction": None,
                    "fast_track_eligible": False
                })

        # Sort by tier priority and confidence
        tier_priority = {"HIGH_PRIORITY": 0, "MEDIUM_PRIORITY": 1, "LOW_PRIORITY": 2, "UNKNOWN": 3}
        symbols_analysis.sort(key=lambda x: (
            tier_priority.get(x["tier"], 99),
            -(x["confidence"] if x["confidence"] else 0)
        ))

        return {
            "symbols": symbols_analysis,
            "total_symbols": len(symbols_analysis),
            "with_opportunities": sum(1 for s in symbols_analysis if s["has_opportunity"]),
            "fast_track_ready": sum(1 for s in symbols_analysis if s["fast_track_eligible"]),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in symbol analysis: {e}", exc_info=True)
        return {"symbols": [], "error": str(e)}

# MT5 Communication Endpoints
@app.get("/api/mt5/commands")
async def get_mt5_commands():
    """MT5 polls this endpoint for pending commands"""
    # Return pending commands from queue
    # For now, return empty (trader will send commands directly)
    return {"commands": []}

@app.post("/api/mt5/account")
async def receive_account_info(account_data: dict):
    """Receive account info from MT5"""
    logger.info(f"Received account info: {account_data}")
    # Update state with account info
    if account_data:
        state.status.update({
            "balance": account_data.get("balance", 0),
            "equity": account_data.get("equity", 0),
            "margin": account_data.get("margin", 0),
            "free_margin": account_data.get("free_margin", 0)
        })
    return {"status": "received"}

@app.post("/api/mt5/positions")
async def receive_positions(positions_data: dict):
    """Receive open positions from MT5"""
    logger.info(f"Received {len(positions_data.get('positions', []))} positions")
    # Update state with positions
    if positions_data and "positions" in positions_data:
        state.status["open_positions"] = positions_data["positions"]
    return {"status": "received"}

@app.post("/api/mt5/trade_result")
async def receive_trade_result(result_data: dict):
    """Receive trade execution result from MT5"""
    logger.info(f"Trade result: {result_data}")
    # Broadcast to connected clients
    await manager.broadcast({
        "type": "trade_result",
        "data": result_data
    })
    return {"status": "received"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        # Send initial state
        await websocket.send_json({
            "type": "initial_state",
            "data": {
                "status": state.status,
                "settings": state.settings
            }
        })

        # Keep connection alive and broadcast updates
        while True:
            # Wait for messages (or send periodic updates)
            try:
                # Receive any client messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                # Process client message if needed

            except asyncio.TimeoutError:
                # Send periodic status update
                await websocket.send_json({
                    "type": "status_update",
                    "data": state.status,
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Create a standalone trade executor for MT5 connection checking
from src.execution.trade_executor import TradeExecutor
standalone_executor = TradeExecutor()

# Background task to update status
async def update_status_loop():
    """Periodically update status and broadcast to clients"""
    while True:
        await asyncio.sleep(3)  # Update every 3 seconds

        try:
            # Always check MT5 connection, even if trader isn't running
            executor = state.trader.trade_executor if (state.trader and state.is_running) else standalone_executor

            # Check if MT5 is connected
            account_info = executor.get_account_info()
            mt5_connected = account_info is not None

            if account_info and mt5_connected:
                # Calculate profit from actual account profit field
                account_profit = account_info.get('profit', 0.0)
                balance = account_info['balance']
                equity = account_info['equity']

                # Profit % = (current profit / balance) * 100
                current_profit_pct = (account_profit / balance * 100) if balance > 0 else 0.0

                # Get detailed activity from trader if running
                if state.is_running and state.trader:
                    activity = getattr(state.trader, 'current_activity', 'Scanning markets...')
                else:
                    activity = "Connected - Start trader to begin"

                state.status.update({
                    "mt5_connected": True,
                    "current_activity": activity,
                    "balance": balance,
                    "equity": equity,
                    "current_profit_pct": round(current_profit_pct, 2),
                    "open_positions": executor.get_open_positions() or [],
                    "last_updated": datetime.now().isoformat()
                })
            else:
                state.status.update({
                    "mt5_connected": False,
                    "current_activity": "Waiting for MT5 connection...",
                    "last_updated": datetime.now().isoformat()
                })

            # Broadcast to all clients
            await manager.broadcast({
                "type": "status_update",
                "data": state.status
            })

        except Exception as e:
            logger.error(f"Error updating status: {e}")
            state.status["mt5_connected"] = False
            state.status["current_activity"] = f"Error: {str(e)}"

@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(update_status_loop())
    logger.info("API Server started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if state.trader and state.is_running:
        state.trader.shutdown()
    logger.info("API Server shutdown")

# Run with: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
