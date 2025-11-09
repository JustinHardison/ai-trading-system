#!/usr/bin/env python3
"""
Pre-Installation Verification Script
Checks that all required files are present before installing MT5 EA
"""
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def main():
    """Verify installation files"""

    console.print(Panel.fit(
        "[bold cyan]MT5 Socket Bridge - Installation Verification[/bold cyan]\n"
        "Checking all files before installation",
        border_style="cyan"
    ))

    # Files to check
    required_files = {
        "MT5 Expert Advisor": "MT5_Socket_Server.mq5",
        "Python Socket Client": "src/brokers/mt5_socket_client.py",
        "Test Script": "test_mt5_socket.py",
        "Installation Guide": "INSTALL_MT5_SOCKET.md",
        "macOS Setup Guide": "MT5_MACOS_SETUP.md",
    }

    # Check files
    table = Table(title="File Verification")
    table.add_column("Component", style="cyan")
    table.add_column("File", style="white")
    table.add_column("Status", style="green")

    all_present = True

    for component, filename in required_files.items():
        file_path = Path(filename)
        if file_path.exists():
            status = "✓ Found"
            style = "green"
        else:
            status = "✗ Missing"
            style = "red"
            all_present = False

        table.add_row(component, filename, f"[{style}]{status}[/{style}]")

    console.print(table)
    console.print()

    if all_present:
        console.print("[bold green]✓ All files present![/bold green]\n")

        # Show next steps
        console.print("[bold]Next Steps:[/bold]\n")
        console.print("1. Open MT5 terminal on your Mac")
        console.print("2. Follow the instructions in [cyan]INSTALL_MT5_SOCKET.md[/cyan]")
        console.print("3. The key steps are:")
        console.print("   • Go to [yellow]File → Open Data Folder[/yellow] in MT5")
        console.print("   • Copy [cyan]MT5_Socket_Server.mq5[/cyan] to the [yellow]MQL5/Experts/[/yellow] folder")
        console.print("   • Press [yellow]F4[/yellow] in MT5 to open MetaEditor")
        console.print("   • Compile the EA ([yellow]F7[/yellow])")
        console.print("   • Go to [yellow]Tools → Options → Expert Advisors[/yellow]")
        console.print("   • Enable [yellow]'Allow algorithmic trading'[/yellow]")
        console.print("   • Drag the EA onto any chart")
        console.print("4. Look for [green]'Socket server started on port 9090'[/green] in Experts tab")
        console.print("5. Run: [cyan]python3 test_mt5_socket.py[/cyan]\n")

        # Show absolute path to EA file
        ea_path = Path("MT5_Socket_Server.mq5").absolute()
        console.print(Panel(
            f"[bold]MT5 EA File Location:[/bold]\n{ea_path}\n\n"
            "[dim]You'll need to copy this file to your MT5 Experts folder[/dim]",
            border_style="yellow",
            title="Important"
        ))

    else:
        console.print("[bold red]✗ Some files are missing![/bold red]")
        console.print("[yellow]Please ensure all files were created correctly[/yellow]")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
