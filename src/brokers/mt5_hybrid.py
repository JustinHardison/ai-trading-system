"""
MT5 Hybrid Connector - Works on macOS and Windows
Uses MetaTrader5 package on Windows, manual connection on macOS
"""
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class Position:
    """Trading position"""
    ticket: int
    symbol: str
    type: str
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    time: datetime


@dataclass
class Tick:
    """Price tick"""
    symbol: str
    time: datetime
    bid: float
    ask: float
    last: float


class MT5HybridConnector:
    """
    Hybrid MT5 connector that works on both macOS and Windows

    Windows: Uses official MetaTrader5 package
    macOS: Uses alternative connection methods
    """

    def __init__(self, account: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None):
        self.account = account
        self.password = password
        self.server = server
        self.connected = False
        self.is_windows = sys.platform == "win32"
        self.mt5 = None

        # Simulated state for macOS testing
        self.mock_positions = {}
        self.mock_balance = 100000.0
        self.mock_equity = 100000.0
        self.next_ticket = 1000

        if self.is_windows:
            try:
                import MetaTrader5 as mt5
                self.mt5 = mt5
                logger.info("Running on Windows - using official MetaTrader5 package")
            except ImportError:
                logger.warning("MetaTrader5 package not installed")
                self.is_windows = False
        else:
            logger.info("Running on macOS - using hybrid mode with manual data entry")

    def connect(self) -> Tuple[bool, str]:
        """Connect to MT5"""

        if self.is_windows and self.mt5:
            # Windows: Use official package
            return self._connect_windows()
        else:
            # macOS: Use manual connection
            return self._connect_macos()

    def _connect_windows(self) -> Tuple[bool, str]:
        """Connect using official MT5 package (Windows only)"""
        try:
            if not self.mt5.initialize():
                error = self.mt5.last_error()
                return False, f"MT5 initialization failed: {error}"

            if self.account and self.password and self.server:
                if not self.mt5.login(self.account, self.password, self.server):
                    error = self.mt5.last_error()
                    self.mt5.shutdown()
                    return False, f"Login failed: {error}"

            account_info = self.mt5.account_info()
            if account_info is None:
                self.mt5.shutdown()
                return False, "Failed to get account info"

            self.connected = True
            logger.info(f"✓ Connected to MT5 - Account: {account_info.login}, "
                       f"Balance: ${account_info.balance:.2f}")

            return True, "Connected successfully"

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False, str(e)

    def _connect_macos(self) -> Tuple[bool, str]:
        """
        Connect on macOS using manual data entry

        Since official MT5 package doesn't work on macOS, we'll:
        1. Let user manually enter account details
        2. Fetch market data from alternative sources
        3. Simulate order execution for testing
        """

        print("\n" + "="*60)
        print("MT5 CONNECTION - macOS MODE")
        print("="*60)
        print("\nSince MetaTrader5 package only works on Windows,")
        print("we'll use a hybrid approach for testing on macOS.\n")

        # Get account details
        if not self.account:
            print("Please enter your MT5 demo account details:")
            try:
                self.account = int(input("Account Number: ").strip())
                self.server = input("Server Name (e.g., FTMO-Demo): ").strip()
                self.mock_balance = float(input("Account Balance: ").strip() or "100000")
            except ValueError:
                return False, "Invalid input"

        self.connected = True
        self.mock_equity = self.mock_balance

        logger.info(f"✓ Connected to MT5 (macOS hybrid mode)")
        logger.info(f"  Account: {self.account}")
        logger.info(f"  Server: {self.server}")
        logger.info(f"  Balance: ${self.mock_balance:,.2f}")
        print(f"\n✓ Connected successfully!")
        print(f"  Account: {self.account}")
        print(f"  Balance: ${self.mock_balance:,.2f}\n")

        return True, "Connected in hybrid mode"

    def disconnect(self):
        """Disconnect from MT5"""
        if self.is_windows and self.mt5 and self.connected:
            self.mt5.shutdown()

        self.connected = False
        logger.info("Disconnected from MT5")

    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        if not self.connected:
            return None

        if self.is_windows and self.mt5:
            # Windows: Use real data
            account = self.mt5.account_info()
            if account is None:
                return None

            return {
                "login": account.login,
                "balance": account.balance,
                "equity": account.equity,
                "margin": account.margin,
                "margin_free": account.margin_free,
                "profit": account.profit,
                "leverage": account.leverage,
                "server": account.server,
            }
        else:
            # macOS: Use simulated data
            total_profit = sum(p.profit for p in self.mock_positions.values())

            return {
                "login": self.account,
                "balance": self.mock_balance,
                "equity": self.mock_balance + total_profit,
                "margin": 0,
                "margin_free": self.mock_balance,
                "profit": total_profit,
                "leverage": 100,
                "server": self.server,
            }

    def get_tick(self, symbol: str) -> Optional[Tick]:
        """Get current tick"""
        if not self.connected:
            return None

        if self.is_windows and self.mt5:
            # Windows: Get real tick
            tick = self.mt5.symbol_info_tick(symbol)
            if tick is None:
                return None

            return Tick(
                symbol=symbol,
                time=datetime.fromtimestamp(tick.time),
                bid=tick.bid,
                ask=tick.ask,
                last=tick.last,
            )
        else:
            # macOS: Get from yfinance or manual input
            import yfinance as yf

            # Map MT5 symbols to Yahoo symbols
            yahoo_symbol = self._mt5_to_yahoo(symbol)

            try:
                ticker = yf.Ticker(yahoo_symbol)
                data = ticker.history(period="1d", interval="1m")

                if data.empty:
                    return None

                last_price = float(data['Close'].iloc[-1])
                spread = last_price * 0.0002  # 2 pips spread

                return Tick(
                    symbol=symbol,
                    time=datetime.now(),
                    bid=last_price - spread/2,
                    ask=last_price + spread/2,
                    last=last_price,
                )
            except Exception as e:
                logger.error(f"Error fetching tick for {symbol}: {e}")
                return None

    def _mt5_to_yahoo(self, symbol: str) -> str:
        """Convert MT5 symbol to Yahoo Finance symbol"""
        conversions = {
            "EURUSD": "EURUSD=X",
            "GBPUSD": "GBPUSD=X",
            "USDJPY": "USDJPY=X",
            "AUDUSD": "AUDUSD=X",
            "USDCAD": "USDCAD=X",
            "XAUUSD": "GC=F",  # Gold
            "US30": "^DJI",    # Dow Jones
            "US500": "^GSPC",  # S&P 500
            "NAS100": "^NDX",  # Nasdaq
        }
        return conversions.get(symbol, symbol)

    def get_rates(
        self,
        symbol: str,
        timeframe: str = "1H",
        count: int = 100,
    ) -> Optional[pd.DataFrame]:
        """Get historical rates"""
        if not self.connected:
            return None

        if self.is_windows and self.mt5:
            # Windows: Use real MT5 data
            timeframe_map = {
                "M1": self.mt5.TIMEFRAME_M1,
                "M5": self.mt5.TIMEFRAME_M5,
                "M15": self.mt5.TIMEFRAME_M15,
                "M30": self.mt5.TIMEFRAME_M30,
                "H1": self.mt5.TIMEFRAME_H1,
                "H4": self.mt5.TIMEFRAME_H4,
                "D1": self.mt5.TIMEFRAME_D1,
            }

            tf = timeframe_map.get(timeframe, self.mt5.TIMEFRAME_H1)
            rates = self.mt5.copy_rates_from_pos(symbol, tf, 0, count)

            if rates is None or len(rates) == 0:
                return None

            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df.columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']

            return df
        else:
            # macOS: Use yfinance
            yahoo_symbol = self._mt5_to_yahoo(symbol)

            try:
                import yfinance as yf

                interval_map = {
                    "M1": "1m",
                    "M5": "5m",
                    "M15": "15m",
                    "M30": "30m",
                    "H1": "1h",
                    "H4": "4h",
                    "D1": "1d",
                }

                period_map = {
                    "M1": "1d",
                    "M5": "5d",
                    "M15": "5d",
                    "M30": "5d",
                    "H1": "5d",
                    "H4": "60d",
                    "D1": "1y",
                }

                interval = interval_map.get(timeframe, "1h")
                period = period_map.get(timeframe, "5d")

                ticker = yf.Ticker(yahoo_symbol)
                df = ticker.history(period=period, interval=interval)

                if df.empty:
                    return None

                # Standardize column names
                df.columns = [col.lower() for col in df.columns]
                df = df[['open', 'high', 'low', 'close', 'volume']]

                return df.tail(count)

            except Exception as e:
                logger.error(f"Error fetching rates for {symbol}: {e}")
                return None

    def get_positions(self) -> List[Position]:
        """Get open positions"""
        if not self.connected:
            return []

        if self.is_windows and self.mt5:
            # Windows: Get real positions
            positions = self.mt5.positions_get()
            if positions is None:
                return []

            result = []
            for pos in positions:
                position = Position(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type='buy' if pos.type == self.mt5.ORDER_TYPE_BUY else 'sell',
                    volume=pos.volume,
                    price_open=pos.price_open,
                    price_current=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    time=datetime.fromtimestamp(pos.time),
                )
                result.append(position)

            return result
        else:
            # macOS: Return simulated positions
            return list(self.mock_positions.values())

    def open_position(
        self,
        symbol: str,
        action: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "AI Bot",
    ) -> Tuple[bool, str, Optional[int]]:
        """Open position"""
        if not self.connected:
            return False, "Not connected", None

        # Get current price
        tick = self.get_tick(symbol)
        if tick is None:
            return False, f"Failed to get price for {symbol}", None

        if self.is_windows and self.mt5:
            # Windows: Execute real order
            order_type = self.mt5.ORDER_TYPE_BUY if action.lower() == 'buy' else self.mt5.ORDER_TYPE_SELL
            price = tick.ask if action.lower() == 'buy' else tick.bid

            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl or 0,
                "tp": tp or 0,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }

            result = self.mt5.order_send(request)
            if result is None or result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return False, f"Order failed: {result.comment if result else 'Unknown error'}", None

            logger.info(f"✓ Opened {action} {symbol} x{volume} @ {price}")
            return True, "Position opened", result.order
        else:
            # macOS: Simulate order
            ticket = self.next_ticket
            self.next_ticket += 1

            price = tick.ask if action.lower() == 'buy' else tick.bid

            position = Position(
                ticket=ticket,
                symbol=symbol,
                type=action.lower(),
                volume=volume,
                price_open=price,
                price_current=price,
                sl=sl or 0,
                tp=tp or 0,
                profit=0,
                time=datetime.now(),
            )

            self.mock_positions[ticket] = position

            logger.info(f"✓ [SIMULATED] Opened {action} {symbol} x{volume} @ {price:.5f} (Ticket: {ticket})")
            print(f"\n✓ [SIMULATED] Opened {action.upper()} position:")
            print(f"  Symbol: {symbol}")
            print(f"  Volume: {volume}")
            print(f"  Price: {price:.5f}")
            print(f"  Stop Loss: {sl or 'None'}")
            print(f"  Take Profit: {tp or 'None'}")
            print(f"  Ticket: {ticket}\n")

            return True, "Position opened (simulated)", ticket

    def close_position(self, ticket: int) -> Tuple[bool, str]:
        """Close position"""
        if not self.connected:
            return False, "Not connected"

        if self.is_windows and self.mt5:
            # Windows: Close real position
            position = self.mt5.positions_get(ticket=ticket)
            if position is None or len(position) == 0:
                return False, f"Position {ticket} not found"

            position = position[0]
            order_type = self.mt5.ORDER_TYPE_SELL if position.type == self.mt5.ORDER_TYPE_BUY else self.mt5.ORDER_TYPE_BUY
            tick = self.get_tick(position.symbol)
            price = tick.bid if order_type == self.mt5.ORDER_TYPE_SELL else tick.ask

            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }

            result = self.mt5.order_send(request)
            if result is None or result.retcode != self.mt5.TRADE_RETCODE_DONE:
                return False, f"Close failed: {result.comment if result else 'Unknown error'}"

            logger.info(f"✓ Closed position {ticket}, P&L: {position.profit:.2f}")
            return True, f"Closed, P&L: {position.profit:.2f}"
        else:
            # macOS: Simulate close
            if ticket not in self.mock_positions:
                return False, f"Position {ticket} not found"

            position = self.mock_positions[ticket]
            tick = self.get_tick(position.symbol)

            if tick:
                exit_price = tick.bid if position.type == 'buy' else tick.ask

                if position.type == 'buy':
                    profit = (exit_price - position.price_open) * position.volume * 100000  # Simplified
                else:
                    profit = (position.price_open - exit_price) * position.volume * 100000

                self.mock_balance += profit

                del self.mock_positions[ticket]

                logger.info(f"✓ [SIMULATED] Closed position {ticket}, P&L: ${profit:.2f}")
                print(f"\n✓ [SIMULATED] Closed position {ticket}")
                print(f"  P&L: ${profit:+.2f}")
                print(f"  New Balance: ${self.mock_balance:,.2f}\n")

                return True, f"Closed (simulated), P&L: ${profit:.2f}"

            return False, "Failed to get exit price"

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
