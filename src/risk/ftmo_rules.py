"""
FTMO Rule Validator
Validates ALL FTMO rules to prevent instant disqualification
"""
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FTMORuleStatus:
    """FTMO rule compliance status"""
    rule_name: str
    is_compliant: bool
    current_value: float
    limit_value: float
    buffer: float  # How much room left before violation
    severity: str  # 'CRITICAL', 'WARNING', 'OK'
    message: str


@dataclass
class FTMOChallengeStatus:
    """Complete FTMO challenge status"""
    phase: int  # 1, 2, or 3 (funded)
    starting_balance: float
    current_balance: float
    profit_pct: float
    max_drawdown_pct: float
    daily_loss_pct: float
    days_elapsed: int
    days_remaining: int
    trading_days_count: int
    is_passing: bool
    rules: List[FTMORuleStatus]
    violations: List[str]


class FTMORuleValidator:
    """
    Validates all FTMO challenge rules
    """

    def __init__(
        self,
        phase: int = 1,
        starting_balance: float = 10000.0,
        challenge_start_date: datetime = None
    ):
        """
        Args:
            phase: 1 (Phase 1), 2 (Phase 2), 3 (Funded)
            starting_balance: Starting account balance
            challenge_start_date: When challenge started
        """
        self.phase = phase
        self.starting_balance = starting_balance
        self.start_date = challenge_start_date or datetime.now()

        # FTMO rules by phase
        self.rules = self._get_phase_rules()

    def _get_phase_rules(self) -> Dict:
        """Get rules for current phase"""
        if self.phase == 1:
            return {
                'profit_target_pct': 10.0,
                'max_daily_loss_pct': 5.0,
                'max_total_loss_pct': 10.0,
                'max_days': 30,
                'min_trading_days': 4,
                'max_daily_profit_pct': None,  # No limit in Phase 1
                'consistency_rule': False
            }
        elif self.phase == 2:
            return {
                'profit_target_pct': 5.0,
                'max_daily_loss_pct': 5.0,
                'max_total_loss_pct': 10.0,
                'max_days': 60,
                'min_trading_days': 4,
                'max_daily_profit_pct': None,  # Checked via consistency rule
                'consistency_rule': True  # Can't make >50% profit in 1 day
            }
        else:  # Funded
            return {
                'profit_target_pct': None,  # No target when funded
                'max_daily_loss_pct': 5.0,
                'max_total_loss_pct': 10.0,
                'max_days': None,
                'min_trading_days': None,
                'max_daily_profit_pct': None,
                'consistency_rule': False
            }

    def validate_all_rules(
        self,
        current_balance: float,
        equity: float,
        daily_pnl_pct: float,
        max_equity_today: float,
        max_equity_ever: float,
        trading_days: List[datetime]
    ) -> FTMOChallengeStatus:
        """
        Validate all FTMO rules

        Args:
            current_balance: Current account balance
            equity: Current equity (balance + floating P&L)
            daily_pnl_pct: Today's P&L as %
            max_equity_today: Highest equity reached today
            max_equity_ever: Highest equity ever reached
            trading_days: List of dates when trades were executed

        Returns:
            Complete challenge status
        """
        rules_status = []
        violations = []

        # Calculate metrics
        profit_pct = ((current_balance - self.starting_balance) / self.starting_balance) * 100
        max_drawdown_pct = ((self.starting_balance - equity) / self.starting_balance) * 100
        days_elapsed = (datetime.now() - self.start_date).days
        days_remaining = self.rules['max_days'] - days_elapsed if self.rules['max_days'] else None
        trading_days_count = len(set([d.date() for d in trading_days]))

        # Rule 1: Profit Target
        if self.rules['profit_target_pct']:
            target = self.rules['profit_target_pct']
            buffer = target - profit_pct
            is_passing = profit_pct >= target

            rules_status.append(FTMORuleStatus(
                rule_name="Profit Target",
                is_compliant=profit_pct >= 0,  # Not violated unless negative
                current_value=profit_pct,
                limit_value=target,
                buffer=buffer,
                severity='CRITICAL' if buffer < 2.0 else 'WARNING' if buffer < 5.0 else 'OK',
                message=f"Need +{buffer:.1f}% more to pass" if not is_passing else "Target reached!"
            ))

        # Rule 2: Daily Loss Limit (CRITICAL)
        daily_loss_limit = self.rules['max_daily_loss_pct']
        daily_buffer = daily_loss_limit - abs(daily_pnl_pct) if daily_pnl_pct < 0 else daily_loss_limit

        # Calculate based on max equity today
        daily_drawdown_from_high = ((max_equity_today - equity) / max_equity_today) * 100 if max_equity_today > 0 else 0

        is_daily_compliant = daily_drawdown_from_high < daily_loss_limit

        rules_status.append(FTMORuleStatus(
            rule_name="Daily Loss Limit",
            is_compliant=is_daily_compliant,
            current_value=daily_drawdown_from_high,
            limit_value=daily_loss_limit,
            buffer=daily_loss_limit - daily_drawdown_from_high,
            severity='CRITICAL' if daily_buffer < 1.0 else 'WARNING' if daily_buffer < 2.0 else 'OK',
            message=f"{daily_buffer:.1f}% buffer remaining today"
        ))

        if not is_daily_compliant:
            violations.append(f"DAILY LOSS LIMIT VIOLATED: {daily_drawdown_from_high:.1f}% > {daily_loss_limit}%")

        # Rule 3: Maximum Drawdown (CRITICAL)
        max_loss_limit = self.rules['max_total_loss_pct']
        max_drawdown_from_high = ((max_equity_ever - equity) / max_equity_ever) * 100 if max_equity_ever > 0 else 0
        drawdown_buffer = max_loss_limit - max_drawdown_from_high

        is_drawdown_compliant = max_drawdown_from_high < max_loss_limit

        rules_status.append(FTMORuleStatus(
            rule_name="Maximum Drawdown",
            is_compliant=is_drawdown_compliant,
            current_value=max_drawdown_from_high,
            limit_value=max_loss_limit,
            buffer=drawdown_buffer,
            severity='CRITICAL' if drawdown_buffer < 2.0 else 'WARNING' if drawdown_buffer < 4.0 else 'OK',
            message=f"{drawdown_buffer:.1f}% buffer remaining overall"
        ))

        if not is_drawdown_compliant:
            violations.append(f"MAX DRAWDOWN VIOLATED: {max_drawdown_from_high:.1f}% > {max_loss_limit}%")

        # Rule 4: Time Limit
        if self.rules['max_days']:
            is_time_compliant = days_elapsed <= self.rules['max_days']

            rules_status.append(FTMORuleStatus(
                rule_name="Time Limit",
                is_compliant=is_time_compliant,
                current_value=days_elapsed,
                limit_value=self.rules['max_days'],
                buffer=days_remaining,
                severity='WARNING' if days_remaining < 5 else 'OK',
                message=f"{days_remaining} days remaining"
            ))

            if not is_time_compliant:
                violations.append(f"TIME LIMIT EXCEEDED: {days_elapsed} > {self.rules['max_days']} days")

        # Rule 5: Minimum Trading Days
        if self.rules['min_trading_days']:
            min_days = self.rules['min_trading_days']
            is_min_days_compliant = trading_days_count >= min_days or days_remaining > (min_days - trading_days_count)

            rules_status.append(FTMORuleStatus(
                rule_name="Minimum Trading Days",
                is_compliant=is_min_days_compliant,
                current_value=trading_days_count,
                limit_value=min_days,
                buffer=trading_days_count - min_days,
                severity='WARNING' if trading_days_count < min_days else 'OK',
                message=f"Need {max(0, min_days - trading_days_count)} more trading days"
            ))

        # Rule 6: Consistency Rule (Phase 2 only)
        if self.rules['consistency_rule']:
            # Check if today's profit is >50% of total profit
            if profit_pct > 0 and daily_pnl_pct > 0:
                daily_pct_of_total = (daily_pnl_pct / profit_pct) * 100 if profit_pct > 0 else 0
                is_consistent = daily_pct_of_total <= 50.0

                rules_status.append(FTMORuleStatus(
                    rule_name="Consistency Rule",
                    is_compliant=is_consistent,
                    current_value=daily_pct_of_total,
                    limit_value=50.0,
                    buffer=50.0 - daily_pct_of_total,
                    severity='CRITICAL' if not is_consistent else 'WARNING' if daily_pct_of_total > 40 else 'OK',
                    message=f"Today's profit is {daily_pct_of_total:.1f}% of total (max 50%)"
                ))

                if not is_consistent:
                    violations.append(f"CONSISTENCY RULE VIOLATED: {daily_pct_of_total:.1f}% > 50%")

        # Determine if passing overall
        is_passing = len(violations) == 0 and \
                    (profit_pct >= self.rules['profit_target_pct'] if self.rules['profit_target_pct'] else True)

        logger.info(f"FTMO Status: Phase {self.phase}, Profit: {profit_pct:.1f}%, "
                   f"Daily: {daily_pnl_pct:.1f}%, Drawdown: {max_drawdown_pct:.1f}%, "
                   f"Days: {days_elapsed}/{self.rules['max_days']}, "
                   f"Violations: {len(violations)}")

        return FTMOChallengeStatus(
            phase=self.phase,
            starting_balance=self.starting_balance,
            current_balance=current_balance,
            profit_pct=profit_pct,
            max_drawdown_pct=max_drawdown_pct,
            daily_loss_pct=daily_pnl_pct,
            days_elapsed=days_elapsed,
            days_remaining=days_remaining if days_remaining else 0,
            trading_days_count=trading_days_count,
            is_passing=is_passing,
            rules=rules_status,
            violations=violations
        )

    def can_trade(
        self,
        current_status: FTMOChallengeStatus,
        proposed_risk_pct: float
    ) -> Tuple[bool, str]:
        """
        Check if a new trade is allowed given current status

        Returns:
            (allowed, reason)
        """
        # Check for violations
        if current_status.violations:
            return False, f"ACCOUNT VIOLATED: {current_status.violations[0]}"

        # Check daily loss proximity
        daily_rule = [r for r in current_status.rules if r.rule_name == "Daily Loss Limit"][0]
        if daily_rule.buffer < proposed_risk_pct:
            return False, f"Trade risk {proposed_risk_pct:.1f}% would exceed daily loss buffer {daily_rule.buffer:.1f}%"

        # Check max drawdown proximity
        dd_rule = [r for r in current_status.rules if r.rule_name == "Maximum Drawdown"][0]
        if dd_rule.buffer < proposed_risk_pct * 2:  # Need 2x buffer
            return False, f"Trade risk {proposed_risk_pct:.1f}% too close to max drawdown limit (buffer: {dd_rule.buffer:.1f}%)"

        # Check consistency rule (Phase 2)
        if self.rules['consistency_rule'] and current_status.daily_loss_pct > 0:
            # Don't take trade if today's profit already high
            if current_status.daily_loss_pct > 2.0 and current_status.profit_pct > 0:
                daily_pct_of_total = (current_status.daily_loss_pct / current_status.profit_pct) * 100
                if daily_pct_of_total > 40:
                    return False, f"Consistency risk: Today's profit already {daily_pct_of_total:.1f}% of total"

        return True, "Trade allowed"

    def should_stop_trading_today(self, current_status: FTMOChallengeStatus) -> Tuple[bool, str]:
        """
        Determine if should stop trading for the day

        Returns:
            (should_stop, reason)
        """
        # Stop if daily loss buffer < 1%
        daily_rule = [r for r in current_status.rules if r.rule_name == "Daily Loss Limit"][0]
        if daily_rule.buffer < 1.0:
            return True, f"Daily loss buffer critical: {daily_rule.buffer:.1f}% remaining"

        # Stop if max drawdown buffer < 2%
        dd_rule = [r for r in current_status.rules if r.rule_name == "Maximum Drawdown"][0]
        if dd_rule.buffer < 2.0:
            return True, f"Max drawdown buffer critical: {dd_rule.buffer:.1f}% remaining"

        # Stop if profit target reached (lock in profits)
        if self.rules['profit_target_pct']:
            if current_status.profit_pct >= self.rules['profit_target_pct']:
                return True, f"Profit target reached: {current_status.profit_pct:.1f}% >= {self.rules['profit_target_pct']}%"

        # Stop if near consistency rule violation (Phase 2)
        if self.rules['consistency_rule'] and current_status.profit_pct > 0:
            if current_status.daily_loss_pct > 0:
                daily_pct_of_total = (current_status.daily_loss_pct / current_status.profit_pct) * 100
                if daily_pct_of_total > 45:
                    return True, f"Consistency risk: Today's profit {daily_pct_of_total:.1f}% of total (limit 50%)"

        return False, "Trading allowed"
