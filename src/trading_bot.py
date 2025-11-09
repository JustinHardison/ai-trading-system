"""
Main AI Trading Bot
Integrates all components and executes autonomous trading
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich import box

from .config import get_settings
from .agents.groq_market_analyzer import GroqMarketAnalyzer
from .data.indicators import TechnicalIndicators
from .brokers.paper_broker import PaperBroker
from .risk.position_sizer import PositionSizer, PositionSizingMethod
from .risk.prop_firm_compliance import PropFirmCompliance, ComplianceStatus
from .utils.logger import get_logger


logger = get_logger(__name__)
console = Console()


class AITradingBot:
    """
    Autonomous AI Trading Bot
    Analyzes markets, makes decisions, and executes trades
    """

    def __init__(self):
        self.settings = get_settings()

        # Initialize components
        self.analyzer = GroqMarketAnalyzer()
        self.broker = PaperBroker(initial_balance=self.settings.account_size)
        self.position_sizer = PositionSizer()
        self.compliance = PropFirmCompliance(
            prop_firm=self.settings.prop_firm,
            account_size=self.settings.account_size,
            account_type=self.settings.account_type,
        )

        # Trading state
        self.is_running = False
        self.symbols = self.settings.trading_symbols.split(",") if hasattr(self.settings, 'trading_symbols') else ["SPY"]
        self.scan_interval = 300  # Scan every 5 minutes
        self.last_scan_time = {}

        logger.info(f"AI Trading Bot initialized with {len(self.symbols)} symbols")
        logger.info(f"Symbols: {', '.join(self.symbols)}")

    async def start(self):
        """Start the trading bot"""
        self.is_running = True

        console.print("\n[bold green]🚀 AI Trading Bot Starting...[/bold green]\n")
        console.print(f"[cyan]Trading Symbols:[/cyan] {', '.join(self.symbols)}")
        console.print(f"[cyan]Account Size:[/cyan] ${self.settings.account_size:,.2f}")
        console.print(f"[cyan]Prop Firm:[/cyan] {self.settings.prop_firm}")
        console.print(f"[cyan]LLM Provider:[/cyan] {self.settings.llm_provider}")
        console.print(f"[cyan]Scan Interval:[/cyan] {self.scan_interval}s\n")

        try:
            # Main trading loop
            while self.is_running:
                await self._trading_cycle()
                await asyncio.sleep(10)  # Wait 10 seconds between cycles

        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Shutting down gracefully...[/yellow]")
            await self.stop()

        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            console.print(f"\n[red]❌ Error: {e}[/red]")
            await self.stop()

    async def stop(self):
        """Stop the trading bot"""
        self.is_running = False

        # Close all open positions
        if self.broker.positions:
            console.print("\n[yellow]Closing all open positions...[/yellow]")
            for symbol in list(self.broker.positions.keys()):
                current_price = await self.broker.get_current_price(symbol)
                if current_price:
                    self.broker.close_position(symbol, current_price, "shutdown")

        # Print final statistics
        await self._print_summary()

        console.print("\n[bold green]✓ Bot stopped successfully[/bold green]\n")

    async def _trading_cycle(self):
        """Execute one trading cycle"""
        current_time = datetime.now()

        # Update existing positions
        updates = await self.broker.update_positions()
        for update in updates:
            if update["action"] == "closed":
                self._record_trade(update["trade"])

        # Scan for new opportunities
        for symbol in self.symbols:
            # Check if enough time has passed since last scan
            last_scan = self.last_scan_time.get(symbol, datetime.min)
            if (current_time - last_scan).total_seconds() < self.scan_interval:
                continue

            self.last_scan_time[symbol] = current_time

            # Skip if already have position in this symbol
            if symbol in self.broker.positions:
                await self._manage_position(symbol)
                continue

            # Look for new opportunity
            await self._scan_symbol(symbol)

        # Display dashboard
        self._display_dashboard()

    async def _scan_symbol(self, symbol: str):
        """Scan a symbol for trading opportunities"""
        try:
            logger.info(f"Scanning {symbol}...")

            # Get current price
            current_price = await self.broker.get_current_price(symbol)
            if not current_price:
                logger.warning(f"Could not get price for {symbol}")
                return

            # Get historical data
            hist_data = await self.broker.get_historical_data(symbol, period="5d", interval="1h")
            if hist_data is None or hist_data.empty:
                logger.warning(f"No historical data for {symbol}")
                return

            # Calculate technical indicators
            indicators = TechnicalIndicators.calculate_all(hist_data)

            # Get LLM analysis
            analysis = self.analyzer.analyze_market(
                symbol=symbol,
                current_price=current_price,
                technical_indicators=indicators,
                timeframe="1H",
            )

            logger.info(f"{symbol} Analysis: {analysis.get('action')} - "
                       f"Confidence: {analysis.get('confidence', 0):.1f}% - "
                       f"{analysis.get('reasoning', 'No reasoning')}")

            # Check if should enter trade
            if analysis.get("action") not in ["BUY", "SELL"]:
                return

            if analysis.get("confidence", 0) < 65:
                logger.info(f"{symbol}: Confidence too low ({analysis.get('confidence')}%), skipping")
                return

            # Calculate position size
            entry_price = analysis.get("entry_price", current_price)
            stop_loss = analysis.get("stop_loss", entry_price * 0.98)

            # Get account status
            account = self.broker.get_account_status()

            position_info = self.position_sizer.calculate_position_size(
                method=PositionSizingMethod.FIXED_PERCENTAGE,
                account_balance=account["balance"],
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                max_position_size=self.settings.max_position_size,
            )

            if position_info["shares"] == 0:
                logger.warning(f"{symbol}: Position size calculated as 0, skipping")
                return

            # Create trade object for compliance check
            trade = {
                "symbol": symbol,
                "size": position_info["shares"],
                "direction": "LONG" if analysis["action"] == "BUY" else "SHORT",
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "risk_amount": position_info["risk_amount"],
                "position_value": position_info["position_value"],
            }

            # Check prop firm compliance
            status, message = await self.compliance.validate_trade(
                trade,
                self.broker.get_positions(),
            )

            if status == ComplianceStatus.REJECTED:
                logger.warning(f"{symbol}: Trade rejected by compliance - {message}")
                console.print(f"[yellow]⚠️  {symbol}: Trade rejected - {message}[/yellow]")
                return

            # Execute trade
            position_type = "LONG" if analysis["action"] == "BUY" else "SHORT"
            take_profit = analysis.get("take_profit", entry_price * 1.03)

            success, msg = self.broker.open_position(
                symbol=symbol,
                entry_price=entry_price,
                size=position_info["shares"],
                position_type=position_type,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

            if success:
                console.print(
                    f"\n[bold green]✓ Opened {position_type} position in {symbol}[/bold green]"
                )
                console.print(f"  Entry: ${entry_price:.2f} | Size: {position_info['shares']} shares")
                console.print(f"  Stop Loss: ${stop_loss:.2f} | Take Profit: ${take_profit:.2f}")
                console.print(f"  Reason: {analysis.get('reasoning', 'N/A')}\n")

                # Record trade with compliance engine
                self.compliance.record_trade(trade)
            else:
                logger.error(f"Failed to open position in {symbol}: {msg}")

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

    async def _manage_position(self, symbol: str):
        """Manage existing position - check if should close"""
        try:
            position = self.broker.positions.get(symbol)
            if not position:
                return

            # Get current price
            current_price = await self.broker.get_current_price(symbol)
            if not current_price:
                return

            # Get historical data for indicators
            hist_data = await self.broker.get_historical_data(symbol, period="2d", interval="1h")
            if hist_data is None or hist_data.empty:
                return

            # Calculate indicators
            indicators = TechnicalIndicators.calculate_all(hist_data)

            # Get hold time
            hold_time_hours = (datetime.now() - position.entry_time).total_seconds() / 3600

            # Ask LLM if should close
            decision = self.analyzer.should_close_position(
                symbol=symbol,
                entry_price=position.entry_price,
                current_price=current_price,
                position_type=position.position_type,
                hold_time_hours=hold_time_hours,
                technical_indicators=indicators,
            )

            if decision.get("action") == "CLOSE":
                success, msg, trade = self.broker.close_position(
                    symbol, current_price, decision.get("reasoning", "LLM decision")
                )

                if success:
                    console.print(
                        f"\n[bold yellow]→ Closed position in {symbol}[/bold yellow]"
                    )
                    console.print(f"  Exit: ${current_price:.2f}")
                    console.print(f"  P&L: ${trade['pnl']:+,.2f} ({trade['pnl_pct']:+.2f}%)")
                    console.print(f"  Reason: {decision.get('reasoning', 'N/A')}\n")

                    self._record_trade(trade)

        except Exception as e:
            logger.error(f"Error managing position in {symbol}: {e}")

    def _record_trade(self, trade: Dict):
        """Record closed trade with compliance engine"""
        # Update compliance engine
        self.compliance.update_account_balance(self.broker.balance)

        # Record with compliance
        compliance_trade = {
            "symbol": trade["symbol"],
            "pnl": trade["pnl"],
            "size": trade["size"],
        }
        self.compliance.record_trade(compliance_trade)

    def _display_dashboard(self):
        """Display live trading dashboard"""
        # Get account status
        account = self.broker.get_account_status()
        compliance_status = self.compliance.get_compliance_status()

        # Clear console and display
        console.clear()

        # Header
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]              AI TRADING BOT - LIVE DASHBOARD              [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

        # Account Info Table
        account_table = Table(title="Account Status", box=box.ROUNDED)
        account_table.add_column("Metric", style="cyan")
        account_table.add_column("Value", style="green")

        account_table.add_row("Balance", f"${account['balance']:,.2f}")
        account_table.add_row("Total Value", f"${account['total_value']:,.2f}")
        account_table.add_row(
            "Total P&L",
            f"[{'green' if account['total_pnl'] >= 0 else 'red'}]"
            f"${account['total_pnl']:+,.2f} ({account['total_pnl_pct']:+.2f}%)[/]"
        )
        account_table.add_row(
            "Daily P&L",
            f"[{'green' if account['daily_pnl'] >= 0 else 'red'}]"
            f"${account['daily_pnl']:+,.2f} ({account['daily_pnl_pct']:+.2f}%)[/]"
        )
        account_table.add_row(
            "Drawdown",
            f"[{'red' if account['drawdown_pct'] > 5 else 'yellow'}]"
            f"${account['drawdown']:,.2f} ({account['drawdown_pct']:.2f}%)[/]"
        )

        console.print(account_table)
        console.print()

        # Trading Stats Table
        stats_table = Table(title="Trading Statistics", box=box.ROUNDED)
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")

        stats_table.add_row("Total Trades", str(account['total_trades']))
        stats_table.add_row("Open Positions", str(account['open_positions']))
        stats_table.add_row("Win Rate", f"{account['win_rate']:.1f}%")
        stats_table.add_row("Profit Factor", f"{account['profit_factor']:.2f}")
        stats_table.add_row("Avg Win", f"${account['avg_win']:,.2f}")
        stats_table.add_row("Avg Loss", f"${account['avg_loss']:,.2f}")

        console.print(stats_table)
        console.print()

        # Compliance Status
        compliance_table = Table(title=f"{self.settings.prop_firm} Compliance", box=box.ROUNDED)
        compliance_table.add_column("Rule", style="cyan")
        compliance_table.add_column("Status", style="green")

        daily_loss_pct = compliance_status['daily_loss_used_pct']
        overall_loss_pct = compliance_status['overall_loss_used_pct']
        profit_pct = compliance_status['profit_target_achieved_pct']

        compliance_table.add_row(
            "Daily Loss Limit",
            f"[{'red' if daily_loss_pct > 80 else 'yellow' if daily_loss_pct > 50 else 'green'}]"
            f"{daily_loss_pct:.1f}% used[/]"
        )
        compliance_table.add_row(
            "Overall Loss Limit",
            f"[{'red' if overall_loss_pct > 80 else 'yellow' if overall_loss_pct > 50 else 'green'}]"
            f"{overall_loss_pct:.1f}% used[/]"
        )
        compliance_table.add_row(
            "Profit Target",
            f"[{'green' if profit_pct >= 100 else 'cyan'}]{profit_pct:.1f}% achieved[/]"
        )
        compliance_table.add_row("Trading Days", str(compliance_status['trading_days']))
        compliance_table.add_row(
            "Can Trade",
            f"[{'green' if compliance_status['can_trade'] else 'red'}]"
            f"{'✓ Yes' if compliance_status['can_trade'] else '✗ No'}[/]"
        )

        console.print(compliance_table)
        console.print()

        # Open Positions
        if self.broker.positions:
            positions_table = Table(title="Open Positions", box=box.ROUNDED)
            positions_table.add_column("Symbol", style="cyan")
            positions_table.add_column("Type", style="yellow")
            positions_table.add_column("Entry", style="white")
            positions_table.add_column("Size", style="white")
            positions_table.add_column("Stop Loss", style="red")
            positions_table.add_column("Take Profit", style="green")

            for symbol, pos in self.broker.positions.items():
                positions_table.add_row(
                    symbol,
                    pos.position_type,
                    f"${pos.entry_price:.2f}",
                    str(pos.size),
                    f"${pos.stop_loss:.2f}" if pos.stop_loss else "N/A",
                    f"${pos.take_profit:.2f}" if pos.take_profit else "N/A",
                )

            console.print(positions_table)
            console.print()

        # Footer
        console.print(f"[dim]Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]")
        console.print(f"[dim]Press Ctrl+C to stop[/dim]\n")

    async def _print_summary(self):
        """Print final summary"""
        account = self.broker.get_account_status()

        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold cyan]                    FINAL SUMMARY                          [/bold cyan]")
        console.print("[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]\n")

        console.print(f"[cyan]Initial Balance:[/cyan] ${self.settings.account_size:,.2f}")
        console.print(f"[cyan]Final Balance:[/cyan] ${account['total_value']:,.2f}")
        console.print(
            f"[cyan]Total P&L:[/cyan] [{'green' if account['total_pnl'] >= 0 else 'red'}]"
            f"${account['total_pnl']:+,.2f} ({account['total_pnl_pct']:+.2f}%)[/]"
        )
        console.print(f"[cyan]Total Trades:[/cyan] {account['total_trades']}")
        console.print(f"[cyan]Win Rate:[/cyan] {account['win_rate']:.1f}%")
        console.print(f"[cyan]Profit Factor:[/cyan] {account['profit_factor']:.2f}")
