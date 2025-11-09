#!/bin/bash
# Start API for EA Testing

echo "═══════════════════════════════════════════════════════════════════"
echo "STARTING AI TRADING API FOR EA TESTING"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  - Symbol: US30 (only trained model)"
echo "  - Port: 5007"
echo "  - Order Flow: Enabled"
echo "  - Symbol Cleaning: Enabled"
echo ""
echo "Starting API..."
echo ""

cd /Users/justinhardison/ai-trading-system
python3 api.py
