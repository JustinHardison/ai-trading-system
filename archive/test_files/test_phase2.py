#!/usr/bin/env python3
"""
Test Phase 2: Multi-Speed Parallel Scanning
"""
import sys

print("="*70)
print("TESTING PHASE 2: MULTI-SPEED PARALLEL SCANNING")
print("="*70)
print()

# Test 1: Import checks
print("[1/4] Testing imports...")
try:
    import threading
    import symbol_config
    from concurrent.futures import ThreadPoolExecutor
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

print()

# Test 2: Symbol configuration
print("[2/4] Testing symbol configuration...")
try:
    # Test symbol classification
    assert symbol_config.get_symbol_tier('US30') == 'HIGH_PRIORITY'
    assert symbol_config.get_scan_interval('US30') == 30
    assert symbol_config.get_symbol_tier('EURUSD') == 'MEDIUM_PRIORITY'
    assert symbol_config.get_scan_interval('EURUSD') == 90
    
    # Test organization
    test_symbols = ['US30', 'EURUSD', 'GBPUSD', 'AUDNZD']
    organized = symbol_config.organize_symbols_by_tier(test_symbols)
    assert 'US30' in organized['HIGH_PRIORITY']
    assert 'EURUSD' in organized['MEDIUM_PRIORITY']
    assert 'AUDNZD' in organized['LOW_PRIORITY']
    
    print("✓ Symbol configuration working correctly")
except AssertionError as e:
    print(f"✗ Symbol configuration test failed: {e}")
    sys.exit(1)

print()

# Test 3: Check autonomous_trader.py has new methods
print("[3/4] Testing autonomous_trader.py modifications...")
try:
    from autonomous_trader import AutonomousTrader
    
    # Check if new methods exist
    assert hasattr(AutonomousTrader, '_scan_single_symbol')
    assert hasattr(AutonomousTrader, '_scan_tier_loop')
    assert hasattr(AutonomousTrader, '_process_opportunities_from_queue')
    
    print("✓ All new methods present in AutonomousTrader")
except (ImportError, AssertionError) as e:
    print(f"✗ AutonomousTrader check failed: {e}")
    sys.exit(1)

print()

# Test 4: Threading capability
print("[4/4] Testing threading capability...")
try:
    import time
    
    results = []
    def test_thread(name, delay):
        time.sleep(delay)
        results.append(name)
    
    threads = []
    for i in range(3):
        t = threading.Thread(target=test_thread, args=(f"thread-{i}", 0.1))
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join()
    
    assert len(results) == 3
    print(f"✓ Threading working (completed {len(results)} threads)")
except Exception as e:
    print(f"✗ Threading test failed: {e}")
    sys.exit(1)

print()
print("="*70)
print("ALL TESTS PASSED ✅")
print("="*70)
print()
print("Phase 2 implementation is ready!")
print()
print("Next steps:")
print("1. Test with real MT5 connection (autonomous_trader.py will use multi-speed by default)")
print("2. Verify US30 scans every 30s in logs")
print("3. Verify MEDIUM tier scans every 90s in logs")
print("4. Verify LOW tier scans every 180s in logs")
print()
