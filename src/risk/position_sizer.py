"""
Position sizing module using Kelly Criterion and other methods
"""
import math
from typing import Dict, Optional
from enum import Enum

from ..config import get_settings
from ..utils.logger import get_logger


logger = get_logger(__name__)


class PositionSizingMethod(str, Enum):
    """Position sizing methods"""
    FIXED_PERCENTAGE = "fixed_percentage"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    RISK_PARITY = "risk_parity"


class PositionSizer:
    """
    Calculate position sizes based on various methods
    Implements Kelly Criterion, volatility adjustment, and fixed percentage
    """

    def __init__(self):
        self.settings = get_settings()
        self.default_risk_pct = self.settings.risk_per_trade_pct

    def calculate_position_size(
        self,
        method: PositionSizingMethod,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        volatility: Optional[float] = None,
        max_position_size: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Calculate position size using specified method

        Args:
            method: Position sizing method to use
            account_balance: Current account balance
            entry_price: Entry price for the trade
            stop_loss_price: Stop loss price
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade size
            avg_loss: Average losing trade size
            volatility: Asset volatility (ATR or standard deviation)
            max_position_size: Maximum position size allowed

        Returns:
            Dictionary with position size details
        """
        risk_amount = account_balance * self.default_risk_pct
        stop_loss_distance = abs(entry_price - stop_loss_price)

        if stop_loss_distance == 0:
            logger.error("Stop loss distance is zero")
            return {
                "shares": 0,
                "position_value": 0,
                "risk_amount": 0,
                "error": "Invalid stop loss"
            }

        if method == PositionSizingMethod.FIXED_PERCENTAGE:
            result = self._fixed_percentage_sizing(
                account_balance, entry_price, stop_loss_price, risk_amount
            )
        elif method == PositionSizingMethod.KELLY_CRITERION:
            result = self._kelly_criterion_sizing(
                account_balance, entry_price, stop_loss_price,
                win_rate, avg_win, avg_loss
            )
        elif method == PositionSizingMethod.VOLATILITY_ADJUSTED:
            result = self._volatility_adjusted_sizing(
                account_balance, entry_price, stop_loss_price,
                volatility, risk_amount
            )
        else:
            logger.warning(f"Unknown sizing method: {method}, using fixed percentage")
            result = self._fixed_percentage_sizing(
                account_balance, entry_price, stop_loss_price, risk_amount
            )

        # Apply maximum position size limit
        if max_position_size and result["position_value"] > max_position_size:
            scaling_factor = max_position_size / result["position_value"]
            result["shares"] = int(result["shares"] * scaling_factor)
            result["position_value"] = result["shares"] * entry_price
            result["adjusted_for_max_size"] = True

        result["method"] = method
        result["account_balance"] = account_balance
        result["position_pct"] = (result["position_value"] / account_balance) * 100

        return result

    def _fixed_percentage_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_amount: float,
    ) -> Dict[str, float]:
        """
        Fixed percentage risk per trade

        Risk a fixed percentage of account on each trade
        """
        stop_loss_distance = abs(entry_price - stop_loss_price)
        shares = int(risk_amount / stop_loss_distance)
        position_value = shares * entry_price

        return {
            "shares": shares,
            "position_value": position_value,
            "risk_amount": risk_amount,
            "stop_loss_distance": stop_loss_distance,
        }

    def _kelly_criterion_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        win_rate: Optional[float],
        avg_win: Optional[float],
        avg_loss: Optional[float],
    ) -> Dict[str, float]:
        """
        Kelly Criterion position sizing

        Formula: f* = (p * b - q) / b
        where:
        - p = probability of win (win_rate)
        - q = probability of loss (1 - win_rate)
        - b = ratio of avg_win to avg_loss

        For trading, we use fractional Kelly (0.25x to 0.5x)
        """
        if not all([win_rate, avg_win, avg_loss]) or avg_loss == 0:
            logger.warning("Kelly Criterion: Missing parameters, using fixed percentage")
            return self._fixed_percentage_sizing(
                account_balance, entry_price, stop_loss_price,
                account_balance * self.default_risk_pct
            )

        # Calculate Kelly percentage
        p = win_rate
        q = 1 - win_rate
        b = avg_win / avg_loss

        kelly_pct = (p * b - q) / b

        # Apply fractional Kelly (conservative: 0.25x)
        fractional_kelly = 0.25
        kelly_pct = max(0, kelly_pct * fractional_kelly)

        # Cap at maximum risk
        kelly_pct = min(kelly_pct, self.default_risk_pct * 2)

        # Calculate position size
        risk_amount = account_balance * kelly_pct
        stop_loss_distance = abs(entry_price - stop_loss_price)
        shares = int(risk_amount / stop_loss_distance)
        position_value = shares * entry_price

        return {
            "shares": shares,
            "position_value": position_value,
            "risk_amount": risk_amount,
            "kelly_percentage": kelly_pct * 100,
            "win_rate": win_rate,
            "risk_reward_ratio": avg_win / avg_loss,
        }

    def _volatility_adjusted_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        volatility: Optional[float],
        base_risk_amount: float,
    ) -> Dict[str, float]:
        """
        Volatility-adjusted position sizing

        Reduce position size in high volatility environments
        Increase position size in low volatility environments
        """
        if volatility is None or volatility == 0:
            logger.warning("Volatility not provided, using fixed percentage")
            return self._fixed_percentage_sizing(
                account_balance, entry_price, stop_loss_price, base_risk_amount
            )

        # Normalize volatility (assuming volatility is ATR)
        volatility_pct = (volatility / entry_price) * 100

        # Base volatility assumption (adjust based on asset class)
        base_volatility = 1.0

        # Volatility adjustment factor
        volatility_factor = base_volatility / volatility_pct
        volatility_factor = max(0.5, min(2.0, volatility_factor))  # Cap between 0.5x and 2x

        # Adjust risk amount
        adjusted_risk_amount = base_risk_amount * volatility_factor

        # Calculate position size
        stop_loss_distance = abs(entry_price - stop_loss_price)
        shares = int(adjusted_risk_amount / stop_loss_distance)
        position_value = shares * entry_price

        return {
            "shares": shares,
            "position_value": position_value,
            "risk_amount": adjusted_risk_amount,
            "volatility": volatility,
            "volatility_pct": volatility_pct,
            "volatility_factor": volatility_factor,
        }

    def calculate_multi_position_sizing(
        self,
        positions: list[Dict],
        account_balance: float,
        correlation_matrix: Optional[Dict] = None,
    ) -> Dict[str, float]:
        """
        Calculate position sizing for multiple correlated positions

        Reduce overall exposure when positions are highly correlated
        """
        total_position_value = sum(p["position_value"] for p in positions)
        total_risk = sum(p["risk_amount"] for p in positions)

        # Calculate correlation adjustment
        correlation_adjustment = 1.0
        if correlation_matrix:
            # Average correlation between positions
            avg_correlation = self._calculate_average_correlation(
                positions, correlation_matrix
            )
            # Reduce exposure for highly correlated positions
            correlation_adjustment = 1.0 - (avg_correlation * 0.5)

        # Adjust position sizes
        adjusted_positions = []
        for position in positions:
            adjusted_position = position.copy()
            adjusted_position["shares"] = int(
                position["shares"] * correlation_adjustment
            )
            adjusted_position["position_value"] = (
                adjusted_position["shares"] * position["entry_price"]
            )
            adjusted_positions.append(adjusted_position)

        return {
            "positions": adjusted_positions,
            "total_position_value": total_position_value * correlation_adjustment,
            "total_risk": total_risk * correlation_adjustment,
            "correlation_adjustment": correlation_adjustment,
            "portfolio_leverage": (total_position_value / account_balance),
        }

    def _calculate_average_correlation(
        self,
        positions: list[Dict],
        correlation_matrix: Dict,
    ) -> float:
        """Calculate average correlation between positions"""
        if len(positions) < 2:
            return 0.0

        correlations = []
        for i, pos1 in enumerate(positions):
            for pos2 in positions[i + 1:]:
                symbol1 = pos1.get("symbol")
                symbol2 = pos2.get("symbol")
                if symbol1 and symbol2:
                    corr = correlation_matrix.get(f"{symbol1}_{symbol2}", 0.0)
                    correlations.append(abs(corr))

        return sum(correlations) / len(correlations) if correlations else 0.0

    def validate_position_size(
        self,
        position_size: float,
        account_balance: float,
        max_position_pct: float = 0.25,
    ) -> tuple[bool, str]:
        """
        Validate that position size is within acceptable limits

        Args:
            position_size: Position size in dollars
            account_balance: Current account balance
            max_position_pct: Maximum position size as percentage of account

        Returns:
            Tuple of (is_valid, message)
        """
        position_pct = (position_size / account_balance) * 100

        if position_size <= 0:
            return False, "Position size must be positive"

        if position_size > account_balance:
            return False, f"Position size (${position_size:,.2f}) exceeds account balance"

        if position_pct > max_position_pct * 100:
            return False, f"Position size ({position_pct:.1f}%) exceeds maximum allowed ({max_position_pct * 100:.1f}%)"

        return True, "Position size valid"
