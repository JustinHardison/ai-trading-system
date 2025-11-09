"""
Feature Caching System for Speed Optimization
==============================================

Caches features that don't change frequently:
- Time-based features (only change once per hour/day)
- Multi-asset data (cache for 1 minute)
- Sentiment data (cache for 15 minutes)
- Regime features (cache for 5 minutes)

Author: AI Trading System
Created: 2025-01-13
"""

import time
from typing import Dict, Optional, Any, Callable
from loguru import logger
import threading


class FeatureCache:
    """
    Thread-safe feature caching system.

    Reduces computation time by caching expensive features:
    - Time features: 1 hour cache
    - Multi-asset: 1 minute cache (already cached in module)
    - Sentiment: 15 minutes cache (already cached in module)
    - Regime: 5 minutes cache (expensive ADX calculations)
    """

    def __init__(self):
        """Initialize cache with thread safety."""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        logger.info("✓ FeatureCache initialized (thread-safe)")

    def get(self, key: str, ttl_seconds: int = 60) -> Optional[Any]:
        """
        Get cached value if still valid.

        Args:
            key: Cache key
            ttl_seconds: Time to live in seconds

        Returns:
            Cached value or None if expired/missing
        """
        with self._lock:
            if key not in self._cache:
                return None

            cache_entry = self._cache[key]
            age = time.time() - cache_entry['timestamp']

            if age > ttl_seconds:
                # Expired
                del self._cache[key]
                return None

            return cache_entry['value']

    def set(self, key: str, value: Any) -> None:
        """
        Set cache value with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': time.time()
            }

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl_seconds: int = 60
    ) -> Any:
        """
        Get cached value or compute and cache it.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl_seconds: Time to live in seconds

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        cached = self.get(key, ttl_seconds)
        if cached is not None:
            return cached

        # Compute and cache
        value = compute_fn()
        self.set(key, value)
        return value

    def invalidate(self, key: str) -> None:
        """
        Invalidate (delete) a cache entry.

        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats
        """
        with self._lock:
            total_entries = len(self._cache)

            # Calculate ages
            current_time = time.time()
            ages = []
            for entry in self._cache.values():
                age = current_time - entry['timestamp']
                ages.append(age)

            return {
                'total_entries': total_entries,
                'avg_age_seconds': sum(ages) / len(ages) if ages else 0,
                'oldest_age_seconds': max(ages) if ages else 0,
            }


# Global cache instance
_global_cache: Optional[FeatureCache] = None


def get_cache() -> FeatureCache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = FeatureCache()
    return _global_cache


# Test function
def test_cache():
    """Test cache functionality."""
    print("═══════════════════════════════════════════════════════════════════")
    print("🧪 FEATURE CACHE TEST")
    print("═══════════════════════════════════════════════════════════════════\n")

    cache = FeatureCache()

    # Test 1: Set and get
    print("1. SET AND GET:")
    cache.set('test_key', {'value': 123})
    result = cache.get('test_key', ttl_seconds=60)
    print(f"   Set value: {{'value': 123}}")
    print(f"   Got value: {result}")
    print(f"   Match: {result == {'value': 123}}")

    # Test 2: Expiration
    print("\n2. EXPIRATION TEST:")
    cache.set('expire_test', 'should_expire')
    time.sleep(0.1)
    result = cache.get('expire_test', ttl_seconds=0.05)  # 50ms TTL
    print(f"   After 100ms with 50ms TTL: {result}")
    print(f"   Expired: {result is None}")

    # Test 3: Get or compute
    print("\n3. GET OR COMPUTE:")
    compute_count = 0

    def expensive_computation():
        nonlocal compute_count
        compute_count += 1
        print(f"   Computing... (call #{compute_count})")
        return {'computed': True}

    # First call - should compute
    result1 = cache.get_or_compute('computed_key', expensive_computation, ttl_seconds=60)
    print(f"   First call result: {result1}")

    # Second call - should use cache
    result2 = cache.get_or_compute('computed_key', expensive_computation, ttl_seconds=60)
    print(f"   Second call result: {result2}")
    print(f"   Compute count: {compute_count} (should be 1)")

    # Test 4: Stats
    print("\n4. CACHE STATS:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # Test 5: Clear
    print("\n5. CLEAR:")
    cache.clear()
    stats = cache.get_stats()
    print(f"   Entries after clear: {stats['total_entries']}")

    print("\n═══════════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    test_cache()
