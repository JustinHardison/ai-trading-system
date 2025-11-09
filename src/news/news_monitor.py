"""
News and Economic Calendar Monitoring
Prevents trading during high-impact news events
"""
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)


class NewsEvent:
    """Economic calendar event"""

    def __init__(self, data: Dict):
        self.title = data.get('title', '')
        self.country = data.get('country', '')
        self.date = data.get('date', '')
        self.impact = data.get('impact', 'medium')  # low, medium, high
        self.forecast = data.get('forecast', '')
        self.previous = data.get('previous', '')

    def __repr__(self):
        return f"NewsEvent({self.title}, {self.impact}, {self.date})"


class NewsMonitor:
    """
    Monitors economic calendar and prevents trading during high-impact events

    Uses free APIs:
    - Trading Economics API (free tier)
    - Forex Factory scraping (backup)
    - Economic Calendar API

    High-impact events to avoid:
    - Fed interest rate decisions
    - NFP (Non-Farm Payrolls)
    - CPI (Inflation)
    - GDP releases
    - FOMC statements
    - Unemployment data
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.cached_events = []
        self.cache_expiry = None
        self.cache_file = Path("cache/news_events.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Load cached events
        self._load_cache()

    def is_trading_safe(self, minutes_buffer: int = 30) -> tuple[bool, Optional[str]]:
        """
        Check if it's safe to trade (no high-impact news within buffer)

        Args:
            minutes_buffer: Minutes before/after news to avoid trading

        Returns:
            (is_safe, reason)
        """
        now = datetime.now()

        # Refresh events if cache expired
        if not self.cached_events or not self.cache_expiry or now > self.cache_expiry:
            self._refresh_events()

        # Check upcoming events
        upcoming_events = [
            e for e in self.cached_events
            if e.impact == 'high'
        ]

        for event in upcoming_events:
            try:
                event_time = datetime.fromisoformat(event.date)

                # Check if event is within buffer
                time_diff = (event_time - now).total_seconds() / 60  # minutes

                if -minutes_buffer <= time_diff <= minutes_buffer:
                    reason = f"HIGH IMPACT: {event.title} in {int(time_diff)} minutes"
                    logger.warning(f"Trading NOT SAFE: {reason}")
                    return False, reason

            except Exception as e:
                logger.error(f"Error parsing event time: {e}")
                continue

        logger.info("Trading SAFE: No high-impact news within buffer")
        return True, None

    def _refresh_events(self):
        """Refresh economic calendar events"""
        logger.info("Refreshing economic calendar...")

        # Try multiple sources
        events = []

        # Source 1: Free Forex Factory API (best source - real data)
        ff_events = self._fetch_forex_factory_api()
        if ff_events:
            events.extend(ff_events)
            logger.info(f"✓ Fetched {len(ff_events)} events from Forex Factory API")
        else:
            # Fallback: Trading Economics (if API key provided)
            if self.api_key:
                events.extend(self._fetch_trading_economics())
            # Fallback: Hardcoded major events
            events.extend(self._get_known_major_events())

        self.cached_events = events
        self.cache_expiry = datetime.now() + timedelta(hours=6)  # Refresh every 6 hours to avoid rate limits

        # Save to cache
        self._save_cache()

        logger.info(f"Cached {len(events)} economic events")

    def _fetch_trading_economics(self) -> List[NewsEvent]:
        """Fetch from Trading Economics API"""
        try:
            url = "https://api.tradingeconomics.com/calendar"
            params = {
                'c': self.api_key,
                'country': 'united states',
                'importance': '3',  # High importance only
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            events = []
            for item in data:
                events.append(NewsEvent({
                    'title': item.get('Event', ''),
                    'country': item.get('Country', ''),
                    'date': item.get('Date', ''),
                    'impact': 'high',
                    'forecast': item.get('Forecast', ''),
                    'previous': item.get('Previous', '')
                }))

            logger.info(f"Fetched {len(events)} events from Trading Economics")
            return events

        except Exception as e:
            logger.error(f"Error fetching from Trading Economics: {e}")
            return []

    def _fetch_forex_factory_api(self) -> List[NewsEvent]:
        """
        Fetch from free Forex Factory API (faireconomy.media)
        This provides REAL economic calendar data matching FTMO MetriX
        """
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            for item in data:
                # Map impact levels
                impact = item.get('impact', 'Low').lower()
                if impact not in ['low', 'medium', 'high']:
                    impact = 'medium'
                
                # Parse date - format: "2025-12-19T08:30:00-05:00"
                date_str = item.get('date', '')
                
                events.append(NewsEvent({
                    'title': item.get('title', ''),
                    'country': item.get('country', ''),
                    'date': date_str,
                    'impact': impact,
                    'forecast': item.get('forecast', ''),
                    'previous': item.get('previous', '')
                }))
            
            # Filter to relevant currencies for our instruments
            # USD for US indices, XAU affected by USD events
            relevant_currencies = ['USD', 'EUR', 'GBP', 'JPY']
            high_impact = [e for e in events if e.impact == 'high' and e.country in relevant_currencies]
            
            logger.info(f"Forex Factory API: {len(events)} total, {len(high_impact)} high-impact USD/EUR/GBP/JPY")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching Forex Factory API: {e}")
            return []
    
    def _fetch_forex_factory(self) -> List[NewsEvent]:
        """
        Legacy fallback - uses hardcoded recurring events
        Only used if API fails
        """
        events = []
        now = datetime.now()

        # NFP: First Friday of each month at 8:30 AM ET
        first_day = datetime(now.year, now.month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
        if first_friday < now:
            if now.month == 12:
                first_day = datetime(now.year + 1, 1, 1)
            else:
                first_day = datetime(now.year, now.month + 1, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)

        nfp_time = first_friday.replace(hour=8, minute=30)

        events.append(NewsEvent({
            'title': 'Non-Farm Payrolls (NFP)',
            'country': 'USD',
            'date': nfp_time.isoformat(),
            'impact': 'high',
            'forecast': '',
            'previous': ''
        }))

        logger.info(f"Generated {len(events)} recurring high-impact events (fallback)")
        return events

    def _get_known_major_events(self) -> List[NewsEvent]:
        """
        Hardcoded major events (failsafe)

        These are known fixed events that should always be avoided
        """
        now = datetime.now()
        year = now.year

        # FOMC meetings 2025 (8 per year)
        fomc_dates = [
            datetime(year, 1, 29, 14, 0),  # Jan 28-29
            datetime(year, 3, 19, 14, 0),  # Mar 18-19
            datetime(year, 5, 7, 14, 0),   # May 6-7
            datetime(year, 6, 18, 14, 0),  # Jun 17-18
            datetime(year, 7, 30, 14, 0),  # Jul 29-30
            datetime(year, 9, 17, 14, 0),  # Sep 16-17
            datetime(year, 11, 5, 14, 0),  # Nov 4-5
            datetime(year, 12, 17, 14, 0), # Dec 16-17
        ]

        events = []

        for date in fomc_dates:
            if date > now:  # Only future events
                events.append(NewsEvent({
                    'title': 'FOMC Meeting Decision',
                    'country': 'USD',
                    'date': date.isoformat(),
                    'impact': 'high',
                    'forecast': '',
                    'previous': ''
                }))

        return events

    def _save_cache(self):
        """Save events to cache file"""
        try:
            cache_data = {
                'events': [
                    {
                        'title': e.title,
                        'country': e.country,
                        'date': e.date,
                        'impact': e.impact,
                        'forecast': e.forecast,
                        'previous': e.previous
                    }
                    for e in self.cached_events
                ],
                'expiry': self.cache_expiry.isoformat() if self.cache_expiry else None
            }

            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving news cache: {e}")

    def _load_cache(self):
        """Load events from cache file"""
        try:
            if not self.cache_file.exists():
                return

            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)

            if cache_data.get('expiry'):
                self.cache_expiry = datetime.fromisoformat(cache_data['expiry'])

                # Check if cache is still valid
                if self.cache_expiry > datetime.now():
                    self.cached_events = [
                        NewsEvent(e) for e in cache_data.get('events', [])
                    ]
                    logger.info(f"Loaded {len(self.cached_events)} events from cache")

        except Exception as e:
            logger.error(f"Error loading news cache: {e}")

    def get_upcoming_events(self, hours: int = 24) -> List[NewsEvent]:
        """Get high-impact events in next N hours"""
        now = datetime.now()
        cutoff = now + timedelta(hours=hours)

        upcoming = []
        for event in self.cached_events:
            if event.impact != 'high':
                continue

            try:
                event_time = datetime.fromisoformat(event.date)
                if now < event_time < cutoff:
                    upcoming.append(event)
            except:
                continue

        return sorted(upcoming, key=lambda e: e.date)
