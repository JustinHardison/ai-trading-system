#!/usr/bin/env python3
"""
Train ML Model using ONLY H1 + H4 data
Generates 54 features (27 per timeframe)
Matches what the EA actually sends
"""
import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console
from datetime import datetime
import pickle

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

from src.ml.feature_engineering import FeatureEngineer
from src.data.indicators import TechnicalIndicators

console = Console()

def download_us30_data():
    """Download US30 H1 and H4 data"""
    console.print("\n[cyan]📊 Downloading US30 data...[/cyan]\n")
    
    data = {}
    for tf, period in [('1h', '60d'), ('4h', '730d')]:
        ticker = yf.Ticker('^DJI')
        df = ticker.history(period=period, interval=tf)
        
        if not df.empty:
            timeframe_name = 'H1' if tf == '1h' else 'H4'
            data[timeframe_name] = df
            console.print(f"  ✓ {timeframe_name}: {len(df)} bars")
    
    return data

def label_trades(df, forward_bars=5, threshold=0.003):
    """Label trades: 0=HOLD, 1=BUY, 2=SELL"""
    labels = []
    
    for i in range(len(df) - forward_bars):
        current_price = df['Close'].iloc[i]
        future_prices = df['Close'].iloc[i+1:i+forward_bars+1]
        
        max_gain = (future_prices.max() - current_price) / current_price
        max_loss = (current_price - future_prices.min()) / current_price
        
        if max_gain > threshold and max_gain > max_loss * 1.5:
            labels.append(1)  # BUY
        elif max_loss > threshold and max_loss > max_gain * 1.5:
            labels.append(2)  # SELL
        else:
            labels.append(0)  # HOLD
    
    # Last bars = HOLD
    labels.extend([0] * forward_bars)
    
    return labels

# Download data
mtf_data = download_us30_data()

# Calculate indicators
console.print("\n[cyan]🔧 Calculating indicators...[/cyan]\n")
mtf_indicators = {}
for tf in ['H1', 'H4']:
    mtf_indicators[tf] = TechnicalIndicators.calculate_all(mtf_data[tf])

# Extract features using H1 as primary
console.print("[cyan]🔧 Engineering features (H1 + H4 only)...[/cyan]\n")
engineer = FeatureEngineer()

X_list = []
y_list = []

# Use H1 as primary timeframe
df_h1 = mtf_data['H1']
labels = label_trades(df_h1)

for i in range(50, len(df_h1)):  # Need history for indicators
    try:
        # Extract features at this point in time
        features = engineer.extract_features(
            symbol="US30Z25.sim",
            mtf_data={
                'H1': df_h1.iloc[:i+1],
                'H4': mtf_data['H4'].iloc[:i//4+1]  # Align H4 with H1
            },
            mtf_indicators={
                'H1': TechnicalIndicators.calculate_all(df_h1.iloc[:i+1]),
                'H4': TechnicalIndicators.calculate_all(mtf_data['H4'].iloc[:i//4+1])
            }
        )
        
        X_list.append(features)
        y_list.append(labels[i])
    except:
        continue

console.print(f"✓ Generated {len(X_list)} samples\n")

# Convert to DataFrame
X = pd.DataFrame(X_list)
y = np.array(y_list)

console.print(f"Features generated: {X.shape[1]}")
console.print(f"Feature names: {list(X.columns)}\n")

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train models
console.print("[cyan]🤖 Training models...[/cyan]\n")

models = {
    'GradientBoosting': GradientBoostingClassifier(n_estimators=200, max_depth=5, random_state=42),
    'RandomForest': RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
}

best_model = None
best_accuracy = 0
best_name = None

for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    console.print(f"  {name}: {accuracy:.3f}")
    
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        best_model = model
        best_name = name

console.print(f"\n[green]✓ Best Model: {best_name} ({best_accuracy:.3f})[/green]\n")

# Save model
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
model_path = f"models/us30_h1h4_only_{timestamp}.pkl"

model_data = {
    'model': best_model,
    'feature_names': list(X.columns),
    'accuracy': best_accuracy,
    'trained_on': timestamp
}

with open(model_path, 'wb') as f:
    pickle.dump(model_data, f)

# Update latest link
import os
os.system(f"cd models && rm -f us30_optimized_latest.pkl && ln -s us30_h1h4_only_{timestamp}.pkl us30_optimized_latest.pkl")

console.print(f"[green]✓ Model saved: {model_path}[/green]")
console.print(f"[green]✓ Updated: models/us30_optimized_latest.pkl[/green]\n")

# Classification report
console.print("\n[cyan]Classification Report:[/cyan]\n")
print(classification_report(y_test, model.predict(X_test), target_names=['HOLD', 'BUY', 'SELL']))

console.print("\n[green]✅ Training complete! Model ready for EA.[/green]\n")
