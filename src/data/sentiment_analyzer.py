"""
SENTIMENT ANALYSIS FOR US30
Aggregates sentiment from multiple free sources
"""
import requests
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta
from collections import Counter
import re

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """
    Aggregates market sentiment from free sources:
    - Reddit (wallstreetbets, stocks, Dow30, investing)
    - Fear & Greed Index
    - VIX level (volatility sentiment)
    - Market breadth indicators
    """

    def __init__(self):
        self.reddit_keywords = [
            'dow', 'us30', 'dow jones', 'djia', 'dow 30',
            'blue chip', 'industrial average'
        ]

    def get_overall_sentiment(self) -> Dict[str, float]:
        """
        Get aggregated market sentiment

        Returns:
            sentiment_score: -1 (bearish) to +1 (bullish)
            confidence: 0-100
            sources: breakdown by source
        """
        sentiments = {}

        # 1. Fear & Greed Index
        try:
            fg_sentiment = self._get_fear_greed_index()
            sentiments['fear_greed'] = fg_sentiment
        except Exception as e:
            logger.warning(f"Fear & Greed failed: {e}")
            sentiments['fear_greed'] = 0.0

        # 2. VIX-based sentiment
        try:
            vix_sentiment = self._get_vix_sentiment()
            sentiments['vix'] = vix_sentiment
        except Exception as e:
            logger.warning(f"VIX sentiment failed: {e}")
            sentiments['vix'] = 0.0

        # 3. Reddit sentiment
        try:
            reddit_sentiment = self._get_reddit_sentiment()
            sentiments['reddit'] = reddit_sentiment
        except Exception as e:
            logger.warning(f"Reddit sentiment failed: {e}")
            sentiments['reddit'] = 0.0

        # 4. Market breadth
        try:
            breadth_sentiment = self._get_market_breadth()
            sentiments['breadth'] = breadth_sentiment
        except Exception as e:
            logger.warning(f"Market breadth failed: {e}")
            sentiments['breadth'] = 0.0

        # Weighted average
        weights = {
            'fear_greed': 0.30,
            'vix': 0.25,
            'reddit': 0.20,
            'breadth': 0.25
        }

        total_weight = sum(weights.values())
        overall_sentiment = sum(sentiments[k] * weights[k] for k in sentiments) / total_weight

        # Calculate confidence based on agreement
        sentiment_values = list(sentiments.values())
        sentiment_std = np.std(sentiment_values)
        confidence = max(0, 100 - (sentiment_std * 100))

        return {
            'sentiment_score': overall_sentiment,
            'confidence': confidence,
            'sources': sentiments,
            'interpretation': self._interpret_sentiment(overall_sentiment)
        }

    def _get_fear_greed_index(self) -> float:
        """
        CNN Fear & Greed Index (free API)
        Returns: -1 (extreme fear) to +1 (extreme greed)
        """
        try:
            # Alternative Fear & Greed API
            url = "https://api.alternative.me/fng/?limit=1"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                value = int(data['data'][0]['value'])

                # Convert 0-100 to -1 to +1
                # 0-25 = extreme fear (-1 to -0.5)
                # 25-45 = fear (-0.5 to -0.1)
                # 45-55 = neutral (-0.1 to 0.1)
                # 55-75 = greed (0.1 to 0.5)
                # 75-100 = extreme greed (0.5 to 1.0)

                if value < 25:
                    return -1 + (value / 25) * 0.5
                elif value < 45:
                    return -0.5 + ((value - 25) / 20) * 0.4
                elif value < 55:
                    return -0.1 + ((value - 45) / 10) * 0.2
                elif value < 75:
                    return 0.1 + ((value - 55) / 20) * 0.4
                else:
                    return 0.5 + ((value - 75) / 25) * 0.5

        except Exception as e:
            logger.warning(f"Fear & Greed API error: {e}")

        return 0.0

    def _get_vix_sentiment(self) -> float:
        """
        VIX-based sentiment
        Low VIX = bullish, High VIX = bearish
        Returns: -1 to +1
        """
        try:
            # Use Yahoo Finance API (free)
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=1d"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                vix = data['chart']['result'][0]['indicators']['quote'][0]['close'][0]

                # VIX interpretation:
                # < 12 = very low vol (bullish) = +1
                # 12-20 = low vol (bullish) = +0.5
                # 20-30 = normal (neutral) = 0
                # 30-40 = high vol (bearish) = -0.5
                # > 40 = panic (very bearish) = -1

                if vix < 12:
                    return 1.0
                elif vix < 20:
                    return 0.5
                elif vix < 30:
                    return 0.0
                elif vix < 40:
                    return -0.5
                else:
                    return -1.0

        except Exception as e:
            logger.warning(f"VIX API error: {e}")

        return 0.0

    def _get_reddit_sentiment(self) -> float:
        """
        Reddit sentiment from financial subreddits
        Uses Pushshift/Reddit API (free, no key needed)
        Returns: -1 to +1
        """
        try:
            # Pushshift API for Reddit data
            subreddits = ['wallstreetbets', 'stocks', 'investing']
            keywords = ' OR '.join(self.reddit_keywords)

            sentiment_scores = []

            for subreddit in subreddits:
                try:
                    url = f"https://api.pushshift.io/reddit/search/submission/"
                    params = {
                        'subreddit': subreddit,
                        'q': keywords,
                        'size': 25,
                        'sort': 'desc',
                        'after': int((datetime.now() - timedelta(days=1)).timestamp())
                    }

                    response = requests.get(url, params=params, timeout=5)
                    if response.status_code != 200:
                        continue

                    posts = response.json().get('data', [])

                    for post in posts:
                        title = post.get('title', '').lower()
                        score = post.get('score', 0)

                        # Simple keyword-based sentiment
                        bullish_words = ['bullish', 'buy', 'calls', 'moon', 'rally', 'breakout', 'up']
                        bearish_words = ['bearish', 'sell', 'puts', 'crash', 'dump', 'down', 'drop']

                        bull_count = sum(1 for word in bullish_words if word in title)
                        bear_count = sum(1 for word in bearish_words if word in title)

                        if bull_count > bear_count:
                            sentiment_scores.append(min(1.0, score / 100))
                        elif bear_count > bull_count:
                            sentiment_scores.append(max(-1.0, -score / 100))

                except:
                    continue

            if sentiment_scores:
                return np.clip(np.mean(sentiment_scores), -1, 1)

        except Exception as e:
            logger.warning(f"Reddit sentiment error: {e}")

        return 0.0

    def _get_market_breadth(self) -> float:
        """
        Market breadth indicators
        Advance/Decline ratio proxy
        Returns: -1 to +1
        """
        try:
            # Get DOW components performance (proxy)
            # Using simple market breadth from major indices

            symbols = ['^DJI', '^GSPC', '^IXIC']  # Dow, S&P, Nasdaq
            performances = []

            for symbol in symbols:
                try:
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                    params = {'interval': '1d', 'range': '5d'}
                    response = requests.get(url, params=params, timeout=5)

                    if response.status_code == 200:
                        data = response.json()
                        quotes = data['chart']['result'][0]['indicators']['quote'][0]['close']

                        # Calculate 5-day return
                        if len(quotes) >= 5:
                            ret = (quotes[-1] - quotes[0]) / quotes[0]
                            performances.append(ret)

                except:
                    continue

            if performances:
                avg_return = np.mean(performances)
                # Convert to -1 to +1
                # +5% = +1, -5% = -1
                return np.clip(avg_return * 20, -1, 1)

        except Exception as e:
            logger.warning(f"Market breadth error: {e}")

        return 0.0

    def _interpret_sentiment(self, score: float) -> str:
        """Convert sentiment score to interpretation"""
        if score > 0.5:
            return "VERY_BULLISH"
        elif score > 0.2:
            return "BULLISH"
        elif score > -0.2:
            return "NEUTRAL"
        elif score > -0.5:
            return "BEARISH"
        else:
            return "VERY_BEARISH"

    def get_sentiment_features(self) -> Dict[str, float]:
        """
        Get sentiment as ML features

        Returns dictionary of features for ML model
        """
        sentiment_data = self.get_overall_sentiment()

        features = {
            'sentiment_overall': sentiment_data['sentiment_score'],
            'sentiment_confidence': sentiment_data['confidence'] / 100,
            'sentiment_fear_greed': sentiment_data['sources'].get('fear_greed', 0),
            'sentiment_vix': sentiment_data['sources'].get('vix', 0),
            'sentiment_reddit': sentiment_data['sources'].get('reddit', 0),
            'sentiment_breadth': sentiment_data['sources'].get('breadth', 0),
            'sentiment_very_bullish': 1 if sentiment_data['interpretation'] == 'VERY_BULLISH' else 0,
            'sentiment_bullish': 1 if sentiment_data['interpretation'] == 'BULLISH' else 0,
            'sentiment_bearish': 1 if sentiment_data['interpretation'] == 'BEARISH' else 0,
            'sentiment_very_bearish': 1 if sentiment_data['interpretation'] == 'VERY_BEARISH' else 0
        }

        return features
