#!/bin/bash

echo "="*80
echo "CLEANING TECHNICAL DEBT AND GARBAGE FILES"
echo "="*80

# Find and list garbage files
echo ""
echo "1. Finding temporary/garbage files..."

# Broken/backup files
find . -maxdepth 1 -name "*.broken*" -o -name "*.backup*" -o -name "*_old.*" | while read file; do
    echo "   Removing: $file"
    rm -f "$file"
done

# Duplicate scripts
echo ""
echo "2. Checking for duplicate/obsolete scripts..."
ls -1 *.py 2>/dev/null | grep -E "(FIX_|REBUILD_|PROPER_REBUILD)" | while read file; do
    if [ "$file" != "TRAIN_ALL_SYMBOLS_PROPERLY.py" ]; then
        echo "   Archiving: $file"
        mv "$file" archive/implementation_scripts/ 2>/dev/null
    fi
done

# Old log files
echo ""
echo "3. Cleaning old logs..."
find . -maxdepth 1 -name "*.log" -mtime +7 -exec rm -f {} \;
echo "   ✅ Old logs cleaned"

# Pycache
echo ""
echo "4. Removing __pycache__..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo "   ✅ Python cache cleaned"

# Check for dead code in src/
echo ""
echo "5. Checking src/ directory..."
if [ -d "src/features" ]; then
    if [ ! -f "src/features/feature_engineer.py" ]; then
        echo "   ⚠️  feature_engineer.py missing (already removed as dead code)"
    fi
fi

echo ""
echo "="*80
echo "✅ CLEANUP COMPLETE"
echo "="*80

# List remaining files
echo ""
echo "Current project structure:"
ls -lh *.py 2>/dev/null | awk '{print "   " $9, "(" $5 ")"}'
ls -lh *.md 2>/dev/null | awk '{print "   " $9, "(" $5 ")"}'

