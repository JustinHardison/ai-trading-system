#!/usr/bin/env python3
"""
Analyze ML Model Confidence Threshold
Find the optimal threshold for US30 trading
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
import sys

sys.path.append('/Users/justinhardison/ai-trading-system')

from src.features.ea_feature_engineer import EAFeatureEngineer

print("═══════════════════════════════════════════════════════════════════")
print("ML CONFIDENCE THRESHOLD ANALYSIS")
print("═══════════════════════════════════════════════════════════════════\n")

# Load model
print("[1/5] Loading model...")
model_path = '/Users/justinhardison/ai-trading-system/models/integrated_ensemble_20251112_200757.pkl'
model_data = joblib.load(model_path)

xgb_model = model_data['xgb_model']
lgb_model = model_data['lgb_model']

print(f"✓ Loaded ensemble: XGBoost + LightGBM")
print(f"  Expected features: {len(model_data['feature_names'])}")

# Load US30 data
print("\n[2/5] Loading US30 M1 data...")
df = pd.read_csv('/Users/justinhardison/ai-trading-system/us30_historical_data.csv', sep='\t')
df.columns = [col.strip().lower() for col in df.columns]

# Use last 10,000 bars for analysis (recent data)
df = df.tail(10000).reset_index(drop=True)
print(f"✓ Loaded {len(df)} recent bars")

# Initialize feature engineer
print("\n[3/5] Extracting features...")
feature_engineer = EAFeatureEngineer()

features_list = []
labels = []
confidences = []
valid_indices = []

for i in range(100, len(df) - 10):
    try:
        # Create multi-timeframe data (simulate what EA sends)
        mtf_data = {
            'm1': df.iloc[max(0, i-50):i+1],
            'm5': df.iloc[max(0, i-50):i+1],  # Using M1 data as proxy
            'm15': df.iloc[max(0, i-50):i+1],
            'm30': df.iloc[max(0, i-50):i+1],
            'h1': df.iloc[max(0, i-50):i+1],
            'h4': df.iloc[max(0, i-50):i+1],
            'd1': df.iloc[max(0, i-50):i+1],
        }
        
        # Extract features
        features = feature_engineer.extract_features(mtf_data)
        
        if features is None or len(features) != 153:
            continue
        
        # Create label (future outcome)
        current_price = df['close'].iloc[i]
        future_prices = df['close'].iloc[i+1:i+11]
        
        max_future = future_prices.max()
        min_future = future_prices.min()
        
        up_move = max_future - current_price
        down_move = current_price - min_future
        
        if up_move > down_move * 1.2 and up_move > 30:  # Bullish
            label = 1
        elif down_move > up_move * 1.2 and down_move > 30:  # Bearish
            label = 2
        else:
            label = 0  # Hold
        
        features_list.append(features)
        labels.append(label)
        valid_indices.append(i)
        
    except Exception as e:
        continue
    
    if i % 1000 == 0:
        print(f"  Processed {i}/{len(df)} bars...")

print(f"✓ Extracted {len(features_list)} valid samples")

# Convert to array
X = np.array(features_list)
y = np.array(labels)

# Get predictions with confidence
print("\n[4/5] Getting model predictions...")
xgb_proba = xgb_model.predict_proba(X)
lgb_proba = lgb_model.predict_proba(X)

# Ensemble (average probabilities)
ensemble_proba = (xgb_proba + lgb_proba) / 2

# Get predicted class and confidence
predictions = np.argmax(ensemble_proba, axis=1)
confidences = np.max(ensemble_proba, axis=1) * 100  # Convert to percentage

print(f"✓ Generated {len(predictions)} predictions")

# Analyze confidence distribution
print("\n[5/5] Analyzing confidence distribution...")
print("\n" + "═"*70)
print("CONFIDENCE DISTRIBUTION")
print("═"*70)

bins = [0, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
hist, _ = np.histogram(confidences, bins=bins)

for i in range(len(bins)-1):
    count = hist[i]
    pct = count / len(confidences) * 100
    bar = "█" * int(pct / 2)
    print(f"{bins[i]:3.0f}-{bins[i+1]:3.0f}%: {bar} {count:5d} ({pct:5.1f}%)")

print(f"\nMean Confidence: {confidences.mean():.1f}%")
print(f"Median Confidence: {np.median(confidences):.1f}%")
print(f"Std Dev: {confidences.std():.1f}%")

# Test different thresholds
print("\n" + "═"*70)
print("THRESHOLD PERFORMANCE ANALYSIS")
print("═"*70)
print(f"\n{'Threshold':<12} {'Trades':<8} {'Correct':<8} {'Win Rate':<10} {'BUY Win':<10} {'SELL Win':<10}")
print("-" * 70)

thresholds = [40, 42, 45, 47, 50, 52, 55, 57, 60, 65, 70]

best_threshold = None
best_win_rate = 0

for threshold in thresholds:
    # Filter predictions by threshold
    mask = confidences >= threshold
    
    if mask.sum() == 0:
        continue
    
    filtered_preds = predictions[mask]
    filtered_labels = y[mask]
    filtered_conf = confidences[mask]
    
    # Calculate accuracy
    correct = (filtered_preds == filtered_labels).sum()
    total = len(filtered_preds)
    win_rate = correct / total * 100 if total > 0 else 0
    
    # BUY/SELL win rates
    buy_mask = filtered_preds == 1
    sell_mask = filtered_preds == 2
    
    buy_correct = ((filtered_preds == 1) & (filtered_labels == 1)).sum()
    buy_total = buy_mask.sum()
    buy_win_rate = buy_correct / buy_total * 100 if buy_total > 0 else 0
    
    sell_correct = ((filtered_preds == 2) & (filtered_labels == 2)).sum()
    sell_total = sell_mask.sum()
    sell_win_rate = sell_correct / sell_total * 100 if sell_total > 0 else 0
    
    marker = " ⭐" if threshold == 55 else ""
    marker += " 🏆" if win_rate > best_win_rate and total > 50 else ""
    
    print(f"{threshold}%{marker:<8} {total:<8} {correct:<8} {win_rate:>6.1f}%    {buy_win_rate:>6.1f}%     {sell_win_rate:>6.1f}%")
    
    if win_rate > best_win_rate and total > 50:
        best_threshold = threshold
        best_win_rate = win_rate

print("\n" + "═"*70)
print("RECOMMENDATION")
print("═"*70)

print(f"\nCurrent Threshold: 55% ⭐")
print(f"Optimal Threshold: {best_threshold}% 🏆 ({best_win_rate:.1f}% win rate)")

if best_threshold < 55:
    print(f"\n⚠️  CURRENT THRESHOLD TOO HIGH!")
    print(f"   You're filtering out good trades at {best_threshold}%-54%")
    print(f"   Consider lowering to {best_threshold}%")
elif best_threshold > 55:
    print(f"\n⚠️  CURRENT THRESHOLD TOO LOW!")
    print(f"   Consider raising to {best_threshold}%")
else:
    print(f"\n✅ CURRENT THRESHOLD IS OPTIMAL!")

print("\n" + "═"*70)
