"""
LLM Risk Manager - Strategic Oversight Layer
Analyzes account health and sets risk parameters for ML systems
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from groq import Groq
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMRiskManager:
    """
    LLM-based strategic risk manager
    
    Analyzes:
    - Account balance and equity
    - Trade history and performance
    - Drawdown levels
    - Win rates and profit factors
    - Market conditions
    
    Outputs:
    - Trading mode (AGGRESSIVE/NORMAL/CONSERVATIVE/STOP)
    - Risk multipliers for scalping and swing
    - Confidence threshold adjustments
    - Max positions allowed
    - Strategic reasoning
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GROQ_API_KEY')
        if not self.api_key:
            logger.warning("No Groq API key found, using fallback risk management")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)
        
        # Cache for risk parameters (updated every 60s)
        self.current_params = {
            'scalping_mode': 'NORMAL',
            'scalping_risk_multiplier': 1.0,
            'swing_mode': 'NORMAL',
            'swing_risk_multiplier': 1.0,
            'max_scalp_positions': 1,
            'max_swing_positions': 1,
            'scalping_threshold_adjustment': 0.0,
            'swing_threshold_adjustment': 0.0,
            'reasoning': 'Initial state',
            'timestamp': datetime.now()
        }
        
        logger.info("LLM Risk Manager initialized")
    
    def analyze_account_health(
        self,
        account_data: Dict,
        trade_history: List[Dict],
        market_data: Dict
    ) -> Dict:
        """
        Analyze account health and return risk parameters
        
        Args:
            account_data: {balance, equity, daily_pnl, drawdown, starting_balance}
            trade_history: List of recent trades with outcomes
            market_data: {regime, volatility, session}
            
        Returns:
            Risk parameters for both scalping and swing trading
        """
        try:
            # Calculate performance metrics
            metrics = self._calculate_metrics(account_data, trade_history)
            
            # Get LLM analysis if available
            if self.client:
                llm_params = self._get_llm_analysis(account_data, metrics, market_data)
            else:
                llm_params = self._fallback_analysis(account_data, metrics, market_data)
            
            # Update cache
            self.current_params = llm_params
            self.current_params['timestamp'] = datetime.now()
            
            logger.info(
                f"Risk Manager: Scalp={llm_params['scalping_mode']} ({llm_params['scalping_risk_multiplier']}x), "
                f"Swing={llm_params['swing_mode']} ({llm_params['swing_risk_multiplier']}x)"
            )
            
            return self.current_params
            
        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            return self.current_params  # Return cached params on error
    
    def _calculate_metrics(self, account_data: Dict, trade_history: List[Dict]) -> Dict:
        """Calculate performance metrics from trade history"""
        if not trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'avg_profit': 0.0,
                'max_loss': 0.0,
                'consecutive_losses': 0,
                'recent_trend': 'neutral'
            }
        
        # Last 24 hours of trades
        recent_trades = [t for t in trade_history if t.get('timestamp')]
        
        total_trades = len(recent_trades)
        winning_trades = sum(1 for t in recent_trades if t.get('profit', 0) > 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Profit factor
        total_profit = sum(t.get('profit', 0) for t in recent_trades if t.get('profit', 0) > 0)
        total_loss = abs(sum(t.get('profit', 0) for t in recent_trades if t.get('profit', 0) < 0))
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        # Average profit
        avg_profit = sum(t.get('profit', 0) for t in recent_trades) / total_trades if total_trades > 0 else 0
        
        # Max loss
        max_loss = min((t.get('profit', 0) for t in recent_trades), default=0)
        
        # Consecutive losses
        consecutive_losses = 0
        for trade in reversed(recent_trades):
            if trade.get('profit', 0) < 0:
                consecutive_losses += 1
            else:
                break
        
        # Recent trend (last 10 trades)
        recent_10 = recent_trades[-10:] if len(recent_trades) >= 10 else recent_trades
        recent_pnl = sum(t.get('profit', 0) for t in recent_10)
        recent_trend = 'positive' if recent_pnl > 0 else 'negative' if recent_pnl < 0 else 'neutral'
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_profit': avg_profit,
            'max_loss': max_loss,
            'consecutive_losses': consecutive_losses,
            'recent_trend': recent_trend
        }
    
    def _get_llm_analysis(
        self,
        account_data: Dict,
        metrics: Dict,
        market_data: Dict
    ) -> Dict:
        """Get risk analysis from Groq LLM"""
        
        prompt = f"""You are a professional risk manager for a US30 futures trading account.

ACCOUNT STATUS:
- Balance: ${account_data.get('balance', 0):.2f}
- Equity: ${account_data.get('equity', 0):.2f}
- Daily P/L: {account_data.get('daily_pnl', 0):.2f}%
- Total Drawdown: {account_data.get('drawdown', 0):.2f}%
- Starting Balance: ${account_data.get('starting_balance', 0):.2f}

RECENT PERFORMANCE (Last 24h):
- Total trades: {metrics['total_trades']}
- Win rate: {metrics['win_rate']:.1f}%
- Profit factor: {metrics['profit_factor']:.2f}
- Avg profit/trade: {metrics['avg_profit']:.2f}%
- Max single loss: {metrics['max_loss']:.2f}%
- Consecutive losses: {metrics['consecutive_losses']}
- Recent trend: {metrics['recent_trend']}

MARKET CONDITIONS:
- Regime: {market_data.get('regime', 'unknown')}
- Volatility: {market_data.get('volatility', 'normal')}
- Session: {market_data.get('session', 'unknown')}

RISK MANAGEMENT RULES:
1. If drawdown > 4.5%: STOP all trading
2. If daily loss > 4%: CONSERVATIVE mode
3. If consecutive losses > 5: Reduce risk
4. If win rate < 50%: CONSERVATIVE mode
5. If win rate > 75%: Can be AGGRESSIVE
6. Scalping: Fast trades, lower risk per trade
7. Swing: Slower trades, higher risk per trade

Based on this analysis, determine risk parameters for BOTH trading modes:

SCALPING MODE (M1 timeframe, 20-40 trades/day):
- mode: AGGRESSIVE / NORMAL / CONSERVATIVE / STOP
- risk_multiplier: 0.0 to 2.0 (applied to 0.5% base risk)
- threshold_adjustment: -20 to +30 (percentage points)

SWING MODE (H1/H4/D1 timeframe, 1-5 trades/day):
- mode: AGGRESSIVE / NORMAL / CONSERVATIVE / STOP
- risk_multiplier: 0.0 to 2.0 (applied to 1.0% base risk)
- threshold_adjustment: -20 to +30 (percentage points)

POSITION LIMITS:
- max_scalp_positions: 0 to 2
- max_swing_positions: 0 to 2

Provide brief reasoning for your decisions.

Respond ONLY with valid JSON in this exact format:
{{
    "scalping_mode": "NORMAL",
    "scalping_risk_multiplier": 1.0,
    "scalping_threshold_adjustment": 0.0,
    "swing_mode": "NORMAL",
    "swing_risk_multiplier": 1.0,
    "swing_threshold_adjustment": 0.0,
    "max_scalp_positions": 1,
    "max_swing_positions": 1,
    "reasoning": "Brief explanation"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a professional trading risk manager. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            params = json.loads(content)
            
            # Validate and sanitize
            params['scalping_risk_multiplier'] = max(0.0, min(2.0, params.get('scalping_risk_multiplier', 1.0)))
            params['swing_risk_multiplier'] = max(0.0, min(2.0, params.get('swing_risk_multiplier', 1.0)))
            params['scalping_threshold_adjustment'] = max(-20.0, min(30.0, params.get('scalping_threshold_adjustment', 0.0)))
            params['swing_threshold_adjustment'] = max(-20.0, min(30.0, params.get('swing_threshold_adjustment', 0.0)))
            params['max_scalp_positions'] = max(0, min(2, params.get('max_scalp_positions', 1)))
            params['max_swing_positions'] = max(0, min(2, params.get('max_swing_positions', 1)))
            
            return params
            
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            return self._fallback_analysis(account_data, metrics, market_data)
    
    def _fallback_analysis(
        self,
        account_data: Dict,
        metrics: Dict,
        market_data: Dict
    ) -> Dict:
        """Fallback rule-based risk management if LLM unavailable"""
        
        drawdown = account_data.get('drawdown', 0)
        daily_pnl = account_data.get('daily_pnl', 0)
        win_rate = metrics.get('win_rate', 0)
        consecutive_losses = metrics.get('consecutive_losses', 0)
        
        # Determine modes
        if drawdown > 4.5:
            scalping_mode = 'STOP'
            swing_mode = 'STOP'
            scalp_risk = 0.0
            swing_risk = 0.0
            scalp_threshold = 50.0
            swing_threshold = 50.0
            reasoning = "STOP: Drawdown limit reached"
        
        elif daily_pnl < -4.0:
            scalping_mode = 'CONSERVATIVE'
            swing_mode = 'CONSERVATIVE'
            scalp_risk = 0.3
            swing_risk = 0.5
            scalp_threshold = 25.0
            swing_threshold = 20.0
            reasoning = "CONSERVATIVE: Large daily loss"
        
        elif consecutive_losses > 5:
            scalping_mode = 'CONSERVATIVE'
            swing_mode = 'NORMAL'
            scalp_risk = 0.5
            swing_risk = 0.8
            scalp_threshold = 20.0
            swing_threshold = 10.0
            reasoning = "CONSERVATIVE scalping: Too many consecutive losses"
        
        elif win_rate > 75 and daily_pnl > 2.0:
            scalping_mode = 'AGGRESSIVE'
            swing_mode = 'AGGRESSIVE'
            scalp_risk = 1.5
            swing_risk = 1.5
            scalp_threshold = -15.0
            swing_threshold = -10.0
            reasoning = "AGGRESSIVE: Excellent performance"
        
        elif win_rate < 50:
            scalping_mode = 'CONSERVATIVE'
            swing_mode = 'CONSERVATIVE'
            scalp_risk = 0.6
            swing_risk = 0.7
            scalp_threshold = 15.0
            swing_threshold = 15.0
            reasoning = "CONSERVATIVE: Low win rate"
        
        else:
            scalping_mode = 'NORMAL'
            swing_mode = 'NORMAL'
            scalp_risk = 1.0
            swing_risk = 1.0
            scalp_threshold = 0.0
            swing_threshold = 0.0
            reasoning = "NORMAL: Standard conditions"
        
        return {
            'scalping_mode': scalping_mode,
            'scalping_risk_multiplier': scalp_risk,
            'scalping_threshold_adjustment': scalp_threshold,
            'swing_mode': swing_mode,
            'swing_risk_multiplier': swing_risk,
            'swing_threshold_adjustment': swing_threshold,
            'max_scalp_positions': 0 if scalping_mode == 'STOP' else 1,
            'max_swing_positions': 0 if swing_mode == 'STOP' else 1,
            'reasoning': reasoning
        }
    
    def get_current_params(self) -> Dict:
        """Get cached risk parameters (for fast access)"""
        return self.current_params
    
    def should_allow_scalping(self) -> bool:
        """Quick check if scalping is allowed"""
        return self.current_params['scalping_mode'] != 'STOP'
    
    def should_allow_swing(self) -> bool:
        """Quick check if swing trading is allowed"""
        return self.current_params['swing_mode'] != 'STOP'
