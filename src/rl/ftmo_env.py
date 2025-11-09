"""
FTMO-Compliant Trading Environment
===================================
Gym environment for training PPO agent with FTMO prop trading rules.

FTMO Rules Enforced:
- Max Daily Loss: $5,000 (5% of $100K)
- Max Total Drawdown: $10,000 (10% of $100K)
- Realistic US30 spreads, slippage, commissions

State Space: ~600 features (multi-timeframe + regime + account)
Action Space: Continuous [direction, size, stop_loss, take_profit]
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class FTMOTradingEnv(gym.Env):
    """
    FTMO-compliant trading environment for US30.

    Enforces FTMO challenge rules:
    - Phase 1: $10K profit target, $5K max daily loss, $10K max total DD
    - Realistic market conditions (spread, slippage, commission)
    """

    metadata = {'render.modes': ['human']}

    def __init__(
        self,
        data: Dict[str, pd.DataFrame],  # {'M1': df, 'M5': df, 'H1': df, ...}
        initial_balance: float = 100000.0,
        max_daily_loss: float = 5000.0,
        max_total_drawdown: float = 10000.0,
        spread_points: float = 10.0,
        slippage_points: float = 2.0,
        commission_per_lot: float = 0.0,
        max_position_size: float = 10.0,  # Max lots
        lookback_bars: int = 100,
    ):
        super().__init__()

        # Market data
        self.data = data
        self.m1_data = data['M1'] if 'M1' in data else None
        self.current_step = lookback_bars
        self.lookback_bars = lookback_bars
        self.max_steps = len(self.m1_data) - 1 if self.m1_data is not None else 1000

        # FTMO rules
        self.initial_balance = initial_balance
        self.max_daily_loss = max_daily_loss
        self.max_total_drawdown = max_total_drawdown

        # Trading costs
        self.spread_points = spread_points
        self.slippage_points = slippage_points
        self.commission_per_lot = commission_per_lot
        self.max_position_size = max_position_size

        # Account state
        self.balance = initial_balance
        self.equity = initial_balance
        self.peak_balance = initial_balance
        self.daily_start_balance = initial_balance
        self.daily_pnl = 0.0
        self.total_drawdown = 0.0

        # Position state
        self.position = None  # {'direction': 1/-1, 'size': lots, 'entry_price': float, 'sl': float, 'tp': float, 'entry_step': int}

        # Episode tracking
        self.episode_trades = []
        self.episode_returns = []
        self.steps_since_last_trade = 0

        # Action space: [direction, size, stop_loss_atr, take_profit_atr]
        # direction: -1 (short) to +1 (long), 0 = close/no position
        # size: 0.0 to 1.0 (fraction of max safe position)
        # stop_loss_atr: 0.5 to 3.0 (ATR multiplier)
        # take_profit_atr: 1.5 to 6.0 (ATR multiplier)
        self.action_space = spaces.Box(
            low=np.array([-1.0, 0.0, 0.5, 1.5]),
            high=np.array([1.0, 1.0, 3.0, 6.0]),
            dtype=np.float32
        )

        # Observation space: Will be filled by state encoder
        # For now, define high-dimensional space
        # Transformer will encode multi-timeframe data
        # Additional features: account state, position, indicators
        self.observation_space = spaces.Dict({
            'market_state': spaces.Box(low=-np.inf, high=np.inf, shape=(512,), dtype=np.float32),  # Transformer embedding
            'account_state': spaces.Box(low=-np.inf, high=np.inf, shape=(12,), dtype=np.float32),
            'position_state': spaces.Box(low=-np.inf, high=np.inf, shape=(6,), dtype=np.float32),
            'indicators': spaces.Box(low=-np.inf, high=np.inf, shape=(20,), dtype=np.float32),
        })

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict, Dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)

        # Reset account
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.peak_balance = self.initial_balance
        self.daily_start_balance = self.initial_balance
        self.daily_pnl = 0.0
        self.total_drawdown = 0.0

        # Reset position
        self.position = None

        # Reset episode tracking
        self.episode_trades = []
        self.episode_returns = []
        self.steps_since_last_trade = 0

        # Random starting point (but ensure enough lookback)
        if self.m1_data is not None:
            self.current_step = np.random.randint(
                self.lookback_bars,
                max(self.lookback_bars + 1, len(self.m1_data) - 1000)
            )
        else:
            self.current_step = self.lookback_bars

        # Get initial observation
        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def step(self, action: np.ndarray) -> Tuple[Dict, float, bool, bool, Dict]:
        """
        Execute one timestep.

        Args:
            action: [direction, size, stop_loss_atr, take_profit_atr]

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Parse action
        direction_raw, size_fraction, sl_atr, tp_atr = action

        # Current market price
        current_price = self._get_current_price()
        atr = self._get_atr()

        # Manage existing position
        if self.position is not None:
            # Check stop loss / take profit
            if self._check_position_exit(current_price):
                realized_pnl = self._close_position(current_price)
            else:
                # Update unrealized P&L
                self.equity = self.balance + self._get_unrealized_pnl(current_price)

        # Determine if we should open new position
        # Direction threshold: Only trade if strong signal (> 0.3)
        should_trade = abs(direction_raw) > 0.3 and self.position is None

        if should_trade and size_fraction > 0.1:
            # Determine direction
            direction = 1 if direction_raw > 0 else -1

            # Calculate position size
            max_safe_size = self._calculate_max_safe_position(atr, sl_atr)
            position_size = max_safe_size * size_fraction
            position_size = min(position_size, self.max_position_size)
            position_size = max(position_size, 0.1)  # Minimum 0.1 lot

            # Calculate SL/TP
            if direction == 1:
                entry_price = current_price + self.spread_points + self.slippage_points
                stop_loss = entry_price - (atr * sl_atr)
                take_profit = entry_price + (atr * tp_atr)
            else:
                entry_price = current_price - self.slippage_points
                stop_loss = entry_price + (atr * sl_atr)
                take_profit = entry_price - (atr * tp_atr)

            # Open position
            self.position = {
                'direction': direction,
                'size': position_size,
                'entry_price': entry_price,
                'sl': stop_loss,
                'tp': take_profit,
                'entry_step': self.current_step,
            }

            # Deduct commission
            commission = self.commission_per_lot * position_size
            self.balance -= commission

            self.steps_since_last_trade = 0

        # Move to next timestep
        self.current_step += 1
        self.steps_since_last_trade += 1

        # Check if new trading day (reset daily P&L)
        if self._is_new_trading_day():
            self.daily_start_balance = self.balance
            self.daily_pnl = 0.0

        # Calculate reward
        reward = self._calculate_reward()

        # Check termination conditions
        terminated = self._check_ftmo_violation()
        truncated = self.current_step >= self.max_steps

        # Get next observation
        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _get_observation(self) -> Dict:
        """
        Build observation dict.

        Note: Transformer encoding will happen in custom feature extractor.
        Here we just return raw data + processed features.
        """
        # Account state (12 features)
        daily_loss = abs(min(0, self.daily_pnl))
        total_dd = abs(min(0, self.equity - self.peak_balance))

        account_state = np.array([
            self.balance / self.initial_balance,  # Normalized balance
            self.equity / self.initial_balance,
            self.daily_pnl / self.initial_balance,
            daily_loss / self.max_daily_loss,  # How close to daily limit
            total_dd / self.max_total_drawdown,  # How close to DD limit
            (self.max_daily_loss - daily_loss) / self.max_daily_loss,  # Distance to daily limit
            (self.max_total_drawdown - total_dd) / self.max_total_drawdown,  # Distance to DD limit
            self.peak_balance / self.initial_balance,
            (self.equity - self.initial_balance) / self.initial_balance,  # Total return
            self._get_current_step_in_day() / 1440.0,  # Time of day (normalized)
            self._get_day_of_week() / 7.0,
            self.steps_since_last_trade / 100.0,
        ], dtype=np.float32)

        # Position state (6 features)
        if self.position is not None:
            current_price = self._get_current_price()
            unrealized_pnl = self._get_unrealized_pnl(current_price)
            position_state = np.array([
                1.0,  # Has position
                self.position['direction'],
                self.position['size'] / self.max_position_size,
                unrealized_pnl / self.balance,
                (current_price - self.position['entry_price']) / self.position['entry_price'],
                (self.current_step - self.position['entry_step']) / 100.0,
            ], dtype=np.float32)
        else:
            position_state = np.zeros(6, dtype=np.float32)

        # Indicators (20 features)
        # ATR, RSI, MACD, etc.
        indicators = self._calculate_indicators()

        # Market state embedding (will be processed by Transformer)
        # For now, return zeros - Transformer will fill this
        market_state = np.zeros(512, dtype=np.float32)

        return {
            'market_state': market_state,
            'account_state': account_state,
            'position_state': position_state,
            'indicators': indicators,
        }

    def _calculate_reward(self) -> float:
        """
        FTMO-optimized reward function.

        Prioritizes:
        1. Realized P&L (primary objective)
        2. Avoiding FTMO violations (critical)
        3. Consistent profits (bonus)
        4. Risk-adjusted returns (bonus)
        """
        reward = 0.0

        # 1. Realized P&L (when trade closes)
        if len(self.episode_trades) > 0:
            last_trade = self.episode_trades[-1]
            if last_trade['close_step'] == self.current_step - 1:
                pnl_reward = last_trade['pnl'] / self.initial_balance * 1000  # Scale up
                reward += pnl_reward

        # 2. FTMO violation penalties (CRITICAL)
        daily_loss = abs(min(0, self.daily_pnl))
        total_dd = abs(min(0, self.equity - self.peak_balance))

        # Progressive penalties as we approach limits
        if daily_loss > 4000:  # $4K of $5K limit
            reward -= 100
        elif daily_loss > 3000:
            reward -= 50
        elif daily_loss > 2000:
            reward -= 20

        if total_dd > 8000:  # $8K of $10K limit
            reward -= 100
        elif total_dd > 6000:
            reward -= 50

        # Catastrophic penalty for violation
        if daily_loss >= self.max_daily_loss or total_dd >= self.max_total_drawdown:
            reward -= 1000

        # 3. Consistency bonus (reward steady profits)
        if self.daily_pnl > 0:
            consistency_bonus = min(self.daily_pnl / 1000, 5.0)  # Max +5 for $1K day
            reward += consistency_bonus

        # 4. Holding penalty (opportunity cost)
        if self.position is not None:
            bars_held = self.current_step - self.position['entry_step']
            hold_penalty = -0.01 * (bars_held / 60)  # Small penalty per hour
            reward += hold_penalty

        # 5. Risk-reward bonus (encourage 2:1+ trades)
        if len(self.episode_trades) > 0:
            last_trade = self.episode_trades[-1]
            if last_trade['close_step'] == self.current_step - 1 and last_trade['pnl'] > 0:
                risk = abs(last_trade['entry_price'] - last_trade['sl'])
                profit = last_trade['pnl']
                if risk > 0:
                    rr_ratio = profit / risk
                    if rr_ratio > 2.0:
                        reward += 2.0
                    elif rr_ratio > 1.5:
                        reward += 1.0

        # 6. Overtrading penalty
        if len(self.episode_trades) > 10:
            reward -= 2.0 * (len(self.episode_trades) - 10)

        # 7. Progress toward profit target
        total_pnl = self.balance - self.initial_balance
        profit_target = 10000  # Phase 1 target
        target_progress = (total_pnl / profit_target) * 10
        reward += target_progress * 0.1

        return reward

    def _check_position_exit(self, current_price: float) -> bool:
        """Check if position should be closed (SL/TP hit)."""
        if self.position is None:
            return False

        direction = self.position['direction']
        sl = self.position['sl']
        tp = self.position['tp']

        if direction == 1:  # Long
            if current_price <= sl or current_price >= tp:
                return True
        else:  # Short
            if current_price >= sl or current_price <= tp:
                return True

        return False

    def _close_position(self, exit_price: float) -> float:
        """Close position and return realized P&L."""
        if self.position is None:
            return 0.0

        # Calculate P&L
        direction = self.position['direction']
        size = self.position['size']
        entry_price = self.position['entry_price']

        # US30: 1 point = $1 per lot
        point_value = 1.0

        if direction == 1:  # Long
            pnl = (exit_price - entry_price) * size * point_value
        else:  # Short
            pnl = (entry_price - exit_price) * size * point_value

        # Subtract commission on exit
        commission = self.commission_per_lot * size
        pnl -= commission

        # Update account
        self.balance += pnl
        self.equity = self.balance
        self.daily_pnl += pnl

        # Update peak balance
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        # Record trade
        self.episode_trades.append({
            'entry_step': self.position['entry_step'],
            'close_step': self.current_step,
            'direction': direction,
            'size': size,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'sl': self.position['sl'],
            'tp': self.position['tp'],
            'pnl': pnl,
        })

        # Clear position
        self.position = None

        return pnl

    def _get_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L of open position."""
        if self.position is None:
            return 0.0

        direction = self.position['direction']
        size = self.position['size']
        entry_price = self.position['entry_price']
        point_value = 1.0

        if direction == 1:
            return (current_price - entry_price) * size * point_value
        else:
            return (entry_price - current_price) * size * point_value

    def _calculate_max_safe_position(self, atr: float, sl_atr: float) -> float:
        """
        Calculate max position size based on 2% risk rule.

        Risk = (ATR × SL_multiplier) × position_size
        Max Risk = 2% of balance
        position_size = (balance × 0.02) / (ATR × SL_multiplier)
        """
        risk_per_trade = self.balance * 0.02
        stop_distance = atr * sl_atr

        if stop_distance > 0:
            max_size = risk_per_trade / stop_distance
            return min(max_size, self.max_position_size)

        return 1.0  # Default

    def _check_ftmo_violation(self) -> bool:
        """Check if FTMO rules violated (episode termination)."""
        daily_loss = abs(min(0, self.daily_pnl))
        total_dd = abs(min(0, self.equity - self.peak_balance))

        if daily_loss >= self.max_daily_loss:
            logger.warning(f"FTMO VIOLATION: Daily loss ${daily_loss:.2f} >= ${self.max_daily_loss:.2f}")
            return True

        if total_dd >= self.max_total_drawdown:
            logger.warning(f"FTMO VIOLATION: Total DD ${total_dd:.2f} >= ${self.max_total_drawdown:.2f}")
            return True

        return False

    def _get_current_price(self) -> float:
        """Get current market price (mid price)."""
        if self.m1_data is not None and self.current_step < len(self.m1_data):
            return self.m1_data.iloc[self.current_step]['close']
        return 50000.0  # Default US30 price

    def _get_atr(self, period: int = 14) -> float:
        """Calculate ATR."""
        if self.m1_data is not None and self.current_step >= period:
            data = self.m1_data.iloc[self.current_step - period:self.current_step]
            high = data['high']
            low = data['low']
            close = data['close'].shift(1)

            tr1 = high - low
            tr2 = abs(high - close)
            tr3 = abs(low - close)
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            atr = tr.mean()
            return atr if atr > 0 else 100.0

        return 100.0  # Default ATR for US30

    def _calculate_indicators(self) -> np.ndarray:
        """Calculate technical indicators for state."""
        if self.m1_data is None or self.current_step < 50:
            return np.zeros(20, dtype=np.float32)

        data = self.m1_data.iloc[max(0, self.current_step - 100):self.current_step]

        # ATR
        atr = self._get_atr()
        atr_norm = atr / data['close'].iloc[-1] if len(data) > 0 else 0

        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss if loss.iloc[-1] > 0 else 100
        rsi = 100 - (100 / (1 + rs.iloc[-1])) if len(rs) > 0 else 50

        # Moving averages
        ma20 = data['close'].rolling(20).mean().iloc[-1] if len(data) >= 20 else data['close'].iloc[-1]
        ma50 = data['close'].rolling(50).mean().iloc[-1] if len(data) >= 50 else data['close'].iloc[-1]
        current_price = data['close'].iloc[-1]

        # Volume
        avg_volume = data['volume'].mean() if 'volume' in data else 1.0
        current_volume = data['volume'].iloc[-1] if 'volume' in data and len(data) > 0 else 1.0
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        indicators = np.array([
            atr_norm,
            rsi / 100.0,
            (current_price - ma20) / current_price if current_price > 0 else 0,
            (current_price - ma50) / current_price if current_price > 0 else 0,
            volume_ratio,
            # Padding for future indicators
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ], dtype=np.float32)

        return indicators

    def _get_current_step_in_day(self) -> int:
        """Get current M1 bar number within the day (0-1439)."""
        return self.current_step % 1440

    def _get_day_of_week(self) -> int:
        """Get day of week (0-6)."""
        return (self.current_step // 1440) % 7

    def _is_new_trading_day(self) -> bool:
        """Check if we've moved to a new trading day."""
        if self.current_step % 1440 == 0:
            return True
        return False

    def _get_info(self) -> Dict:
        """Return info dict for logging."""
        daily_loss = abs(min(0, self.daily_pnl))
        total_dd = abs(min(0, self.equity - self.peak_balance))

        return {
            'balance': self.balance,
            'equity': self.equity,
            'daily_pnl': self.daily_pnl,
            'daily_loss': daily_loss,
            'total_drawdown': total_dd,
            'distance_to_daily_limit': self.max_daily_loss - daily_loss,
            'distance_to_dd_limit': self.max_total_drawdown - total_dd,
            'num_trades': len(self.episode_trades),
            'has_position': self.position is not None,
        }

    def render(self, mode='human'):
        """Render environment state."""
        if mode == 'human':
            daily_loss = abs(min(0, self.daily_pnl))
            total_dd = abs(min(0, self.equity - self.peak_balance))

            print(f"\n=== FTMO Trading Environment ===")
            print(f"Step: {self.current_step}")
            print(f"Balance: ${self.balance:,.2f}")
            print(f"Equity: ${self.equity:,.2f}")
            print(f"Daily P&L: ${self.daily_pnl:,.2f}")
            print(f"Daily Loss: ${daily_loss:,.2f} / ${self.max_daily_loss:,.2f}")
            print(f"Total DD: ${total_dd:,.2f} / ${self.max_total_drawdown:,.2f}")
            print(f"Trades: {len(self.episode_trades)}")
            print(f"Position: {self.position is not None}")
            if self.position:
                unrealized = self._get_unrealized_pnl(self._get_current_price())
                print(f"  Unrealized P&L: ${unrealized:,.2f}")
