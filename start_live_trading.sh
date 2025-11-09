#!/bin/bash
#
# Start Live Trading System
# Run this AFTER you've loaded the EA in MT5
#

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "           STARTING LIVE TRADING SYSTEM"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if EA is responding
echo "Step 1: Checking EA connection..."
python3 check_ea_status.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ EA is not responding. Please load the EA in MT5 first!"
    echo ""
    echo "Quick steps:"
    echo "  1. Open MetaTrader 5"
    echo "  2. Drag 'MT5_Socket_Server' EA onto any chart"
    echo "  3. Enable AutoTrading (Alt+E)"
    echo "  4. Run this script again"
    echo ""
    exit 1
fi

echo ""
echo "Step 2: Stopping old trader instance..."
pkill -f autonomous_trader.py
sleep 2

echo ""
echo "Step 3: Starting autonomous trader..."
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "           🎯 LIVE TRADING ACTIVE 🎯"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "The AI trader is now:"
echo "  ✅ Scanning 15+ markets"
echo "  ✅ Analyzing opportunities with ML models"
echo "  ✅ Executing LIVE trades when conditions are met"
echo "  ✅ Managing positions with FTMO rules"
echo ""
echo "Watch the output below for trading activity..."
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""

# Start trader (this will run in foreground so you can see output)
python3 autonomous_trader.py
