#!/usr/bin/env python3
"""
Train ML Model for US30 ONLY using yfinance
Uses multiple ML architectures and selects the best performer

US30 = Dow Jones Industrial Average (^DJI on yfinance)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from datetime import datetime, timedelta
import pickle
from pathlib import Path

# ML Models
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.preprocessing import StandardScaler

from src.ml.feature_engineering import FeatureEngineer
from src.data.indicators import TechnicalIndicators
from src.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


def download_us30_data(period='60d', timeframes=['1m', '5m', '15m', '30m', '1h']):
    """
    Download US30 (Dow Jones) data from yfinance

    NOTE: yfinance limits intraday data:
    - 1m data: max 7 days
    - 5m data: max 60 days
    - 15m, 30m, 1h: max 60 days

    Args:
        period: Historical period (limited for intraday)
        timeframes: List of timeframes to download

    Returns:
        Dict of {timeframe: DataFrame}
    """
    console.print(f"\n[cyan]📊 Downloading US30 ({period}) from yfinance...[/cyan]\n")

    data = {}
    ticker = yf.Ticker("^DJI")  # Dow Jones Industrial Average

    for tf in timeframes:
        try:
            console.print(f"[yellow]  • Fetching {tf} data...[/yellow]")
            df = ticker.history(period=period, interval=tf)

            if not df.empty and len(df) > 100:
                # Standardize column names
                df.columns = [col.lower() for col in df.columns]
                df = df[['open', 'high', 'low', 'close', 'volume']]
                data[tf] = df
                console.print(f"[green]    ✓ {tf}: {len(df)} bars[/green]")
            else:
                console.print(f"[red]    ✗ {tf}: No data[/red]")

        except Exception as e:
            console.print(f"[red]    ✗ {tf}: {e}[/red]")

    console.print(f"\n[green]✓ Downloaded {len(data)} timeframes[/green]\n")
    return data


def label_us30_trades(df, lookforward_bars=10, min_profit_points=50):
    """
    Label US30 bars as buy/sell/hold

    US30 moves in POINTS (e.g., 42,000 points)
    50 points = $5 per mini lot

    Args:
        df: OHLCV dataframe
        lookforward_bars: How many bars ahead to check
        min_profit_points: Minimum profit in US30 points (not %)

    Returns:
        DataFrame with labels
    """
    df = df.copy()
    df['label_buy'] = 0
    df['label_sell'] = 0

    for i in range(len(df) - lookforward_bars):
        current_price = df['close'].iloc[i]
        future_prices = df['close'].iloc[i+1:i+1+lookforward_bars]

        max_future = future_prices.max()
        min_future = future_prices.min()

        # Calculate point movements (US30 is in points, not %)
        upside_points = max_future - current_price
        downside_points = current_price - min_future

        # Label based on point movements
        if upside_points >= min_profit_points and upside_points > downside_points * 1.5:
            df.loc[df.index[i], 'label_buy'] = 1
        elif downside_points >= min_profit_points and downside_points > upside_points * 1.5:
            df.loc[df.index[i], 'label_sell'] = 1

    return df


def build_training_dataset(data, lookforward_bars=10, min_profit_points=50):
    """
    Build training dataset from US30 multi-timeframe data

    Args:
        data: Dict of {timeframe: DataFrame}
        lookforward_bars: Bars to look ahead for labeling
        min_profit_points: Minimum profit in US30 points

    Returns:
        DataFrame with features and labels
    """
    console.print("\n[cyan]🔧 Building training dataset...[/cyan]\n")

    # Map yfinance keys to MT5 format (FeatureEngineer expects M15, M30, H1, H4, D1)
    tf_mapping = {
        '15m': 'M15',
        '30m': 'M30',
        '1h': 'H1',
        '4h': 'H4',
        '1d': 'D1'
    }

    # Remap data keys
    data_mt5 = {tf_mapping.get(k, k): v for k, v in data.items()}

    # Use H1 as primary timeframe
    if 'H1' not in data_mt5:
        console.print("[red]Error: 1h data required![/red]")
        return None

    df_h1 = data_mt5['H1'].copy()

    # Label the data
    console.print("[yellow]  • Labeling trades...[/yellow]")
    df_labeled = label_us30_trades(df_h1, lookforward_bars, min_profit_points)

    # Calculate indicators for all timeframes (using MT5 keys)
    console.print("[yellow]  • Calculating indicators...[/yellow]")
    mtf_indicators = {}
    for tf, df in data_mt5.items():
        if len(df) >= 50:
            mtf_indicators[tf] = TechnicalIndicators.calculate_all(df)

    # Extract features
    console.print("[yellow]  • Engineering features...[/yellow]")
    feature_engineer = FeatureEngineer()

    all_features = []
    for i in range(100, len(df_labeled) - lookforward_bars):  # Skip first 100 for indicators
        try:
            # Get slice of data up to this point (using MT5 keys)
            mtf_data_slice = {}
            for tf, df in data_mt5.items():
                # Align indices - find closest timestamp
                ts = df_labeled.index[i]
                closest_idx = df.index.get_indexer([ts], method='nearest')[0]
                if closest_idx >= 50:  # Need history for indicators
                    mtf_data_slice[tf] = df.iloc[:closest_idx+1]

            # Extract features for this point (now with correct 75 features)
            features = feature_engineer.extract_features(
                symbol='US30',
                mtf_data=mtf_data_slice,
                mtf_indicators={tf: TechnicalIndicators.calculate_all(df)
                               for tf, df in mtf_data_slice.items()}
            )

            # Add labels
            features['label_buy'] = df_labeled['label_buy'].iloc[i]
            features['label_sell'] = df_labeled['label_sell'].iloc[i]

            all_features.append(features)

        except Exception as e:
            continue

    training_df = pd.DataFrame(all_features)

    # Remove rows with NaN
    training_df = training_df.dropna()

    console.print(f"\n[green]✓ Built training dataset: {len(training_df)} samples[/green]")

    # Class distribution
    buy_count = training_df['label_buy'].sum()
    sell_count = training_df['label_sell'].sum()
    hold_count = len(training_df) - buy_count - sell_count

    console.print(f"[cyan]  • Buy signals: {buy_count} ({buy_count/len(training_df)*100:.1f}%)[/cyan]")
    console.print(f"[cyan]  • Sell signals: {sell_count} ({sell_count/len(training_df)*100:.1f}%)[/cyan]")
    console.print(f"[cyan]  • Hold: {hold_count} ({hold_count/len(training_df)*100:.1f}%)[/cyan]\n")

    return training_df


def train_multiple_models(training_df):
    """
    Train multiple ML models and select best performer

    Tests:
    - Random Forest (current)
    - Gradient Boosting
    - Neural Network (MLP)

    Returns:
        Best model and metrics
    """
    console.print("\n[cyan]🤖 Training multiple ML models...[/cyan]\n")

    # Separate features and labels
    feature_cols = [col for col in training_df.columns if not col.startswith('label_')]
    X = training_df[feature_cols].fillna(0)

    # Multi-class labels: 0=hold, 1=buy, 2=sell
    y = np.zeros(len(training_df))
    y[training_df['label_buy'] == 1] = 1
    y[training_df['label_sell'] == 1] = 2

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Define models to test
    models = {
        'Random Forest': RandomForestClassifier(
            n_estimators=300,  # Increased from 200
            max_depth=25,      # Increased from 20
            min_samples_split=8,
            min_samples_leaf=4,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
            class_weight='balanced'
        ),
        'Gradient Boosting': GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=10,
            min_samples_split=10,
            min_samples_leaf=5,
            subsample=0.8,
            random_state=42
        ),
        'Neural Network': MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            alpha=0.001,
            learning_rate='adaptive',
            max_iter=500,
            random_state=42,
            early_stopping=True
        )
    }

    results = {}

    for name, model in models.items():
        console.print(f"[yellow]  • Training {name}...[/yellow]")

        # Train
        model.fit(X_train_scaled, y_train)

        # Evaluate
        train_score = model.score(X_train_scaled, y_train)
        test_score = model.score(X_test_scaled, y_test)

        # Cross-validation
        cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5)

        # Predictions
        y_pred = model.predict(X_test_scaled)

        results[name] = {
            'model': model,
            'train_score': train_score,
            'test_score': test_score,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'predictions': y_pred
        }

        console.print(f"[green]    ✓ {name}:[/green]")
        console.print(f"[green]      - Test accuracy: {test_score:.3f}[/green]")
        console.print(f"[green]      - CV mean: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})[/green]\n")

    # Select best model based on test accuracy
    best_name = max(results, key=lambda k: results[k]['test_score'])
    best_model = results[best_name]['model']

    console.print(f"\n[bold green]🏆 Best Model: {best_name}[/bold green]")
    console.print(f"[bold green]   Test Accuracy: {results[best_name]['test_score']:.3f}[/bold green]\n")

    # Detailed report for best model
    y_pred = results[best_name]['predictions']
    console.print("[cyan]Classification Report (Best Model):[/cyan]")
    print(classification_report(y_test, y_pred, target_names=['Hold', 'Buy', 'Sell']))

    console.print("[cyan]Confusion Matrix:[/cyan]")
    print(confusion_matrix(y_test, y_pred))

    return best_model, scaler, feature_cols, results


def save_model(model, scaler, feature_names, model_name='us30_optimized'):
    """Save trained model"""
    model_dir = Path("models")
    model_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = model_dir / f"{model_name}_{timestamp}.pkl"

    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'trained_on': 'US30_only',
        'timestamp': timestamp
    }

    with open(filename, 'wb') as f:
        pickle.dump(model_data, f)

    # Create symlink to latest
    latest_link = model_dir / f"{model_name}_latest.pkl"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(filename.name)

    console.print(f"\n[green]✓ Model saved: {filename}[/green]")
    console.print(f"[green]✓ Latest link: {latest_link}[/green]\n")

    return filename


def main():
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]       US30-ONLY ML MODEL TRAINER (Optimized)[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # Step 1: Download US30 data (M5, M15, M30, H1, H4 - 5 timeframes)
    # NOTE: yfinance limits: 1m=7d, 5m/15m/30m=60d, 1h=2y, 1d=max
    # Using M5 as fastest timeframe (M1 only has 7 days = insufficient data)
    data = download_us30_data(period='2y', timeframes=['5m', '15m', '30m', '1h', '4h'])

    if not data:
        console.print("[red]Failed to download data![/red]")
        return

    # Step 2: Build training dataset
    training_df = build_training_dataset(
        data,
        lookforward_bars=10,
        min_profit_points=50  # 50 points = reasonable move for US30
    )

    if training_df is None or len(training_df) < 1000:
        console.print("[red]Insufficient training data![/red]")
        return

    # Step 3: Train multiple models and select best
    best_model, scaler, feature_names, results = train_multiple_models(training_df)

    # Step 4: Save best model
    save_model(best_model, scaler, feature_names, model_name='us30_optimized')

    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]                  TRAINING COMPLETE![/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]\n")


if __name__ == '__main__':
    main()
