"""
News Sentiment Analysis
Phase 3 - Avoid trading during high-impact news
"""

import requests
from datetime import datetime, timedelta
import json

class NewsSentimentAnalyzer:
    """
    Analyzes news sentiment and economic calendar
    Helps avoid trading during high-impact events
    """
    
    def __init__(self):
        # Using free news API
        self.news_api_key = None  # Will use free tier
        self.economic_calendar_cache = {}
        self.last_update = None
        
    def get_economic_calendar(self):
        """Get today's economic events"""
        try:
            # Using investing.com economic calendar (free)
            # In production, use paid API for reliability
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Check cache
            if today in self.economic_calendar_cache:
                return self.economic_calendar_cache[today]
            
            # High-impact events to avoid (hardcoded for now)
            # In production, fetch from API
            high_impact_times = [
                {'time': '08:30', 'event': 'NFP', 'impact': 'HIGH'},
                {'time': '10:00', 'event': 'ISM', 'impact': 'HIGH'},
                {'time': '14:00', 'event': 'FOMC', 'impact': 'HIGH'},
            ]
            
            self.economic_calendar_cache[today] = high_impact_times
            self.last_update = datetime.now()
            
            return high_impact_times
            
        except Exception as e:
            print(f"News API error: {e}")
            return []
    
    def is_high_impact_news_time(self, buffer_minutes=30):
        """
        Check if current time is near high-impact news
        Returns: (is_news_time, event_name)
        """
        try:
            events = self.get_economic_calendar()
            current_time = datetime.now()
            
            for event in events:
                # Parse event time
                event_hour, event_min = map(int, event['time'].split(':'))
                event_time = current_time.replace(hour=event_hour, minute=event_min, second=0)
                
                # Check if within buffer
                time_diff = abs((current_time - event_time).total_seconds() / 60)
                
                if time_diff <= buffer_minutes and event['impact'] == 'HIGH':
                    return True, event['event']
            
            return False, None
            
        except Exception as e:
            print(f"News check error: {e}")
            return False, None
    
    def get_market_sentiment(self):
        """
        Get overall market sentiment from news
        Returns: sentiment score (-1 to 1)
        """
        try:
            # In production, analyze news headlines
            # For now, return neutral
            return 0.0
            
        except Exception as e:
            print(f"Sentiment error: {e}")
            return 0.0
    
    def should_avoid_trading(self):
        """
        Determine if trading should be avoided
        Returns: (should_avoid, reason)
        """
        # Check for high-impact news
        is_news_time, event = self.is_high_impact_news_time()
        
        if is_news_time:
            return True, f"High-impact news: {event}"
        
        # Check market hours (avoid first/last 15 min)
        current_time = datetime.now()
        hour = current_time.hour
        minute = current_time.minute
        
        # Market opens at 9:30 ET
        if hour == 9 and minute < 45:
            return True, "Market opening volatility"
        
        # Market closes at 16:00 ET
        if hour == 15 and minute > 45:
            return True, "Market closing volatility"
        
        return False, None
