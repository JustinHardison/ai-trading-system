"""
Groq-powered market analysis agent
Fast, efficient market analysis using Groq's inference API
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from groq import Groq

from ..config import get_settings
from ..utils.logger import get_logger


logger = get_logger(__name__)


class GroqMarketAnalyzer:
    """
    Fast market analysis using Groq API
    Uses llama3 or mixtral models for rapid decision making
    """

    def __init__(self):
        self.settings = get_settings()
        if not self.settings.groq_api_key:
            raise ValueError("GROQ_API_KEY not set in environment")

        self.client = Groq(api_key=self.settings.groq_api_key)
        self.model = "llama-3.3-70b-versatile"  # Fast and capable model (updated)

        logger.info(f"Initialized Groq Market Analyzer with model: {self.model}")

    def analyze_market(
        self,
        symbol: str,
        current_price: float,
        technical_indicators: Dict[str, Any],
        timeframe: str = "1H",
    ) -> Dict[str, Any]:
        """
        Analyze market conditions and generate trading decision

        Args:
            symbol: Trading symbol (e.g., "SPY", "AAPL")
            current_price: Current price of the asset
            technical_indicators: Dictionary of technical indicators
            timeframe: Trading timeframe

        Returns:
            Dictionary with trading decision and analysis
        """
        logger.info(f"Analyzing {symbol} at ${current_price} on {timeframe}")

        # Build the analysis prompt
        prompt = self._build_analysis_prompt(symbol, current_price, technical_indicators, timeframe)

        # Get analysis from Groq
        try:
            analysis = self._call_groq(prompt)
            analysis["timestamp"] = datetime.now().isoformat()
            analysis["symbol"] = symbol
            analysis["current_price"] = current_price

            logger.info(f"Analysis complete: {analysis.get('action', 'HOLD')} - "
                       f"Confidence: {analysis.get('confidence', 0):.1f}%")

            return analysis

        except Exception as e:
            logger.error(f"Error in market analysis: {e}")
            return self._fallback_analysis(symbol, current_price, technical_indicators)

    def _build_analysis_prompt(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, Any],
        timeframe: str,
    ) -> str:
        """Build detailed analysis prompt for LLM"""

        prompt = f"""You are an expert algorithmic trader analyzing {symbol} on {timeframe} timeframe.

CURRENT MARKET DATA:
Symbol: {symbol}
Current Price: ${current_price:.2f}
Timeframe: {timeframe}

TECHNICAL INDICATORS:
"""

        # Add price action
        if "price_action" in indicators:
            pa = indicators["price_action"]
            prompt += f"""
PRICE ACTION:
- Open: ${pa.get('open', 0):.2f}
- High: ${pa.get('high', 0):.2f}
- Low: ${pa.get('low', 0):.2f}
- Close: ${pa.get('close', 0):.2f}
- Change: {pa.get('change_pct', 0):.2f}%
"""

        # Add trend indicators
        if "trend" in indicators:
            trend = indicators["trend"]
            prompt += f"""
TREND INDICATORS:
- SMA 20: ${trend.get('sma_20', 0):.2f}
- SMA 50: ${trend.get('sma_50', 0):.2f}
- EMA 12: ${trend.get('ema_12', 0):.2f}
- EMA 26: ${trend.get('ema_26', 0):.2f}
- Price vs SMA20: {((current_price / trend.get('sma_20', current_price) - 1) * 100):.2f}%
- Price vs SMA50: {((current_price / trend.get('sma_50', current_price) - 1) * 100):.2f}%
"""

        # Add momentum indicators
        if "momentum" in indicators:
            mom = indicators["momentum"]
            prompt += f"""
MOMENTUM INDICATORS:
- RSI: {mom.get('rsi', 50):.1f}
- MACD: {mom.get('macd', 0):.4f}
- MACD Signal: {mom.get('macd_signal', 0):.4f}
- MACD Histogram: {mom.get('macd_hist', 0):.4f}
"""

        # Add volatility indicators
        if "volatility" in indicators:
            vol = indicators["volatility"]
            prompt += f"""
VOLATILITY INDICATORS:
- ATR: ${vol.get('atr', 0):.2f}
- Bollinger Upper: ${vol.get('bb_upper', 0):.2f}
- Bollinger Middle: ${vol.get('bb_middle', 0):.2f}
- Bollinger Lower: ${vol.get('bb_lower', 0):.2f}
- BB Width: {vol.get('bb_width', 0):.2f}%
"""

        # Add volume if available
        if "volume" in indicators:
            vol_data = indicators["volume"]
            prompt += f"""
VOLUME ANALYSIS:
- Current Volume: {vol_data.get('current', 0):,.0f}
- Average Volume: {vol_data.get('average', 0):,.0f}
- Volume Ratio: {vol_data.get('ratio', 1):.2f}x
"""

        prompt += """

ANALYZE THIS DATA AND PROVIDE A TRADING DECISION.

Respond in JSON format with the following structure:
{
    "action": "BUY" or "SELL" or "HOLD",
    "confidence": 0-100,
    "reasoning": "brief explanation of the decision",
    "entry_price": suggested entry price,
    "stop_loss": suggested stop loss price,
    "take_profit": suggested take profit price,
    "position_size_pct": suggested position size as % of capital (0-100),
    "risk_reward_ratio": expected risk/reward ratio,
    "timeframe_hold": "estimated holding period (e.g., '2-4 hours', '1-2 days')",
    "key_factors": ["list of key factors influencing decision"]
}

IMPORTANT RULES:
1. Only suggest BUY or SELL if confidence > 65%
2. Always include stop loss for risk management
3. Risk/reward ratio should be at least 2:1
4. Position size should never exceed 25% of capital
5. Consider both technical indicators and price action
6. Be conservative - it's better to HOLD than force a bad trade

Respond ONLY with valid JSON, no other text.
"""

        return prompt

    def _call_groq(self, prompt: str) -> Dict[str, Any]:
        """Call Groq API and parse response"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert algorithmic trader. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            content = response.choices[0].message.content.strip()

            # Try to extract JSON from the response
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            # Parse JSON
            analysis = json.loads(content)

            # Validate required fields
            required_fields = ["action", "confidence", "reasoning"]
            for field in required_fields:
                if field not in analysis:
                    raise ValueError(f"Missing required field: {field}")

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Groq response: {e}")
            logger.error(f"Response content: {content}")
            raise
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            raise

    def _fallback_analysis(
        self,
        symbol: str,
        current_price: float,
        indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Simple rule-based fallback when LLM fails"""

        action = "HOLD"
        confidence = 30
        reasoning = "LLM analysis failed, using simple rules"

        # Simple RSI-based logic
        if "momentum" in indicators:
            rsi = indicators["momentum"].get("rsi", 50)
            if rsi < 30:
                action = "BUY"
                confidence = 50
                reasoning = f"RSI oversold at {rsi:.1f}"
            elif rsi > 70:
                action = "SELL"
                confidence = 50
                reasoning = f"RSI overbought at {rsi:.1f}"

        # Simple trend-following
        if "trend" in indicators:
            sma_20 = indicators["trend"].get("sma_20", current_price)
            sma_50 = indicators["trend"].get("sma_50", current_price)

            if current_price > sma_20 > sma_50 and action == "HOLD":
                action = "BUY"
                confidence = 45
                reasoning = "Price above rising moving averages"
            elif current_price < sma_20 < sma_50 and action == "HOLD":
                action = "SELL"
                confidence = 45
                reasoning = "Price below falling moving averages"

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "entry_price": current_price,
            "stop_loss": current_price * (0.98 if action == "BUY" else 1.02),
            "take_profit": current_price * (1.04 if action == "BUY" else 0.96),
            "position_size_pct": 10,
            "risk_reward_ratio": 2.0,
            "timeframe_hold": "4-8 hours",
            "key_factors": ["Fallback analysis due to LLM error"],
            "fallback_mode": True,
        }

    def should_close_position(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        position_type: str,
        hold_time_hours: float,
        technical_indicators: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Decide whether to close an existing position

        Args:
            symbol: Trading symbol
            entry_price: Entry price of position
            current_price: Current market price
            position_type: "LONG" or "SHORT"
            hold_time_hours: How long position has been held
            technical_indicators: Current technical indicators

        Returns:
            Dictionary with close decision
        """

        pnl_pct = ((current_price / entry_price) - 1) * 100
        if position_type == "SHORT":
            pnl_pct = -pnl_pct

        prompt = f"""You are managing an open {position_type} position on {symbol}.

POSITION DETAILS:
- Entry Price: ${entry_price:.2f}
- Current Price: ${current_price:.2f}
- P&L: {pnl_pct:+.2f}%
- Hold Time: {hold_time_hours:.1f} hours

CURRENT TECHNICAL INDICATORS:
"""

        # Add current indicators (simplified)
        if "momentum" in technical_indicators:
            rsi = technical_indicators["momentum"].get("rsi", 50)
            prompt += f"- RSI: {rsi:.1f}\n"

        if "trend" in technical_indicators:
            trend = technical_indicators["trend"]
            prompt += f"- Price vs SMA20: {((current_price / trend.get('sma_20', current_price) - 1) * 100):+.2f}%\n"

        prompt += """
Should we CLOSE this position or HOLD it?

Respond in JSON format:
{
    "action": "CLOSE" or "HOLD",
    "confidence": 0-100,
    "reasoning": "explanation"
}

CLOSE if:
- Profit target reached (>3%)
- Stop loss hit (<-2%)
- Momentum reversing
- Better opportunities elsewhere

Respond ONLY with valid JSON.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert trader managing positions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()

            decision = json.loads(content)
            decision["pnl_pct"] = pnl_pct

            return decision

        except Exception as e:
            logger.error(f"Error in close position decision: {e}")

            # Fallback: use simple profit/loss rules
            if pnl_pct >= 3:
                return {"action": "CLOSE", "confidence": 80, "reasoning": "Profit target reached", "pnl_pct": pnl_pct}
            elif pnl_pct <= -2:
                return {"action": "CLOSE", "confidence": 90, "reasoning": "Stop loss triggered", "pnl_pct": pnl_pct}
            else:
                return {"action": "HOLD", "confidence": 50, "reasoning": "No clear exit signal", "pnl_pct": pnl_pct}
