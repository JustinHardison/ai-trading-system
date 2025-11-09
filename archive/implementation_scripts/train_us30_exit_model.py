#!/usr/bin/env python3
"""
Train AI EXIT MODEL for US30
Learns when to HOLD, TAKE_PROFIT, or STOP_LOSS based on position state

This replaces hardcoded ATR-based exits with intelligent AI decisions.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console
from datetime import datetime
import pickle
from pathlib import Path

# ML Models
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler

from src.data.indicators import TechnicalIndicators

console = Console()


def download_us30_data(period='2y', interval='1h'):
    """Download US30 data for exit training"""
    console.print(f"\n[cyan]📊 Downloading US30 ({period}, {interval}) for exit training...[/cyan]\n")

    ticker = yf.Ticker("^DJI")
    df = ticker.history(period=period, interval=interval)

    if not df.empty:
        df.columns = [col.lower() for col in df.columns]
        df = df[['open', 'high', 'low', 'close', 'volume']]
        console.print(f"[green]✓ Downloaded {len(df)} bars[/green]\n")
        return df

    console.print("[red]Failed to download data![/red]")
    return None


def simulate_trades_and_label_exits(df, lookforward_bars=20):
    """
    Simulate US30 trades and label optimal exit points

    For each bar, simulate entering a trade and determine:
    - HOLD: Position is favorable, keep it open
    - TAKE_PROFIT: Profit target reached, close now
    - STOP_LOSS: Position moving against us, exit to prevent losses

    Args:
        df: OHLCV DataFrame
        lookforward_bars: How many bars ahead to analyze

    Returns:
        DataFrame with exit labels and features
    """
    console.print("[cyan]🔧 Simulating trades and labeling exits...[/cyan]\n")

    samples = []

    for i in range(100, len(df) - lookforward_bars):
        entry_price = df['close'].iloc[i]
        entry_bar = i

        # Simulate LONG position
        for bars_held in range(1, min(lookforward_bars, len(df) - i)):
            current_bar = i + bars_held
            current_price = df['close'].iloc[current_bar]
            highest_since_entry = df['high'].iloc[i:current_bar+1].max()
            lowest_since_entry = df['low'].iloc[i:current_bar+1].min()

            # Calculate position metrics
            profit_points = current_price - entry_price
            profit_pct = (profit_points / entry_price) * 100
            max_profit_points = highest_since_entry - entry_price
            max_loss_points = entry_price - lowest_since_entry

            # Look ahead to see what WOULD happen
            future_bars = df.iloc[current_bar:current_bar+10]
            if len(future_bars) < 5:
                continue

            future_high = future_bars['high'].max()
            future_low = future_bars['low'].min()

            future_profit = future_high - current_price
            future_loss = current_price - future_low

            # Determine optimal action
            # TAKE_PROFIT: If profit is good and future shows reversal risk
            if profit_points > 50 and future_loss > future_profit * 1.5:
                action = 'TAKE_PROFIT'
            # STOP_LOSS: If losing and future shows more downside
            elif profit_points < -30 and future_loss > future_profit:
                action = 'STOP_LOSS'
            # HOLD: Position is favorable
            elif future_profit > future_loss * 1.2:
                action = 'HOLD'
            else:
                action = 'HOLD'

            # Extract features for this exit decision point
            sample = extract_exit_features(
                df=df,
                current_bar=current_bar,
                entry_price=entry_price,
                current_price=current_price,
                bars_held=bars_held,
                profit_points=profit_points,
                profit_pct=profit_pct,
                max_profit_points=max_profit_points,
                max_loss_points=max_loss_points,
                direction='LONG'
            )

            sample['exit_action'] = action
            samples.append(sample)

        # Simulate SHORT position
        for bars_held in range(1, min(lookforward_bars, len(df) - i)):
            current_bar = i + bars_held
            current_price = df['close'].iloc[current_bar]
            highest_since_entry = df['high'].iloc[i:current_bar+1].max()
            lowest_since_entry = df['low'].iloc[i:current_bar+1].min()

            # Calculate position metrics (SHORT)
            profit_points = entry_price - current_price
            profit_pct = (profit_points / entry_price) * 100
            max_profit_points = entry_price - lowest_since_entry
            max_loss_points = highest_since_entry - entry_price

            # Look ahead
            future_bars = df.iloc[current_bar:current_bar+10]
            if len(future_bars) < 5:
                continue

            future_high = future_bars['high'].max()
            future_low = future_bars['low'].min()

            future_profit = current_price - future_low
            future_loss = future_high - current_price

            # Determine optimal action for SHORT
            if profit_points > 50 and future_loss > future_profit * 1.5:
                action = 'TAKE_PROFIT'
            elif profit_points < -30 and future_loss > future_profit:
                action = 'STOP_LOSS'
            elif future_profit > future_loss * 1.2:
                action = 'HOLD'
            else:
                action = 'HOLD'

            sample = extract_exit_features(
                df=df,
                current_bar=current_bar,
                entry_price=entry_price,
                current_price=current_price,
                bars_held=bars_held,
                profit_points=profit_points,
                profit_pct=profit_pct,
                max_profit_points=max_profit_points,
                max_loss_points=max_loss_points,
                direction='SHORT'
            )

            sample['exit_action'] = action
            samples.append(sample)

    exit_df = pd.DataFrame(samples)
    console.print(f"[green]✓ Created {len(exit_df)} exit samples[/green]\n")

    # Show distribution
    for action in ['HOLD', 'TAKE_PROFIT', 'STOP_LOSS']:
        count = (exit_df['exit_action'] == action).sum()
        pct = count / len(exit_df) * 100
        console.print(f"[cyan]  • {action}: {count} ({pct:.1f}%)[/cyan]")

    return exit_df


def extract_exit_features(df, current_bar, entry_price, current_price,
                         bars_held, profit_points, profit_pct,
                         max_profit_points, max_loss_points, direction):
    """Extract features for exit decision"""

    # Position features
    features = {
        'direction': 1 if direction == 'LONG' else -1,
        'bars_held': bars_held,
        'profit_points': profit_points,
        'profit_pct': profit_pct,
        'max_profit_points': max_profit_points,
        'max_loss_points': max_loss_points,
        'price_vs_entry': (current_price / entry_price - 1) * 100,
    }

    # Current market conditions
    recent_df = df.iloc[max(0, current_bar-50):current_bar+1]
    indicators = TechnicalIndicators.calculate_all(recent_df)

    features['rsi'] = indicators.get('rsi', 50)
    features['macd'] = indicators.get('macd', 0)
    features['macd_signal'] = indicators.get('macd_signal', 0)
    features['atr'] = indicators.get('atr', 0)
    features['bb_upper'] = indicators.get('bb_upper', current_price)
    features['bb_lower'] = indicators.get('bb_lower', current_price)
    features['bb_middle'] = indicators.get('bb_middle', current_price)

    # Volatility
    if len(recent_df) >= 20:
        features['volatility_20'] = recent_df['close'].pct_change().std() * 100
    else:
        features['volatility_20'] = 0

    # Trend strength
    if len(recent_df) >= 50:
        ema20 = recent_df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = recent_df['close'].ewm(span=50).mean().iloc[-1]
        features['trend_strength'] = (ema20 / ema50 - 1) * 100
    else:
        features['trend_strength'] = 0

    # Price momentum
    if len(recent_df) >= 10:
        features['momentum_10'] = (recent_df['close'].iloc[-1] / recent_df['close'].iloc[-10] - 1) * 100
    else:
        features['momentum_10'] = 0

    # Volume
    if len(recent_df) >= 20:
        features['volume_ratio'] = recent_df['volume'].iloc[-1] / recent_df['volume'].rolling(20).mean().iloc[-1]
    else:
        features['volume_ratio'] = 1.0

    # Bollinger Band position
    if features['bb_upper'] != features['bb_lower']:
        features['bb_position'] = (current_price - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
    else:
        features['bb_position'] = 0.5

    # Max adverse excursion (MAE) - how much it went against us
    if direction == 'LONG':
        features['mae_points'] = max_loss_points
        features['mae_pct'] = (max_loss_points / entry_price) * 100 if entry_price > 0 else 0
    else:
        features['mae_points'] = max_loss_points
        features['mae_pct'] = (max_loss_points / entry_price) * 100 if entry_price > 0 else 0

    # Max favorable excursion (MFE) - how much profit we had
    features['mfe_points'] = max_profit_points
    features['mfe_pct'] = (max_profit_points / entry_price) * 100 if entry_price > 0 else 0

    return features


def train_exit_model(exit_df):
    """Train AI model to predict optimal exit action"""
    console.print("\n[cyan]🤖 Training exit decision model...[/cyan]\n")

    # Separate features and labels
    feature_cols = [col for col in exit_df.columns if col != 'exit_action']
    X = exit_df[feature_cols].fillna(0)

    # Convert actions to numeric: 0=HOLD, 1=TAKE_PROFIT, 2=STOP_LOSS
    y = exit_df['exit_action'].map({'HOLD': 0, 'TAKE_PROFIT': 1, 'STOP_LOSS': 2})

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train multiple models
    models = {
        'Random Forest': RandomForestClassifier(
            n_estimators=300,
            max_depth=20,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        ),
        'Gradient Boosting': GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=8,
            min_samples_split=15,
            min_samples_leaf=8,
            subsample=0.8,
            random_state=42
        )
    }

    results = {}

    for name, model in models.items():
        console.print(f"[yellow]  • Training {name}...[/yellow]")

        model.fit(X_train_scaled, y_train)

        test_score = model.score(X_test_scaled, y_test)
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)

        y_pred = model.predict(X_test_scaled)

        results[name] = {
            'model': model,
            'test_score': test_score,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'predictions': y_pred
        }

        console.print(f"[green]    ✓ {name}: {test_score:.3f} accuracy[/green]")
        console.print(f"[green]      CV: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})[/green]\n")

    # Select best model
    best_name = max(results, key=lambda k: results[k]['test_score'])
    best_model = results[best_name]['model']

    console.print(f"\n[bold green]🏆 Best Exit Model: {best_name}[/bold green]")
    console.print(f"[bold green]   Accuracy: {results[best_name]['test_score']:.3f}[/bold green]\n")

    # Detailed report
    y_pred = results[best_name]['predictions']
    console.print("[cyan]Classification Report:[/cyan]")
    print(classification_report(y_test, y_pred, target_names=['HOLD', 'TAKE_PROFIT', 'STOP_LOSS']))

    console.print("[cyan]Confusion Matrix:[/cyan]")
    print(confusion_matrix(y_test, y_pred))

    return best_model, scaler, feature_cols


def save_exit_model(model, scaler, feature_names):
    """Save exit model"""
    model_dir = Path("models")
    model_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = model_dir / f"us30_exit_model_{timestamp}.pkl"

    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'model_type': 'exit_decision',
        'trained_on': 'US30_exits',
        'timestamp': timestamp
    }

    with open(filename, 'wb') as f:
        pickle.dump(model_data, f)

    # Create symlink to latest
    latest_link = model_dir / "us30_exit_model_latest.pkl"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(filename.name)

    console.print(f"\n[green]✓ Exit model saved: {filename}[/green]")
    console.print(f"[green]✓ Latest link: {latest_link}[/green]\n")

    return filename


def main():
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]       US30 AI EXIT MODEL TRAINER[/bold cyan]")
    console.print("[bold cyan]       Learns WHEN to exit positions[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # Step 1: Download US30 data
    df = download_us30_data(period='2y', interval='1h')
    if df is None or len(df) < 500:
        console.print("[red]Insufficient data![/red]")
        return

    # Step 2: Simulate trades and label exits
    exit_df = simulate_trades_and_label_exits(df, lookforward_bars=20)
    if exit_df is None or len(exit_df) < 1000:
        console.print("[red]Insufficient exit samples![/red]")
        return

    # Step 3: Train exit model
    exit_model, scaler, feature_names = train_exit_model(exit_df)

    # Step 4: Save model
    save_exit_model(exit_model, scaler, feature_names)

    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]       EXIT MODEL TRAINING COMPLETE![/bold green]")
    console.print("[bold green]       AI now decides WHEN to exit positions[/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]\n")


if __name__ == '__main__':
    main()
