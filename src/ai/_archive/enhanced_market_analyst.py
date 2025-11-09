"""
Enhanced Groq Market Analyst
Reads FULL market conditions from chart data and makes intelligent decisions

Unlike basic indicator analysis, this LLM sees:
- Full candlestick patterns (last 50-100 bars)
- Support/Resistance levels
- Price action and market structure
- Order flow and volume patterns
- Multi-timeframe context
- Recent highs/lows and pivot points

Works WITH ML models, not just validates them
"""
import os
from groq import Groq
from typing import Dict, List, Optional
import json
from datetime import datetime
import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


class EnhancedMarketAnalyst:
    """
    Advanced market analyst that reads charts like a human trader

    Key difference from basic LLM:
    - Sees full price action (not just current RSI/MACD)
    - Identifies support/resistance from chart structure
    - Analyzes candlestick patterns
    - Reads market context (where we are in the bigger picture)
    - Makes independent decisions based on chart reading
    """

    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

        logger.info("EnhancedMarketAnalyst initialized - Full chart analysis enabled")

    def analyze_market_structure(
        self,
        symbol: str,
        market_data: Dict,
        indicators: Dict,
        ml_prediction: Optional[Dict] = None
    ) -> Dict:
        """
        FULL market analysis from chart data

        This is the main intelligence - LLM reads the chart and decides

        Args:
            symbol: Trading symbol
            market_data: Full OHLCV data from multiple timeframes
            indicators: Technical indicators
            ml_prediction: Optional ML model prediction to consider

        Returns:
            Complete market analysis with trade decision
        """

        # Extract chart structure
        chart_analysis = self._analyze_chart_structure(market_data, indicators)

        # Build comprehensive prompt with FULL market picture
        prompt = self._build_comprehensive_prompt(
            symbol=symbol,
            chart_analysis=chart_analysis,
            market_data=market_data,
            indicators=indicators,
            ml_prediction=ml_prediction
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert US30 (Dow Jones) trader with 20 years of experience.

Your specialty is READING CHARTS and identifying high-probability setups.

You analyze:
1. Market structure (higher highs/lows, support/resistance breaks)
2. Price action (candlestick patterns, rejection wicks, engulfing bars)
3. Multi-timeframe alignment (H4 trend + H1 entry)
4. Volume/momentum confirmation
5. Key levels (recent highs/lows, round numbers, pivots)

You make INDEPENDENT decisions based on chart reading.
You can agree or disagree with ML models.
You explain your reasoning like a professional trader.

Be direct, concise, and actionable."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"}
            )

            analysis = json.loads(response.choices[0].message.content)

            logger.info(
                f"Enhanced Analysis: {analysis.get('decision', 'UNKNOWN')} | "
                f"Confidence: {analysis.get('confidence', 0)}% | "
                f"Chart: {analysis.get('chart_signal', 'N/A')}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Enhanced market analysis error: {e}")
            return {
                "decision": "HOLD",
                "confidence": 0,
                "chart_signal": "ERROR",
                "reasoning": f"Analysis error: {str(e)}",
                "support_level": 0,
                "resistance_level": 0,
                "risk_factors": ["Analysis unavailable"]
            }

    def _analyze_chart_structure(self, market_data: Dict, indicators: Dict) -> Dict:
        """
        Extract chart structure features for LLM to analyze

        Returns key levels, patterns, and structure info
        """
        analysis = {}

        # Get H1 and H4 data
        h1_data = market_data.get('H1', {})
        h4_data = market_data.get('H4', {})

        if 'close' in h1_data:
            h1_close = np.array(h1_data['close'])
            h1_high = np.array(h1_data.get('high', h1_close))
            h1_low = np.array(h1_data.get('low', h1_close))
            h1_open = np.array(h1_data.get('open', h1_close))

            # Current price
            analysis['current_price'] = float(h1_close[-1])

            # Recent highs/lows (support/resistance candidates)
            lookback = min(50, len(h1_high))
            analysis['recent_high'] = float(np.max(h1_high[-lookback:]))
            analysis['recent_low'] = float(np.min(h1_low[-lookback:]))

            # Swing highs/lows (last 20 bars)
            swing_lookback = min(20, len(h1_high))
            analysis['swing_high'] = float(np.max(h1_high[-swing_lookback:]))
            analysis['swing_low'] = float(np.min(h1_low[-swing_lookback:]))

            # Price position in recent range
            recent_range = analysis['recent_high'] - analysis['recent_low']
            price_position = (analysis['current_price'] - analysis['recent_low']) / recent_range if recent_range > 0 else 0.5
            analysis['price_position_pct'] = float(price_position * 100)

            # Last 10 candlesticks (price action)
            last_n = min(10, len(h1_close))
            analysis['last_10_candles'] = []
            for i in range(-last_n, 0):
                candle = {
                    'open': float(h1_open[i]),
                    'high': float(h1_high[i]),
                    'low': float(h1_low[i]),
                    'close': float(h1_close[i]),
                    'direction': 'BULLISH' if h1_close[i] > h1_open[i] else 'BEARISH',
                    'body_size': abs(float(h1_close[i] - h1_open[i])),
                    'upper_wick': float(h1_high[i] - max(h1_open[i], h1_close[i])),
                    'lower_wick': float(min(h1_open[i], h1_close[i]) - h1_low[i])
                }
                analysis['last_10_candles'].append(candle)

            # Trend direction (last 20 bars)
            if len(h1_close) >= 20:
                slope = (h1_close[-1] - h1_close[-20]) / 20
                if slope > 0:
                    analysis['h1_trend'] = 'UPTREND'
                elif slope < 0:
                    analysis['h1_trend'] = 'DOWNTREND'
                else:
                    analysis['h1_trend'] = 'SIDEWAYS'

            # Higher highs / Lower lows detection
            if len(h1_high) >= 15:
                hh = h1_high[-5] > h1_high[-10] and h1_high[-1] > h1_high[-5]
                ll = h1_low[-5] < h1_low[-10] and h1_low[-1] < h1_low[-5]

                if hh and not ll:
                    analysis['market_structure'] = 'HIGHER_HIGHS'
                elif ll and not hh:
                    analysis['market_structure'] = 'LOWER_LOWS'
                else:
                    analysis['market_structure'] = 'CHOPPY'

        # H4 context (bigger picture)
        if 'close' in h4_data:
            h4_close = np.array(h4_data['close'])
            h4_high = np.array(h4_data.get('high', h4_close))
            h4_low = np.array(h4_data.get('low', h4_close))

            # H4 trend
            if len(h4_close) >= 20:
                h4_slope = (h4_close[-1] - h4_close[-20]) / 20
                if h4_slope > 0:
                    analysis['h4_trend'] = 'UPTREND'
                elif h4_slope < 0:
                    analysis['h4_trend'] = 'DOWNTREND'
                else:
                    analysis['h4_trend'] = 'SIDEWAYS'

            # H4 key levels
            h4_lookback = min(30, len(h4_high))
            analysis['h4_high'] = float(np.max(h4_high[-h4_lookback:]))
            analysis['h4_low'] = float(np.min(h4_low[-h4_lookback:]))

        return analysis

    def _build_comprehensive_prompt(
        self,
        symbol: str,
        chart_analysis: Dict,
        market_data: Dict,
        indicators: Dict,
        ml_prediction: Optional[Dict]
    ) -> str:
        """
        Build FULL market analysis prompt with chart data

        This gives LLM complete picture to make intelligent decisions
        """

        # Extract indicators
        h1_ind = indicators.get('H1', {})
        h4_ind = indicators.get('H4', {})

        current_price = chart_analysis.get('current_price', 0)
        recent_high = chart_analysis.get('recent_high', 0)
        recent_low = chart_analysis.get('recent_low', 0)
        swing_high = chart_analysis.get('swing_high', 0)
        swing_low = chart_analysis.get('swing_low', 0)
        price_position = chart_analysis.get('price_position_pct', 50)

        h1_trend = chart_analysis.get('h1_trend', 'UNKNOWN')
        h4_trend = chart_analysis.get('h4_trend', 'UNKNOWN')
        market_structure = chart_analysis.get('market_structure', 'UNKNOWN')

        # Last 5 candlesticks for pattern recognition
        last_candles = chart_analysis.get('last_10_candles', [])[-5:]
        candles_text = ""
        for i, c in enumerate(last_candles, 1):
            candles_text += f"""
Candle {i}: {c['direction']} | Open: {c['open']:.0f} → Close: {c['close']:.0f}
  Body: {c['body_size']:.0f} pts | Upper Wick: {c['upper_wick']:.0f} | Lower Wick: {c['lower_wick']:.0f}"""

        # ML prediction context (if available)
        ml_context = ""
        if ml_prediction:
            ml_context = f"""
**ML MODEL INPUT:**
- Direction: {ml_prediction.get('direction', 'N/A')}
- Confidence: {ml_prediction.get('confidence', 0):.1f}%
- Regime: {ml_prediction.get('regime', 'N/A')}

(You can agree or disagree - make YOUR OWN decision based on the chart)
"""

        prompt = f"""You are analyzing the {symbol} chart. Read the market structure and decide.

══════════════════════════════════════════════════════════════
CHART STRUCTURE
══════════════════════════════════════════════════════════════

**CURRENT MARKET:**
- Price: {current_price:.0f}
- Position in Range: {price_position:.0f}% (0% = at lows, 100% = at highs)

**KEY LEVELS:**
- Recent High (50 bars): {recent_high:.0f}
- Recent Low (50 bars): {recent_low:.0f}
- Swing High (20 bars): {swing_high:.0f}
- Swing Low (20 bars): {swing_low:.0f}

**TREND ANALYSIS:**
- H1 Trend: {h1_trend}
- H4 Trend: {h4_trend}
- Market Structure: {market_structure}

**LAST 5 CANDLESTICKS:**{candles_text}

**TECHNICAL INDICATORS:**
- H1 RSI: {h1_ind.get('rsi', 50):.1f}
- H1 MACD: {h1_ind.get('macd', 0):.4f}
- H1 ATR: {h1_ind.get('atr', 0):.0f} points
- H4 RSI: {h4_ind.get('rsi', 50):.1f}
- H4 MACD: {h4_ind.get('macd', 0):.4f}

{ml_context}

══════════════════════════════════════════════════════════════
YOUR ANALYSIS
══════════════════════════════════════════════════════════════

Read the chart and provide JSON response:

{{
  "decision": "BUY" or "SELL" or "HOLD",
  "confidence": 0-100,
  "chart_signal": "BULLISH_BREAKOUT" / "BEARISH_REVERSAL" / "RANGE_BOUND" / etc,
  "reasoning": "Your professional chart reading (2-4 sentences)",
  "support_level": nearest_support_price,
  "resistance_level": nearest_resistance_price,
  "entry_trigger": "What needs to happen for entry",
  "invalidation": "What would invalidate this setup",
  "risk_factors": ["factor1", "factor2"],
  "time_horizon": "SCALP" or "INTRADAY" or "SWING"
}}

ANALYZE:
1. Market Structure: Are we making HH/HL (uptrend) or LH/LL (downtrend)?
2. Price Action: What do recent candlesticks tell you?
3. Key Levels: Are we at support/resistance?
4. Multi-Timeframe: H4 trend + H1 entry alignment?
5. Risk/Reward: Where's nearest support/resistance for stops/targets?

BE HONEST: If chart is unclear or choppy → HOLD
If setup is clean → BUY/SELL with conviction

Make YOUR decision as a professional trader would."""

        return prompt

    def analyze_position_management(
        self,
        position: Dict,
        market_data: Dict,
        indicators: Dict
    ) -> Dict:
        """
        Analyze if position should be held or exited based on chart structure

        This is different from entry - we're monitoring an OPEN position
        """

        chart_analysis = self._analyze_chart_structure(market_data, indicators)

        entry_price = position.get('entry_price', 0)
        current_price = chart_analysis.get('current_price', 0)
        direction = position.get('direction', 'LONG')
        time_held = position.get('time_held_minutes', 0)
        profit_points = position.get('profit_points', 0)

        # Build position management prompt
        prompt = f"""You have an OPEN {direction} position on US30.

**POSITION DETAILS:**
- Entry: {entry_price:.0f}
- Current: {current_price:.0f}
- P&L: {profit_points:+.0f} points
- Time Held: {time_held} minutes

**CURRENT CHART STRUCTURE:**
- Recent High: {chart_analysis.get('recent_high', 0):.0f}
- Recent Low: {chart_analysis.get('recent_low', 0):.0f}
- Swing High: {chart_analysis.get('swing_high', 0):.0f}
- Swing Low: {chart_analysis.get('swing_low', 0):.0f}
- H1 Trend: {chart_analysis.get('h1_trend', 'UNKNOWN')}
- H4 Trend: {chart_analysis.get('h4_trend', 'UNKNOWN')}
- Market Structure: {chart_analysis.get('market_structure', 'UNKNOWN')}

**INDICATORS:**
- RSI: {indicators.get('H1', {}).get('rsi', 50):.1f}
- MACD: {indicators.get('H1', {}).get('macd', 0):.4f}

**YOUR TASK:**
Decide if you should HOLD, TAKE_PROFIT, or STOP_LOSS.

Provide JSON response:
{{
  "action": "HOLD" or "TAKE_PROFIT" or "STOP_LOSS",
  "confidence": 0-100,
  "reasoning": "Your chart-based analysis (2-3 sentences)",
  "chart_says": "What is price action telling you?",
  "next_target": price_level_if_holding,
  "exit_trigger": "What would make you exit?"
}}

CONSIDER:
1. Is market structure still intact or breaking?
2. Are we approaching key resistance/support?
3. Is momentum fading or accelerating?
4. Should we protect profit or let it run?
5. Is this a normal pullback or reversal?

Make the professional trader decision."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are managing an open position. Read the chart and decide: hold, take profit, or stop loss. Be decisive."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )

            analysis = json.loads(response.choices[0].message.content)
            return analysis

        except Exception as e:
            logger.error(f"Position management analysis error: {e}")
            return {
                "action": "HOLD",
                "confidence": 50,
                "reasoning": f"Error: {str(e)}",
                "chart_says": "Analysis unavailable"
            }
