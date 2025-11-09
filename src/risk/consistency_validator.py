"""
Consistency Rule Validator
Ensures no single day contributes >50% of total profit (FTMO Phase 2 requirement)
"""
from typing import List, Tuple, Dict
from datetime import datetime, date
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConsistencyStatus:
    """Consistency rule status"""
    is_compliant: bool
    today_profit_pct: float
    total_profit_pct: float
    largest_day_pct: float
    recommendation: str
    safe_profit_limit: float
    daily_breakdown: Dict[str, float]


class ConsistencyRuleValidator:
    """
    Validates FTMO Consistency Rule (Phase 2)

    Rule: No single trading day can account for more than 50% of total profit

    Example:
    - Total profit: $1000
    - Day 1: $600 profit
    - Day 1 contribution: 60%
    - VIOLATION: >50%

    This validator prevents that by:
    1. Tracking daily profit distribution
    2. Warning when approaching 40%
    3. Stopping trading at 45%
    """

    def __init__(
        self,
        warning_threshold: float = 40.0,  # Warn at 40%
        critical_threshold: float = 45.0,  # Stop at 45%
        max_single_day: float = 50.0       # FTMO limit
    ):
        """
        Args:
            warning_threshold: Pct where we warn user
            critical_threshold: Pct where we stop trading
            max_single_day: FTMO maximum (50%)
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.max_single_day = max_single_day

        # Track daily profits
        self.daily_profits: Dict[date, float] = {}

    def record_daily_profit(self, trade_date: date, profit_dollars: float):
        """
        Record profit for a specific day

        Args:
            trade_date: Date of trade
            profit_dollars: Profit in dollars
        """
        if trade_date not in self.daily_profits:
            self.daily_profits[trade_date] = 0

        self.daily_profits[trade_date] += profit_dollars
        logger.debug(f"Recorded ${profit_dollars:.2f} profit for {trade_date}")

    def check_consistency(
        self,
        current_date: date = None,
        current_day_profit: float = 0
    ) -> ConsistencyStatus:
        """
        Check if consistency rule is at risk

        Args:
            current_date: Today's date
            current_day_profit: Profit today so far (unrealized)

        Returns:
            ConsistencyStatus with recommendation
        """
        if current_date is None:
            current_date = datetime.now().date()

        # Calculate total profit
        total_profit = sum(self.daily_profits.values()) + current_day_profit

        if total_profit <= 0:
            return ConsistencyStatus(
                is_compliant=True,
                today_profit_pct=0,
                total_profit_pct=100,
                largest_day_pct=0,
                recommendation="No profit yet - consistency rule N/A",
                safe_profit_limit=float('inf'),
                daily_breakdown={}
            )

        # Calculate today's contribution
        projected_today = self.daily_profits.get(current_date, 0) + current_day_profit
        today_pct = (projected_today / total_profit) * 100

        # Find largest day
        all_days = self.daily_profits.copy()
        all_days[current_date] = projected_today

        largest_day_profit = max(all_days.values())
        largest_day_pct = (largest_day_profit / total_profit) * 100

        # Calculate safe limit for today
        # Formula: Today's profit must keep it under critical_threshold
        # safe_limit = (critical_threshold / 100) * total_profit - already_made_today
        already_made_today = self.daily_profits.get(current_date, 0)
        safe_limit = (self.critical_threshold / 100) * total_profit - already_made_today
        safe_limit = max(0, safe_limit)

        # Determine recommendation
        if today_pct >= self.critical_threshold:
            recommendation = f"🚨 STOP TRADING: Today is {today_pct:.1f}% of profit (limit: {self.max_single_day}%)"
            is_compliant = False

        elif today_pct >= self.warning_threshold:
            recommendation = f"⚠️  WARNING: Today is {today_pct:.1f}% of profit. Limit: ${safe_limit:.2f}"
            is_compliant = True

        else:
            recommendation = f"✅ Consistency safe: Today is {today_pct:.1f}% of profit"
            is_compliant = True

        # Create daily breakdown
        daily_pct = {
            str(day): (profit / total_profit * 100)
            for day, profit in all_days.items()
        }

        logger.info(f"Consistency check: {recommendation}")

        return ConsistencyStatus(
            is_compliant=is_compliant,
            today_profit_pct=today_pct,
            total_profit_pct=100,
            largest_day_pct=largest_day_pct,
            recommendation=recommendation,
            safe_profit_limit=safe_limit,
            daily_breakdown=daily_pct
        )

    def should_stop_trading_today(
        self,
        current_date: date = None,
        current_day_profit: float = 0
    ) -> Tuple[bool, str]:
        """
        Check if should stop trading today

        Returns:
            (should_stop, reason)
        """
        status = self.check_consistency(current_date, current_day_profit)

        if not status.is_compliant:
            return True, status.recommendation

        if status.today_profit_pct >= self.critical_threshold:
            return True, f"Today's profit ({status.today_profit_pct:.1f}%) approaching limit"

        return False, "OK to continue trading"

    def get_daily_distribution(self) -> Dict[str, float]:
        """
        Get daily profit distribution

        Returns:
            Dict of {date: profit_pct}
        """
        total = sum(self.daily_profits.values())
        if total <= 0:
            return {}

        return {
            str(day): (profit / total * 100)
            for day, profit in self.daily_profits.items()
        }

    def reset(self):
        """Reset validator (for new challenge)"""
        self.daily_profits = {}
        logger.info("Consistency validator reset")
