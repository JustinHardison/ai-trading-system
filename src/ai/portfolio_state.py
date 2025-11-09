"""
Portfolio State Tracker - Elite Hedge Fund Grade
Tracks correlation, risk attribution, and performance for optimal position sizing
"""
import logging
from typing import Dict, List
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


class PortfolioState:
    """
    Track portfolio state for elite position sizing
    
    Features:
    - Correlation matrix between symbols
    - Risk attribution per position
    - Recent performance metrics
    - Dynamic risk budget allocation
    """
    
    def __init__(self):
        # Static correlation matrix (fallback)
        self.static_correlation_matrix = {
            # Forex correlations
            ('eurusd', 'gbpusd'): 0.7,
            ('eurusd', 'usdjpy'): -0.5,
            ('gbpusd', 'usdjpy'): -0.4,
            
            # Indices correlations (highly correlated)
            ('us30', 'us100'): 0.85,
            ('us30', 'us500'): 0.90,
            ('us100', 'us500'): 0.88,
            
            # Commodities
            ('xau', 'usoil'): 0.3,
            
            # Cross-asset (low correlation - good for diversification)
            ('eurusd', 'us30'): 0.2,
            ('xau', 'us30'): -0.1,
            ('usoil', 'us30'): 0.4,
            ('xau', 'us100'): -0.15,
            ('xau', 'us500'): -0.1,
            ('eurusd', 'xau'): 0.3,
        }
        
        # Dynamic correlation matrix (updated from real-time data)
        self.dynamic_correlation_matrix = {}
        
        # Price history for real-time correlation calculation
        self.price_history = {}  # symbol -> list of (timestamp, price)
        self.max_history_size = 100  # Keep last 100 prices per symbol
        
        # Recent trades for performance tracking
        self.recent_trades = []  # Last 20 trades
        
        # Current risk attribution
        self.position_risks = {}  # symbol -> risk_dollars
        
        # Correlation matrix (combined static + dynamic)
        self.correlation_matrix = self.static_correlation_matrix.copy()
    
    def update_price(self, symbol: str, price: float, timestamp: datetime = None):
        """
        Update price history for real-time correlation calculation
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        symbol_clean = self._clean_symbol(symbol)
        
        if symbol_clean not in self.price_history:
            self.price_history[symbol_clean] = []
        
        self.price_history[symbol_clean].append((timestamp, price))
        
        # Keep only last N prices
        if len(self.price_history[symbol_clean]) > self.max_history_size:
            self.price_history[symbol_clean] = self.price_history[symbol_clean][-self.max_history_size:]
        
        # Recalculate correlations if we have enough data
        if len(self.price_history[symbol_clean]) >= 20:
            self._update_dynamic_correlations(symbol_clean)
    
    def _clean_symbol(self, symbol: str) -> str:
        """Clean symbol name for correlation lookup"""
        s = symbol.lower()
        # Remove common suffixes
        for suffix in ['.sim', 'z25', 'f26', 'g26', 'h26', 'j26', 'k26', 'm26', 'n26', 'q26', 'u26', 'v26', 'x26']:
            s = s.replace(suffix, '')
        return s
    
    def _update_dynamic_correlations(self, symbol: str):
        """
        Calculate real-time correlations with other symbols
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < 20:
            return
        
        symbol_prices = [p[1] for p in self.price_history[symbol][-50:]]
        symbol_returns = np.diff(symbol_prices) / symbol_prices[:-1] if len(symbol_prices) > 1 else []
        
        if len(symbol_returns) < 10:
            return
        
        for other_symbol, other_history in self.price_history.items():
            if other_symbol == symbol or len(other_history) < 20:
                continue
            
            other_prices = [p[1] for p in other_history[-50:]]
            other_returns = np.diff(other_prices) / other_prices[:-1] if len(other_prices) > 1 else []
            
            if len(other_returns) < 10:
                continue
            
            # Align lengths
            min_len = min(len(symbol_returns), len(other_returns))
            if min_len < 10:
                continue
            
            try:
                corr = np.corrcoef(symbol_returns[-min_len:], other_returns[-min_len:])[0, 1]
                if not np.isnan(corr):
                    # Update dynamic correlation
                    pair = tuple(sorted([symbol, other_symbol]))
                    self.dynamic_correlation_matrix[pair] = corr
                    
                    # Blend with static (70% dynamic, 30% static for stability)
                    static_corr = self.static_correlation_matrix.get(pair, 0.0)
                    if static_corr == 0.0:
                        static_corr = self.static_correlation_matrix.get((pair[1], pair[0]), 0.0)
                    
                    blended = corr * 0.7 + static_corr * 0.3
                    self.correlation_matrix[pair] = blended
            except Exception:
                pass  # Skip on calculation errors
        
    def get_correlation(self, symbol1: str, symbol2: str, direction1: str, direction2: str) -> float:
        """
        Get correlation between two positions
        
        Args:
            symbol1, symbol2: Trading symbols (cleaned)
            direction1, direction2: 'BUY' or 'SELL'
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        # Clean symbols
        s1 = symbol1.lower().replace('usd', '').replace('jpy', '')
        s2 = symbol2.lower().replace('usd', '').replace('jpy', '')
        
        # Same symbol = perfect correlation
        if s1 == s2:
            return 1.0 if direction1 == direction2 else -1.0
        
        # Look up in matrix
        base_corr = self.correlation_matrix.get((s1, s2), 0.0)
        if base_corr == 0.0:
            base_corr = self.correlation_matrix.get((s2, s1), 0.0)
        
        # Adjust for direction
        if direction1 != direction2:
            base_corr = -base_corr
        
        return base_corr
    
    def calculate_portfolio_correlation(
        self,
        new_symbol: str,
        new_direction: str,
        open_positions: List[Dict]
    ) -> float:
        """
        Calculate average correlation of new position with existing portfolio
        
        Returns:
            Average correlation (0-1, absolute value)
        """
        if not open_positions:
            return 0.0  # No correlation with empty portfolio
        
        correlations = []
        for pos in open_positions:
            pos_symbol = pos.get('symbol', '').lower()
            pos_type = pos.get('type', 0)
            pos_direction = 'BUY' if pos_type == 0 else 'SELL'
            
            corr = self.get_correlation(new_symbol, pos_symbol, new_direction, pos_direction)
            correlations.append(abs(corr))  # Use absolute value
        
        avg_corr = np.mean(correlations) if correlations else 0.0
        
        logger.info(f"   Portfolio Correlation: {avg_corr:.2f} (lower = better diversification)")
        
        return avg_corr
    
    def calculate_diversification_factor(self, avg_correlation: float) -> float:
        """
        Convert correlation to diversification bonus
        
        Low correlation = size up (diversifies portfolio)
        High correlation = size down (concentrates risk)
        
        Returns:
            Multiplier (0.5 - 1.5)
        """
        # Diversification factor = 1.0 - (correlation * 0.5)
        # correlation=0.0 → factor=1.0 (neutral)
        # correlation=0.5 → factor=0.75 (reduce size 25%)
        # correlation=1.0 → factor=0.5 (reduce size 50%)
        
        factor = 1.0 - (avg_correlation * 0.5)
        
        logger.info(f"   Diversification Factor: {factor:.2f}x")
        
        return max(0.5, min(1.5, factor))
    
    def add_trade_result(self, symbol: str, profit: float, win: bool):
        """Track trade result for performance feedback"""
        self.recent_trades.append({
            'symbol': symbol,
            'profit': profit,
            'win': win,
            'timestamp': datetime.now()
        })
        
        # Keep only last 20
        if len(self.recent_trades) > 20:
            self.recent_trades = self.recent_trades[-20:]
    
    def calculate_recent_performance(self, last_n: int = 10) -> Dict:
        """
        Calculate recent performance metrics
        
        Returns:
            {
                'win_rate': float (0-1),
                'avg_profit': float,
                'sharpe_estimate': float,
                'performance_multiplier': float (0.7-1.3)
            }
        """
        if not self.recent_trades:
            return {
                'win_rate': 0.5,
                'avg_profit': 0.0,
                'sharpe_estimate': 0.0,
                'performance_multiplier': 1.0
            }
        
        recent = self.recent_trades[-last_n:]
        
        win_rate = sum(1 for t in recent if t['win']) / len(recent)
        avg_profit = np.mean([t['profit'] for t in recent])
        std_profit = np.std([t['profit'] for t in recent]) if len(recent) > 1 else 1.0
        
        sharpe_estimate = avg_profit / std_profit if std_profit > 0 else 0.0
        
        # Performance multiplier: 0.7-1.3
        # win_rate < 0.4 → 0.7x (system struggling)
        # win_rate = 0.5 → 1.0x (neutral)
        # win_rate > 0.6 → 1.3x (system working well)
        
        if win_rate < 0.4:
            multiplier = 0.7
        elif win_rate > 0.6:
            multiplier = 1.3
        else:
            # Linear interpolation between 0.4-0.6
            multiplier = 0.7 + (win_rate - 0.4) * 3.0  # 0.7 to 1.3
        
        logger.info(f"   Recent Performance: WR={win_rate:.1%}, Avg=${avg_profit:.0f}, Sharpe={sharpe_estimate:.2f}")
        logger.info(f"   Performance Multiplier: {multiplier:.2f}x")
        
        return {
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'sharpe_estimate': sharpe_estimate,
            'performance_multiplier': multiplier
        }
    
    def update_position_risk(self, symbol: str, risk_dollars: float):
        """Update risk attribution for a position"""
        self.position_risks[symbol] = risk_dollars
    
    def get_total_portfolio_risk(self) -> float:
        """Get total risk across all positions"""
        return sum(self.position_risks.values())
    
    def calculate_concentration_limit(
        self,
        daily_risk_budget: float,
        max_concentration_pct: float = 0.30
    ) -> float:
        """
        Calculate maximum additional risk allowed (concentration limit)
        
        Args:
            daily_risk_budget: Total risk budget for the day
            max_concentration_pct: Max % of budget in one position
            
        Returns:
            Maximum risk dollars for new position
        """
        current_total_risk = self.get_total_portfolio_risk()
        max_single_position_risk = daily_risk_budget * max_concentration_pct
        
        # How much risk is available?
        available_risk = max_single_position_risk
        
        logger.info(f"   Portfolio Risk: ${current_total_risk:.0f} / ${daily_risk_budget:.0f}")
        logger.info(f"   Max Single Position: ${max_single_position_risk:.0f} ({max_concentration_pct:.0%})")
        
        return available_risk


# Global instance
_portfolio_state = None

def get_portfolio_state():
    """Get global portfolio state instance"""
    global _portfolio_state
    if _portfolio_state is None:
        _portfolio_state = PortfolioState()
    return _portfolio_state
