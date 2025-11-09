"""
Flash Crash Circuit Breaker
Prevents black swan disaster events
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import deque

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status"""
    is_triggered: bool
    reason: str
    severity: str  # 'CRITICAL', 'WARNING', 'OK'
    should_halt_trading: bool
    should_close_positions: bool
    cooldown_minutes: int


class FlashCrashCircuitBreaker:
    """
    Circuit breaker to prevent catastrophic losses

    Triggers on:
    - Flash crash (>100 pips in 1 minute)
    - Rapid drawdown (>3% in 5 minutes)
    - Connection loss
    - Consecutive losses (5+ in a row)
    - Daily loss approaching limit
    """

    def __init__(
        self,
        flash_crash_pips: float = 100,
        rapid_drawdown_pct: float = 3.0,
        rapid_drawdown_minutes: int = 5,
        max_consecutive_losses: int = 5,
        daily_loss_critical_buffer: float = 1.0  # Stop when buffer < 1%
    ):
        """
        Args:
            flash_crash_pips: Pip threshold for flash crash detection
            rapid_drawdown_pct: % drawdown threshold
            rapid_drawdown_minutes: Time window for rapid drawdown
            max_consecutive_losses: Max consecutive losses before halt
            daily_loss_critical_buffer: FTMO daily loss buffer to trigger halt
        """
        self.flash_crash_threshold = flash_crash_pips
        self.rapid_drawdown_pct = rapid_drawdown_pct
        self.rapid_drawdown_minutes = rapid_drawdown_minutes
        self.max_consecutive_losses = max_consecutive_losses
        self.daily_loss_buffer_critical = daily_loss_critical_buffer

        # Tracking
        self.price_history: Dict[str, deque] = {}  # symbol -> [(timestamp, price)]
        self.equity_history: deque = deque(maxlen=100)  # (timestamp, equity)
        self.recent_trades: deque = deque(maxlen=20)  # Recent trade results
        self.last_connection_check: Optional[datetime] = None
        self.consecutive_losses: int = 0

        # Circuit breaker state
        self.is_halted: bool = False
        self.halt_reason: str = ""
        self.halt_until: Optional[datetime] = None

        logger.info("Initialized Flash Crash Circuit Breaker")

    def check_circuit_breaker(
        self,
        current_equity: float,
        current_prices: Dict[str, float],
        ftmo_daily_loss_buffer: float,
        positions: List[Dict] = None,
        connection_alive: bool = True
    ) -> CircuitBreakerStatus:
        """
        Check all circuit breaker conditions

        Args:
            current_equity: Current account equity
            current_prices: Current prices per symbol
            ftmo_daily_loss_buffer: FTMO daily loss buffer %
            positions: Open positions
            connection_alive: MT5 connection status

        Returns:
            CircuitBreakerStatus
        """
        now = datetime.now()

        # Check if currently halted
        if self.is_halted:
            if self.halt_until and now >= self.halt_until:
                # Cooldown expired
                self.is_halted = False
                self.halt_reason = ""
                self.halt_until = None
                logger.info("Circuit breaker reset - Trading resumed")
            else:
                remaining = (self.halt_until - now).total_seconds() / 60 if self.halt_until else 0
                return CircuitBreakerStatus(
                    is_triggered=True,
                    reason=f"Trading halted: {self.halt_reason} (Cooldown: {remaining:.0f} min)",
                    severity='CRITICAL',
                    should_halt_trading=True,
                    should_close_positions=False,
                    cooldown_minutes=int(remaining)
                )

        # Update tracking
        self._update_price_history(current_prices, now)
        self._update_equity_history(current_equity, now)

        # Check conditions (in order of severity)

        # 1. Connection loss
        if not connection_alive:
            return self._trigger_circuit_breaker(
                reason="MT5 connection lost",
                severity='CRITICAL',
                should_close=True,
                cooldown_minutes=30
            )

        # 2. Flash crash detection
        flash_crash = self._detect_flash_crash()
        if flash_crash:
            return self._trigger_circuit_breaker(
                reason=f"FLASH CRASH DETECTED: {flash_crash}",
                severity='CRITICAL',
                should_close=True,
                cooldown_minutes=60
            )

        # 3. Rapid drawdown
        rapid_dd = self._detect_rapid_drawdown()
        if rapid_dd:
            return self._trigger_circuit_breaker(
                reason=f"RAPID DRAWDOWN: {rapid_dd}",
                severity='CRITICAL',
                should_close=True,
                cooldown_minutes=30
            )

        # 4. FTMO daily loss critical
        if ftmo_daily_loss_buffer < self.daily_loss_buffer_critical:
            return self._trigger_circuit_breaker(
                reason=f"FTMO daily loss buffer critical: {ftmo_daily_loss_buffer:.2f}%",
                severity='CRITICAL',
                should_close=True,
                cooldown_minutes=1440  # Rest of day
            )

        # 5. Consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            return self._trigger_circuit_breaker(
                reason=f"{self.consecutive_losses} consecutive losses - System may be broken",
                severity='CRITICAL',
                should_close=False,  # Don't close existing, but halt new trades
                cooldown_minutes=120  # 2 hours to investigate
            )

        # 6. Large single-position loss (>50% of position)
        if positions:
            for pos in positions:
                risk_amount = pos.get('risk_amount', 0)
                current_loss = pos.get('profit', 0)
                if risk_amount > 0 and current_loss < -risk_amount * 0.5:
                    return CircuitBreakerStatus(
                        is_triggered=True,
                        reason=f"Large loss in {pos['symbol']}: ${current_loss:.2f} (>{50}% of risk)",
                        severity='WARNING',
                        should_halt_trading=False,
                        should_close_positions=False,  # Position monitor will handle
                        cooldown_minutes=0
                    )

        # All clear
        return CircuitBreakerStatus(
            is_triggered=False,
            reason="All systems normal",
            severity='OK',
            should_halt_trading=False,
            should_close_positions=False,
            cooldown_minutes=0
        )

    def record_trade_result(self, profit: float):
        """Record trade result for consecutive loss tracking"""
        is_loss = profit < 0

        if is_loss:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0  # Reset on win

        self.recent_trades.append({
            'timestamp': datetime.now(),
            'profit': profit,
            'is_loss': is_loss
        })

        if self.consecutive_losses >= 3:
            logger.warning(f"Consecutive losses: {self.consecutive_losses}")

    def reset_circuit_breaker(self):
        """Manually reset circuit breaker (admin override)"""
        self.is_halted = False
        self.halt_reason = ""
        self.halt_until = None
        logger.info("Circuit breaker manually reset")

    def _update_price_history(self, prices: Dict[str, float], timestamp: datetime):
        """Update price history for flash crash detection"""
        for symbol, price in prices.items():
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=60)  # Keep 60 data points

            self.price_history[symbol].append((timestamp, price))

    def _update_equity_history(self, equity: float, timestamp: datetime):
        """Update equity history for drawdown detection"""
        self.equity_history.append((timestamp, equity))

    def _detect_flash_crash(self) -> Optional[str]:
        """
        Detect flash crash (>100 pips in 1 minute)

        Returns:
            Description if detected, None otherwise
        """
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        for symbol, history in self.price_history.items():
            if len(history) < 2:
                continue

            # Get prices from last minute
            recent = [(ts, price) for ts, price in history if ts >= one_minute_ago]

            if len(recent) < 2:
                continue

            # Calculate max price movement in last minute
            prices = [p for _, p in recent]
            max_price = max(prices)
            min_price = min(prices)
            movement_pips = (max_price - min_price) * 10000

            if movement_pips > self.flash_crash_threshold:
                return f"{symbol} moved {movement_pips:.0f} pips in 1 minute"

        return None

    def _detect_rapid_drawdown(self) -> Optional[str]:
        """
        Detect rapid drawdown (>3% in 5 minutes)

        Returns:
            Description if detected, None otherwise
        """
        if len(self.equity_history) < 2:
            return None

        now = datetime.now()
        window_start = now - timedelta(minutes=self.rapid_drawdown_minutes)

        # Get equity values in window
        window_values = [(ts, equity) for ts, equity in self.equity_history if ts >= window_start]

        if len(window_values) < 2:
            return None

        # Calculate drawdown
        equities = [e for _, e in window_values]
        max_equity = max(equities)
        current_equity = equities[-1]

        drawdown_pct = ((max_equity - current_equity) / max_equity) * 100

        if drawdown_pct > self.rapid_drawdown_pct:
            return f"Account dropped {drawdown_pct:.1f}% in {self.rapid_drawdown_minutes} minutes"

        return None

    def _trigger_circuit_breaker(
        self,
        reason: str,
        severity: str,
        should_close: bool,
        cooldown_minutes: int
    ) -> CircuitBreakerStatus:
        """Trigger circuit breaker"""
        self.is_halted = True
        self.halt_reason = reason
        self.halt_until = datetime.now() + timedelta(minutes=cooldown_minutes)

        logger.critical(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
        logger.critical(f"Trading halted for {cooldown_minutes} minutes")

        if should_close:
            logger.critical("⚠️  CLOSING ALL POSITIONS")

        return CircuitBreakerStatus(
            is_triggered=True,
            reason=reason,
            severity=severity,
            should_halt_trading=True,
            should_close_positions=should_close,
            cooldown_minutes=cooldown_minutes
        )

    def get_status_report(self) -> str:
        """Generate circuit breaker status report"""
        if self.is_halted:
            remaining = (self.halt_until - datetime.now()).total_seconds() / 60 if self.halt_until else 0
            return f"""
CIRCUIT BREAKER STATUS
======================
Status: 🚨 TRIGGERED
Reason: {self.halt_reason}
Cooldown Remaining: {remaining:.0f} minutes
Consecutive Losses: {self.consecutive_losses}
"""
        else:
            return f"""
CIRCUIT BREAKER STATUS
======================
Status: ✓ ARMED (All systems normal)
Consecutive Losses: {self.consecutive_losses}
Flash Crash Threshold: {self.flash_crash_threshold} pips / 1 min
Rapid Drawdown Threshold: {self.rapid_drawdown_pct}% / {self.rapid_drawdown_minutes} min
"""
