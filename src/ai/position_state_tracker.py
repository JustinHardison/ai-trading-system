"""
Position State Tracker - Tracks pyramiding, DCA, and partial exits
"""
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionStateTracker:
    """
    Tracks state for each open position to enable:
    - Pyramiding (adding to winners)
    - Smart DCA (adding to losers when AI confident)
    - Partial exits
    """
    
    def __init__(self):
        self.positions = {}  # symbol -> position_state
    
    def create_position(self, symbol: str, initial_lots: float, entry_price: float,
                       direction: str, stop_price: float, target_price: float) -> None:
        """Create new position tracking"""
        self.positions[symbol] = {
            'symbol': symbol,
            'direction': direction,
            'initial_lots': initial_lots,
            'current_lots': initial_lots,
            'avg_entry': entry_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'add_count': 0,
            'dca_count': 0,
            'add_history': [],
            'scale_out_history': [],
            'peak_profit_pct': 0.0,
            'entry_time': datetime.now(),
            'ftmo_exposure': 0.0
        }
        logger.info(f"📊 Position tracking created: {symbol} {direction} {initial_lots} lots @ {entry_price}")
    
    def add_to_position(self, symbol: str, add_lots: float, add_price: float, 
                       is_dca: bool = False) -> bool:
        """Add to existing position (pyramid or DCA)"""
        if symbol not in self.positions:
            logger.error(f"❌ Cannot add to position: {symbol} not tracked")
            return False
        
        pos = self.positions[symbol]
        
        # Update average entry
        total_cost = (pos['current_lots'] * pos['avg_entry']) + (add_lots * add_price)
        new_total_lots = pos['current_lots'] + add_lots
        new_avg = total_cost / new_total_lots
        
        # Record the add
        add_record = {
            'time': datetime.now(),
            'lots': add_lots,
            'price': add_price,
            'type': 'DCA' if is_dca else 'PYRAMID'
        }
        
        pos['add_history'].append(add_record)
        pos['current_lots'] = new_total_lots
        pos['avg_entry'] = new_avg
        
        if is_dca:
            pos['dca_count'] += 1
            logger.info(f"📉 DCA: Added {add_lots} lots @ {add_price} (total: {new_total_lots}, avg: {new_avg:.2f})")
        else:
            pos['add_count'] += 1
            logger.info(f"📈 PYRAMID: Added {add_lots} lots @ {add_price} (total: {new_total_lots}, avg: {new_avg:.2f})")
        
        return True
    
    def scale_out(self, symbol: str, reduce_lots: float, exit_price: float) -> bool:
        """Reduce position size (partial exit)"""
        if symbol not in self.positions:
            logger.error(f"❌ Cannot scale out: {symbol} not tracked")
            return False
        
        pos = self.positions[symbol]
        
        if reduce_lots >= pos['current_lots']:
            logger.warning(f"⚠️ Scale out {reduce_lots} >= current {pos['current_lots']}, closing all")
            reduce_lots = pos['current_lots']
        
        # Record the scale out
        scale_record = {
            'time': datetime.now(),
            'lots': reduce_lots,
            'price': exit_price,
            'profit_per_lot': exit_price - pos['avg_entry']
        }
        
        pos['scale_out_history'].append(scale_record)
        pos['current_lots'] -= reduce_lots
        
        logger.info(f"📉 SCALE OUT: Reduced {reduce_lots} lots @ {exit_price} (remaining: {pos['current_lots']})")
        
        return True
    
    def close_position(self, symbol: str) -> None:
        """Close and remove position tracking"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            logger.info(f"🚪 Position closed: {symbol} - Final: {pos['current_lots']} lots @ avg {pos['avg_entry']:.2f}")
            del self.positions[symbol]
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position state"""
        return self.positions.get(symbol)
    
    def can_add_to_winner(self, symbol: str, account_balance: float) -> tuple[bool, str]:
        """Check if can pyramid (add to winner)"""
        if symbol not in self.positions:
            return False, "Position not tracked"
        
        pos = self.positions[symbol]
        
        # Check 1: Max adds
        if pos['add_count'] >= 2:
            return False, "Max pyramids reached (2)"
        
        # Check 2: Max total size
        max_total = pos['initial_lots'] * 2.5
        if pos['current_lots'] >= max_total:
            return False, f"Max size reached ({max_total:.1f} lots)"
        
        # Check 3: Portfolio exposure (1.5% per symbol)
        max_exposure = account_balance * 0.015
        if pos['ftmo_exposure'] >= max_exposure:
            return False, f"Max exposure reached (${max_exposure:,.0f})"
        
        return True, "OK"
    
    def can_dca(self, symbol: str) -> tuple[bool, str]:
        """Check if can DCA (add to loser)"""
        if symbol not in self.positions:
            return False, "Position not tracked"
        
        pos = self.positions[symbol]
        
        # Check 1: Max DCA
        if pos['dca_count'] >= 1:
            return False, "Max DCA reached (1)"
        
        # Check 2: Position age (< 30 minutes)
        age_minutes = (datetime.now() - pos['entry_time']).total_seconds() / 60
        if age_minutes > 30:
            return False, f"Position too old ({age_minutes:.0f} min)"
        
        return True, "OK"
    
    def update_peak_profit(self, symbol: str, current_profit_pct: float) -> None:
        """Update peak profit tracking"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            if current_profit_pct > pos['peak_profit_pct']:
                pos['peak_profit_pct'] = current_profit_pct
    
    def update_ftmo_exposure(self, symbol: str, exposure_dollars: float) -> None:
        """Update FTMO exposure tracking"""
        if symbol in self.positions:
            self.positions[symbol]['ftmo_exposure'] = exposure_dollars


# Global instance
_tracker = None

def get_position_tracker():
    """Get global position tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = PositionStateTracker()
    return _tracker
