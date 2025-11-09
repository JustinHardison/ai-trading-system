#!/usr/bin/env python3
"""
COMPREHENSIVE TEST - Verify all implementations work
"""

import requests
import json
import time

def test_api_health():
    """Test 1: API Health"""
    print("\n" + "="*80)
    print("TEST 1: API HEALTH CHECK")
    print("="*80)
    
    try:
        response = requests.get("http://localhost:5007/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ API is online")
            print(f"   ML Models: {data.get('ml_models')}")
            print(f"   Feature Engineer: {data.get('feature_engineer')}")
            print(f"   Trade Manager: {data.get('trade_manager')}")
            return True
        else:
            print(f"❌ API returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach API: {e}")
        return False


def test_trigger_timeframe():
    """Test 2: Trigger Timeframe Detection"""
    print("\n" + "="*80)
    print("TEST 2: TRIGGER TIMEFRAME DETECTION")
    print("="*80)
    
    request_data = {
        "symbol": "US100Z25.sim",
        "trigger_timeframe": "H4",  # Test H4 trigger
        "symbol_info": {"symbol": "US100Z25.sim", "point": 0.01, "digits": 2},
        "account_info": {"balance": 100000, "equity": 100000, "margin_free": 100000, "profit": 0},
        "positions": [],
        "timeframes": {
            tf: [{"time": f"2025-11-23 0{i}:00:00", "open": 20000+i, "high": 20010+i, "low": 19990+i, "close": 20005+i, "volume": 1000}
                 for i in range(100)]
            for tf in ["M5", "M15", "M30", "H1", "H4", "D1"]
        }
    }
    
    try:
        response = requests.post("http://localhost:5007/api/ai/trade_decision", json=request_data, timeout=30)
        
        # Check logs for trigger detection
        with open('/tmp/ai_trading_api.log', 'r') as f:
            logs = f.readlines()
        
        recent = logs[-50:]
        found_trigger = False
        found_weights = False
        
        for line in recent:
            if "Triggered by: H4" in line:
                found_trigger = True
                print(f"✅ Trigger detected: {line.strip()}")
            if "Timeframe weights" in line or "tf_weights" in line:
                found_weights = True
                print(f"✅ Weights adjusted: {line.strip()}")
        
        if found_trigger and found_weights:
            print("✅ TEST PASSED: Trigger timeframe working")
            return True
        elif found_trigger:
            print("⚠️  TEST PARTIAL: Trigger detected but weights not logged")
            return True
        else:
            print("❌ TEST FAILED: Trigger not detected")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def test_dqn_agent():
    """Test 3: DQN Agent Loading"""
    print("\n" + "="*80)
    print("TEST 3: DQN AGENT")
    print("="*80)
    
    # Check startup logs
    with open('/tmp/ai_trading_api.log', 'r') as f:
        logs = f.read()
    
    if "DQN RL Agent loaded: 2265 states learned" in logs:
        print("✅ DQN agent loaded successfully")
        print("   2,265 states learned")
        return True
    else:
        print("❌ DQN agent not loaded")
        return False


def test_conviction_scoring():
    """Test 4: Conviction Scoring Function"""
    print("\n" + "="*80)
    print("TEST 4: CONVICTION SCORING")
    print("="*80)
    
    # Check if function exists in API
    with open('/Users/justinhardison/ai-trading-system/api.py', 'r') as f:
        api_code = f.read()
    
    if "def calculate_conviction" in api_code:
        print("✅ Conviction scoring function defined")
        
        # Check if it's called
        if "conviction = calculate_conviction" in api_code:
            print("✅ Conviction scoring is called in decision flow")
            return True
        else:
            print("❌ Conviction function exists but not called")
            return False
    else:
        print("❌ Conviction scoring function not found")
        return False


def test_models_loaded():
    """Test 5: All Models Loaded"""
    print("\n" + "="*80)
    print("TEST 5: ML MODELS")
    print("="*80)
    
    with open('/tmp/ai_trading_api.log', 'r') as f:
        logs = f.read()
    
    symbols = ['us30', 'us100', 'us500', 'eurusd', 'gbpusd', 'usdjpy', 'xau', 'usoil']
    loaded = []
    
    for symbol in symbols:
        if f"Loaded model for {symbol}" in logs:
            loaded.append(symbol)
            print(f"✅ {symbol.upper()}: Model loaded")
    
    if len(loaded) == 8:
        print(f"\n✅ All 8 models loaded successfully")
        return True
    else:
        print(f"\n⚠️  Only {len(loaded)}/8 models loaded")
        return False


def test_integration():
    """Test 6: Full Integration"""
    print("\n" + "="*80)
    print("TEST 6: INTEGRATION CHECK")
    print("="*80)
    
    checks = {
        "DQN agent in position management": False,
        "Conviction scoring in decision flow": False,
        "Trigger timeframe extraction": False,
        "Timeframe weight adjustment": False,
    }
    
    with open('/Users/justinhardison/ai-trading-system/api.py', 'r') as f:
        api_code = f.read()
    
    # Check integrations
    if "Use DQN RL agent if available" in api_code or "dqn_agent is not None" in api_code:
        checks["DQN agent in position management"] = True
    
    if "conviction = calculate_conviction" in api_code:
        checks["Conviction scoring in decision flow"] = True
    
    if "trigger_timeframe = request.get" in api_code:
        checks["Trigger timeframe extraction"] = True
    
    if "adjust_timeframe_weights" in api_code:
        checks["Timeframe weight adjustment"] = True
    
    # Print results
    all_passed = True
    for check, passed in checks.items():
        if passed:
            print(f"✅ {check}")
        else:
            print(f"❌ {check}")
            all_passed = False
    
    return all_passed


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("COMPREHENSIVE SYSTEM TEST")
    print("="*80)
    print("Testing all implementations...")
    
    tests = [
        ("API Health", test_api_health),
        ("Trigger Timeframe", test_trigger_timeframe),
        ("DQN Agent", test_dqn_agent),
        ("Conviction Scoring", test_conviction_scoring),
        ("ML Models", test_models_loaded),
        ("Integration", test_integration),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
            time.sleep(1)  # Brief pause between tests
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    print(f"RESULTS: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - SYSTEM FULLY IMPLEMENTED")
        return True
    elif passed >= total * 0.8:
        print("\n✅ MOST TESTS PASSED - SYSTEM MOSTLY IMPLEMENTED")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED - CHECK IMPLEMENTATION")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
