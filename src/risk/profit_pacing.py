"""
Profit Pacing Manager
Dynamically adjusts trading strategy based on progress toward FTMO target

Key Insight:
- If behind schedule → increase aggression (trade more, slightly lower confidence)
- If on track → maintain current approach
- If ahead → reduce aggression (protect profits, higher confidence required)
- If way ahead (>12%) → stop trading early (protect gains)
"""
from typing import Tuple, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PacingStatus:
    """Current pacing status"""
    current_profit_pct: float
    target_profit_pct: float  # 10% for Phase 1, 5% for Phase 2
    days_elapsed: int
    days_remaining: int
    progress_pct: float  # % of target achieved
    is_on_track: bool
    recommendation: str
    urgency_level: str  # RELAXED, NORMAL, AGGRESSIVE, URGENT
    min_confidence: float  # Dynamic confidence threshold
    max_risk_per_trade: float  # Dynamic risk level
    target_trades_today: int  # How many trades to take today


class ProfitPacingManager:
    """
    Intelligently paces toward FTMO profit target

    Scenarios:
    1. Way ahead (>15%): Stop trading, protect profits
    2. Ahead (12-15%): Very selective, high confidence only
    3. On track (8-12%): Normal operations
    4. Slightly behind (5-8%): Slightly more aggressive
    5. Behind (3-5%): More aggressive, lower confidence threshold
    6. Significantly behind (<3%, <5 days left): URGENT mode
    """

    def __init__(
        self,
        phase: int = 1,
        challenge_days: int = 30
    ):
        """
        Args:
            phase: FTMO phase (1, 2, or 3)
            challenge_days: Total days in challenge (default 30)
        """
        self.phase = phase
        self.challenge_days = challenge_days

        # Set targets based on phase
        if phase == 1:
            self.profit_target = 10.0  # 10%
            self.max_safe_profit = 15.0  # Stop at 15%
        elif phase == 2:
            self.profit_target = 5.0  # 5%
            self.max_safe_profit = 8.0  # Stop at 8%
        else:  # Funded
            self.profit_target = 10.0  # Monthly target
            self.max_safe_profit = 15.0

    def assess_pacing(
        self,
        current_profit_pct: float,
        challenge_start_date: datetime,
        current_date: datetime = None
    ) -> PacingStatus:
        """
        Assess current progress and recommend strategy adjustments

        Args:
            current_profit_pct: Current profit percentage
            challenge_start_date: When challenge started
            current_date: Current date (default: now)

        Returns:
            PacingStatus with recommendations
        """
        if current_date is None:
            current_date = datetime.now()

        # Calculate time progress
        days_elapsed = (current_date - challenge_start_date).days
        days_remaining = max(0, self.challenge_days - days_elapsed)

        # Calculate progress
        progress_pct = (current_profit_pct / self.profit_target) * 100 if self.profit_target > 0 else 0

        # Expected progress (linear)
        expected_progress = (days_elapsed / self.challenge_days) * self.profit_target
        ahead_or_behind = current_profit_pct - expected_progress

        # Determine urgency and strategy
        urgency, recommendation, min_conf, max_risk, target_trades = self._calculate_strategy(
            current_profit_pct=current_profit_pct,
            days_remaining=days_remaining,
            ahead_or_behind=ahead_or_behind,
            progress_pct=progress_pct
        )

        is_on_track = abs(ahead_or_behind) <= 2.0  # Within 2% of expected

        logger.info(
            f"Pacing: {current_profit_pct:.1f}% profit, "
            f"{days_elapsed} days elapsed, {days_remaining} days left. "
            f"Progress: {progress_pct:.0f}%, {urgency} mode"
        )

        return PacingStatus(
            current_profit_pct=current_profit_pct,
            target_profit_pct=self.profit_target,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining,
            progress_pct=progress_pct,
            is_on_track=is_on_track,
            recommendation=recommendation,
            urgency_level=urgency,
            min_confidence=min_conf,
            max_risk_per_trade=max_risk,
            target_trades_today=target_trades
        )

    def _calculate_strategy(
        self,
        current_profit_pct: float,
        days_remaining: int,
        ahead_or_behind: float,
        progress_pct: float
    ) -> Tuple[str, str, float, float, int]:
        """
        Calculate trading strategy based on situation

        Returns:
            (urgency_level, recommendation, min_confidence, max_risk, target_trades)
        """

        # SCENARIO 1: Target reached or exceeded
        if current_profit_pct >= self.profit_target:
            if current_profit_pct >= self.max_safe_profit:
                return (
                    "PROTECTED",
                    f"🎉 Target exceeded! {current_profit_pct:.1f}% (target: {self.profit_target}%). STOP TRADING - protect gains!",
                    100.0,  # Don't trade (impossible confidence)
                    0.0,    # No risk
                    0       # No trades
                )
            else:
                return (
                    "CONSERVATIVE",
                    f"✅ Target reached! {current_profit_pct:.1f}% (target: {self.profit_target}%). Trade very conservatively to protect.",
                    85.0,   # Very high confidence only
                    0.5,    # Low risk
                    1       # Max 1 trade per day
                )

        # SCENARIO 2: Way ahead of schedule (>4% ahead)
        if ahead_or_behind > 4.0:
            return (
                "RELAXED",
                f"📈 Ahead of schedule by {ahead_or_behind:.1f}%. Reduce risk, be very selective.",
                80.0,   # High confidence
                1.0,    # Lower risk
                1-2     # 1-2 trades per day
            )

        # SCENARIO 3: Ahead of schedule (2-4% ahead)
        if ahead_or_behind > 2.0:
            return (
                "COMFORTABLE",
                f"✅ Ahead by {ahead_or_behind:.1f}%. Maintain selectivity, standard risk.",
                75.0,   # Standard confidence
                1.5,    # Standard risk
                2       # 2 trades per day
            )

        # SCENARIO 4: On track (within 2% of expected)
        if abs(ahead_or_behind) <= 2.0:
            return (
                "NORMAL",
                f"✅ On track. Continue normal operations.",
                75.0,   # Standard confidence
                1.5,    # Standard risk
                2-3     # 2-3 trades per day
            )

        # SCENARIO 5: Slightly behind (2-4% behind, >10 days left)
        if -4.0 < ahead_or_behind <= -2.0 and days_remaining > 10:
            return (
                "FOCUSED",
                f"⚠️  Slightly behind by {abs(ahead_or_behind):.1f}%. Need {abs(ahead_or_behind) / days_remaining:.1f}% per day.",
                70.0,   # Slightly lower confidence
                2.0,    # Slightly higher risk
                3       # 3 trades per day
            )

        # SCENARIO 6: Behind (4-6% behind, >5 days left)
        if -6.0 < ahead_or_behind <= -4.0 and days_remaining > 5:
            return (
                "AGGRESSIVE",
                f"⚠️  Behind by {abs(ahead_or_behind):.1f}%. Need {abs(ahead_or_behind) / days_remaining:.1f}% per day. Increase activity.",
                65.0,   # Lower confidence
                2.5,    # Higher risk
                4       # 4 trades per day
            )

        # SCENARIO 7: Significantly behind (<5 days left, need >2% per day)
        required_per_day = (self.profit_target - current_profit_pct) / max(days_remaining, 1)

        if days_remaining <= 5 and required_per_day > 2.0:
            if required_per_day > 5.0:
                return (
                    "IMPOSSIBLE",
                    f"🚨 Need {required_per_day:.1f}% per day with {days_remaining} days left. Target likely unachievable.",
                    60.0,   # Very low confidence (desperation)
                    3.0,    # Max risk
                    6       # Many trades
                )
            else:
                return (
                    "URGENT",
                    f"🚨 URGENT: Need {required_per_day:.1f}% per day with {days_remaining} days left!",
                    65.0,   # Low confidence
                    2.5,    # High risk
                    5       # 5 trades per day
                )

        # SCENARIO 8: Very behind, but time remaining
        if ahead_or_behind <= -6.0 and days_remaining > 5:
            return (
                "AGGRESSIVE",
                f"⚠️  Very behind by {abs(ahead_or_behind):.1f}%. Need {abs(ahead_or_behind) / days_remaining:.1f}% per day.",
                65.0,   # Low confidence
                2.5,    # High risk
                4-5     # 4-5 trades per day
            )

        # Default: Normal
        return (
            "NORMAL",
            "Continue normal operations",
            75.0,
            1.5,
            2
        )

    def should_stop_trading(
        self,
        current_profit_pct: float,
        current_date: datetime,
        challenge_start_date: datetime
    ) -> Tuple[bool, str]:
        """
        Determine if should stop trading for the challenge

        Returns:
            (should_stop, reason)
        """
        # Stop if target exceeded
        if current_profit_pct >= self.max_safe_profit:
            return True, f"Target exceeded ({current_profit_pct:.1f}% > {self.max_safe_profit}%). Protect profits!"

        # Stop if target reached with <3 days left
        days_remaining = self.challenge_days - (current_date - challenge_start_date).days
        if current_profit_pct >= self.profit_target and days_remaining <= 3:
            return True, f"Target reached with {days_remaining} days left. Protect profits!"

        return False, "Continue trading"

    def calculate_daily_target(
        self,
        current_profit_pct: float,
        days_remaining: int
    ) -> float:
        """
        Calculate optimal daily profit target

        Args:
            current_profit_pct: Current profit
            days_remaining: Days left in challenge

        Returns:
            Daily profit target %
        """
        if days_remaining <= 0:
            return 0

        remaining_profit = max(0, self.profit_target - current_profit_pct)
        daily_target = remaining_profit / days_remaining

        # Cap at reasonable maximum (3% per day)
        return min(daily_target, 3.0)

    def get_confidence_adjustment(
        self,
        base_confidence: float,
        pacing_status: PacingStatus
    ) -> float:
        """
        Adjust ML confidence requirement based on pacing

        Args:
            base_confidence: ML signal confidence
            pacing_status: Current pacing status

        Returns:
            Adjusted confidence (may lower threshold if behind)
        """
        if pacing_status.urgency_level == "PROTECTED":
            # Don't trade at all
            return 0

        if pacing_status.urgency_level == "CONSERVATIVE":
            # Raise threshold
            return base_confidence + 10

        if pacing_status.urgency_level == "RELAXED":
            # Slightly raise threshold
            return base_confidence + 5

        if pacing_status.urgency_level in ["NORMAL", "COMFORTABLE"]:
            # Normal threshold
            return base_confidence

        if pacing_status.urgency_level == "FOCUSED":
            # Slightly lower threshold
            return base_confidence - 5

        if pacing_status.urgency_level in ["AGGRESSIVE", "URGENT"]:
            # Lower threshold significantly
            return base_confidence - 10

        if pacing_status.urgency_level == "IMPOSSIBLE":
            # Desperation mode
            return base_confidence - 15

        return base_confidence

    def get_risk_adjustment(
        self,
        base_risk: float,
        pacing_status: PacingStatus
    ) -> float:
        """
        Adjust risk per trade based on pacing

        Args:
            base_risk: Base risk %
            pacing_status: Current pacing status

        Returns:
            Adjusted risk %
        """
        urgency_multipliers = {
            "PROTECTED": 0.0,      # No trades
            "CONSERVATIVE": 0.5,   # Very low risk
            "RELAXED": 0.75,       # Reduced risk
            "COMFORTABLE": 1.0,    # Standard risk
            "NORMAL": 1.0,         # Standard risk
            "FOCUSED": 1.25,       # Slightly higher
            "AGGRESSIVE": 1.5,     # Higher risk
            "URGENT": 1.75,        # Much higher risk
            "IMPOSSIBLE": 2.0      # Max risk (desperation)
        }

        multiplier = urgency_multipliers.get(pacing_status.urgency_level, 1.0)
        adjusted_risk = base_risk * multiplier

        # Cap at 3% per trade (never risk more)
        return min(adjusted_risk, 3.0)
