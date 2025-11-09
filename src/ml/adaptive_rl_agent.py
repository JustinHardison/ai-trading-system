"""
Adaptive Reinforcement Learning Agent
Learns from mistakes in REAL-TIME and adjusts strategy

Key Features:
1. Recognizes bad trades early and exits fast
2. Learns optimal holding times per regime
3. Adapts stop/target distances based on results
4. Detects mistake patterns (time of day, direction, etc.)
5. Overrides ML/LLM when historical data shows better approach
"""
import numpy as np
import pandas as pd
from collections import deque, defaultdict
from typing import Dict, List, Tuple, Optional
import pickle
from pathlib import Path
from datetime import datetime, time

from ..utils.logger import get_logger

logger = get_logger(__name__)


class AdaptiveRLAgent:
    """
    Adaptive RL Agent that learns from every trade and adjusts in real-time

    This is NOT just threshold adjustment - this is ACTIVE TRADE MANAGEMENT
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        memory_size: int = 1000
    ):
        self.learning_rate = learning_rate
        self.memory = deque(maxlen=memory_size)

        # Pattern Recognition: Learn what works and what doesn't
        self.pattern_outcomes = defaultdict(lambda: {
            'trades': 0,
            'wins': 0,
            'avg_profit': 0.0,
            'avg_hold_time': 0.0,
            'early_exit_success': 0,  # Times early exit saved money
            'let_run_success': 0      # Times letting it run paid off
        })

        # Bad Trade Recognition: Learn early warning signs
        self.bad_trade_patterns = []  # Store patterns of losing trades

        # Optimal Holding Times: Learn best exit timing per regime
        self.optimal_hold_times = defaultdict(lambda: {
            'min': 5,   # Minimum hold time (minutes)
            'max': 120, # Maximum hold time (minutes)
            'optimal': 30,  # Sweet spot
            'variance': 15  # How much variance is OK
        })

        # Stop/Target Adaptation: Learn what multipliers work
        self.stop_target_performance = defaultdict(lambda: {
            'tight_stops_wins': 0,    # 1.5x ATR
            'normal_stops_wins': 0,   # 2.5x ATR
            'wide_stops_wins': 0,     # 3.5x ATR
            'total_trades': 0
        })

        # Time-of-Day Performance: Learn when to trade aggressively
        self.time_performance = defaultdict(lambda: {
            'BUY_wins': 0,
            'BUY_losses': 0,
            'SELL_wins': 0,
            'SELL_losses': 0
        })

        # Stats
        self.total_trades = 0
        self.total_profit = 0.0
        self.early_exits_saved = 0.0  # $ saved by early exits

    def should_exit_early(
        self,
        current_trade: Dict,
        market_state: Dict
    ) -> Tuple[bool, str]:
        """
        CRITICAL: Recognize bad trades early and exit fast

        Args:
            current_trade: {
                'direction': 'BUY/SELL',
                'entry_time': datetime,
                'entry_price': float,
                'current_price': float,
                'profit_points': float,
                'confidence': float,
                'regime': str
            }
            market_state: Current market indicators

        Returns:
            (should_exit, reason)
        """
        minutes_held = (datetime.now() - current_trade['entry_time']).seconds / 60
        profit_points = current_trade['profit_points']
        regime = current_trade['regime']
        confidence = current_trade['confidence']

        # Pattern 1: Early loss in wrong regime
        if minutes_held < 5 and profit_points < -20:
            # Check if this regime/direction combo is historically bad
            pattern_key = f"{regime}_{current_trade['direction']}_early_loss"
            pattern = self.pattern_outcomes[pattern_key]

            if pattern['trades'] >= 3 and pattern['wins'] / pattern['trades'] < 0.3:
                # This pattern has 70%+ loss rate - GET OUT NOW!
                return True, f"Early loss pattern in {regime} - historical 70%+ loss rate"

        # Pattern 2: Quick profit reversal (price came back against us)
        if minutes_held < 10:
            if profit_points < -30 and current_trade.get('max_profit', 0) > 20:
                # Was up +20, now down -30 = -50 point reversal
                return True, "Quick profit reversal - market structure failed"

        # Pattern 3: Held too long with small profit
        optimal_time = self.optimal_hold_times[regime]['optimal']
        if minutes_held > optimal_time * 1.5:
            if 0 < profit_points < 30:
                # Held way past optimal time with tiny profit
                return True, f"Held {minutes_held}min > optimal {optimal_time}min with only +{profit_points} pts"

        # Pattern 4: Low confidence trade going wrong
        if confidence < 80 and profit_points < -25 and minutes_held < 15:
            # Low confidence + early loss = probably bad trade
            return True, f"Low confidence ({confidence}%) trade failing early"

        # Pattern 5: Wrong time of day for this direction
        hour = datetime.now().hour
        time_key = f"hour_{hour}"
        time_stats = self.time_performance[time_key]

        direction = current_trade['direction']
        if direction == 'BUY':
            total = time_stats['BUY_wins'] + time_stats['BUY_losses']
            if total >= 5 and time_stats['BUY_wins'] / total < 0.3:
                if profit_points < 0:
                    return True, f"BUY trades at hour {hour} have 70%+ loss rate"
        else:  # SELL
            total = time_stats['SELL_wins'] + time_stats['SELL_losses']
            if total >= 5 and time_stats['SELL_wins'] / total < 0.3:
                if profit_points < 0:
                    return True, f"SELL trades at hour {hour} have 70%+ loss rate"

        return False, ""

    def should_let_run(
        self,
        current_trade: Dict,
        ml_says_exit: bool,
        ml_confidence: float
    ) -> Tuple[bool, str]:
        """
        Override ML exit signal if historical data says let it run

        Returns:
            (override_to_hold, reason)
        """
        if not ml_says_exit:
            return False, ""

        minutes_held = (datetime.now() - current_trade['entry_time']).seconds / 60
        profit_points = current_trade['profit_points']
        regime = current_trade['regime']

        # Pattern: Quick profit that usually runs further
        if minutes_held < 15 and profit_points > 50:
            pattern_key = f"{regime}_quick_profit"
            pattern = self.pattern_outcomes[pattern_key]

            if pattern['trades'] >= 5:
                # Check if letting these run historically paid off
                if pattern['let_run_success'] > pattern['early_exit_success'] * 1.5:
                    return True, f"Quick profit in {regime} usually runs further (historical data)"

        # Pattern: Trending regime with strong momentum
        if 'TRENDING' in regime and profit_points > 30:
            optimal_time = self.optimal_hold_times[regime]['optimal']
            if minutes_held < optimal_time * 0.7:
                # Haven't reached optimal hold time yet
                return True, f"Trending trade before optimal exit time ({minutes_held}/{optimal_time} min)"

        return False, ""

    def get_adaptive_stop_multiplier(
        self,
        regime: str,
        confidence: float,
        current_volatility: float
    ) -> float:
        """
        Learn optimal stop distance for this regime

        Returns:
            ATR multiplier (1.5, 2.5, or 3.5)
        """
        perf = self.stop_target_performance[regime]

        if perf['total_trades'] < 10:
            # Not enough data - use default
            if 'HIGH_VOL' in regime:
                return 3.5  # Wide stops in volatile
            elif 'RANGING' in regime:
                return 1.5  # Tight stops in ranging
            else:
                return 2.5  # Normal

        # Calculate win rates for each approach
        tight_wr = perf['tight_stops_wins'] / max(1, perf['total_trades'] * 0.33)
        normal_wr = perf['normal_stops_wins'] / max(1, perf['total_trades'] * 0.33)
        wide_wr = perf['wide_stops_wins'] / max(1, perf['total_trades'] * 0.33)

        # Use what works best for this regime
        best = max([
            (tight_wr, 1.5),
            (normal_wr, 2.5),
            (wide_wr, 3.5)
        ])

        logger.info(
            f"Adaptive Stop: {regime} uses {best[1]}x ATR "
            f"(Tight: {tight_wr:.1f}%, Normal: {normal_wr:.1f}%, Wide: {wide_wr:.1f}%)"
        )

        return best[1]

    def record_trade_outcome(
        self,
        trade_info: Dict,
        outcome: Dict
    ):
        """
        Learn from completed trade

        Args:
            trade_info: Entry details (regime, confidence, direction, time, etc.)
            outcome: Exit details (profit, exit_reason, time_held, etc.)
        """
        profit = outcome['profit_points']
        time_held = outcome['time_held_minutes']
        regime = trade_info['regime']
        direction = trade_info['direction']
        confidence = trade_info['confidence']

        # Update overall stats
        self.total_trades += 1
        self.total_profit += profit

        is_win = profit > 0

        # 1. LEARN OPTIMAL HOLDING TIMES
        optimal = self.optimal_hold_times[regime]
        if is_win:
            # Update optimal hold time (moving average)
            optimal['optimal'] = (
                optimal['optimal'] * 0.9 + time_held * 0.1
            )
            optimal['variance'] = abs(time_held - optimal['optimal'])

        # 2. LEARN STOP/TARGET PERFORMANCE
        stop_type = outcome.get('stop_type', 'normal')  # tight/normal/wide
        perf = self.stop_target_performance[regime]
        perf['total_trades'] += 1

        if is_win:
            if stop_type == 'tight':
                perf['tight_stops_wins'] += 1
            elif stop_type == 'normal':
                perf['normal_stops_wins'] += 1
            else:
                perf['wide_stops_wins'] += 1

        # 3. LEARN PATTERN OUTCOMES
        # Quick profit pattern
        if time_held < 15 and profit > 50:
            pattern_key = f"{regime}_quick_profit"
            pattern = self.pattern_outcomes[pattern_key]
            pattern['trades'] += 1
            if is_win:
                pattern['wins'] += 1
            pattern['avg_profit'] = (
                pattern['avg_profit'] * 0.9 + profit * 0.1
            )

            # Track if early exit or letting run worked
            if outcome.get('exit_reason') == 'ML_EXIT' and time_held < 20:
                if is_win:
                    pattern['early_exit_success'] += 1
            elif time_held > 30:
                if is_win and profit > 100:
                    pattern['let_run_success'] += 1

        # Early loss pattern
        if time_held < 5 and profit < -20:
            pattern_key = f"{regime}_{direction}_early_loss"
            pattern = self.pattern_outcomes[pattern_key]
            pattern['trades'] += 1
            if is_win:
                pattern['wins'] += 1

        # 4. LEARN TIME-OF-DAY PERFORMANCE
        entry_hour = trade_info['entry_time'].hour
        time_key = f"hour_{entry_hour}"
        time_stats = self.time_performance[time_key]

        if direction == 'BUY':
            if is_win:
                time_stats['BUY_wins'] += 1
            else:
                time_stats['BUY_losses'] += 1
        else:
            if is_win:
                time_stats['SELL_wins'] += 1
            else:
                time_stats['SELL_losses'] += 1

        # 5. TRACK BAD TRADE PATTERNS
        if not is_win and profit < -50:
            # This was a bad trade - remember the pattern
            bad_pattern = {
                'regime': regime,
                'direction': direction,
                'confidence': confidence,
                'time_of_day': entry_hour,
                'loss_amount': profit
            }
            self.bad_trade_patterns.append(bad_pattern)

            # Keep only last 50 bad trades
            if len(self.bad_trade_patterns) > 50:
                self.bad_trade_patterns.pop(0)

        # Log what we learned
        logger.info(
            f"RL Learning: {regime} {direction} @ {confidence}% → "
            f"${profit:.0f} in {time_held} min | "
            f"Optimal hold: {optimal['optimal']:.0f} min | "
            f"Total: {self.total_trades} trades, ${self.total_profit:.0f}"
        )

    def get_insights(self) -> Dict:
        """
        Get current RL insights for debugging/monitoring
        """
        insights = {
            'total_trades': self.total_trades,
            'total_profit': self.total_profit,
            'optimal_hold_times': dict(self.optimal_hold_times),
            'stop_performance': dict(self.stop_target_performance),
            'pattern_outcomes': dict(self.pattern_outcomes),
            'time_performance': dict(self.time_performance)
        }

        return insights

    def save_state(self, filepath: str):
        """Save learned knowledge"""
        state = {
            'pattern_outcomes': dict(self.pattern_outcomes),
            'bad_trade_patterns': self.bad_trade_patterns,
            'optimal_hold_times': dict(self.optimal_hold_times),
            'stop_target_performance': dict(self.stop_target_performance),
            'time_performance': dict(self.time_performance),
            'total_trades': self.total_trades,
            'total_profit': self.total_profit,
            'early_exits_saved': self.early_exits_saved
        }

        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

        logger.info(f"Adaptive RL state saved: {self.total_trades} trades, ${self.total_profit:.2f}")

    def load_state(self, filepath: str):
        """Load learned knowledge"""
        if not Path(filepath).exists():
            logger.info("No saved RL state found - starting fresh")
            return

        with open(filepath, 'rb') as f:
            state = pickle.load(f)

        self.pattern_outcomes = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'avg_profit': 0.0,
            'avg_hold_time': 0.0, 'early_exit_success': 0,
            'let_run_success': 0
        }, state['pattern_outcomes'])

        self.bad_trade_patterns = state.get('bad_trade_patterns', [])
        self.optimal_hold_times = defaultdict(lambda: {
            'min': 5, 'max': 120, 'optimal': 30, 'variance': 15
        }, state.get('optimal_hold_times', {}))

        self.stop_target_performance = defaultdict(lambda: {
            'tight_stops_wins': 0, 'normal_stops_wins': 0,
            'wide_stops_wins': 0, 'total_trades': 0
        }, state.get('stop_target_performance', {}))

        self.time_performance = defaultdict(lambda: {
            'BUY_wins': 0, 'BUY_losses': 0,
            'SELL_wins': 0, 'SELL_losses': 0
        }, state.get('time_performance', {}))

        self.total_trades = state.get('total_trades', 0)
        self.total_profit = state.get('total_profit', 0.0)
        self.early_exits_saved = state.get('early_exits_saved', 0.0)

        logger.info(
            f"Adaptive RL state loaded: {self.total_trades} trades, "
            f"${self.total_profit:.2f} profit"
        )
