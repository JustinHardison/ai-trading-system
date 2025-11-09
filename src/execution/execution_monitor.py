"""
Execution Quality Monitor
Tracks execution quality to preserve edge
- Uses LIMIT orders (not MARKET orders)
- Tracks slippage (expected vs actual fill price)
- Monitors spread widening
- Execution quality scoring
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionQuality:
    """Execution quality metrics"""
    trade_id: int
    symbol: str
    direction: str
    requested_price: float
    fill_price: float
    slippage_pips: float
    spread_pips: float
    execution_time_ms: float
    quality_score: float  # 0-100
    rating: str  # 'EXCELLENT', 'GOOD', 'FAIR', 'POOR'


@dataclass
class ExecutionStats:
    """Overall execution statistics"""
    total_trades: int
    avg_slippage_pips: float
    avg_spread_pips: float
    avg_execution_time_ms: float
    avg_quality_score: float
    excellent_count: int
    good_count: int
    fair_count: int
    poor_count: int


class ExecutionQualityMonitor:
    """
    Monitors execution quality to preserve trading edge

    Key Features:
    - Limit orders with acceptable slippage buffer
    - Spread monitoring (don't trade if spread > 2x normal)
    - Slippage tracking per symbol
    - Execution quality scoring
    - Alerts on poor execution
    """

    def __init__(
        self,
        max_slippage_pips: float = 1.0,
        max_spread_multiplier: float = 2.0,
        history_size: int = 1000
    ):
        """
        Args:
            max_slippage_pips: Maximum acceptable slippage
            max_spread_multiplier: Max spread vs normal (e.g., 2.0 = 2x normal)
            history_size: Number of executions to keep in history
        """
        self.max_slippage = max_slippage_pips
        self.max_spread_multiplier = max_spread_multiplier

        # Execution history
        self.execution_history: deque = deque(maxlen=history_size)

        # Per-symbol tracking
        self.symbol_stats: Dict[str, Dict] = {}

        # Normal spread baselines (updated over time)
        self.normal_spreads: Dict[str, float] = {
            'EURUSD': 0.8,
            'GBPUSD': 1.2,
            'USDJPY': 0.9,
            'USDCHF': 1.3,
            'AUDUSD': 1.0,
            'NZDUSD': 1.5,
            'USDCAD': 1.2,
            'EURJPY': 1.2,
            'GBPJPY': 2.0,
            'EURGBP': 1.0,
            'AUDJPY': 1.5,
            'EURAUD': 1.8
        }

        logger.info(f"Initialized Execution Quality Monitor (max slippage: {max_slippage_pips} pips)")

    def check_spread(self, symbol: str, current_spread_pips: float) -> Tuple[bool, str]:
        """
        Check if current spread is acceptable for trading

        Returns:
            (is_acceptable, reason)
        """
        # Get normal spread for symbol
        normal_spread = self.normal_spreads.get(symbol.replace('.sim', ''), 1.5)

        # Check if spread is widened
        if current_spread_pips > normal_spread * self.max_spread_multiplier:
            return False, f"Spread widened: {current_spread_pips:.1f} pips (normal: {normal_spread:.1f}, max: {normal_spread * self.max_spread_multiplier:.1f})"

        return True, "Spread acceptable"

    def calculate_limit_price(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        slippage_buffer_pips: float = 0.5
    ) -> float:
        """
        Calculate limit order price with slippage buffer

        Args:
            symbol: Trading symbol
            direction: 'BUY' or 'SELL'
            current_price: Current market price
            slippage_buffer_pips: Acceptable slippage in pips

        Returns:
            Limit price
        """
        pip_value = 0.0001  # Standard for most forex pairs

        if direction == 'BUY':
            # For buy, accept price up to current + buffer
            limit_price = current_price + (slippage_buffer_pips * pip_value)
        else:  # SELL
            # For sell, accept price down to current - buffer
            limit_price = current_price - (slippage_buffer_pips * pip_value)

        logger.debug(f"{symbol} {direction} limit: {limit_price:.5f} (market: {current_price:.5f}, buffer: {slippage_buffer_pips} pips)")

        return limit_price

    def record_execution(
        self,
        trade_id: int,
        symbol: str,
        direction: str,
        requested_price: float,
        fill_price: float,
        spread_pips: float,
        execution_time_ms: float
    ) -> ExecutionQuality:
        """
        Record execution and calculate quality metrics

        Returns:
            ExecutionQuality report
        """
        # Calculate slippage
        slippage_pips = abs(fill_price - requested_price) * 10000

        # Adjust for direction
        if direction == 'BUY' and fill_price > requested_price:
            # Paid more than expected (negative slippage)
            slippage_pips = -slippage_pips
        elif direction == 'SELL' and fill_price < requested_price:
            # Got less than expected (negative slippage)
            slippage_pips = -slippage_pips

        # Calculate quality score (0-100)
        quality_score = self._calculate_quality_score(
            slippage_pips=slippage_pips,
            spread_pips=spread_pips,
            execution_time_ms=execution_time_ms,
            symbol=symbol
        )

        # Determine rating
        if quality_score >= 90:
            rating = 'EXCELLENT'
        elif quality_score >= 75:
            rating = 'GOOD'
        elif quality_score >= 60:
            rating = 'FAIR'
        else:
            rating = 'POOR'

        execution = ExecutionQuality(
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            requested_price=requested_price,
            fill_price=fill_price,
            slippage_pips=slippage_pips,
            spread_pips=spread_pips,
            execution_time_ms=execution_time_ms,
            quality_score=quality_score,
            rating=rating
        )

        # Add to history
        self.execution_history.append(execution)

        # Update symbol stats
        self._update_symbol_stats(execution)

        # Update normal spread baseline
        self._update_normal_spread(symbol, spread_pips)

        # Log quality
        if rating == 'POOR':
            logger.warning(
                f"POOR execution quality for {symbol}: "
                f"Slippage: {slippage_pips:.2f} pips, "
                f"Spread: {spread_pips:.1f} pips, "
                f"Score: {quality_score:.0f}/100"
            )
        else:
            logger.info(
                f"{rating} execution for {symbol}: "
                f"Score: {quality_score:.0f}/100, "
                f"Slippage: {slippage_pips:.2f} pips"
            )

        return execution

    def get_execution_stats(self, last_n: Optional[int] = None) -> ExecutionStats:
        """
        Get execution statistics

        Args:
            last_n: Only include last N executions (None = all)

        Returns:
            ExecutionStats summary
        """
        if not self.execution_history:
            return ExecutionStats(
                total_trades=0,
                avg_slippage_pips=0,
                avg_spread_pips=0,
                avg_execution_time_ms=0,
                avg_quality_score=0,
                excellent_count=0,
                good_count=0,
                fair_count=0,
                poor_count=0
            )

        # Get relevant executions
        if last_n:
            executions = list(self.execution_history)[-last_n:]
        else:
            executions = list(self.execution_history)

        # Calculate stats
        total = len(executions)
        avg_slippage = sum([abs(e.slippage_pips) for e in executions]) / total
        avg_spread = sum([e.spread_pips for e in executions]) / total
        avg_time = sum([e.execution_time_ms for e in executions]) / total
        avg_score = sum([e.quality_score for e in executions]) / total

        # Count ratings
        excellent = len([e for e in executions if e.rating == 'EXCELLENT'])
        good = len([e for e in executions if e.rating == 'GOOD'])
        fair = len([e for e in executions if e.rating == 'FAIR'])
        poor = len([e for e in executions if e.rating == 'POOR'])

        return ExecutionStats(
            total_trades=total,
            avg_slippage_pips=avg_slippage,
            avg_spread_pips=avg_spread,
            avg_execution_time_ms=avg_time,
            avg_quality_score=avg_score,
            excellent_count=excellent,
            good_count=good,
            fair_count=fair,
            poor_count=poor
        )

    def get_symbol_stats(self, symbol: str) -> Optional[Dict]:
        """Get execution stats for specific symbol"""
        return self.symbol_stats.get(symbol)

    def should_pause_trading(self) -> Tuple[bool, str]:
        """
        Determine if trading should be paused due to poor execution quality

        Returns:
            (should_pause, reason)
        """
        # Need at least 10 trades to make decision
        if len(self.execution_history) < 10:
            return False, "Not enough data"

        # Check last 10 executions
        recent_stats = self.get_execution_stats(last_n=10)

        # Pause if >50% poor executions in last 10 trades
        if recent_stats.poor_count >= 5:
            return True, f"Poor execution quality: {recent_stats.poor_count}/10 poor executions"

        # Pause if average quality < 60
        if recent_stats.avg_quality_score < 60:
            return True, f"Low average quality: {recent_stats.avg_quality_score:.0f}/100"

        # Pause if average slippage > 2 pips
        if recent_stats.avg_slippage_pips > 2.0:
            return True, f"High slippage: {recent_stats.avg_slippage_pips:.2f} pips average"

        return False, "Execution quality acceptable"

    def _calculate_quality_score(
        self,
        slippage_pips: float,
        spread_pips: float,
        execution_time_ms: float,
        symbol: str
    ) -> float:
        """
        Calculate execution quality score (0-100)

        Factors:
        - Slippage (50% weight)
        - Spread (30% weight)
        - Speed (20% weight)
        """
        score = 100.0

        # Slippage component (50% weight)
        # Perfect = 0 pips, Poor = 2+ pips
        slippage_penalty = (abs(slippage_pips) / self.max_slippage) * 50
        score -= min(slippage_penalty, 50)

        # Spread component (30% weight)
        # Compare to normal spread
        normal_spread = self.normal_spreads.get(symbol.replace('.sim', ''), 1.5)
        spread_ratio = spread_pips / normal_spread
        if spread_ratio > 1.0:
            spread_penalty = ((spread_ratio - 1.0) / (self.max_spread_multiplier - 1.0)) * 30
            score -= min(spread_penalty, 30)

        # Speed component (20% weight)
        # Perfect = <100ms, Poor = >1000ms
        if execution_time_ms > 1000:
            speed_penalty = ((execution_time_ms - 1000) / 1000) * 20
            score -= min(speed_penalty, 20)

        return max(0, score)

    def _update_symbol_stats(self, execution: ExecutionQuality):
        """Update per-symbol statistics"""
        symbol = execution.symbol

        if symbol not in self.symbol_stats:
            self.symbol_stats[symbol] = {
                'count': 0,
                'total_slippage': 0,
                'total_spread': 0,
                'total_time': 0,
                'total_score': 0,
                'excellent': 0,
                'good': 0,
                'fair': 0,
                'poor': 0
            }

        stats = self.symbol_stats[symbol]
        stats['count'] += 1
        stats['total_slippage'] += abs(execution.slippage_pips)
        stats['total_spread'] += execution.spread_pips
        stats['total_time'] += execution.execution_time_ms
        stats['total_score'] += execution.quality_score

        if execution.rating == 'EXCELLENT':
            stats['excellent'] += 1
        elif execution.rating == 'GOOD':
            stats['good'] += 1
        elif execution.rating == 'FAIR':
            stats['fair'] += 1
        else:
            stats['poor'] += 1

    def _update_normal_spread(self, symbol: str, current_spread: float):
        """Update normal spread baseline using exponential moving average"""
        symbol_clean = symbol.replace('.sim', '')

        if symbol_clean not in self.normal_spreads:
            self.normal_spreads[symbol_clean] = current_spread
        else:
            # EMA with alpha = 0.1
            old_spread = self.normal_spreads[symbol_clean]
            self.normal_spreads[symbol_clean] = old_spread * 0.9 + current_spread * 0.1

    def get_execution_report(self) -> str:
        """Generate execution quality report"""
        stats = self.get_execution_stats()

        if stats.total_trades == 0:
            return "No executions yet"

        report = f"""
EXECUTION QUALITY REPORT
========================
Total Trades: {stats.total_trades}
Average Quality Score: {stats.avg_quality_score:.1f}/100

Performance:
- Excellent: {stats.excellent_count} ({stats.excellent_count/stats.total_trades*100:.1f}%)
- Good: {stats.good_count} ({stats.good_count/stats.total_trades*100:.1f}%)
- Fair: {stats.fair_count} ({stats.fair_count/stats.total_trades*100:.1f}%)
- Poor: {stats.poor_count} ({stats.poor_count/stats.total_trades*100:.1f}%)

Metrics:
- Average Slippage: {stats.avg_slippage_pips:.2f} pips
- Average Spread: {stats.avg_spread_pips:.1f} pips
- Average Execution Time: {stats.avg_execution_time_ms:.0f} ms

Per-Symbol Stats:
"""
        for symbol, data in sorted(self.symbol_stats.items()):
            avg_slippage = data['total_slippage'] / data['count']
            avg_score = data['total_score'] / data['count']
            report += f"  {symbol}: {data['count']} trades, {avg_slippage:.2f} pips slippage, {avg_score:.0f}/100 score\n"

        return report
