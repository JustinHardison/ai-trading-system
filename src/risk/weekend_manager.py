"""
Weekend/Friday Risk Management
Prevents weekend gap disasters
"""
from datetime import datetime, time
from typing import Dict, List, Tuple
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WeekendRiskStatus:
    """Weekend risk assessment"""
    is_friday: bool
    is_near_close: bool  # After 4pm Friday
    should_close_all: bool
    should_reduce_size: bool
    weekend_gap_risk: float  # 0-100
    recommendation: str


class WeekendRiskManager:
    """
    Manages weekend and Friday risk

    Key Features:
    - Close all positions by 4pm Friday (or reduce to 0.5% risk)
    - Gap risk calculator
    - Monday morning gap scanner
    - News event awareness for weekends
    """

    def __init__(
        self,
        friday_close_hour: int = 16,  # 4 PM
        allow_weekend_holds: bool = False,
        weekend_max_risk_pct: float = 0.5
    ):
        """
        Args:
            friday_close_hour: Hour to start closing positions on Friday (24h format)
            allow_weekend_holds: Allow holding positions over weekend with reduced size
            weekend_max_risk_pct: Max risk per position over weekend
        """
        self.friday_close_hour = friday_close_hour
        self.allow_weekend_holds = allow_weekend_holds
        self.weekend_max_risk = weekend_max_risk_pct

        logger.info(
            f"Initialized Weekend Risk Manager "
            f"(close hour: {friday_close_hour}, "
            f"weekend holds: {allow_weekend_holds})"
        )

    def assess_weekend_risk(
        self,
        current_time: datetime = None,
        open_positions: List[Dict] = None,
        broker_weekday: int = None,
        broker_hour: int = None
    ) -> WeekendRiskStatus:
        """
        Assess weekend risk and provide recommendations

        Args:
            current_time: System time (deprecated - only used if broker time not provided)
            open_positions: List of open positions
            broker_weekday: MT5 broker weekday (0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday)
            broker_hour: MT5 broker hour (0-23)

        Returns:
            WeekendRiskStatus with recommendations
        """
        # Use broker time if provided, otherwise fall back to system time
        if broker_weekday is not None and broker_hour is not None:
            # MT5 uses: 0=Sunday, 1=Monday, ..., 5=Friday, 6=Saturday
            # Python uses: 0=Monday, ..., 4=Friday, 5=Saturday, 6=Sunday
            # Convert MT5 weekday to Python weekday
            if broker_weekday == 0:  # MT5 Sunday = Python 6
                weekday = 6
            else:  # MT5 1-6 = Python 0-5
                weekday = broker_weekday - 1

            is_friday = weekday == 4
            current_hour = broker_hour
            logger.debug(f"Using MT5 broker time: weekday={broker_weekday} (Python={weekday}), hour={broker_hour}")
        else:
            # Fallback to system time (not recommended)
            current_time = current_time or datetime.now()
            is_friday = current_time.weekday() == 4
            current_hour = current_time.hour
            weekday = current_time.weekday()
            logger.warning("Using system time for weekend check - should use MT5 broker time!")

        open_positions = open_positions or []

        # Check if Friday
        # (is_friday already set above)

        # Check if near close (after specified hour on Friday)
        is_near_close = is_friday and current_hour >= self.friday_close_hour

        # Calculate weekend gap risk (now using broker weekday instead of current_time)
        gap_risk = self._calculate_weekend_gap_risk(
            weekday=weekday,
            hour=current_hour,
            open_positions=open_positions
        )

        # Determine recommendations
        should_close_all = False
        should_reduce_size = False
        recommendation = ""

        if is_near_close:
            if not self.allow_weekend_holds or gap_risk > 70:
                should_close_all = True
                recommendation = f"CLOSE ALL positions - Friday {current_hour}:00 (broker time), Gap risk: {gap_risk:.0f}%"
            elif gap_risk > 50:
                should_reduce_size = True
                recommendation = f"REDUCE position sizes to {self.weekend_max_risk}% risk - Gap risk: {gap_risk:.0f}%"
            else:
                should_reduce_size = True
                recommendation = f"Can hold over weekend with reduced size (Gap risk: {gap_risk:.0f}%)"
        elif is_friday and current_hour >= 14:
            recommendation = f"Friday afternoon (broker time) - {self.friday_close_hour - current_hour} hours until close time"
        else:
            recommendation = "No weekend risk concerns"

        return WeekendRiskStatus(
            is_friday=is_friday,
            is_near_close=is_near_close,
            should_close_all=should_close_all,
            should_reduce_size=should_reduce_size,
            weekend_gap_risk=gap_risk,
            recommendation=recommendation
        )

    def should_open_new_position(
        self,
        current_time: datetime = None,
        market_is_open: bool = True  # Default to True, let MT5 tell us if closed
    ) -> Tuple[bool, str]:
        """
        Check if new positions should be opened given time

        Args:
            current_time: Current time to check
            market_is_open: Whether MT5 reports market as open (from tick data)

        Returns:
            (should_open, reason)
        """
        current_time = current_time or datetime.now()

        # If MT5 says market is closed, respect that
        if not market_is_open:
            return False, "Market closed - No tick data from MT5"

        # Don't open new positions after 2pm Friday (EST/NY time)
        # NOTE: Only applies if truly Friday in trading time, not local time
        if current_time.weekday() == 4 and current_time.hour >= 14:
            # But Forex is 24/5, so check if we're really close to Friday 5pm EST
            # For now, allow trading - let MT5 tick data determine market status
            pass

        # REMOVED: Calendar-based weekend check - Forex trades 24/5!
        # Use MT5 market_is_open flag instead

        # REMOVED: Hard-coded Monday morning rule
        # Market conditions are now evaluated by LLM in portfolio_manager
        # LLM analyzes actual market data (volatility, spreads, liquidity)
        # instead of checking calendar dates

        return True, "Safe to open positions"

    def _calculate_weekend_gap_risk(
        self,
        weekday: int,
        hour: int,
        open_positions: List[Dict]
    ) -> float:
        """
        Calculate weekend gap risk (0-100)

        Args:
            weekday: Day of week (0=Monday, ..., 4=Friday, 5=Saturday, 6=Sunday)
            hour: Hour of day (0-23)
            open_positions: List of open positions

        Factors:
        - Time until weekend
        - Current market volatility
        - Geopolitical situation (would need news API)
        - Number of open positions
        - Position directions (all same direction = higher risk)
        """
        risk = 0.0

        # Base risk from time proximity
        if weekday == 4:  # Friday
            # Friday - higher risk as day progresses
            risk += 30 + (hour * 2)  # 30-76 risk
        elif weekday == 3:  # Thursday
            # Thursday evening
            risk += 20
        else:
            risk += 10

        # Risk from open positions
        if open_positions:
            # More positions = more risk
            position_risk = min(len(open_positions) * 5, 20)
            risk += position_risk

            # Check if all positions in same direction (correlation risk)
            directions = [p['direction'] for p in open_positions]
            if len(set(directions)) == 1:  # All BUY or all SELL
                risk += 15
                logger.warning("Weekend risk elevated - all positions same direction")

        # Cap at 100
        risk = min(risk, 100)

        return risk

    def check_monday_gaps(
        self,
        positions: List[Dict],
        market_data: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Check for Monday morning gaps in open positions

        Returns:
            List of positions with significant gaps
        """
        current_time = datetime.now()

        # Only relevant on Monday morning
        if current_time.weekday() != 0 or current_time.hour > 6:
            return []

        gapped_positions = []

        for position in positions:
            symbol = position['symbol']
            entry_price = position['entry_price']

            # Get current price
            if symbol not in market_data:
                continue

            current_price = market_data[symbol].get('close', entry_price)

            # Calculate gap
            gap_pips = abs(current_price - entry_price) * 10000

            # Significant gap > 20 pips
            if gap_pips > 20:
                direction = position['direction']
                is_favorable = (direction == 'BUY' and current_price > entry_price) or \
                              (direction == 'SELL' and current_price < entry_price)

                gapped_positions.append({
                    'position': position,
                    'gap_pips': gap_pips,
                    'is_favorable': is_favorable,
                    'recommendation': 'HOLD' if is_favorable else 'CLOSE IMMEDIATELY'
                })

                logger.warning(
                    f"Monday gap detected: {symbol} {direction} - "
                    f"Gap: {gap_pips:.1f} pips ({'Favorable' if is_favorable else 'Unfavorable'})"
                )

        return gapped_positions

    def get_weekend_report(
        self,
        current_time: datetime = None,
        open_positions: List[Dict] = None
    ) -> str:
        """Generate weekend risk report"""
        status = self.assess_weekend_risk(current_time, open_positions)

        report = f"""
WEEKEND RISK ASSESSMENT
=======================
Day: {current_time.strftime('%A %H:%M') if current_time else 'N/A'}
Is Friday: {status.is_friday}
Near Close: {status.is_near_close}
Weekend Gap Risk: {status.weekend_gap_risk:.0f}/100

RECOMMENDATION:
{status.recommendation}

Actions:
- Close All: {status.should_close_all}
- Reduce Size: {status.should_reduce_size}

Open Positions: {len(open_positions) if open_positions else 0}
"""

        return report
