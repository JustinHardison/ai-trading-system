"""
Sniper Entry System - Multi-Timeframe Confluence & Market Structure
Analyzes D1/H4/H1/M1 alignment and support/resistance for high-probability entries
"""

import numpy as np
from typing import Dict, Tuple, List
from loguru import logger


class SniperConfluence:
    """
    Analyzes multi-timeframe confluence and market structure for sniper entries

    Key Features:
    1. Multi-Timeframe Trend Alignment (D1/H4/H1/M1)
    2. Support/Resistance Detection
    3. Supply/Demand Zones
    4. Confluence Scoring
    """

    def __init__(self):
        self.confluence_weights = {
            'd1_trend': 0.30,      # Daily trend most important
            'h4_trend': 0.25,      # 4H trend confirmation
            'h1_structure': 0.25,  # 1H structure (S/R levels)
            'm1_timing': 0.20      # M1 entry timing
        }

    def analyze_timeframe_trend(self, df, timeframe: str) -> Dict:
        """
        Analyze trend for a single timeframe
        Returns: {direction: str, strength: float, ema_alignment: bool}
        """
        # Require minimum bars based on timeframe (not strict 200)
        min_bars = {'D1': 50, 'H4': 100, 'H1': 100, 'M1': 100}.get(timeframe, 100)

        if df is None or len(df) < min_bars:
            # For higher timeframes without data, assume NEUTRAL (not UNKNOWN)
            # This prevents blocking trades due to missing H4/D1 data
            return {'direction': 'NEUTRAL', 'strength': 0.5, 'ema_alignment': False}

        close = np.array(df['close'])

        # EMA 20, 50, 200 for trend detection
        ema_20 = self._ema(close, 20)
        ema_50 = self._ema(close, 50)
        ema_200 = self._ema(close, 200)

        current_price = close[-1]

        # Trend direction based on EMA alignment
        if current_price > ema_20 > ema_50 > ema_200:
            direction = 'BULLISH'
            strength = min(1.0, (current_price - ema_200) / ema_200 * 100)  # % above EMA200
        elif current_price < ema_20 < ema_50 < ema_200:
            direction = 'BEARISH'
            strength = min(1.0, (ema_200 - current_price) / ema_200 * 100)
        elif current_price > ema_200:
            direction = 'BULLISH_WEAK'
            strength = 0.5
        elif current_price < ema_200:
            direction = 'BEARISH_WEAK'
            strength = 0.5
        else:
            direction = 'RANGING'
            strength = 0.0

        ema_alignment = (
            (current_price > ema_20 > ema_50 > ema_200) or  # Bull alignment
            (current_price < ema_20 < ema_50 < ema_200)      # Bear alignment
        )

        logger.debug(f"{timeframe} Trend: {direction} | Strength: {strength:.2f} | EMA Aligned: {ema_alignment}")

        return {
            'direction': direction,
            'strength': strength,
            'ema_alignment': ema_alignment,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'ema_200': ema_200
        }

    def detect_support_resistance(self, df, lookback: int = 100) -> Dict:
        """
        Detect key support and resistance levels using swing highs/lows
        Returns: {support_levels: List, resistance_levels: List, nearest_support: float, nearest_resistance: float}
        """
        if len(df) < lookback:
            lookback = len(df)

        high = np.array(df['high'])[-lookback:]
        low = np.array(df['low'])[-lookback:]
        close = np.array(df['close'])[-lookback:]

        current_price = close[-1]

        # Find swing highs (resistance)
        resistance_levels = []
        for i in range(5, len(high) - 5):
            if high[i] == max(high[i-5:i+6]):  # Local maximum
                resistance_levels.append(high[i])

        # Find swing lows (support)
        support_levels = []
        for i in range(5, len(low) - 5):
            if low[i] == min(low[i-5:i+6]):  # Local minimum
                support_levels.append(low[i])

        # Cluster levels (within 0.1% are same level)
        resistance_levels = self._cluster_levels(resistance_levels, current_price)
        support_levels = self._cluster_levels(support_levels, current_price)

        # Find nearest levels
        resistance_above = [r for r in resistance_levels if r > current_price]
        support_below = [s for s in support_levels if s < current_price]

        nearest_resistance = min(resistance_above) if resistance_above else current_price * 1.02
        nearest_support = max(support_below) if support_below else current_price * 0.98

        # Distance to levels (as %)
        resistance_distance = (nearest_resistance - current_price) / current_price * 100
        support_distance = (current_price - nearest_support) / current_price * 100

        logger.debug(f"S/R Levels: Support {nearest_support:.2f} ({support_distance:.2f}% below) | Resistance {nearest_resistance:.2f} ({resistance_distance:.2f}% above)")

        return {
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'support_distance_pct': support_distance,
            'resistance_distance_pct': resistance_distance
        }

    def calculate_confluence_score(self, mtf_data: Dict, ml_direction: str, ml_confidence: float) -> Dict:
        """
        Calculate overall confluence score based on all factors
        Returns: {confluence_score: float, confluence_factors: List[str], recommendation: str}
        """
        # Work with available timeframes (M1/M5/M15/M30/H1 from EA)
        # Use H1 as major trend, M30 as intermediate, M15/M5 as minor
        if 'h1' not in mtf_data or 'm1' not in mtf_data:
            logger.warning("Missing essential timeframe data (H1/M1) for confluence analysis")
            return {
                'confluence_score': 0.0,
                'confluence_factors': ['Missing H1/M1 data'],
                'recommendation': 'INSUFFICIENT_DATA',
                'adjusted_confidence': ml_confidence,  # No boost if missing data
                'd1_trend': 'UNKNOWN',
                'h4_trend': 'UNKNOWN',
                'h1_structure': {},
                'm1_momentum': 0.0
            }

        # Analyze available timeframes (H1 = major, M30 = intermediate, M15/M5/M1 = minor)
        h1_trend = self.analyze_timeframe_trend(mtf_data.get('h1'), 'H1')
        m30_trend = self.analyze_timeframe_trend(mtf_data.get('m30'), 'M30') if 'm30' in mtf_data else 'NEUTRAL'
        m15_trend = self.analyze_timeframe_trend(mtf_data.get('m15'), 'M15') if 'm15' in mtf_data else 'NEUTRAL'
        m1_trend = self.analyze_timeframe_trend(mtf_data.get('m1'), 'M1')

        # Map to expected names for compatibility
        d1_trend = h1_trend  # Use H1 as major trend
        h4_trend = m30_trend  # Use M30 as intermediate

        # Detect H1 structure (most relevant for entries)
        h1_structure = self.detect_support_resistance(mtf_data['h1'], lookback=100)

        # Calculate confluence score
        confluence_score = 0.0
        confluence_factors = []

        # 1. D1 Trend Alignment (30%)
        if ml_direction == 'BUY' and 'BULLISH' in d1_trend['direction']:
            confluence_score += self.confluence_weights['d1_trend']
            confluence_factors.append(f"✓ D1 Bullish Trend ({d1_trend['strength']:.1f})")
        elif ml_direction == 'SELL' and 'BEARISH' in d1_trend['direction']:
            confluence_score += self.confluence_weights['d1_trend']
            confluence_factors.append(f"✓ D1 Bearish Trend ({d1_trend['strength']:.1f})")
        elif d1_trend['direction'] == 'NEUTRAL':
            # Give 50% credit when D1 data not available (don't penalize)
            confluence_score += self.confluence_weights['d1_trend'] * 0.5
            confluence_factors.append(f"~ D1 Neutral (no data, 50% credit)")
        else:
            confluence_factors.append(f"✗ D1 Trend Mismatch (D1:{d1_trend['direction']} vs ML:{ml_direction})")

        # 2. H4 Trend Confirmation (25%)
        if ml_direction == 'BUY' and 'BULLISH' in h4_trend['direction']:
            confluence_score += self.confluence_weights['h4_trend']
            confluence_factors.append(f"✓ H4 Bullish Trend ({h4_trend['strength']:.1f})")
        elif ml_direction == 'SELL' and 'BEARISH' in h4_trend['direction']:
            confluence_score += self.confluence_weights['h4_trend']
            confluence_factors.append(f"✓ H4 Bearish Trend ({h4_trend['strength']:.1f})")
        elif h4_trend['direction'] == 'NEUTRAL':
            # Give 50% credit when H4 data not available (don't penalize)
            confluence_score += self.confluence_weights['h4_trend'] * 0.5
            confluence_factors.append(f"~ H4 Neutral (no data, 50% credit)")
        else:
            confluence_factors.append(f"✗ H4 Trend Mismatch (H4:{h4_trend['direction']} vs ML:{ml_direction})")

        # 3. H1 Structure (25%) - Price near support (BUY) or resistance (SELL)
        if ml_direction == 'BUY' and h1_structure['support_distance_pct'] < 0.5:  # Within 0.5% of support
            confluence_score += self.confluence_weights['h1_structure']
            confluence_factors.append(f"✓ Near H1 Support ({h1_structure['support_distance_pct']:.2f}% away)")
        elif ml_direction == 'SELL' and h1_structure['resistance_distance_pct'] < 0.5:  # Within 0.5% of resistance
            confluence_score += self.confluence_weights['h1_structure']
            confluence_factors.append(f"✓ Near H1 Resistance ({h1_structure['resistance_distance_pct']:.2f}% away)")
        else:
            confluence_factors.append(f"✗ Not at H1 structure level")

        # 4. M1 Timing (20%) - Recent momentum in ML direction
        m1_close = np.array(mtf_data['m1']['close'])
        if len(m1_close) >= 10:
            recent_change = (m1_close[-1] - m1_close[-10]) / m1_close[-10] * 100
            if (ml_direction == 'BUY' and recent_change > 0.05) or (ml_direction == 'SELL' and recent_change < -0.05):
                confluence_score += self.confluence_weights['m1_timing']
                confluence_factors.append(f"✓ M1 Momentum ({recent_change:+.2f}%)")
            else:
                confluence_factors.append(f"✗ Weak M1 momentum ({recent_change:+.2f}%)")

        # Final recommendation
        if confluence_score >= 0.75:  # 3+ factors aligned
            recommendation = 'SNIPER_ENTRY'  # High confluence - take the shot!
        elif confluence_score >= 0.50:  # 2 factors aligned
            recommendation = 'GOOD_ENTRY'  # Decent setup
        elif confluence_score >= 0.25:  # 1 factor aligned
            recommendation = 'WEAK_ENTRY'  # Risky
        else:
            recommendation = 'NO_ENTRY'  # Against all timeframes - don't trade

        # Boost ML confidence based on confluence
        adjusted_confidence = ml_confidence * (1.0 + confluence_score * 0.3)  # Up to 30% boost

        logger.info(f"🎯 CONFLUENCE ANALYSIS:")
        logger.info(f"   Score: {confluence_score:.2f} ({int(confluence_score*100)}%)")
        logger.info(f"   Recommendation: {recommendation}")
        logger.info(f"   ML Confidence: {ml_confidence:.1f}% → {adjusted_confidence:.1f}% (after confluence)")
        for factor in confluence_factors:
            logger.info(f"   {factor}")

        return {
            'confluence_score': confluence_score,
            'confluence_factors': confluence_factors,
            'recommendation': recommendation,
            'adjusted_confidence': adjusted_confidence,
            'd1_trend': d1_trend['direction'],
            'h4_trend': h4_trend['direction'],
            'h1_structure': h1_structure,
            'm1_momentum': recent_change if len(m1_close) >= 10 else 0.0
        }

    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate EMA for last value"""
        if len(data) < period:
            return data[-1]
        alpha = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def _cluster_levels(self, levels: List[float], current_price: float, tolerance_pct: float = 0.1) -> List[float]:
        """Cluster price levels within tolerance%"""
        if not levels:
            return []

        levels = sorted(levels)
        clustered = []
        current_cluster = [levels[0]]

        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_price * 100 < tolerance_pct:
                current_cluster.append(level)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]

        clustered.append(np.mean(current_cluster))
        return clustered
