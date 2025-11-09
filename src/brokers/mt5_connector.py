"""
MetaTrader 5 Real-Time Connector
Direct integration with MT5 terminal for FTMO trading
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
from dataclasses import dataclass

from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class MT5Position:
    """Represents an open MT5 position"""
    ticket: int
    symbol: str
    type: str  # 'buy' or 'sell'
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    swap: float
    commission: float
    time: datetime
    comment: str


@dataclass
class MT5Tick:
    """Real-time tick data"""
    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float
    volume: int
    spread: int


class MT5Connector:
    """
    Real-time connection to MetaTrader 5 terminal
    Handles all communication with FTMO MT5 platform
    """

    def __init__(self, account: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None):
        self.account = account
        self.password = password
        self.server = server
        self.connected = False
        self.symbols = []

        logger.info("Initialized MT5 Connector")

    def connect(self) -> Tuple[bool, str]:
        """
        Establish connection to MT5 terminal

        Returns:
            Tuple of (success, message)
        """
        try:
            # Initialize MT5 connection
            if not mt5.initialize():
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False, f"Failed to initialize MT5: {error}"

            # Login if credentials provided
            if self.account and self.password and self.server:
                if not mt5.login(self.account, self.password, self.server):
                    error = mt5.last_error()
                    logger.error(f"MT5 login failed: {error}")
                    mt5.shutdown()
                    return False, f"Failed to login: {error}"

            # Get account info
            account_info = mt5.account_info()
            if account_info is None:
                mt5.shutdown()
                return False, "Failed to get account info"

            self.connected = True
            logger.info(f"Connected to MT5 - Account: {account_info.login}, "
                       f"Balance: ${account_info.balance:.2f}, "
                       f"Equity: ${account_info.equity:.2f}, "
                       f"Server: {account_info.server}")

            return True, "Connected successfully"

        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            return False, str(e)

    def disconnect(self):
        """Disconnect from MT5 terminal"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")

    def get_account_info(self) -> Optional[Dict]:
        """Get current account information"""
        if not self.connected:
            logger.warning("Not connected to MT5")
            return None

        try:
            account = mt5.account_info()
            if account is None:
                return None

            return {
                "login": account.login,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_free": account.margin_free,
                "margin_level": account.margin_level,
                "profit": account.profit,
                "leverage": account.leverage,
                "server": account.server,
                "currency": account.currency,
                "company": account.company,
            }

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def get_tick(self, symbol: str) -> Optional[MT5Tick]:
        """Get current tick for symbol"""
        if not self.connected:
            return None

        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None

            return MT5Tick(
                symbol=symbol,
                time=datetime.fromtimestamp(tick.time),
                bid=tick.bid,
                ask=tick.ask,
                last=tick.last,
                volume=tick.volume,
                spread=tick.spread,
            )

        except Exception as e:
            logger.error(f"Error getting tick for {symbol}: {e}")
            return None

    def get_rates(
        self,
        symbol: str,
        timeframe: int = mt5.TIMEFRAME_H1,
        count: int = 100,
    ) -> Optional[pd.DataFrame]:
        """
        Get historical rates (OHLCV data)

        Args:
            symbol: Trading symbol
            timeframe: MT5 timeframe constant (M1, M5, H1, etc.)
            count: Number of bars to retrieve

        Returns:
            DataFrame with OHLCV data
        """
        if not self.connected:
            return None

        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None or len(rates) == 0:
                return None

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)

            # Rename columns for consistency
            df.columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']

            return df

        except Exception as e:
            logger.error(f"Error getting rates for {symbol}: {e}")
            return None

    def get_positions(self) -> List[MT5Position]:
        """Get all open positions"""
        if not self.connected:
            return []

        try:
            positions = mt5.positions_get()
            if positions is None:
                return []

            result = []
            for pos in positions:
                position = MT5Position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type='buy' if pos.type == mt5.ORDER_TYPE_BUY else 'sell',
                    volume=pos.volume,
                    price_open=pos.price_open,
                    price_current=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    swap=pos.swap,
                    commission=pos.commission,
                    time=datetime.fromtimestamp(pos.time),
                    comment=pos.comment,
                )
                result.append(position)

            return result

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def open_position(
        self,
        symbol: str,
        action: str,  # 'buy' or 'sell'
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "AI Trading Bot",
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Open a new position

        Args:
            symbol: Trading symbol
            action: 'buy' or 'sell'
            volume: Position size in lots
            sl: Stop loss price
            tp: Take profit price
            comment: Order comment

        Returns:
            Tuple of (success, message, ticket)
        """
        if not self.connected:
            return False, "Not connected to MT5", None

        try:
            # Get current price
            tick = self.get_tick(symbol)
            if tick is None:
                return False, f"Failed to get price for {symbol}", None

            # Prepare request
            order_type = mt5.ORDER_TYPE_BUY if action.lower() == 'buy' else mt5.ORDER_TYPE_SELL
            price = tick.ask if action.lower() == 'buy' else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": 20,  # Max slippage in points
                "magic": 234000,  # Magic number for EA identification
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Add SL/TP if provided
            if sl:
                request["sl"] = sl
            if tp:
                request["tp"] = tp

            # Send order
            result = mt5.order_send(request)

            if result is None:
                return False, "order_send failed", None

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Order failed: {result.comment}", None

            logger.info(f"Opened {action.upper()} position: {symbol} x{volume} @ {price:.5f} "
                       f"(Ticket: {result.order})")

            return True, "Position opened successfully", result.order

        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return False, str(e), None

    def close_position(self, ticket: int) -> Tuple[bool, str]:
        """
        Close an existing position

        Args:
            ticket: Position ticket number

        Returns:
            Tuple of (success, message)
        """
        if not self.connected:
            return False, "Not connected to MT5"

        try:
            # Get position info
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                return False, f"Position {ticket} not found"

            position = position[0]

            # Prepare close request (opposite order type)
            order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(position.symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close by AI Trading Bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Send close order
            result = mt5.order_send(request)

            if result is None:
                return False, "order_send failed"

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Close failed: {result.comment}"

            logger.info(f"Closed position {ticket}: Profit = {position.profit:.2f}")

            return True, f"Position closed, P&L: {position.profit:.2f}"

        except Exception as e:
            logger.error(f"Error closing position {ticket}: {e}")
            return False, str(e)

    def modify_position(
        self,
        ticket: int,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Modify stop loss and/or take profit of existing position

        Args:
            ticket: Position ticket number
            sl: New stop loss price
            tp: New take profit price

        Returns:
            Tuple of (success, message)
        """
        if not self.connected:
            return False, "Not connected to MT5"

        try:
            # Get position info
            position = mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                return False, f"Position {ticket} not found"

            position = position[0]

            # Prepare modification request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": ticket,
                "sl": sl if sl is not None else position.sl,
                "tp": tp if tp is not None else position.tp,
            }

            # Send modification
            result = mt5.order_send(request)

            if result is None:
                return False, "order_send failed"

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Modification failed: {result.comment}"

            logger.info(f"Modified position {ticket}: SL={sl}, TP={tp}")

            return True, "Position modified successfully"

        except Exception as e:
            logger.error(f"Error modifying position {ticket}: {e}")
            return False, str(e)

    def get_available_symbols(self) -> List[str]:
        """Get list of available trading symbols"""
        if not self.connected:
            return []

        try:
            symbols = mt5.symbols_get()
            if symbols is None:
                return []

            return [s.name for s in symbols if s.visible]

        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get detailed symbol information"""
        if not self.connected:
            return None

        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return None

            return {
                "name": info.name,
                "description": info.description,
                "point": info.point,
                "digits": info.digits,
                "spread": info.spread,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
                "contract_size": info.contract_size,
                "trade_mode": info.trade_mode,
                "currency_base": info.currency_base,
                "currency_profit": info.currency_profit,
                "currency_margin": info.currency_margin,
            }

        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
