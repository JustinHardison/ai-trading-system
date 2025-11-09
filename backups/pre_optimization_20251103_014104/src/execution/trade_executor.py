"""
Trade Executor
Executes trades via MT5 file-based API
"""
import json
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradeExecutor:
    """
    Executes trades via MT5 file-based communication

    Commands sent to MT5 via ai_command.txt:
    - OPEN_TRADE: Open new position
    - CLOSE_TRADE: Close existing position
    - MODIFY_TRADE: Modify SL/TP
    - CLOSE_ALL: Emergency close all
    """

    def __init__(
        self,
        command_file: str = "ai_command.txt",
        response_file: str = "ai_response.txt",
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Args:
            command_file: Path to command file for MT5
            response_file: Path to response file from MT5
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (seconds)
        """
        # Use MT5 Common Files directory (FILE_COMMON location)
        import os
        mt5_common_files = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"

        # If paths are just filenames (not full paths), use MT5 directory
        if not Path(command_file).is_absolute():
            self.command_file = mt5_common_files / command_file
        else:
            self.command_file = Path(command_file)

        if not Path(response_file).is_absolute():
            self.response_file = mt5_common_files / response_file
        else:
            self.response_file = Path(response_file)

        self.max_retries = max_retries
        self.retry_delay = retry_delay

        logger.info(f"Initialized Trade Executor (command: {self.command_file})")

    def open_trade(
        self,
        symbol: str,
        direction: str,
        risk_pct: float,
        stop_loss_pips: float,
        take_profit_pips: float,
        account_balance: float,
        comment: str = "AI Trade"
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Open new trade

        Args:
            symbol: Trading symbol (e.g., EURUSD)
            direction: 'BUY' or 'SELL'
            risk_pct: Risk percentage (e.g., 1.5)
            stop_loss_pips: Stop loss in pips
            take_profit_pips: Take profit in pips
            account_balance: Current account balance
            comment: Trade comment

        Returns:
            (success, message, ticket_id)
        """
        # Calculate lot size based on risk
        pip_value = 10  # Standard lot pip value for forex
        risk_amount = account_balance * (risk_pct / 100)
        lot_size = risk_amount / (stop_loss_pips * pip_value)

        # Round to 2 decimals and enforce min/max
        lot_size = round(lot_size, 2)
        lot_size = max(0.01, min(lot_size, 10.0))  # Min 0.01, Max 10 lots

        command = {
            "action": "OPEN_TRADE",
            "symbol": symbol,
            "direction": direction,
            "lots": lot_size,
            "stop_loss_pips": stop_loss_pips,
            "take_profit_pips": take_profit_pips,
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(
            f"Opening {direction} {symbol}: {lot_size} lots, "
            f"SL: {stop_loss_pips} pips, TP: {take_profit_pips} pips, "
            f"Risk: {risk_pct:.2f}%"
        )

        success, response = self._send_command(command)

        if success and response:
            ticket = response.get('ticket')
            if ticket:
                logger.info(f"✓ Trade opened successfully: Ticket #{ticket}")
                return True, f"Trade opened: #{ticket}", ticket
            else:
                logger.warning(f"Trade opened but no ticket returned: {response}")
                return True, "Trade opened (no ticket)", None
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'No response from MT5'
            logger.error(f"✗ Failed to open trade: {error_msg}")
            return False, f"Failed: {error_msg}", None

    def close_trade(
        self,
        ticket: int,
        reason: str = "AI Decision"
    ) -> Tuple[bool, str]:
        """
        Close existing trade

        Args:
            ticket: Trade ticket number
            reason: Reason for closing

        Returns:
            (success, message)
        """
        command = {
            "action": "CLOSE_TRADE",
            "ticket": ticket,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Closing trade #{ticket}: {reason}")

        success, response = self._send_command(command)

        if success:
            logger.info(f"✓ Trade #{ticket} closed successfully")
            return True, f"Trade #{ticket} closed"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'No response from MT5'
            logger.error(f"✗ Failed to close trade #{ticket}: {error_msg}")
            return False, f"Failed: {error_msg}"

    def modify_trade(
        self,
        ticket: int,
        new_stop_loss: Optional[float] = None,
        new_take_profit: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Modify existing trade SL/TP

        Args:
            ticket: Trade ticket number
            new_stop_loss: New stop loss price (None = don't change)
            new_take_profit: New take profit price (None = don't change)

        Returns:
            (success, message)
        """
        command = {
            "action": "MODIFY_TRADE",
            "ticket": ticket,
            "timestamp": datetime.now().isoformat()
        }

        if new_stop_loss is not None:
            command['stop_loss'] = new_stop_loss

        if new_take_profit is not None:
            command['take_profit'] = new_take_profit

        logger.info(f"Modifying trade #{ticket}: SL={new_stop_loss}, TP={new_take_profit}")

        success, response = self._send_command(command)

        if success:
            logger.info(f"✓ Trade #{ticket} modified successfully")
            return True, f"Trade #{ticket} modified"
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'No response from MT5'
            logger.error(f"✗ Failed to modify trade #{ticket}: {error_msg}")
            return False, f"Failed: {error_msg}"

    def close_all_positions(self, reason: str = "Emergency Close") -> Tuple[bool, str, int]:
        """
        Close all open positions

        Args:
            reason: Reason for closing all

        Returns:
            (success, message, num_closed)
        """
        command = {
            "action": "CLOSE_ALL",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }

        logger.warning(f"⚠️  CLOSING ALL POSITIONS: {reason}")

        success, response = self._send_command(command)

        if success and response:
            num_closed = response.get('closed_count', 0)
            logger.info(f"✓ Closed {num_closed} positions")
            return True, f"Closed {num_closed} positions", num_closed
        else:
            error_msg = response.get('error', 'Unknown error') if response else 'No response from MT5'
            logger.error(f"✗ Failed to close all positions: {error_msg}")
            return False, f"Failed: {error_msg}", 0

    def move_to_breakeven(self, ticket: int, entry_price: float) -> Tuple[bool, str]:
        """
        Move stop loss to breakeven

        Args:
            ticket: Trade ticket number
            entry_price: Original entry price

        Returns:
            (success, message)
        """
        logger.info(f"Moving trade #{ticket} to breakeven (SL={entry_price:.5f})")
        return self.modify_trade(ticket, new_stop_loss=entry_price)

    def _send_command(self, command: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Send command to MT5 and wait for response

        Args:
            command: Command dictionary

        Returns:
            (success, response_dict)
        """
        for attempt in range(self.max_retries):
            try:
                # Clear old response file
                if self.response_file.exists():
                    self.response_file.unlink()

                # Write command
                with open(self.command_file, 'w') as f:
                    json.dump(command, f, indent=2)

                logger.debug(f"Command sent (attempt {attempt + 1}/{self.max_retries}): {command['action']}")

                # Wait for response (timeout 10 seconds)
                start_time = time.time()
                timeout = 10.0

                while time.time() - start_time < timeout:
                    if self.response_file.exists():
                        # Small delay to ensure write is complete
                        time.sleep(0.1)

                        try:
                            # MT5 writes UTF-16 with BOM (FILE_TXT in MQL5)
                            with open(self.response_file, 'r', encoding='utf-16') as f:
                                response = json.load(f)

                            logger.debug(f"Response received: {response}")

                            # Check if response matches command
                            # GET_SYMBOLS doesn't echo action, so check for "success" field
                            if response.get('action') == command['action'] or response.get('success') is not None:
                                if response.get('status') == 'success' or response.get('success') == True:
                                    return True, response
                                else:
                                    return False, response

                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.warning(f"Failed to parse response: {e}")
                            time.sleep(0.5)
                            continue

                    time.sleep(0.2)

                logger.warning(f"Command timeout (attempt {attempt + 1})")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"Error sending command: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        logger.error(f"Failed to send command after {self.max_retries} attempts")
        return False, None

    def get_account_info(self) -> Optional[Dict]:
        """
        Get account information from MT5

        Returns:
            Dict with balance, equity, margin, etc. or None
        """
        command = {
            "action": "GET_ACCOUNT_INFO",
            "timestamp": datetime.now().isoformat()
        }

        success, response = self._send_command(command)

        if success and response:
            return response.get('account_info')
        return None

    def get_open_positions(self) -> Optional[list]:
        """
        Get all open positions from MT5

        Returns:
            List of position dicts or None
        """
        command = {
            "action": "GET_POSITIONS",
            "timestamp": datetime.now().isoformat()
        }

        success, response = self._send_command(command)

        if success and response:
            return response.get('positions', [])
        return None

    def is_mt5_connected(self) -> bool:
        """
        Check if MT5 is connected and responsive

        Returns:
            True if connected
        """
        account_info = self.get_account_info()
        return account_info is not None

    def get_market_watch_symbols(self) -> Optional[list]:
        """
        Get all symbols from MT5 Market Watch

        Returns:
            List of symbol strings (e.g. ['EURUSD', 'GBPUSD', ...]) or None if failed
        """
        command = {
            "action": "GET_SYMBOLS",
            "timestamp": datetime.now().isoformat()
        }

        success, response = self._send_command(command)

        if success and response and response.get('success'):
            symbols = response.get('symbols', [])
            logger.info(f"Fetched {len(symbols)} symbols from MT5 market watch")
            return symbols

        logger.warning("Failed to fetch symbols from MT5")
        return None
