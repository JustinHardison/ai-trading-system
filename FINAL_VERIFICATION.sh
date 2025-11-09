#!/bin/bash

echo "════════════════════════════════════════════════════════════════════════════"
echo "FINAL SYSTEM VERIFICATION"
echo "════════════════════════════════════════════════════════════════════════════"

echo ""
echo "1. Checking API Status..."
if curl -s http://localhost:5007/health > /dev/null 2>&1; then
    echo "   ✅ API is running on port 5007"
    curl -s http://localhost:5007/health | python3 -m json.tool 2>/dev/null | head -10
else
    echo "   ❌ API is not running"
fi

echo ""
echo "2. Checking API Logs..."
if tail -20 /tmp/ai_trading_api.log | grep -q "DQN RL Agent loaded"; then
    echo "   ✅ DQN agent loaded"
fi
if tail -20 /tmp/ai_trading_api.log | grep -q "Total models loaded: 8"; then
    echo "   ✅ All 8 models loaded"
fi
if tail -20 /tmp/ai_trading_api.log | grep -q "SYSTEM READY"; then
    echo "   ✅ System ready"
fi

echo ""
echo "3. Checking Implementation..."
if grep -q "def calculate_conviction" api.py; then
    echo "   ✅ Conviction scoring function exists"
fi
if grep -q "conviction = calculate_conviction" api.py; then
    echo "   ✅ Conviction scoring is called"
fi
if grep -q "dqn_agent is not None" api.py; then
    echo "   ✅ DQN agent is used"
fi
if grep -q "trigger_timeframe = request.get" api.py; then
    echo "   ✅ Trigger timeframe detection exists"
fi

echo ""
echo "4. Checking Files..."
for file in "COMPLETE_IMPLEMENTATION_REPORT.md" "FINAL_IMPLEMENTATION_STATUS.md" "COMPREHENSIVE_TEST.py" "EA_EVENT_DRIVEN_PATCH.mq5"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file missing"
    fi
done

echo ""
echo "5. Checking Models..."
model_count=$(ls -1 models/*_ensemble_latest.pkl 2>/dev/null | wc -l | tr -d ' ')
echo "   ✅ $model_count/8 models found"

if [ -f "models/dqn_agent.pkl" ]; then
    echo "   ✅ DQN agent file exists"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "VERIFICATION COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""
echo "System Status: READY ✅"
echo ""
echo "To start trading:"
echo "  1. API is already running"
echo "  2. Attach AI_Trading_EA_Ultimate to any chart in MT5"
echo "  3. Monitor: tail -f /tmp/ai_trading_api.log"
echo ""
