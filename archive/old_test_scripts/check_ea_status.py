#!/usr/bin/env python3
"""
Check if MT5 EA is running and communicating
"""
from pathlib import Path
import json
import time

def check_ea_status():
    """Check if EA is responding"""
    # FILE_COMMON path (where EA stores files)
    doc_path = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/Public/Documents"
    cmd_file = doc_path / "ai_command.txt"
    resp_file = doc_path / "ai_response.txt"

    print("\n" + "="*60)
    print("MT5 EXPERT ADVISOR STATUS CHECK")
    print("="*60)

    # Check if MT5 is running
    import subprocess
    result = subprocess.run(['pgrep', '-f', 'MetaTrader'], capture_output=True)
    if result.returncode != 0:
        print("\n❌ MT5 is NOT running")
        print("\nStart MT5 first!")
        return False

    print("\n✅ MT5 is running")

    # Test EA communication
    print("\n📡 Testing EA communication...")

    # Clean up old response
    if resp_file.exists():
        resp_file.unlink()

    # Send test command
    test_cmd = {"command": "get_account"}
    cmd_file.write_text(json.dumps(test_cmd))
    print(f"   Sent: {test_cmd}")

    # Wait for response
    print("   Waiting for response", end="", flush=True)
    for i in range(10):
        time.sleep(0.5)
        print(".", end="", flush=True)

        if resp_file.exists():
            time.sleep(0.2)  # Let MT5 finish writing
            try:
                response_text = resp_file.read_text(encoding='utf-8-sig').strip('\ufeff').strip()
                response = json.loads(response_text)

                print("\n\n✅ EA IS RESPONDING!\n")

                if response.get('success'):
                    print(f"Account Information:")
                    print(f"  Login:        {response.get('login', 'N/A')}")
                    print(f"  Balance:      ${response.get('balance', 0):,.2f}")
                    print(f"  Equity:       ${response.get('equity', 0):,.2f}")
                    print(f"  Margin:       ${response.get('margin', 0):,.2f}")
                    print(f"  Free Margin:  ${response.get('margin_free', 0):,.2f}")
                    print(f"  Profit:       ${response.get('profit', 0):,.2f}")
                    print("\n✅ READY TO TRADE!")
                    return True
                else:
                    print(f"\n⚠️  EA responded but with error: {response.get('error', 'Unknown')}")
                    return False

            except Exception as e:
                print(f"\n❌ Error reading response: {e}")
                return False

    print("\n\n❌ EA IS NOT RESPONDING")
    print("\nThe Expert Advisor is not loaded on a chart!")
    print("\nTO FIX:")
    print("  1. Open MetaTrader 5")
    print("  2. Open any chart (File → New Chart)")
    print("  3. In Navigator, find 'MT5_Socket_Server' under Expert Advisors")
    print("  4. Drag it onto the chart")
    print("  5. Enable AutoTrading (press Alt+E or click the button)")
    print("  6. Look for a smiley face icon on the chart")
    print("\nThen run this script again to verify.")

    return False

if __name__ == "__main__":
    success = check_ea_status()
    print("\n" + "="*60)
    exit(0 if success else 1)
