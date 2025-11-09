"""
Portfolio Optimization for Multi-Symbol Trading
Modern Portfolio Theory + Risk Management
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from scipy.optimize import minimize


class PortfolioOptimizer:
    """
    Optimize position sizes across multiple symbols
    
    Uses:
    - Modern Portfolio Theory (MPT)
    - Correlation-based risk management
    - Sharpe ratio maximization
    - FTMO constraint compliance
    """
    
    def __init__(self, symbols: List[str]):
        """
        Initialize portfolio optimizer
        
        Args:
            symbols: List of trading symbols
        """
        self.symbols = symbols
        self.n_symbols = len(symbols)
        self.correlations = None
        self.returns_history = {}
        
    def update_correlations(self, price_data: Dict[str, List[float]]):
        """
        Update correlation matrix from price data
        
        Args:
            price_data: {symbol: [prices...]}
        """
        # Convert to DataFrame
        df = pd.DataFrame(price_data)
        
        # Calculate returns
        returns = df.pct_change().dropna()
        
        # Calculate correlation matrix
        self.correlations = returns.corr().values
        
        # Store returns for later use
        for symbol in self.symbols:
            if symbol in price_data:
                self.returns_history[symbol] = returns[symbol].values
    
    def optimize_position_sizes(
        self,
        signals: List[Dict],
        account_balance: float,
        max_total_risk: float = 0.10,  # 10% max total portfolio risk
        max_per_symbol: float = 0.30   # 30% max per symbol
    ) -> Dict[str, float]:
        """
        Optimize position sizes across portfolio
        
        Args:
            signals: List of {
                'symbol': str,
                'direction': str,
                'confidence': float,
                'expected_return': float,
                'risk': float
            }
            account_balance: Current account balance
            max_total_risk: Maximum total portfolio risk
            max_per_symbol: Maximum allocation per symbol
            
        Returns:
            {symbol: position_size_dollars}
        """
        if not signals:
            return {}
        
        # If no correlations, use equal weighting
        if self.correlations is None:
            return self._equal_weight_allocation(signals, account_balance, max_per_symbol)
        
        # Extract signal data
        symbols = [s['symbol'] for s in signals]
        expected_returns = np.array([s.get('expected_return', 0.01) for s in signals])
        risks = np.array([s.get('risk', 0.02) for s in signals])
        confidences = np.array([s.get('confidence', 0.5) for s in signals])
        
        # Get correlation submatrix for these symbols
        symbol_indices = [self.symbols.index(s) if s in self.symbols else 0 for s in symbols]
        corr_matrix = self.correlations[np.ix_(symbol_indices, symbol_indices)]
        
        # Objective: Maximize Sharpe ratio
        def portfolio_sharpe(weights):
            """Calculate negative Sharpe ratio (for minimization)"""
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_variance = np.dot(weights, np.dot(corr_matrix * np.outer(risks, risks), weights))
            portfolio_std = np.sqrt(portfolio_variance)
            
            if portfolio_std == 0:
                return 0
            
            sharpe = portfolio_return / portfolio_std
            return -sharpe  # Negative for minimization
        
        # Constraints
        constraints = [
            # Weights sum to 1
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
            # Total risk constraint
            {'type': 'ineq', 'fun': lambda w: max_total_risk - np.dot(w, risks)}
        ]
        
        # Bounds: 0 to max_per_symbol for each weight
        bounds = [(0, max_per_symbol) for _ in range(len(signals))]
        
        # Initial guess: weighted by confidence
        initial_weights = confidences / confidences.sum()
        
        # Optimize
        result = minimize(
            portfolio_sharpe,
            x0=initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        if not result.success:
            # Fallback to confidence-weighted
            return self._confidence_weighted_allocation(signals, account_balance, max_per_symbol)
        
        # Convert weights to dollar amounts
        optimal_weights = result.x
        position_sizes = {}
        
        for i, signal in enumerate(signals):
            position_sizes[signal['symbol']] = optimal_weights[i] * account_balance
        
        return position_sizes
    
    def _equal_weight_allocation(
        self,
        signals: List[Dict],
        account_balance: float,
        max_per_symbol: float
    ) -> Dict[str, float]:
        """Equal weight allocation"""
        weight_per_symbol = min(1.0 / len(signals), max_per_symbol)
        
        return {
            signal['symbol']: weight_per_symbol * account_balance
            for signal in signals
        }
    
    def _confidence_weighted_allocation(
        self,
        signals: List[Dict],
        account_balance: float,
        max_per_symbol: float
    ) -> Dict[str, float]:
        """Confidence-weighted allocation"""
        confidences = np.array([s.get('confidence', 0.5) for s in signals])
        total_confidence = confidences.sum()
        
        if total_confidence == 0:
            return self._equal_weight_allocation(signals, account_balance, max_per_symbol)
        
        weights = confidences / total_confidence
        weights = np.minimum(weights, max_per_symbol)  # Cap at max
        weights = weights / weights.sum()  # Renormalize
        
        return {
            signal['symbol']: weights[i] * account_balance
            for i, signal in enumerate(signals)
        }
    
    def calculate_portfolio_risk(self, positions: Dict[str, float]) -> Dict:
        """
        Calculate portfolio risk metrics
        
        Args:
            positions: {symbol: position_size_dollars}
            
        Returns:
            {
                'total_exposure': float,
                'portfolio_variance': float,
                'portfolio_std': float,
                'diversification_ratio': float,
                'max_correlation': float
            }
        """
        if not positions or self.correlations is None:
            return {
                'total_exposure': sum(positions.values()),
                'portfolio_variance': 0,
                'portfolio_std': 0,
                'diversification_ratio': 1.0,
                'max_correlation': 0
            }
        
        # Get position weights
        total_exposure = sum(positions.values())
        weights = np.array([positions.get(s, 0) / total_exposure if total_exposure > 0 else 0 
                           for s in self.symbols])
        
        # Calculate portfolio variance
        portfolio_variance = np.dot(weights, np.dot(self.correlations, weights))
        portfolio_std = np.sqrt(portfolio_variance)
        
        # Diversification ratio
        individual_std = np.sqrt(np.diag(self.correlations))
        weighted_avg_std = np.dot(weights, individual_std)
        diversification_ratio = weighted_avg_std / portfolio_std if portfolio_std > 0 else 1.0
        
        # Max correlation
        max_correlation = np.max(np.abs(self.correlations[np.triu_indices_from(self.correlations, k=1)]))
        
        return {
            'total_exposure': total_exposure,
            'portfolio_variance': portfolio_variance,
            'portfolio_std': portfolio_std,
            'diversification_ratio': diversification_ratio,
            'max_correlation': max_correlation
        }
    
    def get_hedging_recommendations(self, positions: Dict[str, float]) -> List[Dict]:
        """
        Recommend hedging positions based on correlations
        
        Args:
            positions: Current positions {symbol: size}
            
        Returns:
            List of hedging recommendations
        """
        if self.correlations is None:
            return []
        
        recommendations = []
        
        # Find highly correlated pairs
        for i in range(self.n_symbols):
            for j in range(i + 1, self.n_symbols):
                corr = self.correlations[i, j]
                
                # High positive correlation (>0.7) - consider reducing one
                if corr > 0.7:
                    symbol1 = self.symbols[i]
                    symbol2 = self.symbols[j]
                    
                    if symbol1 in positions and symbol2 in positions:
                        recommendations.append({
                            'type': 'reduce_correlation',
                            'symbols': [symbol1, symbol2],
                            'correlation': corr,
                            'action': f'Consider reducing exposure to {symbol1} or {symbol2} (highly correlated)'
                        })
                
                # High negative correlation (<-0.7) - natural hedge
                elif corr < -0.7:
                    symbol1 = self.symbols[i]
                    symbol2 = self.symbols[j]
                    
                    recommendations.append({
                        'type': 'natural_hedge',
                        'symbols': [symbol1, symbol2],
                        'correlation': corr,
                        'action': f'{symbol1} and {symbol2} are negatively correlated - natural hedge'
                    })
        
        return recommendations


# Example usage
if __name__ == "__main__":
    symbols = ['US30', 'US100', 'US500', 'EURUSD', 'GBPUSD', 'USDJPY', 'XAU', 'USOIL']
    optimizer = PortfolioOptimizer(symbols)
    
    # Simulate price data
    price_data = {
        symbol: np.random.randn(100).cumsum() + 100
        for symbol in symbols
    }
    
    optimizer.update_correlations(price_data)
    
    # Simulate signals
    signals = [
        {'symbol': 'US30', 'direction': 'BUY', 'confidence': 0.8, 'expected_return': 0.02, 'risk': 0.015},
        {'symbol': 'EURUSD', 'direction': 'BUY', 'confidence': 0.6, 'expected_return': 0.015, 'risk': 0.012},
        {'symbol': 'XAU', 'direction': 'SELL', 'confidence': 0.7, 'expected_return': 0.018, 'risk': 0.020},
    ]
    
    # Optimize
    positions = optimizer.optimize_position_sizes(signals, account_balance=100000)
    
    print("Optimized Positions:")
    for symbol, size in positions.items():
        print(f"  {symbol}: ${size:,.2f} ({size/100000*100:.1f}%)")
    
    # Calculate risk
    risk_metrics = optimizer.calculate_portfolio_risk(positions)
    print(f"\nPortfolio Risk:")
    print(f"  Total Exposure: ${risk_metrics['total_exposure']:,.2f}")
    print(f"  Portfolio Std: {risk_metrics['portfolio_std']:.4f}")
    print(f"  Diversification Ratio: {risk_metrics['diversification_ratio']:.2f}")
    print(f"  Max Correlation: {risk_metrics['max_correlation']:.2f}")
