"""
Paper trading broker - simulated trading for testing
Uses real market data but simulated execution
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

from ..utils.logger import get_logger


logger = get_logger(__name__)


class Position:
    """Represents an open trading position"""

    def __init__(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        position_type: str,
        entry_time: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ):
        self.symbol = symbol
        self.entry_price = entry_price
        self.size = size  # Number of shares
        self.position_type = position_type  # "LONG" or "SHORT"
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def get_current_pnl(self, current_price: float) -> float:
        """Calculate current P&L"""
        if self.position_type == "LONG":
            return (current_price - self.entry_price) * self.size
        else:  # SHORT
            return (self.entry_price - current_price) * self.size

    def get_pnl_pct(self, current_price: float) -> float:
        """Calculate P&L percentage"""
        position_value = self.entry_price * self.size
        pnl = self.get_current_pnl(current_price)
        return (pnl / position_value) * 100 if position_value > 0 else 0

    def should_close(self, current_price: float) -> tuple[bool, str]:
        """Check if position should be closed based on stop/target"""
        if self.stop_loss and self.position_type == "LONG" and current_price <= self.stop_loss:
            return True, "stop_loss"
        if self.stop_loss and self.position_type == "SHORT" and current_price >= self.stop_loss:
            return True, "stop_loss"
        if self.take_profit and self.position_type == "LONG" and current_price >= self.take_profit:
            return True, "take_profit"
        if self.take_profit and self.position_type == "SHORT" and current_price <= self.take_profit:
            return True, "take_profit"
        return False, ""


class PaperBroker:
    """
    Paper trading broker with simulated execution
    Uses real market data from yfinance
    """

    def __init__(self, initial_balance: float = 100000):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict] = []
        self.daily_starting_balance = initial_balance
        self.peak_balance = initial_balance

        logger.info(f"Initialized Paper Broker with ${initial_balance:,.2f}")

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            # Get last 1 day of data
            hist = ticker.history(period="1d", interval="1m")

            if hist.empty:
                logger.warning(f"No data available for {symbol}")
                return None

            current_price = float(hist['Close'].iloc[-1])
            logger.debug(f"{symbol} current price: ${current_price:.2f}")
            return current_price

        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "5d",
        interval: str = "1h",
    ) -> Optional[pd.DataFrame]:
        """Get historical data for technical analysis"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                logger.warning(f"No historical data for {symbol}")
                return None

            # Rename columns to lowercase for consistency
            hist.columns = [col.lower() for col in hist.columns]

            logger.debug(f"Retrieved {len(hist)} bars for {symbol}")
            return hist

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None

    def open_position(
        self,
        symbol: str,
        entry_price: float,
        size: float,
        position_type: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Open a new position

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            size: Number of shares
            position_type: "LONG" or "SHORT"
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            Tuple of (success, message)
        """
        # Check if already have position in this symbol
        if symbol in self.positions:
            return False, f"Already have open position in {symbol}"

        # Calculate position value
        position_value = entry_price * size

        # Check if we have enough balance
        if position_value > self.balance:
            return False, f"Insufficient balance. Need ${position_value:,.2f}, have ${self.balance:,.2f}"

        # Create position
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            size=size,
            position_type=position_type,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        self.positions[symbol] = position

        # Reduce available balance (simplified - not using margin)
        self.balance -= position_value

        logger.info(
            f"Opened {position_type} position: {symbol} x{size} @ ${entry_price:.2f} "
            f"(Value: ${position_value:,.2f}, Remaining Balance: ${self.balance:,.2f})"
        )

        return True, "Position opened successfully"

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "manual",
    ) -> tuple[bool, str, Optional[Dict]]:
        """
        Close an existing position

        Args:
            symbol: Trading symbol
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Tuple of (success, message, trade_details)
        """
        if symbol not in self.positions:
            return False, f"No open position in {symbol}", None

        position = self.positions[symbol]

        # Calculate P&L
        pnl = position.get_current_pnl(exit_price)
        pnl_pct = position.get_pnl_pct(exit_price)

        # Return capital
        position_value = exit_price * position.size
        self.balance += position_value

        # Update peak balance
        self.peak_balance = max(self.peak_balance, self.balance)

        # Record trade
        trade = {
            "symbol": symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "size": position.size,
            "position_type": position.position_type,
            "entry_time": position.entry_time,
            "exit_time": datetime.now(),
            "hold_time_hours": (datetime.now() - position.entry_time).total_seconds() / 3600,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "reason": reason,
        }

        self.closed_trades.append(trade)

        # Remove position
        del self.positions[symbol]

        logger.info(
            f"Closed {position.position_type} position: {symbol} @ ${exit_price:.2f} "
            f"(P&L: ${pnl:+,.2f} / {pnl_pct:+.2f}%, Reason: {reason})"
        )

        return True, "Position closed successfully", trade

    async def update_positions(self) -> List[Dict]:
        """Update all positions with current prices and check stop/target"""
        updates = []

        for symbol, position in list(self.positions.items()):
            current_price = await self.get_current_price(symbol)

            if current_price is None:
                continue

            # Check if should close based on stop/target
            should_close, reason = position.should_close(current_price)

            if should_close:
                success, message, trade = self.close_position(symbol, current_price, reason)
                if success:
                    updates.append({
                        "action": "closed",
                        "symbol": symbol,
                        "reason": reason,
                        "trade": trade,
                    })

        return updates

    def get_account_status(self) -> Dict:
        """Get current account status"""
        # Calculate total position value
        total_position_value = sum(
            pos.entry_price * pos.size for pos in self.positions.values()
        )

        # Calculate unrealized P&L (would need current prices, simplified here)
        total_value = self.balance + total_position_value

        # Calculate daily P&L
        daily_pnl = self.balance - self.daily_starting_balance

        # Calculate overall P&L
        total_pnl = total_value - self.initial_balance

        # Calculate drawdown
        drawdown = self.peak_balance - total_value
        drawdown_pct = (drawdown / self.peak_balance) * 100 if self.peak_balance > 0 else 0

        # Trading statistics
        winning_trades = [t for t in self.closed_trades if t["pnl"] > 0]
        losing_trades = [t for t in self.closed_trades if t["pnl"] < 0]

        win_rate = (
            len(winning_trades) / len(self.closed_trades) * 100
            if self.closed_trades else 0
        )

        avg_win = sum(t["pnl"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t["pnl"] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        return {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "total_position_value": total_position_value,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": (total_pnl / self.initial_balance) * 100,
            "daily_pnl": daily_pnl,
            "daily_pnl_pct": (daily_pnl / self.daily_starting_balance) * 100,
            "peak_balance": self.peak_balance,
            "drawdown": drawdown,
            "drawdown_pct": drawdown_pct,
            "open_positions": len(self.positions),
            "total_trades": len(self.closed_trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
        }

    def get_positions(self) -> List[Dict]:
        """Get list of open positions"""
        return [
            {
                "symbol": symbol,
                "entry_price": pos.entry_price,
                "size": pos.size,
                "position_type": pos.position_type,
                "entry_time": pos.entry_time.isoformat(),
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
            }
            for symbol, pos in self.positions.items()
        ]

    def reset_daily_balance(self):
        """Reset daily starting balance (call at start of each trading day)"""
        self.daily_starting_balance = self.balance
        logger.info(f"Reset daily starting balance to ${self.balance:,.2f}")
