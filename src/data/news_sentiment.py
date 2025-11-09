"""
News Sentiment Analysis for Trading
Uses free news APIs and TextBlob for sentiment
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    print("⚠️  TextBlob not available - install with: pip install textblob")


class NewsSentimentAnalyzer:
    """
    Fetch and analyze news sentiment for trading symbols
    
    Free APIs supported:
    - NewsAPI.org (100 requests/day free)
    - Finnhub.io (60 requests/minute free)
    - Alpha Vantage (5 requests/minute free)
    """
    
    def __init__(self, api_key: Optional[str] = None, provider: str = 'newsapi'):
        """
        Initialize news sentiment analyzer
        
        Args:
            api_key: API key for news provider (optional for some)
            provider: 'newsapi', 'finnhub', or 'alphavantage'
        """
        self.api_key = api_key
        self.provider = provider
        self.cache = {}
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds between requests
        
    def get_symbol_sentiment(self, symbol: str, hours: int = 24) -> Dict:
        """
        Get news sentiment for a symbol
        
        Args:
            symbol: Trading symbol (e.g., 'US30', 'EURUSD', 'XAU')
            hours: Look back this many hours
            
        Returns:
            {
                'sentiment_score': float (-1 to 1),
                'sentiment_magnitude': float (0 to 1),
                'news_count': int,
                'positive_count': int,
                'negative_count': int,
                'neutral_count': int
            }
        """
        # Check cache
        cache_key = f"{symbol}_{hours}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < 300:  # 5 min cache
                return cached_data
        
        # Rate limiting
        self._rate_limit()
        
        # Get news
        news_articles = self._fetch_news(symbol, hours)
        
        if not news_articles:
            return self._get_neutral_sentiment()
        
        # Analyze sentiment
        sentiment_data = self._analyze_sentiment(news_articles)
        
        # Cache result
        self.cache[cache_key] = (time.time(), sentiment_data)
        
        return sentiment_data
    
    def _fetch_news(self, symbol: str, hours: int) -> List[Dict]:
        """Fetch news articles"""
        # Map trading symbols to search terms
        search_term = self._symbol_to_search_term(symbol)
        
        if self.provider == 'newsapi' and self.api_key:
            return self._fetch_newsapi(search_term, hours)
        elif self.provider == 'finnhub' and self.api_key:
            return self._fetch_finnhub(search_term, hours)
        else:
            # Fallback: use free RSS feeds
            return self._fetch_rss(search_term, hours)
    
    def _fetch_newsapi(self, search_term: str, hours: int) -> List[Dict]:
        """Fetch from NewsAPI.org"""
        url = "https://newsapi.org/v2/everything"
        params = {
            'q': search_term,
            'from': (datetime.now() - timedelta(hours=hours)).isoformat(),
            'sortBy': 'publishedAt',
            'language': 'en',
            'apiKey': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('articles', [])
        except Exception as e:
            print(f"⚠️  NewsAPI error: {e}")
        
        return []
    
    def _fetch_finnhub(self, search_term: str, hours: int) -> List[Dict]:
        """Fetch from Finnhub.io"""
        url = "https://finnhub.io/api/v1/news"
        params = {
            'category': 'forex' if 'USD' in search_term else 'general',
            'token': self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"⚠️  Finnhub error: {e}")
        
        return []
    
    def _fetch_rss(self, search_term: str, hours: int) -> List[Dict]:
        """Fallback: Simple RSS feed parsing"""
        # For now, return empty - can add RSS parsing later
        return []
    
    def _analyze_sentiment(self, articles: List[Dict]) -> Dict:
        """Analyze sentiment of news articles"""
        if not TEXTBLOB_AVAILABLE:
            return self._get_neutral_sentiment()
        
        sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for article in articles:
            # Get text
            text = article.get('title', '') + ' ' + article.get('description', '')
            if not text.strip():
                continue
            
            # Analyze
            try:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity  # -1 to 1
                
                sentiments.append(polarity)
                
                if polarity > 0.1:
                    positive_count += 1
                elif polarity < -0.1:
                    negative_count += 1
                else:
                    neutral_count += 1
            except:
                continue
        
        if not sentiments:
            return self._get_neutral_sentiment()
        
        # Calculate metrics
        avg_sentiment = sum(sentiments) / len(sentiments)
        sentiment_std = (sum((s - avg_sentiment) ** 2 for s in sentiments) / len(sentiments)) ** 0.5
        
        return {
            'sentiment_score': avg_sentiment,
            'sentiment_magnitude': sentiment_std,
            'news_count': len(sentiments),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'sentiment_trend': 'bullish' if avg_sentiment > 0.1 else 'bearish' if avg_sentiment < -0.1 else 'neutral'
        }
    
    def _get_neutral_sentiment(self) -> Dict:
        """Return neutral sentiment"""
        return {
            'sentiment_score': 0.0,
            'sentiment_magnitude': 0.0,
            'news_count': 0,
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'sentiment_trend': 'neutral'
        }
    
    def _symbol_to_search_term(self, symbol: str) -> str:
        """Convert trading symbol to search term"""
        symbol_map = {
            'US30': 'Dow Jones',
            'US100': 'Nasdaq',
            'US500': 'S&P 500',
            'EURUSD': 'EUR USD forex',
            'GBPUSD': 'GBP USD forex',
            'USDJPY': 'USD JPY forex',
            'XAU': 'Gold',
            'USOIL': 'Crude Oil'
        }
        
        # Remove .sim suffix
        clean_symbol = symbol.replace('.sim', '').replace('Z25', '').replace('F26', '')
        
        return symbol_map.get(clean_symbol, clean_symbol)
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()


# Example usage
if __name__ == "__main__":
    # Without API key (uses fallback)
    analyzer = NewsSentimentAnalyzer()
    
    # With NewsAPI key
    # analyzer = NewsSentimentAnalyzer(api_key='YOUR_API_KEY', provider='newsapi')
    
    symbols = ['US30', 'EURUSD', 'XAU']
    
    for symbol in symbols:
        sentiment = analyzer.get_symbol_sentiment(symbol, hours=24)
        print(f"\n{symbol} Sentiment:")
        print(f"  Score: {sentiment['sentiment_score']:.3f}")
        print(f"  Trend: {sentiment['sentiment_trend']}")
        print(f"  News Count: {sentiment['news_count']}")
        print(f"  Positive: {sentiment['positive_count']}")
        print(f"  Negative: {sentiment['negative_count']}")
