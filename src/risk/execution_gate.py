"""
Execution Gate - Final Risk Validation Before Trade Execution

This module provides a comprehensive pre-execution validation that ALL trades
must pass through, regardless of ML confidence or fast-track status.

Acts as the final safety gate before money is risked.
"""
from datetime import datetime
from typing import Tuple, Optional, List
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionGateResult:
    """Result from execution gate validation"""
    can_trade: bool
    reason: str
    violations: List[str]


class ExecutionGate:
    """
    Final risk validation gate before trade execution.

    All trades MUST pass through this gate regardless of:
    - ML confidence level
    - Fast-track status
    - LLM recommendation

    This ensures no trade bypasses safety checks.
    """

    def __init__(
        self,
        news_filter,
        weekend_manager,
        circuit_breaker,
        exposure_tracker,
        max_positions: int = 3,
        enable_market_hours_filter: bool = True
    ):
        """
        Args:
            news_filter: NewsEventFilter instance
            weekend_manager: WeekendRiskManager instance
            circuit_breaker: FlashCrashCircuitBreaker instance
            exposure_tracker: CurrencyExposureTracker instance
            max_positions: Maximum concurrent positions allowed
            enable_market_hours_filter: Only trade during market hours
        """
        self.news_filter = news_filter
        self.weekend_manager = weekend_manager
        self.circuit_breaker = circuit_breaker
        self.exposure_tracker = exposure_tracker
        self.max_positions = max_positions
        self.enable_market_hours_filter = enable_market_hours_filter

        logger.info(f"Initialized Execution Gate (max positions: {max_positions})")

    def validate_trade(
        self,
        symbol: str,
        direction: str,
        open_positions: List,
        account_balance: float,
        current_time: datetime,
        broker_weekday: Optional[int] = None,
        broker_hour: Optional[int] = None
    ) -> ExecutionGateResult:
        """
        Validate if trade can be executed.

        This is the FINAL check before money is risked.

        Args:
            symbol: Trading symbol
            direction: 'BUY' or 'SELL'
            open_positions: List of currently open positions
            account_balance: Current account balance
            current_time: Current datetime
            broker_weekday: MT5 broker weekday (0=Sunday, 6=Saturday)
            broker_hour: MT5 broker hour (0-23)

        Returns:
            ExecutionGateResult with can_trade flag and reasons
        """
        violations = []

        # ========================================
        # CHECK 1: Position Limits
        # ========================================
        if len(open_positions) >= self.max_positions:
            violations.append(f"Position limit reached ({len(open_positions)}/{self.max_positions})")
            logger.warning(f"❌ GATE: Position limit ({len(open_positions)}/{self.max_positions})")

        # ========================================
        # CHECK 2: News Filter
        # ========================================
        if not self.news_filter.can_trade(symbol, current_time):
            news_events = self.news_filter.get_upcoming_events(symbol, current_time, hours_ahead=1)
            if news_events:
                event_desc = news_events[0]['title']
                violations.append(f"High-impact news within 1 hour: {event_desc}")
                logger.warning(f"❌ GATE: News filter blocked - {event_desc}")

        # ========================================
        # CHECK 3: Weekend Risk
        # ========================================
        weekend_status = self.weekend_manager.check_weekend_risk(
            current_time=current_time,
            open_positions=open_positions,
            broker_weekday=broker_weekday,
            broker_hour=broker_hour
        )

        if weekend_status.should_avoid_new_trades:
            violations.append(f"Weekend risk: {weekend_status.recommendation}")
            logger.warning(f"❌ GATE: {weekend_status.recommendation}")

        # ========================================
        # CHECK 4: Circuit Breaker
        # ========================================
        breaker_status = self.circuit_breaker.check_for_crash(
            symbol=symbol,
            current_price=0,  # Will be fetched by circuit breaker
            timestamp=current_time
        )

        if not breaker_status.can_trade:
            violations.append(f"Circuit breaker: {breaker_status.severity}")
            logger.warning(f"❌ GATE: Circuit breaker active - {breaker_status.severity}")

        # ========================================
        # CHECK 5: Currency Exposure
        # ========================================
        exposure = self.exposure_tracker.calculate_exposure(
            positions=open_positions,
            account_balance=account_balance
        )

        # Check if adding this symbol would exceed limits
        if not exposure.is_safe:
            violations.append(f"Currency exposure warnings: {exposure.warnings}")
            logger.warning(f"⚠️  GATE: Exposure warnings - {exposure.warnings}")

        # Extract currencies from symbol (e.g., EURUSD -> EUR, USD)
        if len(symbol) >= 6:
            base_currency = symbol[:3]
            quote_currency = symbol[3:6]

            # Check if either currency is already at limit
            for currency, pct in exposure.exposure.items():
                if currency in [base_currency, quote_currency]:
                    if pct >= 4.0:  # Max 4% per currency
                        violations.append(f"{currency} exposure at limit: {pct:.1f}%")
                        logger.warning(f"❌ GATE: {currency} exposure at {pct:.1f}% (max 4%)")

        # ========================================
        # CHECK 6: Market Hours (US30 specific)
        # ========================================
        if self.enable_market_hours_filter and 'US30' in symbol:
            if not self._is_market_hours(current_time):
                violations.append("Outside US market hours (9:30am-3pm EST)")
                logger.warning("❌ GATE: Outside market hours")

        # ========================================
        # FINAL DECISION
        # ========================================
        can_trade = len(violations) == 0

        if can_trade:
            logger.info(f"✅ EXECUTION GATE PASSED: {symbol} {direction}")
            reason = "All risk checks passed"
        else:
            logger.warning(f"❌ EXECUTION GATE BLOCKED: {symbol} {direction}")
            reason = f"Failed {len(violations)} checks"

        return ExecutionGateResult(
            can_trade=can_trade,
            reason=reason,
            violations=violations
        )

    def _is_market_hours(self, current_time: datetime) -> bool:
        """
        Check if within US market hours (9:30am-3pm EST)

        Args:
            current_time: Current datetime

        Returns:
            True if within market hours
        """
        # Convert to EST
        import pytz
        est = pytz.timezone('US/Eastern')
        est_time = current_time.astimezone(est)

        # Check weekday (0=Monday, 6=Sunday)
        if est_time.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check time (9:30am-3pm)
        hour = est_time.hour
        minute = est_time.minute

        # Before 9:30am
        if hour < 9 or (hour == 9 and minute < 30):
            return False

        # After 3:00pm
        if hour >= 15:
            return False

        return True
