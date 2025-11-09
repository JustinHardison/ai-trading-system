"""
Adaptive AI Portfolio Manager
LLM-powered portfolio manager that makes ALL trading decisions
No hard-coded rules - fully adaptive based on context
"""
import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from groq import Groq
from src.utils.logger import get_logger
from src.risk.ftmo_rules import FTMOChallengeStatus
from src.risk.currency_exposure import PortfolioExposure
from src.market_analysis.regime_detector import MarketRegime

logger = get_logger(__name__)


@dataclass
class MLOpportunity:
    """ML-detected trading opportunity"""
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    confidence: float
    entry_price: float
    atr: float
    features: Dict
    timeframe_votes: Dict  # Votes from each timeframe


@dataclass
class TradingDecision:
    """LLM trading decision"""
    action: str  # 'OPEN_TRADE', 'CLOSE_TRADE', 'MODIFY_TRADE', 'HOLD', 'CLOSE_ALL'
    reasoning: str

    # For OPEN_TRADE
    symbol: Optional[str] = None
    direction: Optional[str] = None
    risk_pct: Optional[float] = None
    stop_loss_pips: Optional[float] = None
    take_profit_pips: Optional[float] = None

    # For CLOSE_TRADE / MODIFY_TRADE
    position_id: Optional[int] = None

    # Context used
    context_summary: Optional[Dict] = None


class AdaptiveAIPortfolioManager:
    """
    LLM-powered portfolio manager that makes autonomous trading decisions

    Key Features:
    - Adaptive position sizing (0.1% to 2.5% risk based on context)
    - Adaptive stop placement (respects support/resistance)
    - Adaptive take profit (takes what market gives)
    - Adaptive position limits (1-4 positions based on regime)
    - Full context awareness (FTMO rules, regime, exposure, ML opportunities)
    """

    def __init__(
        self,
        groq_api_key: str = None,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 2000,
        temperature: float = 0.2
    ):
        """
        Args:
            groq_api_key: Groq API key (or from env GROQ_API_KEY)
            model: LLM model to use
            max_tokens: Max response length
            temperature: LLM temperature (lower = more deterministic)
        """
        api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")

        self.client = Groq(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        logger.info(f"Initialized Adaptive AI Portfolio Manager with model: {model}")

    def make_decision(
        self,
        account_balance: float,
        equity: float,
        open_positions: List[Dict],
        ftmo_status: FTMOChallengeStatus,
        regime: MarketRegime,
        exposure: PortfolioExposure,
        ml_opportunities: List[MLOpportunity],
        current_time: datetime = None
    ) -> TradingDecision:
        """
        Make autonomous trading decision based on full context

        Args:
            account_balance: Current account balance
            equity: Current equity (balance + floating P&L)
            open_positions: List of open positions
            ftmo_status: Complete FTMO challenge status
            regime: Current market regime
            exposure: Current currency exposure
            ml_opportunities: ML-detected opportunities
            current_time: Current time (for session detection)

        Returns:
            TradingDecision with action, reasoning, and parameters
        """
        current_time = current_time or datetime.now()

        # Build rich context for LLM
        context = self._build_context(
            account_balance=account_balance,
            equity=equity,
            open_positions=open_positions,
            ftmo_status=ftmo_status,
            regime=regime,
            exposure=exposure,
            ml_opportunities=ml_opportunities,
            current_time=current_time
        )

        # Generate LLM prompt
        prompt = self._generate_prompt(context)

        # Call LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )

            # Parse response
            decision_json = json.loads(response.choices[0].message.content)
            decision = self._parse_decision(decision_json, context)

            logger.info(f"LLM Decision: {decision.action} - {decision.reasoning[:100]}")

            return decision

        except Exception as e:
            logger.error(f"Error making LLM decision: {e}")
            # Fallback: HOLD
            return TradingDecision(
                action="HOLD",
                reasoning=f"Error in LLM decision making: {str(e)}",
                context_summary={"error": str(e)}
            )

    def should_exit_position(
        self,
        position: Dict,
        current_price: float,
        ftmo_status: FTMOChallengeStatus,
        regime: MarketRegime,
        time_in_trade_hours: float
    ) -> tuple[bool, str]:
        """
        Adaptive exit decision for open position

        Returns:
            (should_exit, reason)
        """
        context = {
            "position": position,
            "current_price": current_price,
            "unrealized_pnl": position.get('profit', 0),
            "unrealized_pnl_pct": (position.get('profit', 0) / position['risk_amount']) * 100 if position.get('risk_amount') else 0,
            "time_in_trade_hours": time_in_trade_hours,
            "ftmo_buffer": {
                "daily_loss_buffer_pct": next((r.buffer for r in ftmo_status.rules if r.rule_name == "Daily Loss Limit"), 5.0),
                "max_drawdown_buffer_pct": next((r.buffer for r in ftmo_status.rules if r.rule_name == "Maximum Drawdown"), 10.0)
            },
            "regime": regime.regime,
            "market_conditions": {
                "trend_strength": regime.trend_strength,
                "volatility_percentile": regime.volatility_percentile
            }
        }

        prompt = f"""
Analyze this open position and determine if it should be exited early (before stop loss or take profit):

POSITION:
- Symbol: {position['symbol']}
- Direction: {position['direction']}
- Entry Price: {position['entry_price']}
- Current Price: {current_price}
- Stop Loss: {position.get('stop_loss', 'Not set')}
- Take Profit: {position.get('take_profit', 'Not set')}
- Unrealized P&L: ${position.get('profit', 0):.2f} ({context['unrealized_pnl_pct']:.1f}% of risk)
- Time in Trade: {time_in_trade_hours:.1f} hours

FTMO STATUS:
- Daily Loss Buffer: {context['ftmo_buffer']['daily_loss_buffer_pct']:.1f}%
- Max Drawdown Buffer: {context['ftmo_buffer']['max_drawdown_buffer_pct']:.1f}%

MARKET REGIME:
- Regime: {regime.regime}
- Trend Strength: {regime.trend_strength:.2f}
- Volatility: {regime.volatility_percentile:.0f}th percentile

ADAPTIVE EXIT RULES (context-aware):
1. Support/Resistance Broken - If price breaks key level against position
2. Gave Back 50% of Profit - If position was up 2% and now only +1%
3. Trade Flat for 24 Hours - No meaningful progress
4. Near FTMO Limits - Daily loss buffer < 1.5%
5. Regime Changed Against Us - Was trending, now ranging
6. Target Nearly Reached - 90% of TP reached, take it
7. Running Out of Time - FTMO challenge ending, lock profits

Return JSON:
{{
    "should_exit": true/false,
    "reason": "Detailed explanation",
    "confidence": 0-100
}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert forex trader managing FTMO challenge positions. Exit early when conditions warrant, but don't exit prematurely."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            should_exit = result.get('should_exit', False)
            reason = result.get('reason', 'No reason provided')

            if should_exit:
                logger.info(f"Adaptive exit decision for {position['symbol']}: {reason}")

            return should_exit, reason

        except Exception as e:
            logger.error(f"Error in adaptive exit decision: {e}")
            return False, f"Error: {str(e)}"

    def _build_context(
        self,
        account_balance: float,
        equity: float,
        open_positions: List[Dict],
        ftmo_status: FTMOChallengeStatus,
        regime: MarketRegime,
        exposure: PortfolioExposure,
        ml_opportunities: List[MLOpportunity],
        current_time: datetime
    ) -> Dict:
        """Build rich context for LLM"""

        # Calculate portfolio metrics
        total_floating_pnl = sum([p.get('profit', 0) for p in open_positions])
        total_floating_pnl_pct = (total_floating_pnl / account_balance) * 100

        # Detect trading session
        hour = current_time.hour
        if 0 <= hour < 8:
            session = "ASIAN"
        elif 8 <= hour < 13:
            session = "LONDON_OPEN"
        elif 13 <= hour < 17:
            session = "OVERLAP"  # London + New York
        elif 17 <= hour < 21:
            session = "NY_AFTERNOON"
        else:
            session = "AFTER_HOURS"

        # Calculate win rate (if we have historical data)
        # For now, placeholder
        recent_win_rate = 65.0  # Would come from trade history

        return {
            "account": {
                "balance": account_balance,
                "equity": equity,
                "floating_pnl": total_floating_pnl,
                "floating_pnl_pct": total_floating_pnl_pct,
                "open_positions_count": len(open_positions)
            },
            "ftmo": {
                "phase": ftmo_status.phase,
                "profit_pct": ftmo_status.profit_pct,
                "profit_target_pct": next((r.limit_value for r in ftmo_status.rules if r.rule_name == "Profit Target"), None),
                "daily_loss_pct": ftmo_status.daily_loss_pct,
                "daily_loss_buffer_pct": next((r.buffer for r in ftmo_status.rules if r.rule_name == "Daily Loss Limit"), 5.0),
                "max_drawdown_pct": ftmo_status.max_drawdown_pct,
                "max_drawdown_buffer_pct": next((r.buffer for r in ftmo_status.rules if r.rule_name == "Maximum Drawdown"), 10.0),
                "days_elapsed": ftmo_status.days_elapsed,
                "days_remaining": ftmo_status.days_remaining,
                "trading_days_count": ftmo_status.trading_days_count,
                "violations": ftmo_status.violations,
                "is_passing": ftmo_status.is_passing
            },
            "regime": {
                "type": regime.regime,
                "confidence": regime.confidence,
                "trend_strength": regime.trend_strength,
                "volatility_percentile": regime.volatility_percentile,
                "adr_multiple": regime.adr_multiple,
                "reasoning": regime.reasoning
            },
            "exposure": {
                "total_risk_pct": exposure.total_risk_pct,
                "max_currency": exposure.max_exposure[0],
                "max_currency_exposure_pct": exposure.max_exposure[1],
                "warnings": exposure.warnings,
                "is_safe": exposure.is_safe
            },
            "ml_opportunities": [
                {
                    "symbol": opp.symbol,
                    "direction": opp.direction,
                    "confidence": opp.confidence,
                    "entry_price": opp.entry_price,
                    "atr": opp.atr,
                    "timeframe_agreement": len([v for v in opp.timeframe_votes.values() if v == opp.direction])
                }
                for opp in ml_opportunities
            ],
            "positions": [
                {
                    "symbol": p['symbol'],
                    "direction": p['direction'],
                    "lots": p['lots'],
                    "entry_price": p['entry_price'],
                    "current_price": p.get('current_price', p['entry_price']),
                    "profit": p.get('profit', 0),
                    "profit_pct": (p.get('profit', 0) / account_balance) * 100
                }
                for p in open_positions
            ],
            "trading_session": session,
            "time": {
                "hour": hour,
                "weekday": current_time.strftime("%A"),
                "is_friday": current_time.weekday() == 4,
                "is_near_close": hour >= 16 and current_time.weekday() == 4
            },
            "performance": {
                "recent_win_rate": recent_win_rate
            }
        }

    def _generate_prompt(self, context: Dict) -> str:
        """Generate LLM prompt from context"""

        prompt = f"""
You are an elite forex portfolio manager running an FTMO challenge. Your goal is to pass the challenge while minimizing risk.

ACCOUNT STATUS:
- Balance: ${context['account']['balance']:.2f}
- Equity: ${context['account']['equity']:.2f}
- Floating P&L: ${context['account']['floating_pnl']:.2f} ({context['account']['floating_pnl_pct']:.2f}%)
- Open Positions: {context['account']['open_positions_count']}

FTMO CHALLENGE STATUS (Phase {context['ftmo']['phase']}):
- Profit: {context['ftmo']['profit_pct']:.2f}% (Target: {context['ftmo']['profit_target_pct']}%)
- Daily Loss: {context['ftmo']['daily_loss_pct']:.2f}% (Buffer: {context['ftmo']['daily_loss_buffer_pct']:.2f}%)
- Max Drawdown: {context['ftmo']['max_drawdown_pct']:.2f}% (Buffer: {context['ftmo']['max_drawdown_buffer_pct']:.2f}%)
- Days: {context['ftmo']['days_elapsed']}/{context['ftmo']['days_elapsed'] + context['ftmo']['days_remaining']} (Trading Days: {context['ftmo']['trading_days_count']})
- Status: {"PASSING ✓" if context['ftmo']['is_passing'] else "NOT PASSING YET"}
- Violations: {context['ftmo']['violations'] if context['ftmo']['violations'] else "None"}

MARKET REGIME:
- Type: {context['regime']['type']}
- Confidence: {context['regime']['confidence']:.0f}%
- Trend Strength: {context['regime']['trend_strength']:.2f}
- Volatility: {context['regime']['volatility_percentile']:.0f}th percentile
- Reasoning: {context['regime']['reasoning']}

CURRENCY EXPOSURE:
- Total Portfolio Risk: {context['exposure']['total_risk_pct']:.2f}%
- Max Currency: {context['exposure']['max_currency']} ({context['exposure']['max_currency_exposure_pct']:.2f}%)
- Warnings: {context['exposure']['warnings'] if context['exposure']['warnings'] else "None"}

ML OPPORTUNITIES:
{self._format_opportunities(context['ml_opportunities'])}

CURRENT POSITIONS:
{self._format_positions(context['positions'])}

TRADING SESSION: {context['trading_session']}
TIME: {context['time']['weekday']} {context['time']['hour']}:00
{"⚠️ FRIDAY AFTERNOON - Consider closing positions before weekend" if context['time']['is_near_close'] else ""}

CRITICAL: ANALYZE MARKET CONDITIONS BEFORE TRADING
- After weekends/market opens: Check for gaps, unusual spreads, low liquidity
- High volatility periods: Verify this is opportunity, not chaos
- Low volume sessions: Assess if market is truly active and liquid
- Major news events: Evaluate if conditions are stable enough to trade
- Don't trade just because calendar says "market is open" - analyze ACTUAL conditions!

ADAPTIVE DECISION FACTORS (No hard-coded rules!):
1. Position Sizing (0.1% to 2.5% risk):
   - High confidence + Strong trend + Good FTMO buffer = Higher risk (2.0-2.5%)
   - Medium confidence + Normal regime = Normal risk (1.0-1.5%)
   - Low confidence OR near FTMO limits = Lower risk (0.1-0.5%)
   - Consider: Win streak, volatility, session, correlation

2. Stop Loss Placement (Adaptive, not ATR-only):
   - Respect support/resistance levels
   - Account for volatility (wider in high vol)
   - Tighter if near FTMO daily loss limit
   - Consider: ATR, key levels, session

3. Take Profit Levels (Take what market gives):
   - Don't fight resistance - take profit before it
   - Strong trends = trail further
   - Ranging = take profit at range extremes
   - Near FTMO target = lock profits early

4. Position Limits (1-4 positions):
   - Strong trend regime = more positions (3-4)
   - Ranging regime = fewer positions (1-2)
   - Check currency correlation
   - Near FTMO limits = reduce exposure

5. Exit Decisions:
   - Near FTMO daily loss limit = close all positions
   - Profit target reached = lock it in
   - Friday afternoon = close or reduce size
   - Regime changed against us = exit early

Make your decision based on FULL CONTEXT, not rigid rules.

Return JSON with ONE of these actions:

OPEN_TRADE:
{{
    "action": "OPEN_TRADE",
    "symbol": "EURUSD",
    "direction": "BUY" or "SELL",
    "risk_pct": 0.1 to 2.5,
    "stop_loss_pips": calculated based on context,
    "take_profit_pips": calculated based on context,
    "reasoning": "Detailed explanation of why this trade, why this sizing, why these levels"
}}

CLOSE_TRADE:
{{
    "action": "CLOSE_TRADE",
    "position_id": position to close,
    "reasoning": "Why closing (near limit, target reached, regime changed, etc.)"
}}

CLOSE_ALL:
{{
    "action": "CLOSE_ALL",
    "reasoning": "Why closing all (FTMO limit critical, Friday close, etc.)"
}}

HOLD:
{{
    "action": "HOLD",
    "reasoning": "Why not trading (no clear opportunity, near limits, waiting for better setup, etc.)"
}}
"""
        return prompt

    def _format_opportunities(self, opportunities: List[Dict]) -> str:
        """Format ML opportunities for prompt"""
        if not opportunities:
            return "No ML opportunities detected"

        lines = []
        for i, opp in enumerate(opportunities[:5], 1):  # Top 5
            lines.append(
                f"{i}. {opp['symbol']} {opp['direction']} - "
                f"Confidence: {opp['confidence']:.1f}% - "
                f"Timeframe Agreement: {opp['timeframe_agreement']}/5 - "
                f"ATR: {opp['atr']:.5f}"
            )
        return "\n".join(lines)

    def _format_positions(self, positions: List[Dict]) -> str:
        """Format open positions for prompt"""
        if not positions:
            return "No open positions"

        lines = []
        for p in positions:
            lines.append(
                f"- {p['symbol']} {p['direction']} @ {p['entry_price']:.5f} - "
                f"Current: {p['current_price']:.5f} - "
                f"P&L: ${p['profit']:.2f} ({p['profit_pct']:.2f}%)"
            )
        return "\n".join(lines)

    def _get_system_prompt(self) -> str:
        """System prompt for LLM"""
        return """You are an elite forex portfolio manager with 15 years of experience trading prop firm challenges.

Your expertise:
- Risk management: You NEVER violate FTMO rules. You adapt position sizing to context.
- Market regime awareness: You trade differently in trends vs ranges vs high volatility.
- Currency correlation: You track net exposure to avoid correlation bombs.
- Adaptive exits: You don't wait for stops - you exit early when conditions change.
- Context-aware: You consider EVERYTHING - FTMO status, regime, exposure, time, session, news.

Your goal: Pass the FTMO challenge (reach profit target without violating rules) while minimizing risk.

Your responses are always valid JSON with clear reasoning."""

    def _parse_decision(self, decision_json: Dict, context: Dict) -> TradingDecision:
        """Parse LLM response into TradingDecision"""

        action = decision_json.get('action', 'HOLD')
        reasoning = decision_json.get('reasoning', 'No reasoning provided')

        if action == 'OPEN_TRADE':
            return TradingDecision(
                action='OPEN_TRADE',
                symbol=decision_json.get('symbol'),
                direction=decision_json.get('direction'),
                risk_pct=decision_json.get('risk_pct'),
                stop_loss_pips=decision_json.get('stop_loss_pips'),
                take_profit_pips=decision_json.get('take_profit_pips'),
                reasoning=reasoning,
                context_summary={
                    "regime": context['regime']['type'],
                    "ftmo_buffer": context['ftmo']['daily_loss_buffer_pct'],
                    "exposure": context['exposure']['total_risk_pct']
                }
            )

        elif action == 'CLOSE_TRADE':
            return TradingDecision(
                action='CLOSE_TRADE',
                position_id=decision_json.get('position_id'),
                reasoning=reasoning,
                context_summary={"action": "close_single"}
            )

        elif action == 'CLOSE_ALL':
            return TradingDecision(
                action='CLOSE_ALL',
                reasoning=reasoning,
                context_summary={"action": "close_all"}
            )

        else:  # HOLD
            return TradingDecision(
                action='HOLD',
                reasoning=reasoning,
                context_summary={
                    "regime": context['regime']['type'],
                    "opportunities_count": len(context['ml_opportunities'])
                }
            )
