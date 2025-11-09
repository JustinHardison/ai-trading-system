"""
FTMO Challenge Strategy Module
Professional-grade risk management for prop firm trading

Features:
1. Correlation-Based Portfolio Risk
2. Session-Based Trading Adjustments
3. Win Rate Tracking Per Symbol
4. Drawdown Recovery Mode
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional
import pytz

logger = logging.getLogger(__name__)


class FTMOStrategy:
    """
    FTMO Challenge Strategy - Professional Risk Management
    
    This module provides:
    1. Correlation-based position sizing (reduce size for correlated positions)
    2. Session-based adjustments (best liquidity during London/NY overlap)
    3. Win rate tracking per symbol (dynamic sizing based on performance)
    4. Drawdown recovery mode (ultra-conservative after significant DD)
    """
    
    # Symbol correlation groups
    CORRELATION_GROUPS = {
        'indices_us': ['us30', 'us100', 'us500'],  # ~90% correlated
        'forex_eur': ['eurusd', 'gbpusd'],          # ~80% correlated
        'forex_jpy': ['usdjpy'],                    # Independent
        'commodities_gold': ['xau', 'xauusd', 'gold'],  # Independent
        'commodities_oil': ['usoil', 'wti', 'oil'],     # Independent
    }
    
    # Correlation penalties (reduce size when adding correlated positions)
    CORRELATION_PENALTIES = {
        'indices_us': 0.5,    # 50% size for 2nd position, 33% for 3rd
        'forex_eur': 0.6,     # 60% size for 2nd position
    }
    
    # Trading sessions (UTC times)
    SESSIONS = {
        'asian': {'start': 0, 'end': 8, 'indices_mult': 0.5, 'forex_mult': 0.7},
        'london': {'start': 8, 'end': 16, 'indices_mult': 0.8, 'forex_mult': 1.0},
        'new_york': {'start': 13, 'end': 21, 'indices_mult': 1.0, 'forex_mult': 1.0},
        'overlap': {'start': 13, 'end': 16, 'indices_mult': 1.2, 'forex_mult': 1.2},  # Best liquidity
    }
    
    def __init__(self):
        self.win_rate_tracker: Dict[str, Dict] = {}  # symbol -> {wins, losses, streak}
        self.daily_start_balance: float = 0.0
        self.peak_balance: float = 0.0
        self.recovery_mode: bool = False
        self.recovery_mode_start_balance: float = 0.0
        
        logger.info("🏆 FTMO Strategy Module initialized")
        logger.info("   - Correlation-based portfolio risk")
        logger.info("   - Session-based trading adjustments")
        logger.info("   - Win rate tracking per symbol")
        logger.info("   - Drawdown recovery mode")
    
    def update_account_state(self, balance: float, equity: float, daily_start: float, peak: float):
        """Update account state for drawdown tracking"""
        self.daily_start_balance = daily_start
        self.peak_balance = peak
        
        # Check for recovery mode
        drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0
        
        if drawdown_pct >= 3.0 and not self.recovery_mode:
            # Enter recovery mode
            self.recovery_mode = True
            self.recovery_mode_start_balance = equity
            logger.warning(f"🚨 RECOVERY MODE ACTIVATED: {drawdown_pct:.2f}% drawdown from peak")
            logger.warning(f"   Only A+ setups until back to ${self.recovery_mode_start_balance * 1.02:,.0f}")
        
        elif self.recovery_mode and equity >= self.recovery_mode_start_balance * 1.02:
            # Exit recovery mode (recovered 2% from entry)
            self.recovery_mode = False
            logger.info(f"✅ RECOVERY MODE DEACTIVATED: Recovered to ${equity:,.0f}")
    
    def record_trade_result(self, symbol: str, is_win: bool, profit_pct: float):
        """Record trade result for win rate tracking"""
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '')
        
        if symbol_lower not in self.win_rate_tracker:
            self.win_rate_tracker[symbol_lower] = {
                'wins': 0,
                'losses': 0,
                'total_profit_pct': 0.0,
                'streak': 0,  # Positive = win streak, negative = loss streak
                'last_10': []  # Last 10 results for recent performance
            }
        
        tracker = self.win_rate_tracker[symbol_lower]
        
        if is_win:
            tracker['wins'] += 1
            tracker['streak'] = max(1, tracker['streak'] + 1)
        else:
            tracker['losses'] += 1
            tracker['streak'] = min(-1, tracker['streak'] - 1)
        
        tracker['total_profit_pct'] += profit_pct
        tracker['last_10'].append(1 if is_win else 0)
        if len(tracker['last_10']) > 10:
            tracker['last_10'].pop(0)
        
        win_rate = tracker['wins'] / (tracker['wins'] + tracker['losses']) * 100
        recent_win_rate = sum(tracker['last_10']) / len(tracker['last_10']) * 100 if tracker['last_10'] else 50
        
        logger.info(f"📊 {symbol_lower.upper()} Trade Result: {'WIN' if is_win else 'LOSS'}")
        logger.info(f"   Overall: {win_rate:.1f}% ({tracker['wins']}W/{tracker['losses']}L)")
        logger.info(f"   Recent (last 10): {recent_win_rate:.1f}%")
        logger.info(f"   Streak: {tracker['streak']}")
    
    def get_correlation_multiplier(self, symbol: str, open_positions: List[str]) -> float:
        """
        Calculate position size multiplier based on correlation with existing positions.
        
        Returns a multiplier 0.0-1.0 to reduce position size for correlated positions.
        """
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '')
        
        # Find which correlation group this symbol belongs to
        symbol_group = None
        for group_name, symbols in self.CORRELATION_GROUPS.items():
            if any(s in symbol_lower for s in symbols):
                symbol_group = group_name
                break
        
        if symbol_group is None:
            return 1.0  # No correlation group, full size
        
        # Count how many correlated positions are already open
        correlated_count = 0
        for pos_symbol in open_positions:
            pos_lower = pos_symbol.lower().replace('.sim', '').replace('z25', '')
            if pos_lower == symbol_lower:
                continue  # Don't count self
            
            for s in self.CORRELATION_GROUPS.get(symbol_group, []):
                if s in pos_lower:
                    correlated_count += 1
                    break
        
        if correlated_count == 0:
            return 1.0  # No correlated positions
        
        # Apply correlation penalty
        base_penalty = self.CORRELATION_PENALTIES.get(symbol_group, 0.7)
        
        # Each additional correlated position reduces size further
        # 1st correlated: base_penalty, 2nd: base_penalty^2, etc.
        multiplier = base_penalty ** correlated_count
        
        logger.info(f"   📊 Correlation: {symbol_lower.upper()} has {correlated_count} correlated positions")
        logger.info(f"      Group: {symbol_group} → {multiplier:.2f}x size")
        
        return multiplier
    
    def get_session_multiplier(self, symbol: str) -> float:
        """
        Calculate position size multiplier based on current trading session.
        
        Best liquidity during London/NY overlap = larger positions allowed.
        Asian session = reduce size for indices.
        """
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '')
        
        # Determine symbol type
        is_index = any(s in symbol_lower for s in ['us30', 'us100', 'us500', 'dax', 'ftse'])
        is_forex = any(s in symbol_lower for s in ['eur', 'gbp', 'jpy', 'aud', 'nzd', 'cad', 'chf'])
        
        # Get current UTC hour
        utc_now = datetime.now(pytz.UTC)
        current_hour = utc_now.hour
        
        # Check which session we're in
        session_name = 'asian'  # Default
        session_mult = 0.7
        
        # Check for overlap first (highest priority)
        if 13 <= current_hour < 16:
            session_name = 'overlap'
            session_mult = self.SESSIONS['overlap']['indices_mult' if is_index else 'forex_mult']
        elif 13 <= current_hour < 21:
            session_name = 'new_york'
            session_mult = self.SESSIONS['new_york']['indices_mult' if is_index else 'forex_mult']
        elif 8 <= current_hour < 16:
            session_name = 'london'
            session_mult = self.SESSIONS['london']['indices_mult' if is_index else 'forex_mult']
        else:
            session_name = 'asian'
            session_mult = self.SESSIONS['asian']['indices_mult' if is_index else 'forex_mult']
        
        logger.info(f"   📊 Session: {session_name.upper()} (UTC {current_hour}:00) → {session_mult:.2f}x for {'index' if is_index else 'forex'}")
        
        return session_mult
    
    def get_win_rate_multiplier(self, symbol: str) -> float:
        """
        Calculate position size multiplier based on symbol's win rate.
        
        >60% win rate = increase size
        <40% win rate = decrease size
        """
        symbol_lower = symbol.lower().replace('.sim', '').replace('z25', '')
        
        if symbol_lower not in self.win_rate_tracker:
            return 1.0  # No history, default size
        
        tracker = self.win_rate_tracker[symbol_lower]
        total_trades = tracker['wins'] + tracker['losses']
        
        if total_trades < 5:
            return 1.0  # Not enough data
        
        # Use recent win rate (last 10) for more responsive adjustment
        recent_win_rate = sum(tracker['last_10']) / len(tracker['last_10']) if tracker['last_10'] else 0.5
        
        # Also consider streak
        streak = tracker['streak']
        
        # Calculate multiplier
        if recent_win_rate >= 0.7:
            multiplier = 1.3  # 30% boost for hot symbol
        elif recent_win_rate >= 0.6:
            multiplier = 1.15  # 15% boost
        elif recent_win_rate >= 0.5:
            multiplier = 1.0  # Normal
        elif recent_win_rate >= 0.4:
            multiplier = 0.8  # 20% reduction
        else:
            multiplier = 0.5  # 50% reduction for cold symbol
        
        # Streak adjustment
        if streak >= 3:
            multiplier *= 1.1  # Hot streak bonus
        elif streak <= -3:
            multiplier *= 0.8  # Cold streak penalty
        
        logger.info(f"   📊 Win Rate: {symbol_lower.upper()} recent={recent_win_rate*100:.0f}% streak={streak} → {multiplier:.2f}x")
        
        return multiplier
    
    def get_recovery_mode_multiplier(self) -> float:
        """
        Get position size multiplier for recovery mode.
        
        In recovery mode, only take A+ setups with reduced size.
        """
        if not self.recovery_mode:
            return 1.0
        
        logger.warning(f"   🚨 RECOVERY MODE: 0.5x size (only A+ setups)")
        return 0.5
    
    def get_total_multiplier(
        self,
        symbol: str,
        open_positions: List[str],
        ml_confidence: float = 50.0,
        market_score: float = 50.0
    ) -> Dict:
        """
        Calculate total position size multiplier combining all factors.
        
        Returns dict with:
        - total_multiplier: Combined multiplier
        - should_trade: Whether to take the trade
        - reason: Explanation
        - breakdown: Individual multipliers
        """
        
        # Get individual multipliers
        correlation_mult = self.get_correlation_multiplier(symbol, open_positions)
        session_mult = self.get_session_multiplier(symbol)
        win_rate_mult = self.get_win_rate_multiplier(symbol)
        recovery_mult = self.get_recovery_mode_multiplier()
        
        # Combine multipliers
        total_mult = correlation_mult * session_mult * win_rate_mult * recovery_mult
        
        # Recovery mode: Only take A+ setups
        should_trade = True
        reason = "Normal trading"
        
        if self.recovery_mode:
            # A+ setup = ML confidence > 70% AND market score > 65
            if ml_confidence < 70 or market_score < 65:
                should_trade = False
                reason = f"Recovery mode: Need A+ setup (ML>{70}%, Score>{65}), got ML={ml_confidence:.0f}%, Score={market_score:.0f}"
            else:
                reason = "Recovery mode: A+ setup approved"
        
        # Don't trade if multiplier is too low
        if total_mult < 0.2:
            should_trade = False
            reason = f"Total multiplier too low: {total_mult:.2f}x"
        
        logger.info(f"   📊 FTMO Strategy Total: {total_mult:.2f}x")
        logger.info(f"      Correlation: {correlation_mult:.2f}x | Session: {session_mult:.2f}x")
        logger.info(f"      Win Rate: {win_rate_mult:.2f}x | Recovery: {recovery_mult:.2f}x")
        
        return {
            'total_multiplier': total_mult,
            'should_trade': should_trade,
            'reason': reason,
            'breakdown': {
                'correlation': correlation_mult,
                'session': session_mult,
                'win_rate': win_rate_mult,
                'recovery': recovery_mult
            }
        }


# Singleton instance
_ftmo_strategy: Optional[FTMOStrategy] = None


def get_ftmo_strategy() -> FTMOStrategy:
    """Get or create the FTMO strategy singleton"""
    global _ftmo_strategy
    if _ftmo_strategy is None:
        _ftmo_strategy = FTMOStrategy()
    return _ftmo_strategy
