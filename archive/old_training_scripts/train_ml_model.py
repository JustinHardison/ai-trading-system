#!/usr/bin/env python3
"""
Train ML Model for Trade Classification
Collects historical data from MT5 and trains Random Forest classifier
"""
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src.brokers.mt5_file_client import MT5FileClient
from src.ml.data_collector import DataCollector
from src.ml.model_trainer import ModelTrainer

console = Console()


def main():
    """Train ML model"""

    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]         ML MODEL TRAINING FOR AI TRADING SYSTEM           [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

    # Connect to MT5
    console.print("[cyan]Step 1: Connecting to MT5...[/cyan]")
    mt5 = MT5FileClient()
    success, message = mt5.connect()

    if not success:
        console.print(f"[red]✗ Connection failed: {message}[/red]")
        return 1

    console.print("[green]✓ Connected to MT5[/green]\n")

    # Get available symbols
    console.print("[cyan]Step 2: Getting available symbols...[/cyan]")
    symbols = mt5.get_all_symbols()

    if not symbols:
        console.print("[red]✗ No symbols found[/red]")
        return 1

    console.print(f"[green]✓ Found {len(symbols)} symbols[/green]")
    console.print(f"   Symbols: {', '.join(symbols)}\n")

    # Collect training data
    console.print("[cyan]Step 3: Collecting historical training data...[/cyan]")
    console.print("[dim]   This will analyze 500 bars per symbol across 5 timeframes[/dim]")
    console.print("[dim]   This may take 5-10 minutes...[/dim]\n")

    collector = DataCollector(mt5_client=mt5)

    training_data = collector.collect_training_data(
        symbols=symbols,
        timeframes=['M15', 'M30', 'H1', 'H4', 'D1'],
        lookforward_bars=10,
        min_profit_pct=0.5  # 0.5% minimum profit to label as successful
    )

    if training_data.empty:
        console.print("[red]✗ Failed to collect training data[/red]")
        return 1

    console.print(f"[green]✓ Collected {len(training_data)} training samples[/green]\n")

    # Train model
    console.print("[cyan]Step 4: Training Random Forest classifier...[/cyan]")
    console.print("[dim]   200 trees, max depth 20, balanced class weights[/dim]\n")

    trainer = ModelTrainer()
    metrics = trainer.train(training_data, test_size=0.2)

    console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold green]                  TRAINING COMPLETE                          [/bold green]")
    console.print("[bold green]═══════════════════════════════════════════════════════════[/bold green]\n")

    console.print("[bold]Performance Metrics:[/bold]")
    console.print(f"  Training Accuracy:    {metrics['train_accuracy']:.1%}")
    console.print(f"  Test Accuracy:        {metrics['test_accuracy']:.1%}")
    console.print(f"  Cross-Val Mean:       {metrics['cv_mean']:.1%}")
    console.print(f"  Cross-Val Std:        {metrics['cv_std']:.1%}")

    console.print(f"\n[bold]Top 10 Most Important Features:[/bold]")
    for idx, row in metrics['feature_importance'].head(10).iterrows():
        console.print(f"  {row['feature']:30s} {row['importance']:.4f}")

    console.print("\n[green]✓ Model saved to models/rf_model_latest.pkl[/green]")
    console.print("[green]✓ Ready to use in hybrid ML+LLM scanner[/green]\n")

    # Disconnect
    mt5.disconnect()

    return 0


if __name__ == "__main__":
    exit(main())
