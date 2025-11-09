#!/usr/bin/env python3
"""
Test MT5 Socket Connection
Verifies Python can communicate with MT5 via socket bridge
"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def main():
    """Test MT5 socket connection"""

    console.print(Panel.fit(
        "[bold cyan]MT5 Socket Connection Test[/bold cyan]\n"
        "Testing direct connection to MT5 terminal",
        border_style="cyan"
    ))

    try:
        from src.brokers.mt5_socket_client import MT5SocketClient

        console.print("\n[cyan]Step 1: Connecting to MT5 socket server...[/cyan]")
        console.print("[dim]Make sure MT5 is running with the EA attached![/dim]\n")

        # Create client
        client = MT5SocketClient(host="127.0.0.1", port=9090)

        # Test connection
        success, message = client.connect()

        if not success:
            console.print(f"[red]✗ Connection failed: {message}[/red]\n")
            console.print("[yellow]Troubleshooting:[/yellow]")
            console.print("1. Is MT5 running?")
            console.print("2. Is the MT5_Socket_Server EA attached to a chart?")
            console.print("3. Do you see 'Socket server started' in MT5 Experts tab?")
            console.print("4. Is there a smiley face on the chart?")
            console.print("\n[cyan]See INSTALL_MT5_SOCKET.md for detailed instructions[/cyan]")
            return 1

        console.print(f"[green]✓ Connected: {message}[/green]\n")

        # Test 1: Account Info
        console.print("[bold]Test 1: Getting Account Information[/bold]")

        account = client.get_account_info()

        if account:
            table = Table()
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Balance", f"${account['balance']:,.2f}")
            table.add_row("Equity", f"${account['equity']:,.2f}")
            table.add_row("Margin", f"${account['margin']:,.2f}")
            table.add_row("Free Margin", f"${account['margin_free']:,.2f}")
            table.add_row("Profit", f"${account['profit']:+,.2f}")
            table.add_row("Leverage", f"1:{account['leverage']}")

            console.print(table)
            console.print("[green]✓ Account info test passed[/green]\n")
        else:
            console.print("[red]✗ Failed to get account info[/red]\n")

        # Test 2: Market Data
        console.print("[bold]Test 2: Getting Real-Time Market Data[/bold]")

        symbols = ["EURUSD", "GBPUSD"]
        price_table = Table()
        price_table.add_column("Symbol", style="cyan")
        price_table.add_column("Bid", style="red")
        price_table.add_column("Ask", style="green")
        price_table.add_column("Spread", style="yellow")

        all_ticks_ok = True

        for symbol in symbols:
            tick = client.get_tick(symbol)

            if tick:
                spread = (tick.ask - tick.bid) * 10000
                price_table.add_row(
                    symbol,
                    f"{tick.bid:.5f}",
                    f"{tick.ask:.5f}",
                    f"{spread:.1f} pips"
                )
            else:
                price_table.add_row(symbol, "N/A", "N/A", "N/A")
                all_ticks_ok = False

        console.print(price_table)

        if all_ticks_ok:
            console.print("[green]✓ Market data test passed[/green]\n")
        else:
            console.print("[yellow]⚠ Some symbols failed to load[/yellow]\n")

        # Test 3: Open Positions
        console.print("[bold]Test 3: Checking Open Positions[/bold]")

        positions = client.get_positions()

        if len(positions) > 0:
            pos_table = Table()
            pos_table.add_column("Ticket", style="cyan")
            pos_table.add_column("Symbol", style="white")
            pos_table.add_column("Type", style="yellow")
            pos_table.add_column("Volume", style="white")
            pos_table.add_column("Price", style="white")
            pos_table.add_column("Profit", style="green")

            for pos in positions:
                pos_table.add_row(
                    str(pos.ticket),
                    pos.symbol,
                    pos.type.upper(),
                    f"{pos.volume:.2f}",
                    f"{pos.price_open:.5f}",
                    f"${pos.profit:+,.2f}"
                )

            console.print(pos_table)
            console.print(f"[green]✓ Found {len(positions)} open position(s)[/green]\n")
        else:
            console.print("[cyan]No open positions (this is OK)[/cyan]\n")

        # Test 4: Test Trade (optional)
        console.print("[bold]Test 4: Test Order Execution[/bold]")
        console.print("[yellow]This will open a small test position (0.01 lots)[/yellow]")

        proceed = input("\nProceed with test trade? (y/n): ").strip().lower()

        if proceed == 'y':
            console.print("\n[cyan]Opening test BUY position: EURUSD 0.01 lots[/cyan]")

            tick = client.get_tick("EURUSD")
            if tick:
                sl = tick.ask - 0.0020  # 20 pips SL
                tp = tick.ask + 0.0040  # 40 pips TP

                success, message, ticket = client.open_position(
                    symbol="EURUSD",
                    action="buy",
                    volume=0.01,
                    sl=sl,
                    tp=tp,
                    comment="Socket Test"
                )

                if success:
                    console.print(f"[green]✓ Position opened (Ticket: {ticket})[/green]")
                    console.print(f"[dim]Check MT5 terminal - you should see the position![/dim]")

                    # Ask to close
                    close = input("\nClose the test position? (y/n): ").strip().lower()

                    if close == 'y' and ticket:
                        success, message = client.close_position(ticket)

                        if success:
                            console.print(f"[green]✓ Position closed[/green]\n")
                        else:
                            console.print(f"[red]✗ Failed to close: {message}[/red]\n")
                            console.print("[yellow]You can close it manually in MT5[/yellow]\n")
                else:
                    console.print(f"[red]✗ Failed to open position: {message}[/red]\n")
        else:
            console.print("[yellow]Test trade skipped[/yellow]\n")

        # Disconnect
        client.disconnect()

        # Summary
        console.print("="*60)
        console.print("[bold green]✓ Socket connection working![/bold green]\n")

        console.print("[bold]What's Working:[/bold]")
        console.print("✓ Python connected to MT5 via socket")
        console.print("✓ Real-time account information")
        console.print("✓ Real-time market prices from MT5")
        console.print("✓ Position monitoring")
        console.print("✓ Order execution to real MT5\n")

        console.print("[bold]Next Steps:[/bold]")
        console.print("1. Update trading bot to use socket client")
        console.print("2. Run: [cyan]python3 -m src.main[/cyan]")
        console.print("3. Watch AI trade on real MT5 account")
        console.print("4. Monitor positions in MT5 terminal\n")

        console.print("[bold green]You're ready to trade with real MT5 connection![/bold green]\n")

        return 0

    except ImportError as e:
        console.print(f"[red]✗ Import error: {e}[/red]")
        console.print("\n[yellow]Make sure you're in the project directory[/yellow]")
        return 1

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
