"""
Shared lock for MT5 file-based communication

This module provides a single lock that is shared across all components
that communicate with MT5 via ai_command.txt / ai_response.txt files.

This prevents race conditions where multiple threads try to send commands
simultaneously, which would overwrite each other's command files.
"""
import threading
import time

# Global lock shared by all MT5 communication components
_mt5_request_lock = threading.Lock()
_last_request_time = 0
_min_request_interval = 1.5  # Minimum seconds between requests


def acquire_mt5_lock():
    """
    Acquire the MT5 communication lock and enforce minimum request interval.

    This ensures:
    1. Only one thread can send commands at a time
    2. At least 1.5 seconds between consecutive requests
    """
    global _last_request_time

    _mt5_request_lock.acquire()

    # Enforce minimum interval between requests
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)

    _last_request_time = time.time()


def release_mt5_lock():
    """Release the MT5 communication lock."""
    _mt5_request_lock.release()
