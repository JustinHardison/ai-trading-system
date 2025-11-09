"""
Async Data Fetcher for Speed Optimization
==========================================

Fetches external data in parallel:
- Multi-asset data (Yahoo Finance)
- Sentiment data (Reddit, VIX)

Instead of sequential (854ms + 500ms = 1354ms),
runs in parallel (max(854ms, 500ms) = 854ms)

Saves ~500ms per request!

Author: AI Trading System
Created: 2025-01-13
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Any, Callable
from loguru import logger


class AsyncFetcher:
    """
    Async data fetcher for external APIs.

    Uses ThreadPoolExecutor to run blocking I/O in parallel.
    """

    def __init__(self, max_workers: int = 5):
        """
        Initialize async fetcher.

        Args:
            max_workers: Max parallel threads
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"✓ AsyncFetcher initialized ({max_workers} workers)")

    def fetch_parallel(
        self,
        tasks: Dict[str, Callable[[], Any]]
    ) -> Dict[str, Any]:
        """
        Fetch multiple data sources in parallel.

        Args:
            tasks: Dict of {name: fetch_function}

        Returns:
            Dict of {name: result}

        Example:
            results = fetcher.fetch_parallel({
                'multi_asset': lambda: multi_asset.get_features_dict(),
                'sentiment': lambda: sentiment.get_features_dict(),
            })
        """
        start_time = time.time()

        # Submit all tasks
        futures = {}
        for name, fetch_fn in tasks.items():
            future = self.executor.submit(fetch_fn)
            futures[name] = future

        # Wait for all to complete
        results = {}
        errors = {}

        for name, future in futures.items():
            try:
                result = future.result(timeout=5.0)  # 5 second timeout
                results[name] = result
            except Exception as e:
                logger.error(f"Failed to fetch {name}: {e}")
                errors[name] = str(e)
                results[name] = None

        elapsed_ms = (time.time() - start_time) * 1000

        if errors:
            logger.warning(f"⚡ Parallel fetch: {len(results)} tasks, {len(errors)} errors, {elapsed_ms:.0f}ms")
        else:
            logger.info(f"⚡ Parallel fetch: {len(results)} tasks in {elapsed_ms:.0f}ms")

        return results

    def shutdown(self):
        """Shutdown executor gracefully."""
        self.executor.shutdown(wait=True)
        logger.info("AsyncFetcher shutdown")


# Test function
def test_async_fetcher():
    """Test async fetcher."""
    print("═══════════════════════════════════════════════════════════════════")
    print("⚡ ASYNC FETCHER TEST")
    print("═══════════════════════════════════════════════════════════════════\n")

    fetcher = AsyncFetcher(max_workers=3)

    # Simulate slow API calls
    def slow_task_1():
        print("   Task 1: Starting (500ms)...")
        time.sleep(0.5)
        print("   Task 1: Done!")
        return {'result': 'task1'}

    def slow_task_2():
        print("   Task 2: Starting (800ms)...")
        time.sleep(0.8)
        print("   Task 2: Done!")
        return {'result': 'task2'}

    def slow_task_3():
        print("   Task 3: Starting (300ms)...")
        time.sleep(0.3)
        print("   Task 3: Done!")
        return {'result': 'task3'}

    # Sequential would take: 500 + 800 + 300 = 1600ms
    # Parallel should take: max(500, 800, 300) = 800ms

    print("1. PARALLEL EXECUTION TEST:")
    print("   Sequential time: 500 + 800 + 300 = 1600ms")
    print("   Expected parallel time: max(500, 800, 300) = ~800ms\n")

    start = time.time()
    results = fetcher.fetch_parallel({
        'task1': slow_task_1,
        'task2': slow_task_2,
        'task3': slow_task_3,
    })
    elapsed = (time.time() - start) * 1000

    print(f"\n   Actual time: {elapsed:.0f}ms")
    print(f"   Speedup: {1600 / elapsed:.2f}x")
    print(f"   Results: {len(results)} tasks completed")

    # Test error handling
    print("\n2. ERROR HANDLING TEST:")

    def error_task():
        raise ValueError("Simulated error")

    def success_task():
        return {'success': True}

    results = fetcher.fetch_parallel({
        'error': error_task,
        'success': success_task,
    })

    print(f"   Error task result: {results['error']}")
    print(f"   Success task result: {results['success']}")

    fetcher.shutdown()

    print("\n═══════════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    test_async_fetcher()
