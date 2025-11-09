"""
ML/RL Risk Manager - Intelligent Position Sizing & Trade Filtering
Learns optimal risk from account state, performance history, and market conditions
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import pickle
from datetime import datetime, timedelta
from loguru import logger


class MLRiskManager:
    """
    ML-based risk manager that predicts optimal position sizing
    Based on: account health, recent performance, market state, signal quality
    """

    def __init__(self):
        self.feature_names = []
        # US30-SPECIFIC: Aggressive risk for profitable growth - MATCH MONEY TO ANTICIPATED MOVES!
        # With 100pt stop and $0.50/pt: $50 risk per lot
        # $100k account * 3% = $3000 risk = 60 lots (proper profit capture!)
        # This matches the anticipated US30 moves (50-150 points typical)
        self.baseline_risk = 3.0  # 3% baseline (aggressive but controlled)
        self.min_risk = 2.0  # 2.0% minimum (floor for bad conditions)
        self.max_risk = 5.0  # 5.0% maximum (stay within FTMO daily loss limit)

        # Performance tracking
        self.decision_history = []
        self.last_update = None

    def extract_features(self,
                        balance: float,
                        equity: float,
                        daily_pnl: float,
                        current_drawdown: float,
                        open_positions: int,
                        ml_confidence: float,
                        trade_history: List[Dict]) -> np.ndarray:
        """
        Extract 30+ features that predict optimal risk
        """

        # Ensure trade_history is a list (defensive programming)
        if not isinstance(trade_history, list):
            logger.warning(f"⚠️ trade_history is not a list (type: {type(trade_history)}), converting to empty list")
            trade_history = []

        # Account health features
        equity_ratio = equity / balance if balance > 0 else 1.0
        drawdown_pct = abs(current_drawdown) / balance * 100 if balance > 0 else 0
        daily_pnl_pct = daily_pnl / balance * 100 if balance > 0 else 0

        # Recent performance (last 10 trades)
        recent_trades = trade_history[-10:] if len(trade_history) >= 10 else trade_history

        if len(recent_trades) > 0:
            wins = sum(1 for t in recent_trades if t.get('pnl', 0) > 0)
            win_rate_10 = wins / len(recent_trades)
            avg_pnl_10 = np.mean([t.get('pnl', 0) for t in recent_trades])
            max_loss_10 = min([t.get('pnl', 0) for t in recent_trades]) if recent_trades else 0
        else:
            win_rate_10 = 0.5  # Neutral
            avg_pnl_10 = 0
            max_loss_10 = 0

        # Medium-term performance (last 50 trades)
        medium_trades = trade_history[-50:] if len(trade_history) >= 50 else trade_history

        if len(medium_trades) > 0:
            wins_50 = sum(1 for t in medium_trades if t.get('pnl', 0) > 0)
            win_rate_50 = wins_50 / len(medium_trades)
            avg_pnl_50 = np.mean([t.get('pnl', 0) for t in medium_trades])
        else:
            win_rate_50 = 0.5
            avg_pnl_50 = 0

        # Streak detection
        current_streak = self._calculate_streak(trade_history)
        max_consecutive_losses = self._max_consecutive_losses(trade_history)

        # Risk metrics
        sharpe_ratio = self._calculate_sharpe(trade_history)
        profit_factor = self._calculate_profit_factor(trade_history)

        # Compile features
        features = np.array([
            # Account state (5 features)
            balance / 100000,  # Normalized
            equity_ratio,
            drawdown_pct / 10,  # Scale to 0-1 range
            daily_pnl_pct / 5,  # Scale to 0-1 range
            open_positions / 5,  # Max 5 positions

            # Recent performance (5 features)
            win_rate_10,
            avg_pnl_10 / 1000,  # Normalized
            max_loss_10 / -1000,  # Positive value
            win_rate_50,
            avg_pnl_50 / 1000,

            # Streak & consistency (3 features)
            current_streak / 5,  # -5 to +5 scaled
            max_consecutive_losses / 5,
            sharpe_ratio / 3,  # Scale to 0-1 range

            # Risk metrics (2 features)
            profit_factor / 3,
            ml_confidence / 100,

            # Time-based (2 features)
            datetime.now().hour / 24,  # Time of day
            datetime.now().weekday() / 7,  # Day of week
        ])

        return features

    def predict_optimal_risk(self,
                            balance: float,
                            equity: float,
                            daily_pnl: float,
                            current_drawdown: float,
                            open_positions: int,
                            ml_confidence: float,
                            trade_history: List[Dict]) -> Dict:
        """
        Predict optimal risk percentage based on current state
        Returns aggressive but smart risk sizing
        """

        # Ensure trade_history is a list (defensive programming)
        if not isinstance(trade_history, list):
            logger.warning(f"⚠️ trade_history is not a list (type: {type(trade_history)}), converting to empty list")
            trade_history = []

        # Extract features
        features = self.extract_features(
            balance, equity, daily_pnl, current_drawdown,
            open_positions, ml_confidence, trade_history
        )

        # Rule-based risk calculation (smart heuristics)
        risk_pct = self.baseline_risk
        reasons = []

        # 1. Account health adjustments (LESS CONSERVATIVE - match money to anticipated moves!)
        equity_ratio = equity / balance if balance > 0 else 1.0
        if equity_ratio < 0.90:  # Only reduce if seriously underwater
            risk_pct *= 0.85  # Gentle reduction (was 0.7)
            reasons.append("Drawdown protection")
        elif equity_ratio > 1.02:
            risk_pct *= 1.3  # Increase when profitable (was 1.2)
            reasons.append("Profit momentum")

        # 2. Recent performance adjustments (LESS CONSERVATIVE)
        recent_trades = trade_history[-10:] if len(trade_history) >= 10 else trade_history
        if len(recent_trades) > 0:
            wins = sum(1 for t in recent_trades if t.get('pnl', 0) > 0)
            win_rate = wins / len(recent_trades)

            if win_rate >= 0.7:
                risk_pct *= 1.4  # Hot streak - be more aggressive (was 1.3)
                reasons.append("Hot streak (70%+ WR)")
            elif win_rate <= 0.2:  # Only reduce on VERY cold streak (was 0.3)
                risk_pct *= 0.75  # Less aggressive reduction (was 0.6)
                reasons.append("Cold streak protection")

        # 3. Daily P&L adjustments (LESS CONSERVATIVE)
        daily_pnl_pct = daily_pnl / balance * 100 if balance > 0 else 0

        if daily_pnl_pct < -4:  # Only reduce on big daily loss (was -3)
            risk_pct *= 0.65  # Less aggressive reduction (was 0.5)
            reasons.append("Daily loss limit approaching")
        elif daily_pnl_pct > 2:
            risk_pct *= 1.25  # More aggressive when profitable (was 1.15)
            reasons.append("Daily profit buffer")

        # 4. Drawdown protection (LESS CONSERVATIVE)
        drawdown_pct = abs(current_drawdown) / balance * 100 if balance > 0 else 0

        if drawdown_pct > 6:  # Higher threshold (was 4)
            risk_pct *= 0.65  # Less aggressive reduction (was 0.5)
            reasons.append("Max drawdown protection")
        elif drawdown_pct > 4:  # Higher threshold (was 2)
            risk_pct *= 0.85  # Less aggressive reduction (was 0.75)
            reasons.append("Drawdown caution")

        # 5. ML confidence adjustment (MORE AGGRESSIVE)
        if ml_confidence >= 85:  # Reward high confidence more (was 80)
            risk_pct *= 1.4  # More aggressive (was 1.2)
            reasons.append("High confidence signal")
        elif ml_confidence < 60:  # Only reduce on lower confidence (adjusted from 65 to match 58% threshold)
            risk_pct *= 0.95  # Less aggressive reduction (was 0.9)
            reasons.append("Lower confidence")

        # 6. Position concentration (LESS CONSERVATIVE)
        if open_positions >= 4:  # Higher threshold (was 3)
            risk_pct *= 0.9  # Less aggressive reduction (was 0.8)
            reasons.append("Position concentration")

        # 7. Streak adjustments (MORE AGGRESSIVE ON WINS)
        streak = self._calculate_streak(trade_history)
        if streak >= 3:
            risk_pct *= 1.25  # More aggressive on winning streaks (was 1.1)
            reasons.append(f"{streak}-trade winning streak")
        elif streak <= -4:  # Only reduce on longer losing streaks (was -3)
            risk_pct *= 0.8  # Less aggressive reduction (was 0.7)
            reasons.append(f"{abs(streak)}-trade losing streak")

        # Apply bounds
        risk_pct = np.clip(risk_pct, self.min_risk, self.max_risk)

        # Trade filter decision
        take_trade = True

        # Don't trade if:
        if drawdown_pct > 4.5:
            take_trade = False
            reasons.append("🛑 Max drawdown reached")
        elif daily_pnl_pct < -4:
            take_trade = False
            reasons.append("🛑 Daily loss limit")
        elif ml_confidence < 55:  # Lowered from 65 to allow 58%+ ML threshold signals
            take_trade = False
            reasons.append("🛑 Low confidence signal")

        # Calculate max positions dynamically
        max_positions = self._calculate_max_positions(
            equity_ratio, win_rate if len(recent_trades) > 0 else 0.5, drawdown_pct
        )

        return {
            'risk_pct': risk_pct,
            'take_trade': take_trade,
            'max_positions': max_positions,
            'reasons': reasons,
            'confidence': ml_confidence
        }

    def _calculate_streak(self, trade_history: List[Dict]) -> int:
        """Calculate current win/loss streak"""
        if not trade_history:
            return 0

        streak = 0
        for trade in reversed(trade_history):
            pnl = trade.get('pnl', 0)
            if pnl > 0:
                if streak >= 0:
                    streak += 1
                else:
                    break
            elif pnl < 0:
                if streak <= 0:
                    streak -= 1
                else:
                    break
            else:
                break

        return streak

    def _max_consecutive_losses(self, trade_history: List[Dict]) -> int:
        """Find maximum consecutive losses in history"""
        if not trade_history:
            return 0

        max_losses = 0
        current_losses = 0

        for trade in trade_history:
            if trade.get('pnl', 0) < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0

        return max_losses

    def _calculate_sharpe(self, trade_history: List[Dict], periods: int = 50) -> float:
        """Calculate Sharpe ratio from recent trades"""
        recent = trade_history[-periods:] if len(trade_history) >= periods else trade_history

        if len(recent) < 5:
            return 1.0  # Neutral

        returns = [t.get('pnl', 0) / 100000 * 100 for t in recent]  # % returns

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 1.0

        sharpe = mean_return / std_return * np.sqrt(252)  # Annualized
        return max(0, min(sharpe, 5))  # Clip to reasonable range

    def _calculate_profit_factor(self, trade_history: List[Dict]) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        if not trade_history:
            return 1.0

        wins = sum(t.get('pnl', 0) for t in trade_history if t.get('pnl', 0) > 0)
        losses = abs(sum(t.get('pnl', 0) for t in trade_history if t.get('pnl', 0) < 0))

        if losses == 0:
            return 3.0  # Max

        pf = wins / losses
        return min(pf, 5.0)  # Clip

    def _calculate_max_positions(self, equity_ratio: float, win_rate: float, drawdown_pct: float) -> int:
        """Dynamic position limits based on performance"""

        # Start with baseline
        max_pos = 3

        # Increase if doing well
        if equity_ratio > 1.05 and win_rate > 0.6:
            max_pos = 5
        elif equity_ratio > 1.02 and win_rate > 0.55:
            max_pos = 4

        # Decrease if struggling
        if drawdown_pct > 3 or win_rate < 0.4:
            max_pos = 2
        if drawdown_pct > 4:
            max_pos = 1

        return max_pos

    def save(self, filepath: str):
        """Save risk manager state"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'decision_history': self.decision_history,
                'baseline_risk': self.baseline_risk
            }, f)
        logger.info(f"✅ ML Risk Manager saved to {filepath}")

    @classmethod
    def load(cls, filepath: str):
        """Load risk manager state"""
        manager = cls()
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            manager.decision_history = data.get('decision_history', [])
            manager.baseline_risk = data.get('baseline_risk', 1.0)
            logger.info(f"✅ ML Risk Manager loaded from {filepath}")
        except FileNotFoundError:
            logger.warning(f"⚠️ No saved state found at {filepath}, using defaults")
        return manager


class RLRiskOptimizer:
    """
    RL-based risk optimizer that learns from actual trading outcomes
    Adjusts risk multiplier based on observed performance
    """

    def __init__(self):
        self.state_history = []
        self.reward_history = []
        self.learning_rate = 0.1
        self.gamma = 0.95  # Discount factor

        # Simple Q-table for risk multipliers
        self.risk_multipliers = np.linspace(0.5, 2.0, 10)
        self.q_table = {}  # state_hash -> action_values

    def get_risk_multiplier(self,
                           balance: float,
                           equity: float,
                           win_rate: float,
                           sharpe: float,
                           drawdown_pct: float) -> float:
        """
        Get risk multiplier based on current state
        Returns: 0.5x to 2.0x multiplier
        """

        # Discretize state
        state = self._discretize_state(equity/balance, win_rate, sharpe, drawdown_pct)
        state_hash = hash(state)

        # Initialize Q-values if new state
        if state_hash not in self.q_table:
            self.q_table[state_hash] = np.ones(len(self.risk_multipliers))

        # Epsilon-greedy: 90% exploit, 10% explore
        if np.random.random() < 0.1:
            action_idx = np.random.randint(len(self.risk_multipliers))
        else:
            action_idx = np.argmax(self.q_table[state_hash])

        multiplier = self.risk_multipliers[action_idx]

        # Store for learning
        self.state_history.append((state_hash, action_idx))

        return multiplier

    def update(self, reward: float):
        """Update Q-values based on reward (called after trade closes)"""
        if not self.state_history:
            return

        state_hash, action_idx = self.state_history[-1]

        # Q-learning update
        current_q = self.q_table[state_hash][action_idx]
        max_next_q = np.max(self.q_table[state_hash])  # Simplified

        new_q = current_q + self.learning_rate * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state_hash][action_idx] = new_q

        self.reward_history.append(reward)

    def _discretize_state(self, equity_ratio: float, win_rate: float,
                         sharpe: float, drawdown_pct: float) -> tuple:
        """Convert continuous state to discrete bins"""

        equity_bin = int(np.clip(equity_ratio, 0.9, 1.1) * 10) - 9  # 0-2
        wr_bin = int(np.clip(win_rate, 0, 1) * 5)  # 0-5
        sharpe_bin = int(np.clip(sharpe, 0, 3))  # 0-3
        dd_bin = int(np.clip(drawdown_pct, 0, 5))  # 0-5

        return (equity_bin, wr_bin, sharpe_bin, dd_bin)

    def reset(self):
        """
        PROFESSIONAL SOLUTION: Reset RL optimizer after major system changes

        Call this when:
        - Fixing major bugs in position sizing or exits
        - Deploying new ML models
        - Major strategy changes

        This gives the NEW system a clean slate instead of being penalized
        for the OLD system's performance.
        """
        self.state_history = []
        self.reward_history = []
        self.q_table = {}
        logger.info("🔄 RL Risk Optimizer RESET - Clean slate for new system")
        logger.info("   Starting fresh with baseline risk multipliers")
        logger.info("   Will learn from NEW system's performance only")

    def save(self, filepath: str):
        """Save RL optimizer state"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'q_table': self.q_table,
                'reward_history': self.reward_history
            }, f)
        logger.info(f"✅ RL Risk Optimizer saved to {filepath}")

    @classmethod
    def load(cls, filepath: str):
        """Load RL optimizer state"""
        optimizer = cls()
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            optimizer.q_table = data.get('q_table', {})
            optimizer.reward_history = data.get('reward_history', [])
            logger.info(f"✅ RL Risk Optimizer loaded from {filepath}")
        except FileNotFoundError:
            logger.warning(f"⚠️ No saved state found at {filepath}, using defaults")
        return optimizer
