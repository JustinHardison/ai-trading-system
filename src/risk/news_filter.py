"""
News Event Filter
Prevents trading during high-impact economic news events

Uses REAL data from Forex Factory API (faireconomy.media)
NO FAKE/HARDCODED DATA - All events are fetched from live API
"""
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import calendar
import requests
import json
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache file for API data
NEWS_CACHE_FILE = Path("cache/forex_factory_events.json")
NEWS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class NewsEvent:
    """High-impact news event"""
    name: str
    impact: str  # HIGH, MEDIUM
    currency: str  # USD, EUR, GBP, etc.
    scheduled_time: datetime
    description: str


@dataclass
class NewsFilterStatus:
    """News filter assessment"""
    is_safe: bool
    reason: str
    upcoming_events: List[NewsEvent]
    minutes_to_next_event: Optional[float]


class NewsEventFilter:
    """
    Filters out high-impact news events

    High-impact events that cause unpredictable volatility:
    - Non-Farm Payrolls (NFP) - First Friday, 8:30 AM EST
    - Federal Reserve (FOMC) - 8 times/year, 2:00 PM EST
    - GDP Releases - Quarterly, 8:30 AM EST
    - CPI (Inflation) - Monthly, 8:30 AM EST
    - Interest Rate Decisions (Fed, ECB, BOE, etc.)
    - Employment Data (ADP, Jobless Claims)

    Strategy:
    - Don't open new positions 30 min before event
    - Don't open new positions 30 min after event
    - Close risky positions before event (optional)
    """

    # High-impact recurring events
    HIGH_IMPACT_SCHEDULE = {
        "NFP": {
            "description": "Non-Farm Payrolls",
            "frequency": "first_friday",
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 30
        },
        "FOMC": {
            "description": "Federal Reserve Meeting",
            "frequency": "8_times_year",  # Manually scheduled
            "time": "14:00",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 60  # 1 hour before/after
        },
        "CPI": {
            "description": "Consumer Price Index (Inflation)",
            "frequency": "monthly_mid",  # ~15th of month
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 30
        },
        "GDP": {
            "description": "GDP Report",
            "frequency": "quarterly",  # End of quarter
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 30
        },
        "ECB_RATE": {
            "description": "ECB Interest Rate Decision",
            "frequency": "8_times_year",
            "time": "07:45",  # 13:45 CET = 7:45 EST
            "timezone": "EST",
            "currency": "EUR",
            "avoid_minutes": 60
        },
        "BOE_RATE": {
            "description": "Bank of England Rate Decision",
            "frequency": "8_times_year",
            "time": "07:00",  # 12:00 GMT = 7:00 EST
            "timezone": "EST",
            "currency": "GBP",
            "avoid_minutes": 60
        },
        "PPI": {
            "description": "Producer Price Index (Wholesale Inflation)",
            "frequency": "monthly_mid",  # ~12th-15th of month
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 30
        },
        "RETAIL_SALES": {
            "description": "Retail Sales Report",
            "frequency": "monthly_mid",  # ~15th of month
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 30
        },
        "JOBLESS_CLAIMS": {
            "description": "Initial Jobless Claims",
            "frequency": "weekly_thursday",
            "time": "08:30",
            "timezone": "EST",
            "currency": "USD",
            "avoid_minutes": 15  # Less impact than NFP/CPI
        }
    }

    # 2025 FOMC Meeting Dates (update these)
    FOMC_DATES_2025 = [
        "2025-01-29", "2025-03-19", "2025-04-30",
        "2025-06-18", "2025-07-30", "2025-09-17",
        "2025-10-29", "2025-12-17"
    ]

    # 2025 ECB Meeting Dates
    ECB_DATES_2025 = [
        "2025-01-30", "2025-03-13", "2025-04-17",
        "2025-06-12", "2025-07-24", "2025-09-11",
        "2025-10-30", "2025-12-18"
    ]

    # 2025 BOE Meeting Dates
    BOE_DATES_2025 = [
        "2025-02-06", "2025-03-20", "2025-05-08",
        "2025-06-19", "2025-08-07", "2025-09-18",
        "2025-11-06", "2025-12-18"
    ]

    def __init__(
        self,
        avoid_minutes_before: int = 30,
        avoid_minutes_after: int = 30
    ):
        """
        Args:
            avoid_minutes_before: Minutes before event to stop trading
            avoid_minutes_after: Minutes after event to stop trading
        """
        self.avoid_minutes_before = avoid_minutes_before
        self.avoid_minutes_after = avoid_minutes_after
        self.cached_events = []
        self.cache_expiry = None
        
        # Fetch real events on init
        self._refresh_forex_factory_events()
    
    def _refresh_forex_factory_events(self):
        """
        Fetch REAL economic calendar data from Forex Factory API
        This is the ONLY source of truth - NO hardcoded fake data
        """
        # Check cache first
        if self.cache_expiry and datetime.now() < self.cache_expiry and self.cached_events:
            logger.debug(f"Using cached events ({len(self.cached_events)} events)")
            return
        
        try:
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            for item in data:
                impact = item.get('impact', 'Low')
                if impact not in ['High', 'Medium', 'Low']:
                    impact = 'Medium'
                
                # Parse date - format: "2025-12-19T08:30:00-05:00"
                date_str = item.get('date', '')
                try:
                    # Handle timezone in date string
                    if '+' in date_str or date_str.count('-') > 2:
                        # Has timezone, parse without it for simplicity
                        date_str_clean = date_str[:19]  # "2025-12-19T08:30:00"
                        scheduled_time = datetime.strptime(date_str_clean, "%Y-%m-%dT%H:%M:%S")
                    else:
                        scheduled_time = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                except:
                    continue
                
                events.append(NewsEvent(
                    name=item.get('title', ''),
                    impact=impact.upper(),
                    currency=item.get('country', ''),
                    scheduled_time=scheduled_time,
                    description=f"{item.get('title', '')} - Forecast: {item.get('forecast', 'N/A')}, Previous: {item.get('previous', 'N/A')}"
                ))
            
            self.cached_events = events
            self.cache_expiry = datetime.now() + timedelta(hours=6)  # Cache for 6 hours
            
            # Save to file cache
            try:
                cache_data = [
                    {
                        'name': e.name,
                        'impact': e.impact,
                        'currency': e.currency,
                        'scheduled_time': e.scheduled_time.isoformat(),
                        'description': e.description
                    }
                    for e in events
                ]
                with open(NEWS_CACHE_FILE, 'w') as f:
                    json.dump({'events': cache_data, 'expiry': self.cache_expiry.isoformat()}, f)
            except Exception as e:
                logger.debug(f"Could not save cache: {e}")
            
            # Log high-impact events for our symbols
            high_impact_usd = [e for e in events if e.impact == 'HIGH' and e.currency == 'USD']
            logger.info(f"✓ Forex Factory API: {len(events)} events, {len(high_impact_usd)} high-impact USD")
            
        except Exception as e:
            logger.warning(f"Could not fetch Forex Factory API: {e}")
            # Try to load from file cache
            self._load_from_file_cache()
    
    def _load_from_file_cache(self):
        """Load events from file cache if API fails"""
        try:
            if NEWS_CACHE_FILE.exists():
                with open(NEWS_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                
                events = []
                for item in data.get('events', []):
                    events.append(NewsEvent(
                        name=item['name'],
                        impact=item['impact'],
                        currency=item['currency'],
                        scheduled_time=datetime.fromisoformat(item['scheduled_time']),
                        description=item['description']
                    ))
                
                self.cached_events = events
                expiry_str = data.get('expiry')
                if expiry_str:
                    self.cache_expiry = datetime.fromisoformat(expiry_str)
                
                logger.info(f"✓ Loaded {len(events)} events from file cache")
        except Exception as e:
            logger.error(f"Could not load file cache: {e}")
            self.cached_events = []

    def is_safe_to_trade(
        self,
        current_time: datetime = None,
        symbols: List[str] = None
    ) -> NewsFilterStatus:
        """
        Check if it's safe to open new positions

        Args:
            current_time: Current time (default: now)
            symbols: Symbols being traded (to check currency relevance)

        Returns:
            NewsFilterStatus with safety assessment
        """
        if current_time is None:
            current_time = datetime.now()

        # Get upcoming events
        upcoming = self._get_upcoming_events(current_time)

        # Check if any event is too close
        for event in upcoming:
            minutes_away = (event.scheduled_time - current_time).total_seconds() / 60

            # Check if in danger zone
            if -self.avoid_minutes_after <= minutes_away <= self.avoid_minutes_before:
                # Check if this event affects our symbols
                if symbols and not self._affects_symbols(event, symbols):
                    continue

                return NewsFilterStatus(
                    is_safe=False,
                    reason=f"🚨 {event.name} in {abs(minutes_away):.0f} min - NO TRADING",
                    upcoming_events=upcoming[:3],
                    minutes_to_next_event=minutes_away
                )

        # All clear
        next_minutes = (upcoming[0].scheduled_time - current_time).total_seconds() / 60 if upcoming else None

        return NewsFilterStatus(
            is_safe=True,
            reason=f"✅ Clear to trade. Next event: {upcoming[0].name if upcoming else 'None'} in {next_minutes:.0f}min" if upcoming else "✅ No major news today",
            upcoming_events=upcoming[:3],
            minutes_to_next_event=next_minutes
        )

    def _get_upcoming_events(
        self,
        current_time: datetime,
        lookahead_hours: int = 24
    ) -> List[NewsEvent]:
        """
        Get upcoming high-impact events from REAL Forex Factory data
        
        Only returns HIGH impact events that affect our trading symbols:
        - USD events affect: US30, US100, US500, XAU (gold priced in USD)
        - We filter to only USD events since those are our instruments

        Args:
            current_time: Current time
            lookahead_hours: Hours to look ahead

        Returns:
            List of NewsEvent sorted by time
        """
        # Refresh if cache expired
        if not self.cached_events or (self.cache_expiry and datetime.now() >= self.cache_expiry):
            self._refresh_forex_factory_events()
        
        # Filter to upcoming HIGH impact USD events only
        # Our symbols: XAU, US30, US100, US500 - all affected by USD news
        cutoff = current_time + timedelta(hours=lookahead_hours)
        
        upcoming = [
            event for event in self.cached_events
            if event.impact == 'HIGH'
            and event.currency == 'USD'  # Only USD affects our symbols
            and current_time <= event.scheduled_time <= cutoff
        ]
        
        # Sort by time
        upcoming.sort(key=lambda e: e.scheduled_time)
        
        return upcoming

    def _get_first_friday(self, year: int, month: int) -> Optional[datetime]:
        """Get first Friday of the month"""
        for day in range(1, 8):
            date = datetime(year, month, day)
            if date.weekday() == 4:  # Friday
                return date
        return None

    def _affects_symbols(self, event: NewsEvent, symbols: List[str]) -> bool:
        """
        Check if news event affects any of the symbols

        Args:
            event: News event
            symbols: List of symbols (e.g., ['EURUSD', 'GBPJPY', 'US30', 'XAU'])

        Returns:
            True if event currency is in any symbol
        """
        event_curr = event.currency

        # US indices and gold are heavily affected by USD news (NFP, CPI, PPI, FOMC)
        USD_AFFECTED_SYMBOLS = ['US30', 'US100', 'US500', 'XAU', 'GOLD', 'USOIL', 'OIL']

        for symbol in symbols:
            symbol_upper = symbol.upper()
            
            # Direct currency match (e.g., USD in EURUSD)
            if event_curr in symbol_upper:
                return True
            
            # USD news affects indices, gold, and oil
            if event_curr == 'USD':
                for affected in USD_AFFECTED_SYMBOLS:
                    if affected in symbol_upper:
                        return True

        return False

    def should_close_positions(
        self,
        current_time: datetime = None,
        open_positions: List[Dict] = None
    ) -> Tuple[bool, str, List[str]]:
        """
        Check if should close positions before major news

        Args:
            current_time: Current time
            open_positions: Open positions with 'symbol' key

        Returns:
            (should_close, reason, symbols_to_close)
        """
        if current_time is None:
            current_time = datetime.now()

        if not open_positions:
            return False, "No positions open", []

        symbols = [pos.get('symbol', '') for pos in open_positions]
        upcoming = self._get_upcoming_events(current_time, lookahead_hours=1)

        for event in upcoming:
            minutes_away = (event.scheduled_time - current_time).total_seconds() / 60

            # If major event in next 15 minutes
            if 0 <= minutes_away <= 15:
                affected = [s for s in symbols if event.currency in s]
                if affected:
                    return True, f"{event.name} in {minutes_away:.0f} min - close {event.currency} positions", affected

        return False, "No imminent high-impact news", []
