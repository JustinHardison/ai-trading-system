"""
Prop firm rules compliance engine
Enforces FTMO, TopStep, and other prop firm trading rules
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import asyncio

from ..config import get_settings, PROP_FIRM_RULES
from ..utils.logger import get_logger


logger = get_logger(__name__)


class ComplianceStatus(str, Enum):
    """Compliance check status"""
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


class PropFirmCompliance:
    """
    Enforce prop firm trading rules
    Validates trades before execution and monitors ongoing compliance
    """

    def __init__(self, prop_firm: str, account_size: float, account_type: str):
        self.settings = get_settings()
        self.prop_firm = prop_firm
        self.account_size = account_size
        self.account_type = account_type
        self.rules = PROP_FIRM_RULES.get(prop_firm, {})

        # Trading state
        self.starting_balance = account_size
        self.current_balance = account_size
        self.daily_starting_balance = account_size
        self.peak_balance = account_size
        self.trades_today = []
        self.total_trades = []
        self.trading_days = set()
        self.daily_pnl = {}

        logger.info(f"Initialized {prop_firm} compliance for ${account_size:,.2f} {account_type} account")

    async def validate_trade(
        self,
        trade: Dict,
        current_positions: List[Dict],
    ) -> Tuple[ComplianceStatus, str]:
        """
        Validate if a trade complies with prop firm rules

        Args:
            trade: Trade details (symbol, size, direction, entry_price, stop_loss, etc.)
            current_positions: List of current open positions

        Returns:
            Tuple of (status, message)
        """
        # Run all compliance checks
        checks = [
            self._check_daily_loss_limit(trade),
            self._check_overall_loss_limit(trade),
            self._check_position_size_limit(trade),
            self._check_max_simultaneous_positions(trade, current_positions),
            self._check_trading_hours(trade),
            self._check_consistency_rules(trade),
            self._check_forbidden_strategies(trade),
        ]

        # Execute checks concurrently
        results = await asyncio.gather(*checks)

        # Analyze results
        for status, message in results:
            if status == ComplianceStatus.REJECTED:
                logger.warning(f"Trade rejected: {message}")
                return status, message

        # Check for warnings
        warnings = [msg for status, msg in results if status == ComplianceStatus.WARNING]
        if warnings:
            warning_msg = "; ".join(warnings)
            logger.info(f"Trade approved with warnings: {warning_msg}")
            return ComplianceStatus.WARNING, warning_msg

        logger.info("Trade approved - all compliance checks passed")
        return ComplianceStatus.APPROVED, "All compliance checks passed"

    async def _check_daily_loss_limit(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check daily loss limit"""
        if self.prop_firm == "FTMO":
            max_daily_loss_pct = self.rules.get("max_daily_loss_pct", 0.05)
            max_daily_loss = self.starting_balance * max_daily_loss_pct

            # Calculate current daily loss
            daily_loss = self.daily_starting_balance - self.current_balance

            # Estimate potential loss from this trade
            potential_loss = trade.get("risk_amount", 0)
            total_potential_loss = daily_loss + potential_loss

            if total_potential_loss > max_daily_loss:
                return (
                    ComplianceStatus.REJECTED,
                    f"Daily loss limit exceeded: ${total_potential_loss:,.2f} > ${max_daily_loss:,.2f}"
                )

            # Warning if approaching limit (80%)
            if total_potential_loss > max_daily_loss * 0.8:
                return (
                    ComplianceStatus.WARNING,
                    f"Approaching daily loss limit: ${total_potential_loss:,.2f} / ${max_daily_loss:,.2f}"
                )

        elif self.prop_firm == "TopStep":
            max_daily_loss = self.rules["max_daily_loss"].get(int(self.account_size), 2000)
            daily_loss = self.daily_starting_balance - self.current_balance
            potential_loss = trade.get("risk_amount", 0)
            total_potential_loss = daily_loss + potential_loss

            if total_potential_loss > max_daily_loss:
                return (
                    ComplianceStatus.REJECTED,
                    f"Daily loss limit exceeded: ${total_potential_loss:,.2f} > ${max_daily_loss:,.2f}"
                )

        return ComplianceStatus.APPROVED, "Daily loss limit OK"

    async def _check_overall_loss_limit(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check maximum overall loss limit (trailing drawdown)"""
        if self.prop_firm in ["FTMO", "FundedNext"]:
            max_overall_loss_pct = self.rules.get("max_overall_loss_pct", 0.10)
            max_overall_loss = self.starting_balance * max_overall_loss_pct

            # Calculate current overall loss from peak
            current_drawdown = self.peak_balance - self.current_balance

            # Estimate potential loss
            potential_loss = trade.get("risk_amount", 0)
            total_potential_drawdown = current_drawdown + potential_loss

            if total_potential_drawdown > max_overall_loss:
                return (
                    ComplianceStatus.REJECTED,
                    f"Overall loss limit exceeded: ${total_potential_drawdown:,.2f} > ${max_overall_loss:,.2f}"
                )

            # Warning if approaching limit (80%)
            if total_potential_drawdown > max_overall_loss * 0.8:
                return (
                    ComplianceStatus.WARNING,
                    f"Approaching overall loss limit: ${total_potential_drawdown:,.2f} / ${max_overall_loss:,.2f}"
                )

        return ComplianceStatus.APPROVED, "Overall loss limit OK"

    async def _check_position_size_limit(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check maximum position size"""
        if self.prop_firm == "TopStep":
            max_contracts = self.rules["max_contracts"].get(int(self.account_size), 10)
            trade_size = trade.get("size", 0)

            if trade_size > max_contracts:
                return (
                    ComplianceStatus.REJECTED,
                    f"Position size {trade_size} exceeds max contracts {max_contracts}"
                )

        # General position size check (max 25% of account)
        position_value = trade.get("position_value", 0)
        max_position_pct = 0.25
        max_position_value = self.current_balance * max_position_pct

        if position_value > max_position_value:
            return (
                ComplianceStatus.REJECTED,
                f"Position value ${position_value:,.2f} exceeds {max_position_pct * 100:.0f}% of account"
            )

        return ComplianceStatus.APPROVED, "Position size OK"

    async def _check_max_simultaneous_positions(
        self,
        trade: Dict,
        current_positions: List[Dict]
    ) -> Tuple[ComplianceStatus, str]:
        """Check maximum number of simultaneous positions"""
        if self.prop_firm == "FTMO":
            max_positions = self.rules.get("max_simultaneous_orders", 200)
            current_count = len(current_positions)

            if current_count >= max_positions:
                return (
                    ComplianceStatus.REJECTED,
                    f"Maximum simultaneous positions ({max_positions}) reached"
                )

        return ComplianceStatus.APPROVED, "Position count OK"

    async def _check_trading_hours(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if trading is allowed at current time"""
        trading_hours = self.rules.get("trading_hours", "24/5")
        current_time = datetime.now()

        # Check weekend trading
        if trading_hours == "24/5":
            allow_weekend = self.rules.get("allow_weekend_trading", False)
            if not allow_weekend and current_time.weekday() >= 5:
                return (
                    ComplianceStatus.REJECTED,
                    "Weekend trading not allowed"
                )

        # Check if during futures market hours (TopStep)
        if trading_hours == "futures_market_hours":
            # Simplified check - would need more sophisticated logic
            hour = current_time.hour
            if hour < 6 or hour > 17:  # Outside typical futures hours
                return (
                    ComplianceStatus.WARNING,
                    "Trading outside typical market hours"
                )

        return ComplianceStatus.APPROVED, "Trading hours OK"

    async def _check_consistency_rules(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check consistency rules (TopStep requirement)"""
        if self.prop_firm == "TopStep" and self.rules.get("consistency_rule"):
            # Check if single day profits exceed 50% of total
            if len(self.daily_pnl) > 0:
                total_pnl = sum(self.daily_pnl.values())
                if total_pnl > 0:
                    max_daily_pnl = max(self.daily_pnl.values())
                    max_single_day_pct = self.rules.get("max_single_day_profit_pct", 0.50)

                    if max_daily_pnl > total_pnl * max_single_day_pct:
                        return (
                            ComplianceStatus.WARNING,
                            f"Single day profits ({max_daily_pnl / total_pnl * 100:.1f}%) "
                            f"exceed {max_single_day_pct * 100:.0f}% of total"
                        )

        return ComplianceStatus.APPROVED, "Consistency rules OK"

    async def _check_forbidden_strategies(self, trade: Dict) -> Tuple[ComplianceStatus, str]:
        """Check if trade uses forbidden strategies"""
        forbidden = self.rules.get("forbidden_strategies", [])

        # Check for martingale (doubling position size after loss)
        if "martingale" in forbidden:
            if len(self.trades_today) > 0:
                last_trade = self.trades_today[-1]
                if last_trade.get("pnl", 0) < 0:
                    if trade.get("size", 0) > last_trade.get("size", 0) * 1.8:
                        return (
                            ComplianceStatus.REJECTED,
                            "Potential martingale strategy detected"
                        )

        # Check for grid trading (multiple positions at different levels)
        if "grid_trading" in forbidden:
            symbol = trade.get("symbol")
            same_symbol_positions = [p for p in self.trades_today if p.get("symbol") == symbol]
            if len(same_symbol_positions) > 3:
                return (
                    ComplianceStatus.WARNING,
                    "Multiple positions on same symbol may indicate grid trading"
                )

        # TopStep: Check for automated trading
        if self.prop_firm == "TopStep" and not self.rules.get("automated_trading_allowed", False):
            # In practice, this would need to be manually confirmed
            # For now, we'll log a warning
            pass

        return ComplianceStatus.APPROVED, "Strategy compliance OK"

    def update_account_balance(self, new_balance: float):
        """Update account balance after trade execution"""
        self.current_balance = new_balance
        self.peak_balance = max(self.peak_balance, new_balance)

        # Reset daily starting balance if new day
        current_date = datetime.now().date()
        if current_date not in self.trading_days:
            self.daily_starting_balance = self.current_balance
            self.trading_days.add(current_date)
            self.trades_today = []

    def record_trade(self, trade: Dict):
        """Record a trade for compliance tracking"""
        trade_date = datetime.now().date()
        trade_with_date = {**trade, "date": trade_date}

        self.trades_today.append(trade_with_date)
        self.total_trades.append(trade_with_date)

        # Update daily P&L
        pnl = trade.get("pnl", 0)
        if trade_date not in self.daily_pnl:
            self.daily_pnl[trade_date] = 0
        self.daily_pnl[trade_date] += pnl

    def get_compliance_status(self) -> Dict:
        """Get current compliance status and metrics"""
        current_drawdown = self.peak_balance - self.current_balance
        daily_loss = self.daily_starting_balance - self.current_balance
        total_pnl = self.current_balance - self.starting_balance

        if self.prop_firm == "FTMO":
            max_overall_loss = self.starting_balance * self.rules.get("max_overall_loss_pct", 0.10)
            max_daily_loss = self.starting_balance * self.rules.get("max_daily_loss_pct", 0.05)
            profit_target_pct = (
                self.rules.get("profit_target_challenge_pct")
                if self.account_type == "challenge"
                else self.rules.get("profit_target_verification_pct")
            )
            profit_target = self.starting_balance * profit_target_pct

        elif self.prop_firm == "TopStep":
            max_daily_loss = self.rules["max_daily_loss"].get(int(self.account_size), 2000)
            profit_target = self.rules["profit_target"].get(int(self.account_size), 3000)
            max_overall_loss = max_daily_loss * 2  # Estimate

        else:
            max_overall_loss = self.starting_balance * 0.10
            max_daily_loss = self.starting_balance * 0.05
            profit_target = self.starting_balance * 0.10

        return {
            "prop_firm": self.prop_firm,
            "account_type": self.account_type,
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "peak_balance": self.peak_balance,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / self.starting_balance) * 100,
            "daily_pnl": daily_loss * -1,
            "current_drawdown": current_drawdown,
            "max_overall_loss": max_overall_loss,
            "max_daily_loss": max_daily_loss,
            "overall_loss_used_pct": (current_drawdown / max_overall_loss) * 100,
            "daily_loss_used_pct": (daily_loss / max_daily_loss) * 100,
            "profit_target": profit_target,
            "profit_target_achieved_pct": (total_pnl / profit_target) * 100,
            "trading_days": len(self.trading_days),
            "total_trades": len(self.total_trades),
            "trades_today": len(self.trades_today),
            "can_trade": current_drawdown < max_overall_loss and daily_loss < max_daily_loss,
        }
