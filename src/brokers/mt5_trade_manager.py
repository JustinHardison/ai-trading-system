"""
MT5 Trade Manager - Python controls everything
EA is just a dumb executor that forwards requests
"""
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a trade"""
    ticket: int
    symbol: str
    type: str  # 'BUY' or 'SELL'
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    profit: float
    profit_points: float
    bars_held: int
    time_open: datetime
    comment: str


class MT5TradeManager:
    """
    Manages ALL trading logic in Python
    EA just executes orders
    """

    def __init__(self):
        self.connected = False
        self.positions_cache = {}
        logger.info("MT5TradeManager initialized")

    def connect(self) -> bool:
        """Connect to MT5"""
        try:
            if not mt5.initialize():
                logger.error(f"MT5 init failed: {mt5.last_error()}")
                return False

            self.connected = True
            account = mt5.account_info()
            logger.info(f"✅ MT5 Connected - Account: {account.login}, Balance: ${account.balance:,.2f}")
            return True

        except Exception as e:
            logger.error(f"MT5 connect error: {e}")
            return False

    def get_open_positions(self) -> List[Trade]:
        """Get all open positions"""
        if not self.connected:
            if not self.connect():
                return []

        try:
            positions = mt5.positions_get()
            if positions is None:
                return []

            trades = []
            for pos in positions:
                # Calculate bars held (approximate from time)
                time_open = datetime.fromtimestamp(pos.time)
                minutes_held = (datetime.now() - time_open).total_seconds() / 60
                bars_held = int(minutes_held)  # M1 bars

                # Calculate profit in points
                if pos.type == 0:  # BUY
                    profit_points = pos.price_current - pos.price_open
                else:  # SELL
                    profit_points = pos.price_open - pos.price_current

                trade = Trade(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    type='BUY' if pos.type == 0 else 'SELL',
                    volume=pos.volume,
                    price_open=pos.price_open,
                    price_current=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    profit_points=profit_points,
                    bars_held=bars_held,
                    time_open=time_open,
                    comment=pos.comment
                )
                trades.append(trade)

            logger.info(f"📊 Found {len(trades)} open positions")
            return trades

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_todays_trade_history(self) -> List[Dict]:
        """Get today's closed trades"""
        if not self.connected:
            if not self.connect():
                return []

        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            deals = mt5.history_deals_get(today_start, datetime.now())

            if deals is None or len(deals) == 0:
                return []

            # Group deals by position ID to get full trades
            position_deals = {}
            for deal in deals:
                pos_id = deal.position_id
                if pos_id not in position_deals:
                    position_deals[pos_id] = []
                position_deals[pos_id].append(deal)

            # Build trade history
            trade_history = []
            for pos_id, deals_list in position_deals.items():
                # Find entry and exit
                entry_deal = None
                exit_deal = None

                for deal in deals_list:
                    if deal.entry == 0:  # Entry
                        entry_deal = deal
                    elif deal.entry == 1:  # Exit
                        exit_deal = deal

                if entry_deal and exit_deal:
                    trade_history.append({
                        'position_id': pos_id,
                        'symbol': entry_deal.symbol,
                        'type': 'BUY' if entry_deal.type == 0 else 'SELL',
                        'volume': entry_deal.volume,
                        'entry_price': entry_deal.price,
                        'exit_price': exit_deal.price,
                        'profit': exit_deal.profit,
                        'time_entry': datetime.fromtimestamp(entry_deal.time),
                        'time_exit': datetime.fromtimestamp(exit_deal.time),
                        'duration_minutes': (exit_deal.time - entry_deal.time) / 60
                    })

            logger.info(f"📊 Found {len(trade_history)} closed trades today")
            return trade_history

        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []

    def close_position(self, ticket: int, volume: Optional[float] = None) -> Tuple[bool, str]:
        """Close a position (full or partial)"""
        if not self.connected:
            if not self.connect():
                return False, "Not connected to MT5"

        try:
            # Get position info
            position = None
            for pos in mt5.positions_get():
                if pos.ticket == ticket:
                    position = pos
                    break

            if position is None:
                return False, f"Position {ticket} not found"

            # Determine close volume
            close_volume = volume if volume else position.volume

            # Determine close type (opposite of position type)
            close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY

            # Get current price
            tick = mt5.symbol_info_tick(position.symbol)
            if tick is None:
                return False, "Failed to get current price"

            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

            # Create close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": close_volume,
                "type": close_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": position.magic,
                "comment": "Python API close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Send order
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Order failed: {result.comment}"

            logger.info(f"✅ Closed {close_volume} lots of position {ticket}")
            return True, f"Closed successfully"

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False, str(e)

    def open_position(self, symbol: str, direction: str, volume: float,
                     sl: float = 0, tp: float = 0, comment: str = "") -> Tuple[bool, str, int]:
        """Open a new position"""
        if not self.connected:
            if not self.connect():
                return False, "Not connected to MT5", 0

        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return False, f"Symbol {symbol} not found", 0

            # Ensure symbol is visible
            if not symbol_info.visible:
                if not mt5.symbol_select(symbol, True):
                    return False, f"Failed to select symbol {symbol}", 0

            # Get current price
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False, "Failed to get current price", 0

            # Determine order type and price
            if direction == "BUY":
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
            else:  # SELL
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid

            # Create order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": comment or "Python API",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Send order
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Order failed: {result.comment}", 0

            ticket = result.order
            logger.info(f"✅ Opened {direction} {volume} lots of {symbol} - Ticket: {ticket}")
            return True, "Position opened successfully", ticket

        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return False, str(e), 0

    def modify_position(self, ticket: int, sl: Optional[float] = None,
                       tp: Optional[float] = None) -> Tuple[bool, str]:
        """Modify SL/TP of existing position"""
        if not self.connected:
            if not self.connect():
                return False, "Not connected to MT5"

        try:
            # Get position
            position = None
            for pos in mt5.positions_get():
                if pos.ticket == ticket:
                    position = pos
                    break

            if position is None:
                return False, f"Position {ticket} not found"

            # Use current values if not specified
            new_sl = sl if sl is not None else position.sl
            new_tp = tp if tp is not None else position.tp

            # Create modify request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": position.symbol,
                "position": ticket,
                "sl": new_sl,
                "tp": new_tp,
            }

            # Send order
            result = mt5.order_send(request)

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return False, f"Modify failed: {result.comment}"

            logger.info(f"✅ Modified position {ticket} - SL: {new_sl}, TP: {new_tp}")
            return True, "Modified successfully"

        except Exception as e:
            logger.error(f"Error modifying position: {e}")
            return False, str(e)

    def get_account_info(self) -> Dict:
        """Get account information"""
        if not self.connected:
            if not self.connect():
                return {}

        try:
            account = mt5.account_info()
            if account is None:
                return {}

            return {
                'balance': account.balance,
                'equity': account.equity,
                'profit': account.profit,
                'margin': account.margin,
                'margin_free': account.margin_free,
                'margin_level': account.margin_level if account.margin > 0 else 0,
                'leverage': account.leverage,
                'login': account.login,
                'server': account.server
            }

        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}

    def disconnect(self):
        """Disconnect from MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("MT5 disconnected")
