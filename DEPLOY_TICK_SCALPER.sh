#!/bin/bash
#
# Deploy Tick-by-Tick Scalping System for US30
# This script trains new models and restarts the API
#

echo "═══════════════════════════════════════════════════════════"
echo "  US30 TICK-BY-TICK SCALPING SYSTEM DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Step 1: Train new tick-optimized models
echo "Step 1: Training tick-by-tick ML models..."
echo "  - This will fetch 30 days of US30 M1 data from MT5"
echo "  - Entry model: Predicts BUY/SELL/HOLD on every tick"
echo "  - Exit model: Manages positions tick-by-tick"
echo ""

python3 train_tick_scalper.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Training failed! Check the error above."
    exit 1
fi

echo ""
echo "✓ Models trained successfully!"
echo ""

# Step 2: Kill old API process
echo "Step 2: Stopping old API..."
OLD_PID=$(ps aux | grep "ml_api_ultimate.py" | grep -v grep | awk '{print $2}')

if [ ! -z "$OLD_PID" ]; then
    kill $OLD_PID
    echo "✓ Stopped old API (PID: $OLD_PID)"
else
    echo "  No old API running"
fi

sleep 2

# Step 3: Start new API with tick models
echo ""
echo "Step 3: Starting new tick-scalping API..."
nohup python3 ml_api_ultimate.py > /tmp/v4_tick_scalper.log 2>&1 &
NEW_PID=$!

echo "✓ API started (PID: $NEW_PID)"
echo "  Log: /tmp/v4_tick_scalper.log"

sleep 3

# Step 4: Test API
echo ""
echo "Step 4: Testing API health..."
curl -s http://127.0.0.1:5007/health | python3 -m json.tool

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "System Configuration:"
echo "  • ML Entry: Tick-by-tick predictions (every price change)"
echo "  • ML Exit: Tick-by-tick position management"
echo "  • LLM: 60-second market overview + confirmation"
echo "  • Stop Loss: 30 points (tight scalping)"
echo "  • Take Profit: 60 points (2:1 ratio)"
echo "  • Risk: 0.5% per trade"
echo "  • Threshold: 40-50% (aggressive for NY session)"
echo ""
echo "EA Configuration:"
echo "  • Make sure US30_Ultimate_AI_v3 EA is running in MT5"
echo "  • EA will call API on every tick"
echo "  • LLM updates market context every 60 seconds"
echo ""
echo "Monitor logs:"
echo "  tail -f /tmp/v4_tick_scalper.log"
echo "  tail -f logs/trading_$(date +%Y-%m-%d).log"
echo ""
echo "🚀 Ready to scalp US30 during NY session!"
echo ""
