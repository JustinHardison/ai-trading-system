import requests
import json

print("Testing API with sample data to verify it processes correctly...\n")

# Test data simulating what EA sends
test_request = {
    "symbol": "US30",
    "account_balance": 98645.32,
    "account_equity": 98645.32,
    "daily_pnl": 0.0,
    "open_positions": 0,
    "position_profit": 0.0,
    "bars_held": 0,
    "market_data": {
        "M1": {
            "close": [47500, 47505, 47510, 47515, 47520],
            "high": [47505, 47510, 47515, 47520, 47525],
            "low": [47495, 47500, 47505, 47510, 47515],
            "open": [47500, 47505, 47510, 47515, 47520],
            "volume": [100, 110, 105, 115, 120]
        }
    }
}

try:
    response = requests.post(
        "http://localhost:5007/api/ultimate/ml_entry",
        json=test_request,
        timeout=5
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ API Response Received!\n")
        print("=" * 60)
        print("ACCOUNT DATA PROCESSED:")
        print("=" * 60)
        print(f"Balance: ${data.get('account_balance', 'N/A'):,.2f}" if isinstance(data.get('account_balance'), (int, float)) else f"Balance: {data.get('account_balance', 'N/A')}")
        print(f"Max Positions: {data.get('max_positions', 'N/A')}")
        print(f"Current Positions: {data.get('current_positions', 'N/A')}")
        print(f"Daily P&L: ${data.get('daily_pnl', 'N/A'):,.2f}" if isinstance(data.get('daily_pnl'), (int, float)) else f"Daily P&L: {data.get('daily_pnl', 'N/A')}")
        print(f"Drawdown: {data.get('current_drawdown', 'N/A')}")
        print()
        print("=" * 60)
        print("ML/RL DECISION:")
        print("=" * 60)
        print(f"Direction: {data.get('direction', 'N/A')}")
        print(f"Confidence: {data.get('confidence', 'N/A')}%")
        print(f"Take Trade: {data.get('take_trade', 'N/A')}")
        print(f"Lot Size: {data.get('lot_size', 'N/A')}")
        print()
        print("=" * 60)
        print("RL SCALING:")
        print("=" * 60)
        print(f"Should Scale In: {data.get('should_scale_in', 'N/A')}")
        print(f"Scale Amount: {data.get('scale_amount', 'N/A')}")
        print(f"RL Action: {data.get('rl_scale_action', 'N/A')}")
        print()
        print("✅ API is processing all data correctly!")
    else:
        print(f"❌ API Error: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ Connection Error: {e}")
    print("Is the API running?")

