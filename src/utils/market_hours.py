"""
Market Hours Detection - US30 Trading Hours
Knows when market is open/closed based on broker time
"""
from datetime import datetime, time, timedelta
from typing import Dict, Optional
import pytz

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MarketHours:
    """
    US30 (Dow Jones) Market Hours Detection
    
    Trading Hours (America/New_York):
    - Sunday: 6:00 PM - 11:59 PM (pre-week)
    - Monday-Thursday: 12:00 AM - 11:59 PM (24 hours)
    - Friday: 12:00 AM - 5:00 PM (closes early)
    - Saturday: CLOSED
    
    Best Trading Sessions:
    - London Open: 3:00 AM - 5:00 AM ET
    - NY Open: 9:30 AM - 11:30 AM ET (BEST!)
    - NY Afternoon: 1:00 PM - 4:00 PM ET
    """
    
    def __init__(self, timezone: str = 'America/New_York'):
        self.timezone = pytz.timezone(timezone)
        
        # US30 trading hours (24/5 market)
        self.sunday_open = time(18, 0)  # 6:00 PM Sunday
        self.friday_close = time(17, 0)  # 5:00 PM Friday
        
        # Best trading sessions
        self.sessions = {
            'asian': {'start': time(0, 0), 'end': time(3, 0)},  # 12 AM - 3 AM
            'london': {'start': time(3, 0), 'end': time(9, 30)},  # 3 AM - 9:30 AM
            'ny_open': {'start': time(9, 30), 'end': time(11, 30)},  # 9:30 AM - 11:30 AM (BEST!)
            'ny_lunch': {'start': time(11, 30), 'end': time(13, 0)},  # 11:30 AM - 1 PM (slow)
            'ny_afternoon': {'start': time(13, 0), 'end': time(17, 0)},  # 1 PM - 5 PM
            'after_hours': {'start': time(17, 0), 'end': time(18, 0)}  # 5 PM - 6 PM (thin)
        }
        
        logger.info("Market Hours initialized")
        logger.info(f"  Timezone: {timezone}")
        logger.info(f"  Trading: Sunday 6PM - Friday 5PM ET")
    
    def get_current_time(self) -> datetime:
        """Get current time in market timezone"""
        return datetime.now(self.timezone)
    
    def is_market_open(self, dt: Optional[datetime] = None) -> Dict:
        """
        Check if US30 market is currently open
        
        Args:
            dt: Datetime to check (defaults to now)
            
        Returns:
            {
                'open': bool,
                'reason': str,
                'next_open': datetime or None,
                'next_close': datetime or None
            }
        """
        if dt is None:
            dt = self.get_current_time()
        
        # Ensure timezone aware
        if dt.tzinfo is None:
            dt = self.timezone.localize(dt)
        else:
            dt = dt.astimezone(self.timezone)
        
        weekday = dt.weekday()  # 0=Monday, 6=Sunday
        current_time = dt.time()
        
        # Saturday - CLOSED
        if weekday == 5:  # Saturday
            # Next open: Sunday 6 PM
            days_until_sunday = 1
            next_open = dt.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
            return {
                'open': False,
                'reason': 'Market closed: Saturday',
                'next_open': next_open,
                'next_close': None,
                'session': 'closed'
            }
        
        # Sunday - Opens at 6 PM
        if weekday == 6:  # Sunday
            if current_time < self.sunday_open:
                next_open = dt.replace(hour=18, minute=0, second=0, microsecond=0)
                return {
                    'open': False,
                    'reason': f'Market closed: Sunday before 6 PM (opens in {(next_open - dt).total_seconds() / 3600:.1f} hours)',
                    'next_open': next_open,
                    'next_close': None,
                    'session': 'closed'
                }
            else:
                # Open Sunday evening
                next_close = (dt + timedelta(days=5)).replace(hour=17, minute=0, second=0, microsecond=0)
                return {
                    'open': True,
                    'reason': 'Market open: Sunday evening',
                    'next_open': None,
                    'next_close': next_close,
                    'session': self._get_current_session(current_time)
                }
        
        # Friday - Closes at 5 PM
        if weekday == 4:  # Friday
            if current_time >= self.friday_close:
                # Closed Friday evening
                days_until_sunday = 2
                next_open = dt.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
                return {
                    'open': False,
                    'reason': 'Market closed: Friday after 5 PM (weekend)',
                    'next_open': next_open,
                    'next_close': None,
                    'session': 'closed'
                }
            else:
                # Open Friday
                next_close = dt.replace(hour=17, minute=0, second=0, microsecond=0)
                return {
                    'open': True,
                    'reason': 'Market open: Friday',
                    'next_open': None,
                    'next_close': next_close,
                    'session': self._get_current_session(current_time)
                }
        
        # Monday-Thursday - Open 24 hours
        if weekday in [0, 1, 2, 3]:  # Monday-Thursday
            next_close = (dt + timedelta(days=(4 - weekday))).replace(hour=17, minute=0, second=0, microsecond=0)
            return {
                'open': True,
                'reason': f'Market open: {["Monday", "Tuesday", "Wednesday", "Thursday"][weekday]}',
                'next_open': None,
                'next_close': next_close,
                'session': self._get_current_session(current_time)
            }
        
        # Fallback
        return {
            'open': False,
            'reason': 'Unknown market state',
            'next_open': None,
            'next_close': None,
            'session': 'unknown'
        }
    
    def _get_current_session(self, current_time: time) -> str:
        """Determine which trading session we're in"""
        for session_name, times in self.sessions.items():
            if times['start'] <= current_time < times['end']:
                return session_name
        return 'unknown'
    
    def get_session_info(self, dt: Optional[datetime] = None) -> Dict:
        """
        Get detailed session information
        
        Returns:
            {
                'session': str,
                'quality': str (excellent/good/fair/poor),
                'volatility': str (high/medium/low),
                'recommendation': str
            }
        """
        if dt is None:
            dt = self.get_current_time()
        
        market_status = self.is_market_open(dt)
        
        if not market_status['open']:
            return {
                'session': 'closed',
                'quality': 'none',
                'volatility': 'none',
                'recommendation': 'Do not trade - market closed'
            }
        
        session = market_status['session']
        
        # Session characteristics
        session_data = {
            'asian': {
                'quality': 'fair',
                'volatility': 'low',
                'recommendation': 'Low liquidity - good for swing trades with high confidence'
            },
            'london': {
                'quality': 'good',
                'volatility': 'medium',
                'recommendation': 'Good for swing trades - European trends developing'
            },
            'ny_open': {
                'quality': 'excellent',
                'volatility': 'high',
                'recommendation': 'BEST for scalping - highest volume and liquidity!'
            },
            'ny_lunch': {
                'quality': 'fair',
                'volatility': 'low',
                'recommendation': 'Reduced activity - prefer swing over scalp'
            },
            'ny_afternoon': {
                'quality': 'good',
                'volatility': 'medium',
                'recommendation': 'Good for both scalping and swing'
            },
            'after_hours': {
                'quality': 'fair',
                'volatility': 'low',
                'recommendation': 'Thin liquidity - good for swing trades with high confidence'
            }
        }
        
        info = session_data.get(session, {
            'quality': 'unknown',
            'volatility': 'unknown',
            'recommendation': 'Unknown session'
        })
        
        info['session'] = session
        return info
    
    def should_trade_now(self, dt: Optional[datetime] = None) -> Dict:
        """
        Get market context for smart trading decisions
        
        Returns context, not hard rules - let ML/RL decide!
        
        Returns:
            {
                'market_open': bool,
                'reason': str,
                'risk_multiplier': float (0.0 - 1.5),
                'session': str,
                'confidence_threshold_adjustment': float,
                'recommendation': str
            }
        """
        market_status = self.is_market_open(dt)
        
        if not market_status['open']:
            return {
                'market_open': False,
                'reason': market_status['reason'],
                'risk_multiplier': 0.0,
                'session': 'closed',
                'confidence_threshold_adjustment': 0.0,
                'recommendation': 'Market closed - no trading possible'
            }
        
        session_info = self.get_session_info(dt)
        session = session_info['session']
        
        # SMART ADJUSTMENTS by session
        # Asian/After-hours: Lower risk, higher threshold (only very confident trades)
        # London: Good for swing trades
        # NY Open: BEST for scalping (high volume, tight spreads)
        # NY Afternoon: Good for both
        
        session_params = {
            'asian': {
                'risk_mult': 0.4,
                'threshold_adj': +15,  # Need 15% more confidence
                'recommendation': 'Low liquidity - only high-confidence swing trades'
            },
            'london': {
                'risk_mult': 0.8,
                'threshold_adj': +5,  # Need 5% more confidence
                'recommendation': 'Good for swing trades - European traders active'
            },
            'ny_open': {
                'risk_mult': 1.5,
                'threshold_adj': -10,  # Can take 10% lower confidence
                'recommendation': 'BEST for scalping - highest volume and liquidity!'
            },
            'ny_lunch': {
                'risk_mult': 0.6,
                'threshold_adj': +10,  # Need 10% more confidence
                'recommendation': 'Reduced activity - prefer swing over scalp'
            },
            'ny_afternoon': {
                'risk_mult': 1.0,
                'threshold_adj': 0,  # Normal
                'recommendation': 'Good for both scalping and swing'
            },
            'after_hours': {
                'risk_mult': 0.4,
                'threshold_adj': +15,  # Need 15% more confidence
                'recommendation': 'Thin liquidity - only high-confidence swing trades'
            }
        }
        
        params = session_params.get(session, {
            'risk_mult': 1.0,
            'threshold_adj': 0,
            'recommendation': 'Normal trading'
        })
        
        return {
            'market_open': True,
            'reason': f'{session.upper()} session - {params["recommendation"]}',
            'risk_multiplier': params['risk_mult'],
            'session': session,
            'confidence_threshold_adjustment': params['threshold_adj'],
            'recommendation': params['recommendation']
        }
    
    def get_market_summary(self) -> str:
        """Get human-readable market status summary"""
        status = self.is_market_open()
        
        if status['open']:
            session_info = self.get_session_info()
            return (
                f"Market: OPEN\n"
                f"Session: {session_info['session'].upper()}\n"
                f"Quality: {session_info['quality'].upper()}\n"
                f"Volatility: {session_info['volatility'].upper()}\n"
                f"Recommendation: {session_info['recommendation']}"
            )
        else:
            next_open = status['next_open']
            if next_open:
                hours_until = (next_open - self.get_current_time()).total_seconds() / 3600
                return (
                    f"Market: CLOSED\n"
                    f"Reason: {status['reason']}\n"
                    f"Opens in: {hours_until:.1f} hours\n"
                    f"Next open: {next_open.strftime('%A %I:%M %p %Z')}"
                )
            else:
                return f"Market: CLOSED\n{status['reason']}"
