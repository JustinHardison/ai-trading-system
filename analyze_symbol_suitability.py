#!/usr/bin/env python3
"""
Analyze which symbols are best suited for the AI trading strategy
Based on: volatility, liquidity, trend characteristics, and ML predictability
"""
import pandas as pd
import numpy as np
import glob
import os
from datetime import datetime

class SymbolAnalyzer:
    """Analyze symbol characteristics for trading suitability"""
    
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.symbol = os.path.basename(csv_file).replace('_m1_historical_data.csv', '').upper()
        self.df = None
        self.metrics = {}
        
    def load_data(self):
        """Load historical data"""
        try:
            self.df = pd.read_csv(self.csv_file)
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df = self.df.sort_values('timestamp').reset_index(drop=True)
            return True
        except Exception as e:
            print(f"❌ {self.symbol}: Failed to load - {e}")
            return False
            
    def calculate_volatility(self):
        """Calculate various volatility metrics"""
        close = self.df['close'].values
        high = self.df['high'].values
        low = self.df['low'].values
        
        # ATR (Average True Range)
        tr = np.maximum(high - low, 
                       np.maximum(abs(high - np.roll(close, 1)),
                                 abs(low - np.roll(close, 1))))
        atr_20 = pd.Series(tr).rolling(20).mean().iloc[-1]
        
        # Percentage volatility
        returns = np.diff(close) / close[:-1]
        daily_vol = returns.std() * np.sqrt(1440)  # Annualized from M1
        
        # Average daily range
        daily_range = ((high - low) / close).mean() * 100
        
        self.metrics['atr_20'] = atr_20
        self.metrics['daily_volatility_pct'] = daily_vol * 100
        self.metrics['avg_daily_range_pct'] = daily_range
        
    def calculate_liquidity(self):
        """Estimate liquidity from volume and spread"""
        volume = self.df['volume'].values
        
        # Average volume
        avg_volume = volume.mean()
        
        # Volume consistency (lower std = more consistent)
        volume_std = volume.std() / avg_volume if avg_volume > 0 else 999
        
        # Estimate spread from high-low
        high = self.df['high'].values
        low = self.df['low'].values
        close = self.df['close'].values
        avg_spread_pct = ((high - low) / close).mean() * 100
        
        self.metrics['avg_volume'] = avg_volume
        self.metrics['volume_consistency'] = 1 / (1 + volume_std)  # Higher = better
        self.metrics['avg_spread_pct'] = avg_spread_pct
        
    def calculate_trend_characteristics(self):
        """Analyze trending vs ranging behavior"""
        close = self.df['close'].values
        
        # Moving averages
        sma_20 = pd.Series(close).rolling(20).mean()
        sma_50 = pd.Series(close).rolling(50).mean()
        
        # Trend strength (how often price is above/below MA)
        above_sma20 = (close > sma_20).sum() / len(close)
        trend_clarity = abs(above_sma20 - 0.5) * 2  # 0 = ranging, 1 = strong trend
        
        # Directional movement
        up_moves = (np.diff(close) > 0).sum()
        down_moves = (np.diff(close) < 0).sum()
        directional_bias = abs(up_moves - down_moves) / len(close)
        
        # Trend consistency (ADX-like)
        returns = np.diff(close) / close[:-1]
        positive_dm = np.where(returns > 0, returns, 0)
        negative_dm = np.where(returns < 0, abs(returns), 0)
        
        avg_pos_dm = positive_dm.mean()
        avg_neg_dm = negative_dm.mean()
        
        if avg_pos_dm + avg_neg_dm > 0:
            trend_strength = abs(avg_pos_dm - avg_neg_dm) / (avg_pos_dm + avg_neg_dm)
        else:
            trend_strength = 0
            
        self.metrics['trend_clarity'] = trend_clarity
        self.metrics['directional_bias'] = directional_bias
        self.metrics['trend_strength'] = trend_strength
        
    def calculate_ml_predictability(self):
        """Estimate how predictable the symbol might be for ML"""
        close = self.df['close'].values
        
        # Autocorrelation (momentum)
        returns = np.diff(close) / close[:-1]
        
        # Lag-1 autocorrelation
        if len(returns) > 1:
            autocorr_1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        else:
            autocorr_1 = 0
            
        # Pattern consistency (how often similar patterns repeat)
        # Simple version: look at return distribution
        return_bins = pd.cut(returns, bins=10)
        pattern_consistency = 1 - (return_bins.value_counts().std() / return_bins.value_counts().mean())
        
        # Signal-to-noise ratio
        signal = abs(returns.mean())
        noise = returns.std()
        snr = signal / noise if noise > 0 else 0
        
        # Mean reversion tendency
        mean_price = close.mean()
        mean_reversion = ((close - mean_price) * np.roll(close - mean_price, 1) < 0).sum() / len(close)
        
        self.metrics['autocorrelation'] = autocorr_1
        self.metrics['pattern_consistency'] = pattern_consistency
        self.metrics['signal_noise_ratio'] = snr
        self.metrics['mean_reversion'] = mean_reversion
        
    def calculate_trading_opportunity(self):
        """Estimate trading opportunity frequency"""
        close = self.df['close'].values
        high = self.df['high'].values
        low = self.df['low'].values
        
        # Average move size
        avg_move = ((high - low) / close).mean() * 100
        
        # Frequency of significant moves (>0.5% range)
        significant_moves = ((high - low) / close > 0.005).sum() / len(close)
        
        # Intraday momentum (how often price continues in same direction)
        returns = np.diff(close)
        momentum_continuation = (returns[:-1] * returns[1:] > 0).sum() / len(returns)
        
        self.metrics['avg_move_pct'] = avg_move
        self.metrics['significant_move_freq'] = significant_moves
        self.metrics['momentum_continuation'] = momentum_continuation
        
    def analyze(self):
        """Run all analyses"""
        if not self.load_data():
            return None
            
        self.calculate_volatility()
        self.calculate_liquidity()
        self.calculate_trend_characteristics()
        self.calculate_ml_predictability()
        self.calculate_trading_opportunity()
        
        # Calculate overall suitability score
        self.calculate_suitability_score()
        
        return self.metrics
        
    def calculate_suitability_score(self):
        """Calculate overall suitability score for AI trading"""
        
        # Volatility score (moderate is best)
        vol_score = 1 - abs(self.metrics['daily_volatility_pct'] - 2.0) / 5.0
        vol_score = max(0, min(1, vol_score))
        
        # Liquidity score (higher is better)
        liquidity_score = self.metrics['volume_consistency']
        
        # Trend score (moderate trending is best)
        trend_score = self.metrics['trend_strength'] * 0.5 + self.metrics['trend_clarity'] * 0.5
        
        # ML predictability score
        ml_score = (
            abs(self.metrics['autocorrelation']) * 0.3 +
            self.metrics['pattern_consistency'] * 0.3 +
            self.metrics['signal_noise_ratio'] * 0.2 +
            self.metrics['mean_reversion'] * 0.2
        )
        
        # Trading opportunity score
        opportunity_score = (
            min(self.metrics['avg_move_pct'] / 2.0, 1.0) * 0.5 +
            self.metrics['significant_move_freq'] * 0.5
        )
        
        # Overall score (weighted average)
        overall_score = (
            vol_score * 0.25 +
            liquidity_score * 0.20 +
            trend_score * 0.20 +
            ml_score * 0.20 +
            opportunity_score * 0.15
        ) * 100
        
        self.metrics['volatility_score'] = vol_score * 100
        self.metrics['liquidity_score'] = liquidity_score * 100
        self.metrics['trend_score'] = trend_score * 100
        self.metrics['ml_score'] = ml_score * 100
        self.metrics['opportunity_score'] = opportunity_score * 100
        self.metrics['overall_score'] = overall_score
        
        # Determine rating
        if overall_score >= 70:
            self.metrics['rating'] = '⭐⭐⭐ EXCELLENT'
        elif overall_score >= 60:
            self.metrics['rating'] = '⭐⭐ GOOD'
        elif overall_score >= 50:
            self.metrics['rating'] = '⭐ FAIR'
        else:
            self.metrics['rating'] = '❌ POOR'


def main():
    """Analyze all available symbols"""
    print("═══════════════════════════════════════════════════════════════════")
    print("SYMBOL SUITABILITY ANALYSIS FOR AI TRADING")
    print("═══════════════════════════════════════════════════════════════════\n")
    
    # Find all CSV files
    csv_files = glob.glob('*_m1_historical_data.csv')
    
    if not csv_files:
        print("❌ No historical data files found!")
        print("   Run ExportAllSymbolsData.mq5 in MT5 first")
        return
        
    print(f"Found {len(csv_files)} symbols to analyze\n")
    
    # Analyze each symbol
    results = []
    
    for csv_file in sorted(csv_files):
        analyzer = SymbolAnalyzer(csv_file)
        metrics = analyzer.analyze()
        
        if metrics:
            metrics['symbol'] = analyzer.symbol
            results.append(metrics)
            
    if not results:
        print("❌ No symbols could be analyzed")
        return
        
    # Create DataFrame and sort by overall score
    df = pd.DataFrame(results)
    df = df.sort_values('overall_score', ascending=False)
    
    # Display results
    print("\n" + "═"*100)
    print("SYMBOL RANKINGS")
    print("═"*100 + "\n")
    
    print(f"{'Rank':<6} {'Symbol':<10} {'Score':<8} {'Rating':<20} {'Vol%':<8} {'Trend':<8} {'ML':<8} {'Opportunity':<12}")
    print("-" * 100)
    
    for idx, row in df.iterrows():
        rank = df.index.get_loc(idx) + 1
        print(f"{rank:<6} {row['symbol']:<10} {row['overall_score']:<8.1f} {row['rating']:<20} "
              f"{row['daily_volatility_pct']:<8.2f} {row['trend_score']:<8.1f} "
              f"{row['ml_score']:<8.1f} {row['avg_move_pct']:<12.2f}")
              
    # Detailed analysis for top symbols
    print("\n" + "═"*100)
    print("DETAILED ANALYSIS - TOP SYMBOLS")
    print("═"*100 + "\n")
    
    for idx, row in df.head(10).iterrows():
        print(f"\n{'='*70}")
        print(f"{row['symbol']} - {row['rating']} (Score: {row['overall_score']:.1f}/100)")
        print(f"{'='*70}")
        print(f"Volatility:")
        print(f"  • Daily Volatility: {row['daily_volatility_pct']:.2f}%")
        print(f"  • Average Daily Range: {row['avg_daily_range_pct']:.2f}%")
        print(f"  • ATR(20): {row['atr_20']:.2f}")
        print(f"\nLiquidity:")
        print(f"  • Average Volume: {row['avg_volume']:,.0f}")
        print(f"  • Volume Consistency: {row['volume_consistency']:.2f}")
        print(f"  • Average Spread: {row['avg_spread_pct']:.3f}%")
        print(f"\nTrend Characteristics:")
        print(f"  • Trend Strength: {row['trend_strength']:.2f}")
        print(f"  • Trend Clarity: {row['trend_clarity']:.2f}")
        print(f"  • Directional Bias: {row['directional_bias']:.2f}")
        print(f"\nML Predictability:")
        print(f"  • Autocorrelation: {row['autocorrelation']:.3f}")
        print(f"  • Pattern Consistency: {row['pattern_consistency']:.2f}")
        print(f"  • Signal/Noise Ratio: {row['signal_noise_ratio']:.4f}")
        print(f"  • Mean Reversion: {row['mean_reversion']:.2f}")
        print(f"\nTrading Opportunity:")
        print(f"  • Average Move: {row['avg_move_pct']:.2f}%")
        print(f"  • Significant Moves: {row['significant_move_freq']:.1%}")
        print(f"  • Momentum Continuation: {row['momentum_continuation']:.2f}")
        
    # Recommendations
    print("\n" + "═"*100)
    print("RECOMMENDATIONS")
    print("═"*100 + "\n")
    
    excellent = df[df['overall_score'] >= 70]
    good = df[(df['overall_score'] >= 60) & (df['overall_score'] < 70)]
    fair = df[(df['overall_score'] >= 50) & (df['overall_score'] < 60)]
    poor = df[df['overall_score'] < 50]
    
    if len(excellent) > 0:
        print(f"⭐⭐⭐ EXCELLENT SYMBOLS ({len(excellent)}) - HIGHLY RECOMMENDED:")
        for symbol in excellent['symbol'].values:
            print(f"   ✅ {symbol}: Train and deploy immediately")
            
    if len(good) > 0:
        print(f"\n⭐⭐ GOOD SYMBOLS ({len(good)}) - RECOMMENDED:")
        for symbol in good['symbol'].values:
            print(f"   ✅ {symbol}: Good candidate for trading")
            
    if len(fair) > 0:
        print(f"\n⭐ FAIR SYMBOLS ({len(fair)}) - USE WITH CAUTION:")
        for symbol in fair['symbol'].values:
            print(f"   ⚠️  {symbol}: May work but monitor closely")
            
    if len(poor) > 0:
        print(f"\n❌ POOR SYMBOLS ({len(poor)}) - NOT RECOMMENDED:")
        for symbol in poor['symbol'].values:
            print(f"   ❌ {symbol}: Skip or use very conservatively")
            
    # Save results
    output_file = f"symbol_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✅ Analysis saved to: {output_file}")
    
    # Strategy-specific recommendations
    print("\n" + "═"*100)
    print("STRATEGY-SPECIFIC RECOMMENDATIONS")
    print("═"*100 + "\n")
    
    print("For AI ML Trading (Current Strategy):")
    print("  Best characteristics:")
    print("  • Moderate volatility (1-3% daily)")
    print("  • Strong trend characteristics")
    print("  • High ML predictability (autocorrelation, patterns)")
    print("  • Frequent trading opportunities")
    print("\n  Top picks from analysis:")
    for symbol in df.head(5)['symbol'].values:
        score = df[df['symbol'] == symbol]['overall_score'].values[0]
        print(f"    {symbol}: {score:.1f}/100")


if __name__ == "__main__":
    main()
