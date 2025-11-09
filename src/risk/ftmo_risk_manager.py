"""
FTMO Professional Risk Manager
===============================
Institutional-grade risk management for FTMO prop trading.

Features:
1. Auto lot sizing (based on account equity, ATR, stop loss)
2. FTMO rule enforcement (5% daily loss, 10% total DD)
3. Scale entry/exit (professional position building)
4. Profit-based exits (target $ amount for FTMO)
5. Dynamic position sizing based on market conditions
6. Real-time risk monitoring

Used by: Production API for all trade signals
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class FTMOAccount:
    """FTMO account state."""
    balance: float
    equity: float
    daily_start_balance: float
    peak_balance: float
    phase: str  # "challenge_1", "challenge_2", "live"

    # FTMO limits
    max_daily_loss: float = 5000.0  # $5K
    max_total_drawdown: float = 10000.0  # $10K

    # Profit targets
    challenge_1_target: float = 10000.0  # $10K (10%)
    challenge_2_target: float = 5000.0   # $5K (5%)

    @property
    def daily_pnl(self) -> float:
        """Current daily P&L."""
        return self.equity - self.daily_start_balance

    @property
    def daily_loss(self) -> float:
        """Current daily loss (positive number)."""
        return abs(min(0, self.daily_pnl))

    @property
    def total_drawdown(self) -> float:
        """Total drawdown from peak (positive number)."""
        return abs(min(0, self.equity - self.peak_balance))

    @property
    def distance_to_daily_limit(self) -> float:
        """How much $ left before hitting daily loss limit."""
        return self.max_daily_loss - self.daily_loss

    @property
    def distance_to_dd_limit(self) -> float:
        """How much $ left before hitting total DD limit."""
        return self.max_total_drawdown - self.total_drawdown

    @property
    def total_profit(self) -> float:
        """Total profit from starting balance."""
        return self.equity - 100000.0  # Assuming $100K start

    @property
    def profit_target(self) -> float:
        """Current profit target based on phase."""
        if self.phase == "challenge_1":
            return self.challenge_1_target
        elif self.phase == "challenge_2":
            return self.challenge_2_target
        return 0.0  # Live has no target, just make money

    @property
    def progress_to_target(self) -> float:
        """Progress to profit target (0.0 to 1.0+)."""
        if self.profit_target == 0:
            return 1.0
        return self.total_profit / self.profit_target

    def is_ftmo_violated(self) -> bool:
        """Check if FTMO rules violated."""
        return (self.daily_loss >= self.max_daily_loss or
                self.total_drawdown >= self.max_total_drawdown)

    def can_trade(self) -> bool:
        """Check if we can still trade (not violated)."""
        return not self.is_ftmo_violated()


@dataclass
class Position:
    """Open position."""
    ticket: int
    symbol: str
    type: str  # "BUY" or "SELL"
    lots: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    unrealized_pnl: float = 0.0

    @property
    def is_long(self) -> bool:
        return self.type == "BUY"

    @property
    def is_short(self) -> bool:
        return self.type == "SELL"

    def update_pnl(self, current_price: float, point_value: float = 1.0):
        """Update unrealized P&L."""
        if self.is_long:
            self.unrealized_pnl = (current_price - self.entry_price) * self.lots * point_value
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.lots * point_value


class FTMORiskManager:
    """
    Professional-grade FTMO risk manager.

    Handles:
    - Position sizing (auto lot calculation)
    - FTMO rule enforcement
    - Scale entry/exit
    - Profit-based exits
    - Risk monitoring
    """

    def __init__(
        self,
        account: FTMOAccount,
        max_risk_per_trade: float = 0.02,  # 2% of account
        max_daily_risk: float = 0.04,  # 4% max daily risk
        profit_target_exit_ratio: float = 0.8,  # Close 80% of position at target
        scale_entry_enabled: bool = True,
        scale_exit_enabled: bool = True,
    ):
        self.account = account
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_risk = max_daily_risk
        self.profit_target_exit_ratio = profit_target_exit_ratio
        self.scale_entry_enabled = scale_entry_enabled
        self.scale_exit_enabled = scale_exit_enabled

        # Position tracking
        self.positions: List[Position] = []
        self.total_exposure = 0.0

        # Daily tracking
        self.trades_today = 0
        self.max_trades_per_day = 20

    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        atr: float,
        broker_min_lot: float = 0.01,
        broker_max_lot: float = 100.0,
        broker_lot_step: float = 0.01,
        point_value: float = 1.0,  # US30: 1 point = $1 per lot
    ) -> Dict:
        """
        Calculate optimal position size based on risk parameters.

        Professional lot sizing formula:
        1. Calculate $ risk per lot based on stop distance
        2. Calculate max $ risk allowed (2% of equity)
        3. Divide max risk by risk per lot
        4. Apply FTMO safety adjustments
        5. Round to broker lot step

        Args:
            symbol: Symbol name
            entry_price: Entry price
            stop_loss: Stop loss price
            atr: Current ATR
            broker_min_lot: Broker minimum lot size
            broker_max_lot: Broker maximum lot size
            broker_lot_step: Broker lot step size
            point_value: $ value per point per lot

        Returns:
            Dict with {
                'lots': Recommended lot size,
                'risk_dollars': Risk in $,
                'risk_percent': Risk as % of equity,
                'reason': Explanation,
                'safety_factor': Applied safety multiplier
            }
        """

        # 1. Calculate stop distance in points
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance <= 0:
            return {
                'lots': 0.0,
                'risk_dollars': 0.0,
                'risk_percent': 0.0,
                'reason': "Invalid stop loss (distance <= 0)",
                'safety_factor': 0.0,
            }

        # 2. Calculate $ risk per lot
        risk_per_lot = stop_distance * point_value

        if risk_per_lot <= 0:
            return {
                'lots': 0.0,
                'risk_dollars': 0.0,
                'risk_percent': 0.0,
                'reason': "Invalid risk calculation",
                'safety_factor': 0.0,
            }

        # 3. Calculate max $ risk allowed
        max_risk_dollars = self.account.equity * self.max_risk_per_trade

        # FTMO Safety Adjustment #1: Distance to daily limit
        # If we're close to daily limit, reduce risk
        distance_to_daily = self.account.distance_to_daily_limit
        if distance_to_daily < 2000:  # <$2K left
            safety_factor_daily = max(0.1, distance_to_daily / 2000)  # 10-100%
            max_risk_dollars *= safety_factor_daily
            logger.warning(f"FTMO: Near daily limit, reducing risk by {(1-safety_factor_daily)*100:.1f}%")

        # FTMO Safety Adjustment #2: Distance to DD limit
        distance_to_dd = self.account.distance_to_dd_limit
        if distance_to_dd < 4000:  # <$4K left
            safety_factor_dd = max(0.1, distance_to_dd / 4000)  # 10-100%
            max_risk_dollars *= safety_factor_dd
            logger.warning(f"FTMO: Near DD limit, reducing risk by {(1-safety_factor_dd)*100:.1f}%")

        # FTMO Safety Adjustment #3: Already losing today
        if self.account.daily_pnl < 0:
            daily_loss_factor = max(0.5, 1.0 - abs(self.account.daily_pnl) / 1000)  # Reduce if losing
            max_risk_dollars *= daily_loss_factor

        # 4. Calculate lot size
        ideal_lots = max_risk_dollars / risk_per_lot

        # 5. Apply broker constraints
        lots = max(broker_min_lot, min(ideal_lots, broker_max_lot))

        # 6. Round to broker lot step
        lots = round(lots / broker_lot_step) * broker_lot_step

        # 7. Final safety check: Don't risk more than remaining daily limit
        actual_risk = lots * risk_per_lot
        if actual_risk > distance_to_daily * 0.8:  # Don't risk more than 80% of remaining
            lots = (distance_to_daily * 0.8) / risk_per_lot
            lots = round(lots / broker_lot_step) * broker_lot_step
            lots = max(broker_min_lot, lots)

        # 8. Calculate final metrics
        final_risk_dollars = lots * risk_per_lot
        final_risk_percent = (final_risk_dollars / self.account.equity) * 100

        safety_factor = lots / ideal_lots if ideal_lots > 0 else 0.0

        return {
            'lots': lots,
            'risk_dollars': final_risk_dollars,
            'risk_percent': final_risk_percent,
            'reason': f"2% risk adjusted for FTMO limits",
            'safety_factor': safety_factor,
            'stop_distance_points': stop_distance,
            'risk_per_lot': risk_per_lot,
            'ideal_lots': ideal_lots,
        }

    def calculate_scale_entry(
        self,
        base_lots: float,
        num_entries: int = 3,
        scale_factor: float = 0.6,
    ) -> List[Dict]:
        """
        Calculate scale entry plan.

        Professional approach:
        - Entry 1: 60% of position (base × 0.6)
        - Entry 2: 30% of position (base × 0.3)
        - Entry 3: 10% of position (base × 0.1)

        Args:
            base_lots: Base position size
            num_entries: Number of entries (default: 3)
            scale_factor: How much to scale down (default: 0.6)

        Returns:
            List of entry sizes
        """
        if not self.scale_entry_enabled:
            return [{'entry': 1, 'lots': base_lots, 'percent': 100}]

        # Professional scaling: 60/30/10
        if num_entries == 3:
            return [
                {'entry': 1, 'lots': base_lots * 0.6, 'percent': 60},
                {'entry': 2, 'lots': base_lots * 0.3, 'percent': 30},
                {'entry': 3, 'lots': base_lots * 0.1, 'percent': 10},
            ]

        # Alternative: 50/30/20
        elif num_entries == 3:
            return [
                {'entry': 1, 'lots': base_lots * 0.5, 'percent': 50},
                {'entry': 2, 'lots': base_lots * 0.3, 'percent': 30},
                {'entry': 3, 'lots': base_lots * 0.2, 'percent': 20},
            ]

        # Fallback: Equal distribution
        lot_per_entry = base_lots / num_entries
        return [
            {'entry': i+1, 'lots': lot_per_entry, 'percent': 100/num_entries}
            for i in range(num_entries)
        ]

    def calculate_scale_exit(
        self,
        position_lots: float,
        current_pnl_dollars: float,
        target_pnl_dollars: float,
    ) -> Optional[Dict]:
        """
        Calculate scale exit based on profit targets.

        Professional exit strategy:
        - At 50% of target: Close 30% of position
        - At 80% of target: Close 40% of position
        - At 100% of target: Close remaining 30%

        Args:
            position_lots: Current position size
            current_pnl_dollars: Current P&L in $
            target_pnl_dollars: Target P&L in $

        Returns:
            Dict with exit recommendation or None
        """
        if not self.scale_exit_enabled:
            return None

        if target_pnl_dollars <= 0:
            return None

        progress = current_pnl_dollars / target_pnl_dollars

        # Scale exit levels
        if progress >= 1.0:  # 100% of target
            return {
                'close_percent': 30,
                'close_lots': position_lots * 0.3,
                'reason': '100% profit target reached',
                'remaining_lots': position_lots * 0.7,
            }
        elif progress >= 0.8:  # 80% of target
            return {
                'close_percent': 40,
                'close_lots': position_lots * 0.4,
                'reason': '80% profit target reached',
                'remaining_lots': position_lots * 0.6,
            }
        elif progress >= 0.5:  # 50% of target
            return {
                'close_percent': 30,
                'close_lots': position_lots * 0.3,
                'reason': '50% profit target reached',
                'remaining_lots': position_lots * 0.7,
            }

        return None

    def should_close_for_profit_target(
        self,
        current_total_pnl: float,
    ) -> Dict:
        """
        Check if we should close positions based on FTMO profit target.

        FTMO Challenge Strategy:
        - Challenge 1: Target $10K, close 80% at $8K, close 100% at $10K
        - Challenge 2: Target $5K, close 80% at $4K, close 100% at $5K
        - Live: No target, just manage risk

        Args:
            current_total_pnl: Current total P&L (all positions)

        Returns:
            Dict with recommendation
        """
        if self.account.phase == "live":
            return {
                'should_close': False,
                'close_percent': 0,
                'reason': 'Live account - no profit target'
            }

        profit_target = self.account.profit_target
        total_profit = self.account.total_profit

        # Calculate progress including unrealized P&L
        projected_profit = total_profit + current_total_pnl
        progress = projected_profit / profit_target if profit_target > 0 else 0

        # Close 80% at 80% of target (lock in profits)
        if progress >= 0.8 and progress < 1.0:
            return {
                'should_close': True,
                'close_percent': 80,
                'reason': f'80% of {self.account.phase} target (${profit_target:,.0f}) reached',
                'current_profit': projected_profit,
                'target_profit': profit_target,
                'progress': progress,
            }

        # Close 100% at 100% of target (target achieved!)
        elif progress >= 1.0:
            return {
                'should_close': True,
                'close_percent': 100,
                'reason': f'{self.account.phase} target (${profit_target:,.0f}) ACHIEVED!',
                'current_profit': projected_profit,
                'target_profit': profit_target,
                'progress': progress,
            }

        return {
            'should_close': False,
            'close_percent': 0,
            'reason': f'Progress: {progress*100:.1f}% of target',
            'current_profit': projected_profit,
            'target_profit': profit_target,
            'progress': progress,
        }

    def can_open_new_position(self) -> Tuple[bool, str]:
        """
        Check if we can open a new position.

        Returns:
            (can_trade, reason)
        """
        # Check FTMO violations
        if self.account.is_ftmo_violated():
            return False, "FTMO rules violated - account locked"

        # Check if too close to daily limit
        if self.account.distance_to_daily_limit < 500:  # <$500 left
            return False, f"Too close to daily loss limit (${self.account.distance_to_daily_limit:.2f} remaining)"

        # Check if too close to DD limit
        if self.account.distance_to_dd_limit < 1000:  # <$1K left
            return False, f"Too close to total DD limit (${self.account.distance_to_dd_limit:.2f} remaining)"

        # Check max trades per day
        if self.trades_today >= self.max_trades_per_day:
            return False, f"Max trades per day reached ({self.max_trades_per_day})"

        # Check total exposure
        if len(self.positions) >= 3:  # Max 3 concurrent positions
            return False, "Max concurrent positions reached (3)"

        return True, "OK to trade"

    def add_position(self, position: Position):
        """Add position to tracker."""
        self.positions.append(position)
        self.trades_today += 1
        self.total_exposure += position.lots
        logger.info(f"Position added: {position.symbol} {position.type} {position.lots} lots")

    def remove_position(self, ticket: int):
        """Remove closed position."""
        self.positions = [p for p in self.positions if p.ticket != ticket]
        self.total_exposure = sum(p.lots for p in self.positions)

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L from all positions."""
        return sum(p.unrealized_pnl for p in self.positions)

    def get_risk_status(self) -> Dict:
        """
        Get comprehensive risk status.

        Returns:
            Dict with all risk metrics
        """
        total_unrealized = self.get_total_unrealized_pnl()

        return {
            'account_balance': self.account.balance,
            'account_equity': self.account.equity,
            'daily_pnl': self.account.daily_pnl,
            'daily_loss': self.account.daily_loss,
            'total_drawdown': self.account.total_drawdown,
            'distance_to_daily_limit': self.account.distance_to_daily_limit,
            'distance_to_dd_limit': self.account.distance_to_dd_limit,
            'total_profit': self.account.total_profit,
            'profit_target': self.account.profit_target,
            'progress_to_target': self.account.progress_to_target,
            'open_positions': len(self.positions),
            'total_exposure_lots': self.total_exposure,
            'total_unrealized_pnl': total_unrealized,
            'trades_today': self.trades_today,
            'can_trade': self.account.can_trade(),
            'ftmo_violated': self.account.is_ftmo_violated(),
            'phase': self.account.phase,
        }


if __name__ == "__main__":
    """Test the risk manager."""

    print("Testing FTMO Risk Manager...")
    print("="*70)

    # Create FTMO account (Challenge Phase 1)
    account = FTMOAccount(
        balance=100000.0,
        equity=101500.0,  # Up $1.5K
        daily_start_balance=100000.0,
        peak_balance=102000.0,
        phase="challenge_1",
    )

    # Create risk manager
    rm = FTMORiskManager(account)

    # Test 1: Position sizing
    print("\n1. Position Sizing Test:")
    print("-" * 70)

    entry_price = 50000.0
    stop_loss = 49900.0  # 100 points
    atr = 120.0

    size = rm.calculate_position_size(
        symbol="US30",
        entry_price=entry_price,
        stop_loss=stop_loss,
        atr=atr,
        broker_min_lot=1.0,
        broker_max_lot=100.0,
        broker_lot_step=1.0,
    )

    print(f"Entry: ${entry_price:,.0f}")
    print(f"Stop Loss: ${stop_loss:,.0f}")
    print(f"Stop Distance: {size['stop_distance_points']:.0f} points")
    print(f"Risk per lot: ${size['risk_per_lot']:.2f}")
    print(f"Ideal lots: {size['ideal_lots']:.2f}")
    print(f"Recommended lots: {size['lots']:.2f}")
    print(f"Risk: ${size['risk_dollars']:.2f} ({size['risk_percent']:.2f}%)")
    print(f"Safety factor: {size['safety_factor']:.2%}")

    # Test 2: Scale entry
    print("\n2. Scale Entry Test:")
    print("-" * 70)

    scale_plan = rm.calculate_scale_entry(base_lots=10.0, num_entries=3)
    for entry in scale_plan:
        print(f"Entry {entry['entry']}: {entry['lots']:.2f} lots ({entry['percent']:.0f}%)")

    # Test 3: Profit target check
    print("\n3. Profit Target Check:")
    print("-" * 70)

    # Simulate profit scenarios
    for unrealized_pnl in [0, 4000, 6000, 8000, 10000]:
        check = rm.should_close_for_profit_target(unrealized_pnl)
        print(f"Unrealized P&L: ${unrealized_pnl:,.0f}")
        print(f"  Should close: {check['should_close']}")
        print(f"  Close %: {check['close_percent']}%")
        print(f"  Reason: {check['reason']}")
        print(f"  Progress: {check['progress']*100:.1f}%")
        print()

    # Test 4: Risk status
    print("4. Risk Status:")
    print("-" * 70)

    status = rm.get_risk_status()
    for key, value in status.items():
        if isinstance(value, float):
            print(f"{key}: {value:,.2f}")
        else:
            print(f"{key}: {value}")

    print("\n" + "="*70)
    print("✅ Risk Manager tests passed!")
