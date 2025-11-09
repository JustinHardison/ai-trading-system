"""
Trade Performance Tracker - Hedge Fund Grade
Tracks every trade with full metrics for continuous improvement
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np


class TradeTracker:
    """Track and analyze trade performance in real-time"""
    
    def __init__(self, log_file='/tmp/trade_performance.json'):
        self.log_file = log_file
        self.trades = self._load_trades()
    
    def _load_trades(self) -> List[Dict]:
        """Load existing trades from file"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_trades(self):
        """Save trades to file"""
        try:
            with open(self.log_file, 'w') as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            print(f"Error saving trades: {e}")
    
    def log_entry(self, symbol: str, direction: str, entry_price: float, 
                  lots: float, score: float, ml_confidence: float, 
                  signals: List[str], context: Dict = None):
        """Log trade entry with full context"""
        trade = {
            'id': f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'lots': lots,
            'entry_time': datetime.now().isoformat(),
            'entry_score': score,
            'ml_confidence': ml_confidence,
            'signals': signals,
            'context': context or {},
            'outcome': None,
            'exit_price': None,
            'exit_time': None,
            'profit': None,
            'pips': None,
            'exit_reason': None,
            'duration_minutes': None
        }
        self.trades.append(trade)
        self._save_trades()
        return trade['id']
    
    def log_exit(self, symbol: str, exit_price: float, profit: float, 
                 reason: str, exit_score: float = None):
        """Log trade exit"""
        for trade in reversed(self.trades):
            if trade['symbol'] == symbol and trade['outcome'] is None:
                trade['outcome'] = 'WIN' if profit > 0 else 'LOSS'
                trade['exit_price'] = exit_price
                trade['exit_time'] = datetime.now().isoformat()
                trade['profit'] = profit
                trade['exit_reason'] = reason
                trade['exit_score'] = exit_score
                
                # Calculate pips
                pip_value = 0.0001 if 'JPY' not in symbol else 0.01
                trade['pips'] = (exit_price - trade['entry_price']) / pip_value
                if trade['direction'] == 'SELL':
                    trade['pips'] *= -1
                
                # Calculate duration
                entry_time = datetime.fromisoformat(trade['entry_time'])
                exit_time = datetime.fromisoformat(trade['exit_time'])
                trade['duration_minutes'] = (exit_time - entry_time).total_seconds() / 60
                
                self._save_trades()
                break
    
    def get_stats(self, symbol: str = None, last_n: int = None) -> Dict:
        """Get performance statistics"""
        trades = self.trades
        
        # Filter by symbol if specified
        if symbol:
            trades = [t for t in trades if t['symbol'] == symbol]
        
        # Filter by last N trades
        if last_n:
            trades = trades[-last_n:]
        
        # Only completed trades
        completed = [t for t in trades if t['outcome'] is not None]
        
        if not completed:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'avg_duration': 0
            }
        
        wins = [t for t in completed if t['outcome'] == 'WIN']
        losses = [t for t in completed if t['outcome'] == 'LOSS']
        
        total_wins = sum(t['profit'] for t in wins)
        total_losses = abs(sum(t['profit'] for t in losses))
        
        return {
            'total_trades': len(completed),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(completed) if completed else 0,
            'avg_win': np.mean([t['profit'] for t in wins]) if wins else 0,
            'avg_loss': np.mean([t['profit'] for t in losses]) if losses else 0,
            'total_profit': sum(t['profit'] for t in completed),
            'profit_factor': total_wins / total_losses if total_losses > 0 else 0,
            'avg_duration': np.mean([t['duration_minutes'] for t in completed if t['duration_minutes']]),
            'avg_entry_score': np.mean([t['entry_score'] for t in completed]),
            'avg_ml_confidence': np.mean([t['ml_confidence'] for t in completed])
        }
    
    def get_best_setups(self, min_trades: int = 5) -> List[Dict]:
        """Identify highest performing setups"""
        completed = [t for t in self.trades if t['outcome'] is not None]
        
        # Group by primary signal
        setups = {}
        for trade in completed:
            if not trade.get('signals'):
                continue
            primary_signal = trade['signals'][0] if trade['signals'] else 'unknown'
            
            if primary_signal not in setups:
                setups[primary_signal] = []
            setups[primary_signal].append(trade)
        
        # Calculate stats for each setup
        results = []
        for signal, trades in setups.items():
            if len(trades) < min_trades:
                continue
            
            wins = [t for t in trades if t['outcome'] == 'WIN']
            win_rate = len(wins) / len(trades)
            avg_profit = np.mean([t['profit'] for t in trades])
            
            results.append({
                'signal': signal,
                'trades': len(trades),
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'total_profit': sum(t['profit'] for t in trades)
            })
        
        # Sort by total profit
        results.sort(key=lambda x: x['total_profit'], reverse=True)
        return results
    
    def get_worst_setups(self, min_trades: int = 5) -> List[Dict]:
        """Identify lowest performing setups to avoid"""
        best = self.get_best_setups(min_trades)
        return sorted(best, key=lambda x: x['total_profit'])[:5]


# Global tracker instance
_tracker = None

def get_tracker() -> TradeTracker:
    """Get global tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = TradeTracker()
    return _tracker
