"""
Indicator Cache System

Caches technical indicators for frequently scanned symbols to avoid
recalculating all 50 bars on every scan. Updates incrementally.
"""

import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
from src.utils.logger import get_logger

logger = get_logger(__name__)


class IndicatorCache:
    """
    Caches calculated indicators to improve performance.

    Instead of recalculating 50 bars of RSI, ATR, Bollinger Bands, etc.
    on every scan, we:
    1. Calculate once
    2. Store result
    3. Update incrementally with new bars
    """

    def __init__(self, cache_ttl_seconds: int = 300):
        """
        Args:
            cache_ttl_seconds: Time-to-live for cached indicators (default 5 minutes)
        """
        self.cache = {}  # {symbol: {indicator_type: (timestamp, data)}}
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        logger.info(f"Initialized indicator cache (TTL: {cache_ttl_seconds}s)")

    def get(self, symbol: str, indicator_type: str) -> Optional[pd.Series]:
        """
        Get cached indicator if valid.

        Args:
            symbol: Trading symbol
            indicator_type: Type of indicator (e.g., 'rsi', 'atr', 'bbands')

        Returns:
            Cached indicator series or None if cache miss/expired
        """
        if symbol not in self.cache:
            return None

        if indicator_type not in self.cache[symbol]:
            return None

        timestamp, data = self.cache[symbol][indicator_type]

        # Check if cache is still valid
        if datetime.now() - timestamp > self.cache_ttl:
            logger.debug(f"Cache expired for {symbol}/{indicator_type}")
            del self.cache[symbol][indicator_type]
            return None

        logger.debug(f"Cache hit: {symbol}/{indicator_type}")
        return data

    def put(self, symbol: str, indicator_type: str, data: pd.Series):
        """
        Store indicator in cache.

        Args:
            symbol: Trading symbol
            indicator_type: Type of indicator
            data: Indicator data to cache
        """
        if symbol not in self.cache:
            self.cache[symbol] = {}

        self.cache[symbol][indicator_type] = (datetime.now(), data)
        logger.debug(f"Cached: {symbol}/{indicator_type}")

    def invalidate(self, symbol: str):
        """
        Invalidate all cached indicators for a symbol.

        Args:
            symbol: Trading symbol to invalidate
        """
        if symbol in self.cache:
            del self.cache[symbol]
            logger.debug(f"Invalidated cache for {symbol}")

    def clear(self):
        """Clear entire cache"""
        self.cache = {}
        logger.info("Cache cleared")

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        total_entries = sum(len(indicators) for indicators in self.cache.values())

        return {
            'symbols_cached': len(self.cache),
            'total_indicators': total_entries,
            'cache_ttl_seconds': self.cache_ttl.total_seconds()
        }


# Global cache instance
_cache = None

def get_indicator_cache() -> IndicatorCache:
    """Get global indicator cache instance"""
    global _cache
    if _cache is None:
        _cache = IndicatorCache()
    return _cache
