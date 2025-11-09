"""
Position Monitor with Adaptive Exits
Monitors open positions every minute and makes adaptive exit decisions
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from src.utils.logger import get_logger
from src.risk.ftmo_rules import FTMOChallengeStatus
from src.market_analysis.regime_detector import MarketRegime, RegimeDetector
from src.ai.portfolio_manager import AdaptiveAIPortfolioManager

logger = get_logger(__name__)


@dataclass
class PositionAnalysis:
    """Position analysis result"""
    position_id: int
    symbol: str
    should_exit: bool
    reason: str
    confidence: float
    metrics: Dict


class PositionMonitor:
    """
    Monitors open positions and makes adaptive exit decisions

    Key Features:
    - Checks positions every 1 minute (not just at stop/TP)
    - Adaptive exits based on:
      - Support/resistance broken
      - Gave back 50% of profit
      - Trade flat for 24 hours
      - Near FTMO limits
      - Regime changed against us
    - Trailing stop logic (move to breakeven after +1%)
    """

    def __init__(
        self,
        portfolio_manager: AdaptiveAIPortfolioManager,
        regime_detector: RegimeDetector,
        check_interval_seconds: int = 60
    ):
        """
        Args:
            portfolio_manager: AI portfolio manager for exit decisions
            regime_detector: Market regime detector
            check_interval_seconds: How often to check positions
        """
        self.portfolio_manager = portfolio_manager
        self.regime_detector = regime_detector
        self.check_interval = check_interval_seconds

        # Track position history
        self.position_history: Dict[int, List[Dict]] = {}  # position_id -> history
        self.position_peak_profit: Dict[int, float] = {}  # position_id -> peak profit

        logger.info(f"Initialized Position Monitor (check every {check_interval_seconds}s)")

    def monitor_positions(
        self,
        open_positions: List[Dict],
        market_data: Dict[str, Dict],
        ftmo_status: FTMOChallengeStatus
    ) -> List[PositionAnalysis]:
        """
        Monitor all open positions and identify which should exit

        Args:
            open_positions: List of open positions
            market_data: Current market data per symbol
            ftmo_status: Current FTMO status

        Returns:
            List of PositionAnalysis for positions that should exit
        """
        if not open_positions:
            return []

        exit_recommendations = []

        for position in open_positions:
            analysis = self._analyze_position(
                position=position,
                market_data=market_data.get(position['symbol']),
                ftmo_status=ftmo_status
            )

            if analysis.should_exit:
                exit_recommendations.append(analysis)
                logger.warning(
                    f"EXIT RECOMMENDATION: {position['symbol']} - "
                    f"{analysis.reason} (Confidence: {analysis.confidence:.0f}%)"
                )

        return exit_recommendations

    def _analyze_position(
        self,
        position: Dict,
        market_data: Optional[Dict],
        ftmo_status: FTMOChallengeStatus
    ) -> PositionAnalysis:
        """
        Analyze single position for exit decision

        Args:
            position: Position details
            market_data: Current market data for position symbol
            ftmo_status: FTMO challenge status

        Returns:
            PositionAnalysis with exit decision
        """
        position_id = position['id']
        symbol = position['symbol']

        if not market_data:
            logger.warning(f"No market data for {symbol}, skipping analysis")
            return PositionAnalysis(
                position_id=position_id,
                symbol=symbol,
                should_exit=False,
                reason="No market data",
                confidence=0,
                metrics={}
            )

        # Update position history
        self._update_position_history(position, market_data)

        # Get current price
        current_price = market_data.get('close', position.get('current_price', position['entry_price']))

        # Calculate metrics
        metrics = self._calculate_position_metrics(position, current_price, market_data)

        # Check adaptive exit conditions
        should_exit, reason, confidence = self._check_exit_conditions(
            position=position,
            metrics=metrics,
            ftmo_status=ftmo_status,
            market_data=market_data
        )

        return PositionAnalysis(
            position_id=position_id,
            symbol=symbol,
            should_exit=should_exit,
            reason=reason,
            confidence=confidence,
            metrics=metrics
        )

    def _update_position_history(self, position: Dict, market_data: Dict):
        """Track position history for analysis"""
        position_id = position['id']

        if position_id not in self.position_history:
            self.position_history[position_id] = []

        # Add current state
        current_price = market_data.get('close', position.get('current_price', position['entry_price']))
        current_profit = position.get('profit', 0)

        self.position_history[position_id].append({
            'timestamp': datetime.now(),
            'price': current_price,
            'profit': current_profit
        })

        # Track peak profit
        if position_id not in self.position_peak_profit:
            self.position_peak_profit[position_id] = current_profit
        else:
            self.position_peak_profit[position_id] = max(
                self.position_peak_profit[position_id],
                current_profit
            )

        # Keep only last 1440 entries (24 hours at 1 min intervals)
        if len(self.position_history[position_id]) > 1440:
            self.position_history[position_id] = self.position_history[position_id][-1440:]

    def _calculate_position_metrics(
        self,
        position: Dict,
        current_price: float,
        market_data: Dict
    ) -> Dict:
        """Calculate position metrics for analysis"""
        position_id = position['id']
        entry_price = position['entry_price']
        direction = position['direction']

        # Calculate P&L
        if direction == 'BUY':
            pips_profit = (current_price - entry_price) * 10000  # Forex pip calculation
            pct_profit = ((current_price - entry_price) / entry_price) * 100
        else:  # SELL
            pips_profit = (entry_price - current_price) * 10000
            pct_profit = ((entry_price - current_price) / entry_price) * 100

        # Time in trade
        entry_time = position.get('entry_time', datetime.now())
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        time_in_trade = (datetime.now() - entry_time).total_seconds() / 3600  # hours

        # Price movement analysis
        history = self.position_history.get(position_id, [])
        price_stagnant = False
        if len(history) >= 60:  # At least 1 hour of data
            recent_prices = [h['price'] for h in history[-60:]]
            price_range = max(recent_prices) - min(recent_prices)
            atr = market_data.get('atr', 0.0001)
            if price_range < atr * 0.25:  # Less than 25% of ATR movement in 1 hour
                price_stagnant = True

        # Profit drawdown (gave back profit)
        peak_profit = self.position_peak_profit.get(position_id, position.get('profit', 0))
        current_profit = position.get('profit', 0)
        profit_drawdown_pct = 0
        if peak_profit > 0:
            profit_drawdown_pct = ((peak_profit - current_profit) / peak_profit) * 100

        # Distance to stop/TP
        stop_loss = position.get('stop_loss')
        take_profit = position.get('take_profit')

        distance_to_sl_pips = None
        distance_to_tp_pips = None

        if stop_loss:
            if direction == 'BUY':
                distance_to_sl_pips = (current_price - stop_loss) * 10000
            else:
                distance_to_sl_pips = (stop_loss - current_price) * 10000

        if take_profit:
            if direction == 'BUY':
                distance_to_tp_pips = (take_profit - current_price) * 10000
            else:
                distance_to_tp_pips = (current_price - take_profit) * 10000

        return {
            'current_price': current_price,
            'pips_profit': pips_profit,
            'pct_profit': pct_profit,
            'time_in_trade_hours': time_in_trade,
            'peak_profit': peak_profit,
            'current_profit': current_profit,
            'profit_drawdown_pct': profit_drawdown_pct,
            'price_stagnant': price_stagnant,
            'distance_to_sl_pips': distance_to_sl_pips,
            'distance_to_tp_pips': distance_to_tp_pips
        }

    def _check_exit_conditions(
        self,
        position: Dict,
        metrics: Dict,
        ftmo_status: FTMOChallengeStatus,
        market_data: Dict
    ) -> Tuple[bool, str, float]:
        """
        Check all adaptive exit conditions

        Returns:
            (should_exit, reason, confidence)
        """

        # CRITICAL: Near FTMO daily loss limit
        daily_buffer = next((r.buffer for r in ftmo_status.rules if r.rule_name == "Daily Loss Limit"), 5.0)
        if daily_buffer < 1.5:
            return True, f"CRITICAL: Daily loss buffer only {daily_buffer:.1f}% - Exit all positions", 100

        # CRITICAL: Near FTMO max drawdown
        dd_buffer = next((r.buffer for r in ftmo_status.rules if r.rule_name == "Maximum Drawdown"), 10.0)
        if dd_buffer < 2.0:
            return True, f"CRITICAL: Max drawdown buffer only {dd_buffer:.1f}% - Exit all positions", 100

        # HIGH: Gave back 50%+ of profit
        if metrics['profit_drawdown_pct'] > 50 and metrics['peak_profit'] > 0:
            return True, f"Gave back {metrics['profit_drawdown_pct']:.0f}% of profit (Peak: ${metrics['peak_profit']:.2f}, Now: ${metrics['current_profit']:.2f})", 85

        # HIGH: Trade flat for 24+ hours with profit
        if metrics['time_in_trade_hours'] > 24 and metrics['price_stagnant'] and metrics['pct_profit'] > 0.3:
            return True, f"Trade flat for {metrics['time_in_trade_hours']:.0f} hours - Lock in {metrics['pct_profit']:.2f}% profit", 80

        # HIGH: Near take profit (90%+ reached)
        if metrics['distance_to_tp_pips'] is not None and metrics['distance_to_tp_pips'] < 5:
            return True, f"Near take profit ({metrics['distance_to_tp_pips']:.1f} pips away) - Take it", 90

        # MEDIUM: FTMO profit target reached - lock it in
        if ftmo_status.profit_pct >= next((r.limit_value for r in ftmo_status.rules if r.rule_name == "Profit Target"), 100):
            return True, f"FTMO profit target reached ({ftmo_status.profit_pct:.1f}%) - Lock it in", 95

        # REMOVED: Hard-coded Friday 4pm rule
        # LLM now evaluates weekend risk based on actual market conditions
        # (volatility, spreads, position size) instead of calendar date

        # MEDIUM: Regime changed against us (would need regime detection)
        # This would call regime_detector and compare to entry regime
        # Skipping for now, would integrate with LLM exit decision

        # LOW: Trade underwater for 48+ hours
        if metrics['time_in_trade_hours'] > 48 and metrics['pct_profit'] < -0.3:
            return True, f"Trade underwater {metrics['pct_profit']:.2f}% for {metrics['time_in_trade_hours']:.0f} hours - Cut loss", 60

        # Use LLM for nuanced exit decision if any warning flags
        if (metrics['time_in_trade_hours'] > 12 or
            metrics['profit_drawdown_pct'] > 30 or
            daily_buffer < 3.0):

            # Get market regime
            try:
                import pandas as pd
                df = pd.DataFrame([market_data])
                regime = self.regime_detector.detect_regime(df)

                should_exit, reason = self.portfolio_manager.should_exit_position(
                    position=position,
                    current_price=metrics['current_price'],
                    ftmo_status=ftmo_status,
                    regime=regime,
                    time_in_trade_hours=metrics['time_in_trade_hours']
                )

                if should_exit:
                    return True, f"LLM Decision: {reason}", 75

            except Exception as e:
                logger.error(f"Error in LLM exit decision: {e}")

        return False, "Position OK", 0

    def should_move_to_breakeven(self, position: Dict, metrics: Dict) -> bool:
        """Check if stop should be moved to breakeven"""

        # Move to breakeven after +1% profit
        if metrics['pct_profit'] >= 1.0:
            # Check if stop is still below entry
            if position.get('stop_loss'):
                entry_price = position['entry_price']
                stop_loss = position['stop_loss']
                direction = position['direction']

                if direction == 'BUY' and stop_loss < entry_price:
                    return True
                elif direction == 'SELL' and stop_loss > entry_price:
                    return True

        return False

    def cleanup_closed_position(self, position_id: int):
        """Clean up tracking for closed position"""
        if position_id in self.position_history:
            del self.position_history[position_id]
        if position_id in self.position_peak_profit:
            del self.position_peak_profit[position_id]

        logger.info(f"Cleaned up tracking for position {position_id}")
