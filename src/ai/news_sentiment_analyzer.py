"""
News Sentiment Analysis - Hedge Fund Grade
AI-powered news impact assessment using NLP techniques

Based on institutional approaches:
- Keyword-based sentiment scoring (fast, reliable)
- Event classification (Fed, NFP, CPI, etc.)
- Currency/Asset impact mapping
- Historical event impact analysis
- Real-time sentiment aggregation
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class NewsImpact(Enum):
    """News impact levels"""
    CRITICAL = "CRITICAL"      # Fed rate decision, NFP, major geopolitical
    HIGH = "HIGH"              # CPI, GDP, central bank speeches
    MEDIUM = "MEDIUM"          # PMI, retail sales, housing data
    LOW = "LOW"                # Minor economic data
    NONE = "NONE"              # No significant news


class NewsSentiment(Enum):
    """Sentiment classification"""
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"


@dataclass
class NewsEvent:
    """Structured news event"""
    title: str
    timestamp: datetime
    impact: NewsImpact
    sentiment: NewsSentiment
    sentiment_score: float  # -1 to 1
    affected_currencies: List[str]
    affected_assets: List[str]
    event_type: str
    source: str


@dataclass
class MarketSentimentState:
    """Aggregated market sentiment"""
    overall_sentiment: NewsSentiment
    sentiment_score: float  # -1 to 1
    confidence: float  # 0-1
    dominant_theme: str
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'
    upcoming_events: List[Dict]
    recent_events: List[Dict]
    currency_sentiment: Dict[str, float]
    asset_sentiment: Dict[str, float]


class NewsSentimentAnalyzer:
    """
    AI-powered news sentiment analysis
    
    Features:
    1. Keyword-based sentiment scoring
    2. Event type classification
    3. Currency/Asset impact mapping
    4. Temporal decay (recent news weighted more)
    5. Aggregated market sentiment
    """
    
    def __init__(self):
        # ═══════════════════════════════════════════════════════════
        # SENTIMENT KEYWORDS - Institutional Grade
        # Based on how markets typically react to these terms
        # ═══════════════════════════════════════════════════════════
        
        self.bullish_keywords = {
            # Strong bullish
            'surge': 0.8, 'soar': 0.8, 'rally': 0.7, 'boom': 0.8,
            'breakout': 0.6, 'bullish': 0.7, 'optimistic': 0.5,
            'growth': 0.4, 'expansion': 0.5, 'recovery': 0.5,
            'beat expectations': 0.6, 'beats': 0.5, 'exceeds': 0.5,
            'stronger than expected': 0.6, 'upside surprise': 0.7,
            'hawkish': 0.5,  # Bullish for currency
            'rate hike': 0.4, 'tightening': 0.3,
            'record high': 0.6, 'all-time high': 0.7,
            'breakthrough': 0.5, 'accelerate': 0.4,
            'outperform': 0.5, 'upgrade': 0.5,
            
            # Moderate bullish
            'improve': 0.3, 'gain': 0.3, 'rise': 0.3,
            'increase': 0.2, 'higher': 0.2, 'up': 0.1,
            'positive': 0.3, 'strong': 0.3, 'robust': 0.4,
            'resilient': 0.3, 'stable': 0.2,
        }
        
        self.bearish_keywords = {
            # Strong bearish
            'crash': -0.9, 'collapse': -0.8, 'plunge': -0.8,
            'crisis': -0.7, 'recession': -0.7, 'bearish': -0.7,
            'panic': -0.8, 'fear': -0.5, 'sell-off': -0.6,
            'miss expectations': -0.6, 'misses': -0.5, 'disappoints': -0.5,
            'weaker than expected': -0.6, 'downside surprise': -0.7,
            'dovish': -0.5,  # Bearish for currency
            'rate cut': -0.4, 'easing': -0.3,
            'record low': -0.6, 'all-time low': -0.7,
            'breakdown': -0.5, 'decelerate': -0.4,
            'underperform': -0.5, 'downgrade': -0.5,
            
            # Moderate bearish
            'decline': -0.3, 'drop': -0.3, 'fall': -0.3,
            'decrease': -0.2, 'lower': -0.2, 'down': -0.1,
            'negative': -0.3, 'weak': -0.3, 'soft': -0.3,
            'concern': -0.3, 'worry': -0.3, 'uncertain': -0.2,
            'slowdown': -0.4, 'contraction': -0.5,
            'default': -0.7, 'bankruptcy': -0.8,
            'war': -0.6, 'conflict': -0.5, 'sanctions': -0.4,
            'inflation': -0.3,  # Generally negative for risk assets
        }
        
        # ═══════════════════════════════════════════════════════════
        # EVENT TYPE CLASSIFICATION
        # ═══════════════════════════════════════════════════════════
        
        self.event_patterns = {
            'FED': {
                'patterns': ['fed', 'fomc', 'federal reserve', 'powell', 'rate decision'],
                'impact': NewsImpact.CRITICAL,
                'affected_currencies': ['usd'],
                'affected_assets': ['us30', 'us100', 'us500', 'xau'],
            },
            'ECB': {
                'patterns': ['ecb', 'european central bank', 'lagarde'],
                'impact': NewsImpact.CRITICAL,
                'affected_currencies': ['eur'],
                'affected_assets': ['de40', 'eu50'],
            },
            'BOE': {
                'patterns': ['boe', 'bank of england', 'bailey'],
                'impact': NewsImpact.CRITICAL,
                'affected_currencies': ['gbp'],
                'affected_assets': ['uk100'],
            },
            'BOJ': {
                'patterns': ['boj', 'bank of japan', 'ueda', 'kuroda'],
                'impact': NewsImpact.CRITICAL,
                'affected_currencies': ['jpy'],
                'affected_assets': [],
            },
            'NFP': {
                'patterns': ['nfp', 'non-farm payroll', 'jobs report', 'employment'],
                'impact': NewsImpact.CRITICAL,
                'affected_currencies': ['usd'],
                'affected_assets': ['us30', 'us100', 'us500'],
            },
            'CPI': {
                'patterns': ['cpi', 'inflation', 'consumer price'],
                'impact': NewsImpact.HIGH,
                'affected_currencies': ['usd', 'eur', 'gbp'],
                'affected_assets': ['xau', 'us30', 'us100'],
            },
            'GDP': {
                'patterns': ['gdp', 'gross domestic product', 'economic growth'],
                'impact': NewsImpact.HIGH,
                'affected_currencies': ['usd', 'eur', 'gbp'],
                'affected_assets': ['us30', 'us100', 'us500'],
            },
            'PMI': {
                'patterns': ['pmi', 'purchasing manager', 'manufacturing index'],
                'impact': NewsImpact.MEDIUM,
                'affected_currencies': ['usd', 'eur', 'gbp', 'cny'],
                'affected_assets': [],
            },
            'RETAIL': {
                'patterns': ['retail sales', 'consumer spending'],
                'impact': NewsImpact.MEDIUM,
                'affected_currencies': ['usd', 'eur', 'gbp'],
                'affected_assets': [],
            },
            'GEOPOLITICAL': {
                'patterns': ['war', 'conflict', 'sanctions', 'tariff', 'trade war', 'military'],
                'impact': NewsImpact.HIGH,
                'affected_currencies': [],
                'affected_assets': ['xau', 'usoil'],
            },
            'EARNINGS': {
                'patterns': ['earnings', 'quarterly results', 'profit', 'revenue'],
                'impact': NewsImpact.MEDIUM,
                'affected_currencies': [],
                'affected_assets': ['us30', 'us100', 'us500'],
            },
        }
        
        # ═══════════════════════════════════════════════════════════
        # CURRENCY IMPACT MAPPING
        # How events typically affect each currency
        # ═══════════════════════════════════════════════════════════
        
        self.currency_event_impact = {
            'usd': {
                'hawkish_fed': 0.8,
                'dovish_fed': -0.8,
                'strong_nfp': 0.7,
                'weak_nfp': -0.7,
                'high_cpi': 0.5,  # Initially bullish (rate hike expectations)
                'low_cpi': -0.3,
                'risk_off': 0.5,  # USD = safe haven
                'risk_on': -0.3,
            },
            'eur': {
                'hawkish_ecb': 0.8,
                'dovish_ecb': -0.8,
                'strong_eu_data': 0.5,
                'weak_eu_data': -0.5,
                'risk_off': -0.3,
                'risk_on': 0.3,
            },
            'jpy': {
                'hawkish_boj': 0.8,
                'dovish_boj': -0.8,
                'risk_off': 0.7,  # JPY = safe haven
                'risk_on': -0.5,
            },
            'gbp': {
                'hawkish_boe': 0.8,
                'dovish_boe': -0.8,
                'strong_uk_data': 0.5,
                'weak_uk_data': -0.5,
            },
            'aud': {
                'risk_on': 0.6,  # AUD = risk currency
                'risk_off': -0.6,
                'china_positive': 0.5,
                'china_negative': -0.5,
            },
            'cad': {
                'oil_up': 0.5,  # CAD correlated with oil
                'oil_down': -0.5,
                'risk_on': 0.3,
                'risk_off': -0.3,
            },
        }
        
        # News event history
        self.news_history: List[NewsEvent] = []
        self.max_history = 100
        
        # Current sentiment state
        self.current_sentiment: Optional[MarketSentimentState] = None
        
    def analyze_headline(self, headline: str, source: str = 'unknown') -> NewsEvent:
        """
        Analyze a single news headline
        
        Returns structured NewsEvent with sentiment and impact
        """
        headline_lower = headline.lower()
        
        # Calculate sentiment score
        sentiment_score = 0.0
        matched_keywords = []
        
        for keyword, score in self.bullish_keywords.items():
            if keyword in headline_lower:
                sentiment_score += score
                matched_keywords.append((keyword, score))
        
        for keyword, score in self.bearish_keywords.items():
            if keyword in headline_lower:
                sentiment_score += score
                matched_keywords.append((keyword, score))
        
        # Normalize sentiment score to -1 to 1
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        # Classify sentiment
        if sentiment_score > 0.5:
            sentiment = NewsSentiment.VERY_BULLISH
        elif sentiment_score > 0.2:
            sentiment = NewsSentiment.BULLISH
        elif sentiment_score < -0.5:
            sentiment = NewsSentiment.VERY_BEARISH
        elif sentiment_score < -0.2:
            sentiment = NewsSentiment.BEARISH
        else:
            sentiment = NewsSentiment.NEUTRAL
        
        # Classify event type and impact
        event_type = 'GENERAL'
        impact = NewsImpact.LOW
        affected_currencies = []
        affected_assets = []
        
        for etype, config in self.event_patterns.items():
            for pattern in config['patterns']:
                if pattern in headline_lower:
                    event_type = etype
                    impact = config['impact']
                    affected_currencies = config['affected_currencies']
                    affected_assets = config['affected_assets']
                    break
            if event_type != 'GENERAL':
                break
        
        # Create news event
        event = NewsEvent(
            title=headline,
            timestamp=datetime.now(),
            impact=impact,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            affected_currencies=affected_currencies,
            affected_assets=affected_assets,
            event_type=event_type,
            source=source
        )
        
        # Add to history
        self.news_history.append(event)
        if len(self.news_history) > self.max_history:
            self.news_history = self.news_history[-self.max_history:]
        
        logger.info(f"📰 NEWS: {headline[:50]}...")
        logger.info(f"   Sentiment: {sentiment.value} ({sentiment_score:.2f})")
        logger.info(f"   Impact: {impact.value}, Type: {event_type}")
        
        return event
    
    def analyze_multiple_headlines(self, headlines: List[str], source: str = 'unknown') -> List[NewsEvent]:
        """Analyze multiple headlines"""
        return [self.analyze_headline(h, source) for h in headlines]
    
    def get_aggregated_sentiment(
        self,
        lookback_minutes: int = 60,
        symbol: str = None
    ) -> MarketSentimentState:
        """
        Get aggregated market sentiment from recent news
        
        Args:
            lookback_minutes: How far back to look
            symbol: Optional - filter for specific symbol
            
        Returns:
            MarketSentimentState with aggregated analysis
        """
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        # Filter recent events
        recent_events = [e for e in self.news_history if e.timestamp > cutoff_time]
        
        # Filter by symbol if specified
        if symbol:
            symbol_clean = symbol.lower().replace('usd', '').replace('jpy', '').replace('.sim', '')
            recent_events = [
                e for e in recent_events 
                if symbol_clean in e.affected_currencies or symbol_clean in e.affected_assets
            ]
        
        if not recent_events:
            return MarketSentimentState(
                overall_sentiment=NewsSentiment.NEUTRAL,
                sentiment_score=0.0,
                confidence=0.3,
                dominant_theme='No recent news',
                risk_level='LOW',
                upcoming_events=[],
                recent_events=[],
                currency_sentiment={},
                asset_sentiment={}
            )
        
        # Calculate weighted sentiment (more recent = higher weight)
        total_weight = 0.0
        weighted_sentiment = 0.0
        
        for event in recent_events:
            # Time decay: events from 60 min ago get 50% weight
            age_minutes = (datetime.now() - event.timestamp).total_seconds() / 60
            time_weight = 1.0 - (age_minutes / lookback_minutes * 0.5)
            
            # Impact weight
            impact_weights = {
                NewsImpact.CRITICAL: 2.0,
                NewsImpact.HIGH: 1.5,
                NewsImpact.MEDIUM: 1.0,
                NewsImpact.LOW: 0.5,
                NewsImpact.NONE: 0.1,
            }
            impact_weight = impact_weights.get(event.impact, 1.0)
            
            weight = time_weight * impact_weight
            weighted_sentiment += event.sentiment_score * weight
            total_weight += weight
        
        avg_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0.0
        
        # Classify overall sentiment
        if avg_sentiment > 0.4:
            overall = NewsSentiment.VERY_BULLISH
        elif avg_sentiment > 0.15:
            overall = NewsSentiment.BULLISH
        elif avg_sentiment < -0.4:
            overall = NewsSentiment.VERY_BEARISH
        elif avg_sentiment < -0.15:
            overall = NewsSentiment.BEARISH
        else:
            overall = NewsSentiment.NEUTRAL
        
        # Find dominant theme
        theme_counts = defaultdict(int)
        for event in recent_events:
            theme_counts[event.event_type] += 1
        dominant_theme = max(theme_counts, key=theme_counts.get) if theme_counts else 'GENERAL'
        
        # Calculate risk level
        critical_count = sum(1 for e in recent_events if e.impact == NewsImpact.CRITICAL)
        high_count = sum(1 for e in recent_events if e.impact == NewsImpact.HIGH)
        
        if critical_count >= 2 or (critical_count >= 1 and abs(avg_sentiment) > 0.5):
            risk_level = 'EXTREME'
        elif critical_count >= 1 or high_count >= 3:
            risk_level = 'HIGH'
        elif high_count >= 1:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
        
        # Calculate per-currency sentiment
        currency_sentiment = defaultdict(list)
        for event in recent_events:
            for curr in event.affected_currencies:
                currency_sentiment[curr].append(event.sentiment_score)
        
        currency_avg = {k: sum(v)/len(v) for k, v in currency_sentiment.items()}
        
        # Calculate per-asset sentiment
        asset_sentiment = defaultdict(list)
        for event in recent_events:
            for asset in event.affected_assets:
                asset_sentiment[asset].append(event.sentiment_score)
        
        asset_avg = {k: sum(v)/len(v) for k, v in asset_sentiment.items()}
        
        # Confidence based on number of events
        confidence = min(1.0, len(recent_events) / 10)
        
        state = MarketSentimentState(
            overall_sentiment=overall,
            sentiment_score=avg_sentiment,
            confidence=confidence,
            dominant_theme=dominant_theme,
            risk_level=risk_level,
            upcoming_events=[],  # Would need calendar integration
            recent_events=[{
                'title': e.title[:50],
                'sentiment': e.sentiment.value,
                'impact': e.impact.value,
                'age_minutes': int((datetime.now() - e.timestamp).total_seconds() / 60)
            } for e in recent_events[-5:]],
            currency_sentiment=currency_avg,
            asset_sentiment=asset_avg
        )
        
        self.current_sentiment = state
        return state
    
    def get_symbol_sentiment(self, symbol: str) -> Dict:
        """
        Get sentiment specifically for a trading symbol
        
        Returns actionable trading guidance based on news
        """
        symbol_clean = symbol.lower()
        
        # Determine affected currencies/assets
        affected = []
        if 'usd' in symbol_clean:
            affected.append('usd')
        if 'eur' in symbol_clean:
            affected.append('eur')
        if 'gbp' in symbol_clean:
            affected.append('gbp')
        if 'jpy' in symbol_clean:
            affected.append('jpy')
        if 'aud' in symbol_clean:
            affected.append('aud')
        if 'cad' in symbol_clean:
            affected.append('cad')
        if 'xau' in symbol_clean or 'gold' in symbol_clean:
            affected.append('xau')
        if 'us30' in symbol_clean or 'dow' in symbol_clean:
            affected.append('us30')
        if 'us100' in symbol_clean or 'nasdaq' in symbol_clean:
            affected.append('us100')
        if 'us500' in symbol_clean or 'spx' in symbol_clean:
            affected.append('us500')
        if 'oil' in symbol_clean:
            affected.append('usoil')
        
        # Get aggregated sentiment
        state = self.get_aggregated_sentiment(lookback_minutes=120)
        
        # Calculate symbol-specific sentiment
        symbol_sentiment = 0.0
        relevant_events = 0
        
        for event in self.news_history[-50:]:
            is_relevant = any(
                a in event.affected_currencies or a in event.affected_assets 
                for a in affected
            )
            if is_relevant:
                symbol_sentiment += event.sentiment_score
                relevant_events += 1
        
        if relevant_events > 0:
            symbol_sentiment /= relevant_events
        
        # Trading guidance
        if state.risk_level == 'EXTREME':
            guidance = 'AVOID_TRADING'
            reason = 'Extreme news risk - wait for clarity'
        elif state.risk_level == 'HIGH' and abs(symbol_sentiment) < 0.3:
            guidance = 'REDUCE_SIZE'
            reason = 'High news risk with unclear direction'
        elif symbol_sentiment > 0.4:
            guidance = 'BULLISH_BIAS'
            reason = f'Strong bullish news sentiment ({symbol_sentiment:.2f})'
        elif symbol_sentiment < -0.4:
            guidance = 'BEARISH_BIAS'
            reason = f'Strong bearish news sentiment ({symbol_sentiment:.2f})'
        elif abs(symbol_sentiment) < 0.1:
            guidance = 'NEUTRAL'
            reason = 'No significant news bias'
        else:
            guidance = 'SLIGHT_BIAS'
            reason = f'Moderate news sentiment ({symbol_sentiment:.2f})'
        
        return {
            'symbol': symbol,
            'sentiment_score': symbol_sentiment,
            'overall_market_sentiment': state.overall_sentiment.value,
            'risk_level': state.risk_level,
            'guidance': guidance,
            'reason': reason,
            'relevant_events': relevant_events,
            'dominant_theme': state.dominant_theme
        }
    
    def should_avoid_trading(self, symbol: str = None) -> Tuple[bool, str]:
        """
        Check if news conditions suggest avoiding trading
        """
        state = self.get_aggregated_sentiment(lookback_minutes=30)
        
        if state.risk_level == 'EXTREME':
            return True, f"EXTREME news risk: {state.dominant_theme}"
        
        if state.risk_level == 'HIGH' and state.confidence > 0.5:
            # Check if it affects our symbol
            if symbol:
                symbol_data = self.get_symbol_sentiment(symbol)
                if symbol_data['relevant_events'] > 0:
                    return True, f"HIGH impact news affecting {symbol}"
        
        return False, "News conditions acceptable"


# Global instance
_news_analyzer = None

def get_news_analyzer() -> NewsSentimentAnalyzer:
    """Get global news sentiment analyzer instance"""
    global _news_analyzer
    if _news_analyzer is None:
        _news_analyzer = NewsSentimentAnalyzer()
    return _news_analyzer
