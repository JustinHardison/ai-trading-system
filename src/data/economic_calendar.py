"""
Economic Calendar Integration - FTMO/Oanda
News-aware trading: Avoid high-impact events, trade after releases
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

logger = get_logger(__name__)


class EconomicCalendar:
    """
    FTMO/Oanda Economic Calendar Integration
    
    Features:
    - Fetches upcoming economic events
    - Identifies high-impact news
    - Provides pre-news warnings
    - Post-news trading signals
    """
    
    def __init__(self):
        self.base_url = "https://ftmo.oanda.com/calendar/"
        self.events_cache = []
        self.last_update = None
        self.cache_duration = 3600  # 1 hour cache
        
        # US30-specific high-impact events (USD only!)
        self.high_impact_keywords = [
            'NFP', 'Non-Farm', 'FOMC', 'Fed', 'Interest Rate',
            'CPI', 'Inflation', 'GDP', 'Employment', 'Unemployment',
            'Retail Sales', 'PMI', 'ISM', 'PPI', 'PCE',
            'Jobless Claims', 'Consumer Confidence', 'Manufacturing',
            'Durable Goods', 'Housing', 'Industrial Production'
        ]
        
        # Only track USD events (US30 = Dow Jones = US market)
        self.relevant_currencies = ['USD']
        
        logger.info("Economic Calendar initialized")
        logger.info(f"  Source: FTMO/Oanda")
        logger.info(f"  High-impact events: {len(self.high_impact_keywords)} types")
    
    def fetch_events(self, days_ahead: int = 7) -> List[Dict]:
        """
        Fetch economic events from FTMO/Oanda calendar
        
        Args:
            days_ahead: Number of days to fetch
            
        Returns:
            List of events with time, currency, impact, event name
        """
        # Check cache
        if self.events_cache and self.last_update:
            if (datetime.now() - self.last_update).total_seconds() < self.cache_duration:
                logger.info(f"Using cached events ({len(self.events_cache)} events)")
                return self.events_cache
        
        try:
            # Build URL with date range
            date_from = datetime.now().strftime('%Y-%m-%d')
            date_to = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            url = f"{self.base_url}?dateFrom={date_from}&dateTo={date_to}&timezone=America/New_York"
            
            logger.info(f"Fetching economic calendar: {url}")
            
            # Note: This is a simplified version
            # In production, you'd parse the actual calendar data
            # For now, we'll use a mock structure
            
            events = self._parse_calendar_data(url)
            
            self.events_cache = events
            self.last_update = datetime.now()
            
            logger.info(f"✓ Fetched {len(events)} economic events")
            
            return events
            
        except Exception as e:
            logger.error(f"Error fetching calendar: {e}")
            return self.events_cache  # Return cached if available
    
    def _parse_calendar_data(self, url: str) -> List[Dict]:
        """
        Parse calendar data from FTMO/Oanda
        
        Note: This is a simplified mock version
        In production, you'd parse the actual HTML/JSON
        """
        # Mock events for demonstration
        # In production, parse actual calendar
        now = datetime.now()
        
        mock_events = [
            {
                'time': now.replace(hour=8, minute=30),
                'currency': 'USD',
                'impact': 'high',
                'event': 'CPI (Consumer Price Index)',
                'forecast': '0.3%',
                'previous': '0.2%'
            },
            {
                'time': now.replace(hour=10, minute=0),
                'currency': 'USD',
                'impact': 'medium',
                'event': 'Retail Sales',
                'forecast': '0.5%',
                'previous': '0.4%'
            },
            {
                'time': now.replace(hour=14, minute=0),
                'currency': 'USD',
                'impact': 'high',
                'event': 'FOMC Minutes',
                'forecast': '-',
                'previous': '-'
            }
        ]
        
        return mock_events
    
    def get_upcoming_events(self, hours_ahead: int = 4) -> List[Dict]:
        """
        Get events happening in next N hours
        
        Args:
            hours_ahead: Look ahead window
            
        Returns:
            List of upcoming events
        """
        events = self.fetch_events()
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)
        
        upcoming = [
            event for event in events
            if now <= event['time'] <= cutoff
        ]
        
        return upcoming
    
    def is_high_impact_event_soon(self, minutes_before: int = 30) -> Dict:
        """
        Check if high-impact USD event is coming soon (US30-specific)
        
        Args:
            minutes_before: Warning window before event
            
        Returns:
            {
                'warning': bool,
                'event': dict or None,
                'minutes_until': int
            }
        """
        events = self.fetch_events()
        now = datetime.now()
        
        for event in events:
            # US30 FILTER: Only USD events matter!
            if event['currency'] not in self.relevant_currencies:
                continue
            
            if event['impact'] != 'high':
                continue
            
            # Check if event name contains high-impact keywords
            is_high_impact = any(
                keyword.lower() in event['event'].lower()
                for keyword in self.high_impact_keywords
            )
            
            if not is_high_impact:
                continue
            
            # Calculate time until event
            time_until = (event['time'] - now).total_seconds() / 60
            
            # Check if within warning window
            if 0 <= time_until <= minutes_before:
                return {
                    'warning': True,
                    'event': event,
                    'minutes_until': int(time_until)
                }
        
        return {'warning': False, 'event': None, 'minutes_until': None}
    
    def should_avoid_trading(self, minutes_before: int = 30, minutes_after: int = 15) -> Dict:
        """
        Determine if we should avoid trading due to USD news (US30-specific)
        
        Args:
            minutes_before: Stop trading N minutes before event
            minutes_after: Resume trading N minutes after event
            
        Returns:
            {
                'avoid': bool,
                'reason': str,
                'event': dict or None
            }
        """
        events = self.fetch_events()
        now = datetime.now()
        
        for event in events:
            # US30 FILTER: Only USD events matter!
            if event['currency'] not in self.relevant_currencies:
                continue
            
            if event['impact'] != 'high':
                continue
            
            # Check if high-impact event
            is_high_impact = any(
                keyword.lower() in event['event'].lower()
                for keyword in self.high_impact_keywords
            )
            
            if not is_high_impact:
                continue
            
            # Calculate time relative to event
            time_diff = (event['time'] - now).total_seconds() / 60
            
            # Before event
            if 0 <= time_diff <= minutes_before:
                return {
                    'avoid': True,
                    'reason': f"High-impact event in {int(time_diff)} minutes: {event['event']}",
                    'event': event
                }
            
            # After event (within cooldown)
            if -minutes_after <= time_diff < 0:
                return {
                    'avoid': True,
                    'reason': f"High-impact event {abs(int(time_diff))} minutes ago: {event['event']} (cooldown)",
                    'event': event
                }
        
        return {'avoid': False, 'reason': 'No high-impact events nearby', 'event': None}
    
    def get_news_risk_adjustment(self) -> Dict:
        """
        Get risk adjustment based on upcoming USD news (US30-specific)
        
        Returns:
            {
                'risk_multiplier': float (0.0 - 1.0),
                'max_positions': int,
                'reason': str
            }
        """
        # Check for upcoming high-impact USD events
        warning = self.is_high_impact_event_soon(minutes_before=60)
        
        if warning['warning']:
            minutes = warning['minutes_until']
            
            if minutes <= 15:
                # Very close - stop trading
                return {
                    'risk_multiplier': 0.0,
                    'max_positions': 0,
                    'reason': f"High-impact event in {minutes} min: {warning['event']['event']}"
                }
            elif minutes <= 30:
                # Close - reduce risk significantly
                return {
                    'risk_multiplier': 0.3,
                    'max_positions': 1,
                    'reason': f"High-impact event in {minutes} min: {warning['event']['event']}"
                }
            elif minutes <= 60:
                # Approaching - reduce risk moderately
                return {
                    'risk_multiplier': 0.6,
                    'max_positions': 1,
                    'reason': f"High-impact event in {minutes} min: {warning['event']['event']}"
                }
        
        # No nearby events - normal trading
        return {
            'risk_multiplier': 1.0,
            'max_positions': 2,
            'reason': 'No high-impact events nearby'
        }
    
    def get_post_news_opportunity(self) -> Dict:
        """
        Check if there's a post-USD-news trading opportunity (US30-specific)
        
        High volatility after USD news = good US30 scalping opportunity
        
        Returns:
            {
                'opportunity': bool,
                'event': dict or None,
                'minutes_since': int,
                'recommendation': str
            }
        """
        events = self.fetch_events()
        now = datetime.now()
        
        for event in events:
            # US30 FILTER: Only USD events matter!
            if event['currency'] not in self.relevant_currencies:
                continue
            
            if event['impact'] != 'high':
                continue
            
            # Check if high-impact event
            is_high_impact = any(
                keyword.lower() in event['event'].lower()
                for keyword in self.high_impact_keywords
            )
            
            if not is_high_impact:
                continue
            
            # Calculate time since event
            time_since = (now - event['time']).total_seconds() / 60
            
            # Sweet spot: 15-60 minutes after news
            # Volatility settled, trend established
            if 15 <= time_since <= 60:
                return {
                    'opportunity': True,
                    'event': event,
                    'minutes_since': int(time_since),
                    'recommendation': f"Post-news volatility opportunity: {event['event']}"
                }
        
        return {
            'opportunity': False,
            'event': None,
            'minutes_since': None,
            'recommendation': 'No post-news opportunities'
        }
    
    def get_calendar_summary(self) -> str:
        """Get human-readable summary of today's events"""
        events = self.fetch_events(days_ahead=1)
        
        if not events:
            return "No economic events today"
        
        high_impact = [e for e in events if e['impact'] == 'high']
        medium_impact = [e for e in events if e['impact'] == 'medium']
        
        summary = f"Today's Events: {len(events)} total\n"
        summary += f"  High-impact: {len(high_impact)}\n"
        summary += f"  Medium-impact: {len(medium_impact)}\n"
        
        if high_impact:
            summary += "\nHigh-Impact Events:\n"
            for event in high_impact[:3]:  # Show first 3
                time_str = event['time'].strftime('%H:%M')
                summary += f"  {time_str} - {event['event']} ({event['currency']})\n"
        
        return summary
