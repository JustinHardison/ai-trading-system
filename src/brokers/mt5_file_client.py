"""
MT5 File Client - Connects to MT5 via file-based communication
Works on macOS by communicating with MT5 Expert Advisor via shared files
"""
import json
import time
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

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


class MT5FileClient:
    """
    File-based client for MT5 connection
    Communicates with MT5 Expert Advisor via shared files
    """

    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.connected = False

        # MQL5/Files directory (default for file operations without FILE_COMMON)
        self.mt5_files_path = Path.home() / "Library" / "Application Support" / \
                             "net.metaquotes.wine.metatrader5" / "drive_c" / \
                             "Program Files" / "MetaTrader 5" / "MQL5" / "Files"

        # Ensure directory exists
        self.mt5_files_path.mkdir(parents=True, exist_ok=True)

        self.command_file = self.mt5_files_path / "ai_command.txt"
        self.response_file = self.mt5_files_path / "ai_response.txt"

        logger.info(f"Initialized MT5 File Client")
        logger.info(f"Command file: {self.command_file}")
        logger.info(f"Response file: {self.response_file}")

    def connect(self) -> Tuple[bool, str]:
        """
        Test connection to MT5 file server

        Returns:
            Tuple of (success, message)
        """
        try:
            # Try to get account info as connection test
            result = self._send_command({"command": "get_account"})

            if result and result.get("success"):
                self.connected = True
                balance = result.get("balance", 0)
                logger.info(f"✓ Connected to MT5 via files - Balance: ${balance:,.2f}")
                return True, f"Connected successfully - Balance: ${balance:,.2f}"
            else:
                error = result.get("error", "Unknown error") if result else "No response"
                logger.error(f"Connection test failed: {error}")
                return False, f"Connection failed: {error}"

        except Exception as e:
            logger.error(f"Failed to connect to MT5: {e}")
            return False, str(e)

    def disconnect(self):
        """Disconnect (cleanup files)"""
        self.connected = False
        # Clean up files
        try:
            if self.command_file.exists():
                self.command_file.unlink()
            if self.response_file.exists():
                self.response_file.unlink()
        except:
            pass
        logger.info("Disconnected from MT5")

    def _send_command(self, command: Dict, retries: int = 3) -> Optional[Dict]:
        """
        Send command to MT5 file server

        Args:
            command: Command dictionary
            retries: Number of retry attempts

        Returns:
            Response dictionary or None if failed
        """
        for attempt in range(retries):
            try:
                # Delete old response file if exists
                if self.response_file.exists():
                    self.response_file.unlink()

                # Write command to file
                command_json = json.dumps(command)
                self.command_file.write_text(command_json)

                logger.debug(f"Sent command: {command_json}")

                # Wait for response file
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    if self.response_file.exists():
                        # Give MT5 a moment to finish writing
                        time.sleep(0.1)

                        # Read response (try different encodings)
                        try:
                            response_text = self.response_file.read_text(encoding='utf-8-sig')  # Handles BOM
                        except:
                            try:
                                response_text = self.response_file.read_text(encoding='utf-16-le')
                            except:
                                response_text = self.response_file.read_text(encoding='latin-1')

                        if response_text:
                            # Strip any remaining BOM or whitespace
                            response_text = response_text.strip('\ufeff').strip()
                            response = json.loads(response_text)
                            logger.debug(f"Received response: {response_text}")

                            # Clean up
                            self.response_file.unlink()

                            return response

                    time.sleep(0.1)

                logger.warning(f"Timeout waiting for response (attempt {attempt + 1}/{retries})")

            except Exception as e:
                logger.error(f"File communication error: {e}")
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

    def get_all_symbols(self) -> List[str]:
        """
        Get all available trading symbols from MT5 Market Watch

        Returns:
            List of symbol names
        """
        if not self.connected:
            logger.warning("Not connected to MT5")
            return []

        try:
            response = self._send_command({"command": "get_symbols"})

            if response and response.get("success"):
                symbols = response.get("symbols", [])
                logger.info(f"✓ Got {len(symbols)} symbols from MT5")
                return symbols

            return []

        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    def get_rates(
        self,
        symbol: str,
        timeframe: str = "H1",
        count: int = 100,
    ) -> Optional[pd.DataFrame]:
        """
        Get historical rates directly from MT5

        Args:
            symbol: Trading symbol
            timeframe: Chart timeframe (M1, M5, M15, M30, H1, H4, D1)
            count: Number of bars to retrieve

        Returns:
            DataFrame with OHLCV data
        """
        if not self.connected:
            logger.warning("Not connected to MT5")
            return None

        try:
            response = self._send_command({
                "command": "get_rates",
                "symbol": symbol,
                "timeframe": timeframe,
                "count": count
            })

            if response and response.get("success"):
                bars = response.get("bars", [])

                if not bars:
                    logger.warning(f"No data returned for {symbol}")
                    return None

                # Convert to DataFrame
                df = pd.DataFrame(bars)

                # Convert timestamp to datetime
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)

                # Ensure correct column order
                df = df[['open', 'high', 'low', 'close', 'volume']]

                logger.debug(f"Got {len(df)} bars for {symbol} on {timeframe}")

                return df

            else:
                error = response.get("error", "Unknown error") if response else "No response"
                logger.error(f"Failed to get rates for {symbol}: {error}")
                return None

        except Exception as e:
            logger.error(f"Error getting rates for {symbol}: {e}")
            return None

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
