#!/bin/bash

# Oracle ARM Instance Creation Script with Retry
# Retries every 5 minutes until successful

export SUPPRESS_LABEL_WARNING=True

echo "🔄 Oracle ARM Instance Creation Script"
echo "========================================"
echo ""
echo "Oracle ARM free tier has limited capacity."
echo "This script will retry every 5 minutes until successful."
echo ""
echo "Press Ctrl+C to stop"
echo ""

ATTEMPT=1

while true; do
    echo "[$ATTEMPT] Attempting to create ARM instance at $(date)..."
    
    # Try all 3 availability domains
    for AD in 1 2 3; do
        echo "  Trying AD-$AD..."
        
        OUTPUT=$(~/bin/oci compute instance launch \
          --availability-domain "DzcS:US-ASHBURN-AD-$AD" \
          --compartment-id "ocid1.tenancy.oc1..aaaaaaaa4gpoxff7tk36suxxi4oj2is4fle5yeg6qcfuvve55rj5nxnfji5a" \
          --shape "VM.Standard.A1.Flex" \
          --shape-config '{"ocpus":1,"memoryInGBs":6}' \
          --display-name "ai-trading-bot-arm" \
          --image-id "ocid1.image.oc1.iad.aaaaaaaae6bcfpsytkvjkraph2um7h5fha42wqpgsmtvsw5l4cqnweqe2j4q" \
          --subnet-id "ocid1.subnet.oc1.iad.aaaaaaaajchud3nlj5pdwtylibpaaxqlmqltwjimx7fww2xcsflvpymlepda" \
          --assign-public-ip true \
          --ssh-authorized-keys-file /Users/justinhardison/Downloads/ssh-key-2025-11-09.key.pub 2>&1)
        
        if echo "$OUTPUT" | grep -q '"lifecycle-state": "RUNNING"'; then
            echo ""
            echo "✅ SUCCESS! Instance created in AD-$AD!"
            echo ""
            echo "$OUTPUT" | grep -E '"id"|"public-ip"'
            echo ""
            exit 0
        elif echo "$OUTPUT" | grep -q '"lifecycle-state": "PROVISIONING"'; then
            echo ""
            echo "✅ Instance is provisioning in AD-$AD! Waiting..."
            sleep 30
            
            # Get instance ID
            INSTANCE_ID=$(echo "$OUTPUT" | grep '"id"' | head -1 | cut -d'"' -f4)
            
            # Wait for it to be running
            ~/bin/oci compute instance get --instance-id "$INSTANCE_ID" --wait-for-state RUNNING
            
            echo "✅ Instance is now RUNNING!"
            ~/bin/oci compute instance get --instance-id "$INSTANCE_ID" --query 'data.{"id":id,"ip":"public-ip","state":"lifecycle-state"}'
            exit 0
        elif echo "$OUTPUT" | grep -q "Out of host capacity"; then
            echo "  ❌ AD-$AD: Out of capacity"
        else
            echo "  ❌ AD-$AD: Error"
            echo "$OUTPUT" | grep '"message"' | head -1
        fi
    done
    
    echo ""
    echo "All ADs out of capacity. Waiting 5 minutes before retry..."
    echo "Next attempt: $(date -v+5M)"
    echo ""
    
    ATTEMPT=$((ATTEMPT + 1))
    sleep 300  # Wait 5 minutes
done
