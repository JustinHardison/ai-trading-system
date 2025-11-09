"""
ML-Based Risk Manager with FTMO Rules
Fast, consistent, no API calls, learns from your data
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pickle
from pathlib import Path

from src.utils.logger import get_logger
from src.data.economic_calendar import EconomicCalendar
from src.utils.market_hours import MarketHours

logger = get_logger(__name__)


class MLRiskManager:
    """
    ML-based risk management with FTMO rules
    
    Features:
    - Dynamic position sizing based on account performance
    - FTMO rule compliance (daily loss, total drawdown)
    - Learns from historical account states
    - No API calls, instant decisions
    - Adjusts based on time of day and win rate
    
    FTMO Rules:
    - Max daily loss: 5% of starting balance
    - Max total drawdown: 10% of starting balance
    - Profit target: 10% (for evaluation)
    """
    
    def __init__(self, starting_balance: float = 10000.0):
        self.starting_balance = starting_balance
        
        # Economic Calendar
        self.calendar = EconomicCalendar()
        
        # Market Hours
        self.market_hours = MarketHours(timezone='America/New_York')
        
        # FTMO Rules
        self.max_daily_loss_pct = 5.0  # 5% max daily loss
        self.max_total_drawdown_pct = 10.0  # 10% max total drawdown
        self.profit_target_pct = 10.0  # 10% profit target
        
        # Performance tracking
        self.daily_start_balance = starting_balance
        self.daily_trades = []
        self.daily_pnl = 0.0
        self.peak_balance = starting_balance
        self.current_drawdown = 0.0
        
        # Risk parameters
        self.base_risk_per_trade = 0.5  # 0.5% base risk
        self.current_risk_multiplier = 1.0
        
        # Performance metrics
        self.win_rate = 0.0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.trades_today = 0
        
        logger.info(f"ML Risk Manager initialized: Starting balance ${starting_balance:,.2f}")
        logger.info(f"FTMO Rules: Max daily loss {self.max_daily_loss_pct}%, Max drawdown {self.max_total_drawdown_pct}%")
    
    def check_daily_reset(self):
        """Reset daily counters at midnight"""
        now = datetime.now()
        if hasattr(self, 'last_reset_date'):
            if now.date() > self.last_reset_date:
                self.daily_start_balance = self.peak_balance
                self.daily_trades = []
                self.daily_pnl = 0.0
                self.trades_today = 0
                self.last_reset_date = now.date()
                logger.info(f"📅 Daily reset: New starting balance ${self.daily_start_balance:,.2f}")
        else:
            self.last_reset_date = now.date()
    
    def get_risk_parameters(
        self,
        current_balance: float,
        current_equity: float,
        open_positions: int = 0
    ) -> Dict:
        """
        Calculate risk parameters based on account state and FTMO rules
        
        Returns:
            {
                'can_trade': bool,
                'risk_per_trade_pct': float,
                'max_positions': int,
                'position_size': float,
                'stop_loss_points': int,
                'take_profit_points': int,
                'risk_mode': str,
                'reason': str
            }
        """
        self.check_daily_reset()
        
        # Update metrics
        self.current_drawdown = ((self.peak_balance - current_equity) / self.peak_balance) * 100
        self.daily_pnl = ((current_equity - self.daily_start_balance) / self.daily_start_balance) * 100
        
        # Update peak
        if current_equity > self.peak_balance:
            self.peak_balance = current_equity
            self.current_drawdown = 0.0
        
        # FTMO RULE 1: Check daily loss limit
        daily_loss_limit = self.daily_start_balance * (self.max_daily_loss_pct / 100)
        daily_loss_amount = self.daily_start_balance - current_equity
        
        if daily_loss_amount >= daily_loss_limit:
            logger.error(f"🛑 FTMO VIOLATION: Daily loss limit reached (${daily_loss_amount:,.2f} >= ${daily_loss_limit:,.2f})")
            return self._stop_trading("Daily loss limit reached (FTMO rule)")
        
        # FTMO RULE 2: Check total drawdown limit
        if self.current_drawdown >= self.max_total_drawdown_pct:
            logger.error(f"🛑 FTMO VIOLATION: Total drawdown limit reached ({self.current_drawdown:.2f}% >= {self.max_total_drawdown_pct}%)")
            return self._stop_trading("Total drawdown limit reached (FTMO rule)")
        
        # MARKET HOURS: Check if market is open (hard stop only if closed)
        market_check = self.market_hours.should_trade_now()
        if not market_check['market_open']:
            logger.warning(f"🕐 MARKET CLOSED: {market_check['reason']}")
            return self._stop_trading(market_check['reason'])
        
        # NEWS RULE: Check for high-impact economic events
        news_check = self.calendar.should_avoid_trading(minutes_before=30, minutes_after=15)
        if news_check['avoid']:
            logger.warning(f"📰 NEWS ALERT: {news_check['reason']}")
            return self._stop_trading(news_check['reason'])
        
        # Calculate remaining risk budget for today
        remaining_daily_risk = daily_loss_limit - daily_loss_amount
        remaining_daily_risk_pct = (remaining_daily_risk / current_balance) * 100
        
        # DYNAMIC RISK ADJUSTMENT based on performance
        risk_multiplier = self._calculate_risk_multiplier()
        
        # SESSION RISK ADJUSTMENT (time of day)
        session_mult = market_check['risk_multiplier']
        risk_multiplier *= session_mult
        if session_mult != 1.0:
            logger.info(f"🕐 Session adjustment: {market_check['session']} ({session_mult}x)")
        
        # NEWS RISK ADJUSTMENT
        news_adjustment = self.calendar.get_news_risk_adjustment()
        risk_multiplier *= news_adjustment['risk_multiplier']
        if news_adjustment['risk_multiplier'] < 1.0:
            logger.info(f"📰 News risk adjustment: {news_adjustment['reason']}")
        
        # Base risk per trade (adjusted by multiplier)
        risk_per_trade_pct = min(
            self.base_risk_per_trade * risk_multiplier,
            remaining_daily_risk_pct / 2  # Never risk more than half of remaining daily budget
        )
        
        # Position sizing (for US30, ~$5 per point)
        risk_amount = current_balance * (risk_per_trade_pct / 100)
        
        # Dynamic stop loss based on volatility and risk
        stop_loss_points = self._calculate_dynamic_stop_loss()
        take_profit_points = stop_loss_points * 2  # 2:1 reward:risk
        
        # Position size = Risk Amount / (Stop Loss in points * Point Value)
        point_value = 5.0  # US30 ~$5 per point
        position_size = risk_amount / (stop_loss_points * point_value)
        position_size = round(position_size, 2)
        
        # Max positions based on risk state
        max_positions = self._calculate_max_positions()
        
        # Determine risk mode
        risk_mode = self._determine_risk_mode()
        
        # Can we trade?
        can_trade = (
            remaining_daily_risk_pct > 1.0 and  # At least 1% risk budget left
            self.current_drawdown < (self.max_total_drawdown_pct - 2.0) and  # 2% buffer
            open_positions < max_positions and
            risk_mode != "STOP"
        )
        
        # Reason
        if not can_trade:
            if remaining_daily_risk_pct <= 1.0:
                reason = f"Low daily risk budget ({remaining_daily_risk_pct:.1f}% left)"
            elif self.current_drawdown >= (self.max_total_drawdown_pct - 2.0):
                reason = f"Near drawdown limit ({self.current_drawdown:.1f}%)"
            elif open_positions >= max_positions:
                reason = f"Max positions reached ({open_positions}/{max_positions})"
            else:
                reason = "Risk mode: STOP"
        else:
            reason = f"Risk mode: {risk_mode}, {self.trades_today} trades today"
        
        result = {
            'can_trade': can_trade,
            'risk_per_trade_pct': risk_per_trade_pct,
            'max_positions': max_positions,
            'position_size': position_size,
            'stop_loss_points': stop_loss_points,
            'take_profit_points': take_profit_points,
            'risk_mode': risk_mode,
            'reason': reason,
            'daily_pnl': self.daily_pnl,
            'current_drawdown': self.current_drawdown,
            'remaining_daily_risk_pct': remaining_daily_risk_pct,
            'trades_today': self.trades_today
        }
        
        logger.info(
            f"💰 ML Risk: {risk_mode} | Risk/trade: {risk_per_trade_pct:.2f}% | "
            f"Daily P/L: {self.daily_pnl:+.2f}% | DD: {self.current_drawdown:.2f}% | "
            f"Trades: {self.trades_today}"
        )
        
        return result
    
    def _calculate_risk_multiplier(self) -> float:
        """
        Calculate risk multiplier based on recent performance
        
        Logic:
        - Winning streak: Increase risk slightly
        - Losing streak: Decrease risk significantly
        - High win rate: Increase risk
        - Low win rate: Decrease risk
        - Time of day: More aggressive during NY session
        """
        multiplier = 1.0
        
        # Consecutive wins/losses
        if self.consecutive_wins >= 3:
            multiplier *= 1.2  # 20% more risk after 3 wins
        elif self.consecutive_wins >= 5:
            multiplier *= 1.5  # 50% more risk after 5 wins
        
        if self.consecutive_losses >= 2:
            multiplier *= 0.7  # 30% less risk after 2 losses
        elif self.consecutive_losses >= 3:
            multiplier *= 0.5  # 50% less risk after 3 losses
        elif self.consecutive_losses >= 5:
            multiplier *= 0.3  # 70% less risk after 5 losses
        
        # Win rate adjustment
        if self.trades_today >= 5:  # Need at least 5 trades
            if self.win_rate > 0.7:  # 70%+ win rate
                multiplier *= 1.3
            elif self.win_rate > 0.6:  # 60%+ win rate
                multiplier *= 1.1
            elif self.win_rate < 0.4:  # <40% win rate
                multiplier *= 0.6
        
        # Daily P/L adjustment
        if self.daily_pnl > 2.0:  # Up 2%+ today
            multiplier *= 1.2  # Ride the hot streak
        elif self.daily_pnl < -2.0:  # Down 2%+ today
            multiplier *= 0.5  # Reduce risk when losing
        
        # Time of day (NY session bonus)
        hour = datetime.now().hour
        if 9 <= hour <= 16:  # NY session
            multiplier *= 1.1
        
        # Cap multiplier
        multiplier = max(0.2, min(multiplier, 2.0))
        
        return multiplier
    
    def _calculate_dynamic_stop_loss(self) -> int:
        """Calculate dynamic stop loss based on risk state"""
        # Base stop loss
        base_stop = 50  # 50 points base
        
        # Adjust based on consecutive losses
        if self.consecutive_losses >= 3:
            base_stop = 30  # Tighter stops when losing
        elif self.consecutive_wins >= 3:
            base_stop = 70  # Wider stops when winning
        
        # Adjust based on drawdown
        if self.current_drawdown > 5.0:
            base_stop = 30  # Very tight stops near limit
        
        return base_stop
    
    def _calculate_max_positions(self) -> int:
        """Calculate max positions based on risk state"""
        # Base: 1 position
        max_pos = 1
        
        # Increase if doing well
        if self.win_rate > 0.7 and self.trades_today >= 5:
            max_pos = 2
        
        # Decrease if struggling
        if self.consecutive_losses >= 3 or self.current_drawdown > 5.0:
            max_pos = 1
        
        return max_pos
    
    def _determine_risk_mode(self) -> str:
        """Determine current risk mode"""
        # STOP conditions
        if self.current_drawdown >= (self.max_total_drawdown_pct - 1.0):
            return "STOP"
        if self.daily_pnl <= -(self.max_daily_loss_pct - 1.0):
            return "STOP"
        
        # CONSERVATIVE conditions
        if self.consecutive_losses >= 3:
            return "CONSERVATIVE"
        if self.current_drawdown > 5.0:
            return "CONSERVATIVE"
        if self.daily_pnl < -2.0:
            return "CONSERVATIVE"
        
        # AGGRESSIVE conditions
        if self.consecutive_wins >= 3 and self.win_rate > 0.7:
            return "AGGRESSIVE"
        if self.daily_pnl > 3.0:
            return "AGGRESSIVE"
        
        # Default: NORMAL
        return "NORMAL"
    
    def _stop_trading(self, reason: str) -> Dict:
        """Return stop trading parameters"""
        return {
            'can_trade': False,
            'risk_per_trade_pct': 0.0,
            'max_positions': 0,
            'position_size': 0.0,
            'stop_loss_points': 0,
            'take_profit_points': 0,
            'risk_mode': "STOP",
            'reason': reason,
            'daily_pnl': self.daily_pnl,
            'current_drawdown': self.current_drawdown,
            'remaining_daily_risk_pct': 0.0,
            'trades_today': self.trades_today
        }
    
    def record_trade(self, profit_pct: float, profit_amount: float):
        """Record trade result and update metrics"""
        self.trades_today += 1
        self.daily_trades.append({
            'profit_pct': profit_pct,
            'profit_amount': profit_amount,
            'timestamp': datetime.now()
        })
        
        # Update win/loss streaks
        if profit_amount > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Update win rate
        if self.trades_today > 0:
            wins = sum(1 for t in self.daily_trades if t['profit_amount'] > 0)
            self.win_rate = wins / self.trades_today
        
        logger.info(
            f"📊 Trade recorded: {profit_amount:+.2f} ({profit_pct:+.2f}%) | "
            f"Win rate: {self.win_rate*100:.1f}% | "
            f"Streak: {self.consecutive_wins}W / {self.consecutive_losses}L"
        )
