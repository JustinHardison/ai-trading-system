"""
MT5 Socket Client - Connects to MT5 via socket bridge
Works on macOS by communicating with MT5 Expert Advisor
"""
import socket
import json
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
    sl: float
    tp: float
    profit: float


@dataclass
class Tick:
    """Price tick"""
    symbol: str
    time: datetime
    bid: float
    ask: float


class MT5SocketClient:
    """
    Socket client for MT5 connection
    Connects to MT5 Expert Advisor running socket server
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9090, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.connected = False

        logger.info(f"Initialized MT5 Socket Client (will connect to {host}:{port})")

    def connect(self) -> Tuple[bool, str]:
        """
        Test connection to MT5 socket server

        Returns:
            Tuple of (success, message)
        """
        try:
            # Try to get account info as connection test
            result = self._send_command({"command": "get_account"})

            if result and result.get("success"):
                self.connected = True
                balance = result.get("balance", 0)
                logger.info(f"✓ Connected to MT5 via socket - Balance: ${balance:,.2f}")
                return True, f"Connected successfully - Balance: ${balance:,.2f}"
            else:
                error = result.get("error", "Unknown error") if result else "No response"
                logger.error(f"Connection test failed: {error}")
                return False, f"Connection failed: {error}"

        except Exception as e:
            logger.error(f"Failed to connect to MT5 socket: {e}")
            return False, str(e)

    def disconnect(self):
        """Disconnect (nothing to do for stateless socket)"""
        self.connected = False
        logger.info("Disconnected from MT5")

    def _send_command(self, command: Dict, retries: int = 3) -> Optional[Dict]:
        """
        Send command to MT5 socket server

        Args:
            command: Command dictionary
            retries: Number of retry attempts

        Returns:
            Response dictionary or None if failed
        """
        for attempt in range(retries):
            try:
                # Create socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)

                # Connect
                sock.connect((self.host, self.port))

                # Send command as JSON
                command_json = json.dumps(command)
                sock.sendall(command_json.encode('utf-8'))

                # Receive response
                response_data = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk

                    # Try to parse JSON (check if complete)
                    try:
                        response = json.loads(response_data.decode('utf-8'))
                        sock.close()
                        return response
                    except json.JSONDecodeError:
                        # Not complete yet, continue reading
                        continue

                sock.close()

                # Try to parse final response
                if response_data:
                    return json.loads(response_data.decode('utf-8'))

                return None

            except socket.timeout:
                logger.warning(f"Socket timeout (attempt {attempt + 1}/{retries})")
                if attempt == retries - 1:
                    return None

            except ConnectionRefusedError:
                logger.error("Connection refused - Is MT5 EA running?")
                return None

            except Exception as e:
                logger.error(f"Socket error: {e}")
                if attempt == retries - 1:
                    return None

        return None

    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        if not self.connected:
            logger.warning("Not connected to MT5")
            return None

        try:
            response = self._send_command({"command": "get_account"})

            if response and response.get("success"):
                return {
                    "balance": response.get("balance", 0),
                    "equity": response.get("equity", 0),
                    "margin": response.get("margin", 0),
                    "margin_free": response.get("free_margin", 0),
                    "profit": response.get("profit", 0),
                    "leverage": response.get("leverage", 100),
                }

            return None

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def get_tick(self, symbol: str) -> Optional[Tick]:
        """Get current tick for symbol"""
        if not self.connected:
            return None

        try:
            response = self._send_command({
                "command": "get_tick",
                "symbol": symbol
            })

            if response and response.get("success"):
                return Tick(
                    symbol=response.get("symbol", symbol),
                    time=datetime.fromtimestamp(response.get("time", 0)),
                    bid=response.get("bid", 0),
                    ask=response.get("ask", 0),
                )

            return None

        except Exception as e:
            logger.error(f"Error getting tick for {symbol}: {e}")
            return None

    def get_positions(self) -> List[Position]:
        """Get all open positions"""
        if not self.connected:
            return []

        try:
            response = self._send_command({"command": "get_positions"})

            if response and response.get("success"):
                positions = []
                for pos_data in response.get("positions", []):
                    position = Position(
                        ticket=pos_data.get("ticket", 0),
                        symbol=pos_data.get("symbol", ""),
                        type=pos_data.get("type", "buy"),
                        volume=pos_data.get("volume", 0),
                        price_open=pos_data.get("open_price", 0),
                        sl=pos_data.get("sl", 0),
                        tp=pos_data.get("tp", 0),
                        profit=pos_data.get("profit", 0),
                    )
                    positions.append(position)

                return positions

            return []

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def open_position(
        self,
        symbol: str,
        action: str,
        volume: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "AI Bot",
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
            command = {
                "command": "open_trade",
                "symbol": symbol,
                "type": action.lower(),
                "volume": volume,
            }

            if sl:
                command["sl"] = sl
            if tp:
                command["tp"] = tp

            response = self._send_command(command)

            if response and response.get("success"):
                ticket = response.get("ticket", 0)
                price = response.get("price", 0)

                logger.info(f"✓ Opened {action.upper()} {symbol} x{volume} @ {price:.5f} (Ticket: {ticket})")

                return True, "Position opened successfully", ticket
            else:
                error = response.get("error", "Unknown error") if response else "No response"
                logger.error(f"Failed to open position: {error}")
                return False, error, None

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
            response = self._send_command({
                "command": "close_trade",
                "ticket": ticket
            })

            if response and response.get("success"):
                logger.info(f"✓ Closed position {ticket}")
                return True, "Position closed successfully"
            else:
                error = response.get("error", "Unknown error") if response else "No response"
                logger.error(f"Failed to close position {ticket}: {error}")
                return False, error

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False, str(e)

    def get_rates(
        self,
        symbol: str,
        timeframe: str = "H1",
        count: int = 100,
    ) -> Optional[pd.DataFrame]:
        """
        Get historical rates

        Note: Socket server doesn't support this yet,
        fallback to yfinance for now
        """
        logger.debug(f"Getting historical data for {symbol} from yfinance fallback")

        try:
            # Use yfinance as fallback
            import yfinance as yf

            # Map MT5 symbols to Yahoo symbols
            symbol_map = {
                "EURUSD": "EURUSD=X",
                "GBPUSD": "GBPUSD=X",
                "USDJPY": "USDJPY=X",
                "XAUUSD": "GC=F",
            }

            yahoo_symbol = symbol_map.get(symbol, symbol)

            # Map timeframes
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

            df.columns = [col.lower() for col in df.columns]
            df = df[['open', 'high', 'low', 'close', 'volume']]

            return df.tail(count)

        except Exception as e:
            logger.error(f"Error getting rates: {e}")
            return None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
