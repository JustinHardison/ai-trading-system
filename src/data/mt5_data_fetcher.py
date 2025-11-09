"""
MT5 Data Fetcher
Fetches market data from MT5 via file-based API
"""
import json
import time
import pandas as pd
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from src.utils.logger import get_logger
from src.utils.mt5_lock import acquire_mt5_lock, release_mt5_lock

logger = get_logger(__name__)


class MT5DataFetcher:
    """
    Fetches market data from MT5 via file-based communication
    """

    def __init__(
        self,
        command_file: str = "ai_command.txt",
        response_file: str = "ai_response.txt",
        timeout: float = 10.0
    ):
        """
        Args:
            command_file: Path to command file for MT5
            response_file: Path to response file from MT5
            timeout: Command timeout in seconds
        """
        # Use MT5 TERMINAL_COMMONDATA_PATH (where EA actually writes files)
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

        self.timeout = timeout

    def get_market_data(
        self,
        symbols: List[str],
        timeframes: List[str] = ['M15', 'M30', 'H1', 'H4', 'D1'],
        bars: int = 100
    ) -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Get multi-timeframe market data for symbols

        Args:
            symbols: List of symbols
            timeframes: List of timeframes
            bars: Number of bars to fetch

        Returns:
            Dict of {symbol: {timeframe: dataframe}}
        """
        all_data = {}

        for symbol in symbols:
            symbol_data = {}

            for tf in timeframes:
                df = self._fetch_bars(symbol, tf, bars)
                if df is not None and len(df) > 0:
                    symbol_data[tf] = df

            if symbol_data:
                all_data[symbol] = symbol_data

        logger.info(f"Fetched market data for {len(all_data)}/{len(symbols)} symbols")
        return all_data

    def _fetch_bars(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV bars from MT5

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (M15, M30, H1, H4, D1)
            bars: Number of bars

        Returns:
            DataFrame with OHLCV data or None
        """
        command = {
            "action": "GET_BARS",
            "symbol": symbol,
            "timeframe": timeframe,
            "count": bars,  # EA expects 'count', not 'bars'
            "timestamp": datetime.now().isoformat()
        }

        success, response = self._send_command(command)

        if success and response:
            bars_data = response.get('bars', [])
            if bars_data:
                df = pd.DataFrame(bars_data)
                # Convert timestamp to datetime
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'])
                    df.set_index('time', inplace=True)
                return df

        return None

    def fetch_symbol_data(self, symbol: str, timeframe: str = 'H1', bars: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch single symbol data (alias for _fetch_bars for backward compatibility)

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (M1, M5, M15, M30, H1, H4, D1)
            bars: Number of bars

        Returns:
            DataFrame with OHLCV data or None
        """
        return self._fetch_bars(symbol, timeframe, bars)

    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current bid prices for symbols

        Args:
            symbols: List of symbols

        Returns:
            Dict of {symbol: price}
        """
        command = {
            "action": "GET_PRICES",
            "symbols": symbols,
            "timestamp": datetime.now().isoformat()
        }

        success, response = self._send_command(command)

        if success and response:
            return response.get('prices', {})

        return {}

    def _send_command(self, command: Dict) -> tuple[bool, Optional[Dict]]:
        """
        Send command to MT5 and wait for response

        Args:
            command: Command dictionary

        Returns:
            (success, response_dict)
        """
        # CRITICAL FIX: Use shared lock to prevent command file overwriting
        acquire_mt5_lock()
        try:
            # Clear old response
            if self.response_file.exists():
                self.response_file.unlink()

            # Write command (compact JSON without spaces for EA compatibility)
            with open(self.command_file, 'w') as f:
                json.dump(command, f, separators=(',', ':'))

            # Wait for response
            start_time = time.time()

            while time.time() - start_time < self.timeout:
                if self.response_file.exists():
                    time.sleep(0.1)  # Ensure write complete
                    logger.debug(f"Response file found, reading...")

                    try:
                        # MT5 writes responses in ANSI/UTF-8 (FILE_ANSI in v1.16+)
                        with open(self.response_file, 'r', encoding='utf-8') as f:
                            response = json.load(f)

                        logger.debug(f"Response parsed: action={response.get('action')}, has bars={('bars' in response)}, symbol={response.get('symbol')}")

                        # Check response validity BEFORE deleting file
                        # GET_BARS returns: {"success": true, "symbol": "XXX", "bars": [...]}
                        # GET_SYMBOLS returns: {"success": true, "symbols": [...]}
                        # GET_ACCOUNT_INFO returns: {"action": "GET_ACCOUNT_INFO", "status": "success"}

                        is_valid_response = False

                        if command['action'] == 'GET_BARS':
                            # For GET_BARS, check for 'bars' field and matching symbol
                            if response.get('bars') is not None and response.get('symbol') == command.get('symbol'):
                                is_valid_response = True
                        elif response.get('action') == command['action'] or response.get('success') is not None:
                            if response.get('status') == 'success' or response.get('success') == True:
                                is_valid_response = True
                            else:
                                logger.warning(f"Command failed: {response.get('error')}")
                                self.response_file.unlink()
                                return False, response

                        # Delete response file after validation
                        self.response_file.unlink()

                        if is_valid_response:
                            return True, response
                        # Wrong response - deleted it, keep waiting for correct one

                    except (json.JSONDecodeError, UnicodeDecodeError):
                        time.sleep(0.2)
                        continue
                    except FileNotFoundError:
                        # Response file disappeared - likely race condition
                        time.sleep(0.2)
                        continue

                time.sleep(0.2)

            logger.warning(f"Command timeout: {command['action']}")
            return False, None

        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False, None
        finally:
            release_mt5_lock()
