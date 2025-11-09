"""
LLM-powered market analysis agent
Uses multiple LLMs to analyze market conditions, sentiment, and generate trading insights
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import httpx

from ..config import get_settings
from ..utils.logger import get_logger


logger = get_logger(__name__)
settings = get_settings()


class MarketRegime(str, Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"


class MarketSentiment(str, Enum):
    """Market sentiment classification"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    EXTREME_FEAR = "extreme_fear"
    EXTREME_GREED = "extreme_greed"


class LLMMarketAnalyzer:
    """
    Advanced market analysis using LLMs
    Combines technical analysis, sentiment, and news to generate trading insights
    """

    def __init__(self):
        self.settings = get_settings()
        self._init_llm_clients()

    def _init_llm_clients(self):
        """Initialize LLM API clients"""
        if self.settings.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        else:
            self.anthropic_client = None

        if self.settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        else:
            self.openai_client = None

    async def analyze_market(
        self,
        symbol: str,
        timeframe: str,
        technical_data: Dict[str, Any],
        news_data: Optional[List[Dict]] = None,
        sentiment_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Comprehensive market analysis using LLM

        Args:
            symbol: Trading symbol (e.g., "EURUSD", "AAPL")
            timeframe: Trading timeframe (e.g., "1H", "4H", "1D")
            technical_data: Dictionary containing technical indicators
            news_data: List of recent news articles
            sentiment_data: Sentiment scores from various sources

        Returns:
            Dictionary containing analysis results
        """
        logger.info(f"Starting market analysis for {symbol} on {timeframe}")

        # Build context for LLM
        context = self._build_analysis_context(
            symbol, timeframe, technical_data, news_data, sentiment_data
        )

        # Get analysis from primary LLM
        if self.settings.llm_provider == "anthropic" and self.anthropic_client:
            analysis = await self._analyze_with_claude(context)
        elif self.settings.llm_provider == "openai" and self.openai_client:
            analysis = await self._analyze_with_gpt(context)
        else:
            logger.warning(f"LLM provider {self.settings.llm_provider} not available, using fallback")
            analysis = self._fallback_analysis(technical_data)

        # Enrich analysis with additional insights
        analysis["timestamp"] = datetime.now().isoformat()
        analysis["symbol"] = symbol
        analysis["timeframe"] = timeframe
        analysis["confidence"] = self._calculate_confidence(analysis)

        logger.info(f"Market analysis completed: {analysis.get('market_regime')} regime, "
                   f"{analysis.get('sentiment')} sentiment, confidence: {analysis.get('confidence'):.2f}")

        return analysis

    def _build_analysis_context(
        self,
        symbol: str,
        timeframe: str,
        technical_data: Dict,
        news_data: Optional[List[Dict]],
        sentiment_data: Optional[Dict],
    ) -> str:
        """Build comprehensive context for LLM analysis"""

        context = f"""Analyze the following market data for {symbol} on {timeframe} timeframe:

TECHNICAL INDICATORS:
"""

        # Add price action
        if "price" in technical_data:
            price = technical_data["price"]
            context += f"""
Current Price: {price.get('close', 'N/A')}
Open: {price.get('open', 'N/A')}
High: {price.get('high', 'N/A')}
Low: {price.get('low', 'N/A')}
Change: {price.get('change_pct', 'N/A')}%
"""

        # Add trend indicators
        if "trend" in technical_data:
            trend = technical_data["trend"]
            context += f"""
TREND INDICATORS:
SMA 20: {trend.get('sma_20', 'N/A')}
SMA 50: {trend.get('sma_50', 'N/A')}
SMA 200: {trend.get('sma_200', 'N/A')}
EMA 12: {trend.get('ema_12', 'N/A')}
EMA 26: {trend.get('ema_26', 'N/A')}
MACD: {trend.get('macd', 'N/A')}
MACD Signal: {trend.get('macd_signal', 'N/A')}
MACD Histogram: {trend.get('macd_hist', 'N/A')}
ADX: {trend.get('adx', 'N/A')}
"""

        # Add momentum indicators
        if "momentum" in technical_data:
            momentum = technical_data["momentum"]
            context += f"""
MOMENTUM INDICATORS:
RSI: {momentum.get('rsi', 'N/A')}
Stochastic K: {momentum.get('stoch_k', 'N/A')}
Stochastic D: {momentum.get('stoch_d', 'N/A')}
Williams %R: {momentum.get('williams_r', 'N/A')}
CCI: {momentum.get('cci', 'N/A')}
"""

        # Add volatility indicators
        if "volatility" in technical_data:
            volatility = technical_data["volatility"]
            context += f"""
VOLATILITY INDICATORS:
ATR: {volatility.get('atr', 'N/A')}
Bollinger Bands Upper: {volatility.get('bb_upper', 'N/A')}
Bollinger Bands Middle: {volatility.get('bb_middle', 'N/A')}
Bollinger Bands Lower: {volatility.get('bb_lower', 'N/A')}
BB Width: {volatility.get('bb_width', 'N/A')}
"""

        # Add volume analysis
        if "volume" in technical_data:
            volume = technical_data["volume"]
            context += f"""
VOLUME ANALYSIS:
Current Volume: {volume.get('current', 'N/A')}
Average Volume: {volume.get('average', 'N/A')}
Volume Ratio: {volume.get('ratio', 'N/A')}
OBV: {volume.get('obv', 'N/A')}
"""

        # Add support/resistance levels
        if "levels" in technical_data:
            levels = technical_data["levels"]
            context += f"""
KEY LEVELS:
Support Levels: {levels.get('support', [])}
Resistance Levels: {levels.get('resistance', [])}
"""

        # Add news sentiment if available
        if news_data:
            context += "\nRECENT NEWS:\n"
            for i, news in enumerate(news_data[:5], 1):
                context += f"{i}. {news.get('headline', 'N/A')} - {news.get('sentiment', 'neutral')} "
                context += f"(published: {news.get('published_date', 'N/A')})\n"

        # Add sentiment data if available
        if sentiment_data:
            context += f"""
MARKET SENTIMENT:
Overall Sentiment: {sentiment_data.get('overall', 'neutral')}
Social Media Sentiment: {sentiment_data.get('social', 'N/A')}
Institutional Flow: {sentiment_data.get('institutional', 'N/A')}
Retail Flow: {sentiment_data.get('retail', 'N/A')}
Fear & Greed Index: {sentiment_data.get('fear_greed', 'N/A')}
"""

        context += """
Based on this comprehensive data, provide a detailed analysis including:
1. Market Regime (trending_up, trending_down, ranging, volatile, breakout, reversal)
2. Overall Sentiment (bullish, bearish, neutral, extreme_fear, extreme_greed)
3. Trade Direction (LONG, SHORT, STAY_OUT)
4. Confidence Level (0-100)
5. Entry Strategy
6. Stop Loss Level
7. Take Profit Targets
8. Risk/Reward Ratio
9. Key Risks and Considerations
10. Time Horizon for the Trade

Format your response as a structured JSON object.
"""

        return context

    async def _analyze_with_claude(self, context: str) -> Dict[str, Any]:
        """Perform analysis using Claude (Anthropic)"""
        try:
            response = await self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": context
                    }
                ]
            )

            content = response.content[0].text

            # Try to parse JSON response
            try:
                # Extract JSON from markdown code blocks if present
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    content = content[json_start:json_end].strip()

                analysis = json.loads(content)
            except json.JSONDecodeError:
                # If JSON parsing fails, extract key information using text parsing
                analysis = self._parse_text_analysis(content)

            return analysis

        except Exception as e:
            logger.error(f"Error in Claude analysis: {e}")
            return self._fallback_analysis({})

    async def _analyze_with_gpt(self, context: str) -> Dict[str, Any]:
        """Perform analysis using GPT-4 (OpenAI)"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert quantitative trader and market analyst. "
                                 "Provide detailed technical analysis in JSON format."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            analysis = json.loads(content)
            return analysis

        except Exception as e:
            logger.error(f"Error in GPT analysis: {e}")
            return self._fallback_analysis({})

    def _parse_text_analysis(self, text: str) -> Dict[str, Any]:
        """Parse text response when JSON parsing fails"""
        analysis = {
            "market_regime": "unknown",
            "sentiment": "neutral",
            "trade_direction": "STAY_OUT",
            "confidence": 50,
            "entry_strategy": "Wait for better setup",
            "analysis_text": text
        }

        # Simple keyword-based extraction
        text_lower = text.lower()

        # Detect market regime
        if "trending up" in text_lower or "uptrend" in text_lower:
            analysis["market_regime"] = "trending_up"
        elif "trending down" in text_lower or "downtrend" in text_lower:
            analysis["market_regime"] = "trending_down"
        elif "ranging" in text_lower or "sideways" in text_lower:
            analysis["market_regime"] = "ranging"
        elif "volatile" in text_lower:
            analysis["market_regime"] = "volatile"

        # Detect sentiment
        if "bullish" in text_lower:
            analysis["sentiment"] = "bullish"
        elif "bearish" in text_lower:
            analysis["sentiment"] = "bearish"

        # Detect trade direction
        if "long" in text_lower or "buy" in text_lower:
            analysis["trade_direction"] = "LONG"
        elif "short" in text_lower or "sell" in text_lower:
            analysis["trade_direction"] = "SHORT"

        return analysis

    def _fallback_analysis(self, technical_data: Dict) -> Dict[str, Any]:
        """Simple rule-based analysis as fallback when LLM is not available"""
        analysis = {
            "market_regime": "unknown",
            "sentiment": "neutral",
            "trade_direction": "STAY_OUT",
            "confidence": 30,
            "entry_strategy": "LLM not available, using basic rules",
            "warning": "Fallback analysis - limited accuracy"
        }

        # Basic trend detection from moving averages
        if "trend" in technical_data:
            trend = technical_data["trend"]
            sma_20 = trend.get("sma_20", 0)
            sma_50 = trend.get("sma_50", 0)

            if sma_20 > sma_50:
                analysis["market_regime"] = "trending_up"
                analysis["sentiment"] = "bullish"
            elif sma_20 < sma_50:
                analysis["market_regime"] = "trending_down"
                analysis["sentiment"] = "bearish"

        # Basic RSI analysis
        if "momentum" in technical_data:
            momentum = technical_data["momentum"]
            rsi = momentum.get("rsi", 50)

            if rsi > 70:
                analysis["trade_direction"] = "SHORT"
                analysis["entry_strategy"] = "RSI overbought"
            elif rsi < 30:
                analysis["trade_direction"] = "LONG"
                analysis["entry_strategy"] = "RSI oversold"

        return analysis

    def _calculate_confidence(self, analysis: Dict) -> float:
        """Calculate confidence score for the analysis"""
        confidence = analysis.get("confidence", 50)

        # Adjust based on market regime clarity
        if analysis.get("market_regime") in ["trending_up", "trending_down"]:
            confidence += 10
        elif analysis.get("market_regime") == "unknown":
            confidence -= 20

        # Adjust based on trade direction
        if analysis.get("trade_direction") == "STAY_OUT":
            confidence -= 10

        # Ensure confidence is between 0 and 100
        return max(0, min(100, confidence))

    async def get_sentiment_analysis(
        self,
        symbol: str,
        news_headlines: List[str],
        social_posts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze sentiment from news and social media

        Args:
            symbol: Trading symbol
            news_headlines: List of news headlines
            social_posts: Optional list of social media posts

        Returns:
            Sentiment analysis results
        """
        context = f"Analyze the sentiment for {symbol} based on the following:\n\n"
        context += "NEWS HEADLINES:\n"
        for i, headline in enumerate(news_headlines[:10], 1):
            context += f"{i}. {headline}\n"

        if social_posts:
            context += "\nSOCIAL MEDIA POSTS:\n"
            for i, post in enumerate(social_posts[:10], 1):
                context += f"{i}. {post}\n"

        context += "\nProvide a sentiment analysis with:"
        context += "\n1. Overall sentiment score (-100 to +100)"
        context += "\n2. Sentiment category (very_bearish, bearish, neutral, bullish, very_bullish)"
        context += "\n3. Key themes and narratives"
        context += "\n4. Potential market impact"
        context += "\nFormat as JSON."

        if self.anthropic_client:
            result = await self._analyze_with_claude(context)
        elif self.openai_client:
            result = await self._analyze_with_gpt(context)
        else:
            result = {
                "sentiment_score": 0,
                "sentiment_category": "neutral",
                "warning": "LLM not available"
            }

        return result
