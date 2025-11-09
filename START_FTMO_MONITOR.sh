#!/bin/bash
# Start FTMO Metrics Monitor
# Runs every hour at the top of the hour

cd /Users/justinhardison/ai-trading-system

echo "Starting FTMO Metrics Monitor..."
echo "Schedule: Every hour at :00"
echo "Logs: logs/ftmo_monitor_*.log"
echo ""

# Create logs directory
mkdir -p logs

# Run monitor in background
nohup python3 monitor_ftmo_metrics.py --schedule > logs/ftmo_monitor_console.log 2>&1 &

echo "Monitor started! PID: $!"
echo "To stop: pkill -f monitor_ftmo_metrics"
echo "To view logs: tail -f logs/ftmo_monitor_*.log"
