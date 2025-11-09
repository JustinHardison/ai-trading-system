#!/bin/bash

echo "═══════════════════════════════════════════════════════════════════"
echo "  🚀 ULTIMATE AI TRADING SYSTEM - QUICK START"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check if API is already running
echo "Checking Ultimate AI API status..."
if curl -s http://127.0.0.1:5007/health > /dev/null 2>&1; then
    echo "✅ Ultimate AI API is already running on port 5007"
    echo ""
    curl -s http://127.0.0.1:5007/health | python3 -m json.tool
else
    echo "⚠️  Ultimate AI API not running. Starting it now..."
    echo ""

    cd /Users/justinhardison/ai-trading-system

    # Start in background
    nohup python3 ml_api_ultimate.py > ultimate_api.log 2>&1 &

    echo "Waiting for API to start..."
    sleep 5

    if curl -s http://127.0.0.1:5007/health > /dev/null 2>&1; then
        echo "✅ Ultimate AI API started successfully!"
        echo ""
        curl -s http://127.0.0.1:5007/health | python3 -m json.tool
    else
        echo "❌ Failed to start API. Check ultimate_api.log for errors."
        exit 1
    fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ✅ API READY - NOW GO TO MT5"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "1. Open MetaTrader 5"
echo "2. Press F4 (MetaEditor)"
echo "3. Find: Experts → US30_Ultimate_AI.mq5"
echo "4. Press F7 (Compile)"
echo "5. Drag EA onto US30Z25.sim chart"
echo "6. Enable AutoTrading (green button)"
echo ""
echo "The AI will start monitoring every 60 seconds!"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
