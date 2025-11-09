#!/usr/bin/env python3
"""
Test script to get all available symbols from MT5
"""
from rich.console import Console
from rich.table import Table

from src.brokers.mt5_file_client import MT5FileClient

console = Console()


def main():
    """Get all symbols from MT5"""

    console.print("[cyan]Connecting to MT5...[/cyan]")

    client = MT5FileClient()
    success, message = client.connect()

    if not success:
        console.print(f"[red]✗ Connection failed: {message}[/red]")
        return 1

    console.print(f"[green]✓ Connected[/green]\n")

    # Get all symbols
    console.print("[cyan]Getting all available symbols...[/cyan]")
    symbols = client.get_all_symbols()

    if not symbols:
        console.print("[red]✗ No symbols found[/red]")
        return 1

    console.print(f"[green]✓ Found {len(symbols)} symbols[/green]\n")

    # Display symbols in a table
    table = Table(title=f"MT5 Available Symbols ({len(symbols)} total)")
    table.add_column("#", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Type", style="yellow")

    for i, symbol in enumerate(symbols, 1):
        # Try to categorize
        if "USD" in symbol or "EUR" in symbol or "GBP" in symbol or "JPY" in symbol:
            symbol_type = "Forex"
        elif "XAU" in symbol or "XAG" in symbol:
            symbol_type = "Precious Metals"
        elif "WTI" in symbol or "BRENT" in symbol:
            symbol_type = "Energy"
        else:
            symbol_type = "Other"

        table.add_row(str(i), symbol, symbol_type)

    console.print(table)

    # Disconnect
    client.disconnect()

    return 0


if __name__ == "__main__":
    exit(main())
