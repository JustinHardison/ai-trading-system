#!/bin/bash

# AI Trading API Monitor Script
# Keeps API running and restarts if it crashes

while true; do
    # Check if API is running
    if ! pgrep -f "python3.*api.py" > /dev/null; then
        echo "$(date): ⚠️ API not running - restarting..."
        cd /Users/justinhardison/ai-trading-system
        ./start_api.sh
    else
        # API is running - check health
        if ! curl -s http://127.0.0.1:5007/health > /dev/null 2>&1; then
            echo "$(date): ⚠️ API not responding - restarting..."
            pkill -f "python3 api.py"
            sleep 2
            ./start_api.sh
        fi
    fi
    
    # Check every 30 seconds
    sleep 30
done
