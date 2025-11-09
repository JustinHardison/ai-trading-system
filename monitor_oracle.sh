#!/bin/bash

# Oracle Cloud Monitoring Script
# Run this to check your cloud deployment status

set -e

# Configuration
read -p "Enter Oracle VM IP address: " ORACLE_IP
read -p "Enter path to SSH key: " SSH_KEY
read -p "Enter SSH user (default: ubuntu): " SSH_USER
SSH_USER=${SSH_USER:-ubuntu}

echo ""
echo "🔍 Monitoring Oracle Cloud Deployment"
echo "======================================"
echo ""

# Function to run command on Oracle VM
run_remote() {
  ssh -i "$SSH_KEY" ${SSH_USER}@${ORACLE_IP} "$1"
}

# Check API health
echo "📊 API Health Check:"
curl -s http://${ORACLE_IP}:8000/health | python3 -m json.tool || echo "❌ API not responding"
echo ""

# Check Docker status
echo "🐳 Docker Container Status:"
run_remote "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep trading-api"
echo ""

# Check system resources
echo "💻 System Resources:"
run_remote "echo 'CPU Usage:' && top -bn1 | grep 'Cpu(s)' | awk '{print \$2}' && echo 'Memory:' && free -h | grep Mem | awk '{print \$3 \"/\" \$2}' && echo 'Disk:' && df -h / | tail -1 | awk '{print \$3 \"/\" \$2 \" (\" \$5 \" used)\"}'"
echo ""

# Check recent logs
echo "📋 Recent API Logs (last 20 lines):"
run_remote "docker logs trading-api --tail 20"
echo ""

# Check for errors
echo "❌ Recent Errors (if any):"
run_remote "docker logs trading-api --tail 100 | grep -i error || echo 'No errors found'"
echo ""

# Docker stats
echo "📈 Docker Resource Usage:"
run_remote "docker stats trading-api --no-stream --format 'CPU: {{.CPUPerc}}\tMemory: {{.MemUsage}}\tNet I/O: {{.NetIO}}'"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Monitoring Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🔄 To restart API:"
echo "   ssh -i \"$SSH_KEY\" ${SSH_USER}@${ORACLE_IP} 'docker restart trading-api'"
echo ""
echo "📋 To view live logs:"
echo "   ssh -i \"$SSH_KEY\" ${SSH_USER}@${ORACLE_IP} 'docker logs -f trading-api'"
echo ""
echo "🔧 To access VM:"
echo "   ssh -i \"$SSH_KEY\" ${SSH_USER}@${ORACLE_IP}"
