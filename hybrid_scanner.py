#!/usr/bin/env python3
"""
Hybrid ML + LLM Market Scanner
Uses ML for fast filtering, LLM for intelligent validation
MUCH faster and smarter than pure LLM approach
"""
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
import time

from src.brokers.mt5_file_client import MT5FileClient
from src.agents.groq_market_analyzer import GroqMarketAnalyzer
from src.data.indicators import TechnicalIndicators
from src.ml.feature_engineering import FeatureEngineer
from src.ml.model_trainer import ModelTrainer
from src.utils.logger import get_logger
import pandas as pd

console = Console()
logger = get_logger(__name__)


@dataclass
class TradingOpportunity:
    """A validated trading opportunity"""
    symbol: str
    action: str
    ml_confidence: float
    llm_confidence: float
    final_confidence: float
    current_price: float
    score: float
    ml_reasoning: str
    llm_reasoning: str
    technical_signals: Dict


class HybridScanner:
    """
    Hybrid ML + LLM Scanner

    Stage 1: Technical Screener (instant) - reduces 10 symbols to ~5
    Stage 2: ML Classifier (fast) - reduces 5 to ~2-3 high confidence
    Stage 3: LLM Validator (smart) - validates final 2-3 trades

    Result: 95% reduction in LLM API calls, much faster, smarter decisions
    """

    def __init__(self):
        self.mt5 = MT5FileClient()
        self.feature_engineer = FeatureEngineer()
        self.ml_model = ModelTrainer()
        self.llm_analyzer = GroqMarketAnalyzer()
        self.opportunities: List[TradingOpportunity] = []

    def connect(self) -> bool:
        """Connect to MT5"""
        success, message = self.mt5.connect()
        if success:
            console.print("[green]✓ Connected to MT5[/green]")

            # Load ML model
            if self.ml_model.load_model():
                console.print("[green]✓ ML model loaded[/green]")
            else:
                console.print("[yellow]⚠ ML model not found - train it first with: python3 train_ml_model.py[/yellow]")
                return False
        else:
            console.print(f"[red]✗ Failed to connect: {message}[/red]")

        return success

    async def scan_markets(self, min_ml_confidence: float = 70.0):
        """
        Scan all markets with hybrid ML+LLM approach

        Args:
            min_ml_confidence: Minimum ML confidence to pass to LLM (70-80%)
        """
        start_time = time.time()

        console.print(Panel.fit(
            "[bold cyan]HYBRID ML + LLM MARKET SCANNER[/bold cyan]\n"
            "Stage 1: Technical Screener → Stage 2: ML Filter → Stage 3: LLM Validation",
            border_style="cyan"
        ))

        # Get all symbols
        symbols = self.mt5.get_all_symbols()

        if not symbols:
            console.print("[red]No symbols available[/red]")
            return

        console.print(f"\n[cyan]Found {len(symbols)} symbols[/cyan]\n")

        # STAGE 1: Technical Screener
        console.print("[bold]Stage 1: Technical Screener[/bold] [dim](instant)[/dim]")

        candidates = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Screening...", total=len(symbols))

            for symbol in symbols:
                progress.update(task, description=f"Screening {symbol}...")

                # Quick technical screen
                if self._technical_screen(symbol):
                    candidates.append(symbol)

                progress.advance(task)

        console.print(f"[green]✓ Technical screener: {len(candidates)} candidates[/green]")
        console.print(f"   Passed: {', '.join(candidates) if candidates else 'None'}\n")

        if not candidates:
            console.print("[yellow]No technical setups found[/yellow]")
            return

        # STAGE 2: ML Classification
        console.print("[bold]Stage 2: ML Classification[/bold] [dim](fast, local)[/dim]")

        ml_trades = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("ML analysis...", total=len(candidates))

            for symbol in candidates:
                progress.update(task, description=f"ML analyzing {symbol}...")

                # Get multi-timeframe data
                mtf_data, mtf_indicators = self._get_mtf_data(symbol)

                if not mtf_data:
                    progress.advance(task)
                    continue

                # Extract features
                features = self.feature_engineer.extract_features(
                    symbol=symbol,
                    mtf_data=mtf_data,
                    mtf_indicators=mtf_indicators
                )

                # ML prediction
                features_df = pd.DataFrame([features])
                ml_prediction = self.ml_model.predict(features_df)

                # Only pass high-confidence trades to LLM
                if ml_prediction['confidence'] >= min_ml_confidence and ml_prediction['action'] != 'hold':
                    ml_trades.append({
                        'symbol': symbol,
                        'action': ml_prediction['action'],
                        'confidence': ml_prediction['confidence'],
                        'probabilities': ml_prediction,
                        'mtf_data': mtf_data,
                        'mtf_indicators': mtf_indicators,
                        'current_price': mtf_data['H1']['close'].iloc[-1] if 'H1' in mtf_data else 0
                    })

                progress.advance(task)

        console.print(f"[green]✓ ML classifier: {len(ml_trades)} high-confidence trades (>{min_ml_confidence}%)[/green]")

        if ml_trades:
            for trade in ml_trades:
                console.print(f"   {trade['symbol']}: {trade['action'].upper()} @ {trade['confidence']:.1f}% confidence")
        console.print()

        if not ml_trades:
            console.print("[yellow]No high-confidence ML predictions[/yellow]")
            return

        # STAGE 3: LLM Validation
        console.print("[bold]Stage 3: LLM Validation[/bold] [dim](smart, context-aware)[/dim]\n")

        for idx, trade in enumerate(ml_trades, 1):
            console.print(f"[cyan]Validating trade {idx}/{len(ml_trades)}: {trade['symbol']}...[/cyan]")

            # LLM validates the ML decision
            llm_analysis = await self._llm_validate_trade(trade)

            if llm_analysis and llm_analysis.get('approved'):
                # Calculate final confidence (weighted average)
                final_confidence = (trade['confidence'] * 0.6 + llm_analysis['confidence'] * 0.4)

                opportunity = TradingOpportunity(
                    symbol=trade['symbol'],
                    action=trade['action'],
                    ml_confidence=trade['confidence'],
                    llm_confidence=llm_analysis['confidence'],
                    final_confidence=final_confidence,
                    current_price=trade['current_price'],
                    score=final_confidence,
                    ml_reasoning=f"ML: {trade['probabilities']}",
                    llm_reasoning=llm_analysis['reasoning'],
                    technical_signals=self._extract_signals(trade['mtf_indicators'])
                )

                self.opportunities.append(opportunity)
                console.print(f"[green]✓ APPROVED by LLM ({llm_analysis['confidence']:.1f}%)[/green]\n")
            else:
                reason = llm_analysis.get('reasoning', 'Unknown') if llm_analysis else 'LLM error'
                console.print(f"[red]✗ VETOED by LLM: {reason}[/red]\n")

        elapsed = time.time() - start_time

        # Sort by final confidence
        self.opportunities.sort(key=lambda x: x.final_confidence, reverse=True)

        # Display results
        self._display_results(elapsed, len(symbols), len(candidates), len(ml_trades))

    def _technical_screen(self, symbol: str) -> bool:
        """
        Fast technical screening
        Returns True if symbol has basic setup worth analyzing
        """
        try:
            # Get H1 data for quick check
            df = self.mt5.get_rates(symbol, 'H1', count=50)

            if df is None or len(df) < 50:
                return False

            # Calculate basic indicators
            indicators = TechnicalIndicators.calculate_all(df)

            # Screen for setups:
            rsi = indicators.get('rsi', 50)
            macd = indicators.get('macd', 0)
            macd_signal = indicators.get('macd_signal', 0)
            volume_ratio = indicators.get('volume_ratio', 1.0)

            # RSI extreme or MACD crossover with volume
            has_setup = (
                (rsi < 35 or rsi > 65) or  # RSI extreme
                (abs(macd - macd_signal) > 0.001) or  # Strong MACD
                (volume_ratio > 1.3)  # Volume spike
            )

            return has_setup

        except Exception as e:
            logger.debug(f"Error screening {symbol}: {e}")
            return False

    def _get_mtf_data(self, symbol: str) -> tuple:
        """Get multi-timeframe data and indicators"""
        try:
            timeframes = ['M15', 'M30', 'H1', 'H4', 'D1']
            mtf_data = {}
            mtf_indicators = {}

            for tf in timeframes:
                df = self.mt5.get_rates(symbol, tf, count=100)

                if df is not None and len(df) >= 50:
                    indicators = TechnicalIndicators.calculate_all(df)
                    mtf_data[tf] = df
                    mtf_indicators[tf] = indicators

            if len(mtf_data) >= 3:
                return mtf_data, mtf_indicators

            return {}, {}

        except Exception as e:
            logger.error(f"Error getting MTF data for {symbol}: {e}")
            return {}, {}

    async def _llm_validate_trade(self, trade: Dict) -> Optional[Dict]:
        """
        LLM validates ML decision with context and reasoning
        """
        try:
            # Build context summary for LLM
            context = self._build_trade_context(trade)

            # LLM validation prompt (NOT analysis - validation!)
            prompt = f"""You are validating a trade recommendation from an ML model.

TRADE RECOMMENDATION:
Symbol: {trade['symbol']}
ML Action: {trade['action'].upper()}
ML Confidence: {trade['confidence']:.1f}%
Current Price: ${trade['current_price']:.5f}

TECHNICAL SETUP:
{context}

Your task: Validate or VETO this trade.

Consider:
1. Is the technical setup reliable?
2. Are there any risks the ML model might have missed?
3. Is the timing good (market session, volatility)?
4. Does the multi-timeframe alignment support this?

Respond in JSON format:
{{
    "approved": true/false,
    "confidence": 0-100 (your confidence in this trade),
    "reasoning": "Brief explanation (max 100 chars)",
    "risk_level": "low/medium/high"
}}

Be strict. Only approve high-quality setups."""

            # Call LLM
            analysis = self.llm_analyzer.analyze_market(
                symbol=trade['symbol'],
                current_price=trade['current_price'],
                timeframe='H1',
                technical_indicators=trade['mtf_indicators'].get('H1', {}),
                custom_prompt=prompt
            )

            # Parse LLM response
            if analysis.get('action') in ['buy', 'sell'] and analysis.get('confidence', 0) > 60:
                return {
                    'approved': True,
                    'confidence': analysis.get('confidence', 70),
                    'reasoning': analysis.get('reasoning', 'LLM approved')[:100]
                }
            else:
                return {
                    'approved': False,
                    'confidence': 0,
                    'reasoning': 'LLM rejected: Low confidence or contradictory signals'
                }

        except Exception as e:
            logger.error(f"LLM validation error: {e}")
            return None

    def _build_trade_context(self, trade: Dict) -> str:
        """Build concise context summary for LLM"""
        lines = []

        # Multi-timeframe signals
        for tf in ['D1', 'H4', 'H1']:
            if tf in trade['mtf_indicators']:
                inds = trade['mtf_indicators'][tf]
                rsi = inds.get('rsi', 50)
                macd = inds.get('macd', 0)
                macd_sig = inds.get('macd_signal', 0)

                trend = "Bullish" if macd > macd_sig else "Bearish"
                lines.append(f"{tf}: RSI={rsi:.1f}, {trend}")

        return "\n".join(lines)

    def _extract_signals(self, mtf_indicators: Dict) -> Dict:
        """Extract key signals from multi-timeframe data"""
        signals = {}

        # Average RSI
        rsi_values = [ind.get('rsi', 50) for ind in mtf_indicators.values()]
        avg_rsi = sum(rsi_values) / len(rsi_values) if rsi_values else 50
        signals['avg_rsi'] = f"{avg_rsi:.1f}"

        # Trend consensus
        bullish = sum(1 for ind in mtf_indicators.values()
                     if ind.get('macd', 0) > ind.get('macd_signal', 0))
        signals['bullish_tfs'] = f"{bullish}/{len(mtf_indicators)}"

        return signals

    def _display_results(self, elapsed_time: float, total_symbols: int,
                        candidates: int, ml_trades: int):
        """Display final results"""
        console.print("\n" + "="*80)
        console.print("[bold cyan]HYBRID SCANNER RESULTS[/bold cyan]")
        console.print("="*80 + "\n")

        console.print("[bold]Performance:[/bold]")
        console.print(f"  Total scan time: {elapsed_time:.1f}s")
        console.print(f"  Stage 1 (Technical): {total_symbols} → {candidates} symbols")
        console.print(f"  Stage 2 (ML Filter): {candidates} → {ml_trades} trades")
        console.print(f"  Stage 3 (LLM Validation): {ml_trades} → {len(self.opportunities)} approved")
        console.print(f"  LLM API calls: {ml_trades} (vs {total_symbols * 5} with pure LLM)")
        console.print(f"  API reduction: {((total_symbols * 5 - ml_trades) / (total_symbols * 5) * 100):.1f}%\n")

        if not self.opportunities:
            console.print("[yellow]No approved opportunities found[/yellow]")
            return

        # Create table
        table = Table(title="Approved Trading Opportunities", show_header=True)
        table.add_column("Symbol", style="bold white", width=12)
        table.add_column("Action", style="yellow", width=8)
        table.add_column("ML", style="blue", width=10)
        table.add_column("LLM", style="green", width=10)
        table.add_column("Final", style="bold cyan", width=10)
        table.add_column("Price", style="white", width=12)
        table.add_column("Signals", style="dim", width=20)

        for opp in self.opportunities:
            action_color = "green" if opp.action == "buy" else "red"
            action_text = f"[{action_color}]{opp.action.upper()}[/{action_color}]"

            signals = ", ".join([f"{k}:{v}" for k, v in opp.technical_signals.items()])

            table.add_row(
                opp.symbol,
                action_text,
                f"{opp.ml_confidence:.1f}%",
                f"{opp.llm_confidence:.1f}%",
                f"[bold]{opp.final_confidence:.1f}%[/bold]",
                f"${opp.current_price:.5f}",
                signals
            )

        console.print(table)

        # Top recommendations
        if self.opportunities:
            console.print("\n[bold]🎯 FINAL RECOMMENDATIONS:[/bold]\n")

            for i, opp in enumerate(self.opportunities[:3], 1):
                action_emoji = "📈" if opp.action == "buy" else "📉"
                console.print(f"{action_emoji} [bold]{i}. {opp.symbol}[/bold] - {opp.action.upper()} @ ${opp.current_price:.5f}")
                console.print(f"   ML: {opp.ml_confidence:.1f}% | LLM: {opp.llm_confidence:.1f}% | Final: {opp.final_confidence:.1f}%")
                console.print(f"   ML: {opp.ml_reasoning}")
                console.print(f"   LLM: {opp.llm_reasoning}")
                console.print()

    def disconnect(self):
        """Disconnect from MT5"""
        self.mt5.disconnect()


async def main():
    """Main entry point"""

    scanner = HybridScanner()

    if not scanner.connect():
        return 1

    # Scan with hybrid approach
    await scanner.scan_markets(min_ml_confidence=70.0)

    scanner.disconnect()

    return 0


if __name__ == "__main__":
    asyncio.run(main())
