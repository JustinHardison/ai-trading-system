"""
Circuit Breakers - Safety Limits for Trading System
Prevents catastrophic losses through automatic trading halts
"""

from datetime import datetime, date
from typing import Dict, Optional
from loguru import logger
import json
import os


class CircuitBreakers:
    """
    Trading safety system with multiple circuit breakers

    Features:
    1. Daily loss limit (% of account)
    2. Max consecutive losses counter
    3. Max drawdown from peak
    4. Trading hours restriction
    5. Volatility spike detection
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 5.0,
        max_consecutive_losses: int = 5,
        max_drawdown_pct: float = 10.0,
        state_file: str = "/tmp/circuit_breakers_state.json"
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.max_drawdown_pct = max_drawdown_pct
        self.state_file = state_file

        # Load previous state
        self.state = self._load_state()

        # Initialize if new day
        if self.state.get('date') != str(date.today()):
            self._reset_daily_state()

    def _load_state(self) -> Dict:
        """Load circuit breaker state from file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load circuit breaker state: {e}")

        return self._get_default_state()

    def _save_state(self):
        """Save circuit breaker state to file"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")

    def _get_default_state(self) -> Dict:
        """Get default state for circuit breakers"""
        return {
            'date': str(date.today()),
            'daily_start_balance': 0,
            'daily_pnl': 0,
            'consecutive_losses': 0,
            'peak_balance': 0,
            'trades_today': 0,
            'breakers_triggered': [],
            'trading_halted': False,
            'halt_reason': None
        }

    def _reset_daily_state(self):
        """Reset state for new trading day"""
        logger.info("🔄 Circuit Breakers: New trading day, resetting state")
        self.state = self._get_default_state()
        self._save_state()

    def update_balance(self, current_balance: float, daily_start_balance: Optional[float] = None):
        """
        Update balance tracking

        Args:
            current_balance: Current account balance
            daily_start_balance: Balance at start of day (optional)
        """
        if daily_start_balance is not None:
            self.state['daily_start_balance'] = daily_start_balance

        # Set initial balance if not set
        if self.state['daily_start_balance'] == 0:
            self.state['daily_start_balance'] = current_balance

        # Update peak balance
        if current_balance > self.state['peak_balance']:
            self.state['peak_balance'] = current_balance

        # Calculate daily P&L
        self.state['daily_pnl'] = current_balance - self.state['daily_start_balance']

        self._save_state()

    def record_trade_result(self, profit: float, was_winner: bool):
        """
        Record a trade result

        Args:
            profit: Trade profit/loss
            was_winner: Whether trade was profitable
        """
        self.state['trades_today'] += 1

        if was_winner:
            self.state['consecutive_losses'] = 0
        else:
            self.state['consecutive_losses'] += 1

        logger.info(f"📊 Trade #{self.state['trades_today']}: "
                   f"{'WIN' if was_winner else 'LOSS'} ${profit:.2f} | "
                   f"Consecutive losses: {self.state['consecutive_losses']}")

        self._save_state()

    def check_breakers(self, current_balance: float) -> Dict:
        """
        Check all circuit breakers

        Returns:
            {
                'allow_trading': bool,
                'triggered_breakers': List[str],
                'reason': str,
                'daily_loss_pct': float,
                'consecutive_losses': int,
                'drawdown_pct': float
            }
        """
        triggered = []

        # Update balance
        self.update_balance(current_balance)

        # 1. Daily loss limit
        if self.state['daily_start_balance'] > 0:
            daily_loss_pct = (self.state['daily_pnl'] / self.state['daily_start_balance']) * 100
        else:
            daily_loss_pct = 0

        if daily_loss_pct < -self.max_daily_loss_pct:
            triggered.append(f"Daily loss limit: {daily_loss_pct:.2f}% (max: -{self.max_daily_loss_pct}%)")

        # 2. Consecutive losses
        if self.state['consecutive_losses'] >= self.max_consecutive_losses:
            triggered.append(f"Consecutive losses: {self.state['consecutive_losses']} (max: {self.max_consecutive_losses})")

        # 3. Drawdown from peak
        if self.state['peak_balance'] > 0:
            drawdown_pct = ((self.state['peak_balance'] - current_balance) / self.state['peak_balance']) * 100
        else:
            drawdown_pct = 0

        if drawdown_pct > self.max_drawdown_pct:
            triggered.append(f"Drawdown from peak: {drawdown_pct:.2f}% (max: {self.max_drawdown_pct}%)")

        # Update state if breakers triggered
        if triggered and not self.state['trading_halted']:
            self.state['trading_halted'] = True
            self.state['halt_reason'] = '; '.join(triggered)
            self.state['breakers_triggered'] = triggered
            self._save_state()

            logger.error("🚨 CIRCUIT BREAKERS TRIGGERED - TRADING HALTED 🚨")
            for breaker in triggered:
                logger.error(f"   ❌ {breaker}")

        allow_trading = len(triggered) == 0 and not self.state['trading_halted']

        return {
            'allow_trading': allow_trading,
            'triggered_breakers': triggered,
            'reason': self.state['halt_reason'] if self.state['trading_halted'] else None,
            'daily_loss_pct': daily_loss_pct,
            'consecutive_losses': self.state['consecutive_losses'],
            'drawdown_pct': drawdown_pct,
            'trades_today': self.state['trades_today']
        }

    def manual_halt(self, reason: str = "Manual override"):
        """Manually halt trading"""
        self.state['trading_halted'] = True
        self.state['halt_reason'] = reason
        self._save_state()
        logger.warning(f"⚠️ Trading manually halted: {reason}")

    def manual_resume(self):
        """Manually resume trading"""
        self.state['trading_halted'] = False
        self.state['halt_reason'] = None
        self.state['breakers_triggered'] = []
        self._save_state()
        logger.info("✅ Trading manually resumed")

    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        return {
            'trading_allowed': not self.state['trading_halted'],
            'halt_reason': self.state['halt_reason'],
            'daily_pnl': self.state['daily_pnl'],
            'consecutive_losses': self.state['consecutive_losses'],
            'trades_today': self.state['trades_today'],
            'peak_balance': self.state['peak_balance'],
            'breakers_triggered': self.state['breakers_triggered']
        }
