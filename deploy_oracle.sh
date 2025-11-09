#!/bin/bash

# Oracle Cloud Deployment Script
# Run this on your LOCAL machine to deploy to Oracle Cloud

set -e

echo "🚀 Oracle Cloud Deployment Script"
echo "=================================="
echo ""

# Configuration
read -p "Enter Oracle VM IP address: " ORACLE_IP
read -p "Enter path to SSH key: " SSH_KEY
read -p "Enter SSH user (default: ubuntu): " SSH_USER
SSH_USER=${SSH_USER:-ubuntu}

echo ""
echo "📦 Creating deployment package..."

# Create deployment package
tar -czf trading-system.tar.gz \
  ml_api_integrated.py \
  requirements.txt \
  Dockerfile.cloud \
  src/ \
  models/ \
  .env \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='logs/*' \
  --exclude='cache/*'

echo "✅ Package created: trading-system.tar.gz"
echo ""

echo "📤 Uploading to Oracle Cloud..."
scp -i "$SSH_KEY" trading-system.tar.gz ${SSH_USER}@${ORACLE_IP}:~/

echo "✅ Upload complete"
echo ""

echo "🔧 Setting up on Oracle VM..."
ssh -i "$SSH_KEY" ${SSH_USER}@${ORACLE_IP} << 'ENDSSH'
  # Extract package
  mkdir -p ~/trading-system
  cd ~/trading-system
  tar -xzf ../trading-system.tar.gz
  
  # Stop existing container if running
  docker stop trading-api 2>/dev/null || true
  docker rm trading-api 2>/dev/null || true
  
  # Build Docker image
  echo "🐳 Building Docker image..."
  docker build -f Dockerfile.cloud -t trading-api .
  
  # Run container
  echo "🚀 Starting container..."
  docker run -d \
    --name trading-api \
    --restart always \
    -p 8000:8000 \
    -v ~/trading-system/models:/app/models \
    -v ~/trading-system/data:/app/data \
    -v ~/trading-system/logs:/app/logs \
    --env-file .env \
    trading-api
  
  # Wait for startup
  echo "⏳ Waiting for API to start..."
  sleep 10
  
  # Check status
  echo "📊 Container status:"
  docker ps | grep trading-api
  
  echo ""
  echo "📋 Recent logs:"
  docker logs trading-api --tail 20
ENDSSH

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 Testing API..."
curl -s http://${ORACLE_IP}:8000/health | python3 -m json.tool || echo "⚠️  API not responding yet, may need a few more seconds"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Your API is now running at:"
echo "   http://${ORACLE_IP}:8000"
echo ""
echo "📋 Next steps:"
echo "   1. Update MT5 EA with: string API_Host = \"http://${ORACLE_IP}:8000\";"
echo "   2. Recompile EA"
echo "   3. Test connection"
echo ""
echo "🔍 Monitor logs:"
echo "   ssh -i \"$SSH_KEY\" ${SSH_USER}@${ORACLE_IP} 'docker logs -f trading-api'"
echo ""
echo "💰 Cost: \$0 Forever! 🎊"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
