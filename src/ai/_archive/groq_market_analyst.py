"""
Groq LLM Market Analyst
Uses Groq's ultra-fast LLM for real-time market analysis and decision enhancement

This adds human-like reasoning on top of ML predictions
"""
import os
from groq import Groq
from typing import Dict, List, Optional
import json
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)


class GroqMarketAnalyst:
    """
    Advanced AI analyst using Groq LLM

    Capabilities:
    - Analyzes market conditions with human-like reasoning
    - Validates ML predictions with context awareness
    - Provides detailed trade rationale
    - Detects complex patterns ML might miss
    - Risk assessment and position sizing advice
    """

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"  # Groq's fastest, most capable

        logger.info("GroqMarketAnalyst initialized with llama-3.3-70b-versatile")

    def analyze_entry_opportunity(
        self,
        symbol: str,
        ml_direction: str,
        ml_confidence: float,
        regime: str,
        market_data: Dict,
        indicators: Dict
    ) -> Dict:
        """
        Analyze entry opportunity with LLM reasoning

        Returns enhanced decision with:
        - LLM validation (agree/disagree with ML)
        - Detailed reasoning
        - Risk factors identified
        - Confidence adjustment
        - Alternative scenarios
        """

        # Build market context prompt
        prompt = self._build_entry_analysis_prompt(
            symbol=symbol,
            ml_direction=ml_direction,
            ml_confidence=ml_confidence,
            regime=regime,
            market_data=market_data,
            indicators=indicators
        )

        try:
            # Call Groq with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert US30 SCALPER specializing in quick 30-100 point moves.
You PREFER ACTION over caution - scalping requires taking high-probability setups quickly.
You AGREE with the ML model when it shows 75%+ confidence UNLESS there's a clear structural problem.
You understand: RSI 40-60 is NEUTRAL (tradeable), not a reason to avoid.
MACD crossovers are ENTRY SIGNALS, not warnings.
Your job: VALIDATE the ML model's edge, not second-guess every trade.
Be decisive. Scalpers who hesitate miss profits."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Low temperature for consistent analysis
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            # Parse LLM response
            analysis = json.loads(response.choices[0].message.content)

            logger.info(
                f"Groq Analysis: {analysis.get('llm_decision', 'UNKNOWN')} | "
                f"Confidence: {analysis.get('llm_confidence', 0)}% | "
                f"Reasoning: {analysis.get('reasoning', '')[:100]}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Groq analysis error: {e}")
            # Fallback: Trust ML model
            return {
                "llm_decision": ml_direction,
                "llm_confidence": ml_confidence,
                "agree_with_ml": True,
                "reasoning": "LLM unavailable - using ML prediction",
                "risk_factors": [],
                "final_recommendation": ml_direction
            }

    def analyze_exit_opportunity(
        self,
        position: Dict,
        current_market: Dict,
        ml_exit_action: str,
        ml_exit_confidence: float
    ) -> Dict:
        """
        Analyze exit opportunity with LLM reasoning

        Considers:
        - Current P&L and time held
        - Market structure changes
        - Support/resistance levels
        - Momentum shifts
        - Risk/reward for holding vs exiting
        """

        prompt = self._build_exit_analysis_prompt(
            position=position,
            current_market=current_market,
            ml_exit_action=ml_exit_action,
            ml_exit_confidence=ml_exit_confidence
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert exit strategist for US30 trading.
You know when to take profits, when to let winners run, and when to cut losses quickly.
You consider market structure, momentum, and risk/reward.
You provide clear exit recommendations with specific reasoning."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=400,
                response_format={"type": "json_object"}
            )

            analysis = json.loads(response.choices[0].message.content)

            logger.info(
                f"Groq Exit: {analysis.get('llm_action', 'UNKNOWN')} | "
                f"Reasoning: {analysis.get('reasoning', '')[:100]}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Groq exit analysis error: {e}")
            return {
                "llm_action": ml_exit_action,
                "llm_confidence": ml_exit_confidence,
                "agree_with_ml": True,
                "reasoning": "LLM unavailable - using ML prediction",
                "final_recommendation": ml_exit_action
            }

    def _build_entry_analysis_prompt(
        self,
        symbol: str,
        ml_direction: str,
        ml_confidence: float,
        regime: str,
        market_data: Dict,
        indicators: Dict
    ) -> str:
        """Build detailed prompt for entry analysis"""

        # Extract key data points
        h1_data = market_data.get('H1', {})
        h4_data = market_data.get('H4', {})

        h1_close_series = h1_data.get('close')
        h1_close = h1_close_series.iloc[-1] if h1_close_series is not None and len(h1_close_series) > 0 else 0
        h1_rsi = indicators.get('H1', {}).get('rsi', 50)
        h1_macd = indicators.get('H1', {}).get('macd', 0)
        h1_atr = indicators.get('H1', {}).get('atr', 0)

        h4_rsi = indicators.get('H4', {}).get('rsi', 50)
        h4_macd = indicators.get('H4', {}).get('macd', 0)

        prompt = f"""Analyze this US30 trading opportunity:

**ML MODEL PREDICTION:**
- Direction: {ml_direction}
- Confidence: {ml_confidence:.1f}%

**MARKET REGIME:** {regime}

**CURRENT MARKET DATA:**
- US30 Price: {h1_close:.0f}
- H1 RSI: {h1_rsi:.1f}
- H1 MACD: {h1_macd:.4f}
- H1 ATR: {h1_atr:.0f}
- H4 RSI: {h4_rsi:.1f}
- H4 MACD: {h4_macd:.4f}

**YOUR TASK:**
Analyze this setup and provide a JSON response with:

{{
  "llm_decision": "BUY" or "SELL" or "HOLD",
  "llm_confidence": 0-100,
  "agree_with_ml": true/false,
  "reasoning": "Your 2-3 sentence analysis of why you agree/disagree",
  "risk_factors": ["factor1", "factor2"],
  "opportunity_score": 0-100,
  "final_recommendation": "BUY" or "SELL" or "HOLD"
}}

Consider:
1. Does the ML prediction align with market structure?
2. Are RSI levels sustainable or extreme?
3. Is MACD confirming or diverging?
4. What could go wrong with this trade?
5. Is the regime favorable for this direction?

Be honest. If ML is wrong, say so. If it's right but risky, explain why."""

        return prompt

    def _build_exit_analysis_prompt(
        self,
        position: Dict,
        current_market: Dict,
        ml_exit_action: str,
        ml_exit_confidence: float
    ) -> str:
        """Build prompt for exit analysis"""

        profit_points = position.get('profit_points', 0)
        profit_pct = position.get('profit_pct', 0)
        time_held = position.get('time_held_minutes', 0)
        direction = position.get('direction', 'LONG')

        h1_rsi = current_market.get('h1_rsi', 50)
        h1_macd = current_market.get('h1_macd', 0)

        prompt = f"""Analyze this US30 exit decision:

**CURRENT POSITION:**
- Direction: {direction}
- P&L: {profit_points:.0f} points ({profit_pct:.2f}%)
- Time Held: {time_held} minutes

**ML EXIT PREDICTION:**
- Action: {ml_exit_action}
- Confidence: {ml_exit_confidence:.1f}%

**CURRENT MARKET:**
- H1 RSI: {h1_rsi:.1f}
- H1 MACD: {h1_macd:.4f}

**YOUR TASK:**
Provide JSON response:

{{
  "llm_action": "HOLD" or "TAKE_PROFIT" or "STOP_LOSS",
  "llm_confidence": 0-100,
  "agree_with_ml": true/false,
  "reasoning": "Your 2-3 sentence exit analysis",
  "final_recommendation": "HOLD" or "TAKE_PROFIT" or "STOP_LOSS"
}}

Consider:
1. Is the profit/loss at a decision point?
2. Are indicators showing continuation or reversal?
3. Should we let this run or take profit now?
4. What's the risk of holding vs exiting?

Be decisive. Protect profits, cut losses quickly."""

        return prompt

    def analyze_market(self, prompt: str) -> str:
        """
        v3.15: Simple market analysis with custom prompt
        Used for LLM market overview every 60 seconds

        Returns: LLM response as string
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an aggressive US30 scalping analyst. Be decisive and opportunity-focused."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq analyze_market error: {e}")
            return "neutral|1.0|Market analysis unavailable"

    def get_market_summary(
        self,
        recent_trades: List[Dict],
        current_regime: str,
        performance_stats: Dict
    ) -> str:
        """
        Get LLM-generated market summary and trading advice

        Returns natural language summary of:
        - Recent performance
        - Current market conditions
        - Trading recommendations
        - Risk warnings
        """

        prompt = f"""Provide a brief market summary:

**RECENT TRADES:** {len(recent_trades)} trades
**WIN RATE:** {performance_stats.get('win_rate', 0):.1f}%
**PROFIT FACTOR:** {performance_stats.get('profit_factor', 0):.2f}
**CURRENT REGIME:** {current_regime}

Summarize in 3-4 sentences:
1. How is the AI performing?
2. What's the current market condition?
3. Any warnings or advice?

Be direct and actionable."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a trading performance analyst. Be concise and honest."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=200
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Groq summary error: {e}")
            return f"AI performing at {performance_stats.get('win_rate', 0):.1f}% win rate in {current_regime} regime."
