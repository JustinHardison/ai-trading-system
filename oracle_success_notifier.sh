#!/bin/bash

# Oracle ARM Success Notifier
# Monitors the creation script and notifies when instance is ready

LOG_FILE="/tmp/oracle_arm_creation.log"
NOTIFY_FILE="/tmp/oracle_arm_success.txt"

echo "🔔 Oracle ARM Success Notifier Started"
echo "======================================"
echo ""
echo "Monitoring instance creation..."
echo "Will notify when ready!"
echo ""

# Function to send notification
notify_success() {
    local IP=$1
    local INSTANCE_ID=$2
    
    # Visual notification
    osascript -e 'display notification "Oracle ARM instance is ready! Check Terminal for details." with title "🎉 Oracle Cloud Ready"'
    
    # Audio notification
    afplay /System/Library/Sounds/Glass.aiff
    
    # Terminal notification
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 SUCCESS! ORACLE ARM INSTANCE IS READY!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✅ Instance ID: $INSTANCE_ID"
    echo "✅ Public IP: $IP"
    echo "✅ RAM: 6GB (ARM)"
    echo "✅ Cost: FREE Forever!"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "1. I'll now deploy your trading system automatically"
    echo "2. Wait 5 minutes for deployment"
    echo "3. Update MT5 EA with: http://$IP:8000"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Save to file
    echo "SUCCESS" > "$NOTIFY_FILE"
    echo "IP=$IP" >> "$NOTIFY_FILE"
    echo "INSTANCE_ID=$INSTANCE_ID" >> "$NOTIFY_FILE"
}

# Monitor the creation script
while true; do
    # Check if instance was created
    INSTANCE_CHECK=$(export SUPPRESS_LABEL_WARNING=True && ~/bin/oci compute instance list \
        --compartment-id "ocid1.tenancy.oc1..aaaaaaaa4gpoxff7tk36suxxi4oj2is4fle5yeg6qcfuvve55rj5nxnfji5a" \
        --display-name "ai-trading-bot-arm" \
        --lifecycle-state RUNNING \
        --query 'data[0].{id:id,ip:"public-ip"}' 2>&1)
    
    if echo "$INSTANCE_CHECK" | grep -q "ocid1.instance"; then
        # Extract IP and ID
        INSTANCE_ID=$(echo "$INSTANCE_CHECK" | grep '"id"' | cut -d'"' -f4)
        PUBLIC_IP=$(echo "$INSTANCE_CHECK" | grep '"ip"' | cut -d'"' -f4)
        
        if [ ! -z "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "null" ]; then
            notify_success "$PUBLIC_IP" "$INSTANCE_ID"
            
            # Start automatic deployment
            echo "🚀 Starting automatic deployment..."
            /Users/justinhardison/ai-trading-system/deploy_to_oracle.sh "$PUBLIC_IP"
            
            exit 0
        fi
    fi
    
    # Check every 30 seconds
    sleep 30
done
