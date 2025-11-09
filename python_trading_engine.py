#!/usr/bin/env python3
"""
Python Trading Engine - FULL CONTROL
No more EA making decisions, Python does EVERYTHING
"""
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.brokers.mt5_trade_manager import MT5TradeManager
from src.ml.pro_feature_engineer import ProFeatureEngineer
from src.ai.hybrid_exit_manager import HybridExitManager
from src.ai.rl_exit_agent_pytorch import RLExitAgent
from src.ai.professional_exit_manager import ProfessionalExitManager
from src.risk.position_sizer import PositionSizer
import pickle
import numpy as np
import torch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PythonTradingEngine:
    """
    Complete trading system in Python
    - Monitors market
    - Makes entry decisions (ML)
    - Manages positions (RL + Professional hybrid)
    - Executes trades via MT5
    """

    def __init__(self):
        logger.info("="*80)
        logger.info("PYTHON TRADING ENGINE - INITIALIZING")
        logger.info("="*80)

        # Initialize components
        self.mt5 = MT5TradeManager()
        self.feature_engineer = ProFeatureEngineer(enable_all_tiers=True)
        self.position_sizer = PositionSizer()

        # Load ML models
        logger.info("\n[1/5] Loading ML Entry Models...")
        self.load_ml_models()

        # Load RL exit agent
        logger.info("\n[2/5] Loading RL Exit Agent...")
        self.load_rl_agent()

        # Initialize managers
        logger.info("\n[3/5] Initializing Exit Managers...")
        self.professional_manager = ProfessionalExitManager()
        self.hybrid_manager = HybridExitManager(
            rl_agent=self.rl_agent,
            professional_manager=self.professional_manager,
            rl_weight=0.7
        )

        # Connect to MT5
        logger.info("\n[4/5] Connecting to MT5...")
        if not self.mt5.connect():
            raise Exception("Failed to connect to MT5")

        # Configuration
        self.symbol = "US30Z25.sim"
        self.timeframe = "M1"
        self.entry_threshold = 70  # ML confidence threshold
        self.max_positions = 1
        self.risk_pct = 2.0

        # State
        self.last_check = datetime.now()
        self.monitoring_positions = {}

        logger.info("\n[5/5] Engine Ready!")
        logger.info("="*80)
        logger.info(f"✅ Python Trading Engine ONLINE")
        logger.info(f"   Symbol: {self.symbol}")
        logger.info(f"   Entry Threshold: {self.entry_threshold}%")
        logger.info(f"   Max Positions: {self.max_positions}")
        logger.info(f"   Risk Per Trade: {self.risk_pct}%")
        logger.info("="*80)

    def load_ml_models(self):
        """Load ML entry models"""
        try:
            # M1 Scalping model
            with open('models/integrated_ensemble_latest.pkl', 'rb') as f:
                m1_data = pickle.load(f)
            self.m1_model = m1_data['xgb_model']
            self.m1_scaler = m1_data['scaler']
            logger.info(f"✅ M1 Model loaded")

            # H1 Swing model
            with open('models/integrated_h1_ensemble_latest.pkl', 'rb') as f:
                h1_data = pickle.load(f)
            self.h1_model = h1_data['xgb_model']
            self.h1_scaler = h1_data['scaler']
            logger.info(f"✅ H1 Model loaded")

        except Exception as e:
            logger.error(f"Error loading ML models: {e}")
            raise

    def load_rl_agent(self):
        """Load RL exit agent"""
        try:
            self.rl_agent = RLExitAgent(state_dim=235)
            model_path = 'models/rl_exit_agent.pth'
            self.rl_agent.q_network.load_state_dict(torch.load(model_path))
            self.rl_agent.q_network.eval()
            logger.info(f"✅ RL Agent loaded from {model_path}")

        except Exception as e:
            logger.error(f"Error loading RL agent: {e}")
            raise

    def check_entry_signal(self, bars_data: dict) -> tuple:
        """
        Check if we should enter a trade
        Returns: (should_enter, direction, confidence)
        """
        try:
            # Extract features
            features = self.feature_engineer.extract_all_features(bars_data)

            # Get ML prediction
            X = np.array([list(features.values())])
            X_scaled = self.m1_scaler.transform(X)
            pred_proba = self.m1_model.predict_proba(X_scaled)[0]

            # Get direction and confidence
            pred_class = np.argmax(pred_proba)
            confidence = max(pred_proba) * 100

            if pred_class == 1:  # BUY
                direction = "BUY"
            elif pred_class == 2:  # SELL
                direction = "SELL"
            else:  # HOLD
                return False, "HOLD", confidence

            # Check threshold
            if confidence < self.entry_threshold:
                return False, direction, confidence

            return True, direction, confidence

        except Exception as e:
            logger.error(f"Error checking entry: {e}")
            return False, "HOLD", 0.0

    def manage_position(self, trade):
        """
        Manage an open position using Hybrid Exit Manager
        """
        try:
            # Get current bars data for features
            # (In production, you'd fetch real-time bars)
            # For now, use cached features
            features = self.monitoring_positions.get(trade.ticket, {}).get('features', {})

            # Calculate current metrics
            profit_points = trade.profit_points
            bars_held = trade.bars_held
            max_profit = self.monitoring_positions.get(trade.ticket, {}).get('max_profit', profit_points)

            # Update max profit
            if profit_points > max_profit:
                max_profit = profit_points
                if trade.ticket in self.monitoring_positions:
                    self.monitoring_positions[trade.ticket]['max_profit'] = max_profit

            # Get hybrid exit decision
            decision = self.hybrid_manager.decide_exit(
                features=features,
                current_profit_points=profit_points,
                bars_held=bars_held,
                max_profit_points=max_profit,
                entry_confidence=self.monitoring_positions.get(trade.ticket, {}).get('entry_conf', 70.0),
                trade_type="scalp"
            )

            logger.info(f"🔥 HYBRID EXIT: {decision.action} | Profit: {profit_points:.1f}pts | "
                       f"Combined EV: {decision.combined_ev:.1f} | RL: {decision.rl_contribution*100:.0f}%")

            # Execute decision
            if decision.action == "CLOSE_ALL":
                success, msg = self.mt5.close_position(trade.ticket)
                if success:
                    logger.info(f"✅ CLOSED position {trade.ticket} | Profit: ${trade.profit:.2f}")
                    if trade.ticket in self.monitoring_positions:
                        del self.monitoring_positions[trade.ticket]
                else:
                    logger.error(f"❌ Failed to close: {msg}")

            elif decision.action == "SCALE_OUT_50":
                close_volume = trade.volume * 0.5
                success, msg = self.mt5.close_position(trade.ticket, close_volume)
                if success:
                    logger.info(f"✅ SCALED OUT 50% of position {trade.ticket}")
                else:
                    logger.error(f"❌ Failed to scale: {msg}")

            elif decision.action == "SCALE_OUT_25":
                close_volume = trade.volume * 0.25
                success, msg = self.mt5.close_position(trade.ticket, close_volume)
                if success:
                    logger.info(f"✅ SCALED OUT 25% of position {trade.ticket}")
                else:
                    logger.error(f"❌ Failed to scale: {msg}")

        except Exception as e:
            logger.error(f"Error managing position: {e}")

    def run_cycle(self):
        """Run one trading cycle"""
        try:
            # Get account info
            account = self.mt5.get_account_info()
            if not account:
                logger.error("Failed to get account info")
                return

            # Get open positions
            positions = self.mt5.get_open_positions()

            # Manage existing positions
            for position in positions:
                self.manage_position(position)

            # Check for new entries (if under max positions)
            if len(positions) < self.max_positions:
                # Get current market data (simplified - in production fetch real bars)
                # For now, skip entry checks
                pass

            # Log status every 60 seconds
            now = datetime.now()
            if (now - self.last_check).total_seconds() >= 60:
                logger.info(f"📊 Status: {len(positions)} positions | Balance: ${account['balance']:,.2f} | "
                           f"Equity: ${account['equity']:,.2f} | Profit: ${account['profit']:,.2f}")
                self.last_check = now

        except Exception as e:
            logger.error(f"Error in cycle: {e}")

    def run(self):
        """Main loop"""
        logger.info("\n🚀 Starting main trading loop...")
        logger.info("   Press Ctrl+C to stop\n")

        try:
            while True:
                self.run_cycle()
                time.sleep(1)  # Check every second

        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Keyboard interrupt received")
        except Exception as e:
            logger.error(f"\n\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info("\n🛑 Shutting down...")
            self.mt5.disconnect()
            logger.info("✅ Engine stopped")


if __name__ == "__main__":
    engine = PythonTradingEngine()
    engine.run()
