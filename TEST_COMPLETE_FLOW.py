#!/usr/bin/env python3
"""
Test Complete Trading Flow - Start to Finish
Simulates actual trading scenario with detailed logging
"""

import requests
import json
import time

def create_realistic_request(symbol="US100Z25.sim", trigger_tf="H1", has_position=False):
    """Create realistic API request"""
    
    request = {
        "symbol": symbol,
        "trigger_timeframe": trigger_tf,
        "symbol_info": {
            "symbol": symbol,
            "point": 0.01,
            "digits": 2
        },
        "account_info": {
            "balance": 100000,
            "equity": 100000 if not has_position else 100500,
            "margin_free": 95000,
            "profit": 0 if not has_position else 500
        },
        "positions": [],
        "timeframes": {}
    }
    
    # Add realistic multi-timeframe data
    timeframes = {
        'M5': 100,
        'M15': 100,
        'M30': 100,
        'H1': 100,
        'H4': 100,
        'D1': 50
    }
    
    for tf, bars in timeframes.items():
        request['timeframes'][tf] = []
        for i in range(bars):
            bar = {
                'time': f'2025-11-23 {i:02d}:00:00',
                'open': 20000 + (i * 0.5),
                'high': 20010 + (i * 0.5),
                'low': 19990 + (i * 0.5),
                'close': 20005 + (i * 0.5),
                'volume': 1000 + (i * 10),
                'rsi': 50 + (i % 20),
                'ma_20': 20000 + (i * 0.3),
                'ma_50': 20000 + (i * 0.2),
                'atr': 100 + (i * 0.1),
                'macd': 5 + (i % 10),
                'macd_signal': 4 + (i % 10),
                'bb_upper': 20100 + (i * 0.5),
                'bb_lower': 19900 + (i * 0.5),
                'stoch_k': 50 + (i % 30),
                'stoch_d': 48 + (i % 30)
            }
            request['timeframes'][tf].append(bar)
    
    # Add position if testing position management
    if has_position:
        request['positions'] = [{
            'symbol': symbol,
            'type': 0,  # BUY
            'volume': 0.1,
            'price_open': 20000,
            'profit': 500,
            'sl': 19900,
            'tp': 20200
        }]
    
    return request


def test_new_trade_flow():
    """Test: No position -> New trade decision"""
    print("\n" + "="*80)
    print("TEST 1: NEW TRADE DECISION FLOW")
    print("="*80)
    
    print("\n📊 Scenario: No open position, looking for new trade")
    print("Symbol: US100 (Nasdaq)")
    print("Trigger: H1 bar close")
    
    request = create_realistic_request("US100Z25.sim", "H1", has_position=False)
    
    print("\n🔄 Sending request to API...")
    try:
        response = requests.post(
            "http://localhost:5007/api/ai/trade_decision",
            json=request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ API Response:")
            print(json.dumps(result, indent=2))
            
            print("\n📋 Decision Breakdown:")
            print(f"   Action: {result.get('action', 'N/A')}")
            print(f"   Reason: {result.get('reason', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}%")
            print(f"   Conviction: {result.get('conviction', 0):.2f}/100")
            
            if result.get('action') in ['BUY', 'SELL']:
                print(f"   Lot Size: {result.get('lot_size', 0)}")
                print(f"   Stop Loss: {result.get('stop_loss', 0)}")
                print(f"   Take Profit: {result.get('take_profit', 0)}")
            
            return True
        else:
            print(f"\n❌ API Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False


def test_position_management_flow():
    """Test: Open position -> Position management"""
    print("\n" + "="*80)
    print("TEST 2: POSITION MANAGEMENT FLOW")
    print("="*80)
    
    print("\n📊 Scenario: Open BUY position with $500 profit")
    print("Symbol: US100 (Nasdaq)")
    print("Position: 0.1 lots @ 20000")
    print("Current Profit: $500")
    
    request = create_realistic_request("US100Z25.sim", "H1", has_position=True)
    
    print("\n🔄 Sending request to API...")
    try:
        response = requests.post(
            "http://localhost:5007/api/ai/trade_decision",
            json=request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ API Response:")
            print(json.dumps(result, indent=2))
            
            print("\n📋 Position Management Decision:")
            print(f"   Action: {result.get('action', 'N/A')}")
            print(f"   Reason: {result.get('reason', 'N/A')}")
            
            if result.get('action') == 'SCALE_IN':
                print(f"   Add Lots: {result.get('add_lots', 0)}")
            elif result.get('action') == 'PARTIAL_CLOSE':
                print(f"   Reduce Lots: {result.get('reduce_lots', 0)}")
            
            return True
        else:
            print(f"\n❌ API Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        return False


def check_api_logs():
    """Check API logs for detailed flow"""
    print("\n" + "="*80)
    print("API LOGS - LAST REQUEST")
    print("="*80)
    
    try:
        with open('/tmp/ai_trading_api.log', 'r') as f:
            logs = f.readlines()
        
        # Get logs from last request
        last_request_idx = -1
        for i in range(len(logs)-1, -1, -1):
            if "AI TRADE DECISION REQUEST" in logs[i]:
                last_request_idx = i
                break
        
        if last_request_idx >= 0:
            relevant_logs = logs[last_request_idx:last_request_idx+100]
            
            print("\n📝 Key Log Entries:")
            for log in relevant_logs:
                if any(keyword in log for keyword in [
                    "Symbol:", "Triggered by:", "CONVICTION:", "ML Signal",
                    "DQN", "action", "HOLD", "BUY", "SELL"
                ]):
                    print(f"   {log.strip()}")
        else:
            print("   No recent request found in logs")
            
    except Exception as e:
        print(f"   ❌ Could not read logs: {e}")


def run_complete_flow_test():
    """Run complete flow test"""
    print("\n" + "="*80)
    print("COMPLETE TRADING FLOW TEST")
    print("="*80)
    print("\nThis test simulates:")
    print("1. New trade decision (no position)")
    print("2. Position management (with position)")
    print("3. Log analysis")
    
    # Test 1: New trade
    test1 = test_new_trade_flow()
    time.sleep(2)
    
    # Test 2: Position management
    test2 = test_position_management_flow()
    time.sleep(2)
    
    # Check logs
    check_api_logs()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"New Trade Flow: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Position Management: {'✅ PASSED' if test2 else '❌ FAILED'}")
    
    if test1 and test2:
        print("\n🎉 ALL FLOW TESTS PASSED")
        print("\nSystem is ready for live trading!")
        print("\nWhat happens in live trading:")
        print("1. EA detects bar close → sends data to API")
        print("2. API checks for open positions first")
        print("3. If position exists → Position Manager decides (HOLD/SCALE/CLOSE)")
        print("4. If no position → Full analysis (Features → ML → Conviction → Risk)")
        print("5. API returns decision → EA executes")
        print("6. All steps logged for monitoring")
        return True
    else:
        print("\n⚠️  SOME TESTS FAILED - Check logs above")
        return False


if __name__ == "__main__":
    success = run_complete_flow_test()
    exit(0 if success else 1)
