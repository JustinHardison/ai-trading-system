#!/bin/bash

# Automatic deployment script for Oracle ARM instance
IP=$1

if [ -z "$IP" ]; then
    echo "Usage: $0 <IP_ADDRESS>"
    exit 1
fi

echo "🚀 Deploying to Oracle ARM at $IP"
echo "=================================="
echo ""

# Upload trading system
echo "📤 Uploading trading system..."
scp -i /Users/justinhardison/Downloads/ssh-key-2025-11-09.key \
    -o StrictHostKeyChecking=no \
    /Users/justinhardison/ai-trading-system/trading-system.tar.gz \
    opc@$IP:~/

# Deploy and start
echo "🔧 Installing and starting API..."
ssh -i /Users/justinhardison/Downloads/ssh-key-2025-11-09.key \
    -o StrictHostKeyChecking=no \
    opc@$IP 'bash -s' << 'ENDSSH'
set -e

# Extract
mkdir -p ~/trading-system
cd ~/trading-system
tar -xzf ../trading-system.tar.gz

# Install Python
echo "Installing Python..."
sudo yum install -y python3.11 python3.11-pip gcc gcc-c++ python3.11-devel

# Install dependencies
echo "Installing Python packages..."
python3.11 -m pip install --user -r requirements.txt

# Start API
echo "Starting API..."
nohup python3.11 -m uvicorn ml_api_integrated:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
echo $! > api.pid

# Configure firewall
echo "Configuring firewall..."
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

echo "✅ Deployment complete!"
ENDSSH

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎊 DEPLOYMENT COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ API URL: http://$IP:8000"
echo ""
echo "📋 UPDATE YOUR MT5 EA:"
echo "   string API_Host = \"http://$IP:8000\";"
echo ""
echo "🧪 TEST API:"
echo "   curl http://$IP:8000/health"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
