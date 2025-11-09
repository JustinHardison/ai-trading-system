#!/usr/bin/env python3
"""
Intelligent Market Scanner
Scans ALL available MT5 symbols and ranks them by trading opportunity
The AI decides which are the best trades
"""
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from src.brokers.mt5_file_client import MT5FileClient
from src.agents.groq_market_analyzer import GroqMarketAnalyzer
from src.data.indicators import TechnicalIndicators
from src.utils.logger import get_logger

console = Console()
logger = get_logger(__name__)


@dataclass
class MarketOpportunity:
    """A ranked trading opportunity"""
    symbol: str
    action: str  # buy, sell, or hold
    confidence: float
    current_price: float
    score: float  # Overall opportunity score
    reasoning: str
    technical_signals: Dict


class IntelligentScanner:
    """
    Scans all available symbols and ranks trading opportunities
    """

    def __init__(self):
        self.mt5 = MT5FileClient()
        self.analyzer = GroqMarketAnalyzer()
        self.opportunities: List[MarketOpportunity] = []

    def connect(self) -> bool:
        """Connect to MT5"""
        success, message = self.mt5.connect()
        if success:
            console.print("[green]✓ Connected to MT5[/green]")
        else:
            console.print(f"[red]✗ Failed to connect: {message}[/red]")
        return success

    async def scan_all_symbols(self, timeframe: str = "H1", min_confidence: float = 60.0):
        """
        Scan all available symbols and rank opportunities

        Args:
            timeframe: Chart timeframe to analyze
            min_confidence: Minimum confidence threshold for trading
        """
        console.print(Panel.fit(
            "[bold cyan]Intelligent Market Scanner[/bold cyan]\n"
            "Scanning ALL available symbols to find the best trades",
            border_style="cyan"
        ))

        # Get all symbols
        symbols = self.mt5.get_all_symbols()

        if not symbols:
            console.print("[red]No symbols available[/red]")
            return

        console.print(f"\n[cyan]Found {len(symbols)} symbols to analyze[/cyan]\n")

        # Scan each symbol
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:

            task = progress.add_task("Scanning markets...", total=len(symbols))

            for symbol in symbols:
                progress.update(task, description=f"Analyzing {symbol}...")

                opportunity = await self._analyze_symbol(symbol, timeframe)
                if opportunity:
                    self.opportunities.append(opportunity)

                progress.advance(task)

        # Sort by score (highest first)
        self.opportunities.sort(key=lambda x: x.score, reverse=True)

        # Display results
        self._display_opportunities(min_confidence)

    async def _analyze_symbol(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[MarketOpportunity]:
        """
        Analyze a single symbol across MULTIPLE timeframes
        This gives the AI a complete picture for better decisions
        """

        try:
            # Analyze ALL timeframes for this symbol
            timeframes = ["M15", "M30", "H1", "H4", "D1"]
            all_analyses = {}
            all_indicators = {}
            current_price = 0

            for tf in timeframes:
                # Get historical data for this timeframe
                df = self.mt5.get_rates(symbol, tf, count=100)

                if df is None or df.empty or len(df) < 50:
                    continue

                # Calculate indicators
                indicators = TechnicalIndicators.calculate_all(df)
                current_price = df['close'].iloc[-1]

                # Get AI analysis for this timeframe
                analysis = self.analyzer.analyze_market(
                    symbol=symbol,
                    current_price=current_price,
                    timeframe=tf,
                    technical_indicators=indicators
                )

                all_analyses[tf] = analysis
                all_indicators[tf] = indicators

            if not all_analyses:
                logger.debug(f"No data for {symbol}")
                return None

            # Combine multi-timeframe analysis
            combined_analysis = self._combine_timeframe_analyses(all_analyses)

            # Calculate opportunity score using ALL timeframes
            score = self._calculate_mtf_opportunity_score(
                all_analyses,
                all_indicators
            )

            return MarketOpportunity(
                symbol=symbol,
                action=combined_analysis['action'],
                confidence=combined_analysis['confidence'],
                current_price=current_price,
                score=score,
                reasoning=combined_analysis['reasoning'],
                technical_signals=self._extract_mtf_signals(all_indicators)
            )

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    def _combine_timeframe_analyses(self, analyses: Dict) -> Dict:
        """
        Combine analyses from multiple timeframes
        Higher timeframes get more weight
        """
        # Weight by timeframe importance
        weights = {
            "M15": 0.1,
            "M30": 0.15,
            "H1": 0.25,
            "H4": 0.3,
            "D1": 0.2
        }

        # Count votes for each action
        buy_score = 0
        sell_score = 0
        total_confidence = 0
        all_reasoning = []

        for tf, analysis in analyses.items():
            weight = weights.get(tf, 0.2)
            action = analysis.get('action', 'hold')
            confidence = analysis.get('confidence', 0)

            if action == 'buy':
                buy_score += confidence * weight
            elif action == 'sell':
                sell_score += confidence * weight

            total_confidence += confidence * weight
            all_reasoning.append(f"{tf}: {action.upper()}")

        # Determine final action
        if buy_score > sell_score and buy_score > 30:
            final_action = 'buy'
            final_confidence = buy_score
        elif sell_score > buy_score and sell_score > 30:
            final_action = 'sell'
            final_confidence = sell_score
        else:
            final_action = 'hold'
            final_confidence = total_confidence / len(analyses) if analyses else 0

        reasoning = f"Multi-TF: {', '.join(all_reasoning)}"

        return {
            'action': final_action,
            'confidence': min(final_confidence, 100),
            'reasoning': reasoning
        }

    def _calculate_mtf_opportunity_score(
        self,
        analyses: Dict,
        indicators: Dict
    ) -> float:
        """
        Calculate opportunity score using MULTIPLE timeframes
        Better accuracy than single timeframe
        """
        score = 0.0

        # Multi-timeframe agreement (0-40 points)
        actions = [a.get('action') for a in analyses.values()]
        buy_count = actions.count('buy')
        sell_count = actions.count('sell')
        max_agreement = max(buy_count, sell_count)

        if max_agreement >= 4:  # 4+ timeframes agree
            score += 40
        elif max_agreement >= 3:  # 3 timeframes agree
            score += 30
        elif max_agreement >= 2:  # 2 timeframes agree
            score += 20

        # Average confidence (0-30 points)
        avg_confidence = sum(a.get('confidence', 0) for a in analyses.values()) / len(analyses)
        score += (avg_confidence / 100) * 30

        # Technical strength across timeframes (0-30 points)
        technical_score = 0

        for tf, inds in indicators.items():
            # RSI alignment
            if 'rsi' in inds:
                rsi = inds['rsi']
                if rsi < 30:  # Oversold across timeframes
                    technical_score += 5
                elif rsi > 70:  # Overbought across timeframes
                    technical_score += 5

            # Trend alignment (MACD)
            if 'macd' in inds and 'macd_signal' in inds:
                if abs(inds['macd'] - inds['macd_signal']) > 0.001:
                    technical_score += 5

        score += min(technical_score, 30)

        return min(score, 100.0)

    def _extract_mtf_signals(self, indicators: Dict) -> Dict:
        """Extract signals from multiple timeframes"""
        signals = {}

        # Trend direction across timeframes
        trend_count = {'bullish': 0, 'bearish': 0}

        for tf, inds in indicators.items():
            if 'macd' in inds and 'macd_signal' in inds:
                if inds['macd'] > inds['macd_signal']:
                    trend_count['bullish'] += 1
                else:
                    trend_count['bearish'] += 1

        if trend_count['bullish'] > trend_count['bearish']:
            signals['trend'] = f"Bullish ({trend_count['bullish']}/{len(indicators)} TFs)"
        elif trend_count['bearish'] > trend_count['bullish']:
            signals['trend'] = f"Bearish ({trend_count['bearish']}/{len(indicators)} TFs)"
        else:
            signals['trend'] = "Mixed"

        # RSI consensus
        rsi_values = [inds.get('rsi', 50) for inds in indicators.values() if 'rsi' in inds]
        if rsi_values:
            avg_rsi = sum(rsi_values) / len(rsi_values)
            if avg_rsi < 30:
                signals['rsi'] = f"Oversold ({avg_rsi:.1f})"
            elif avg_rsi > 70:
                signals['rsi'] = f"Overbought ({avg_rsi:.1f})"
            else:
                signals['rsi'] = f"Neutral ({avg_rsi:.1f})"

        return signals

    def _calculate_opportunity_score(
        self,
        analysis: Dict,
        indicators: Dict
    ) -> float:
        """
        Calculate overall opportunity score (0-100)
        Combines AI confidence, technical strength, and risk/reward
        """
        score = 0.0

        # AI confidence (0-50 points)
        confidence = analysis.get('confidence', 0)
        score += (confidence / 100) * 50

        # Action weight (hold = 0, buy/sell = +20)
        if analysis.get('action') in ['buy', 'sell']:
            score += 20

        # Technical alignment (0-30 points)
        technical_score = 0

        # RSI extremes are good
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30 or rsi > 70:  # Oversold or overbought
                technical_score += 10

        # Strong trend (MACD)
        if 'macd' in indicators and 'macd_signal' in indicators:
            macd_diff = abs(indicators['macd'] - indicators['macd_signal'])
            if macd_diff > 0.001:  # Strong momentum
                technical_score += 10

        # Volume confirmation
        if 'volume_sma' in indicators:
            volume_ratio = indicators.get('volume_ratio', 1.0)
            if volume_ratio > 1.2:  # Above average volume
                technical_score += 10

        score += technical_score

        return min(score, 100.0)

    def _extract_signals(self, indicators: Dict) -> Dict:
        """Extract key technical signals"""
        signals = {}

        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if rsi < 30:
                signals['rsi_signal'] = 'Oversold'
            elif rsi > 70:
                signals['rsi_signal'] = 'Overbought'
            else:
                signals['rsi_signal'] = 'Neutral'

        if 'macd' in indicators and 'macd_signal' in indicators:
            if indicators['macd'] > indicators['macd_signal']:
                signals['macd_signal'] = 'Bullish'
            else:
                signals['macd_signal'] = 'Bearish'

        return signals

    def _display_opportunities(self, min_confidence: float):
        """Display ranked opportunities"""

        console.print("\n" + "="*80)
        console.print("[bold cyan]MARKET OPPORTUNITIES RANKED BY SCORE[/bold cyan]")
        console.print("="*80 + "\n")

        # Filter by minimum confidence
        tradeable = [opp for opp in self.opportunities if opp.confidence >= min_confidence]

        if not tradeable:
            console.print(f"[yellow]No opportunities found with confidence >= {min_confidence}%[/yellow]\n")
            console.print("[dim]Showing all opportunities:[/dim]\n")
            tradeable = self.opportunities[:5]  # Show top 5 anyway

        # Create table
        table = Table(title="Top Trading Opportunities", show_header=True)
        table.add_column("Rank", style="cyan", width=6)
        table.add_column("Symbol", style="bold white", width=12)
        table.add_column("Action", style="yellow", width=8)
        table.add_column("Score", style="green", width=8)
        table.add_column("Confidence", style="blue", width=12)
        table.add_column("Price", style="white", width=12)
        table.add_column("Signals", style="dim", width=20)

        for i, opp in enumerate(tradeable[:10], 1):  # Top 10
            # Color action
            action_color = "green" if opp.action == "buy" else "red" if opp.action == "sell" else "dim"
            action_text = f"[{action_color}]{opp.action.upper()}[/{action_color}]"

            # Format signals
            signals = ", ".join([f"{k}: {v}" for k, v in opp.technical_signals.items()])

            # Confidence color
            conf_color = "green" if opp.confidence >= 70 else "yellow" if opp.confidence >= 50 else "red"

            table.add_row(
                f"#{i}",
                opp.symbol,
                action_text,
                f"{opp.score:.1f}",
                f"[{conf_color}]{opp.confidence:.1f}%[/{conf_color}]",
                f"${opp.current_price:.5f}",
                signals
            )

        console.print(table)

        # Show top 3 recommendations
        if len(tradeable) > 0:
            console.print("\n[bold]🎯 TOP 3 RECOMMENDED TRADES:[/bold]\n")

            for i, opp in enumerate(tradeable[:3], 1):
                action_emoji = "📈" if opp.action == "buy" else "📉" if opp.action == "sell" else "⏸️"
                console.print(f"{action_emoji} [bold]{i}. {opp.symbol}[/bold] - {opp.action.upper()} @ ${opp.current_price:.5f}")
                console.print(f"   Score: {opp.score:.1f}/100 | Confidence: {opp.confidence:.1f}%")
                console.print(f"   Reasoning: {opp.reasoning[:100]}...")
                console.print()

    def disconnect(self):
        """Disconnect from MT5"""
        self.mt5.disconnect()


async def main():
    """Main entry point"""

    scanner = IntelligentScanner()

    if not scanner.connect():
        return 1

    # Scan all symbols
    await scanner.scan_all_symbols(
        timeframe="H1",
        min_confidence=60.0  # Only show high-confidence trades
    )

    scanner.disconnect()

    return 0


if __name__ == "__main__":
    asyncio.run(main())
