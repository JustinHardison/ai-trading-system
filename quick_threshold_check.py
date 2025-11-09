#!/usr/bin/env python3
"""
Quick threshold analysis using current live data
"""
import pandas as pd
import numpy as np
import joblib

print("═══════════════════════════════════════════════════════════════════")
print("QUICK CONFIDENCE THRESHOLD CHECK")
print("═══════════════════════════════════════════════════════════════════\n")

# Load model
print("[1/3] Loading model...")
model_path = '/Users/justinhardison/ai-trading-system/models/integrated_ensemble_20251112_200757.pkl'
model_data = joblib.load(model_path)

xgb_model = model_data['xgb_model']
lgb_model = model_data['lgb_model']

print(f"✓ XGBoost + LightGBM ensemble")
print(f"✓ Trained on: {model_data['training_samples']} samples")
print(f"✓ Validation: {model_data['validation_samples']} samples")
print(f"✓ Ensemble accuracy: {model_data['ensemble_accuracy']:.1%}")

# Parse API logs to see real confidence distribution
print("\n[2/3] Analyzing LIVE confidence from API logs...")
import re

with open('/tmp/api_fixed.log', 'r') as f:
    lines = f.readlines()

confidences = []
for line in lines:
    if 'ML SIGNAL:' in line and 'Confidence:' in line:
        match = re.search(r'Confidence: ([\d.]+)%', line)
        if match:
            conf = float(match.group(1))
            confidences.append(conf)

if confidences:
    confidences = np.array(confidences)
    
    print(f"\n✓ Found {len(confidences)} predictions from live trading")
    print(f"\nLIVE CONFIDENCE DISTRIBUTION:")
    print(f"  Mean:   {confidences.mean():.1f}%")
    print(f"  Median: {np.median(confidences):.1f}%")
    print(f"  Min:    {confidences.min():.1f}%")
    print(f"  Max:    {confidences.max():.1f}%")
    print(f"  Std:    {confidences.std():.1f}%")
    
    print(f"\nPERCENTILES:")
    for p in [10, 25, 50, 75, 90, 95, 99]:
        val = np.percentile(confidences, p)
        print(f"  {p:2d}th: {val:.1f}%")
    
    print(f"\nSIGNALS BY THRESHOLD:")
    for threshold in [40, 45, 48, 50, 52, 55, 57, 60, 65]:
        count = (confidences >= threshold).sum()
        pct = count / len(confidences) * 100
        marker = " ⭐ CURRENT" if threshold == 55 else ""
        print(f"  >= {threshold}%: {count:4d} signals ({pct:5.1f}%){marker}")
    
    print(f"\n[3/3] THRESHOLD RECOMMENDATION:")
    print("═"*70)
    
    above_55 = (confidences >= 55).sum()
    above_50 = (confidences >= 50).sum()
    above_48 = (confidences >= 48).sum()
    
    print(f"\nWith 55% threshold: {above_55} signals ({above_55/len(confidences)*100:.1f}%)")
    print(f"With 50% threshold: {above_50} signals ({above_50/len(confidences)*100:.1f}%)")
    print(f"With 48% threshold: {above_48} signals ({above_48/len(confidences)*100:.1f}%)")
    
    if above_55 < len(confidences) * 0.05:  # Less than 5% of signals
        print(f"\n⚠️  55% THRESHOLD IS TOO RESTRICTIVE!")
        print(f"   Only {above_55/len(confidences)*100:.1f}% of signals pass!")
        print(f"   Model is naturally conservative in current market")
        
        # Find threshold that captures ~20% of signals
        target_pct = 0.20
        for t in range(40, 70):
            pct = (confidences >= t).sum() / len(confidences)
            if pct <= target_pct:
                print(f"\n💡 SUGGESTED: Lower to {t}% (captures {pct*100:.1f}% of signals)")
                break
    
    elif above_55 > len(confidences) * 0.50:  # More than 50% of signals
        print(f"\n⚠️  55% THRESHOLD MAY BE TOO LOW!")
        print(f"   {above_55/len(confidences)*100:.1f}% of signals pass")
        print(f"   Consider raising threshold for better quality")
    
    else:
        print(f"\n✅ 55% THRESHOLD LOOKS REASONABLE")
        print(f"   Captures {above_55/len(confidences)*100:.1f}% of signals")

else:
    print("\n❌ No confidence data found in logs")

print("\n═══════════════════════════════════════════════════════════════════")
