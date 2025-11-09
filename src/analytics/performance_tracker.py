"""
Performance Tracker - Real-time Trading Metrics
Logs trades to CSV and calculates live performance metrics
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
from loguru import logger


class PerformanceTracker:
    """
    Track and analyze trading performance in real-time

    Features:
    1. CSV trade logging
    2. Win rate calculation
    3. Risk/Reward ratio
    4. Sharpe ratio
    5. Maximum drawdown
    6. Profit factor
    """

    def __init__(self, log_file: str = "/tmp/trades.csv"):
        self.log_file = log_file
        self.trades: List[Dict] = []

        # Create log file with headers if it doesn't exist
        if not os.path.exists(self.log_file):
            self._create_log_file()

        # Load existing trades
        self._load_trades()

        logger.info(f"Performance Tracker initialized: {len(self.trades)} trades loaded")

    def _create_log_file(self):
        """Create CSV file with headers"""
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'symbol',
                'direction',
                'entry_price',
                'exit_price',
                'lots',
                'profit_points',
                'profit_usd',
                'profit_pct',
                'bars_held',
                'win',
                'strategy',
                'ml_confidence',
                'exit_reason'
            ])

    def _load_trades(self):
        """Load trades from CSV file"""
        if not os.path.exists(self.log_file):
            return

        try:
            with open(self.log_file, 'r') as f:
                reader = csv.DictReader(f)
                self.trades = list(reader)

                # Convert numeric fields
                for trade in self.trades:
                    trade['profit_points'] = float(trade['profit_points'])
                    trade['profit_usd'] = float(trade['profit_usd'])
                    trade['profit_pct'] = float(trade['profit_pct'])
                    trade['win'] = trade['win'] == 'True'
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            self.trades = []

    def log_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        lots: float,
        profit_points: float,
        profit_usd: float,
        profit_pct: float,
        bars_held: int,
        strategy: str = "M1_SCALP",
        ml_confidence: float = 0.0,
        exit_reason: str = "ML_EXIT"
    ):
        """Log a completed trade to CSV"""

        win = profit_points > 0

        trade = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'direction': direction,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'lots': lots,
            'profit_points': profit_points,
            'profit_usd': profit_usd,
            'profit_pct': profit_pct,
            'bars_held': bars_held,
            'win': win,
            'strategy': strategy,
            'ml_confidence': ml_confidence,
            'exit_reason': exit_reason
        }

        # Add to memory
        self.trades.append(trade)

        # Append to CSV
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade['timestamp'],
                    trade['symbol'],
                    trade['direction'],
                    trade['entry_price'],
                    trade['exit_price'],
                    trade['lots'],
                    trade['profit_points'],
                    trade['profit_usd'],
                    trade['profit_pct'],
                    trade['bars_held'],
                    trade['win'],
                    trade['strategy'],
                    trade['ml_confidence'],
                    trade['exit_reason']
                ])
        except Exception as e:
            logger.error(f"Failed to write trade to CSV: {e}")

        logger.info(f"📊 Trade logged: {'WIN' if win else 'LOSS'} {profit_points:+.0f}pts (${profit_usd:+.2f})")

    def get_metrics(self, last_n: Optional[int] = None) -> Dict:
        """
        Calculate performance metrics

        Args:
            last_n: Only use last N trades (None = all trades)

        Returns:
            Dictionary with metrics
        """
        if not self.trades:
            return self._empty_metrics()

        # Get trades to analyze
        trades = self.trades[-last_n:] if last_n else self.trades

        if not trades:
            return self._empty_metrics()

        # Extract data
        profits = [float(t['profit_usd']) for t in trades]
        wins = [t['win'] for t in trades]
        profit_pcts = [float(t['profit_pct']) for t in trades]

        # Basic metrics
        total_trades = len(trades)
        winning_trades = sum(wins)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # P&L metrics
        total_pnl = sum(profits)
        avg_win = np.mean([p for p, w in zip(profits, wins) if w]) if winning_trades > 0 else 0
        avg_loss = np.mean([p for p, w in zip(profits, wins) if not w]) if losing_trades > 0 else 0

        # Risk/Reward
        rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        # Profit factor
        gross_profit = sum([p for p in profits if p > 0])
        gross_loss = abs(sum([p for p in profits if p < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Drawdown
        cumulative = np.cumsum(profits)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
        max_drawdown_pct = (max_drawdown / running_max[np.argmax(drawdown)] * 100) if np.max(running_max) > 0 else 0

        # Sharpe ratio (annualized)
        if len(profit_pcts) > 1:
            returns_std = np.std(profit_pcts)
            avg_return = np.mean(profit_pcts)
            # Assume 252 trading days, ~100 trades per day for scalping
            sharpe = (avg_return / returns_std * np.sqrt(252 * 100)) if returns_std > 0 else 0
        else:
            sharpe = 0

        # Consecutive stats
        consecutive_wins = self._max_consecutive(wins, True)
        consecutive_losses = self._max_consecutive(wins, False)

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'rr_ratio': rr_ratio,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe,
            'consecutive_wins': consecutive_wins,
            'consecutive_losses': consecutive_losses,
            'last_n_trades': last_n if last_n else 'all'
        }

    def _max_consecutive(self, results: List[bool], target: bool) -> int:
        """Calculate max consecutive wins or losses"""
        max_streak = 0
        current_streak = 0

        for result in results:
            if result == target:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        return max_streak

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'rr_ratio': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': 0.0,
            'consecutive_wins': 0,
            'consecutive_losses': 0,
            'last_n_trades': 'all'
        }

    def print_summary(self, last_n: Optional[int] = None):
        """Print performance summary to console"""
        metrics = self.get_metrics(last_n)

        print("\n" + "="*70)
        print(f"📊 PERFORMANCE SUMMARY {'(Last ' + str(last_n) + ' trades)' if last_n else '(All trades)'}")
        print("="*70)
        print(f"Total Trades:       {metrics['total_trades']}")
        print(f"Win Rate:           {metrics['win_rate']:.2f}% ({metrics['winning_trades']}W / {metrics['losing_trades']}L)")
        print(f"Total P&L:          ${metrics['total_pnl']:+.2f}")
        print(f"Avg Win:            ${metrics['avg_win']:.2f}")
        print(f"Avg Loss:           ${metrics['avg_loss']:.2f}")
        print(f"Risk/Reward:        {metrics['rr_ratio']:.2f}")
        print(f"Profit Factor:      {metrics['profit_factor']:.2f}")
        print(f"Max Drawdown:       ${metrics['max_drawdown']:.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        print(f"Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
        print(f"Max Consec Wins:    {metrics['consecutive_wins']}")
        print(f"Max Consec Losses:  {metrics['consecutive_losses']}")
        print("="*70 + "\n")
