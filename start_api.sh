#!/bin/bash

# AI Trading API Startup Script
# Handles proper logging and prevents crashes

cd /Users/justinhardison/ai-trading-system

# Kill any existing API processes
pkill -f "python3 api.py"
sleep 2

# Start API with proper logging (unbuffered output)
python3 -u api.py >> /tmp/ai_trading_api.log 2>&1 &

API_PID=$!
echo "API started with PID: $API_PID"
echo $API_PID > /tmp/api.pid

# Wait a moment and check if it's running
sleep 3
if ps -p $API_PID > /dev/null; then
    echo "✅ API is running successfully"
    curl -s http://127.0.0.1:5007/health | python3 -m json.tool
else
    echo "❌ API failed to start"
    tail -50 /tmp/ai_trading_api.log
    exit 1
fi
