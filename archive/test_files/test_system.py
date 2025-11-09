#!/usr/bin/env python3
"""
Test script to verify the AI trading system is working
Tests all components before live trading
"""
import asyncio
import sys
from rich.console import Console
from rich.panel import Panel

console = Console()


async def test_imports():
    """Test that all modules can be imported"""
    console.print("\n[cyan]Testing imports...[/cyan]")

    try:
        from src.config import get_settings
        from src.agents.groq_market_analyzer import GroqMarketAnalyzer
        from src.data.indicators import TechnicalIndicators
        from src.brokers.paper_broker import PaperBroker
        from src.risk.position_sizer import PositionSizer
        from src.risk.prop_firm_compliance import PropFirmCompliance
        from src.trading_bot import AITradingBot

        console.print("[green]✓ All imports successful[/green]")
        return True

    except Exception as e:
        console.print(f"[red]✗ Import failed: {e}[/red]")
        return False


async def test_configuration():
    """Test configuration loading"""
    console.print("\n[cyan]Testing configuration...[/cyan]")

    try:
        from src.config import get_settings
        settings = get_settings()

        if not settings.groq_api_key:
            console.print("[red]✗ GROQ_API_KEY not set[/red]")
            return False

        console.print(f"[green]✓ Configuration loaded[/green]")
        console.print(f"  - LLM Provider: {settings.llm_provider}")
        console.print(f"  - Prop Firm: {settings.prop_firm}")
        console.print(f"  - Account Size: ${settings.account_size:,.2f}")
        return True

    except Exception as e:
        console.print(f"[red]✗ Configuration test failed: {e}[/red]")
        return False


async def test_groq_api():
    """Test Groq API connection"""
    console.print("\n[cyan]Testing Groq API connection...[/cyan]")

    try:
        from src.agents.groq_market_analyzer import GroqMarketAnalyzer

        analyzer = GroqMarketAnalyzer()

        # Simple test
        mock_indicators = {
            "price_action": {"open": 100, "high": 102, "low": 99, "close": 101, "change_pct": 1.0},
            "trend": {"sma_20": 100, "sma_50": 98, "ema_12": 101, "ema_26": 99},
            "momentum": {"rsi": 55, "macd": 0.5, "macd_signal": 0.3, "macd_hist": 0.2},
            "volatility": {"atr": 2.0, "bb_upper": 105, "bb_middle": 100, "bb_lower": 95, "bb_width": 10},
            "volume": {"current": 1000000, "average": 900000, "ratio": 1.1},
        }

        analysis = analyzer.analyze_market(
            symbol="TEST",
            current_price=101.0,
            technical_indicators=mock_indicators,
            timeframe="1H"
        )

        if "action" in analysis and "confidence" in analysis:
            console.print(f"[green]✓ Groq API working[/green]")
            console.print(f"  - Model: {analyzer.model}")
            console.print(f"  - Test analysis: {analysis['action']} (confidence: {analysis.get('confidence', 0):.1f}%)")
            return True
        else:
            console.print("[red]✗ Unexpected response format[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Groq API test failed: {e}[/red]")
        return False


async def test_broker():
    """Test paper broker"""
    console.print("\n[cyan]Testing paper broker...[/cyan]")

    try:
        from src.brokers.paper_broker import PaperBroker

        broker = PaperBroker(initial_balance=100000)

        # Test getting price
        price = await broker.get_current_price("SPY")

        if price and price > 0:
            console.print(f"[green]✓ Broker working[/green]")
            console.print(f"  - SPY current price: ${price:.2f}")
            return True
        else:
            console.print("[red]✗ Could not fetch price[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Broker test failed: {e}[/red]")
        return False


async def test_indicators():
    """Test technical indicators"""
    console.print("\n[cyan]Testing technical indicators...[/cyan]")

    try:
        from src.brokers.paper_broker import PaperBroker
        from src.data.indicators import TechnicalIndicators

        broker = PaperBroker(initial_balance=100000)
        hist_data = await broker.get_historical_data("SPY", period="5d", interval="1h")

        if hist_data is not None and not hist_data.empty:
            indicators = TechnicalIndicators.calculate_all(hist_data)

            console.print(f"[green]✓ Technical indicators working[/green]")
            console.print(f"  - RSI: {indicators['momentum']['rsi']:.1f}")
            console.print(f"  - SMA20: ${indicators['trend']['sma_20']:.2f}")
            console.print(f"  - ATR: ${indicators['volatility']['atr']:.2f}")
            return True
        else:
            console.print("[red]✗ Could not calculate indicators[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Indicator test failed: {e}[/red]")
        return False


async def test_compliance():
    """Test compliance engine"""
    console.print("\n[cyan]Testing compliance engine...[/cyan]")

    try:
        from src.risk.prop_firm_compliance import PropFirmCompliance

        compliance = PropFirmCompliance(
            prop_firm="FTMO",
            account_size=100000,
            account_type="challenge"
        )

        # Test trade validation
        test_trade = {
            "symbol": "SPY",
            "size": 100,
            "direction": "LONG",
            "risk_amount": 1000,
            "position_value": 50000,
        }

        status, message = await compliance.validate_trade(test_trade, [])

        console.print(f"[green]✓ Compliance engine working[/green]")
        console.print(f"  - Test trade status: {status.value}")
        return True

    except Exception as e:
        console.print(f"[red]✗ Compliance test failed: {e}[/red]")
        return False


async def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold cyan]AI Trading System - Component Tests[/bold cyan]",
        border_style="cyan"
    ))

    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Groq API", test_groq_api),
        ("Paper Broker", test_broker),
        ("Technical Indicators", test_indicators),
        ("Compliance Engine", test_compliance),
    ]

    results = []

    for test_name, test_func in tests:
        result = await test_func()
        results.append((test_name, result))

    # Summary
    console.print("\n" + "="*60)
    console.print("[bold cyan]Test Summary[/bold cyan]\n")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[green]✓ PASS[/green]" if result else "[red]✗ FAIL[/red]"
        console.print(f"{status} - {test_name}")

    console.print(f"\n[bold]Results: {passed}/{total} tests passed[/bold]")

    if passed == total:
        console.print("\n[bold green]✓ All tests passed! System is ready to trade.[/bold green]")
        console.print("\n[cyan]To start the trading bot, run:[/cyan]")
        console.print("[yellow]python -m src.main[/yellow]\n")
        return 0
    else:
        console.print("\n[bold red]✗ Some tests failed. Please fix issues before trading.[/bold red]\n")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
