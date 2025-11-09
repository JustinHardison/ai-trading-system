"""
Symbol Priority Configuration for Multi-Speed Scanning

This module defines symbol tiers for optimized scanning based on volatility
and trading characteristics. Fast-moving symbols get more frequent scans.
"""

# Symbol priority tiers for multi-speed scanning
# US30-ONLY MODE: Maximum focus on Dow Jones for FTMO consistency
SYMBOL_TIERS = {
    'HIGH_PRIORITY': {
        'symbols': [
            'US30Z25.sim',      # Dow Jones - ONLY instrument (focused strategy)
        ],
        'scan_interval': 60,  # 60 seconds - Aggressive scanning for opportunities
        'fast_track_threshold': None,  # DISABLED - Always use full LLM analysis
        'description': 'US30 ONLY - Maximum focus for FTMO pass rate'
    },
    'MEDIUM_PRIORITY': {
        'symbols': [],  # DISABLED in US30-only mode
        'scan_interval': 120,
        'fast_track_threshold': None,
        'description': 'Disabled in US30-only mode'
    },
    'LOW_PRIORITY': {
        'symbols': [],  # DISABLED in US30-only mode
        'scan_interval': 180,
        'fast_track_threshold': None,
        'description': 'Disabled in US30-only mode'
    }
}

def get_symbol_tier(symbol: str) -> str:
    """
    Get the priority tier for a given symbol.

    Args:
        symbol: Trading symbol (e.g., 'EURUSD', 'US30')

    Returns:
        Tier name: 'HIGH_PRIORITY', 'MEDIUM_PRIORITY', or 'LOW_PRIORITY'
    """
    for tier_name, tier_config in SYMBOL_TIERS.items():
        if symbol in tier_config['symbols']:
            return tier_name
    return 'LOW_PRIORITY'

def get_scan_interval(symbol: str) -> int:
    """
    Get the recommended scan interval for a symbol.

    Args:
        symbol: Trading symbol

    Returns:
        Scan interval in seconds
    """
    tier = get_symbol_tier(symbol)
    return SYMBOL_TIERS[tier]['scan_interval']

def get_fast_track_threshold(symbol: str) -> float:
    """
    Get the fast-track confidence threshold for a symbol.

    Args:
        symbol: Trading symbol

    Returns:
        Confidence threshold (0-100) or None if fast-track disabled
    """
    tier = get_symbol_tier(symbol)
    return SYMBOL_TIERS[tier]['fast_track_threshold']

def should_fast_track(symbol: str, confidence: float) -> bool:
    """
    Determine if a trade should bypass LLM analysis and execute immediately.

    This is used for high-confidence signals on volatile symbols where speed
    is critical. The AI still made the initial decision via ML model, but we
    skip the LLM risk assessment step for ultra-high confidence trades.

    Args:
        symbol: Trading symbol
        confidence: ML model confidence (0-100)

    Returns:
        True if should execute immediately, False if should use full LLM analysis
    """
    threshold = get_fast_track_threshold(symbol)
    if threshold is None:
        return False
    return confidence >= threshold

def organize_symbols_by_tier(all_symbols: list) -> dict:
    """
    Organize a list of symbols into priority tiers.

    Args:
        all_symbols: List of all available symbols

    Returns:
        Dictionary with tier names as keys and symbol lists as values
    """
    organized = {
        'HIGH_PRIORITY': [],
        'MEDIUM_PRIORITY': [],
        'LOW_PRIORITY': []
    }

    for symbol in all_symbols:
        tier = get_symbol_tier(symbol)
        organized[tier].append(symbol)

    return organized

def get_tier_info(tier_name: str) -> dict:
    """
    Get complete configuration for a priority tier.

    Args:
        tier_name: 'HIGH_PRIORITY', 'MEDIUM_PRIORITY', or 'LOW_PRIORITY'

    Returns:
        Tier configuration dictionary
    """
    return SYMBOL_TIERS.get(tier_name, SYMBOL_TIERS['LOW_PRIORITY'])

# Summary statistics
def print_tier_summary():
    """Print a summary of symbol tier configuration."""
    print("\n" + "="*60)
    print("SYMBOL PRIORITY TIER CONFIGURATION")
    print("="*60)

    for tier_name, config in SYMBOL_TIERS.items():
        print(f"\n{tier_name}:")
        print(f"  Scan Interval: {config['scan_interval']}s")
        print(f"  Fast-Track Threshold: {config['fast_track_threshold'] or 'Disabled'}")
        print(f"  Symbols ({len(config['symbols'])}):")
        if config['symbols']:
            for symbol in config['symbols']:
                print(f"    - {symbol}")
        else:
            print(f"    (All other symbols)")
        print(f"  Description: {config['description']}")

    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    # Test the configuration
    print_tier_summary()

    # Test some symbols
    test_symbols = ['US30', 'EURUSD', 'AUDNZD', 'BTCUSD']
    print("\nTEST SYMBOL CLASSIFICATION:")
    print("-" * 60)
    for symbol in test_symbols:
        tier = get_symbol_tier(symbol)
        interval = get_scan_interval(symbol)
        threshold = get_fast_track_threshold(symbol)
        print(f"{symbol:10} -> {tier:15} (Scan: {interval}s, Fast-Track: {threshold or 'N/A'})")

    # Test fast-track logic
    print("\n\nTEST FAST-TRACK LOGIC:")
    print("-" * 60)
    test_cases = [
        ('US30', 95),   # HIGH tier, 95% confidence -> should fast-track
        ('US30', 85),   # HIGH tier, 85% confidence -> should use LLM
        ('EURUSD', 96), # MEDIUM tier, 96% confidence -> should fast-track
        ('EURUSD', 93), # MEDIUM tier, 93% confidence -> should use LLM
        ('AUDNZD', 98), # LOW tier, 98% confidence -> should use LLM (no fast-track)
    ]

    for symbol, confidence in test_cases:
        result = should_fast_track(symbol, confidence)
        action = "FAST-TRACK ⚡" if result else "Use LLM 🤖"
        print(f"{symbol:10} @ {confidence}% confidence -> {action}")
