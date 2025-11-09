#!/bin/bash
# Quick Installation Helper for MT5 Socket Bridge

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   MT5 Socket Bridge - Quick Installation Helper      ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Get the absolute path to the EA file
EA_FILE="$(pwd)/MT5_Socket_Server.mq5"

echo "📁 MT5 Expert Advisor Location:"
echo "   $EA_FILE"
echo ""

# Try to find MT5 installation
echo "🔍 Searching for MT5 installation..."
echo ""

POSSIBLE_PATHS=(
    "$HOME/Library/Application Support/MetaTrader 5/MQL5/Experts"
    "$HOME/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts"
    "$HOME/CrossOver/Bottles/"
)

MT5_FOUND=false

for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -d "$path" ]; then
        echo "✓ Found: $path"
        MT5_FOUND=true

        # Offer to copy
        read -p "   Copy EA to this location? (y/n): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp "$EA_FILE" "$path/"
            if [ $? -eq 0 ]; then
                echo "   ✓ EA copied successfully!"
                echo ""
                echo "📋 Next Steps:"
                echo "   1. Open MT5 terminal"
                echo "   2. Press F4 to open MetaEditor"
                echo "   3. Open the MT5_Socket_Server.mq5 file"
                echo "   4. Press F7 to compile"
                echo "   5. Go to Tools → Options → Expert Advisors"
                echo "   6. Enable 'Allow algorithmic trading'"
                echo "   7. Drag the EA onto any chart"
                echo "   8. Look for 'Socket server started' in Experts tab"
                echo ""
                echo "✅ When ready, run: python3 test_mt5_socket.py"
                exit 0
            else
                echo "   ✗ Failed to copy (permission denied?)"
            fi
        fi
    fi
done

if [ "$MT5_FOUND" = false ]; then
    echo "⚠️  Could not automatically find MT5 installation"
    echo ""
    echo "📋 Manual Installation Steps:"
    echo ""
    echo "1. Open MT5 terminal"
    echo "2. Go to: File → Open Data Folder"
    echo "3. This will open Finder to your MT5 data folder"
    echo "4. Navigate to: MQL5/Experts/"
    echo "5. Copy this file there:"
    echo "   $EA_FILE"
    echo ""
    echo "6. In MT5, press F4 to open MetaEditor"
    echo "7. File → Open → MT5_Socket_Server.mq5"
    echo "8. Press F7 to compile (should show 0 errors)"
    echo ""
    echo "9. Go to: Tools → Options → Expert Advisors"
    echo "10. Enable: ✓ Allow algorithmic trading"
    echo ""
    echo "11. Drag the EA from Navigator onto any chart"
    echo "12. Click OK in the dialog"
    echo "13. Look for smiley face on chart (means it's running)"
    echo "14. Check Experts tab for: 'Socket server started on port 9090'"
    echo ""
    echo "✅ When ready, run: python3 test_mt5_socket.py"
fi

echo ""
echo "📖 For detailed instructions, see: INSTALL_MT5_SOCKET.md"
