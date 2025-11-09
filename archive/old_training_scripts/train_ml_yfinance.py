#!/usr/bin/env python3
"""
Train ML Model Using yfinance Historical Data
Maps forex symbols to equivalent ETF/currency pairs for training
"""
import yfinance as yf
import pandas as pd
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from datetime import datetime, timedelta

from src.ml.feature_engineering import FeatureEngineer
from src.ml.model_trainer import ModelTrainer
from src.data.indicators import TechnicalIndicators
from src.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


# Map forex pairs to yfinance tickers
FOREX_MAPPING = {
    'EURUSD': 'EURUSD=X',
    'GBPUSD': 'GBPUSD=X',
    'USDJPY': 'USDJPY=X',
    'AUDUSD': 'AUDUSD=X',
    'USDCAD': 'USDCAD=X',
    'USDCHF': 'USDCHF=X',
    'NZDUSD': 'NZDUSD=X',
    'EURJPY': 'EURJPY=X',
    'GBPJPY': 'GBPJPY=X',
    'EURGBP': 'EURGBP=X',
    'AUDJPY': 'AUDJPY=X',
    'EURAUD': 'EURAUD=X',
    'EURCHF': 'EURCHF=X',
    'EURCAD': 'EURCAD=X',
}


def collect_yfinance_data(symbols, period='6mo', interval='1h'):
    """
    Collect historical data from yfinance

    Args:
        symbols: List of forex pairs (e.g., ['EURUSD', 'GBPUSD'])
        period: How far back ('1mo', '3mo', '6mo', '1y', '2y')
        interval: Bar interval ('1h', '1d')

    Returns:
        Dict of {symbol: DataFrame}
    """
    console.print(f"\n[cyan]Downloading {period} of {interval} data from yfinance...[/cyan]\n")

    data = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Downloading...", total=len(symbols))

        for symbol in symbols:
            progress.update(task, description=f"Downloading {symbol}...")

            # Get yfinance ticker
            yf_ticker = FOREX_MAPPING.get(symbol, f"{symbol}=X")

            try:
                ticker = yf.Ticker(yf_ticker)
                df = ticker.history(period=period, interval=interval)

                if not df.empty and len(df) > 100:
                    # Standardize column names
                    df.columns = [col.lower() for col in df.columns]
                    df = df[['open', 'high', 'low', 'close', 'volume']]

                    data[symbol] = df
                    logger.info(f"✓ {symbol}: {len(df)} bars")
                else:
                    logger.warning(f"✗ {symbol}: No data")

            except Exception as e:
                logger.error(f"✗ {symbol}: {e}")

            progress.advance(task)

    console.print(f"\n[green]✓ Downloaded data for {len(data)}/{len(symbols)} symbols[/green]\n")
    return data


def label_trades(df, lookforward_bars=10, min_profit_pct=0.5):
    """
    Label each bar as buy/sell/hold based on future price movement

    Args:
        df: OHLCV dataframe
        lookforward_bars: How many bars ahead to check
        min_profit_pct: Minimum profit % to label as successful trade

    Returns:
        DataFrame with labels
    """
    labels = []

    for i in range(len(df) - lookforward_bars):
        current_price = df['close'].iloc[i]

        # Calculate ATR for stop loss
        atr_window = df['high'].iloc[max(0, i-14):i+1] - df['low'].iloc[max(0, i-14):i+1]
        atr = atr_window.mean() if len(atr_window) > 0 else current_price * 0.001

        # Look ahead
        future_prices = df['close'].iloc[i+1:i+1+lookforward_bars]

        if len(future_prices) < lookforward_bars:
            labels.append({'label_buy': 0, 'label_sell': 0, 'label_hold': 1})
            continue

        max_future = future_prices.max()
        min_future = future_prices.min()

        # Calculate potential profits
        buy_profit_pct = (max_future - current_price) / current_price * 100
        sell_profit_pct = (current_price - min_future) / current_price * 100

        # Check for stop loss (2 ATR)
        stop_distance = 2 * atr
        buy_stop_hit = (current_price - min_future) > stop_distance
        sell_stop_hit = (max_future - current_price) > stop_distance

        # Label
        if buy_profit_pct >= min_profit_pct and not buy_stop_hit:
            labels.append({'label_buy': 1, 'label_sell': 0, 'label_hold': 0})
        elif sell_profit_pct >= min_profit_pct and not sell_stop_hit:
            labels.append({'label_buy': 0, 'label_sell': 1, 'label_hold': 0})
        else:
            labels.append({'label_buy': 0, 'label_sell': 0, 'label_hold': 1})

    # Fill remaining rows with hold
    for _ in range(lookforward_bars):
        labels.append({'label_buy': 0, 'label_sell': 0, 'label_hold': 1})

    return pd.DataFrame(labels)


def extract_features_from_yfinance(symbol, df, sample_interval=10):
    """
    Extract features from yfinance data

    Args:
        symbol: Symbol name
        df: OHLCV dataframe
        sample_interval: Sample every N bars to avoid correlation

    Returns:
        DataFrame with features and labels
    """
    feature_engineer = FeatureEngineer()
    samples = []

    # Get multi-timeframe by resampling
    # H1 data -> resample to H4, D1
    df_h1 = df.copy()
    df_h4 = df.resample('4H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    df_d1 = df.resample('1D').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()

    # Sample every N bars
    for i in range(100, len(df_h1) - 10, sample_interval):
        try:
            # Get slice up to this point
            h1_slice = df_h1.iloc[:i+1].tail(100)

            # Find corresponding indices in other timeframes
            current_time = df_h1.index[i]
            h4_slice = df_h4[df_h4.index <= current_time].tail(100)
            d1_slice = df_d1[df_d1.index <= current_time].tail(100)

            if len(h1_slice) < 50 or len(h4_slice) < 20 or len(d1_slice) < 10:
                continue

            # Calculate indicators for each timeframe
            mtf_data = {
                'H1': h1_slice,
                'H4': h4_slice,
                'D1': d1_slice
            }

            mtf_indicators = {}
            for tf, data in mtf_data.items():
                mtf_indicators[tf] = TechnicalIndicators.calculate_all(data)

            # Extract features
            features = feature_engineer.extract_features(
                symbol=symbol,
                mtf_data=mtf_data,
                mtf_indicators=mtf_indicators
            )

            # Label this point based on next 10 bars
            # Pass the current bar + next 10 bars to label_trades
            label_df = df_h1.iloc[i:i+11].copy()
            labels = label_trades(label_df, lookforward_bars=10, min_profit_pct=0.3)

            # Combine
            sample = {**features, **labels.iloc[0].to_dict()}
            samples.append(sample)

        except Exception as e:
            logger.debug(f"Error at index {i}: {e}")
            continue

    return pd.DataFrame(samples)


def main():
    """Main training function"""

    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   ML MODEL TRAINING - YFINANCE DATA + LIVE LEARNING       [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # Major forex pairs for training
    symbols = [
        'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD',
        'USDCAD', 'USDCHF', 'NZDUSD', 'EURJPY',
        'GBPJPY', 'EURGBP', 'AUDJPY', 'EURAUD'
    ]

    console.print(f"[cyan]Training on {len(symbols)} major forex pairs[/cyan]")
    console.print(f"[dim]Data source: yfinance (6 months, 1-hour bars)[/dim]\n")

    # Step 1: Download data
    console.print("[bold]Step 1: Downloading historical data...[/bold]")
    yf_data = collect_yfinance_data(symbols, period='6mo', interval='1h')

    if not yf_data:
        console.print("[red]✗ Failed to download any data[/red]")
        return 1

    # Step 2: Extract features and labels
    console.print("\n[bold]Step 2: Extracting features and labeling trades...[/bold]")
    console.print("[dim]This will take 2-3 minutes...[/dim]\n")

    all_samples = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing...", total=len(yf_data))

        for symbol, df in yf_data.items():
            progress.update(task, description=f"Processing {symbol}...")

            samples_df = extract_features_from_yfinance(symbol, df, sample_interval=10)

            if not samples_df.empty:
                all_samples.append(samples_df)
                logger.info(f"  {symbol}: {len(samples_df)} training samples")

            progress.advance(task)

    if not all_samples:
        console.print("\n[red]✗ No training samples generated[/red]")
        return 1

    # Combine all samples
    training_data = pd.concat(all_samples, ignore_index=True)

    console.print(f"\n[green]✓ Generated {len(training_data)} total training samples[/green]")
    console.print(f"  Buy signals: {training_data['label_buy'].sum()}")
    console.print(f"  Sell signals: {training_data['label_sell'].sum()}")
    console.print(f"  Hold signals: {training_data['label_hold'].sum()}\n")

    # Step 3: Train model
    console.print("[bold]Step 3: Training Random Forest model...[/bold]")
    console.print("[dim]200 trees, cross-validation...[/dim]\n")

    trainer = ModelTrainer()
    metrics = trainer.train(training_data, test_size=0.2)

    # Display results
    console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]                 TRAINING COMPLETE                           [/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]\n")

    console.print("[bold]Model Performance:[/bold]")
    console.print(f"  Training Accuracy:  {metrics['train_accuracy']:.1%}")
    console.print(f"  Test Accuracy:      {metrics['test_accuracy']:.1%}")
    console.print(f"  Cross-Val Mean:     {metrics['cv_mean']:.1%} ±{metrics['cv_std']:.1%}")

    console.print(f"\n[bold]Top 10 Most Important Features:[/bold]")
    for idx, row in metrics['feature_importance'].head(10).iterrows():
        console.print(f"  {row['feature']:30s} {row['importance']:.4f}")

    console.print("\n[green]✓ Model saved to models/rf_model_latest.pkl[/green]")
    console.print("[green]✓ Ready for live trading with continuous learning![/green]\n")

    return 0


if __name__ == "__main__":
    exit(main())
