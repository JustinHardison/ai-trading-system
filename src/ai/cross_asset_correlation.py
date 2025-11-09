"""
Cross-Asset Correlation Matrix - Hedge Fund Grade
Real-time correlation tracking across all asset classes with regime awareness

Based on institutional approaches:
- Dynamic correlation updates from live price data
- Regime-dependent correlation shifts (correlations change in crisis)
- Cross-asset class analysis (Forex, Indices, Commodities, Bonds proxy)
- Portfolio risk decomposition
"""
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class CrossAssetCorrelationMatrix:
    """
    Hedge fund grade cross-asset correlation tracking
    
    Key Features:
    1. Real-time correlation updates from price returns
    2. Regime-aware correlations (normal vs stress)
    3. Rolling window analysis (short-term vs long-term)
    4. Cross-asset class risk decomposition
    5. Correlation breakdown alerts
    """
    
    def __init__(self):
        # Asset class definitions
        self.asset_classes = {
            'FOREX_MAJOR': ['eurusd', 'gbpusd', 'usdjpy', 'usdchf', 'audusd', 'usdcad'],
            'FOREX_CROSS': ['eurgbp', 'eurjpy', 'gbpjpy', 'audnzd'],
            'INDICES_US': ['us30', 'us100', 'us500'],
            'INDICES_EU': ['de40', 'uk100', 'eu50'],
            'COMMODITIES_METALS': ['xau', 'xag'],
            'COMMODITIES_ENERGY': ['usoil', 'ukoil', 'natgas'],
            'RISK_PROXY': ['vix']  # If available
        }
        
        # Flatten for lookup
        self.symbol_to_class = {}
        for asset_class, symbols in self.asset_classes.items():
            for symbol in symbols:
                self.symbol_to_class[symbol] = asset_class
        
        # ═══════════════════════════════════════════════════════════
        # INSTITUTIONAL CORRELATION MATRIX
        # Based on historical analysis of asset correlations
        # These are "normal regime" correlations - stress regime differs
        # ═══════════════════════════════════════════════════════════
        
        self.base_correlations = {
            # US Indices (highly correlated with each other)
            ('us30', 'us100'): 0.85,
            ('us30', 'us500'): 0.92,
            ('us100', 'us500'): 0.90,
            
            # EU Indices
            ('de40', 'uk100'): 0.75,
            ('de40', 'eu50'): 0.95,
            ('uk100', 'eu50'): 0.80,
            
            # US vs EU Indices
            ('us500', 'de40'): 0.70,
            ('us500', 'uk100'): 0.65,
            ('us100', 'de40'): 0.65,
            
            # Gold correlations (safe haven)
            ('xau', 'us500'): -0.15,  # Negative in normal times
            ('xau', 'us100'): -0.20,
            ('xau', 'us30'): -0.10,
            ('xau', 'eurusd'): 0.40,  # Gold moves with EUR (anti-USD)
            ('xau', 'usdjpy'): -0.35,  # Gold inverse to USD strength
            ('xau', 'usoil'): 0.25,   # Commodities correlation
            ('xau', 'xag'): 0.85,     # Gold-Silver highly correlated
            
            # Oil correlations
            ('usoil', 'ukoil'): 0.98,  # WTI-Brent almost perfect
            ('usoil', 'us500'): 0.30,  # Oil-Stocks moderate positive
            ('usoil', 'usdcad'): -0.50,  # Oil inverse to CAD (Canada = oil exporter)
            
            # Forex correlations
            ('eurusd', 'gbpusd'): 0.75,  # EUR-GBP move together vs USD
            ('eurusd', 'usdjpy'): -0.45,  # EUR and JPY both anti-USD
            ('eurusd', 'usdchf'): -0.90,  # EUR-CHF almost inverse
            ('gbpusd', 'usdjpy'): -0.35,
            ('audusd', 'usdcad'): -0.60,  # Commodity currencies
            ('audusd', 'us500'): 0.40,   # AUD = risk-on currency
            
            # Cross rates
            ('eurgbp', 'eurusd'): 0.50,
            ('eurjpy', 'usdjpy'): 0.70,
            ('gbpjpy', 'usdjpy'): 0.80,
        }
        
        # ═══════════════════════════════════════════════════════════
        # STRESS REGIME CORRELATIONS
        # During market stress, correlations tend toward 1 or -1
        # "All correlations go to 1 in a crisis" - except safe havens
        # ═══════════════════════════════════════════════════════════
        
        self.stress_correlations = {
            # Risk assets correlate more in stress
            ('us30', 'us100'): 0.95,
            ('us30', 'us500'): 0.98,
            ('us100', 'us500'): 0.97,
            ('us500', 'de40'): 0.85,
            ('us500', 'uk100'): 0.80,
            
            # Safe havens become MORE negative
            ('xau', 'us500'): -0.40,
            ('xau', 'us100'): -0.45,
            ('usdjpy', 'us500'): -0.50,  # JPY = safe haven
            
            # Oil crashes with stocks in stress
            ('usoil', 'us500'): 0.60,
            
            # Forex correlations increase
            ('eurusd', 'gbpusd'): 0.85,
            ('audusd', 'us500'): 0.65,
        }
        
        # Price history for dynamic correlation calculation
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = defaultdict(list)
        self.return_history: Dict[str, List[float]] = defaultdict(list)
        self.max_history = 500  # Keep 500 data points per symbol
        
        # Dynamic correlation cache
        self.dynamic_correlations: Dict[Tuple[str, str], float] = {}
        self.last_correlation_update = datetime.now()
        self.correlation_update_interval = timedelta(minutes=5)
        
        # Current regime
        self.current_regime = 'NORMAL'  # NORMAL, STRESS, RISK_ON, RISK_OFF
        self.regime_history: List[Tuple[datetime, str]] = []
        
    def _clean_symbol(self, symbol: str) -> str:
        """Normalize symbol name"""
        s = symbol.lower()
        # Remove broker suffixes
        for suffix in ['.sim', 'z25', 'f26', 'g26', 'h26', 'j26', 'k26', 'm26', 'n26', 'q26', 'u26', 'v26', 'x26', '.pro']:
            s = s.replace(suffix, '')
        return s
    
    def update_price(self, symbol: str, price: float, timestamp: datetime = None):
        """
        Update price history and recalculate correlations
        
        Called by the API on each price update
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        symbol_clean = self._clean_symbol(symbol)
        
        # Add to price history
        self.price_history[symbol_clean].append((timestamp, price))
        
        # Trim to max size
        if len(self.price_history[symbol_clean]) > self.max_history:
            self.price_history[symbol_clean] = self.price_history[symbol_clean][-self.max_history:]
        
        # Calculate returns if we have enough data
        if len(self.price_history[symbol_clean]) >= 2:
            prices = [p[1] for p in self.price_history[symbol_clean]]
            returns = np.diff(prices) / prices[:-1]
            self.return_history[symbol_clean] = list(returns[-self.max_history:])
        
        # Periodically update correlations
        if datetime.now() - self.last_correlation_update > self.correlation_update_interval:
            self._update_all_correlations()
            self.last_correlation_update = datetime.now()
    
    def _update_all_correlations(self):
        """
        Recalculate all dynamic correlations from return data
        """
        symbols_with_data = [s for s in self.return_history if len(self.return_history[s]) >= 20]
        
        for i, sym1 in enumerate(symbols_with_data):
            for sym2 in symbols_with_data[i+1:]:
                try:
                    returns1 = np.array(self.return_history[sym1][-100:])
                    returns2 = np.array(self.return_history[sym2][-100:])
                    
                    # Align lengths
                    min_len = min(len(returns1), len(returns2))
                    if min_len < 20:
                        continue
                    
                    corr = np.corrcoef(returns1[-min_len:], returns2[-min_len:])[0, 1]
                    
                    if not np.isnan(corr):
                        pair = tuple(sorted([sym1, sym2]))
                        self.dynamic_correlations[pair] = corr
                except Exception:
                    pass
    
    def get_correlation(
        self,
        symbol1: str,
        symbol2: str,
        direction1: str = 'BUY',
        direction2: str = 'BUY',
        use_regime: bool = True
    ) -> float:
        """
        Get correlation between two positions
        
        Combines:
        1. Base institutional correlations
        2. Dynamic real-time correlations (if available)
        3. Regime adjustments (stress vs normal)
        
        Returns: Correlation coefficient (-1 to 1)
        """
        s1 = self._clean_symbol(symbol1)
        s2 = self._clean_symbol(symbol2)
        
        # Same symbol
        if s1 == s2:
            return 1.0 if direction1 == direction2 else -1.0
        
        pair = tuple(sorted([s1, s2]))
        
        # Get base correlation
        base_corr = self.base_correlations.get(pair, 0.0)
        if base_corr == 0.0:
            base_corr = self.base_correlations.get((pair[1], pair[0]), 0.0)
        
        # Get dynamic correlation if available
        dynamic_corr = self.dynamic_correlations.get(pair, None)
        
        # Blend base and dynamic (60% dynamic, 40% base for stability)
        if dynamic_corr is not None:
            corr = dynamic_corr * 0.6 + base_corr * 0.4
        else:
            corr = base_corr
        
        # Apply regime adjustment
        if use_regime and self.current_regime == 'STRESS':
            stress_corr = self.stress_correlations.get(pair, None)
            if stress_corr is not None:
                # In stress, shift toward stress correlation
                corr = corr * 0.5 + stress_corr * 0.5
            else:
                # Risk assets correlate more in stress
                if abs(corr) > 0.3:
                    corr = corr * 1.3  # Amplify existing correlation
                    corr = max(-1.0, min(1.0, corr))
        
        # Adjust for direction
        if direction1 != direction2:
            corr = -corr
        
        return corr
    
    def get_asset_class(self, symbol: str) -> str:
        """Get asset class for a symbol"""
        s = self._clean_symbol(symbol)
        return self.symbol_to_class.get(s, 'UNKNOWN')
    
    def calculate_portfolio_correlation_matrix(
        self,
        positions: List[Dict]
    ) -> Dict:
        """
        Calculate full correlation matrix for current portfolio
        
        Returns:
            {
                'matrix': 2D correlation matrix,
                'symbols': list of symbols,
                'avg_correlation': float,
                'max_correlation': float,
                'risk_concentration': float (0-1),
                'diversification_score': float (0-1)
            }
        """
        if not positions:
            return {
                'matrix': [],
                'symbols': [],
                'avg_correlation': 0.0,
                'max_correlation': 0.0,
                'risk_concentration': 0.0,
                'diversification_score': 1.0
            }
        
        symbols = []
        directions = []
        
        for pos in positions:
            sym = self._clean_symbol(pos.get('symbol', ''))
            direction = 'BUY' if pos.get('type', 0) == 0 else 'SELL'
            symbols.append(sym)
            directions.append(direction)
        
        n = len(symbols)
        matrix = np.eye(n)  # Diagonal = 1
        
        correlations = []
        for i in range(n):
            for j in range(i+1, n):
                corr = self.get_correlation(symbols[i], symbols[j], directions[i], directions[j])
                matrix[i, j] = corr
                matrix[j, i] = corr
                correlations.append(abs(corr))
        
        avg_corr = np.mean(correlations) if correlations else 0.0
        max_corr = np.max(correlations) if correlations else 0.0
        
        # Risk concentration: high if many positions highly correlated
        high_corr_count = sum(1 for c in correlations if c > 0.7)
        risk_concentration = high_corr_count / len(correlations) if correlations else 0.0
        
        # Diversification score: inverse of average correlation
        diversification_score = 1.0 - avg_corr
        
        return {
            'matrix': matrix.tolist(),
            'symbols': symbols,
            'avg_correlation': avg_corr,
            'max_correlation': max_corr,
            'risk_concentration': risk_concentration,
            'diversification_score': diversification_score
        }
    
    def calculate_cross_asset_exposure(
        self,
        positions: List[Dict]
    ) -> Dict:
        """
        Calculate exposure by asset class
        
        Returns exposure breakdown and concentration warnings
        """
        exposure_by_class = defaultdict(float)
        positions_by_class = defaultdict(list)
        
        for pos in positions:
            sym = self._clean_symbol(pos.get('symbol', ''))
            asset_class = self.get_asset_class(sym)
            volume = float(pos.get('volume', 0))
            profit = float(pos.get('profit', 0))
            
            exposure_by_class[asset_class] += volume
            positions_by_class[asset_class].append({
                'symbol': sym,
                'volume': volume,
                'profit': profit
            })
        
        total_exposure = sum(exposure_by_class.values())
        
        # Calculate concentration percentages
        concentration = {}
        warnings = []
        
        for asset_class, exposure in exposure_by_class.items():
            pct = (exposure / total_exposure * 100) if total_exposure > 0 else 0
            concentration[asset_class] = pct
            
            # Warn if over-concentrated
            if pct > 50:
                warnings.append(f"HIGH concentration in {asset_class}: {pct:.0f}%")
            elif pct > 30:
                warnings.append(f"Moderate concentration in {asset_class}: {pct:.0f}%")
        
        return {
            'exposure_by_class': dict(exposure_by_class),
            'concentration_pct': concentration,
            'positions_by_class': dict(positions_by_class),
            'total_exposure': total_exposure,
            'warnings': warnings,
            'is_diversified': len(exposure_by_class) >= 2 and max(concentration.values()) < 60
        }
    
    def update_regime(self, regime: str):
        """
        Update market regime (called by regime detector)
        
        Regimes: NORMAL, STRESS, RISK_ON, RISK_OFF
        """
        if regime != self.current_regime:
            self.regime_history.append((datetime.now(), regime))
            logger.info(f"📊 REGIME CHANGE: {self.current_regime} → {regime}")
            self.current_regime = regime
            
            # Keep last 100 regime changes
            if len(self.regime_history) > 100:
                self.regime_history = self.regime_history[-100:]
    
    def get_new_position_correlation(
        self,
        new_symbol: str,
        new_direction: str,
        positions: List[Dict]
    ) -> Dict:
        """
        Analyze how a new position would affect portfolio correlation
        
        Returns recommendation on whether to add the position
        """
        if not positions:
            return {
                'avg_correlation': 0.0,
                'max_correlation': 0.0,
                'recommendation': 'ALLOW',
                'reason': 'First position - no correlation concerns'
            }
        
        correlations = []
        high_corr_positions = []
        
        for pos in positions:
            sym = self._clean_symbol(pos.get('symbol', ''))
            direction = 'BUY' if pos.get('type', 0) == 0 else 'SELL'
            
            corr = self.get_correlation(new_symbol, sym, new_direction, direction)
            correlations.append(abs(corr))
            
            if abs(corr) > 0.7:
                high_corr_positions.append((sym, corr))
        
        avg_corr = np.mean(correlations)
        max_corr = np.max(correlations)
        
        # Recommendation logic
        if max_corr > 0.85:
            recommendation = 'REDUCE_SIZE'
            reason = f"Very high correlation ({max_corr:.2f}) with {high_corr_positions[0][0]}"
        elif avg_corr > 0.6:
            recommendation = 'REDUCE_SIZE'
            reason = f"High average correlation ({avg_corr:.2f}) - reduces diversification"
        elif avg_corr < 0.3:
            recommendation = 'ALLOW_BOOST'
            reason = f"Low correlation ({avg_corr:.2f}) - good diversification"
        else:
            recommendation = 'ALLOW'
            reason = f"Moderate correlation ({avg_corr:.2f})"
        
        return {
            'avg_correlation': avg_corr,
            'max_correlation': max_corr,
            'high_corr_positions': high_corr_positions,
            'recommendation': recommendation,
            'reason': reason
        }


# Global instance
_cross_asset_matrix = None

def get_cross_asset_matrix() -> CrossAssetCorrelationMatrix:
    """Get global cross-asset correlation matrix instance"""
    global _cross_asset_matrix
    if _cross_asset_matrix is None:
        _cross_asset_matrix = CrossAssetCorrelationMatrix()
    return _cross_asset_matrix
